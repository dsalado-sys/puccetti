"""Persistencia editable de la normativa de superficies en SQLite.

Las tablas del Anexo I (valores numéricos en m²) viven en una base de datos
SQLite (``backend/data/normativa.db``) para poder editarlas desde el frontend.
La estructura/etiquetas (qué usos, categorías y tipologías existen) sigue en
``superficies.py`` como metadato; la BD solo guarda los **valores numéricos**.

Modelo: una única tabla genérica ``superficies(grupo, categoria, tipologia,
valor)`` que cubre todas las tablas del Anexo I. Las celdas no numéricas del PDF
(p. ej. "Sí" del albergue múltiple, o "—") no se almacenan: se mantienen como
default en Python y se muestran como solo-lectura.

Seed: en el primer arranque (BD vacía) se vuelca el contenido de los dicts de
``superficies.py``. ``reset_db()`` restaura esos valores de fábrica.
"""
from __future__ import annotations

import copy
import sqlite3
from pathlib import Path
from typing import Optional

from . import superficies as S

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "normativa.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Crea la tabla si no existe y la siembra desde los dicts si está vacía."""
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS superficies (
                grupo     TEXT NOT NULL,
                categoria TEXT NOT NULL,
                tipologia TEXT NOT NULL,
                valor     REAL,
                PRIMARY KEY (grupo, categoria, tipologia)
            )
            """
        )
        vacia = conn.execute("SELECT COUNT(*) AS c FROM superficies").fetchone()["c"] == 0
        if vacia:
            _sembrar(conn)


def _es_numerico(v) -> bool:
    return not isinstance(v, bool) and isinstance(v, (int, float))


def _sembrar(conn: sqlite3.Connection) -> None:
    filas: list[tuple] = []

    def add(grupo: str, categoria: str, tipologia: str, valor) -> None:
        # Solo valores numéricos; los booleanos y None quedan como default Python.
        if _es_numerico(valor):
            filas.append((grupo, categoria or "_", tipologia, float(valor)))

    for cat, tipos in S.SUPERFICIES_HOTEL.items():
        for tipo, val in tipos.items():
            add("hotel", cat, tipo, val)

    for cat, val in S.AREAS_SOCIALES_POR_UA.items():
        add("areas_sociales_hotel", cat, "area_social", val)

    for cat, tipos in S.SUPERFICIES_HOTEL_APARTAMENTO.items():
        for tipo, val in tipos.items():
            add("hotel_apartamento", cat, tipo, val)

    for cat, tipos in S.SUPERFICIES_APT_EDIFICIOS.items():
        for tipo, val in tipos.items():
            add("apt_edificios", cat, tipo, val)

    for cat, tipos in S.SUPERFICIES_APT_CONJUNTOS.items():
        for tipo, val in tipos.items():
            add("apt_conjuntos", cat, tipo, val)

    for tipo, val in S.SUPERFICIES_VIVIENDA_MAXIMAS.items():
        add("vivienda_maximas", "_", tipo, val)

    for cat, metricas in S.SUPERFICIES_VIVIENDA_ESTANCIAS.items():
        for metrica, val in metricas.items():
            add("vivienda_estancias", cat, metrica, val)

    for clave, val in S.REGLAS_VIVIENDA.items():
        add("vivienda_reglas", "_", clave, val)

    conn.executemany(
        "INSERT OR REPLACE INTO superficies "
        "(grupo, categoria, tipologia, valor) VALUES (?, ?, ?, ?)",
        filas,
    )


def _tablas_base() -> dict:
    """Estructura completa con los valores por defecto (deep copy de los dicts)."""
    return copy.deepcopy(
        {
            "hotel": S.SUPERFICIES_HOTEL,
            "hotel_apartamento": S.SUPERFICIES_HOTEL_APARTAMENTO,
            "apt_edificios": S.SUPERFICIES_APT_EDIFICIOS,
            "apt_conjuntos": S.SUPERFICIES_APT_CONJUNTOS,
            "vivienda_maximas": S.SUPERFICIES_VIVIENDA_MAXIMAS,
            "vivienda_estancias": S.SUPERFICIES_VIVIENDA_ESTANCIAS,
            "vivienda_reglas": S.REGLAS_VIVIENDA,
            "areas_sociales_hotel": S.AREAS_SOCIALES_POR_UA,
        }
    )


def _aplicar(tablas: dict, grupo: str, categoria: str, tipologia: str, valor) -> None:
    """Aplica un valor de la BD sobre la estructura base (overlay)."""
    try:
        if grupo == "areas_sociales_hotel":
            tablas["areas_sociales_hotel"][categoria] = valor
        elif grupo in ("vivienda_maximas", "vivienda_reglas"):
            tablas[grupo][tipologia] = valor
        elif grupo == "vivienda_estancias":
            tablas["vivienda_estancias"].setdefault(categoria, {})[tipologia] = valor
        elif grupo in ("hotel", "hotel_apartamento", "apt_edificios", "apt_conjuntos"):
            tablas[grupo].setdefault(categoria, {})[tipologia] = valor
    except (KeyError, TypeError):
        # Si la BD trae una clave que ya no existe en la estructura, se ignora.
        pass


def get_catalogo() -> dict:
    """Catálogo completo (usos + tablas) con los valores numéricos desde la BD."""
    init_db()
    tablas = _tablas_base()
    with _conn() as conn:
        for r in conn.execute(
            "SELECT grupo, categoria, tipologia, valor FROM superficies"
        ):
            _aplicar(tablas, r["grupo"], r["categoria"], r["tipologia"], r["valor"])
    return {"usos": S.USOS_DISPONIBLES, "tablas": tablas}


def update_valor(grupo: str, categoria: str, tipologia: str, valor: Optional[float]) -> None:
    """Inserta o actualiza un valor concreto de la tabla."""
    init_db()
    v = None if valor in ("", None) else float(valor)
    with _conn() as conn:
        conn.execute(
            "INSERT INTO superficies (grupo, categoria, tipologia, valor) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(grupo, categoria, tipologia) DO UPDATE SET valor = excluded.valor",
            (grupo, categoria or "_", tipologia, v),
        )


def reset_db() -> None:
    """Restaura todos los valores a los de fábrica (los dicts de superficies.py)."""
    with _conn() as conn:
        conn.execute("DELETE FROM superficies")
        _sembrar(conn)
