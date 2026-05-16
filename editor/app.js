/* =====================================================
   Garmin Map Editor - app.js
   Vanilla JS, sin framework, sin build.
   ===================================================== */

'use strict';

// -------------------------------------------------------
// ESTADO GLOBAL
// -------------------------------------------------------
const estado = {
  extractos: [],         // datos crudos de extractos_geofabrik.json
  estilo: null,          // datos crudos de estilo_actual.json
  poligono: null,        // L.Polygon dibujado (o null)
  poligonoCoords: null,  // Array de {lat, lng} del poligono
  extractosSeleccionados: new Set(), // ids de extractos seleccionados
  extractosFiltrados: [], // extractos visibles segun filtro
  colorMap: {},           // type -> { day: '#RRGGBB', night: '#RRGGBB' } (valores actuales)
  mapaLayers: {},         // id -> L.Rectangle de extracto en el mapa
  mapaBbox: null,         // L.Rectangle del bbox del poligono (debug)
};

// -------------------------------------------------------
// UTILIDADES
// -------------------------------------------------------

function sanitizarId(nombre) {
  return nombre
    .toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '') // quitar tildes
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    || 'zona';
}

function colorToHexMayus(hex) {
  if (!hex) return null;
  return hex.toUpperCase();
}

function bboxDePoligono(coords) {
  if (!coords || coords.length === 0) return null;
  let sur = Infinity, norte = -Infinity, oeste = Infinity, este = -Infinity;
  for (const c of coords) {
    const lat = c.lat !== undefined ? c.lat : c[0];
    const lng = c.lng !== undefined ? c.lng : c[1];
    if (lat < sur) sur = lat;
    if (lat > norte) norte = lat;
    if (lng < oeste) oeste = lng;
    if (lng > este) este = lng;
  }
  return { sur, norte, oeste, este };
}

function bboxDeExtractos(extractos) {
  if (!extractos || extractos.length === 0) return null;
  let sur = Infinity, norte = -Infinity, oeste = Infinity, este = -Infinity;
  for (const e of extractos) {
    if (e.bbox.sur < sur) sur = e.bbox.sur;
    if (e.bbox.norte > norte) norte = e.bbox.norte;
    if (e.bbox.oeste < oeste) oeste = e.bbox.oeste;
    if (e.bbox.este > este) este = e.bbox.este;
  }
  return { sur, norte, oeste, este };
}

function bboxsIntersecan(b1, b2) {
  // True si los dos bounding boxes se solapan
  return !(b1.oeste > b2.este || b1.este < b2.oeste ||
           b1.sur > b2.norte || b1.norte < b2.sur);
}

function formatNum(n) {
  return n.toFixed(5);
}

function hoy() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

// Convierte E-notation a decimal string con 7 decimales (formato .poly)
function toPolyNum(n) {
  return n.toFixed(7).replace(/(\.\d+?)0+$/, '$1').padStart(15, ' ');
}

// -------------------------------------------------------
// PREVIEW SVG
// -------------------------------------------------------

/**
 * Genera el SVG de preview para un tipo, aplicando el color actual.
 * Para bitmaps: reproduce pixel_rows con el color actualizado.
 * Para solidos: una linea del color dia.
 */
