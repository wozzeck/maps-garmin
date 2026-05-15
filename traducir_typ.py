#!/usr/bin/env python3
"""Traduce los String1 del archivo rando.txt de francés a español.

Preserva la codificación CP1252 y los finales de línea CRLF originales,
porque mkgmap espera CodePage=1252 al compilar el TYP.
"""
from pathlib import Path

TRADUCCIONES = {
    "Fond": "Fondo",
    " Escalade": " Escalada",
    " Metropole": " Metropoli",
    "Aeroport": "Aeropuerto",
    "Aire de jeux": "Area de juegos",
    "Aire de picnic": "Area de picnic",
    "Autoroute": "Autopista",
    "Bananeraie": "Plantacion de platanos",
    "Barrage": "Presa",
    "Base militaire": "Base militar",
    "basin d eau": "Cuenca de agua",
    "Batiment": "Edificio",
    "Broussaille": "Maleza",
    "Cabane": "Cabana",
    "Cable transporteur": "Cable transportador",
    "Canne a sucre": "Cana de azucar",
    "Carriere": "Cantera",
    "Cascade": "Cascada",
    "Chemin agricole": "Camino agricola",
    "Chemin balisé non gr et grp": "Camino balizado (no GR/GRP)",
    "Chemin de service ou residence prive": "Camino de servicio o residencial privado",
    "Chemin exploitation carrosable moindre": "Camino de explotacion menor",
    "Chemin exploitation carrosable prive": "Camino de explotacion privado",
    "Chemin non visible": "Camino no visible",
    "Chemin peu visible": "Camino poco visible",
    "Chemin peu visible et interdit": "Camino poco visible y prohibido",
    "Chemin VTT balise": "Sendero BTT balizado",
    "cimetiere": "Cementerio",
    "Cloture": "Cerca",
    "Col": "Collado",
    "College, Universite": "Colegio, Universidad",
    "Complexe sportif": "Complejo deportivo",
    "Contour": "Contorno",
    "Cours d eau sousterrain": "Curso de agua subterraneo",
    "eau": "Agua",
    "Eglise": "Iglesia",
    "Escalier": "Escalera",
    "Falaise": "Acantilado",
    "Ferrie": "Ferri",
    "Foret": "Bosque",
    "Funicalaire": "Funicular",
    "Gestion des eaux": "Gestion de aguas",
    "Glacier": "Glaciar",
    # Variantes corruptas en el original (mojibake UTF-8 leído como CP1252)
    "GR, GRP, PR et chemin balisÃ©": "GR, GRP, PR y sendero balizado",
    "GR, GRP, PR et chemin balise": "GR, GRP, PR y sendero balizado",
    "Gravier": "Grava",
    "Grotte": "Cueva",
    "Hameau": "Caserio",
    "Ligne electrique": "Linea electrica",
    "MARAIS SALANTS": "SALINAS",
    "Mur anti bruit": "Muro antirruido",
    "Pairie": "Pradera",
    "Paletuvier": "Manglar",
    "Parc national": "Parque nacional",
    "Parc National": "Parque nacional",
    "Parking": "Aparcamiento",
    "Pierrier": "Pedregal",
    "Piste cyclable en gravier": "Carril bici de grava",
    "Piste cyclable": "Carril bici",
    "Piste de velo": "Pista ciclista",
    "Point d eau": "Punto de agua",
    "Point de vue": "Mirador",
    "Rail dans un tunnel": "Via en tunel",
    "Rail en construction dans un tunnel": "Via en construccion en tunel",
    "Rail en construction": "Via en construccion",
    "Rail non exploite": "Via sin explotar",
    "Rail": "Via ferrea",
    "Refuge": "Refugio",
    "Reserve nationale": "Reserva nacional",
    "reserve naturelle": "Reserva natural",
    "Reservoir d eau": "Deposito de agua",
    "Residentiel": "Residencial",
    "rocher": "Roca",
    "Route de service ou residence": "Carretera de servicio o residencial",
    "Route en construction": "Carretera en construccion",
    "Ruisseau intermittent": "Arroyo intermitente",
    "Ruiseau": "Arroyo",
    "Sable": "Arena",
    "Sentier interdit": "Sendero prohibido",
    "Sentier": "Sendero",
    "Sommet": "Cumbre",
    "Source": "Manantial",
    "Talus": "Talud",
    "Telepherique": "Teleferico",
    "Terrain de jeux": "Campo de juegos",
    "Terrain de tennis": "Pista de tenis",
    "Theatre historique": "Teatro historico",
    "Toilette": "Aseos",
    "Tram": "Tranvia",
    "Tunnel": "Tunel",
    "Verger, plantation, ferme": "Huerto, plantacion, granja",
    "Via ferrata": "Via ferrata",
    "Village": "Pueblo",
    "Ville": "Ciudad",
    "Voie principale": "Via principal",
    "Voie rapide": "Via rapida",
    "Voie secondaire": "Via secundaria",
    "Voie tertiaire": "Via terciaria",
    "Zone humide": "Zona humeda",
    "Zone industrielle, Zone commerciale": "Zona industrial, Zona comercial",
}

# Comentarios de cabecera (no afectan al render, solo a la legibilidad del fuente).
COMENTARIOS = {
    "; Fichier TYP compilé": "; Fichero TYP compilado",
    "; Longueur:": "; Longitud:",
    "; Décompilé le": "; Descompilado el",
    ";=========== COMMENTAIRES ======": ";=========== COMENTARIOS ======",
    ";=========== POLYGONES : PRIORITE DANS L'AFFICHAGE ======": ";=========== POLIGONOS: PRIORIDAD DE VISUALIZACION ======",
    ";===================== POLYGONES ========================": ";===================== POLIGONOS ========================",
}


def traducir(ruta_entrada: Path, ruta_salida: Path) -> None:
    # Leer en modo binario para no convertir CRLF a LF, y decodificar manualmente.
    crudo = ruta_entrada.read_bytes().decode("cp1252")
    cambios = 0
    # Ordenar por longitud descendente para evitar que un prefijo corto reemplace
    # antes que un texto más largo (p. ej. "Rail" vs "Rail dans un tunnel").
    for original in sorted(TRADUCCIONES, key=len, reverse=True):
        for prefijo_tipo in ("String1=0x00,", "String1=0x01,"):
            prefijo = f"{prefijo_tipo}{original}\r\n"
            traduccion = f"{prefijo_tipo}{TRADUCCIONES[original]}\r\n"
            if prefijo in crudo:
                n = crudo.count(prefijo)
                crudo = crudo.replace(prefijo, traduccion)
                cambios += n
    for original, traduccion in COMENTARIOS.items():
        if original in crudo:
            n = crudo.count(original)
            crudo = crudo.replace(original, traduccion)
            cambios += n
    ruta_salida.write_bytes(crudo.encode("cp1252"))
    print(f"Aplicadas {cambios} traducciones en {ruta_salida}")


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    traducir(base / "style" / "rando.txt", base / "style" / "rando.txt")
