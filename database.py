"""Base de datos de contactos, embudo y log de envios (SQLite)."""

from __future__ import annotations

import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import config

SCHEMA = """
create table if not exists contactos (
    id                 integer primary key autoincrement,
    nombre             text not null,
    rubro              text not null,
    telefono           text not null,
    es_celular         integer not null default 0,
    direccion          text,
    link_maps          text,
    estado             text not null default 'pendiente',
    fecha_captura      text not null,
    variante_usada     text,
    fecha_envio        text,
    franja_horaria     text,
    clic_en_link       integer not null default 0,
    fecha_respuesta    text,
    texto_respuesta    text,
    fecha_inicio_prueba text,
    fecha_compra       text,
    fecha_recordatorio text,
    plan_cotizado      text
);

create unique index if not exists idx_contactos_telefono
    on contactos (telefono, rubro);
create index if not exists idx_contactos_estado on contactos (estado);
create index if not exists idx_contactos_rubro on contactos (rubro);
create index if not exists idx_contactos_fecha_envio on contactos (fecha_envio);

create table if not exists envios (
    id          integer primary key autoincrement,
    contacto_id integer not null,
    fecha       text not null,
    variante    text not null,
    franja      text not null,
    canal       text not null,
    modo        text not null,
    texto       text not null,
    foreign key (contacto_id) references contactos (id)
);

create index if not exists idx_envios_fecha on envios (fecha);
create index if not exists idx_envios_contacto on envios (contacto_id);

create table if not exists respuestas (
    id           integer primary key autoincrement,
    contacto_id  integer not null,
    fecha        text not null,
    texto        text not null,
    clasificacion text not null,
    foreign key (contacto_id) references contactos (id)
);

create index if not exists idx_respuestas_contacto on respuestas (contacto_id);
"""


def ahora() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def hoy() -> str:
    return datetime.now().strftime("%Y-%m-%d")


@contextmanager
def conectar():
    conexion = sqlite3.connect(config.DB_PATH)
    conexion.row_factory = sqlite3.Row
    conexion.execute("pragma foreign_keys = on")
    try:
        yield conexion
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def init() -> None:
    with conectar() as c:
        c.executescript(SCHEMA)


def agregar_contacto(
    nombre: str,
    rubro: str,
    telefono: str,
    es_celular: bool,
    direccion: str | None = None,
    link_maps: str | None = None,
) -> int | None:
    with conectar() as c:
        existente = c.execute(
            "select id from contactos where telefono = ? and rubro = ?",
            (telefono, rubro),
        ).fetchone()
        if existente:
            return None
        cur = c.execute(
            """insert into contactos
                   (nombre, rubro, telefono, es_celular, direccion, link_maps,
                    estado, fecha_captura)
               values (?, ?, ?, ?, ?, ?, 'pendiente', ?)""",
            (
                nombre.strip(),
                rubro,
                telefono,
                1 if es_celular else 0,
                direccion,
                link_maps,
                ahora(),
            ),
        )
        return int(cur.lastrowid)


def obtener(contacto_id: int) -> sqlite3.Row | None:
    with conectar() as c:
        return c.execute(
            "select * from contactos where id = ?", (contacto_id,)
        ).fetchone()


def por_telefono(telefono: str) -> sqlite3.Row | None:
    with conectar() as c:
        return c.execute(
            "select * from contactos where telefono = ? order by id desc limit 1",
            (telefono,),
        ).fetchone()


def listar(estado: str | None = None, rubro: str | None = None, limite: int = 50) -> list[sqlite3.Row]:
    condiciones = []
    valores: list = []
    if estado:
        condiciones.append("estado = ?")
        valores.append(estado)
    if rubro:
        condiciones.append("rubro = ?")
        valores.append(rubro)
    where = f"where {' and '.join(condiciones)}" if condiciones else ""
    valores.append(limite)
    with conectar() as c:
        return list(
            c.execute(
                f"select * from contactos {where} order by id desc limit ?", valores
            ).fetchall()
        )


def pendientes_para_enviar(limite: int) -> list[sqlite3.Row]:
    with conectar() as c:
        return list(
            c.execute(
                """select * from contactos
                   where estado = 'pendiente' and es_celular = 1
                   order by id limit ?""",
                (limite,),
            ).fetchall()
        )


def contar_envios_hoy() -> int:
    with conectar() as c:
        fila = c.execute(
            "select count(*) as n from envios where fecha like ? and modo = 'enviado'",
            (f"{hoy()}%",),
        ).fetchone()
    return int(fila["n"])


def margen_hoy() -> int:
    return max(0, config.LIMITE_DIARIO - contar_envios_hoy())


