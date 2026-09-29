"""Cuenta los negocios utilizables en el padron de Alto Parana (paginas 1-3)."""

import collections
import os

import parsear_padron as p

os.chdir(p.OCR)

regs = []
vistos = set()
for f in ["pag001.txt", "pag002.txt", "pag003.txt"]:
    for l in open(f, encoding="utf-8", errors="replace"):
        r = p.parsear_linea(l.strip(), "veterinaria")
        if r and r["telefono"] not in vistos:
            vistos.add(r["telefono"])
            regs.append(r)

print(f"ALTO PARANA (pag 1-3), veterinaria, 3 ciudades permitidas, con movil: {len(regs)}")
for c in ["ciudad_del_este", "hernandarias", "presidente_franco"]:
    print(f"  {c}: {sum(1 for r in regs if r['ciudad'] == c)}")

print("\nlineas por pagina y cuantas detectan ciudad:")
for f in ["pag001.txt", "pag002.txt", "pag003.txt"]:
    total = 0
    con_ciudad = 0
    for l in open(f, encoding="utf-8", errors="replace"):
        l = l.strip()
        if p.es_basura(l):
            continue
        total += 1
        if p.detectar_ciudad(l):
            con_ciudad += 1
    print(f"  {f}: utiles={total} con_ciudad_reconocible={con_ciudad}")
