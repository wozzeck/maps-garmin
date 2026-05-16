#!/usr/bin/env python3
"""
aplicar_estilo.py — Aplica cambios de color de una zona al estilo TYP rando.txt.

Uso:
    python3 aplicar_estilo.py <zona> [--rando RUTA] [--check]

El fichero de estilo es CP1252 con finales de línea CRLF.
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')


def validar_color(color: str, tipo: str, canal: str) -> None:
    """Aborta si el color no tiene formato #RRGGBB."""
    if not COLOR_RE.match(color):
        print(f"ERROR: color inválido para tipo {tipo} ({canal}): {repr(color)}. "
              "Se esperaba #RRGGBB (6 dígitos hex).", file=sys.stderr)
        sys.exit(1)


def normalizar_hex_tipo(tipo: str) -> str:
    """Devuelve el tipo en minúsculas para búsquedas case-insensitive."""
    return tipo.lower()


# ---------------------------------------------------------------------------
# Lógica principal
# ---------------------------------------------------------------------------

def aplicar_cambios(texto: str, cambios: dict, check: bool) -> tuple[str, dict]:
    """
    Aplica los cambios de color al texto del estilo.

    Devuelve (nuevo_texto, resumen) donde resumen tiene:
        aplicados: list of (tipo, canal, viejo, nuevo)
        omitidos:  list of (tipo, canal, motivo)
        no_encontrados: list of tipo
    """
    resumen = {"aplicados": [], "omitidos": [], "no_encontrados": []}

    # Dividir en líneas preservando CRLF exactamente.
    # Dado que el archivo es CRLF puro, splitlines(True) devuelve líneas con \r\n.
    lineas = texto.splitlines(keepends=True)

    # Índice: tipo normalizado → rango [inicio_bloque, fin_bloque) en líneas
    # Un bloque empieza en la línea "[_line]" / "[_polygon]" / "[_point]" y
    # termina en la línea "[end]" / "[End]" (inclusive).
    # Construimos el índice al vuelo recorriendo una sola vez.

    # Para cada tipo en cambios necesitamos localizar su bloque.
    tipos_buscados = {normalizar_hex_tipo(t): t for t in cambios}
    bloques = {}   # tipo_norm → (idx_inicio, idx_fin_inclusive)

    en_bloque = False
    bloque_inicio = 0
    tipo_actual = None

    BLOQUE_INICIO_RE = re.compile(r'^\[_(?:line|polygon|point)\]', re.IGNORECASE)
    TIPO_RE = re.compile(r'^Type=(\S+)', re.IGNORECASE)
    BLOQUE_FIN_RE = re.compile(r'^\[end\]', re.IGNORECASE)

    for i, linea in enumerate(lineas):
        linea_strip = linea.rstrip('\r\n')
        if BLOQUE_INICIO_RE.match(linea_strip):
            en_bloque = True
            bloque_inicio = i
            tipo_actual = None
        elif en_bloque and tipo_actual is None:
            m = TIPO_RE.match(linea_strip)
            if m:
                tipo_norm = normalizar_hex_tipo(m.group(1))
                if tipo_norm in tipos_buscados:
                    tipo_actual = tipo_norm
        elif en_bloque and BLOQUE_FIN_RE.match(linea_strip):
            if tipo_actual is not None:
                bloques[tipo_actual] = (bloque_inicio, i)
            en_bloque = False
            tipo_actual = None

    # Procesar cada tipo en cambios
    for tipo_orig, sub_cambios in cambios.items():
        tipo_norm = normalizar_hex_tipo(tipo_orig)
        if tipo_norm not in bloques:
            resumen["no_encontrados"].append(tipo_orig)
            continue

        inicio, fin = bloques[tipo_norm]

        for canal, color_nuevo in sub_cambios.items():
            # canal es "day" o "night"
            if canal == "day":
                prefijo = "DaycustomColor:"
            elif canal == "night":
                prefijo = "NightcustomColor:"
            else:
                resumen["omitidos"].append((tipo_orig, canal, "canal desconocido (se esperaba 'day' o 'night')"))
                continue

            color_nuevo_upper = color_nuevo.upper()
            validar_color(color_nuevo_upper, tipo_orig, canal)

            # Buscar la línea dentro del bloque
            encontrado = False
            for j in range(inicio, fin + 1):
                linea_strip = lineas[j].rstrip('\r\n')
                if linea_strip.startswith(prefijo):
                    color_viejo = linea_strip[len(prefijo):]
                    nueva_linea = prefijo + color_nuevo_upper + "\r\n"
                    if color_viejo.upper() == color_nuevo_upper:
                        resumen["omitidos"].append(
                            (tipo_orig, canal, f"ya tiene el valor {color_nuevo_upper}")
                        )
                    else:
                        if not check:
                            lineas[j] = nueva_linea
                        resumen["aplicados"].append((tipo_orig, canal, color_viejo, color_nuevo_upper))
                    encontrado = True
                    break

            if not encontrado:
                resumen["omitidos"].append(
                    (tipo_orig, canal,
                     f"el bloque no tiene línea '{prefijo}' (solo se editan tipos con color personalizable)")
                )

    return "".join(lineas), resumen


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aplica cambios de color de una zona al estilo TYP rando.txt."
    )
    parser.add_argument("zona", help="Nombre de la zona (busca zonas/<zona>.estilo.json)")
    parser.add_argument("--rando", default=None,
                        help="Ruta al fichero rando.txt (por defecto: style/rando.txt junto al script)")
    parser.add_argument("--check", action="store_true",
                        help="Dry-run: informa qué cambiaría sin escribir nada")
    args = parser.parse_args()

    script_dir = Path(__file__).parent

    # Ruta al JSON de estilo
    estilo_path = script_dir / "zonas" / f"{args.zona}.estilo.json"
    if not estilo_path.exists():
        print(f"Sin estilo personalizado para {args.zona} (no existe {estilo_path})")
        return 0

    # Ruta al rando.txt
    rando_path = Path(args.rando) if args.rando else script_dir / "style" / "rando.txt"
    if not rando_path.exists():
        print(f"ERROR: no se encontró el fichero de estilo: {rando_path}", file=sys.stderr)
        return 1

    # Leer JSON
    try:
        with open(estilo_path, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"ERROR: no se pudo leer {estilo_path}: {e}", file=sys.stderr)
        return 1

    cambios: dict = datos.get("cambios", {})
    if not cambios:
        print(f"Sin cambios definidos en {estilo_path}")
        return 0

    # Validar todos los colores antes de tocar nada
    for tipo, sub in cambios.items():
        for canal, color in sub.items():
            if canal in ("day", "night"):
                validar_color(color.upper(), tipo, canal)

    # Leer rando.txt como bytes → decodificar cp1252
    try:
        raw = rando_path.read_bytes()
        texto = raw.decode("cp1252")
    except (OSError, UnicodeDecodeError) as e:
        print(f"ERROR: no se pudo leer {rando_path}: {e}", file=sys.stderr)
        return 1

    # Aplicar cambios
    texto_nuevo, resumen = aplicar_cambios(texto, cambios, check=args.check)

    # Imprimir resumen
    print(f"--- Resumen {'(dry-run) ' if args.check else ''}para zona: {args.zona} ---")
    for tipo, canal, viejo, nuevo in resumen["aplicados"]:
        accion = "cambiaría" if args.check else "cambiado"
        print(f"  [{accion}] {tipo} {canal}: {viejo} → {nuevo}")
    for tipo, canal, motivo in resumen["omitidos"]:
        print(f"  [omitido] {tipo} {canal}: {motivo}")
    for tipo in resumen["no_encontrados"]:
        print(f"  [no encontrado] tipo {tipo}: no existe ningún bloque con ese Type= en rando.txt")

    n_tipos = len(cambios)
    n_aplicados = len(resumen["aplicados"])
    n_omitidos = len(resumen["omitidos"])
    n_no_encontrados = len(resumen["no_encontrados"])
    print(f"Tipos procesados: {n_tipos} | Sub-cambios aplicados: {n_aplicados} | "
          f"Omitidos: {n_omitidos} | Tipos no encontrados: {n_no_encontrados}")

    if args.check:
        return 0

    if n_aplicados == 0:
        print("Nada que escribir.")
        return 0

    # Backup antes de escribir
    bak_path = rando_path.with_suffix(rando_path.suffix + ".bak")
    try:
        shutil.copy2(rando_path, bak_path)
        print(f"Backup: {bak_path}")
    except OSError as e:
        print(f"ERROR: no se pudo crear backup {bak_path}: {e}", file=sys.stderr)
        return 1

    # Escribir resultado en cp1252 (preserva CRLF tal como estaban en texto_nuevo)
    try:
        rando_path.write_bytes(texto_nuevo.encode("cp1252"))
        print(f"Escrito: {rando_path}")
    except (OSError, UnicodeEncodeError) as e:
        print(f"ERROR: no se pudo escribir {rando_path}: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