function generarSVG(tipo, dayColor, nightColor) {
  const W_SVG = 280;
  const PX = 4; // pixels de 4x4

  if (tipo.has_bitmap && tipo.pixel_rows && tipo.pixel_rows.length > 0) {
    const H = tipo.pixel_rows.length;
    const W = tipo.pixel_rows[0].length;
    const H_SVG = H * PX;

    // Construir tabla de colores con el color editado
    const ctable = Object.assign({}, tipo.color_table);
    if (tipo.editable_pid !== null && dayColor !== null) {
      ctable[tipo.editable_pid] = dayColor;
    }

    // Calcular cuantas repeticiones horizontales caben
    const patternW = W * PX;
    const reps = Math.ceil(W_SVG / patternW);

    let rects = '';
    for (let row = 0; row < H; row++) {
      for (let rep = 0; rep < reps; rep++) {
        for (let col = 0; col < W; col++) {
          const pid = tipo.pixel_rows[row][col];
          const color = ctable[pid];
          if (color === null || color === undefined) continue; // transparente
          const x = rep * patternW + col * PX;
          const y = row * PX;
          if (x >= W_SVG) continue;
          const w = Math.min(PX, W_SVG - x);
          rects += `<rect x="${x}" y="${y}" width="${w}" height="${PX}" fill="${color}"/>`;
        }
      }
    }

    return `<svg xmlns="http://www.w3.org/2000/svg" width="${W_SVG}" height="${H_SVG}" style="display:block;border-radius:3px;">` +
      `<rect width="${W_SVG}" height="${H_SVG}" fill="var(--bg-preview)"/>` +
      rects +
      `</svg>`;
  } else {
    // Solido
    const lw = Math.max(1, tipo.line_width || 2);
    const color = dayColor || tipo.main_color || '#888888';
    const H_SVG = Math.max(12, lw + 8);
    const y = H_SVG / 2;
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${W_SVG}" height="${H_SVG}" style="display:block;border-radius:3px;">` +
      `<rect width="${W_SVG}" height="${H_SVG}" fill="var(--bg-preview)"/>` +
      `<line x1="8" y1="${y}" x2="${W_SVG - 8}" y2="${y}" stroke="${color}" stroke-width="${lw}" stroke-linecap="round"/>` +
      `</svg>`;
  }
}

// -------------------------------------------------------
// MAPA LEAFLET
// -------------------------------------------------------
let map;

function inicializarMapa() {
  map = L.map('map').setView([40, -3], 5);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 18,
  }).addTo(map);

  // Geoman: solo herramienta de poligono y edicion
  map.pm.addControls({
    position: 'topleft',
    drawMarker: false,
    drawCircleMarker: false,
    drawPolyline: false,
    drawRectangle: false,
    drawCircle: false,
    drawText: false,
    drawPolygon: true,
    editMode: true,
    dragMode: true,
    cutPolygon: false,
    removalMode: true,
    rotateMode: false,
  });

  // Cuando se crea un poligono
  map.on('pm:create', function(e) {
    if (estado.poligono) {
      map.removeLayer(estado.poligono);
    }
    estado.poligono = e.layer;
    actualizarPoligono();

    // Escuchar ediciones del poligono
    e.layer.on('pm:edit', actualizarPoligono);
    e.layer.on('pm:drag', actualizarPoligono);
  });

  // Cuando se elimina una capa
  map.on('pm:remove', function(e) {
    if (e.layer === estado.poligono) {
      estado.poligono = null;
      estado.poligonoCoords = null;
      actualizarBboxDisplay(null);
      actualizarInterseccionExtractos();
    }
  });
}

function actualizarPoligono() {
  if (!estado.poligono) return;
  const latlngs = estado.poligono.getLatLngs();
  // Leaflet puede anidar en arrays
  const coords = Array.isArray(latlngs[0]) ? latlngs[0] : latlngs;
  estado.poligonoCoords = coords.map(c => ({ lat: c.lat, lng: c.lng }));
  const bbox = bboxDePoligono(estado.poligonoCoords);
  actualizarBboxDisplay(bbox);
  actualizarInterseccionExtractos();
}

function actualizarBboxDisplay(bbox) {
  const el = document.getElementById('bbox-display');
  if (!bbox) {
    el.textContent = 'Dibuja un poligono en el mapa para ver el bounding box.';
    return;
  }
  el.innerHTML = `
    <table style="width:100%;font-size:0.78rem;">
      <tr><td style="color:var(--fg3)">Sur:</td><td>${formatNum(bbox.sur)}</td></tr>
      <tr><td style="color:var(--fg3)">Norte:</td><td>${formatNum(bbox.norte)}</td></tr>
      <tr><td style="color:var(--fg3)">Oeste:</td><td>${formatNum(bbox.oeste)}</td></tr>
      <tr><td style="color:var(--fg3)">Este:</td><td>${formatNum(bbox.este)}</td></tr>
    </table>
  `;
}

