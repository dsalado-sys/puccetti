"""Fitness function multicriterio (Mejora 4 del feedback arquitectonico).

Cada candidato de distribucion se evalua en 6 criterios. Score = suma ponderada.
Mejor score = mejor distribucion. El distribuidor genera N candidatos con
distintos seeds y devuelve el mejor.
"""
from __future__ import annotations
from dataclasses import dataclass, field

import networkx as nx
from shapely.geometry import Polygon, LineString

from .grafo_funcional import (
    aristas_requeridas, aristas_prohibidas, construir_grafo_funcional,
)
from .adyacencias import grafo_adyacencias_fisicas, _cat_de
from .treemap import aspect_ratio
from .parcelas import LadoParcela


@dataclass
class Score:
    total: float
    detalle: dict[str, float] = field(default_factory=dict)
    incidencias: list[str] = field(default_factory=list)


# Pesos de cada criterio (relativos)
PESOS = {
    'minimos':       40,   # cumple area_min Anexo I.5
    'aspect_ratio':  20,   # habitaciones no-tubo (AR < 3:1)
    'fachada':       15,   # habitaciones principales con luz exterior
    'requeridas':    15,   # adyacencias REQUERIDAS presentes
    'prohibidas':    25,   # adyacencias PROHIBIDAS ausentes
    'utilizacion':    5,   # aprovechamiento del espacio
}


def _toca_fachada(geom: Polygon, lados: list[LadoParcela], tol: float = 0.5) -> bool:
    if geom.is_empty:
        return False
    geom_buf = geom.buffer(tol)
    for l in lados:
        if l.tipo != 'fachada':
            continue
        if geom_buf.intersects(LineString([l.p1, l.p2])):
            return True
    return False


def evaluar(
    estancias: list,          # list[EstanciaColocada]
    interior: Polygon,
    lados: list[LadoParcela],
) -> Score:
    """Evalua un candidato. estancias = lista de EstanciaColocada del distributor."""
    detalle: dict[str, float] = {}
    incidencias: list[str] = []

    if not estancias:
        return Score(0.0, {'sin_estancias': 0.0})

    # ---- 1) Cumplimiento de minimos (Anexo I.5) ----
    cumplen = sum(1 for e in estancias if e.area_real_m2 + 1e-3 >= e.area_min_m2)
    pct_cumplen = cumplen / len(estancias)
    detalle['minimos'] = pct_cumplen
    for e in estancias:
        if e.area_real_m2 + 1e-3 < e.area_min_m2:
            incidencias.append(
                f"{e.nombre} {e.area_real_m2:.1f} < min {e.area_min_m2:.1f}"
            )

    # ---- 2) Aspect Ratio (Mejora 1) ----
    habs = [e for e in estancias
            if e.categoria in ('publica', 'privada', 'servicio') and not e.geometry.is_empty]
    if habs:
        ars = [aspect_ratio(e.geometry) for e in habs]
        # Score: 1 si AR < 1.8 (cuadrado), 0 si > 4 (tubo)
        bueno = sum(1 for a in ars if a < 1.8)
        regular = sum(1 for a in ars if 1.8 <= a < 3.0)
        malo = sum(1 for a in ars if a >= 3.0)
        score_ar = (bueno + regular * 0.5) / len(ars)
        detalle['aspect_ratio'] = score_ar
        for e, a in zip(habs, ars):
            if a >= 3.0:
                incidencias.append(f"{e.nombre} AR={a:.1f} (forma tubo)")
    else:
        detalle['aspect_ratio'] = 0.0

    # ---- 3) Fachadas — habitaciones ciegas (Mejora 3) ----
    # Salon, cocina, dormitorios DEBEN tocar fachada (luz natural).
    # Baños/aseos PUEDEN dar a patio o ser ciegos si hay ventilacion mecanica.
    principales = [e for e in estancias
                   if e.categoria in ('publica', 'privada')
                   and not e.geometry.is_empty]
    if principales:
        con_luz = sum(1 for e in principales if _toca_fachada(e.geometry, lados))
        score_fach = con_luz / len(principales)
        detalle['fachada'] = score_fach
        for e in principales:
            if not _toca_fachada(e.geometry, lados):
                incidencias.append(f"{e.nombre} sin acceso a fachada (habitacion ciega)")
    else:
        detalle['fachada'] = 1.0

    # ---- 4) Adyacencias REQUERIDAS y 5) PROHIBIDAS ----
    geom_map = {e.nombre: e.geometry for e in estancias if not e.geometry.is_empty}
    g_fis = grafo_adyacencias_fisicas(geom_map, buffer_muro=0.35, min_overlap_m=0.40)
    g_fun = construir_grafo_funcional(list(geom_map.keys()))

    req = aristas_requeridas(g_fun)
    proh = aristas_prohibidas(g_fun)

    if req:
        cumplidas = sum(1 for a, b in req if g_fis.has_edge(a, b))
        score_req = cumplidas / len(req)
        detalle['requeridas'] = score_req
        for a, b in req:
            if not g_fis.has_edge(a, b):
                incidencias.append(f"falta adyacencia requerida: {a}<->{b}")
    else:
        detalle['requeridas'] = 1.0

    if proh:
        violadas = sum(1 for a, b in proh if g_fis.has_edge(a, b))
        score_proh = 1 - (violadas / len(proh))
        detalle['prohibidas'] = score_proh
        for a, b in proh:
            if g_fis.has_edge(a, b):
                incidencias.append(f"adyacencia prohibida: {a}<->{b}")
    else:
        detalle['prohibidas'] = 1.0

    # ---- 6) Utilizacion del espacio ----
    util_areas = sum(e.area_real_m2 for e in estancias
                     if e.categoria in ('publica', 'privada', 'servicio'))
    if not interior.is_empty and interior.area > 0:
        detalle['utilizacion'] = min(1.0, util_areas / (interior.area * 0.70))
    else:
        detalle['utilizacion'] = 0.0

    # ---- Score total ponderado ----
    total = sum(PESOS[k] * detalle.get(k, 0) for k in PESOS)
    total_max = sum(PESOS.values())
    return Score(
        total=round(100 * total / total_max, 1),  # escala 0-100
        detalle={k: round(v, 3) for k, v in detalle.items()},
        incidencias=incidencias,
    )
