"""Descarga los padrones oficiales de empresas de Paraguay (datos abiertos)."""

import os
import sys

import requests

FUNCIONES = {
    "firmas_alto_parana.pdf": "https://informacionpublica.paraguay.gov.py/public/7994003-ListadodeFirmasporDptopdf-ListadodeFirmasporDpto.pdf",
    "establecimientos_cigelec.pdf": "https://informacionpublica.paraguay.gov.py/public/2024/1734978631_3_LISTADOCIGELEC-COMER.pdf",
}

DESTINO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")

CABECERA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}


def main() -> int:
    os.makedirs(DESTINO, exist_ok=True)
    for nombre, url in FUNCIONES.items():
        ruta = os.path.join(DESTINO, nombre)
        if os.path.exists(ruta) and os.path.getsize(ruta) > 1000:
            print(f"ya esta: {nombre} ({os.path.getsize(ruta)} bytes)")
            continue
        print(f"bajando {nombre}...")
        try:
            r = requests.get(url, headers=CABECERA, timeout=120)
            r.raise_for_status()
            with open(ruta, "wb") as f:
                f.write(r.content)
            print(f"  ok: {len(r.content)} bytes")
        except Exception as exc:
            print(f"  fallo: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