// -------------------------------------------------------
// CARGA DE DATOS
// -------------------------------------------------------

async function cargarDatos() {
  const errEl = document.getElementById('error-global');

  try {
    const [resExt, resEstilo] = await Promise.all([
      fetch('../datos/extractos_geofabrik.json'),
      fetch('../datos/estilo_actual.json'),
    ]);

    if (!resExt.ok) throw new Error(`No se pudo cargar extractos_geofabrik.json (HTTP ${resExt.status})`);
    if (!resEstilo.ok) throw new Error(`No se pudo cargar estilo_actual.json (HTTP ${resEstilo.status})`);

    const dataExt = await resExt.json();
    const dataEstilo = await resEstilo.json();

    estado.extractos = dataExt.extractos;
    estado.estilo = dataEstilo;

    // Inicializar colorMap con los valores actuales del JSON
    estado.colorMap = {};
    for (const tipo of dataEstilo.tipos) {
      estado.colorMap[tipo.type] = {
        day: tipo.day_color,
        night: tipo.night_color,
      };
    }

    inicializarMapa();
    inicializarExtractos();
    inicializarEstilo();
    inicializarGenerar();

  } catch (err) {
    errEl.style.display = 'block';
    errEl.textContent = 'Error al cargar datos: ' + err.message +
      '. Asegurate de servir la aplicacion con un servidor HTTP (python3 -m http.server).';
  }
}

// -------------------------------------------------------
// PESTAÑA 1 - ZONA / EXTRACTOS
// -------------------------------------------------------

// Grupo de padres que se muestran por defecto
const DEFAULT_PADRES = new Set(['spain', 'france', 'andorra', 'europe/andorra']);

function padreEsDefault(padre, id) {
  // andorra tiene padre "europe" pero lo consideramos default por proximidad
  return padre === 'spain' || padre === 'france' || id === 'andorra';
}

function obtenerExtractosFiltrados() {
  const filtro = document.getElementById('filtro-padre').value;
  return estado.extractos.filter(e => {
    if (filtro === 'all') return true;
    if (filtro === 'default') return padreEsDefault(e.padre, e.id);
    if (filtro === 'spain') return e.padre === 'spain' || e.id === 'spain';
    if (filtro === 'france') return e.padre === 'france' || e.id === 'france';
    if (filtro === 'europe') return e.padre === 'europe' || e.padre === 'spain' || e.padre === 'france';
    return true;
  });
}

function inicializarExtractos() {
  // Pintar bboxes en el mapa
  pintarExtractosEnMapa();

  // Listener del filtro
  document.getElementById('filtro-padre').addEventListener('change', () => {
    pintarExtractosEnMapa();
    renderListaExtractos();
    actualizarInterseccionExtractos();
  });

  // Renderizar lista
  renderListaExtractos();

  // Listeners de campos de zona
  document.getElementById('nombre-zona').addEventListener('input', () => {
    const id = sanitizarId(document.getElementById('nombre-zona').value);
    document.getElementById('id-preview').textContent = id || '—';
  });

  document.getElementById('mapid-base').addEventListener('input', () => {
    const val = parseInt(document.getElementById('mapid-base').value, 10);
    const warnEl = document.getElementById('mapid-warn');
    if (val === 889 || val === 890) {
      warnEl.style.display = '';
      warnEl.textContent = `AVISO: el ID ${val} esta reservado (pirineos). Usa otro.`;
    } else {
      warnEl.style.display = 'none';
    }
  });
}

