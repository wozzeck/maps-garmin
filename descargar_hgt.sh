#!/bin/bash
# =============================================================================
# descargar_hgt.sh
# Descarga datos de elevación y genera curvas de nivel para una zona.
# Usa pyhgtmap directamente con --area y múltiples fuentes (Sonny, Viewfinder,
# ALOS, SRTM). pyhgtmap descarga los tiles que necesite y los cachea.
#
# Uso: bash descargar_hgt.sh <zona>
#   Ejemplo: bash descargar_hgt.sh pirineos
# =============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

# pyhgtmap suele instalarse en ~/.local/bin con pip --user
export PATH="$HOME/.local/bin:$PATH"

start_time="$(date +%s)"

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

error() {
    echo "ERROR: $*" >&2
    exit 1
}

# -----------------------------------------------------------------------------
# Validar argumento
# -----------------------------------------------------------------------------
if [ $# -eq 0 ]; then
    echo "Uso: bash descargar_hgt.sh <zona>"
    echo "  Ejemplo: bash descargar_hgt.sh pirineos"
    exit 1
fi

ZONA="$1"
CONF="$REPO_DIR/zonas/${ZONA}.conf"
[ -f "$CONF" ] || error "No se encontró la configuración: $CONF"

# shellcheck source=/dev/null
source "$CONF"

# Validar variables obligatorias
for var in NOMBRE_MAPA BBOX_SUR BBOX_NORTE BBOX_OESTE BBOX_ESTE; do
    if [ -z "${!var:-}" ]; then
        error "Variable '$var' no definida en $CONF."
    fi
done

# Fuentes de elevación: preferimos Sonny (Europa, alta calidad) y Viewfinder
# como respaldo. ALOS y SRTM como últimos. pyhgtmap usa el primero disponible
# para cada tile. Se puede sobrescribir en el .conf con FUENTES_HGT.
FUENTES_HGT="${FUENTES_HGT:-sonn1,view1,alos1,srtm1}"

echo "============================================================"
echo " Descarga de elevación y curvas — ${NOMBRE_MAPA}"
echo " Zona:    ${ZONA}"
echo " Hora:    $(date '+%Y-%m-%d %H:%M:%S')"
echo " BBox:    Sur=${BBOX_SUR} Norte=${BBOX_NORTE} Oeste=${BBOX_OESTE} Este=${BBOX_ESTE}"
echo " Fuentes: ${FUENTES_HGT}"
echo "============================================================"

# -----------------------------------------------------------------------------
# Comprobar dependencias
# -----------------------------------------------------------------------------
command -v pyhgtmap >/dev/null 2>&1 || error "pyhgtmap no instalado. pip install --user pyhgtmap"
python3 -c "import pyhgtmap" 2>/dev/null || error "pyhgtmap importable falla. Reinstalar: pip install --user --break-system-packages pyhgtmap"

# -----------------------------------------------------------------------------
# Crear directorios
# -----------------------------------------------------------------------------
mkdir -p "dem/${ZONA}/cache"
mkdir -p "carte_${ZONA}"

# -----------------------------------------------------------------------------
# Lanzar pyhgtmap con --area: descarga lo que necesite + genera curvas
# -----------------------------------------------------------------------------
echo ""
echo "Lanzando pyhgtmap (puede tardar bastante en la primera ejecución;"
echo "los tiles se cachean en dem/${ZONA}/cache/ para reusos futuros)..."
echo ""

cd "dem/${ZONA}"

# Parámetros:
#   --area L:B:R:T  bounding box
#   --sources       lista de fuentes en orden de preferencia
#   --hgtdir        cache de tiles HGT descargados (mantener entre runs)
#   --step=10       intervalo de curvas en metros
#   --no-zero-contour  no dibujar curva de 0 m
#   --jobs=4        paralelismo (ajustar a CPU)
#   --gzip=1        comprimir output .osm.gz
pyhgtmap \
    --area="${BBOX_OESTE}:${BBOX_SUR}:${BBOX_ESTE}:${BBOX_NORTE}" \
    --sources="${FUENTES_HGT}" \
    --hgtdir=cache \
    --step=10 \
    --no-zero-contour \
    --jobs=4 \
    --gzip=1 \
    || error "pyhgtmap falló."

cd "$REPO_DIR"

# -----------------------------------------------------------------------------
# Mover .osm.gz generados a carte_<zona>/
# -----------------------------------------------------------------------------
count_gz="$(find "dem/${ZONA}" -maxdepth 1 -name '*.osm.gz' | wc -l)"

if [ "$count_gz" -eq 0 ]; then
    error "pyhgtmap no generó archivos .osm.gz."
fi

echo ""
echo "Moviendo ${count_gz} archivo(s) .osm.gz a carte_${ZONA}/ ..."
for f in "dem/${ZONA}/"*.osm.gz; do
    mv -f "$f" "carte_${ZONA}/"
    echo "  $(basename "$f")"
done

echo ""
echo "============================================================"
echo " Curvas de nivel listas — ${NOMBRE_MAPA}"
echo " Ya puedes lanzar: bash crear_mapa.sh ${ZONA}"
tiempo_transcurrido
echo "============================================================"
