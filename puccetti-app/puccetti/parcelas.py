"""Carga de parcelas + simplificacion + clasificacion fachada/medianera (§2.1).

La clasificacion se hace por proximidad a la red de portales/vias publicas:
si un lado del poligono esta a menos de UMBRAL metros del borde exterior de la
manzana catastral, se considera fachada. El resto, medianera.
"""
from __future__ import annotations
import math, pathlib
from dataclasses import dataclass
from typing import Literal

import geopandas as gpd
from shapely.geometry import Polygon, LineString, MultiPolygon, Point
from shapely.ops import unary_union

ROOT = pathlib.Path(__file__).resolve().parents[1]
GPKG_PATH = ROOT / "data" / "parcelas_sevilla.gpkg"

LadoTipo = Literal["fachada", "medianera"]


@dataclass
class LadoParcela:
    p1: tuple[float, float]
    p2: tuple[float, float]
    tipo: LadoTipo
    longitud_m: float
    azimut: float   # grados desde norte, 0..360


def cargar_parcelas() -> gpd.GeoDataFrame:
    """Las 10 parcelas de muestra."""
    if not GPKG_PATH.exists():
        raise FileNotFoundError(
            f"{GPKG_PATH} no existe. Ejecuta primero: python scripts/fetch_parcelas.py"
        )
    return gpd.read_file(GPKG_PATH, layer='muestra')


def cargar_contexto() -> gpd.GeoDataFrame:
    """Todas las parcelas del BBOX (incluidas las 10 de muestra). Sirve para
    clasificar fachadas/medianeras correctamente: necesitamos saber donde estan
    las parcelas COLINDANTES, no solo las 10 que vamos a analizar."""
    try:
        return gpd.read_file(GPKG_PATH, layer='contexto')
    except Exception:
        return cargar_parcelas()


def simplificar(geom: Polygon, tolerancia: float = 0.20) -> Polygon:
    """§2.1 — Douglas-Peucker con tolerancia configurable (default 20 cm)."""
    s = geom.simplify(tolerancia, preserve_topology=True)
    if isinstance(s, MultiPolygon):
        s = max(s.geoms, key=lambda g: g.area)
    return s


def _azimut(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Azimut desde norte (CRS metrico) en grados, lado p1->p2."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    ang = (math.degrees(math.atan2(dx, dy))) % 360  # atan2(dx,dy) = norte=0, este=90
    return ang


def _orientacion_cardinal(az: float) -> str:
    """Convierte azimut a N/NE/E/SE/S/SW/W/NW (orientacion de la fachada,
    perpendicular al lado)."""
    # azimut del normal exterior = azimut del lado + 90 (depende de winding).
    # Aqui devolvemos la orientacion del lado mismo; la app puede deducir el normal.
    sectores = ['N','NE','E','SE','S','SO','O','NO']
    idx = int(((az + 12.5) % 360) // 45)
    return sectores[idx]


def clasificar_lados(
    parcela: Polygon,
    parcelas_vecinas: gpd.GeoDataFrame | None = None,
    dist_probe: float = 1.0,
    **_legacy,
) -> list[LadoParcela]:
    """Devuelve cada lado del poligono clasificado como 'fachada' o 'medianera'.

    Heuristica: lanzamos un sondeo perpendicular hacia fuera del punto medio
    del lado (a `dist_probe` metros). Si ese punto cae dentro de OTRA parcela
    catastral, el lado es medianera; si no (cayo a la calle / espacio publico),
    es fachada. Funciona sobre BBOX completo del INSPIRE WFS porque todas las
    parcelas colindantes estan presentes.
    """
    coords = list(parcela.exterior.coords)[:-1]
    lados = []

    if parcelas_vecinas is None or len(parcelas_vecinas) == 0:
        union_vecinas = None
    else:
        mask = parcelas_vecinas.geometry.apply(lambda g: not g.equals(parcela))
        otras = parcelas_vecinas[mask]
        union_vecinas = unary_union(list(otras.geometry)) if len(otras) else None

    for i, p1 in enumerate(coords):
        p2 = coords[(i + 1) % len(coords)]
        seg = LineString([p1, p2])
        long_m = seg.length
        if long_m < 0.10:
            continue
        # punto medio + normal exterior (probamos ambos signos y elegimos el
        # que cae FUERA de la parcela)
        mx = (p1[0] + p2[0]) / 2.0
        my = (p1[1] + p2[1]) / 2.0
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        L = math.hypot(dx, dy)
        nxv = dy / L
        nyv = -dx / L
        probe = Point(mx + nxv * dist_probe, my + nyv * dist_probe)
        if probe.within(parcela):
            probe = Point(mx - nxv * dist_probe, my - nyv * dist_probe)

        if union_vecinas is not None and probe.within(union_vecinas):
            tipo: LadoTipo = "medianera"
        else:
            tipo = "fachada"
        lados.append(LadoParcela(
            p1=p1, p2=p2, tipo=tipo,
            longitud_m=long_m, azimut=_azimut(p1, p2),
        ))
    return lados


def resumen_lados(lados: list[LadoParcela]) -> dict:
    fach = [l for l in lados if l.tipo == "fachada"]
    med  = [l for l in lados if l.tipo == "medianera"]
    return {
        "n_fachadas": len(fach),
        "n_medianeras": len(med),
        "long_fachada_total": sum(l.longitud_m for l in fach),
        "long_medianera_total": sum(l.longitud_m for l in med),
        "orientaciones_fachada": [
            _orientacion_cardinal(l.azimut) for l in fach
        ],
    }