function pintarExtractosEnMapa() {
  // Eliminar capas previas
  for (const id in estado.mapaLayers) {
    map.removeLayer(estado.mapaLayers[id]);
  }
  estado.mapaLayers = {};

  const filtrados = obtenerExtractosFiltrados();
  estado.extractosFiltrados = filtrados;

  for (const ext of filtrados) {
    const b = ext.bbox;
    const rect = L.rectangle(
      [[b.sur, b.oeste], [b.norte, b.este]],
      {
        color: '#2563eb',
        weight: 1,
        fillColor: '#2563eb',
        fillOpacity: 0.07,
      }
    );
    rect.bindTooltip(ext.nombre_es, { sticky: true });
    rect.addTo(map);
    estado.mapaLayers[ext.id] = rect;

    // Click en rectangulo = toggle seleccion
    rect.on('click', () => {
      toggleExtracto(ext.id, !estado.extractosSeleccionados.has(ext.id));
    });
  }
}

function actualizarInterseccionExtractos() {
  if (!estado.poligonoCoords) {
    // Sin poligono, no cambiamos seleccion automatica
    renderListaExtractos();
    return;
  }

  const bbox = bboxDePoligono(estado.poligonoCoords);
  if (!bbox) return;

  // Marcar como seleccionados los que intersectan
  for (const ext of estado.extractosFiltrados) {
    if (bboxsIntersecan(bbox, ext.bbox)) {
      estado.extractosSeleccionados.add(ext.id);
    }
  }

  renderListaExtractos();
  actualizarResaltadoMapa();
}

function toggleExtracto(id, seleccionado) {
  if (seleccionado) {
    estado.extractosSeleccionados.add(id);
  } else {
    estado.extractosSeleccionados.delete(id);
  }
  renderListaExtractos();
  actualizarResaltadoMapa();
}

function actualizarResaltadoMapa() {
  for (const [id, rect] of Object.entries(estado.mapaLayers)) {
    if (estado.extractosSeleccionados.has(id)) {
      rect.setStyle({ color: '#16a34a', fillColor: '#16a34a', fillOpacity: 0.18, weight: 2 });
    } else {
      rect.setStyle({ color: '#2563eb', fillColor: '#2563eb', fillOpacity: 0.07, weight: 1 });
    }
  }
}

function renderListaExtractos() {
  const lista = document.getElementById('extractos-lista');
  const filtrados = estado.extractosFiltrados;

  if (filtrados.length === 0) {
    lista.innerHTML = '<div style="padding:10px;color:var(--fg3);font-size:0.8rem;">Sin extractos para este filtro.</div>';
    document.getElementById('num-extractos').textContent = 0;
    return;
  }

  // Ordenar: seleccionados primero, luego alfabetico
  const ordenados = [...filtrados].sort((a, b) => {
    const sa = estado.extractosSeleccionados.has(a.id);
    const sb = estado.extractosSeleccionados.has(b.id);
    if (sa && !sb) return -1;
    if (!sa && sb) return 1;
    return a.nombre_es.localeCompare(b.nombre_es, 'es');
  });

  lista.innerHTML = '';
  for (const ext of ordenados) {
    const sel = estado.extractosSeleccionados.has(ext.id);
    const item = document.createElement('div');
    item.className = 'extracto-item' + (sel ? ' intersecta' : '');
    item.innerHTML = `
      <input type="checkbox" ${sel ? 'checked' : ''} data-id="${ext.id}">
      <span class="extracto-nombre">${ext.nombre_es}</span>
      <span class="extracto-padre">${ext.padre}</span>
    `;
    item.querySelector('input').addEventListener('change', (ev) => {
      toggleExtracto(ext.id, ev.target.checked);
    });
    item.addEventListener('click', (ev) => {
      if (ev.target.tagName !== 'INPUT') {
        // Click en la fila centra el mapa en el extracto
        const b = ext.bbox;
        map.fitBounds([[b.sur, b.oeste], [b.norte, b.este]]);
      }
    });
    lista.appendChild(item);
  }

  const numSel = estado.extractosSeleccionados.size;
  document.getElementById('num-extractos').textContent = numSel;
}

// -------------------------------------------------------
// PESTAÑA 2 - ESTILO
// -------------------------------------------------------

