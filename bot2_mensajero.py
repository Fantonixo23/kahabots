"""Bot 2: arma los mensajes de WhatsApp y abre el link wa.me para que vos envies."""

from __future__ import annotations

import argparse
import random
import sys
import time
import urllib.parse
import webbrowser
from datetime import datetime

import config
import database


def contar_por_variante() -> dict[str, int]:
    with database.conectar() as c:
        filas = c.execute(
            "select variante, count(*) as n from envios where modo = 'enviado' group by variante"
        ).fetchall()
    return {f["variante"]: f["n"] for f in filas}


def elegir_variante(mensajes: dict, rubro: str, excluir: set[str]) -> dict | None:
    conteo = contar_por_variante()
    candidatas = [
        v for v in mensajes["variantes"] if v["id"] not in excluir
    ] or list(mensajes["variantes"])
    candidatas.sort(key=lambda v: (conteo.get(v["id"], 0), random.random()))
    return candidatas[0]


def armar_texto(plantilla: str, contacto, mensajes: dict) -> str:
    saludo = random.choice(mensajes["saludos"])
    beneficio = ""
    if "{beneficio}" in plantilla:
        beneficio = config.RUBROS.get(
            contacto["rubro"], {"beneficio": ""}
        )["beneficio"]
    return (
        plantilla.replace("{saludo}", saludo)
        .replace("{nombre}", contacto["nombre"])
        .replace("{link_demo}", mensajes.get("link_demo", ""))
        .replace("{beneficio}", beneficio)
    )


def link_wa(telefono: str, texto: str) -> str:
    numero = telefono.lstrip("+")
    return "https://wa.me/" + numero + "?text=" + urllib.parse.quote(texto)


def mostrar(contacto, texto: str, variante: str) -> None:
    print("-" * 60)
    print(f"[{contacto['id']}] {contacto['nombre']}  ({contacto['rubro']}, {contacto['telefono']})")
    print(f"variante: {variante}")
    print(texto)
    print("-" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bot 2: mensajero semi-automatico")
    parser.add_argument("-n", "--cantidad", type=int, default=5)
    parser.add_argument("--rubro")
    parser.add_argument("--sin-pausas", action="store_true", help="no esperar entre mensajes")
    parser.add_argument("--ignorar-horario", action="store_true")
    parser.add_argument("--auto", action="store_true", help="abrir sin preguntar")
    parser.add_argument("--dry-run", action="store_true", help="imprime, no abre nada")
    args = parser.parse_args()

    database.init()
    mensajes = config.cargar_mensajes()

    if not mensajes.get("link_demo"):
        print("AVISO: link_demo vacio en mensajes.json. Cargar el link del video antes de enviar.\n")

    margen = database.margen_hoy()
    if margen <= 0:
        print(f"Limite diario alcanzado ({config.LIMITE_DIARIO}). Frena aca.")
        return 1
    pedido = min(args.cantidad, margen)
    if pedido < args.cantidad:
        print(f"Atencion: solo quedan {margen} mensajes hoy (limite {config.LIMITE_DIARIO}).\n")

    ahora = datetime.now()
    permitido, motivo = config.horario_permitido(ahora.hour * 60 + ahora.minute, ahora.weekday())
    if not permitido and not (args.ignorar_horario or args.dry_run):
        print(f"Horario NO permitido: {motivo}.")
        print("Usar --ignorar-horario si igual queres mandarlo ahora.\n")
        return 1
    franja = config.franja_actual(ahora.hour * 60 + ahora.minute) or "fuera_de_franja"

    contactos = database.pendientes_para_enviar(pedido * 2)
    if args.rubro:
        contactos = [c for c in contactos if c["rubro"] == args.rubro][:pedido]
    else:
        contactos = contactos[:pedido]
    if not contactos:
        print("No hay contactos pendientes con celular valido.")
        return 1

    tanda_actual = database.contar_envios_hoy() // max(
        1, config.LIMITE_DIARIO // config.TANDAS_POR_DIA
    )

    print(f"Mandando {len(contactos)} mensaje(s). Tanda {tanda_actual + 1}. Franja: {franja}.")
    print(f"Modo: {'DRY RUN (no se abre nada)' if args.dry_run else 'envio manual'}.\n")

    excluir: set[str] = set()
    for indice, contacto in enumerate(contactos, start=1):
        variante = elegir_variante(mensajes, contacto["rubro"], excluir)
        excluir = {variante["id"]}
        texto = armar_texto(variante["texto"], contacto, mensajes)
        mostrar(contacto, texto, variante["id"])

        if args.dry_run:
            database.registrar_envio_simulado(contacto["id"], variante["id"], franja, texto)
            print("  (simulado)\n")
        elif args.auto:
            webbrowser.open(link_wa(contacto["telefono"], texto))
            database.marcar_enviado(contacto["id"], variante["id"], franja, texto, "enviado")
            print("  abierto en el navegador\n")
        else:
            respuesta = input("  Enviás vos? [s/N/q] ").strip().lower()
            if respuesta == "q":
                print("Cortado.")
                break
            if respuesta != "s":
                print("  salteado\n")
                continue
            webbrowser.open(link_wa(contacto["telefono"], texto))
            database.marcar_enviado(contacto["id"], variante["id"], franja, texto, "enviado")
            print("  abierto en el navegador\n")

        if (
            not args.sin_pausas
            and not args.dry_run
            and indice < len(contactos)
        ):
            pausa = random.uniform(config.PAUSA_MIN_SEG, config.PAUSA_MAX_SEG)
            print(f"  esperando {pausa:.0f}s...")
            time.sleep(pausa)

    print(f"\nListo. Enviados hoy: {database.contar_envios_hoy()}/{config.LIMITE_DIARIO}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
