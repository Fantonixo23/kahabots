"""Reportes del embudo: resultados por variante, rubro y franja horaria."""

from __future__ import annotations

import argparse
import sys

import config
import database

RESPONDIERON = ("respondió", "pidió_demo", "empezó_prueba", "compró")


def tabla(titulo: str, filas: list[tuple], cabeceras: list[str]) -> None:
    print(f"\n=== {titulo} ===")
    if not filas:
        print("sin datos")
        return
    anchos = [len(h) for h in cabeceras]
    for fila in filas:
        for i, celda in enumerate(fila):
            anchos[i] = max(anchos[i], len(str(celda)))
    print("  ".join(h.ljust(anchos[i]) for i, h in enumerate(cabeceras)))
    print("  ".join("-" * a for a in anchos))
    for fila in filas:
        print("  ".join(str(c).ljust(anchos[i]) for i, c in enumerate(fila)))


def resumen_embudo() -> None:
    r = database.resumen()
    print(f"Contactos totales: {r['total']}   con celular: {r['celulares']}")
    enviados = 0
    with database.conectar() as c:
        enviados = c.execute(
            "select count(*) as n from envios where modo = 'enviado'"
        ).fetchone()["n"]
        respondieron = c.execute(
            "select count(*) as n from contactos where fecha_respuesta is not null"
        ).fetchone()["n"]
        clics = c.execute(
            "select count(*) as n from contactos where clic_en_link = 1"
        ).fetchone()["n"]
    print(f"Mensajes enviados: {enviados}   respondieron: {respondieron}   clics en link: {clics}")
    if enviados:
        print(f"Tasa de respuesta: {respondieron / enviados:.1%}")

    filas = []
    for estado in config.ESTADOS:
        n = r["por_estado"].get(estado, 0)
        if n:
            filas.append((estado, n, f"{n / r['total']:.1%}" if r["total"] else "-"))
    tabla("Embudo", filas, ["estado", "contactos", "% del total"])


def por_dimensión(columna: str, titulo: str) -> None:
    marcas = ",".join("?" for _ in RESPONDIERON)
    with database.conectar() as c:
        filas = list(
            c.execute(
                f"""select {columna} as grupo,
                           count(*) as enviados,
                           sum(case when c.fecha_respuesta is not null then 1 else 0 end) as respondio
                    from envios e join contactos c on c.id = e.contacto_id
                    where e.modo = 'enviado'
                    group by {columna} order by enviados desc"""
            ).fetchall()
        )
    tabla(
        f"Tasa de respuesta por {titulo}",
        [
            (f["grupo"] or "-", f["enviados"], f["respondio"],
             f"{f['respondio'] / f['enviados']:.1%}" if f["enviados"] else "-")
            for f in filas
        ],
        [titulo, "enviados", "respondieron", "tasa"],
    )


def por_dia() -> None:
    with database.conectar() as c:
        filas = list(
            c.execute(
                """select substr(fecha, 1, 10) as dia, count(*) as n
                   from envios where modo = 'enviado' group by dia order by dia desc limit 30"""
            ).fetchall()
        )
    tabla(
        "Mensajes por dia",
        [(f["dia"], f["n"]) for f in filas],
        ["fecha", "mensajes"],
    )


def principal() -> None:
    resumen_embudo()
    por_dimensión("variante", "variante")
    por_dimensión("c.rubro", "rubro")
    por_dimensión("franja", "franja horaria")
    por_dia()

    bajas = database.listar(estado="no_contactar", limite=500)
    quejas = database.listar(estado="no_interesado", limite=500)
    print(f"\nBajas (no_contactar): {len(bajas)}")
    print(f"No interesados: {len(quejas)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Reportes del embudo")
    parser.add_argument("--backup", action="store_true", help="respaldo de la base")
    args = parser.parse_args()

    database.init()
    if args.backup:
        print(f"Respaldo en {database.guardar_backup()}")
        return 0
    principal()
    return 0


if __name__ == "__main__":
    sys.exit(main())
