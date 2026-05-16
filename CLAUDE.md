# CLAUDE.md — Handoff para sesiones futuras

Este archivo contiene todo el contexto necesario para continuar el trabajo sin
historial de conversación previo. Leelo íntegramente antes de tocar nada.


## Resumen ejecutivo

`maps-garmin` es una herramienta de línea de comandos para generar mapas
Garmin (.img) de senderismo a partir de datos OpenStreetMap y modelos de
elevación. Funciona para cualquier zona geográfica: el usuario define un
archivo `.conf` con el bounding box, las fuentes OSM y los parámetros de build.

Estado actual (mayo 2026):
- Pipeline end-to-end validada con un build real completo (~18 min, ~11 GB RAM
  libre, .img de ~475 MB con curvas de nivel).
- Editor web (`editor/`) recién creado, funcional en código, aún sin validar
  en navegador por el usuario.
- Pendiente de prueba en navegador: pestaña de edición de colores de senderos.
- CI en rama local `ci-pending`, no en `main` (ver limitación PAT más abajo).


## Localización y repos

- **Working dir activo:** `/home/wzk/ws/maps/maps-garmin/`
- **Repo GitHub:** https://github.com/wozzeck/maps-garmin (público, rama `main`)
- **Origen:** fork reescrito en español de
  https://gitlab.com/ravenfeld/garmincustommap (Alexis Lecanu)
- **Sandbox antiguo (NO activo):** `/home/wzk/ws/maps/garmincustommap/`
  Es el fork original con el historial de git y datos de un build de prueba.
  No contiene los scripts actuales. No toques ni menciones ese directorio
  salvo que el usuario lo pida explícitamente.


## Limitación del CI / Personal Access Token

El archivo `.github/workflows/ci.yml` existe en la rama local `ci-pending`
pero NO está en `main`. La razón es que el PAT (Personal Access Token) del
propietario no tiene el scope `workflow`, necesario para hacer push de archivos
en `.github/workflows/`. Para subirlo hay dos opciones:

1. Regenerar el PAT en GitHub Settings > Developer settings > Personal access
   tokens, añadir el scope `workflow`, y hacer push desde la rama `ci-pending`.
2. Crear el archivo directamente desde la interfaz web de GitHub (Actions >
   crear workflow nuevo o subir el archivo).

No intentes hacer push del CI sin que el usuario confirme que tiene el PAT
correcto. El push fallará con error 403.


## Convenciones técnicas críticas

Estas convenciones no son obvias del código. Un Claude nuevo que no las conozca
romperá cosas. Leerlas antes de cualquier modificación.

### 1. style/rando.txt es CP1252 + CRLF

`style/rando.txt` es un archivo TYP de Garmin. Su codificación es CP1252
(Latin-1 de Windows) y usa saltos de línea CRLF (`\r\n`). Nunca editarlo en
modo texto si el editor normaliza saltos de línea. En Python, leerlo siempre
como bytes y decodificar explícitamente:

```python
texto = ruta.read_bytes().decode('cp1252')
```

Al escribirlo de vuelta:

```python
ruta.write_bytes(texto.encode('cp1252'))
```

No usar `open(..., encoding='cp1252')` porque algunos entornos normalizan
`\r\n` a `\n` al abrir en modo texto. Los scripts `aplicar_estilo.py` y
`estilo_a_json.py` ya lo hacen correctamente.

### 2. Los recortes osmium son secuenciales por defecto

`crear_mapa.sh` recorta cada fuente OSM con `osmium extract` de forma
secuencial (`PARALELISMO_OSMIUM=1` por defecto). El modo paralelo existe
(`PARALELISMO_OSMIUM=N` en el .conf) pero agota la RAM en máquinas con
menos de ~16 GB libres cuando hay varias fuentes grandes. El default
secuencial es conservador pero estable. No cambies el default sin que el
usuario lo pida.

### 3. La RAM de Java se configura por zona, no globalmente

`RAM_JAVA` está definido en cada `.conf` de zona, no en un archivo global.
El proyecto original usaba 32 GB hardcoded. Los valores típicos actuales:
- Zona pequeña (isla, provincia): `4096m`
- Zona media (región): `4096m` a `6144m`
- Zona grande (Pirineos, país): `8192m`

Si un build falla con `OutOfMemoryError`, subir `RAM_JAVA` en el `.conf`.

### 4. construir.sh usa find en vez de ls para contar archivos

