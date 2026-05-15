#!/bin/bash
# =============================================================================
# construir.sh
# Compilación genérica: splitter + mkgmap → gmapsupp.img para cualquier zona.
# Uso: bash construir.sh <zona>
#   Ejemplo: bash construir.sh pirineos
#            bash construir.sh mallorca
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
# Validar argumento de zona
# -----------------------------------------------------------------------------
if [ $# -eq 0 ]; then
    echo "Uso: bash construir.sh <zona>"
    echo "  Ejemplo: bash construir.sh pirineos"
    exit 1
fi

ZONA="$1"
CONF="$REPO_DIR/zonas/${ZONA}.conf"

if [ ! -f "$CONF" ]; then
    error "No se encontró la configuración para la zona '${ZONA}' en: $CONF"
fi

# -----------------------------------------------------------------------------
# Cargar configuración de la zona
# -----------------------------------------------------------------------------
# shellcheck source=/dev/null
source "$CONF"

# Validar variables obligatorias
for var in NOMBRE_MAPA MAPID_BASE RAM_JAVA; do
    if [ -z "${!var:-}" ]; then
        error "La variable '$var' no está definida en $CONF."
    fi
done

# Construir IDs de mapa: 44<MAPID_BASE> para OSM, 55<MAPID_BASE> para curvas
MAPNAME_BASE="44${MAPID_BASE}"
MAPNAME_CURVAS_BASE="55${MAPID_BASE}"
XMX="-Xmx${RAM_JAVA}"

dm="$(date '+%Y_%m_%d')"
d="$(date '+%d.%m.%Y')"

MAP_DESC="MapRando ${NOMBRE_MAPA} ${d}"
NOMBRE_SIN_ESPACIOS="${NOMBRE_MAPA// /_}"
OUTPUT_IMG="${REPO_DIR}/salida/MapRando_${NOMBRE_SIN_ESPACIOS}_${dm}.img"

WORK_DIR="${REPO_DIR}/carte_${ZONA}"

echo "============================================================"
echo " Construcción del mapa — ${NOMBRE_MAPA}"
echo " Zona: ${ZONA}"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo " RAM Java: ${RAM_JAVA}"
echo "============================================================"

# -----------------------------------------------------------------------------
# Comprobar requisitos básicos
# -----------------------------------------------------------------------------
[ -d "mkgmap" ]              || error "Directorio mkgmap/ no encontrado. Ejecuta download_require.sh primero."
[ -f "mkgmap/mkgmap.jar" ]   || error "mkgmap/mkgmap.jar no encontrado."
[ -d "splitter" ]            || error "Directorio splitter/ no encontrado. Ejecuta download_require.sh primero."
[ -f "splitter/splitter.jar" ] || error "splitter/splitter.jar no encontrado."
[ -f "sea.zip" ]             || error "sea.zip no encontrado. Ejecuta download_require.sh primero."
[ -f "options_rando.args" ]  || error "options_rando.args no encontrado."
[ -f "style/rando.txt" ]     || error "style/rando.txt no encontrado."
[ -f "${WORK_DIR}/${ZONA}.osm.pbf" ] \
    || error "carte_${ZONA}/${ZONA}.osm.pbf no encontrado. Ejecuta crear_mapa.sh ${ZONA} primero."
[ -f "${WORK_DIR}/${ZONA}.poly" ] \
    || error "carte_${ZONA}/${ZONA}.poly no encontrado. Ejecuta crear_mapa.sh ${ZONA} primero."

mkdir -p salida

# Cambiar al directorio de trabajo
cd "$WORK_DIR"

# Limpiar .img huérfanos de ejecuciones anteriores fallidas
rm -f ./*.img 2>/dev/null || true

# =============================================================================
# BLOQUE 1: Curvas de nivel (.osm.gz)
# =============================================================================
count_gz=$(find . -maxdepth 1 -name '*.osm.gz' | wc -l)

if [ "$count_gz" -ne 0 ]; then
    echo ""
    echo "--- Procesando curvas de nivel ($count_gz archivo(s) .osm.gz) ---"

    for fichero_curva in ./*.osm.gz; do
        count_img=$(find . -maxdepth 1 -name '*.img' | wc -l)
        idx="$(printf '%03d' "$count_img")"
        mapid_curva="${MAPNAME_CURVAS_BASE}${idx}"

        echo "  Splitter curvas: $fichero_curva  (mapid=${mapid_curva})"

        # Intentar con polígono primero
        java $XMX -jar "${REPO_DIR}/splitter/splitter.jar" \
            --mapid="${mapid_curva}" \
            --max-nodes=1000000 \
            --polygon-file="${ZONA}.poly" \
            --keep-complete=false \
            "$fichero_curva"

        # Si no se generaron tiles, reintentar sin polígono
        if [ ! -f "${mapid_curva}.osm.pbf" ]; then
            echo "  AVISO: Sin resultados con polígono, reintentando sin --polygon-file..."
            java $XMX -jar "${REPO_DIR}/splitter/splitter.jar" \
                --mapid="${mapid_curva}" \
                --max-nodes=1000000 \
                --keep-complete=false \
                "$fichero_curva"
        fi

        mv template.args courbes.args

        echo "  mkgmap curvas: $fichero_curva"
        java $XMX -jar "${REPO_DIR}/mkgmap/mkgmap.jar" \
            -c "${REPO_DIR}/options_courbes.args" \
            -c courbes.args

        # Limpieza de temporales de splitter/mkgmap para esta iteración
        rm -f "${mapid_curva}"*.osm.pbf
        rm -f areas.list areas.poly courbes.args
        rm -f none-areas.poly none-template.args
        rm -f densities-out.txt osmmap.img osmmap.tdb
    done

    rm -f ./*.osm.gz
    echo "  Curvas de nivel procesadas."
else
    echo ""
    echo "  No se encontraron archivos .osm.gz — se omite la capa de curvas de nivel."
    echo "  (Ejecuta descargar_hgt.sh ${ZONA} para generarlas.)"
fi

# =============================================================================
# BLOQUE 2: Datos OSM principales (splitter)
# =============================================================================
echo ""
echo "--- Splitter: ${ZONA}.osm.pbf ---"

if [ ! -f "${MAPNAME_BASE}000.osm.pbf" ]; then
    java $XMX -jar "${REPO_DIR}/splitter/splitter.jar" \
        --mapid="${MAPNAME_BASE}000" \
        --max-nodes=1000000 \
        --keep-complete=true \
        --route-rel-values=foot,hiking,bicycle \
        --overlap=0 \
        "${ZONA}.osm.pbf" \
        || error "Splitter falló para ${ZONA}.osm.pbf."

    mv template.args map.args
    echo "  Splitter completado."
else
    echo "  Tiles ya existentes (${MAPNAME_BASE}000.osm.pbf) — se omite el splitter."
fi

# =============================================================================
# BLOQUE 3: Compilación mkgmap — capa OSM
# =============================================================================
echo ""
echo "--- mkgmap: compilando capa OSM ---"

java $XMX -jar "${REPO_DIR}/mkgmap/mkgmap.jar" \
    -c "${REPO_DIR}/options_rando.args" \
    -c map.args \
    || error "mkgmap falló en la compilación de la capa OSM."

echo "  Compilación OSM completada."

# =============================================================================
# BLOQUE 4: Ensamblado final gmapsupp.img
# =============================================================================
echo ""
echo "--- mkgmap: ensamblando gmapsupp.img ---"

count_curvas_img=$(find . -maxdepth 1 -name "${MAPNAME_CURVAS_BASE}*.img" | wc -l)

if [ "$count_curvas_img" -gt 0 ]; then
    echo "  Con curvas de nivel (${count_curvas_img} tile(s))."
    java $XMX -jar "${REPO_DIR}/mkgmap/mkgmap.jar" \
        --mapname="${MAPNAME_BASE}000" \
        --family-id="${MAPNAME_BASE}" \
        --description="${MAP_DESC}" \
        -c "${REPO_DIR}/options_rando.args" \
        --gmapsupp \
        "${REPO_DIR}/style/rando.txt" \
        ${MAPNAME_BASE}*.img \
        ${MAPNAME_CURVAS_BASE}*.img \
        || error "mkgmap falló en el ensamblado final con curvas."
else
    echo "  Sin tiles de curvas de nivel."
    java $XMX -jar "${REPO_DIR}/mkgmap/mkgmap.jar" \
        --mapname="${MAPNAME_BASE}000" \
        --family-id="${MAPNAME_BASE}" \
        --description="${MAP_DESC}" \
        -c "${REPO_DIR}/options_rando.args" \
        --gmapsupp \
        "${REPO_DIR}/style/rando.txt" \
        ${MAPNAME_BASE}*.img \
        || error "mkgmap falló en el ensamblado final sin curvas."
fi

echo "  Ensamblado completado."

# =============================================================================
# BLOQUE 5: Limpieza de temporales
# =============================================================================
echo ""
echo "--- Limpieza de archivos temporales ---"

rm -f ${MAPNAME_BASE}*.img
rm -f ${MAPNAME_BASE}*.osm.pbf
rm -f ${MAPNAME_CURVAS_BASE}*.img 2>/dev/null || true
rm -f areas.list areas.poly map.args
rm -f densities-out.txt osmmap.img osmmap.tdb
rm -f none-areas.poly none-template.args 2>/dev/null || true

echo "  Limpieza completada."

# =============================================================================
# BLOQUE 6: Mover el resultado a salida/
# =============================================================================
echo ""
echo "--- Moviendo resultado a salida/ ---"

cd "$REPO_DIR"

if [ ! -f "carte_${ZONA}/gmapsupp.img" ]; then
    error "gmapsupp.img no encontrado en carte_${ZONA}/ tras la compilación."
fi

mv -f "carte_${ZONA}/gmapsupp.img" "$OUTPUT_IMG" \
    || error "No se pudo mover gmapsupp.img a $OUTPUT_IMG."

echo "  Mapa final: $OUTPUT_IMG"
ls -lh "$OUTPUT_IMG"

echo ""
echo "============================================================"
echo " CONSTRUCCIÓN COMPLETADA — ${NOMBRE_MAPA}"
tiempo_transcurrido
echo "============================================================"