function inicializarEstilo() {
  const scroll = document.getElementById('estilo-scroll');
  scroll.innerHTML = '';

  const data = estado.estilo;
  const secciones = data.secciones;
  const tipos = data.tipos;

  // Agrupar tipos por seccion
  const porSeccion = {};
  for (const sec of secciones) {
    porSeccion[sec.id] = { label: sec.label, featured: [], resto: [] };
  }

  for (const tipo of tipos) {
    const sec = porSeccion[tipo.section];
    if (!sec) continue;
    if (tipo.featured) {
      sec.featured.push(tipo);
    } else {
      sec.resto.push(tipo);
    }
  }

  for (const sec of secciones) {
    const grupo = porSeccion[sec.id];
    const todosLosTipos = [...grupo.featured, ...grupo.resto];
    if (todosLosTipos.length === 0) continue;

    const card = document.createElement('div');
    card.className = 'seccion-card';

    const header = document.createElement('div');
    header.className = 'seccion-header';
    header.innerHTML = `<h2>${sec.label}</h2><span class="seccion-toggle">&#9660;</span>`;
    header.addEventListener('click', () => {
      const body = card.querySelector('.seccion-body');
      const collapsed = body.classList.toggle('hidden');
      header.classList.toggle('collapsed', collapsed);
    });
    card.appendChild(header);

    const body = document.createElement('div');
    body.className = 'seccion-body';

    for (const tipo of todosLosTipos) {
      body.appendChild(crearFilaTipo(tipo));
    }

    card.appendChild(body);
    scroll.appendChild(card);
  }

  actualizarBadgeCambios();

  document.getElementById('btn-restaurar-todo').addEventListener('click', () => {
    for (const tipo of data.tipos) {
      estado.colorMap[tipo.type] = {
        day: tipo.day_color,
        night: tipo.night_color,
      };
    }
    // Redibujar todas las filas
    document.querySelectorAll('.tipo-row').forEach(row => {
      const t = row._tipo;
      if (!t) return;
      const dayInput = row.querySelector('[data-campo="day"]');
      const nightInput = row.querySelector('[data-campo="night"]');
      if (dayInput && t.day_color) dayInput.value = t.day_color;
      if (nightInput && t.night_color) nightInput.value = t.night_color;
      actualizarPreviewYEstado(row, t);
    });
    actualizarBadgeCambios();
  });
}

function crearFilaTipo(tipo) {
  const row = document.createElement('div');
  row.className = 'tipo-row' + (tipo.featured ? ' featured' : '');
  row._tipo = tipo;

  const colorActual = estado.colorMap[tipo.type];
  const dayColor = colorActual.day;
  const nightColor = colorActual.night;

  // Preview SVG (reducido a 140px)
  const svgOriginal = generarSVG(tipo, dayColor, nightColor);
  const svgSmall = svgOriginal.replace(/width="280"/, 'width="140"').replace(/width="280"/, 'width="140"');

  // Color pickers
  const tieneDay = tipo.day_color !== null;
  const tieneNight = tipo.night_color !== null;

  const dayField = tieneDay
    ? `<input type="color" data-campo="day" value="${dayColor || '#000000'}">`
    : `<span class="no-color">(sin color)</span>`;

  const nightField = tieneNight
    ? `<input type="color" data-campo="night" value="${nightColor || '#000000'}">`
    : `<span class="no-color">(sin color)</span>`;

  row.innerHTML = `
    <div class="tipo-preview" title="${tipo.name}">${svgSmall}</div>
    <div class="tipo-info">
      <div class="tipo-name">${tipo.name}</div>
      <div class="tipo-hex">${tipo.type}</div>
    </div>
    <div class="tipo-colors">
      <div class="color-field">
        <label>Dia:</label>
        ${dayField}
      </div>
      <div class="color-field">
        <label>Noche:</label>
        ${nightField}
      </div>
    </div>
    <div class="tipo-acciones">
      <button class="btn-reset" title="Restaurar colores originales">Restaurar</button>
    </div>
  `;

  // Listeners de color pickers
  const dayInput = row.querySelector('[data-campo="day"]');
  const nightInput = row.querySelector('[data-campo="night"]');

  if (dayInput) {
    dayInput.addEventListener('input', () => {
      estado.colorMap[tipo.type].day = dayInput.value;
      actualizarPreviewYEstado(row, tipo);
      actualizarBadgeCambios();
    });
  }
  if (nightInput) {
    nightInput.addEventListener('input', () => {
      estado.colorMap[tipo.type].night = nightInput.value;
      actualizarPreviewYEstado(row, tipo);
      actualizarBadgeCambios();
    });
  }

  // Boton restaurar
  row.querySelector('.btn-reset').addEventListener('click', () => {
    estado.colorMap[tipo.type] = {
      day: tipo.day_color,
      night: tipo.night_color,
    };
    if (dayInput && tipo.day_color) dayInput.value = tipo.day_color;
    if (nightInput && tipo.night_color) nightInput.value = tipo.night_color;
    actualizarPreviewYEstado(row, tipo);
    actualizarBadgeCambios();
  });

  return row;
}

