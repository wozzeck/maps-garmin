#!/bin/bash
# =============================================================================
# crear_mapa.sh
# Pipeline genérico para generar mapas Garmin para cualquier zona configurada.
# Uso: bash crear_mapa.sh <zona>
#   Ejemplo: bash crear_mapa.sh pirineos
#            bash crear_mapa.sh mallorca
# Ejecutar desde el directorio raíz del repo: /home/wzk/ws/maps/garmincustommap/
# =============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

start_time="$(date +%s)"

# -----------------------------------------------------------------------------
# Función: tiempo transcurrido
# -----------------------------------------------------------------------------
tiempo_transcurrido() {
    local T="$(($(date +%s) - start_time))"
    local D=$((T / 60 / 60 / 24))
    local H=$((T / 60 / 60 % 24))
    local M=$((T / 60 % 60))
    local S=$((T % 60))
    local msg=""
    [ $D -gt 0 ] && msg="${msg}${D} días "
    [ $H -gt 0 ] && msg="${msg}${H} horas "
    [ $M -gt 0 ] && msg="${msg}${M} minutos "
    msg="${msg}${S} segundos"
    echo "Tiempo total: ${msg}"
}

# -----------------------------------------------------------------------------
# Función: mensaje de error y salida
# -----------------------------------------------------------------------------
error() {
    echo "ERROR: $*" >&2
    exit 1
}

# -----------------------------------------------------------------------------
# Función: listar zonas disponibles
# -----------------------------------------------------------------------------
listar_zonas() {
    echo "Zonas disponibles en zonas/:"
    local encontradas=0
    for f in "$REPO_DIR/zonas/"*.conf; do
        [ -f "$f" ] || continue
        local nombre
        nombre="$(basename "$f" .conf)"
        echo "  - $nombre"
        encontradas=$((encontradas + 1))
    done
    if [ "$encontradas" -eq 0 ]; then
        echo "  (ninguna — crea un archivo zonas/<nombre>.conf para empezar)"
    fi
}

