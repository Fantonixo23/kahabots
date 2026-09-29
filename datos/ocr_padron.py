"""OCR del padron oficial de empresas de Alto Parana (PDF escaneado)."""

import os
import subprocess
import sys

import pymupdf

AQUI = os.path.dirname(os.path.abspath(__file__))
PDF = os.path.join(AQUI, "firmas_alto_parana.pdf")
TESSDATA = os.path.join(AQUI, "tessdata")
TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
SALIDA = os.path.join(AQUI, "ocr")
DPI = 300


def ocr_pagina(documento, indice: int) -> str:
    pagina = documento[indice]
    pix = pagina.get_pixmap(dpi=DPI)
    imagen = os.path.join(SALIDA, f"pag{indice + 1:03d}.png")
    pix.save(imagen)
    base = os.path.join(SALIDA, f"pag{indice + 1:03d}")
    subprocess.run(
        [
            TESSERACT, imagen, base,
            "-l", "spa",
            "--tessdata-dir", TESSDATA,
            "--psm", "6",
        ],
        check=True,
        capture_output=True,
    )
    with open(base + ".txt", encoding="utf-8", errors="replace") as f:
        return f.read()


def main() -> int:
    os.makedirs(SALIDA, exist_ok=True)
    documento = pymupdf.open(PDF)
    paginas = range(documento.page_count)
    if len(sys.argv) > 1:
        paginas = [int(sys.argv[1]) - 1]
    for indice in paginas:
        destino = os.path.join(SALIDA, f"pag{indice + 1:03d}.txt")
        if os.path.exists(destino):
            print(f"pagina {indice + 1}: ya existe")
            continue
        texto = ocr_pagina(documento, indice)
        with open(destino, "w", encoding="utf-8") as f:
            f.write(texto)
        print(f"pagina {indice + 1}: {len(texto)} caracteres")
    return 0


if __name__ == "__main__":
    sys.exit(main())
