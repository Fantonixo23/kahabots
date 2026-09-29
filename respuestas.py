"""Modulo de respuestas: registra lo que contestaron y clasifica el mensaje."""

from __future__ import annotations

import argparse
import sys

import config
import database

BAJA = ["no", "basta", "no molestar", "no moleste", "deja de escribir", "dejar de escribir",
        "stop", "unsubscribe", "baja", "no me escribas", "no escribirme"]
NO_INTERESADO = ["no me interesa", "no gracias", "por ahora no", "despues", "mas adelante",
                 "no ahora", "no por ahora", "ahora no"]
PIDE_DEMO = ["demo", "video", "muestrame", "muestrameme", "como funciona", "ver el video",
             "pasame el", "enviame el", "quiero ver", "me gustaria ver", "explicame"]
PRECIO = ["cuanto", "precio", "cuesta", "vale", "cuanto sale", "cuanto está", "cuanto esta",
          "plan", "valor", "tarifa", "promo", "descuento"]
INTERESADO = ["si", "claro", "dale", "me interesa", "estoy interesado", "cuenta", "info",
              "pasame", "como me registro", "quiero probar", "probar"]


def clasificar(texto: str) -> tuple[str, str]:
    t = texto.lower().strip()
    if any(m in t for m in BAJA) and len(t) < 40:
        return "baja", "no_contactar"
    if any(m in t for m in NO_INTERESADO):
        return "no_interesado", "no_interesado"
    if any(m in t for m in PRECIO):
        return "pregunta", "respondió"
    if any(m in t for m in PIDE_DEMO):
        return "pide_demo", "pidió_demo"
    if any(m in t for m in INTERESADO):
        return "interesado", "respondió"
    return "sin_clasificar", ""


def prioridad(clasificacion: str) -> str:
    if clasificacion in ("pregunta", "pide_demo"):
        return "ATENDER YA"
    if clasificacion == "baja":
        return "baja (no volver a escribir)"
    return "normal"


def aplicar_estado(contacto_id: int, actual: str, nuevo: str) -> str:
    if not nuevo or nuevo == actual:
        return actual
    if config.transicion_permitida(actual, nuevo):
        return database.cambiar_estado(contacto_id, nuevo)
    if (
        actual == "enviado"
        and config.transicion_permitida("enviado", "respondió")
        and config.transicion_permitida("respondió", nuevo)
    ):
        database.cambiar_estado(contacto_id, "respondió")
        return database.cambiar_estado(contacto_id, nuevo)
    raise ValueError(f"no hay camino de {actual} a {nuevo}")


def plantilla_para(clasificacion: str) -> str:
    p = config.cargar_mensajes().get("respuestas_plantilla", {})
    return p.get(clasificacion, "")


def mostrar_plantilla(nombre: str, clasificacion: str) -> None:
    texto = plantilla_para(clasificacion)
    if not texto:
        return
    salida = texto.replace("{nombre}", nombre).replace(
        "{link_demo}", config.cargar_mensajes().get("link_demo", "")
    )
    print("\nRespuesta sugerida (copiala vos, no se envia solo):")
    print(salida)


def main() -> int:
    parser = argparse.ArgumentParser(description="Registrar y clasificar respuestas")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--telefono", help="telefono del contacto (formato E164)")
    grupo.add_argument("--listar", action="store_true", help="mostrar quien respondio")
    grupo.add_argument("--bajas", action="store_true", help="mostrar la lista negra")
    parser.add_argument("--texto", help="lo que contestaron")
    parser.add_argument("--manual", help="forzar la clasificacion")
    args = parser.parse_args()

    database.init()

    if args.listar:
        filas = database.listar(estado="respondió", limite=100)
        if not filas:
            print("Nadie respondio todavia.")
            return 0
        for f in filas:
            print(f"[{f['id']}] {f['nombre']} ({f['telefono']})")
            print(f"    {f['texto_respuesta']}")
        return 0

    if args.bajas:
        filas = database.listar(estado="no_contactar", limite=500)
        print(f"Lista negra: {len(filas)} contactos. No se les escribe nunca mas.")
        for f in filas:
            print(f"  [{f['id']}] {f['nombre']} ({f['telefono']})")
        return 0

    if not args.texto:
        print("Falta --texto con lo que contestaron.")
        return 1

    contacto = database.por_telefono(args.telefono)
    if contacto is None:
        print(f"No conozco el numero {args.telefono}. Corregi o cargalo primero.")
        return 1

    clasificacion, nuevo_estado = clasificar(args.texto)
    if args.manual:
        clasificacion = args.manual
        nuevo_estado = args.manual

    database.registrar_respuesta(contacto["id"], args.texto, clasificacion)
    if nuevo_estado and nuevo_estado != contacto["estado"]:
        try:
            aplicar_estado(contacto["id"], contacto["estado"], nuevo_estado)
        except ValueError as exc:
            print(f"Aviso: {exc}")

    print(f"[{contacto['id']}] {contacto['nombre']} ({contacto['telefono']})")
    print(f"  estado: {contacto['estado']} -> {database.obtener(contacto['id'])['estado']}")
    print(f"  clasificacion: {clasificacion}  prioridad: {prioridad(clasificacion)}")
    if clasificacion in ("pide_demo", "no_interesado", "pregunta"):
        mostrar_plantilla(contacto["nombre"], clasificacion)
    return 0


if __name__ == "__main__":
    sys.exit(main())