function actualizarPreviewYEstado(row, tipo) {
  const c = estado.colorMap[tipo.type];
  const svg = generarSVG(tipo, c.day, c.night);
  const svgSmall = svg.replace(/width="280"/, 'width="140"');
  row.querySelector('.tipo-preview').innerHTML = svgSmall;

  // Marcar si esta modificado
  const dayMod = tipo.day_color !== null && c.day !== null && c.day !== tipo.day_color;
  const nightMod = tipo.night_color !== null && c.night !== null && c.night !== tipo.night_color;
  row.classList.toggle('modificado', dayMod || nightMod);
}

function actualizarBadgeCambios() {
  const n = contarCambios();
  document.getElementById('cambios-badge').textContent = n;
}

function contarCambios() {
  if (!estado.estilo) return 0;
  let n = 0;
  for (const tipo of estado.estilo.tipos) {
    const c = estado.colorMap[tipo.type];
    if (!c) continue;
    const dayMod = tipo.day_color !== null && c.day !== null && c.day !== tipo.day_color;
    const nightMod = tipo.night_color !== null && c.night !== null && c.night !== tipo.night_color;
    if (dayMod || nightMod) n++;
  }
  return n;
}

function obtenerCambiosEstilo() {
  const cambios = {};
  if (!estado.estilo) return cambios;
  for (const tipo of estado.estilo.tipos) {
    const c = estado.colorMap[tipo.type];
    if (!c) continue;
    const dayMod = tipo.day_color !== null && c.day !== null && c.day !== tipo.day_color;
    const nightMod = tipo.night_color !== null && c.night !== null && c.night !== tipo.night_color;
    if (dayMod || nightMod) {
      cambios[tipo.type] = {};
      if (dayMod) cambios[tipo.type].day = colorToHexMayus(c.day);
      if (nightMod) cambios[tipo.type].night = colorToHexMayus(c.night);
    }
  }
  return cambios;
}

// -------------------------------------------------------
// PESTAÑA 3 - GENERAR
// -------------------------------------------------------

function inicializarGenerar() {
  document.getElementById('btn-descargar').addEventListener('click', descargarConfiguracion);
}

