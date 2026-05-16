#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generar_extractos.py — Genera datos/extractos_geofabrik.json

Descarga el índice oficial de Geofabrik (index-v1.json), filtra los extractos
relevantes para el caso de uso (Península Ibérica + Francia + Andorra +
vecinos europeos) y calcula el bounding box de cada uno a partir de su
geometría real.

El editor web usa este JSON para pintar los rectángulos de los extractos
sobre el mapa y, al dibujar un polígono, inferir qué extractos hay que
descargar (FUENTES_OSM).

Uso:
    python3 generar_extractos.py            # usa caché si existe
    python3 generar_extractos.py --refresh  # fuerza descarga del índice
"""
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent
OUT = REPO / "datos" / "extractos_geofabrik.json"
CACHE = Path("/tmp/geofabrik-index.json")
INDEX_URL = "https://download.geofabrik.de/index-v1.json"

# Extractos relevantes. Se incluye un extracto si:
#   - su id está en IDS_DIRECTOS, o
#   - su parent está en PADRES (trae todas las subregiones de ese país)
PADRES = {"spain", "france"}
IDS_DIRECTOS = {
    "spain", "france", "portugal", "andorra",
    "canary-islands",                       # España, pero cuelga de 'africa'
    # Vecinos europeos (por si una zona cruza frontera)
    "italy", "switzerland", "germany", "belgium",
    "netherlands", "luxembourg", "monaco",
    "great-britain", "ireland-and-northern-ireland",
}

# Traducción de los nombres más habituales (el resto se deja como viene).
NOMBRES_ES = {
    "Spain": "España", "France": "Francia", "Portugal": "Portugal",
    "Andorra": "Andorra", "Italy": "Italia", "Switzerland": "Suiza",
    "Germany": "Alemania", "Belgium": "Bélgica", "Netherlands": "Países Bajos",
    "Luxembourg": "Luxemburgo", "Monaco": "Mónaco",
    "Great Britain": "Gran Bretaña",
    "Ireland and Northern Ireland": "Irlanda",
    "Canary Islands": "Islas Canarias",
    "Andalucia": "Andalucía", "Aragon": "Aragón",
    "Asturias": "Asturias", "Cantabria": "Cantabria",
    "Castilla-La Mancha": "Castilla-La Mancha",
    "Castilla y Leon": "Castilla y León", "Cataluna": "Cataluña",
    "Ceuta": "Ceuta", "Extremadura": "Extremadura", "Galicia": "Galicia",
    "Islas Baleares": "Islas Baleares", "La Rioja": "La Rioja",
    "Madrid": "Madrid", "Melilla": "Melilla", "Murcia": "Murcia",
    "Navarra": "Navarra", "Pais Vasco": "País Vasco",
    "Valencia": "Comunidad Valenciana",
}


def descargar_indice(refresh: bool) -> dict:
    if CACHE.exists() and not refresh:
        print(f"Usando caché: {CACHE}")
        return json.loads(CACHE.read_text())
    print(f"Descargando {INDEX_URL} ...")
    with urllib.request.urlopen(INDEX_URL, timeout=60) as r:
        data = r.read()
    CACHE.write_bytes(data)
    return json.loads(data)


def bbox_de_geometria(geom: dict):
    """min/max lon/lat recorriendo todas las coordenadas del (Multi)Polygon."""
    min_lon = min_lat = float("inf")
    max_lon = max_lat = float("-inf")

    def recorrer(coords):
        nonlocal min_lon, min_lat, max_lon, max_lat
        # coords puede anidar varios niveles; las hojas son [lon, lat]
        if (isinstance(coords, list) and len(coords) == 2
                and isinstance(coords[0], (int, float))
                and isinstance(coords[1], (int, float))):
            lon, lat = coords
            min_lon = min(min_lon, lon)
            max_lon = max(max_lon, lon)
            min_lat = min(min_lat, lat)
            max_lat = max(max_lat, lat)
        elif isinstance(coords, list):
            for c in coords:
                recorrer(c)

    recorrer(geom.get("coordinates", []))
    if min_lon == float("inf"):
        return None
    return {
        "oeste": round(min_lon, 5),
        "sur": round(min_lat, 5),
        "este": round(max_lon, 5),
        "norte": round(max_lat, 5),
    }


def main() -> None:
    refresh = "--refresh" in sys.argv
    indice = descargar_indice(refresh)

    extractos = []
    for f in indice["features"]:
        p = f["properties"]
        pid = p.get("id", "")
        parent = p.get("parent", "")
        if not (pid in IDS_DIRECTOS or parent in PADRES):
            continue
        pbf = p.get("urls", {}).get("pbf")
        if not pbf:
            continue
        bbox = bbox_de_geometria(f.get("geometry", {}))
        if not bbox:
            print(f"  Aviso: {pid} sin geometría, omitido")
            continue
        nombre = p.get("name", pid)
        extractos.append({
            "id": pid,
            "nombre": nombre,
            "nombre_es": NOMBRES_ES.get(nombre, nombre),
            "padre": parent,
            "url": pbf,
            "bbox": bbox,
        })

    # Orden: primero países (parent == europe/africa), luego subregiones,
    # alfabético dentro de cada grupo.
    def clave(e):
        es_pais = e["padre"] in ("europe", "africa")
        return (0 if es_pais else 1, e["padre"], e["nombre_es"])

    extractos.sort(key=clave)

    salida = {
        "fuente": INDEX_URL,
        "generado": date.today().isoformat(),
        "total": len(extractos),
        "extractos": extractos,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(salida, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    print(f"Escrito {OUT}")
    print(f"  {len(extractos)} extractos")
    paises = [e for e in extractos if e["padre"] in ("europe", "africa")]
    print(f"  Países: {len(paises)} "
          f"({', '.join(e['nombre_es'] for e in paises)})")
    sub_es = [e for e in extractos if e["padre"] == "spain"]
    sub_fr = [e for e in extractos if e["padre"] == "france"]
    print(f"  Subregiones España: {len(sub_es)}")
    print(f"  Subregiones Francia: {len(sub_fr)}")


if __name__ == "__main__":
    main()
