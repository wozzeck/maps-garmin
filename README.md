# maps-garmin — Generador de mapas Garmin de senderismo

Herramienta de línea de comandos para generar mapas Garmin (.img) optimizados
para senderismo a partir de datos OpenStreetMap y modelos de elevación digital.
Sirve para cualquier zona geográfica: basta con definir un archivo de
configuración de zona.

Repositorio: https://github.com/wozzeck/maps-garmin (rama `main`)

Origen: fork reescrito en español de
https://gitlab.com/ravenfeld/garmincustommap (Alexis Lecanu). Generalizado para
cualquier zona; el original estaba orientado a un único mapa de Francia.


## Qué hace exactamente

1. Descarga extractos OSM regionales de Geofabrik en formato .pbf.
2. Los recorta al polígono o bounding box de la zona con osmium.
3. Si hay varios extractos (zona fronteriza), los fusiona en un único .pbf.
4. Aplica opcionalmente el estilo de color personalizado por zona.
5. Fragmenta el .pbf en tiles con splitter.
6. Compila los tiles en capas .img con mkgmap, aplicando el estilo rando.
7. Si existen curvas de nivel (.osm.gz), las integra en una capa independiente.
8. Ensambla todo en un único gmapsupp.img y lo deposita en `salida/`.

El archivo resultante se copia directamente a la carpeta `Garmin/` del
dispositivo GPS.


## Requisitos del sistema

| Componente | Version / notas |
|---|---|
| Java (JRE) | 11 o superior; recomendado OpenJDK 21 |
| curl | para descargar extractos OSM y herramientas |
| osmium-tool | `sudo apt install osmium-tool` |
| unzip | para descomprimir mkgmap y splitter |
| Python 3.8+ | para los scripts de estilo y utilidades |
| pyhgtmap | solo si quieres curvas de nivel (ver abajo) |
| RAM | minimo 4 GB libres para zonas pequenas; 8-12 GB para zonas grandes |
| Disco | variable; un build de Pirineos ocupa ~5 GB de temporales |

Las herramientas Java (mkgmap, splitter) y el archivo sea.zip las descarga
automáticamente `download_require.sh`.


## Instalación

```bash
git clone https://github.com/wozzeck/maps-garmin.git
cd maps-garmin
bash download_require.sh
```

`download_require.sh` descarga `mkgmap-r4924`, `splitter-r654` y `sea.zip` al
directorio raíz del repo. Si falta alguna dependencia del sistema (curl, java,
unzip), lo indica y sale sin ejecutar `apt`.

Para instalar pyhgtmap (necesario solo para curvas de nivel):

```bash
pip install --user --break-system-packages pyhgtmap
```

En Ubuntu 24.04 el flag `--break-system-packages` es obligatorio por PEP 668.


## Uso rápido

### 1. Definir la zona

Copia la plantilla y edítala:

```bash
cp zonas/template.conf zonas/mi_zona.conf
```

Los campos obligatorios son:

```bash
NOMBRE_MAPA="Mi Zona"          # aparece en el dispositivo Garmin
BBOX_SUR=41.0                  # latitud sur (grados decimales)
BBOX_NORTE=43.0                # latitud norte
BBOX_OESTE=-2.0                # longitud oeste (negativo al oeste de Greenwich)
BBOX_ESTE=1.5                  # longitud este
FUENTES_OSM=(
    "http://download.geofabrik.de/europe/spain/aragon-latest.osm.pbf"
)
MAPID_BASE="500"               # 3 digitos, unico por zona (889=Pirineos, 890=Mallorca)
RAM_JAVA="4096m"               # memoria maxima para Java
```

Para definir el bounding box visualmente:
https://boundingbox.klokantech.com/

Para zonas que cruzan varios extractos regionales (por ejemplo una zona
fronteriza entre España y Francia), añade todas las URLs necesarias en
`FUENTES_OSM`. El script las recorta al polígono y las fusiona automáticamente.

El campo `POLIGONO` es opcional: si se omite o queda vacío, se usa el bounding
box rectangular. Si se especifica, debe ser un archivo .poly (formato osmosis)
con ruta relativa al raíz del repo.

### 2. Descargar curvas de nivel (opcional)

```bash
bash descargar_hgt.sh mi_zona
```

Usa pyhgtmap con multiples fuentes de elevación (Sonny, Viewfinder, ALOS,
SRTM) en orden de calidad. Los tiles HGT se cachean en `dem/mi_zona/cache/`
para no repetir la descarga en builds sucesivos. Las curvas se generan a
intervalos de 10 m. Sin este paso, el mapa se genera sin relieve.

### 3. Generar el mapa

```bash
bash crear_mapa.sh mi_zona
```

El proceso completo tarda entre 5 y 30 minutos dependiendo del tamaño de la
zona y la RAM disponible. Al terminar, el archivo se encuentra en:

```
salida/MapRando_Mi_Zona_AAAA_MM_DD.img
```

### 4. Copiar al dispositivo Garmin

Conecta el GPS por USB y copia el .img a la carpeta `Garmin/` de la tarjeta
de memoria. Si ya existe un `gmapsupp.img`, renombra el nuevo archivo antes
de copiarlo (el nombre no importa para el dispositivo, solo la extension .img).


## El editor web

El directorio `editor/` contiene una aplicación web de una sola página que
permite:

- Dibujar el polígono de la zona sobre un mapa interactivo (Leaflet).
- Seleccionar los extractos de Geofabrik que la cubren.
- Ajustar parámetros (RAM, MAPID_BASE, fuentes HGT).
- Descargar el archivo `zonas/mi_zona.conf` generado.
- Editar los colores de senderos y exportar `zonas/mi_zona.estilo.json`.

