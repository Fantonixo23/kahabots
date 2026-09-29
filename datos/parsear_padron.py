"""Parsea el padron oficial OCR y filtra por rubro y ciudad."""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
OCR = os.path.join(AQUI, "ocr")

sys.path.insert(0, RAIZ)
from bot1_recolector import normalizar  # noqa: E402

PERMITIDAS = {
    "CIUDAD DEL ESTE": "ciudad_del_este",
    "HERNANDARIAS": "hernandarias",
    "PRESIDENTE FRANCO": "presidente_franco",
}

EXCLUIDAS = [
    "SANTA RITA", "MINGA G", "ITAKYRY", "SAN ALBERTO", "ASUNCION", "LUQUE",
    "CAAGUAZ", "ENCARNACION", "PARAGUARI", "AYOLAS", "PIRAPO", "VILLA",
]

RE_CIUDAD = re.compile(
    r"(PUERTO\s+PRESIDENTE\s+FRANCO|CIUDAD\s+DE[Lr]\s+ESTE|CIUDAD\s+DEL\s+ESTE"
    r"|HERNANDARIAS|HERNANDAR[I1]AS|HERNANDADRIAS|PRESIDENTE\s+FRANCO"
    r"|P(?:RESIDENTE|TO|DTE\.?)\.?\s*FRANCO|PDTE\.?\s*FRANCO|PTE\.?\s*FRANCO)"
)

RE_TEL = re.compile(r"\(?\d[\d\s\-()./]{5,}\d")

RUBROS = {
    "veterinaria": [
        "VETERINAR", "VETERIN", "CLINICA VET", "CONSULTORIO VET", "AGROVET",
        "AGRO VET", "PET SHOP", "MASCOT", "ANIMAL", "VETERINARIA", "CLINICA VETERINARIA",
    ],
    "ferreteria": ["FERRETER", "HERRERIA", "HERRER", "FERRO", "MATERIALES DE CONSTRUCCION"],
    "electronica": [
        "ELECTRONIC", "ELECTRIC", "ELECTRODOM", "ELECTRO ", "TV ", "TELEVIS",
        "SONIDO", "ELECTROMAQ", "CELULAR", "MOVIL",
    ],
}

BASURA = [
    "LISTA DE FIRMAS", "Ramos:", "ALTO PARANA", "GOBIERNO NACIONAL", "Página",
    "Ciencias Veterinarias", "SAN LORENZO - PARAGUAY", "Tel", "e-mail", "Casilla",
    "Fax", "PRESIDENCIA", "ES (", "TET", "PANAQUAY", "pagina", "Página",
]


def limpiar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().upper()


def es_basura(linea: str) -> bool:
    limpia = limpiar(linea)
    if len(limpia) < 12:
        return True
    return any(b in limpia for b in BASURA)


def digitos(texto: str) -> str:
    return re.sub(r"[^0-9]", "", texto)


def rutas() -> list[str]:
    archivos = sorted(f for f in os.listdir(OCR) if f.endswith(".txt"))
    return [os.path.join(OCR, f) for f in archivos]


def detectar_rubro(nombre: str) -> str | None:
    n = limpiar(nombre)
    for rubro, claves in RUBROS.items():
        for clave in claves:
            if clave in n:
                return rubro
    return None


def detectar_ciudad(linea: str) -> tuple[str, int, int] | None:
    limpia = limpiar(linea)
    for coincidencia in reversed(list(RE_CIUDAD.finditer(limpia))):
        paren = coincidencia.group(0)
        if "FRANCO" in paren and "PUERTO" in paren:
            paren = "PUERTO PRESIDENTE FRANCO"
        clave = next((k for k in PERMITIDAS if limpiar(k) in paren), None)
        if clave is None and "FRANCO" in paren:
            clave = "PRESIDENTE FRANCO"
        if clave is None:
            continue
        if coincidencia.end() >= len(limpia) - 1:
            continue
        resto = limpia[coincidencia.end():]
        sangria = len(resto) - len(resto.lstrip())
        match = RE_TEL.match(resto.lstrip())
        if not match:
            continue
        return clave, coincidencia.start(), coincidencia.end() + sangria + len(match.group(0))
    return None


