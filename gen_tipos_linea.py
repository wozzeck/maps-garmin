#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generates tipos_de_linea.html with real Xpm bitmap previews.
"""
import re
import html as html_module
from collections import defaultdict

# ---------------------------------------------------------------------------
# 1.  Parse rando.txt
# ---------------------------------------------------------------------------

def parse_rando_lines(path):
    with open(path, encoding='cp1252') as f:
        content = f.read().replace('\r\n', '\n').replace('\r', '\n')

    raw_blocks = re.findall(r'\[_line\](.*?)\[end\]', content, re.IGNORECASE | re.DOTALL)

    results = []
    for block in raw_blocks:
        info = parse_block(block)
        if info:
            results.append(info)
    return results


def parse_block(block):
    # --- Type ---
    m = re.search(r'^Type=(\S+)', block, re.MULTILINE)
    if not m:
        return None
    typ = m.group(1).strip()

    # --- Name ---
    nm = re.search(r'^String1=0x01,(.+)', block, re.MULTILINE)
    name = nm.group(1).strip() if nm else ''

    # --- LineWidth ---
    lw = re.search(r'^LineWidth=(\d+)', block, re.MULTILINE)
    line_width = int(lw.group(1)) if lw else 1

    # --- CustomColor ---
    custom_color_active = bool(re.search(r'^CustomColor=DayAndNight', block, re.MULTILINE))
    dc = re.search(r'^DaycustomColor:(#[0-9A-Fa-f]{6})', block, re.MULTILINE)
    day_custom_color = dc.group(1).upper() if dc else None

    # --- Xpm header ---
    xpm_m = re.search(r'^Xpm="(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"', block, re.MULTILINE)
    if not xpm_m:
        return None
    W, H, N, CPP = int(xpm_m.group(1)), int(xpm_m.group(2)), int(xpm_m.group(3)), int(xpm_m.group(4))

    # --- Parse the rest of the Xpm: N color lines, then H pixel rows ---
    # After the Xpm="..." line, gather all quoted strings in order
    quoted_strings = []
    # Find position of Xpm line in block
    xpm_line_end = xpm_m.end()
    rest = block[xpm_line_end:]
    # Extract quoted strings (handle escaped quotes as well)
    for qm in re.finditer(r'"([^"]*)"', rest):
        quoted_strings.append(qm.group(1))
        if len(quoted_strings) >= N + H:
            break

    # Parse color table
    color_table = {}  # pixel_char -> '#RRGGBB' or None (transparent)
    color_order = []  # ordered list of (pixel_char, hex_or_None)

    for i in range(N):
        if i >= len(quoted_strings):
            break
        cline = quoted_strings[i]
        # Format: "ID c #RRGGBB" or "ID c None" where ID is CPP chars
        # CPP is usually 1 or 2
        if CPP == 0:
            # Degenerate: no bitmap
            continue
        pid = cline[:CPP]  # pixel ID
        # Find color spec
        cm = re.search(r'\bc\s+(#[0-9A-Fa-f]{6}|[Nn]one)\b', cline)
        if cm:
            val = cm.group(1)
            if val.lower() == 'none':
                color_table[pid] = None
            else:
                color_table[pid] = val.upper()
        else:
            color_table[pid] = None
        color_order.append((pid, color_table[pid]))

    # Parse pixel rows
    pixel_rows = []
    if W > 0 and H > 0 and CPP > 0:
        for i in range(H):
            idx = N + i
            if idx >= len(quoted_strings):
                break
            row_str = quoted_strings[idx]
            row = []
            for col in range(W):
                start = col * CPP
                end = start + CPP
                if end <= len(row_str):
                    pid = row_str[start:end]
                else:
                    pid = ' ' * CPP  # pad with spaces
                row.append(pid)
            pixel_rows.append(row)

    # Apply DaycustomColor override:
    # Replaces the FIRST non-transparent color in color_table
    effective_color_table = dict(color_table)
    if custom_color_active and day_custom_color:
        for pid, col in color_order:
            if col is not None:  # first non-transparent
                effective_color_table[pid] = day_custom_color
                break

    # Determine "main display color" for solid lines (W=0 H=0)
    main_color = '#888888'
    if W == 0 and H == 0:
        # Solid line: use DaycustomColor if available, else first color in table
        if custom_color_active and day_custom_color:
            main_color = day_custom_color
        elif color_order:
            for pid, col in color_order:
                if col is not None:
                    main_color = col
                    break
    else:
        # Bitmap: first non-transparent color (effective)
        for pid, col in color_order:
            if col is not None:
                main_color = effective_color_table.get(pid, col) or col
                break

    return {
        'type': typ,
        'name': name,
        'line_width': line_width,
        'custom_color_active': custom_color_active,
        'day_custom_color': day_custom_color,
        'W': W,
        'H': H,
        'N': N,
        'CPP': CPP,
        'color_table': color_table,
        'effective_color_table': effective_color_table,
        'color_order': color_order,
        'pixel_rows': pixel_rows,
        'main_color': main_color,
        'has_bitmap': W > 0 and H > 0,
    }


# ---------------------------------------------------------------------------
# 2.  Parse lines style file for OSM tags and resolution
# ---------------------------------------------------------------------------

def parse_lines_style(path):
    with open(path, encoding='utf-8') as f:
        content = f.read()

    # Map type -> list of (condition_text, resolution_text)
    type_info = defaultdict(list)

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.startswith(';'):
            continue
        # Look for [0xTYPE ...resolution XX...]
        refs = re.findall(r'\[0x([0-9a-fA-F]+)[^\]]*\]', line)
        if not refs:
            continue
        # Extract condition (before the first [)
        cond_part = re.split(r'\s*\[', line)[0].strip()
        # Clean up action blocks {...}
        cond_part = re.sub(r'\{[^}]*\}', '', cond_part).strip()
        # Extract resolution from each ref
        for ref in refs:
            typ = '0x' + ref.lower()
            # Find resolution in the bracket
            bracket = re.search(r'\[0x' + ref + r'([^\]]*)\]', line, re.IGNORECASE)
            res = ''
            if bracket:
                rm = re.search(r'resolution\s+([\d\-]+)', bracket.group(1))
                if rm:
                    res = rm.group(1)
            type_info[typ].append((cond_part, res))

    return type_info


# ---------------------------------------------------------------------------
# 3.  Generate SVG preview for a line type
# ---------------------------------------------------------------------------

PREVIEW_WIDTH = 280   # px
PIXEL_SCALE = 4       # each bitmap pixel -> 4 CSS px
MIN_HEIGHT = 8        # minimum preview height px
BG_COLOR_LIGHT = '#f0f4f8'
BG_COLOR_DARK = '#1e293b'


def make_svg_bitmap(info, preview_w=PREVIEW_WIDTH):
    """Return inline SVG string showing the bitmap pattern repeated horizontally."""
    W = info['W']
    H = info['H']
    pixel_rows = info['pixel_rows']
    ect = info['effective_color_table']

    if not pixel_rows or W == 0 or H == 0:
        return make_svg_solid(info, preview_w)

    px = PIXEL_SCALE
    svg_h = H * px
    # Center vertically in a taller box if too small
    box_h = max(svg_h, MIN_HEIGHT)
    y_offset = (box_h - svg_h) // 2

    # Number of bitmap repetitions needed
    reps = (preview_w // (W * px)) + 2

    rects = []
    for row_i, row in enumerate(pixel_rows):
        y = y_offset + row_i * px
        for rep in range(reps):
            for col_i, pid in enumerate(row):
                color = ect.get(pid)
                if color is None:
                    continue  # transparent
                x = (rep * W + col_i) * px
                if x >= preview_w:
                    break
                # Clip to preview width
                w_rect = min(px, preview_w - x)
                rects.append(
                    f'<rect x="{x}" y="{y}" width="{w_rect}" height="{px}" fill="{html_module.escape(color)}"/>'
                )

    rects_str = '\n    '.join(rects)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{preview_w}" height="{box_h}" '
        f'style="display:block;border-radius:4px;">'
        f'\n  <!-- bitmap {W}x{H} px={px} -->'
        f'\n  <rect width="{preview_w}" height="{box_h}" fill="var(--bg-preview)"/>'
        f'\n    {rects_str}'
        f'\n</svg>'
    )
    return svg


def make_svg_solid(info, preview_w=PREVIEW_WIDTH):
    """Return inline SVG for a solid line."""
    color = info['main_color']
    lw = max(2, min(info['line_width'], 12))
    box_h = max(lw + 8, 16)
    y = box_h // 2
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{preview_w}" height="{box_h}" '
        f'style="display:block;border-radius:4px;">'
        f'\n  <rect width="{preview_w}" height="{box_h}" fill="var(--bg-preview)"/>'
        f'\n  <line x1="8" y1="{y}" x2="{preview_w-8}" y2="{y}" '
        f'stroke="{html_module.escape(color)}" stroke-width="{lw}" stroke-linecap="round"/>'
        f'\n</svg>'
    )
    return svg


# ---------------------------------------------------------------------------
# 4.  Section classification
# ---------------------------------------------------------------------------

SECTION_ORDER = [
    'senderos',
    'carreteras',
    'ferreas',
    'hidrografia',
    'curvas',
    'limites',
    'otras',
    'sin_uso',
    'discontinuas',
]

SECTION_LABELS = {
    'senderos': 'Senderos y caminos',
    'carreteras': 'Carreteras y viales',
    'ferreas': 'Vías ferreas y especiales',
    'hidrografia': 'Hidrografía',
    'curvas': 'Curvas de nivel',
    'limites': 'Límites y perímetros',
    'otras': 'Otras líneas',
    'sin_uso': 'Tipos sin uso activo en el mapa',
    'discontinuas': 'Líneas con patrón Xpm (trama real)',
}

# Explicit assignments
TYPE_SECTION = {
    # Senderos
    '0x10': 'senderos',
    '0x10f01': 'senderos',
    '0x10f02': 'senderos',
    '0x10f04': 'senderos',
    '0x10f09': 'senderos',
    '0x10f11': 'senderos',
    '0x10f12': 'senderos',
    '0x10f13': 'senderos',
    '0x10f14': 'senderos',
    '0x10f15': 'senderos',
    '0x11f01': 'senderos',
    '0x11f02': 'senderos',
    '0x11f06': 'otras',   # cerca/valla
    '0x11': 'senderos',
    '0x12': 'senderos',
    '0x13': 'senderos',
    '0x0e': 'senderos',   # carril bici
    '0x0f': 'senderos',   # escalera
    # Carreteras
    '0x01': 'carreteras',
    '0x02': 'carreteras',
    '0x03': 'carreteras',
    '0x04': 'carreteras',
    '0x06': 'carreteras',
    '0x09': 'carreteras',
    '0x0a': 'carreteras',
    '0x0d': 'carreteras',   # túnel
    '0x10f1b': 'carreteras',
    '0x10f16': 'carreteras',
    '0x10f17': 'carreteras',
    '0x10e1c': 'carreteras',  # carretera en construcción
    '0x10f18': 'carreteras',  # acantilado/cliff
    # Ferreas
    '0x10e02': 'ferreas',
    '0x10e03': 'ferreas',
    '0x10e04': 'ferreas',
    '0x10e05': 'ferreas',
    '0x10e06': 'ferreas',
    '0x10e0a': 'ferreas',
    '0x10e0b': 'ferreas',
    '0x10e00': 'ferreas',   # cable transportador
    '0x10e01': 'ferreas',   # teleferico
    '0x1b': 'ferreas',      # ferri
    # Hidrografía
    '0x18': 'hidrografia',
    '0x1f': 'hidrografia',
    '0x26': 'hidrografia',
    '0x10e0d': 'hidrografia',  # cascada
    '0x10e10': 'hidrografia',  # curso subterráneo
    '0x29': 'otras',        # tubería/línea eléctrica
    # Curvas
    '0x20': 'curvas',
    '0x21': 'curvas',
    '0x22': 'curvas',
    # Límites
    '0x10e1e': 'limites',
    '0x10e1f': 'limites',
    # Otras
    '0x10e13': 'otras',    # muro antirruido
    '0x10e19': 'otras',    # talud
    '0x10f07': 'sin_uso',
    '0x10f1f': 'otras',
    # Sin uso
    '0x10f1b': 'carreteras',
}

FEATURED_TYPES = {'0x10f01', '0x10f02', '0x10f04'}


def classify(info):
    t = info['type'].lower()
    if t in TYPE_SECTION:
        return TYPE_SECTION[t]
    # Fallback heuristics
    return 'otras'


# ---------------------------------------------------------------------------
# 5.  Build OSM tag summary for a type
# ---------------------------------------------------------------------------

def build_osm_summary(type_info_map, typ):
    entries = type_info_map.get(typ.lower(), [])
    if not entries:
        return []
    # De-duplicate conditions
    seen = set()
    result = []
    for cond, res in entries:
        key = cond
        if key not in seen:
            seen.add(key)
            result.append((cond, res))
    return result


def format_resolution(res_str):
    if not res_str:
        return ''
    return res_str


# ---------------------------------------------------------------------------
# 6.  Render one card
# ---------------------------------------------------------------------------

def render_card(info, osm_entries):
    typ = info['type']
    name = info['name'] or '(sin nombre)'
    main_color = info['main_color']
    is_featured = typ.lower() in FEATURED_TYPES
    has_bitmap = info['has_bitmap']

    featured_class = ' card-featured' if is_featured else ''
    featured_badge = '<span class="badge-featured">DESTACADO</span>' if is_featured else ''
    bitmap_badge = '<span class="badge-bitmap">Trama Xpm</span>' if has_bitmap else ''

    if has_bitmap:
        svg_html = make_svg_bitmap(info)
    else:
        svg_html = make_svg_solid(info)

    # OSM tags
    osm_rows = ''
    if osm_entries:
        # Show up to 5 conditions
        for cond, res in osm_entries[:5]:
            res_str = f'res.&nbsp;{html_module.escape(res)}' if res else ''
            osm_rows += (
                f'<div class="osm-row">'
                f'<code class="osm-cond">{html_module.escape(cond)}</code>'
                f'{"<span class=res-badge>" + res_str + "</span>" if res_str else ""}'
                f'</div>\n'
            )
        if len(osm_entries) > 5:
            osm_rows += f'<div class="osm-row osm-more">...y {len(osm_entries)-5} reglas más</div>\n'

    # Color swatch
    swatch = f'<span class="color-swatch" style="background:{html_module.escape(main_color)}" title="{html_module.escape(main_color)}"></span>'

    card = f'''<div class="card{featured_class}" id="type-{html_module.escape(typ)}">
  <div class="card-header">
    <div class="card-title-row">
      <span class="type-code">{html_module.escape(typ)}</span>
      <div class="badge-row">{featured_badge}{bitmap_badge}</div>
    </div>
    <div class="card-name">{html_module.escape(name)}</div>
  </div>
  <div class="card-preview">
    {svg_html}
  </div>
  <div class="card-meta">
    <div class="meta-color">{swatch}<span class="color-hex">{html_module.escape(main_color)}</span>
    {"<span class='override-note'>(override DaycustomColor)</span>" if info['custom_color_active'] and info['day_custom_color'] else ""}
    </div>
    {"<div class='bitmap-dims'>Xpm: " + str(info["W"]) + "x" + str(info["H"]) + " px, " + str(info["N"]) + " colores</div>" if has_bitmap else ""}
  </div>
  {"<div class='osm-section'><div class='osm-title'>Reglas OSM</div>" + osm_rows + "</div>" if osm_rows else ""}
</div>'''
    return card


# ---------------------------------------------------------------------------
# 7.  Build TOC
# ---------------------------------------------------------------------------

def build_toc(sections_content):
    items = []
    for sec_id, sec_label, cards in sections_content:
        items.append(
            f'<li><a href="#{sec_id}">{html_module.escape(sec_label)}</a>'
            f' <span class="toc-count">({len(cards)})</span></li>'
        )
    return '<ul class="toc-list">\n' + '\n'.join(items) + '\n</ul>'


# ---------------------------------------------------------------------------
# 8.  Assemble HTML
# ---------------------------------------------------------------------------

CSS = '''
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #f8f9fa;
  --bg-card: #ffffff;
  --bg-section: #eef2f7;
  --bg-preview: #dde4ed;
  --text: #1a1a2e;
  --text-muted: #6c757d;
  --border: #dee2e6;
  --border-card: #d0d7e3;
  --accent: #2563eb;
  --featured-bg: #fffbeb;
  --featured-border: #f59e0b;
  --badge-featured-bg: #d97706;
  --badge-bitmap-bg: #0369a1;
  --code-bg: #f1f5f9;
  --code-text: #1e40af;
  --tag-bg: #dbeafe;
  --tag-text: #1e40af;
  --res-bg: #e0f2fe;
  --res-text: #0369a1;
  --section-title: #1e3a5f;
  --header-bg: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
  --header-text: #ffffff;
  --footer-bg: #1e3a5f;
  --footer-text: #cbd5e1;
  --toc-bg: #ffffff;
  --toc-border: #e2e8f0;
  --override-note: #9333ea;
  --bitmap-dims: #475569;
  --osm-header: #334155;
  --osm-bg: #f8fafc;
  --osm-border: #e2e8f0;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f172a;
    --bg-card: #1e293b;
    --bg-section: #162032;
    --bg-preview: #1a2540;
    --text: #e2e8f0;
    --text-muted: #94a3b8;
    --border: #334155;
    --border-card: #334155;
    --accent: #60a5fa;
    --featured-bg: #1c1608;
    --featured-border: #d97706;
    --badge-featured-bg: #b45309;
    --badge-bitmap-bg: #0c4a6e;
    --code-bg: #0f172a;
    --code-text: #93c5fd;
    --tag-bg: #1e3a5f;
    --tag-text: #93c5fd;
    --res-bg: #0c2340;
    --res-text: #7dd3fc;
    --section-title: #93c5fd;
    --header-bg: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
    --toc-bg: #1e293b;
    --toc-border: #334155;
    --override-note: #c084fc;
    --bitmap-dims: #94a3b8;
    --osm-header: #cbd5e1;
    --osm-bg: #162032;
    --osm-border: #334155;
  }
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
  font-size: 14px;
}

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* Header */
.site-header {
  background: var(--header-bg);
  color: var(--header-text);
  padding: 2rem 1.5rem 1.5rem;
}
.site-header h1 { font-size: 1.6rem; font-weight: 700; margin-bottom: 0.4rem; }
.site-header p { opacity: 0.85; font-size: 0.92rem; }

/* TOC */
.toc-box {
  background: var(--toc-bg);
  border: 1px solid var(--toc-border);
  border-radius: 8px;
  padding: 1.2rem 1.5rem;
  margin: 1.5rem auto;
  max-width: 960px;
}
.toc-box h2 { font-size: 1rem; font-weight: 600; margin-bottom: 0.8rem; color: var(--section-title); }
.toc-list { list-style: none; display: flex; flex-wrap: wrap; gap: 0.4rem 1.5rem; }
.toc-list li { font-size: 0.88rem; }
.toc-count { color: var(--text-muted); font-size: 0.82rem; }

/* Main content */
.main { max-width: 960px; margin: 0 auto; padding: 0 1rem 3rem; }

/* Section */
.section { margin-bottom: 2.5rem; }
.section-header {
  display: flex; align-items: center; gap: 0.8rem;
  padding: 0.7rem 1rem;
  background: var(--bg-section);
  border-radius: 6px;
  margin-bottom: 1rem;
  border-left: 4px solid var(--accent);
}
.section-header h2 { font-size: 1.05rem; font-weight: 700; color: var(--section-title); }
.section-count { font-size: 0.82rem; color: var(--text-muted); margin-left: auto; }

/* Discontinuous section highlight */
.section-discontinua .section-header {
  border-left-color: #7c3aed;
  background: color-mix(in srgb, var(--bg-section) 90%, #7c3aed 10%);
}

/* Cards grid */
.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1rem;
}

/* Card */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.card-featured {
  background: var(--featured-bg);
  border-color: var(--featured-border);
  border-width: 2px;
}

.card-header {
  padding: 0.7rem 0.9rem 0.5rem;
  border-bottom: 1px solid var(--border-card);
}
.card-title-row {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 0.3rem;
}
.type-code {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--code-text);
  background: var(--code-bg);
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
}
.badge-row { display: flex; gap: 0.3rem; flex-wrap: wrap; justify-content: flex-end; }
.badge-featured, .badge-bitmap {
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
  letter-spacing: 0.02em;
}
.badge-featured { background: var(--badge-featured-bg); color: #fff; }
.badge-bitmap { background: var(--badge-bitmap-bg); color: #fff; }

.card-name {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text);
  line-height: 1.3;
}

.card-preview {
  padding: 0.5rem 0.6rem;
  background: var(--bg-preview);
}
.card-preview svg { max-width: 100%; }

.card-meta {
  padding: 0.5rem 0.9rem;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  font-size: 0.82rem;
}
.meta-color { display: flex; align-items: center; gap: 0.4rem; }
.color-swatch {
  display: inline-block;
  width: 14px; height: 14px;
  border-radius: 3px;
  border: 1px solid rgba(0,0,0,0.2);
  flex-shrink: 0;
}
.color-hex {
  font-family: "SFMono-Regular", Consolas, monospace;
  font-size: 0.8rem;
  color: var(--text-muted);
}
.override-note {
  font-size: 0.74rem;
  color: var(--override-note);
  font-style: italic;
}
.bitmap-dims { font-size: 0.78rem; color: var(--bitmap-dims); }

/* OSM section */
.osm-section {
  border-top: 1px solid var(--osm-border);
  background: var(--osm-bg);
  padding: 0.5rem 0.9rem 0.6rem;
  margin-top: auto;
  flex-grow: 1;
}
.osm-title {
  font-size: 0.74rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--osm-header);
  margin-bottom: 0.35rem;
}
.osm-row {
  font-size: 0.76rem;
  margin-bottom: 0.2rem;
  display: flex;
  align-items: flex-start;
  gap: 0.3rem;
  flex-wrap: wrap;
}
.osm-cond {
  background: var(--code-bg);
  color: var(--code-text);
  padding: 0.05rem 0.3rem;
  border-radius: 3px;
  font-size: 0.73rem;
  word-break: break-all;
  flex: 1;
}
.res-badge {
  background: var(--res-bg);
  color: var(--res-text);
  padding: 0.05rem 0.3rem;
  border-radius: 3px;
  font-size: 0.72rem;
  white-space: nowrap;
  flex-shrink: 0;
}
.osm-more { color: var(--text-muted); font-style: italic; }

/* Footer */
.site-footer {
  background: var(--footer-bg);
  color: var(--footer-text);
  text-align: center;
  padding: 1.5rem;
  font-size: 0.85rem;
}
'''

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Tipos de linea del mapa MapRando</title>
  <style>
{css}
  </style>
</head>
<body>

<header class="site-header">
  <h1>Tipos de linea del mapa MapRando</h1>
  <p>Referencia de los {total} tipos de linea definidos en el TYP Garmin (rando.txt).
     Las previsualizaciones con trama muestran el patron Xpm real tal como aparece en el GPS.</p>
</header>

<div class="toc-box">
  <h2>Indice de secciones</h2>
  {toc}
</div>

<main class="main">
{sections_html}
</main>

<footer class="site-footer">
  Generado desde style/rando.txt (TYP Garmin, CP1252) y style/rando/lines (reglas mkgmap).
  {bitmap_count} tipos con patron Xpm real &mdash; {solid_count} tipos solidos.
</footer>

</body>
</html>
'''


def build_html(line_types, type_info_map):
    # Classify into sections
    sec_map = defaultdict(list)
    for info in line_types:
        sec = classify(info)
        sec_map[sec].append(info)

    # Build "discontinuas" section: all with bitmap (regardless of main section)
    discontinuas = [i for i in line_types if i['has_bitmap']]
    discontinuas.sort(key=lambda i: int(i['type'], 16))
    sec_map['discontinuas'] = discontinuas

    # Sort within each section by type number
    for sec in sec_map:
        if sec != 'discontinuas':
            sec_map[sec].sort(key=lambda i: int(i['type'], 16))

    # Build sections content list (ordered)
    sections_content = []
    for sec_id in SECTION_ORDER:
        cards = sec_map.get(sec_id, [])
        if not cards:
            continue
        sections_content.append((sec_id, SECTION_LABELS[sec_id], cards))

    toc_html = build_toc(sections_content)

    sections_html_parts = []
    for sec_id, sec_label, cards in sections_content:
        extra_class = ' section-discontinua' if sec_id == 'discontinuas' else ''
        card_htmls = []
        for info in cards:
            osm_entries = build_osm_summary(type_info_map, info['type'])
            card_htmls.append(render_card(info, osm_entries))

        sec_html = f'''<section class="section{extra_class}" id="{html_module.escape(sec_id)}">
  <div class="section-header">
    <h2>{html_module.escape(sec_label)}</h2>
    <span class="section-count">{len(cards)} tipo{"s" if len(cards) != 1 else ""}</span>
  </div>
  <div class="cards-grid">
    {"".join(card_htmls)}
  </div>
</section>'''
        sections_html_parts.append(sec_html)

    total = len(line_types)
    bitmap_count = sum(1 for i in line_types if i['has_bitmap'])
    solid_count = total - bitmap_count

    html_out = HTML_TEMPLATE.format(
        css=CSS,
        total=total,
        toc=toc_html,
        sections_html='\n'.join(sections_html_parts),
        bitmap_count=bitmap_count,
        solid_count=solid_count,
    )
    return html_out


# ---------------------------------------------------------------------------
# 9.  Main
# ---------------------------------------------------------------------------

def main():
    rando_path = '/home/wzk/ws/maps/maps-garmin/style/rando.txt'
    lines_path = '/home/wzk/ws/maps/maps-garmin/style/rando/lines'
    output_path = '/home/wzk/ws/maps/maps-garmin/tipos_de_linea.html'

    print('Parsing rando.txt ...')
    line_types = parse_rando_lines(rando_path)
    print(f'  {len(line_types)} line types parsed')

    print('Parsing lines style ...')
    type_info_map = parse_lines_style(lines_path)
    print(f'  {len(type_info_map)} types with OSM rules')

    print('Building HTML ...')
    html_out = build_html(line_types, type_info_map)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_out)
    print(f'  Written to {output_path}')

    # Stats
    bitmap_types = [i for i in line_types if i['has_bitmap']]
    print(f'\nStats:')
    print(f'  Total types: {len(line_types)}')
    print(f'  With bitmap: {len(bitmap_types)}')
    print(f'  Solid only:  {len(line_types) - len(bitmap_types)}')

    # Validate HTML
    print('\nValidating HTML ...')
    from html.parser import HTMLParser
    parser = HTMLParser()
    parser.feed(open(output_path).read())
    print('  HTML parser: OK (no exceptions)')

    # Check specific types
    print('\nChecking bitmap types 0x10f12, 0x10f13, 0x10f14, 0x11f01, 0x11f02, 0x11f06:')
    for t in line_types:
        if t['type'] in ['0x10f12', '0x10f13', '0x10f14', '0x11f01', '0x11f02', '0x11f06']:
            print(f'  {t["type"]}: has_bitmap={t["has_bitmap"]}, W={t["W"]}, H={t["H"]}, main_color={t["main_color"]}')


if __name__ == '__main__':
    main()