`construir.sh` cuenta tiles con `find . -maxdepth 1 -name '*.osm.gz' | wc -l`
en lugar de `ls ./*.osm.gz | wc -l`. Esto es deliberado: con `set -euo pipefail`
activo, el patrón glob de ls aborta el script cuando no hay matches. El `find`
devuelve 0 sin error cuando no hay archivos. No cambiar este patrón.

### 5. Versiones de mkgmap y splitter

`download_require.sh` usa `mkgmap-r4924` y `splitter-r654`. Estas son las
versiones que funcionan con el estilo actual. Las versiones del proyecto
original (anteriores) ya no están disponibles en mkgmap.org.uk. Si hay que
actualizar, verificar que los cambios de API de mkgmap no rompan
`options_rando.args` ni `options_courbes.args`.

### 6. pyhgtmap en Ubuntu 24.04

En Ubuntu 24.04, la instalación correcta es:

```bash
pip install --user --break-system-packages pyhgtmap
```

El flag `--break-system-packages` es obligatorio por PEP 668. `descargar_hgt.sh`
llama a pyhgtmap con multiples fuentes:

```
--sources=sonn1,view1,alos1,srtm1
```

El orden importa: Sonny (Europa, alta resolución) primero, SRTM al final como
fallback. Las URLs directas de NASA SRTM dan 404 actualmente, de ahí el modo
multi-source. pyhgtmap gestiona la descarga y el cacheo de tiles HGT
automáticamente en `dem/<zona>/cache/`.

### 7. El editor web NO toca style/rando.txt

El editor (`editor/`) produce únicamente `zonas/<zona>.estilo.json`, un JSON
de colores. Nunca escribe ni lee `style/rando.txt` directamente (que es
CP1252). La traducción del JSON al TYP la hace `aplicar_estilo.py`.

`crear_mapa.sh` invoca `aplicar_estilo.py` antes del build y restaura
`style/rando.txt` desde `style/rando.txt.orig` al terminar (o si falla),
mediante un `trap EXIT`. De esta forma el estilo base nunca queda en un
estado intermedio.

### 8. Flujo de datos completo del estilo

```
style/rando.txt (CP1252+CRLF, base)
    |
    |  python3 estilo_a_json.py
    v
datos/estilo_actual.json  (UTF-8, incluido en el repo, para el editor web)
    |
    |  editor web (pestaña Estilo, en navegador)
    v
zonas/<zona>.estilo.json  (UTF-8, cambios de color para esa zona)
    |
    |  python3 aplicar_estilo.py <zona>
    |  (o automáticamente via crear_mapa.sh si existe el .estilo.json)
    v
style/rando.txt  (modificado temporalmente; se restaura tras el build)
```

Si se modifica `style/rando.txt` directamente (p.ej. con TYPViewer), hay que
regenerar `datos/estilo_actual.json` con `estilo_a_json.py` para que el editor
web refleje el estado actual.


## Arquitectura del pipeline

### Flujo OSM → .img

```
Geofabrik (.osm.pbf por región)
    |
    |  curl (crear_mapa.sh paso 4)
    v
carte_<zona>/origen/<region>.osm.pbf

    |
    |  osmium extract (crear_mapa.sh paso 5, secuencial por defecto)
    v
carte_<zona>/origen/<region>-<zona>.osm.pbf  (recortado al polígono)

    |
    |  osmium merge (crear_mapa.sh paso 6, solo si hay >1 fuente)
    v
carte_<zona>/<zona>.osm.pbf  (combinado)

    |
    |  splitter (construir.sh bloque 2)
    |  --mapid=44<MAPID_BASE>000 --max-nodes=1000000
    |  --route-rel-values=foot,hiking,bicycle
    v
carte_<zona>/44<MAPID_BASE>xxx.osm.pbf  (tiles)
carte_<zona>/map.args

    |
    |  mkgmap (construir.sh bloque 3)
    |  -c options_rando.args -c map.args
    v
carte_<zona>/44<MAPID_BASE>xxx.img  (tiles compilados)

    |
    |  (si hay curvas de nivel: descargar_hgt.sh genera .osm.gz
    |   que construir.sh procesa en bloque 1 antes que el OSM)
    |
    |  mkgmap --gmapsupp (construir.sh bloque 4)
    v
carte_<zona>/gmapsupp.img

    |
    |  mv a salida/
    v
salida/MapRando_<Nombre>_AAAA_MM_DD.img
```

### Curvas de nivel (flujo adicional)

