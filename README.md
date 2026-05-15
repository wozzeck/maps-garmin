# Creación de un mapa Garmin personalizado

> Fork traducido al español por VVOSCA. Incluye pipeline custom para mapa de Pirineos.
> Proyecto original (francés): https://gitlab.com/ravenfeld/garmincustommap

## Entorno
Mis scripts se utilizan principalmente en MacOsX y se han probado en Ubuntu.

Para descargar las herramientas y comandos necesarios:
```bash
bash download_require.sh
```
> En Mac OS X es necesario instalar los comandos con tu herramienta preferida. Necesitas ``curl``, ``python3``, ``java``, ``unzip``. Yo utilizo Homebrew.

## Modelo de elevación digital (dem)
Si deseas tener curvas de nivel, necesitarás archivos hgt. Para Europa recomiendo los archivos de sonny en arc 1° y para el resto del mundo los de la NASA (https://search.earthdata.nasa.gov/search).

Los scripts utilizan por defecto los archivos de la NASA. Para ello necesitas crear un archivo ``password.txt`` con el siguiente contenido:
```txt
machine urs.earthdata.nasa.gov login MI_USUARIO password MI_CONTRASEÑA
```
- MI_USUARIO: tu nombre de usuario en (https://search.earthdata.nasa.gov/search)
- MI_CONTRASEÑA: tu contraseña en (https://search.earthdata.nasa.gov/search)

Si prefieres utilizar tus propios archivos, colócalos en ``dem/NOMBRE_DE_LA_REGION``

## Agregar una región
```python
python add_country.py NOMBRE_DE_LA_REGION TIPO URL_OSM_GEOFABRIK
```
- NOMBRE_DE_LA_REGION: Nombre del mapa en el reloj y también para los directorios.
- TIPO: rando o route. El estilo rando es el que comparto en el sitio, pero existe otro estilo para ciclismo en ruta.
- URL_OSM_GEOFABRIK: URL del archivo de tu región en http://download.geofabrik.de

Ejemplo para agregar Francia con tipo rando:
```python
python add_country.py Francia rando http://download.geofabrik.de/europe/france-latest.osm.pbf
```

Este comando permite descargar la región, obtener los archivos hgt o utilizar los que ya tengas, y generar el archivo que se depositará en ``~/Documents/Mega/Open_Garmin_Map/``. El script está adaptado para mi uso personal, así que puede que haya rutas que me sean útiles. Puedes modificar el archivo ``create_map.sh`` según tus necesidades.

## Actualizar mis mapas
Es muy simple. Un archivo ``country.txt`` se crea cuando utilizas el script ``add_country.py``, permitiendo mantener tus regiones con los parámetros utilizados. Esto permite ejecutar:

```python
python update_all.py
```
Este comando descarga el archivo osm de geofabrik y también los archivos hgt. Sin embargo, los archivos hgt rara vez se actualizan, por eso existe este comando:

```python
python update_only_osm.py
```
Este comando solo descarga los archivos osm de geofabrik y reutiliza los archivos hgt que ya tienes.

## Posibles problemas al usar los scripts
 - Tengo una máquina con 64 GB de RAM, así que utilizo 32 GB de RAM en los comandos Java. Para modificar esto, busca en los scripts ``java -Xmx32768m`` y reemplázalo con el valor de RAM que desees.

## Detalles de los scripts
Si lo necesitas, puedes ejecutar los diferentes scripts manualmente uno por uno. No recomiendo este método, pero si hay errores permite relanzar solo los que fallen.

#### `download_require.sh`
El script `download_require.sh` descarga los programas splitter y mkgmap, así como en Linux los comandos necesarios para el correcto funcionamiento de los scripts. También ejecuta el comando `pip install -r requirements.txt` para descargar las librerías de Python.
> Atención: es posible que las versiones de mkgmap y/o splitter deban actualizarse para su descarga.
```bash
bash download_require.sh
```

#### `get_contours.py`
El script `get_contours.py` permite descargar los archivos hgt del sitio https://urs.earthdata.nasa.gov/ y convertirlos al formato osm para ser utilizados por otros scripts.
```python
python get_contours.py NOMBRE_DE_LA_REGION URL_OSM_GEOFABRIK
```
- NOMBRE_DE_LA_REGION: Nombre del mapa en el reloj y también para los directorios.
- URL_OSM_GEOFABRIK: URL del archivo de tu región en http://download.geofabrik.de

Para nuestro ejemplo:
```bash
python get_contours.py Francia http://download.geofabrik.de/europe/france-latest.osm.pbf
```

#### `update_map.sh`
El script `update_map.sh` permite descargar el archivo osm y ejecutar el script `create_map.sh`.

Este script asume que el directorio carte_NOMBRE_DE_LA_REGION existe. En nuestro ejemplo: carte_france

```bash
bash update_map.sh NOMBRE_DE_LA_REGION ID TIPO URL_OSM_GEOFABRIK
```
- NOMBRE_DE_LA_REGION: Nombre del mapa en el reloj y también para los directorios.
- ID: Identificador del mapa en el reloj. Debe ser único entre todos los mapas, de lo contrario podrías tener mapas no disponibles en el reloj. Como no conozco los identificadores de otros mapas, es posible que tengas que modificarlo si usas el mismo que un mapa que ya tienes en tu reloj.
- TIPO: rando o route. El estilo rando es el que comparto en el sitio, pero existe otro estilo para ciclismo en ruta.
- URL_OSM_GEOFABRIK: URL del archivo de tu región en http://download.geofabrik.de

Para nuestro ejemplo:
```bash
bash update_map.sh Francia 00 rando http://download.geofabrik.de/europe/france-latest.osm.pbf
```

#### `create_map.sh`
El script `create_map.sh` permite crear un archivo para tu dispositivo Garmin.

Este script asume que el directorio carte_NOMBRE_DE_LA_REGION existe. En nuestro ejemplo: carte_france

Según tus necesidades, si deseas curvas de nivel, los archivos osm de las curvas deben estar presentes en el directorio carte_NOMBRE_DE_LA_REGION. Si no están presentes, la generación se realizará sin integrar las curvas.

```bash
bash create_map.sh NOMBRE_DE_LA_REGION ID TIPO
```
- NOMBRE_DE_LA_REGION: Nombre del mapa en el reloj y también para los directorios.
- ID: Identificador del mapa en el reloj. Debe ser único entre todos los mapas, de lo contrario podrías tener mapas no disponibles en el reloj. Como no conozco los identificadores de otros mapas, es posible que tengas que modificarlo si usas el mismo que un mapa que ya tienes en tu reloj.
- TIPO: rando o route. El estilo rando es el que comparto en el sitio, pero existe otro estilo para ciclismo en ruta.

Para nuestro ejemplo:
```bash
bash create_map.sh Francia 00 rando
```
> Atención: al final del script mueve el archivo generado a ~/Documents/Mega/Open_Garmin_Map/. Esto es útil para mí pero quizá no para ti. Modifícalo según tus necesidades si es preciso.

> La RAM disponible para Java está establecida en 32768m (32 GB). Según tu máquina, modifica este valor.

## Si deseas personalizar el mapa

Documentación del estilo:

https://www.mkgmap.org.uk/doc/pdf/style-manual.pdf

TYPViewer para editar el archivo TYP:

https://sites.google.com/site/sherco40/

## Para ir más allá
Como gestiono varias regiones, he realizado scripts ya que no me sé los comandos de memoria.

En las líneas que siguen explico el proceso para un mapa de Francia.

## Descarga de herramientas
```bash
bash download_require.sh
```

## Descarga de archivos para las curvas de nivel

https://search.earthdata.nasa.gov/search

Obtendrás los archivos en formato tif. Necesitarás convertirlo a hgt y luego a OSM:
```
gdal_translate -of SRTMHGT mi_archivo.tif mi_archivo.hgt
```
Alternativamente, para Europa existe este sitio que permite descargar los archivos en formato hgt directamente:

http://viewfinderpanoramas.org/dem1d.html

o

https://sonny.4lima.de/

El enlace para Francia está aquí:

https://drive.google.com/drive/folders/1MQqQe3VeFuUM9hRlXIz-uM0wvBNXBM2U

Para convertir del formato hgt al formato OSM usaremos la herramienta hgt2osm que puedes descargar aquí:
https://github.com/FSofTlpz/Hgt2Osm2/tree/master/bin

El comando es el siguiente:
```
hgt2osm.exe --HgtPath=. --WriteElevationType=false --FakeDistance=-0.5 --MinVerticePoints=3 --MinBoundingbox=0.00016 --DouglasPeucker=0.05 --MinorDistance=10 --OutputOverwrite=true
```

Ahora que las curvas están en formato OSM recomiendo guardarlas ya que este paso rara vez se repite debido a que los archivos de curvas casi nunca cambian.

## Descarga del mapa
En el sitio http://download.geofabrik.de/ puedes obtener la región que desees.

Para Francia el enlace es: http://download.geofabrik.de/europe/france-latest.osm.pbf

## Fragmentar los archivos
Usaremos la aplicación splitter.

Para las curvas, como están en formato OSM, puedes ejecutar el siguiente comando:

```bash
java -Xmx32768m -jar splitter.jar --mapid=73240100 --max-nodes=1600000 --keep-complete=false *.OSM

mv template.args courbes.args
```

Para fragmentar el archivo de Francia puedes ejecutar el siguiente comando:

```bash
java -Xmx32768m -jar splitter.jar --mapid=63240101 --max-nodes=1000000 --keep-complete=true --route-rel-values=foot,hiking --overlap=0 france-latest.osm.pbf

mv template.args france-latest.args
```

## Generar el archivo IMG para tu reloj
Debes obtener el directorio style que se encuentra en este repositorio. Contiene el archivo TYP y los estilos para mkgmap.

```bash
java -Xmx32768m -jar ../mkgmap-r4802/mkgmap.jar --road-name-pois --add-pois-to-areas --add-pois-to-lines --remove-short-arcs --precomp-sea=../sea.zip --x-check-precomp-sea=0  --style-file=../style/rando ../style/rando.TYP --family-name="Test" --description="Test" --mapname=94240105 --family-id=1 --product-id=1 --latin1 --net --route --road-name-pois --gmapsupp -c france-latest.args -c courbes.args
```

Solo te queda copiar el archivo gmapsupp.img en tu dispositivo Garmin.

> Atención: es posible que ya exista un archivo con este nombre. Si es así, renombra tu archivo de otra manera, no tiene importancia.

## Caso especial: Mapa de Pirineos

Este fork incluye soporte para generar un mapa combinado de los Pirineos (España + Andorra + Francia, desde el Atlántico hasta el Mediterráneo, cubriendo toda la provincia de Huesca al sur y hasta Toulouse al norte).

A diferencia de los mapas regionales estándar, los Pirineos no son una región oficial de Geofabrik, por lo que se combinan varios extractos regionales (Aragón, Cataluña, Navarra, País Vasco, Aquitaine, Midi-Pyrénées, Languedoc-Roussillon, Andorra) y se recortan al polígono `zonas/pirineos.poly`.

**Uso:**
```bash
bash crear_mapa.sh pirineos
```

Opcionalmente, para incluir curvas de nivel (requiere credenciales NASA EarthData en `password.txt`):
```bash
bash descargar_hgt.sh pirineos
bash crear_mapa.sh pirineos
```

Requiere `osmium-tool` instalado (`sudo apt install osmium-tool`).

El resultado se deposita en `salida/MapRando_Pirineos_FECHA.img`, listo para copiar a la carpeta `Garmin/` de tu dispositivo.

## Cómo añadir una nueva zona

Crea un archivo `zonas/<nombre>.conf` con la configuración de la zona. El nombre debe ser en minúsculas y sin espacios (se usará como identificador de directorios y archivos).

**Formato del archivo .conf:**

```bash
# Nombre legible que aparecerá en el dispositivo Garmin
NOMBRE_MAPA="Mi Zona"

# Bounding box
BBOX_SUR=40.0
BBOX_NORTE=42.5
BBOX_OESTE=-2.0
BBOX_ESTE=1.0

# Polígono para recorte fino (ruta relativa al repo).
# Si está vacío (""), se genera automáticamente un rectángulo desde el bbox.
POLIGONO=""

# URLs de Geofabrik (una o más)
FUENTES_OSM=(
    "http://download.geofabrik.de/europe/spain/aragon-latest.osm.pbf"
)

# ID base de 3 dígitos para mkgmap. DEBE ser único entre todas las zonas.
MAPID_BASE="891"

# Memoria RAM para Java
RAM_JAVA="4096m"
```

**Ejemplo completo — añadir mapa de los Pirineos Aragoneses:**

1. Crea `zonas/pirineo_aragones.conf`:

```bash
NOMBRE_MAPA="Pirineo Aragones"
BBOX_SUR=42.0
BBOX_NORTE=43.0
BBOX_OESTE=-1.0
BBOX_ESTE=1.0
POLIGONO=""
FUENTES_OSM=(
    "http://download.geofabrik.de/europe/spain/aragon-latest.osm.pbf"
)
MAPID_BASE="891"
RAM_JAVA="4096m"
```

2. Opcionalmente descarga curvas de nivel:
```bash
bash descargar_hgt.sh pirineo_aragones
```

3. Genera el mapa:
```bash
bash crear_mapa.sh pirineo_aragones
```

4. El resultado aparece en `salida/MapRando_Pirineo_Aragones_FECHA.img`.

**Notas importantes:**
- Cada zona debe tener un `MAPID_BASE` diferente para evitar conflictos de IDs en el Garmin.
- Si defines `POLIGONO`, la ruta debe ser relativa al directorio raíz del repo y el archivo debe existir.
- Para zonas con varias fuentes OSM solapadas (como Pirineos), el script las recorta al polígono en paralelo y las fusiona con `osmium merge`.
- Los rangos actuales en uso: `889` (Pirineos), `890` (Mallorca). Usa `891` en adelante para nuevas zonas.