function actualizarResumenGenerar() {
  const nombre = document.getElementById('nombre-zona').value.trim();
  const id = sanitizarId(nombre);
  const mapid = document.getElementById('mapid-base').value.trim();
  const ram = document.getElementById('ram-java').value;
  const hgt = document.getElementById('fuentes-hgt').value.trim();

  // Bbox
  let bbox = null;
  if (estado.poligonoCoords) {
    bbox = bboxDePoligono(estado.poligonoCoords);
  }
  if (!bbox) {
    const extSel = estado.extractos.filter(e => estado.extractosSeleccionados.has(e.id));
    if (extSel.length > 0) bbox = bboxDeExtractos(extSel);
  }

  document.getElementById('res-id').textContent = id || '—';
  document.getElementById('res-nombre').textContent = nombre || '—';
  document.getElementById('res-mapid').textContent = mapid || '—';
  document.getElementById('res-ram').textContent = ram;
  document.getElementById('res-hgt').textContent = hgt || '—';

  if (bbox) {
    document.getElementById('res-sur').textContent = formatNum(bbox.sur);
    document.getElementById('res-norte').textContent = formatNum(bbox.norte);
    document.getElementById('res-oeste').textContent = formatNum(bbox.oeste);
    document.getElementById('res-este').textContent = formatNum(bbox.este);
  } else {
    ['res-sur','res-norte','res-oeste','res-este'].forEach(i => {
      document.getElementById(i).textContent = '—';
    });
  }

  const numCambios = contarCambios();
  document.getElementById('res-cambios').textContent = `${numCambios} tipo${numCambios !== 1 ? 's' : ''} modificado${numCambios !== 1 ? 's' : ''}`;

  // Extractos
  const extSel = estado.extractos.filter(e => estado.extractosSeleccionados.has(e.id));
  document.getElementById('res-num-ext').textContent = extSel.length;
  const listaEl = document.getElementById('res-extractos-lista');
  if (extSel.length === 0) {
    listaEl.innerHTML = '<span style="color:var(--fg3);font-size:0.8rem;">Ninguno seleccionado.</span>';
  } else {
    listaEl.innerHTML = extSel.map(e =>
      `<div class="resumen-item">${e.nombre_es} — ${e.url}</div>`
    ).join('');
  }

  // Instruccion
  document.getElementById('instruccion-cmd').textContent = `bash crear_mapa.sh ${id || '<id>'}`;

  // Alerta si faltan datos
  const alertaEl = document.getElementById('alerta-generar');
  const errores = [];
  if (!nombre) errores.push('Falta el nombre de la zona.');
  if (!mapid) errores.push('Falta el MAPID_BASE.');
  if (extSel.length === 0) errores.push('No hay extractos OSM seleccionados.');
  if (!bbox) errores.push('No se puede calcular un bounding box (dibuja un poligono o selecciona extractos).');

  if (errores.length > 0) {
    alertaEl.style.display = '';
    alertaEl.textContent = 'Advertencias: ' + errores.join(' | ');
  } else {
    alertaEl.style.display = 'none';
  }
}

// -------------------------------------------------------
// GENERACION DE FICHEROS
// -------------------------------------------------------

