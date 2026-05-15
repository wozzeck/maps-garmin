#!/bin/bash
# Descarga las herramientas necesarias: mkgmap, splitter, sea.zip.
# Si faltan las dependencias del sistema (curl, java, python3, unzip), avisa
# pero NO ejecuta apt automáticamente (evita sudo no autorizado).
set -euo pipefail

# Versiones a usar (ajustar a las últimas en www.mkgmap.org.uk)
MKGMAP="mkgmap-r4924"
SPLITTER="splitter-r654"

# 1. Verificar dependencias del sistema
faltan=()
for cmd in curl java python3 unzip; do
    command -v "$cmd" >/dev/null 2>&1 || faltan+=("$cmd")
done

if [ ${#faltan[@]} -gt 0 ]; then
    echo "AVISO: Faltan comandos del sistema: ${faltan[*]}"
    echo "Instálalos manualmente. En Ubuntu/Debian:"
    echo "  sudo apt install curl openjdk-21-jre-headless python3-pip unzip"
    exit 1
fi

# 2. Descargar mkgmap si no existe
if [ ! -d "mkgmap" ]; then
    echo "Descargando ${MKGMAP}..."
    curl -L -o "mkgmap.zip" "https://www.mkgmap.org.uk/download/${MKGMAP}.zip"
    unzip -q "mkgmap.zip"
    rm "mkgmap.zip"
    mv "${MKGMAP}" mkgmap
    echo "  Listo: mkgmap/"
fi

# 3. Descargar splitter si no existe
if [ ! -d "splitter" ]; then
    echo "Descargando ${SPLITTER}..."
    curl -L -o "splitter.zip" "https://www.mkgmap.org.uk/download/${SPLITTER}.zip"
    unzip -q "splitter.zip"
    rm "splitter.zip"
    mv "${SPLITTER}" splitter
    echo "  Listo: splitter/"
fi

# 4. Descargar sea.zip si no existe
if [ ! -f "sea.zip" ]; then
    echo "Descargando sea.zip (precompiled sea polygons)..."
    curl -L -o "sea.zip" "http://osm.thkukuk.de/data/sea-latest.zip"
    echo "  Listo: sea.zip"
fi

# 5. Instalar requirements Python (sin sudo, con --user o entorno actual)
if [ -f "requirements.txt" ]; then
    # Comprobar si pyhgtmap ya está
    if ! command -v pyhgtmap >/dev/null 2>&1 && ! python3 -c "import pyhgtmap" 2>/dev/null; then
        echo "Instalando paquetes Python (pip --user)..."
        pip3 install --user -r requirements.txt
    else
        echo "Paquetes Python ya instalados (pyhgtmap detectado)."
    fi
fi

echo ""
echo "Listo. Herramientas disponibles:"
echo "  mkgmap/   $(ls mkgmap/ | head -3 | tr '\n' ' ')"
echo "  splitter/ $(ls splitter/ | head -3 | tr '\n' ' ')"
echo "  sea.zip   $(ls -lh sea.zip | awk '{print $5}')"
