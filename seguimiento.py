"""Modulo de seguimiento: recordatorio unico y mensajes de la prueba de 14 dias."""

from __future__ import annotations

import argparse
import random
import sys
import webbrowser
from datetime import datetime

import config
import database
from bot2_mensajero import armar_texto, link_wa

DIAS_PRUEBA = config.DIAS_PRUEBA
SEGUIMIENTOS = [(1, "dia_1"), (2, "dia_2"), (7, "dia_7"), (12, "dia_12")]


def entregar(contacto, texto: str, variante: str, dry_run: bool, auto: bool) -> str:
    if dry_run:
        database.registrar_envio_simulado(contacto["id"], variante, "seguimiento", texto)
        return "simulado"
    if auto:
        webbrowser.open(link_wa(contacto["telefono"], texto))
        database.registrar_envio(contacto["id"], variante, "seguimiento", texto, "enviado")
        return "enviado"
    r = input("  Enviás vos? [s/N/q] ").strip().lower()
    if r == "q":
        return "cortado"
    if r != "s":
        return "salteado"
    webbrowser.open(link_wa(contacto["telefono"], texto))
    database.registrar_envio(contacto["id"], variante, "seguimiento", texto, "enviado")
    return "enviado"


def bloque(contacto, texto: str, etiqueta: str) -> None:
    print("-" * 60)
    print(f"[{contacto['id']}] {contacto['nombre']} ({contacto['telefono']}) - {etiqueta}")
    print(texto)
    print("-" * 60)


def cmd_recordatorio(args, mensajes: dict) -> None:
    for contacto in database.necesita_recordatorio(args.dias):
        ya_usada = contacto["variante_usada"]
        candidatas = [v for v in mensajes["variantes"] if v["id"] != ya_usada]
        if not candidatas:
            continue
        texto = armar_texto(
            random.choice(candidatas)["texto"], contacto, mensajes
        )
        bloque(contacto, texto, "recordatorio")
        resultado = entregar(contacto, texto, "recordatorio", args.dry_run, args.auto)
        if resultado == "enviado":
            database.marcar_registro(contacto["id"], "recordatorio")
            print(f"  enviado, quedan {args.dias} dias para cerrarlo como sin_respuesta\n")
        else:
            print(f"  {resultado}\n")


def cmd_cerrar(args) -> None:
    with database.conectar() as c:
        filas = list(
            c.execute(
                """select * from contactos
                   where estado = 'enviado'
                     and fecha_recordatorio is not null
                     and fecha_respuesta is null
                     and julianday('now','localtime') - julianday(fecha_recordatorio) >= ?""",
                (args.dias,),
            ).fetchall()
        )
    for f in filas:
        database.cambiar_estado(f["id"], "sin_respuesta", forzar=True)
        print(f"[{f['id']}] {f['nombre']} -> sin_respuesta (no insistir mas)")
    if not filas:
        print("Nadie para cerrar todavia.")


def cmd_inicio_prueba(telefono: str) -> None:
    contacto = database.por_telefono(telefono)
    if contacto is None:
        print(f"No conozco {telefono}.")
        return
    database.marcar_registro(contacto["id"], "inicio_prueba")
    database.cambiar_estado(contacto["id"], "empezó_prueba", forzar=True)
    print(f"[{contacto['id']}] {contacto['nombre']} -> empezó_prueba, vence en {DIAS_PRUEBA} dias.")
    print("Recordatorio: en la consola de Kahabox ponele la fecha de vencimiento a la sucursal.")


def cmd_prueba(args, mensajes: dict) -> None:
    pendientes = 0
    for contacto in database.listar(estado="empezó_prueba", limite=200):
        if not contacto["fecha_inicio_prueba"]:
            continue
        inicio = datetime.fromisoformat(contacto["fecha_inicio_prueba"])
        dias = (datetime.now(inicio.tzinfo) - inicio).days
        objetivo = None
        for dia, clave in SEGUIMIENTOS:
            if dias >= dia and not database.ya_envio(contacto["id"], f"prueba_{clave}"):
                objetivo = (dia, clave)
        if objetivo is None:
            continue
        dia, clave = objetivo
        texto = armar_texto(
            mensajes["prueba_14_dias"][clave], contacto, mensajes
        )
        bloque(contacto, texto, f"dia {dia} de la prueba")
        resultado = entregar(contacto, texto, f"prueba_{clave}", args.dry_run, args.auto)
        print(f"  {resultado}\n")
        if resultado == "cortado":
            break
        pendientes += 1
    if not pendientes:
        print("No hay mensajes de prueba vencidos todavia.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seguimiento de contactos")
    parser.add_argument("--recordatorio", action="store_true")
    parser.add_argument("--cerrar-sin-respuesta", action="store_true")
    parser.add_argument("--prueba", action="store_true", help="mensajes de la prueba de 14 dias")
    parser.add_argument("--inicio-prueba", metavar="TELEFONO")
    parser.add_argument("--dias", type=int, default=4, help="dias para el recordatorio")
    parser.add_argument("--auto", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    database.init()
    if args.inicio_prueba:
        cmd_inicio_prueba(args.inicio_prueba)
        return 0
    if not any([args.recordatorio, args.prueba, args.cerrar_sin_respuesta]):
        parser.print_help()
        return 1

    if args.cerrar_sin_respuesta:
        cmd_cerrar(args)
    if args.recordatorio or args.prueba:
        mensajes = config.cargar_mensajes()
        if args.recordatorio:
            cmd_recordatorio(args, mensajes)
        if args.prueba:
            cmd_prueba(args, mensajes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