RUBRO_DOCUMENTO = "veterinaria"


def parsear_linea(linea: str, rubro_documento: str = RUBRO_DOCUMENTO) -> dict | None:
    if es_basura(linea):
        return None
    detectada = detectar_ciudad(linea)
    if not detectada:
        return None
    ciudad, inicio, fin = detectada
    limpia = limpiar(linea)
    nombre = limpia[:inicio]
    cuerpo = limpia[inicio:fin]
    direccion = limpia[fin:]

    nombre = re.sub(r"^[^A-Z0-9]+", "", nombre)
    nombre = re.sub(r"\s+", " ", nombre).strip()
    if len(nombre) < 4:
        return None

    solo_digitos = digitos(cuerpo)
    telefono = None
    for i in range(len(solo_digitos)):
        fragmento = solo_digitos[i:i + 10]
        candidato = None
        if len(fragmento) == 10 and fragmento[0] == "0" and fragmento[1] == "9":
            candidato = fragmento[1:]
        elif len(solo_digitos) >= 9 and i + 9 <= len(solo_digitos):
            nueve = solo_digitos[i:i + 9]
            if nueve[0] == "9":
                candidato = nueve
        if candidato:
            normal, es_celular = normalizar(candidato)
            if normal and es_celular:
                telefono = normal
                break
    if not telefono:
        return None

    rubro = rubro_documento or detectar_rubro(nombre)
    if not rubro:
        return None

    direccion = re.sub(r"\s+", " ", direccion).strip()
    direc_limpia = limpiar(direccion)
    if any(exclusion in direc_limpia for exclusion in EXCLUIDAS):
        return None

    return {
        "nombre": nombre.title(),
        "rubro": rubro,
        "telefono": telefono,
        "ciudad": PERMITIDAS[ciudad],
        "direccion": direccion[:120],
        "origen": "padron oficial SENACSA Alto Parana",
    }


def recolectar(rubro_documento: str = RUBRO_DOCUMENTO) -> list[dict]:
    vistos: dict[str, dict] = {}
    for ruta in rutas():
        with open(ruta, encoding="utf-8", errors="replace") as f:
            for linea in f:
                registro = parsear_linea(linea.strip(), rubro_documento)
                if registro and registro["telefono"] not in vistos:
                    vistos[registro["telefono"]] = registro
    return list(vistos.values())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--muestra", type=int, default=0)
    parser.add_argument("--csv")
    args = parser.parse_args()

    registros = recolectar()
    print(f"total con celular valido y ciudad permitida: {len(registros)}")
    for rubro in RUBROS:
        n = sum(1 for r in registros if r["rubro"] == rubro)
        print(f"  {rubro}: {n}")
    for ciudad in PERMITIDAS.values():
        n = sum(1 for r in registros if r["ciudad"] == ciudad)
        print(f"  {ciudad}: {n}")

    if args.muestra:
        print(f"\n--- MUESTRA DE {args.muestra} PARA VALIDAR ---")
        for r in registros[: args.muestra]:
            print(f"\n  nombre:    {r['nombre']}")
            print(f"  rubro:     {r['rubro']}")
            print(f"  ciudad:    {r['ciudad']}")
            print(f"  whatsapp:  {r['telefono']}")
            print(f"  direccion: {r['direccion']}")

    if args.csv:
        destino = args.csv if os.path.isabs(args.csv) else os.path.join(RAIZ, args.csv)
        with open(destino, "w", newline="", encoding="utf-8-sig") as f:
            escritor = csv.DictWriter(
                f,
                fieldnames=["nombre", "rubro", "telefono", "direccion", "ciudad", "origen"],
            )
            escritor.writeheader()
            for r in registros:
                fila = dict(r)
                fila["rubro"] = {"veterinaria": "veterinaria", "ferreteria": "ferreteria",
                                 "electronica": "electronica"}[r["rubro"]]
                escritor.writerow(fila)
        print(f"\nescrito: {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