```
dem/<zona>/cache/  (tiles HGT, descargados y cacheados por pyhgtmap)
    |
    |  pyhgtmap --area=... --sources=sonn1,view1,alos1,srtm1 --step=10 --gzip=1
    v
dem/<zona>/*.osm.gz

    |
    |  mv a carte_<zona>/
    v
carte_<zona>/*.osm.gz

    |  splitter (construir.sh bloque 1, una pasada por cada .osm.gz)
    |  --mapid=55<MAPID_BASE>xxx
    v
carte_<zona>/55<MAPID_BASE>xxx.img  (tiles de curvas)
```

Los tiles de curvas (55xxx) y los OSM (44xxx) se ensamblan juntos en el
`gmapsupp.img` final.

### IDs de mapa

- Capa OSM: `44<MAPID_BASE>000` hasta `44<MAPID_BASE>999`
- Capa curvas: `55<MAPID_BASE>000` hasta `55<MAPID_BASE>999`
- IDs en uso: `889` (Pirineos), `890` (Mallorca)
- Para nuevas zonas usar cualquier valor libre de 3 dígitos (sugerido: 500-799
  o 900+). El MAPID_BASE debe ser único en el Garmin o los mapas se
  sobrescriben entre sí.


## Cómo probar algo sin un build completo de 18 minutos

- **Zona pequeña:** usar `mallorca` como zona de prueba. Un build de Mallorca
  tarda ~3-5 minutos y usa ~2-3 GB de RAM. Es la referencia para validar
  cambios de pipeline.

- **Dry-run del estilo:** `python3 aplicar_estilo.py mallorca --check` informa
  qué colores cambiaría sin modificar ningún archivo.

- **Solo compilar (si ya existen los .pbf):** ejecutar `bash construir.sh
  mallorca` directamente, sin pasar por el pipeline de descarga y recorte.

- **Regenerar el JSON del estilo:** `python3 estilo_a_json.py` (tarda segundos).

- **Ver el catálogo de tipos de línea:** `python3 gen_tipos_linea.py` genera
  `tipos_de_linea.html`, abrir en navegador.

- **El editor web:** `python3 -m http.server 8080` desde el raíz del repo y
  abrir http://localhost:8080/editor/. No requiere ningún build previo.


## Pendientes conocidos

1. **Validar el editor en navegador.** El usuario no lo ha probado en navegador
   todavía. El código existe pero puede tener bugs de UX o de integración con
   los JSON.

2. **Personalización de colores de senderos.** Es el objetivo principal del
   editor. El flujo técnico ya está implementado (editor → .estilo.json →
   aplicar_estilo.py → rando.txt). Falta que el usuario lo pruebe de punta
   a punta.

3. **CI en rama ci-pending.** Subir `.github/workflows/ci.yml` a `main`
   requiere regenerar el PAT con scope `workflow` o crear el archivo desde
   la web de GitHub. Ver sección "Limitación del CI" arriba.

4. **tipos_de_linea.html tiene rutas hardcoded.** En `gen_tipos_linea.py`,
   `main()` usa rutas absolutas hardcoded al directorio del usuario. Si otra
   persona clona el repo, fallará. Pendiente refactorizar para usar rutas
   relativas al script (como hacen los demás scripts).


## Preferencias del usuario

- Responde siempre en español.
- Para tareas self-contained (un script, un archivo, un análisis acotado),
  delega en subagentes con modelos rápidos (haiku / sonnet) cuando sea
  posible. El usuario lo ha pedido explícitamente más de una vez: es el modo
  de trabajo por defecto, no una excepción.
- No hagas git commits ni push sin que el usuario lo pida explícitamente.
- No modifiques archivos que no están en el scope de la tarea.
- No crees archivos de documentación (.md) salvo que el usuario los pida.


## Primeros pasos para una sesión nueva

1. Lee este archivo completo.
2. Lee `README.md` para tener el panorama general.
3. Lee `zonas/template.conf` y `zonas/mallorca.conf` para entender la
   estructura de configuración de zona.
4. Si vas a tocar el pipeline, lee `crear_mapa.sh` y `construir.sh`.
5. Si vas a tocar el estilo, lee `aplicar_estilo.py` y recuerda la convención
   CP1252+CRLF antes de abrir cualquier archivo en `style/`.
6. Si vas a tocar el editor web, lee `editor/app.js` (las primeras 100 líneas
   definen el estado global y las utilidades clave) y `editor/index.html`.
7. Para validar cualquier cambio, usa `mallorca` como zona de prueba.
8. Antes de proponer cambios al pipeline, comprueba que `set -euo pipefail`
   sigue siendo compatible (en particular, no uses patrones glob de `ls` donde
   el directorio puede estar vacío).
