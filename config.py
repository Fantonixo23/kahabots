"""Configuracion central: rubros, zonas, limites de envio, horarios y estados."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent
load_dotenv(RAIZ / ".env")

for _salida in (sys.stdout, sys.stderr):
    try:
        _salida.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

DB_PATH = RAIZ / "contactos.db"
ARCHIVO_MENSAJES = RAIZ / "mensajes.json"

MI_NUMERO = os.getenv("MI_NUMERO", "").strip()
ZONA_HORARIA = os.getenv("ZONA_HORARIA", "America/Asuncion").strip()
LIMITE_DIARIO = int(os.getenv("LIMITE_DIARIO", "35"))

DIAS_PRUEBA = 14

RUBROS = {
    "ferreteria": {
        "etiqueta": "ferretería",
        "beneficio": "controlás el stock de tus productos y sabés cuándo reponer, sin planillas.",
        "evitar": "No mencionar venta por peso o por metro (tornillos, cables): Kahabox no lo cubre.",
    },
    "electronica": {
        "etiqueta": "electrónica",
        "beneficio": "cada producto se carga escaneando el código de barras, y si otro comercio ya lo cargó aparece solo.",
        "evitar": "",
    },
    "veterinaria": {
        "etiqueta": "veterinaria",
        "beneficio": "llevás el stock de tus productos y accesorios al día desde el celular.",
        "evitar": "No mencionar alimento balanceado suelto ni venta a granel: queda fuera del alcance.",
    },
    "ropa": {
        "etiqueta": "tienda de ropa",
        "beneficio": "controlás el stock por talle y color, para saber qué te queda de cada prenda.",
        "evitar": "",
    },
}

# Zona objetivo. Santa Rita, Minga Guazu e Itakyry quedan FUERA a proposito:
# son localidades distintas, no barrios de Ciudad del Este.
ZONAS = {
    "ciudad_del_este": ["Ciudad del Este"],
    "presidente_franco": ["Presidente Franco"],
    "hernandarias": ["Hernandarias"],
}

ZONAS_INICIALES = ["ciudad_del_este", "presidente_franco", "hernandarias"]

FRANJAS = {
    "manana": (9 * 60, 11 * 60),
    "tarde": (14 * 60 + 30, 16 * 60 + 30),
}
FRANJA_EVITAR = (12 * 60, 14 * 60)
HORA_CORTE = 18 * 60

DIAS_SEMANA_OK = {1, 2, 3}
TANDAS_POR_DIA = 2
PAUSA_MIN_SEG = 45
PAUSA_MAX_SEG = 120

ENVIADO_VIA_SEMI_AUTOMATICO = "wa.me"

ESTADOS = [
    "pendiente",
    "enviado",
    "respondió",
    "pidió_demo",
    "empezó_prueba",
    "compró",
    "no_interesado",
    "sin_respuesta",
    "no_contactar",
]

ESTADOS_TERMINALES = {"compró", "no_contactar"}

TRANSICIONES = {
    "pendiente": {"enviado", "no_contactar"},
    "enviado": {"respondió", "sin_respuesta", "no_contactar"},
    "respondió": {"pidió_demo", "no_interesado", "no_contactar", "empezó_prueba", "compró"},
    "pidió_demo": {"empezó_prueba", "compró", "no_interesado", "no_contactar"},
    "empezó_prueba": {"compró", "no_contactar"},
    "sin_respuesta": {"no_contactar"},
    "no_interesado": {"no_contactar"},
    "no_contactar": set(),
    "compró": set(),
}


def estados_validos() -> list[str]:
    return list(ESTADOS)


def transicion_permitida(desde: str, hacia: str) -> bool:
    return hacia in TRANSICIONES.get(desde, set())


def franja_actual(minuto_del_dia: int) -> str | None:
    for nombre, (inicio, fin) in FRANJAS.items():
        if inicio <= minuto_del_dia < fin:
            return nombre
    return None


def horario_permitido(minuto_del_dia: int, dia_semana: int) -> tuple[bool, str]:
    if dia_semana not in DIAS_SEMANA_OK:
        return False, "hoy no es martes, miercoles ni jueves"
    if minuto_del_dia >= HORA_CORTE:
        return False, "ya son las 18 o pasa, no se manda nada"
    if FRANJA_EVITAR[0] <= minuto_del_dia < FRANJA_EVITAR[1]:
        return False, "es hora de almuerzo/descanso"
    franja = franja_actual(minuto_del_dia)
    if franja is None:
        return False, "fuera de las franjas buenas (9-11 o 14:30-16:30)"
    return True, franja


def cargar_mensajes() -> dict:
    import json

    with open(ARCHIVO_MENSAJES, encoding="utf-8") as f:
        return json.load(f)
