#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
estilo_a_json.py — Exporta el estado actual del estilo a datos/estilo_actual.json

Reutiliza el parser de gen_tipos_linea.py. Añade lo que el editor web necesita
y el parser original no expone:
  - NightcustomColor (gen_tipos_linea solo saca DaycustomColor)
  - editable_pid: qué carácter del bitmap recibe el override de color
    (es el primer color no transparente; cambiarlo es lo que el usuario
     hace al editar "color día/noche")
  - pixel_rows / color_table: para que el navegador regenere el SVG en vivo

El editor NUNCA toca rando.txt (CP1252). Solo produce un JSON de colores que
aplicar_estilo.py traduce de vuelta al TYP.

Uso:
    python3 estilo_a_json.py
"""
import json
import re
from pathlib import Path

import gen_tipos_linea as gtl  # mismo directorio; resuelve en runtime

REPO = Path(__file__).resolve().parent
RANDO = REPO / "style" / "rando.txt"
LINES = REPO / "style" / "rando" / "lines"
OUT = REPO / "datos" / "estilo_actual.json"


def night_color_por_tipo(rando_path: Path) -> dict:
    """Mapa type(hex lower) -> NightcustomColor (#RRGGBB) o None."""
    contenido = rando_path.read_bytes().decode("cp1252").replace("\r\n", "\n")
    bloques = re.findall(r"\[_line\](.*?)\[end\]", contenido,
                         re.IGNORECASE | re.DOTALL)
    resultado = {}
    for b in bloques:
        mt = re.search(r"^Type=(\S+)", b, re.MULTILINE)
        if not mt:
            continue
        tipo = mt.group(1).strip().lower()
        mn = re.search(r"^NightcustomColor:(#[0-9A-Fa-f]{6})", b, re.MULTILINE)
        resultado[tipo] = mn.group(1).upper() if mn else None
    return resultado


def limpiar_cond(cond: str) -> str:
    """Limpia la condición OSM de residuos del parser de gen_tipos_linea.

    parse_lines_style elimina bloques {...} con un regex que no maneja
    comillas ni llaves anidadas; deja restos como "... '}" o "... }".
    Aquí los quitamos para que el editor muestre condiciones limpias.
    """
    c = re.sub(r"\{[^{}]*\}", "", cond)        # bloques bien formados
    c = re.sub(r"\{.*$", "", c)                # bloque abierto sin cerrar
    c = c.replace("}", "").replace("'", "").replace('"', "")
    c = re.sub(r"\s+", " ", c).strip()
    return c


def editable_pid(info: dict):
    """El pixel-char cuyo color se sustituye con Day/NightcustomColor.

    Es el primer color no transparente en color_order — la misma regla que
    aplica parse_block para el override. Si la línea es sólida (sin bitmap)
    no hay pid: el color editable es directamente day/night.
    """
    for pid, col in info["color_order"]:
        if col is not None:
            return pid
    return None


def main() -> None:
    line_types = gtl.parse_rando_lines(str(RANDO))
    type_info_map = gtl.parse_lines_style(str(LINES))
    night_map = night_color_por_tipo(RANDO)

    tipos = []
    for info in line_types:
        t = info["type"]
        sec = gtl.classify(info)
        pid = editable_pid(info)

        osm_entries = gtl.build_osm_summary(type_info_map, t)
        # Resolución mínima: el menor número que aparezca en las reglas
        resoluciones = []
        for _, res in osm_entries:
            for r in re.findall(r"\d+", res or ""):
                resoluciones.append(int(r))
        res_min = min(resoluciones) if resoluciones else None

        tipos.append({
            "type": t,
            "name": info["name"] or "(sin nombre)",
            "section": sec,
            "section_label": gtl.SECTION_LABELS.get(sec, sec),
            "featured": t.lower() in gtl.FEATURED_TYPES,
            "has_bitmap": info["has_bitmap"],
            "line_width": info["line_width"],
            "custom_color_active": info["custom_color_active"],
            # Colores editables por el usuario:
            "day_color": info["day_custom_color"],
            "night_color": night_map.get(t.lower()),
            # Color efectivo que se muestra hoy:
            "main_color": info["main_color"],
            # Geometría del bitmap (para regenerar SVG en el navegador):
            "W": info["W"], "H": info["H"], "N": info["N"], "CPP": info["CPP"],
            "editable_pid": pid,
            "color_table": info["color_table"],
            "pixel_rows": info["pixel_rows"] if info["has_bitmap"] else [],
            # SVG pre-renderizado del estado actual (render inicial rápido):
            "svg": (gtl.make_svg_bitmap(info) if info["has_bitmap"]
                    else gtl.make_svg_solid(info)),
            # Reglas OSM que activan el tipo:
            "osm_rules": [
                {"cond": limpiar_cond(c), "res": r}
                for c, r in osm_entries
                if limpiar_cond(c)
            ],
            "res_min": res_min,
        })

    # Orden estable por sección (orden del editor) y luego por type
    orden_sec = {s: i for i, s in enumerate(gtl.SECTION_ORDER)}
    tipos.sort(key=lambda x: (orden_sec.get(x["section"], 99),
                              int(x["type"], 16)))

    salida = {
        "fuente": "style/rando.txt",
        "total": len(tipos),
        "con_bitmap": sum(1 for x in tipos if x["has_bitmap"]),
        "solidos": sum(1 for x in tipos if not x["has_bitmap"]),
        "secciones": [
            {"id": s, "label": gtl.SECTION_LABELS.get(s, s)}
            for s in gtl.SECTION_ORDER
            if any(x["section"] == s for x in tipos)
        ],
        "tipos": tipos,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(salida, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    print(f"Escrito {OUT}")
    print(f"  {salida['total']} tipos "
          f"({salida['con_bitmap']} con bitmap, {salida['solidos']} sólidos)")
    print(f"  Secciones: {[s['id'] for s in salida['secciones']]}")
    # Aviso de tipos sin ningún color editable (ni day ni night ni pid)
    sin_color = [x["type"] for x in tipos
                 if not x["day_color"] and not x["night_color"]
                 and x["editable_pid"] is None]
    if sin_color:
        print(f"  Aviso: {len(sin_color)} tipos sin color editable "
              f"(p.ej. {sin_color[:5]})")


if __name__ == "__main__":
    main()