def marcar_enviado(contacto_id: int, variante: str, franja: str, texto: str, modo: str) -> None:
    with conectar() as c:
        c.execute(
            """update contactos
               set estado = 'enviado', variante_usada = ?, fecha_envio = ?,
                   franja_horaria = ?
               where id = ?""",
            (variante, ahora(), franja, contacto_id),
        )
        c.execute(
            """insert into envios (contacto_id, fecha, variante, franja, canal, modo, texto)
               values (?, ?, ?, ?, ?, ?, ?)""",
            (contacto_id, ahora(), variante, franja, config.ENVIADO_VIA_SEMI_AUTOMATICO, modo, texto),
        )


def registrar_envio(contacto_id: int, variante: str, franja: str, texto: str, modo: str) -> None:
    with conectar() as c:
        c.execute(
            """insert into envios (contacto_id, fecha, variante, franja, canal, modo, texto)
               values (?, ?, ?, ?, ?, ?, ?)""",
            (contacto_id, ahora(), variante, franja, config.ENVIADO_VIA_SEMI_AUTOMATICO, modo, texto),
        )


def registrar_envio_simulado(contacto_id: int, variante: str, franja: str, texto: str) -> None:
    registrar_envio(contacto_id, variante, franja, texto, "simulado")


def ya_envio(contacto_id: int, variante: str) -> bool:
    with conectar() as c:
        fila = c.execute(
            "select 1 from envios where contacto_id = ? and variante = ? limit 1",
            (contacto_id, variante),
        ).fetchone()
    return fila is not None


def cambiar_estado(contacto_id: int, nuevo: str, forzar: bool = False) -> str:
    if nuevo not in config.ESTADOS:
        raise ValueError(f"estado desconocido: {nuevo}")
    with conectar() as c:
        fila = c.execute(
            "select estado from contactos where id = ?", (contacto_id,)
        ).fetchone()
        if fila is None:
            raise ValueError(f"no existe el contacto {contacto_id}")
        actual = fila["estado"]
        if actual == nuevo:
            return nuevo
        if not forzar and not config.transicion_permitida(actual, nuevo):
            raise ValueError(
                f"transicion no permitida: {actual} -> {nuevo} (usar forzar=True)"
            )
        c.execute(
            "update contactos set estado = ? where id = ?", (nuevo, contacto_id)
        )
    return nuevo


def registrar_respuesta(contacto_id: int, texto: str, clasificacion: str) -> None:
    with conectar() as c:
        c.execute(
            """insert into respuestas (contacto_id, fecha, texto, clasificacion)
               values (?, ?, ?, ?)""",
            (contacto_id, ahora(), texto, clasificacion),
        )
        c.execute(
            "update contactos set fecha_respuesta = ?, texto_respuesta = ? where id = ?",
            (ahora(), texto, contacto_id),
        )


def marcar_registro(contacto_id: int, clave: str, fecha: str | None = None) -> None:
    columna = f"fecha_{clave}"
    with conectar() as c:
        c.execute(
            f"update contactos set {columna} = ? where id = ?",
            (fecha or ahora(), contacto_id),
        )


def marcar_clic(contacto_id: int) -> None:
    with conectar() as c:
        c.execute(
            "update contactos set clic_en_link = 1 where id = ?", (contacto_id,)
        )


def necesita_recordatorio(dias: int = 4) -> list[sqlite3.Row]:
    with conectar() as c:
        return list(
            c.execute(
                """select * from contactos
                   where estado = 'enviado'
                     and fecha_recordatorio is null
                     and fecha_envio is not null
                     and julianday('now', 'localtime') - julianday(fecha_envio) >= ?
                   order by fecha_envio""",
                (dias,),
            ).fetchall()
        )


def guardar_backup() -> str:
    destino = config.RAIZ / f"contactos.db.backup"
    shutil.copy2(config.DB_PATH, destino)
    return str(destino)


def resumen() -> dict:
    with conectar() as c:
        por_estado = {
            f["estado"]: f["n"]
            for f in c.execute(
                "select estado, count(*) as n from contactos group by estado"
            ).fetchall()
        }
        por_rubro = {
            f["rubro"]: f["n"]
            for f in c.execute(
                "select rubro, count(*) as n from contactos group by rubro"
            ).fetchall()
        }
        total = c.execute("select count(*) as n from contactos").fetchone()["n"]
        con_tel = c.execute(
            "select count(*) as n from contactos where telefono is not null"
        ).fetchone()["n"]
        celulares = c.execute(
            "select count(*) as n from contactos where es_celular = 1"
        ).fetchone()["n"]
    return {
        "total": total,
        "con_telefono": con_tel,
        "celulares": celulares,
        "por_estado": por_estado,
        "por_rubro": por_rubro,
    }