Para arrancarlo, solo hace falta un servidor HTTP local (no requiere Node ni
ninguna dependencia):

```bash
cd /ruta/al/repo
python3 -m http.server 8080
```

Abre en el navegador: http://localhost:8080/editor/

El editor necesita los archivos `datos/extractos_geofabrik.json` y
`datos/estilo_actual.json`, que ya están incluidos en el repositorio.
Si quieres regenerarlos:

```bash
python3 generar_extractos.py          # actualiza extractos_geofabrik.json
python3 estilo_a_json.py              # actualiza estilo_actual.json
```


## Personalización del estilo de líneas

El estilo visual del mapa se define en `style/rando.txt`, un archivo TYP de
Garmin en codificación CP1252 con saltos de línea CRLF. No debe editarse
directamente con editores que normalicen saltos de línea.

El flujo de personalización es:

```
style/rando.txt
    |
    v  estilo_a_json.py
datos/estilo_actual.json
    |
    v  editor web (pestaña Estilo)
zonas/mi_zona.estilo.json
    |
    v  aplicar_estilo.py (lo invoca crear_mapa.sh automáticamente)
style/rando.txt  (modificado temporalmente durante el build)
```

`crear_mapa.sh` detecta si existe `zonas/mi_zona.estilo.json` y aplica los
cambios de color antes de compilar. Al terminar (o si el build falla),
restaura `style/rando.txt` al estado original mediante un trap EXIT.

Para comprobar qué cambiaría sin tocar ningún archivo:

```bash
python3 aplicar_estilo.py mi_zona --check
```

El catálogo visual de todos los tipos de línea del estilo está en
`tipos_de_linea.html`. Se puede abrir directamente en el navegador. Para
regenerarlo desde el TYP actual:

```bash
python3 gen_tipos_linea.py
```


## Estructura del repositorio

| Archivo | Descripcion |
|---|---|
| `crear_mapa.sh` | Pipeline principal. Orquesta los pasos 1-7 descritos arriba. Punto de entrada habitual. |
| `construir.sh` | Compilacion (splitter + mkgmap). Lo invoca `crear_mapa.sh`; tambien puede ejecutarse suelto si los .pbf ya existen. |
| `descargar_hgt.sh` | Descarga datos de elevacion y genera curvas de nivel (.osm.gz) con pyhgtmap. |
| `download_require.sh` | Descarga mkgmap, splitter y sea.zip. Comprueba dependencias del sistema. |
| `aplicar_estilo.py` | Lee `zonas/<zona>.estilo.json` y sobreescribe los colores en `style/rando.txt` (CP1252, CRLF). Soporta `--check` (dry-run). |
| `estilo_a_json.py` | Exporta el estado actual de `style/rando.txt` a `datos/estilo_actual.json` para el editor web. |
| `gen_tipos_linea.py` | Genera `tipos_de_linea.html`, catálogo visual de todos los tipos de linea del TYP con previsualizacion SVG real. |
| `generar_extractos.py` | Descarga el índice de Geofabrik y genera `datos/extractos_geofabrik.json` para el editor web. |
| `traducir_typ.py` | Utilidad de traduccion de tipos TYP (uso interno). |
| `zonas/` | Configuraciones de zona. `template.conf` es la plantilla. `pirineos.conf` y `mallorca.conf` son ejemplos. |
| `style/` | TYP Garmin (`rando.txt`) y reglas mkgmap (`rando/lines`, etc.). |
| `editor/` | Aplicacion web: `index.html`, `app.js`, `style.css`. Requiere servidor HTTP local. |
| `datos/` | JSON generados (estilo_actual.json, extractos_geofabrik.json). Incluidos en el repo. |
| `options_rando.args` | Opciones fijas de mkgmap para la capa OSM principal. |
| `options_courbes.args` | Opciones fijas de mkgmap para la capa de curvas de nivel. |
| `tipos_de_linea.html` | Catalogo visual generado. Abrir en el navegador para consultar el estilo. |


## Directorios generados (excluidos del repo)

| Directorio | Contenido |
|---|---|
| `carte_<zona>/` | Directorio de trabajo por zona: .pbf descargados, recortados, tiles intermedios. |
| `dem/<zona>/` | Tiles HGT cacheados y archivos .osm.gz de curvas de nivel. |
| `salida/` | Archivos .img finales listos para copiar al Garmin. |
| `mkgmap/` | Herramienta mkgmap descargada por `download_require.sh`. |
| `splitter/` | Herramienta splitter descargada por `download_require.sh`. |


## Ejemplos de zonas incluidas

| Zona | Descripcion | Fuentes OSM |
|---|---|---|
| `pirineos` | Pirineos completos (España, Francia, Andorra). Usa polígono fino `zonas/pirineos.poly`. | 8 extractos regionales |
| `mallorca` | Isla de Mallorca. Ejemplo de zona pequena con una sola fuente. | 1 extracto (Islas Baleares) |

Usa `mallorca` como referencia para builds de prueba: es pequeña, tarda
aproximadamente 3-5 minutos y consume poca RAM.


## Creditos

Proyecto original: **garmincustommap** de Alexis Lecanu
(https://gitlab.com/ravenfeld/garmincustommap), publicado bajo licencia libre.

Este fork ha sido reescrito en español, generalizado para cualquier zona
geográfica y ampliado con el editor web y las herramientas de personalización
del estilo.
