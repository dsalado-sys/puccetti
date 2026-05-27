"""Salida del edificio plurifamiliar (§2.5/§2.7): estructura JSON + tablas de
superficie por planta que distinguen Superficie Construida (con muros) y
Superficie Util (interior libre)."""
from __future__ import annotations
from typing import Any

import pandas as pd
from shapely.geometry import Polygon

from .config import Parametros
from .macro_layout import EdificioPlurifamiliar, PlantaPlurifamiliar, Unidad, Nucleo


def _ring(geom: Polygon, tol: float = 0.03) -> list[list[float]]:
    """Anillo exterior de un poligono como lista [[x,y],...] redondeada (cm).
    Simplifica a `tol` (3 cm) para no arrastrar la microgeometria catastral."""
    if geom is None or geom.is_empty:
        return []
    g = geom.simplify(tol, preserve_topology=True)
    if g.is_empty or not hasattr(g, "exterior"):
        g = geom
    return [[round(x, 2), round(y, 2)] for x, y in g.exterior.coords]


def _nucleo_dict(nuc: Nucleo | None) -> dict[str, Any] | None:
    if nuc is None:
        return None
    return {
        "poligono": _ring(nuc.geometry),
        "escalera": _ring(nuc.escalera),
        "ascensor": _ring(nuc.ascensor),
        "vestibulo": _ring(nuc.vestibulo),
        "area_m2": round(nuc.area_m2, 2),
        "circulo_libre": {
            "centro": [round(nuc.circulo_centro[0], 2), round(nuc.circulo_centro[1], 2)],
            "radio_m": round(nuc.circulo_radio, 2),
            "diametro_m": round(nuc.circulo_radio * 2, 2),
            "cumple": nuc.circulo_ok,
        },
    }


def _unidad_dict(u: Unidad) -> dict[str, Any]:
    return {
        "id": u.id,
        "tipo": u.tipo,
        "n_dormitorios": u.n_dorms,
        "poligono_util": _ring(u.geometry),
        "poligono_construido": _ring(u.geometry_construida),
        "area_util_m2": u.area_util_m2,
        "area_construida_m2": u.area_construida_m2,
        "area_min_m2": u.area_min_m2,
        "acceso_pasillo": u.acceso_pasillo,
        "borde_pasillo_m": u.borde_pasillo_m,
        "ventilacion": {
            "tipo": u.ventilacion_tipo,
            "borde_m": u.borde_ventilacion_m,
            "hueco_requerido_m2": u.hueco_req_m2,
            "hueco_disponible_m2": u.hueco_disp_m2,
            "cumple": u.ventila_ok,
        },
        "cumple_minimos": u.cumple_min,
        "incidencias": u.incidencias,
    }


def _planta_dict(pl: PlantaPlurifamiliar) -> dict[str, Any]:
    return {
        "n": pl.n,
        "nombre": "PB" if pl.n == 0 else f"P{pl.n}",
        "tipologia": pl.tipologia,
        "edges": pl.edges,
        "footprint": _ring(pl.footprint),
        "nucleo": _nucleo_dict(pl.nucleo),
        "pasillos": [
            {"poligono": _ring(p.geometry), "ancho_m": p.ancho_m,
             "area_m2": round(p.area_m2, 2)}
            for p in pl.pasillos
        ],
        "patios": [
            {"poligono": _ring(p.geometry), "area_m2": round(p.area_m2, 2),
             "luz_recta_m": round(p.luz_recta_m, 2)}
            for p in pl.patios
        ],
        "unidades": [_unidad_dict(u) for u in pl.unidades],
        "superficies": {
            "construida_m2": pl.construida_m2,
            "util_viviendas_m2": pl.util_unidades_m2,
            "circulacion_comun_m2": pl.circulacion_m2,
            "muros_m2": pl.muros_m2,
            "patios_m2": pl.patios_m2,
            "eficiencia_util_pct": round(100 * pl.util_unidades_m2 / pl.construida_m2, 1)
                                   if pl.construida_m2 else 0.0,
        },
        "n_viviendas": len(pl.unidades),
        "score": pl.score,
        "incidencias": pl.incidencias,
    }


def edificio_a_dict(edif: EdificioPlurifamiliar, params: Parametros) -> dict[str, Any]:
    """Estructura JSON completa del edificio (§2.5 — resultado esperado)."""
    plantas = [_planta_dict(p) for p in edif.plantas]
    construida_total = sum(p["superficies"]["construida_m2"] for p in plantas)
    util_total = sum(p["superficies"]["util_viviendas_m2"] for p in plantas)
    return {
        "proyecto": {
            "uso": params.programa.uso,
            "n_dormitorios": params.programa.n_dormitorios,
            "n_viviendas_por_planta": params.programa.n_viviendas_por_planta,
            "n_plantas": len(edif.plantas),
        },
        "parametros": params.model_dump(),
        "parcela": {
            "poligono": _ring(edif.parcela),
            "area_m2": round(edif.parcela.area, 2),
        },
        "edificabilidad": {
            "maxima_m2": round(edif.edificabilidad_max, 2),
            "consumida_m2": round(edif.edificabilidad_consumida, 2),
            "consumida_pct": round(100 * edif.edificabilidad_consumida / edif.edificabilidad_max, 1)
                             if edif.edificabilidad_max else 0.0,
        },
        "plantas": plantas,
        "totales": {
            "n_viviendas": edif.n_viviendas_total,
            "construida_total_m2": round(construida_total, 2),
            "util_total_m2": round(util_total, 2),
            "incidencias": sum(len(p["incidencias"]) for p in plantas),
        },
    }


def tabla_superficies_por_planta(edif: EdificioPlurifamiliar) -> pd.DataFrame:
    """Cuadro de superficies por planta (construida vs util + desglose)."""
    rows = []
    for p in edif.plantas:
        rows.append({
            "planta": "PB" if p.n == 0 else f"P{p.n}",
            "viviendas": len(p.unidades),
            "construida_m2": p.construida_m2,
            "util_viviendas_m2": p.util_unidades_m2,
            "circulacion_m2": p.circulacion_m2,
            "patios_m2": p.patios_m2,
            "muros_m2": p.muros_m2,
            "eficiencia_pct": round(100 * p.util_unidades_m2 / p.construida_m2, 1)
                              if p.construida_m2 else 0.0,
        })
    return pd.DataFrame(rows)


def tabla_unidades(edif: EdificioPlurifamiliar) -> pd.DataFrame:
    """Una fila por vivienda (todas las plantas)."""
    rows = []
    for p in edif.plantas:
        for u in p.unidades:
            rows.append({
                "planta": "PB" if p.n == 0 else f"P{p.n}",
                "vivienda": u.id,
                "dorms": u.n_dorms,
                "util_m2": u.area_util_m2,
                "min_m2": u.area_min_m2,
                "cumple_min": u.cumple_min,
                "ventilacion": u.ventilacion_tipo,
                "ventila_ok": u.ventila_ok,
                "acceso": u.acceso_pasillo,
            })
    return pd.DataFrame(rows)
