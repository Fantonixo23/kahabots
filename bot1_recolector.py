"""Bot 1: carga negocios desde padrones oficiales y CSV, y guarda sus celulares.

Los datos vienen de fuentes públicas gratuitas. No se usa Google Places API
porque exige tarjeta de crédito y cobra por consulta. El flujo es:

    datos/ocr_padron.py   -> PDF oficial a texto (OCR)
    datos/parsear_padron.py -> texto a CSV de negocios filtrados
    bot1_recolector.py --importar-csv  -> contactos en la base
"""

from __future__ import annotations

import argparse
import csv
import sys

import phonenumbers

import config
import database


def normalizar(numero_crudo: str | None) -> tuple[str | None, bool]:
    if not numero_crudo:
        return None, False
    texto = "".join(ch for ch in numero_crudo if ch.isdigit() or ch == "+")
    if not texto.strip("+"):
        return None, False
    candidatos = [texto] if texto.startswith("+") else [texto, texto.lstrip("0")]
    for candidato in candidatos:
        try:
            numero = phonenumbers.parse(candidato, "PY")
        except phonenumbers.NumberParseException:
            continue
        if not phonenumbers.is_valid_number(numero):
            continue
        tipo = phonenumbers.number_type(numero)
        es_celular = tipo in (
            phonenumbers.PhoneNumberType.MOBILE,
            phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,
        )
        return (
            phonenumbers.format_number(numero, phonenumbers.PhoneNumberFormat.E164),
            es_celular,
        )
    return None, False


def exportar_csv(destino: str) -> None:
    with database.conectar() as c:
        filas = list(
            c.execute(
                "select id, nombre, rubro, telefono, direccion, link_maps, estado, fecha_captura from contactos"
            ).fetchall()
        )
    with open(destino, "w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=filas[0].keys() if filas else ["id"])
        escritor.writeheader()
        for fila in filas:
            escritor.writerow(dict(fila))
    print(f"exportado a {destino} ({len(filas)} filas)")


def _rubro_desde(valor: str) -> str | None:
    valor = (valor or "").strip().lower()
    for clave, datos in config.RUBROS.items():
        if valor == clave or valor == datos["etiqueta"].lower():
            return clave
    return None


def importar_csv(origen: str, dry_run: bool) -> None:
    with open(origen, encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        campos = {c.strip().lower() for c in (lector.fieldnames or [])}
        if not {"nombre", "telefono"} <= campos:
            print(
                "El CSV necesita al menos las columnas 'nombre' y 'telefono'.\n"
                "Opcionales: rubro, direccion, link_maps"
            )
            return
        conteo = {"agregados": 0, "duplicado": 0, "fijo": 0, "telefono_invalido": 0,
                  "rubro_desconocido": 0, "sin_nombre": 0}
        for fila in lector:
            limpio = {(k or "").strip().lower(): (v or "").strip() for k, v in fila.items()}
            nombre = limpio.get("nombre", "")
            if not nombre:
                conteo["sin_nombre"] += 1
                continue
            rubro = _rubro_desde(limpio.get("rubro", ""))
            if rubro is None:
                conteo["rubro_desconocido"] += 1
                print(f"  - {nombre}: rubro desconocido, se descarta")
                continue
            telefono, es_celular = normalizar(limpio.get("telefono"))
            if not telefono:
                conteo["telefono_invalido"] += 1
                print(f"  - {nombre}: telefono no valido, se descarta")
                continue
            if not es_celular:
                conteo["fijo"] += 1
                print(f"  - {nombre}: es fijo, se descarta")
                continue
            if database.por_telefono(telefono) is not None:
                conteo["duplicado"] += 1
                continue
            if dry_run:
                print(f"  ? (dry run) {nombre} -> {telefono}")
            else:
                database.agregar_contacto(
                    nombre=nombre,
                    rubro=rubro,
                    telefono=telefono,
                    es_celular=True,
                    direccion=limpio.get("direccion") or None,
                    link_maps=limpio.get("link_maps") or None,
                )
            conteo["agregados"] += 1
    print(f"\ncargados: {conteo['agregados']}")
    for clave, valor in conteo.items():
        if clave != "agregados" and valor:
            print(f"  {clave}: {valor}")


def escribir_plantilla(destino: str) -> None:
    with open(destino, "w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.writer(f)
        escritor.writerow(["nombre", "rubro", "telefono", "direccion", "link_maps"])
        for clave, datos in config.RUBROS.items():
            escritor.writerow(["Ejemplo SA", clave, "0981 123456", "Ejemplo 123", ""])
    print(f"plantilla creada en {destino}")
    print("Rubro valido: " + ", ".join(f"{k} ({v['etiqueta']})" for k, v in config.RUBROS.items()))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bot 1: carga negocios desde padrones oficiales y CSV"
    )
    parser.add_argument("--dry-run", action="store_true", help="no escribe en la base")
    parser.add_argument("--exportar-csv")
    parser.add_argument("--importar-csv", metavar="ARCHIVO")
    parser.add_argument("--plantilla", metavar="ARCHIVO", help="crea un CSV de ejemplo")
    args = parser.parse_args()

    database.init()

    if args.plantilla:
        escribir_plantilla(args.plantilla)
        return 0

    if args.importar_csv:
        importar_csv(args.importar_csv, dry_run=args.dry_run)
        return 0

    if args.exportar_csv:
        exportar_csv(args.exportar_csv)
        return 0

    print("No se paso ninguna accion. Opciones:\n"
          "  --plantilla archivo.csv        crea un CSV de ejemplo\n"
          "  --importar-csv archivo.csv     carga negocios (soporta el CSV de parsear_padron.py)\n"
          "  --exportar-csv archivo.csv     vuelca la base a CSV\n"
          "  --dry-run                      con --importar-csv, solo muestra\n"
          "\nFlujo completo:\n"
          "  python datos/ocr_padron.py\n"
          "  python datos/parsear_padron.py --csv datos/contactos.csv\n"
          "  python bot1_recolector.py --importar-csv datos/contactos.csv --dry-run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