# -----------------------------------------------------------------------------
# Validar argumento de zona
# -----------------------------------------------------------------------------
if [ $# -eq 0 ]; then
    echo "Uso: bash crear_mapa.sh <zona>"
    echo ""
    listar_zonas
    exit 1
fi

ZONA="$1"
CONF="$REPO_DIR/zonas/${ZONA}.conf"

if [ ! -f "$CONF" ]; then
    echo "ERROR: No se encontró la configuración para la zona '${ZONA}'." >&2
    echo "  Buscado en: $CONF" >&2
    echo ""
    listar_zonas
    exit 1
fi

# -----------------------------------------------------------------------------
# Cargar configuración de la zona
# -----------------------------------------------------------------------------
# shellcheck source=/dev/null
source "$CONF"

# Validar variables obligatorias
for var in NOMBRE_MAPA BBOX_SUR BBOX_NORTE BBOX_OESTE BBOX_ESTE MAPID_BASE RAM_JAVA; do
    if [ -z "${!var:-}" ]; then
        error "La variable '$var' no está definida en $CONF."
    fi
done

# Validar FUENTES_OSM (array no vacío)
if [ ${#FUENTES_OSM[@]} -eq 0 ]; then
    error "FUENTES_OSM está vacío en $CONF. Define al menos una URL."
fi

echo "============================================================"
echo " Generador de mapa Garmin — ${NOMBRE_MAPA}"
echo " Zona: ${ZONA}"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo "  BBox: Sur=${BBOX_SUR} Norte=${BBOX_NORTE} Oeste=${BBOX_OESTE} Este=${BBOX_ESTE}"
echo "  Fuentes OSM: ${#FUENTES_OSM[@]}"
echo "  MAPID_BASE: ${MAPID_BASE}  RAM Java: ${RAM_JAVA}"

# Directorios de trabajo
WORK_DIR="${REPO_DIR}/carte_${ZONA}"
ORIGEN_DIR="${WORK_DIR}/origen"

# -----------------------------------------------------------------------------
# 1. Comprobar dependencias
# -----------------------------------------------------------------------------
echo ""
echo "[1/7] Comprobando dependencias..."

dependencias_faltantes=0

for cmd in java curl osmium; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "  AVISO: '$cmd' no encontrado en PATH."
        if [ "$cmd" = "osmium" ]; then
            echo "         Instalar con: sudo apt install osmium-tool"
        fi
        dependencias_faltantes=$((dependencias_faltantes + 1))
    else
        echo "  OK: $cmd"
    fi
done

if [ $dependencias_faltantes -gt 0 ]; then
    echo ""
    error "Instala las dependencias faltantes antes de continuar."
fi

# Comprobar mkgmap, splitter y sea.zip; descargar si no existen
if [ ! -d "mkgmap" ] || [ ! -d "splitter" ] || [ ! -f "sea.zip" ]; then
    echo ""
    echo "  mkgmap, splitter o sea.zip no encontrados. Ejecutando download_require.sh..."
    bash download_require.sh || error "Falló la descarga de mkgmap/splitter/sea.zip."
    echo "  Descarga de herramientas completada."
fi

[ -f "mkgmap/mkgmap.jar" ]     || error "mkgmap/mkgmap.jar no encontrado tras download_require.sh."
[ -f "splitter/splitter.jar" ] || error "splitter/splitter.jar no encontrado tras download_require.sh."
echo "  OK: mkgmap y splitter"

# -----------------------------------------------------------------------------
# 2. Crear estructura de directorios
# -----------------------------------------------------------------------------
echo ""
echo "[2/7] Creando directorios..."

mkdir -p "$ORIGEN_DIR"
mkdir -p "dem/${ZONA}"
mkdir -p "salida"

echo "  carte_${ZONA}/  carte_${ZONA}/origen/  dem/${ZONA}/  salida/"

# -----------------------------------------------------------------------------
# 3. Resolver polígono de recorte
#    - Si POLIGONO está definido, usar ese fichero
#    - Si está vacío, generar un rectángulo desde el BBOX
# -----------------------------------------------------------------------------
echo ""
echo "[3/7] Preparando polígono de recorte..."

POLY_DESTINO="${WORK_DIR}/${ZONA}.poly"

if [ -n "${POLIGONO:-}" ]; then
    # Polígono explícito en el .conf
    POLY_ORIGEN="${REPO_DIR}/${POLIGONO}"
    if [ ! -f "$POLY_ORIGEN" ]; then
        error "El polígono indicado en la configuración no existe: $POLY_ORIGEN"
    fi
    cp "$POLY_ORIGEN" "$POLY_DESTINO"
    echo "  Usando polígono: ${POLIGONO} → ${POLY_DESTINO}"
else
    # Generar polígono rectangular desde BBOX
    echo "  POLIGONO no definido — generando rectángulo desde BBox..."
    cat > "$POLY_DESTINO" <<EOF
${ZONA}
1
   ${BBOX_OESTE}   ${BBOX_SUR}
   ${BBOX_ESTE}    ${BBOX_SUR}
   ${BBOX_ESTE}    ${BBOX_NORTE}
   ${BBOX_OESTE}   ${BBOX_NORTE}
   ${BBOX_OESTE}   ${BBOX_SUR}
END
END
EOF
    echo "  Polígono rectangular generado: ${POLY_DESTINO}"
fi

# -----------------------------------------------------------------------------
# 4. Descargar los .pbf regionales si no existen
# -----------------------------------------------------------------------------
echo ""
echo "[4/7] Comprobando / descargando archivos OSM regionales..."

for url in "${FUENTES_OSM[@]}"; do
    # Extraer nombre de archivo de la URL
    nombre_archivo="$(basename "$url")"
    destino="${ORIGEN_DIR}/${nombre_archivo}"

    if [ -f "$destino" ]; then
        echo "  Ya existe: ${nombre_archivo} — omitiendo descarga."
    else
        echo "  Descargando: ${nombre_archivo} ..."
        curl -L --fail --show-error -o "$destino" "$url" \
            || error "Falló la descarga de $url"
        echo "  Descargado: $destino"
    fi
done

# -----------------------------------------------------------------------------
# 5. Recortar cada .pbf al polígono (en paralelo)
# -----------------------------------------------------------------------------
echo ""
# Paralelismo configurable desde el .conf (PARALELISMO_OSMIUM). Por defecto 1
# para no agotar la RAM en zonas con muchas fuentes grandes.
PARALELISMO_OSMIUM="${PARALELISMO_OSMIUM:-1}"
echo "[5/7] Recortando archivos al polígono (paralelismo=${PARALELISMO_OSMIUM})..."

RECORTADOS=()

# Construir la lista completa de recortados primero
for url in "${FUENTES_OSM[@]}"; do
    nombre_archivo="$(basename "$url")"
    nombre_base="${nombre_archivo%.osm.pbf}"
    recortado="${ORIGEN_DIR}/${nombre_base}-${ZONA}.osm.pbf"
    RECORTADOS+=("$recortado")
done

# Función que recorta una sola fuente
recortar_uno() {
    local url="$1"
    local nombre_archivo nombre_base origen recortado
    nombre_archivo="$(basename "$url")"
    nombre_base="${nombre_archivo%.osm.pbf}"
    origen="${ORIGEN_DIR}/${nombre_archivo}"
    recortado="${ORIGEN_DIR}/${nombre_base}-${ZONA}.osm.pbf"

    # Saltar si ya existe Y no está vacío
    if [ -s "$recortado" ]; then
        echo "  Ya existe recortado: $(basename "$recortado") — omitiendo."
        return 0
    fi
    # Borrar archivo de 0 bytes (resultado de un kill previo)
    rm -f "$recortado"

    echo "  Recortando ${nombre_archivo}..."
    osmium extract \
        --polygon "$POLY_DESTINO" \
        --overwrite \
        -o "$recortado" \
        "$origen" \
        || { echo "  ERROR: falló el recorte de $nombre_archivo"; return 1; }
}

if [ "$PARALELISMO_OSMIUM" -le 1 ]; then
    # Modo secuencial (default) — más lento pero estable con poca RAM
    for url in "${FUENTES_OSM[@]}"; do
        recortar_uno "$url" || error "Falló el recorte; revisa la RAM/disco."
    done
else
    # Modo paralelo controlado con xargs (solo si el usuario lo pide)
    export -f recortar_uno
    export ORIGEN_DIR ZONA POLY_DESTINO
    printf '%s\n' "${FUENTES_OSM[@]}" \
        | xargs -P "$PARALELISMO_OSMIUM" -I {} bash -c 'recortar_uno "$@"' _ {} \
        || error "Algún recorte falló en modo paralelo."
fi

# Verificar que todos los recortados existen y no están vacíos
for recortado in "${RECORTADOS[@]}"; do
    [ -s "$recortado" ] || error "Fichero recortado no encontrado o vacío: $recortado"
done
echo "  Todos los recortes completados."

# -----------------------------------------------------------------------------
# 6. Combinar los .pbf recortados en uno solo
# -----------------------------------------------------------------------------
echo ""
echo "[6/7] Combinando fragmentos en carte_${ZONA}/${ZONA}.osm.pbf..."

PBF_COMBINADO="${WORK_DIR}/${ZONA}.osm.pbf"

if [ "${#RECORTADOS[@]}" -eq 1 ]; then
    # Una sola fuente: simplemente copiar/renombrar
    cp "${RECORTADOS[0]}" "$PBF_COMBINADO"
    echo "  Una sola fuente — copiado directamente: $PBF_COMBINADO"
else
    osmium merge \
        --overwrite \
        -o "$PBF_COMBINADO" \
        "${RECORTADOS[@]}" \
        || error "Falló la combinación con osmium merge."
    echo "  Combinado: $PBF_COMBINADO"
fi

ls -lh "$PBF_COMBINADO"

# -----------------------------------------------------------------------------
# 7. Llamar al script de construcción genérico
# -----------------------------------------------------------------------------
echo ""
echo "[7/7] Iniciando construcción del mapa (splitter + mkgmap)..."
echo "  Script: construir.sh ${ZONA}"

# --- Estilo personalizado por zona -------------------------------------------
ESTILO_JSON="$REPO_DIR/zonas/${ZONA}.estilo.json"
RANDO_PATH="$REPO_DIR/style/rando.txt"
RANDO_ORIG="$REPO_DIR/style/rando.txt.orig"
_estilo_aplicado=0

_restaurar_rando() {
    if [ "$_estilo_aplicado" -eq 1 ] && [ -f "$RANDO_ORIG" ]; then
        cp "$RANDO_ORIG" "$RANDO_PATH"
        echo "  Estilo base restaurado: style/rando.txt"
    fi
}

if [ -f "$ESTILO_JSON" ]; then
    echo "  Estilo personalizado encontrado: $ESTILO_JSON"
    # Guardar copia limpia del estilo base (solo si no existe ya)
    if [ ! -f "$RANDO_ORIG" ]; then
        cp "$RANDO_PATH" "$RANDO_ORIG"
        echo "  Copia limpia guardada: style/rando.txt.orig"
    fi
    # Asegurar restauración aunque construir.sh falle
    trap '_restaurar_rando' EXIT
    python3 "$REPO_DIR/aplicar_estilo.py" "$ZONA" \
        || error "aplicar_estilo.py falló para la zona '${ZONA}'."
    _estilo_aplicado=1
fi
# -----------------------------------------------------------------------------

bash "$REPO_DIR/construir.sh" "$ZONA" || error "Falló construir.sh para la zona '${ZONA}'."

# Restaurar rando.txt si se aplicó un estilo personalizado
_restaurar_rando

# -----------------------------------------------------------------------------
# Resumen final
# -----------------------------------------------------------------------------
echo ""
echo "============================================================"
echo " PIPELINE COMPLETADO — ${NOMBRE_MAPA}"

dm="$(date '+%Y_%m_%d')"
NOMBRE_SIN_ESPACIOS="${NOMBRE_MAPA// /_}"
img_esperado="salida/MapRando_${NOMBRE_SIN_ESPACIOS}_${dm}.img"
if [ -f "$img_esperado" ]; then
    echo " Mapa generado: $img_esperado"
    ls -lh "$img_esperado"
else
    echo " AVISO: No se encontró el archivo de salida esperado: $img_esperado"
fi

tiempo_transcurrido
echo "============================================================"