function generarConf(id, nombre, bbox, extractos, mapid, ram, hgt) {
  const urls = extractos.map(e => `    "${e.url}"`).join('\n');
  return `# =============================================================================
# zonas/${id}.conf
# Generado con el Editor de Mapas Garmin
# Uso: bash crear_mapa.sh ${id}
# =============================================================================

# Nombre legible que aparecera en el Garmin
NOMBRE_MAPA="${nombre}"

# Bounding box (lat_sur lat_norte lon_oeste lon_este)
BBOX_SUR=${formatNum(bbox.sur)}
BBOX_NORTE=${formatNum(bbox.norte)}
BBOX_OESTE=${formatNum(bbox.oeste)}
BBOX_ESTE=${formatNum(bbox.este)}

# Poligono opcional para recorte fino (relativo al repo)
POLIGONO="zonas/${id}.poly"

# Fuentes OSM a combinar (URLs de Geofabrik o similares)
FUENTES_OSM=(
${urls}
)

# ID base para mkgmap (3 digitos). Cada zona DEBE usar uno unico.
MAPID_BASE="${mapid}"

# RAM para Java (formato -Xmx)
RAM_JAVA="${ram}"
${hgt ? `\n# Fuentes de altimetria\nFUENTES_HGT="${hgt}"` : ''}
`;
}

function generarPoly(id, coords) {
  // Si hay coords de poligono, usarlas; si no, un rectangulo del bbox de extractos
  let lines = `${id}\n1\n`;

  if (coords && coords.length > 0) {
    for (const c of coords) {
      // Formato: "  lon  lat" con notacion E si el valor es muy grande
      lines += `${toPolyNum(c.lng)}  ${toPolyNum(c.lat)}\n`;
    }
    // Cerrar el poligono si no esta cerrado
    const first = coords[0];
    const last = coords[coords.length - 1];
    if (first.lat !== last.lat || first.lng !== last.lng) {
      lines += `${toPolyNum(first.lng)}  ${toPolyNum(first.lat)}\n`;
    }
  }
  lines += 'END\nEND\n';
  return lines;
}

function generarEstiloJson(id, cambios) {
  const obj = {
    zona: id,
    generado: hoy(),
    cambios: cambios,
  };
  return JSON.stringify(obj, null, 2);
}

function descargarBlob(contenido, nombre, tipo) {
  const blob = new Blob([contenido], { type: tipo });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 100);
}

function descargarConfiguracion() {
  const nombre = document.getElementById('nombre-zona').value.trim();
  const id = sanitizarId(nombre);
  const mapid = document.getElementById('mapid-base').value.trim();
  const ram = document.getElementById('ram-java').value;
  const hgt = document.getElementById('fuentes-hgt').value.trim();

  if (!nombre || !id) {
    alert('Introduce un nombre para la zona antes de descargar.');
    return;
  }
  if (!mapid) {
    alert('Introduce un MAPID_BASE antes de descargar.');
    return;
  }

  const extSel = estado.extractos.filter(e => estado.extractosSeleccionados.has(e.id));
  if (extSel.length === 0) {
    alert('Selecciona al menos un extracto OSM.');
    return;
  }

  // Calcular bbox
  let bbox = null;
  if (estado.poligonoCoords && estado.poligonoCoords.length > 0) {
    bbox = bboxDePoligono(estado.poligonoCoords);
  }
  if (!bbox) {
    bbox = bboxDeExtractos(extSel);
  }
  if (!bbox) {
    alert('No se puede calcular el bounding box. Dibuja un poligono o selecciona extractos.');
    return;
  }

  // Generar coords para .poly
  let polyCoords = estado.poligonoCoords;
  if (!polyCoords || polyCoords.length === 0) {
    // Rectangulo del bbox combinado
    polyCoords = [
      { lat: bbox.sur, lng: bbox.oeste },
      { lat: bbox.sur, lng: bbox.este },
      { lat: bbox.norte, lng: bbox.este },
      { lat: bbox.norte, lng: bbox.oeste },
    ];
  }

  const cambios = obtenerCambiosEstilo();

  // Generar y descargar los 3 ficheros
  descargarBlob(
    generarConf(id, nombre, bbox, extSel, mapid, ram, hgt),
    `${id}.conf`,
    'text/plain'
  );

  setTimeout(() => {
    descargarBlob(
      generarPoly(id, polyCoords),
      `${id}.poly`,
      'text/plain'
    );
  }, 150);

  setTimeout(() => {
    descargarBlob(
      generarEstiloJson(id, cambios),
      `${id}.estilo.json`,
      'application/json'
    );
  }, 300);
}

// -------------------------------------------------------
// SISTEMA DE TABS
// -------------------------------------------------------

function inicializarTabs() {
  const botones = document.querySelectorAll('nav.tabs button');
  const contenidos = document.querySelectorAll('.tab-content');

  botones.forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;

      botones.forEach(b => b.classList.remove('active'));
      contenidos.forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      const el = document.getElementById(`tab-${tab}`);
      if (el) el.classList.add('active');

      // Al cambiar a generar, actualizar resumen
      if (tab === 'generar') {
        actualizarResumenGenerar();
      }

      // Invalidar mapa al volver a la tab zona
      if (tab === 'zona' && map) {
        setTimeout(() => map.invalidateSize(), 50);
      }
    });
  });
}

// -------------------------------------------------------
// ARRANQUE
// -------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  inicializarTabs();
  cargarDatos();
});
