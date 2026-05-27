"""Squarified Treemap: subdivision rectangular manteniendo aspect ratio ~ 1.

Mejora 1 del feedback arquitectonico: en vez de cortar tiras 1D que generan
habitaciones tipo tubo (0.5x15 m), cada subdivision elige el eje perpendicular
al lado largo del contenedor, manteniendo proporciones cuadradas.

Uso la libreria `squarify` (estandar de facto, M.Bruls et al. 2000) que devuelve
los rectangulos en coordenadas normalizadas, y los mapeamos al bbox del
contenedor real. Luego intersectamos con el poligono base para respetar la
forma irregular.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

import squarify
from shapely.geometry import Polygon, box


@dataclass
class TreemapItem:
    """Item de entrada para el squarified treemap."""
    nombre: str
    area: float          # m2 objetivo (>= minimo)
    payload: dict = None # cualquier metadata adicional (categoria, etc.)


def subdividir_squarified(
    contenedor: Polygon,
    items: list[TreemapItem],
    eje_largo_horizontal: bool = True,
) -> dict[str, Polygon]:
    """Sustituye el corte 1D del distribuidor antiguo.

    contenedor: poligono donde meter las habitaciones (puede ser irregular).
    items:      lista ordenada (de mayor a menor area suele ir bien).
    Devuelve:   dict nombre -> Polygon (ya intersectado con contenedor).

    Estrategia:
    1. Tomamos el bounding box axis-aligned del contenedor.
    2. squarify normaliza las areas al area del bbox y subdivide manteniendo
       aspect ratio cercano a 1.
    3. Convertimos cada rect normalizado a un Polygon en coordenadas reales.
    4. Lo intersectamos con el contenedor real (recorta la forma irregular).
    """
    if not items:
        return {}
    minx, miny, maxx, maxy = contenedor.bounds
    W, H = maxx - minx, maxy - miny
    bbox_area = W * H
    if bbox_area <= 0:
        return {}

    # squarify pide areas normalizadas al area del contenedor.
    target_areas = [it.area for it in items]
    total_target = sum(target_areas)
    if total_target <= 0:
        return {}
    factor = bbox_area / total_target
    sizes = [a * factor for a in target_areas]
    # squarify normalize a [W,H] espera 'normed' = lista que sume W*H
    sizes = squarify.normalize_sizes(sizes, W, H)
    rects = squarify.squarify(sizes, minx, miny, W, H)

    out: dict[str, Polygon] = {}
    for it, r in zip(items, rects):
        rect = box(r['x'], r['y'], r['x'] + r['dx'], r['y'] + r['dy'])
        # Intersectamos con el contenedor real para respetar la forma irregular
        clipped = rect.intersection(contenedor)
        if not clipped.is_empty:
            out[it.nombre] = clipped
    return out


def shelf_packing(
    contenedor: Polygon,
    items: list[TreemapItem],
    altura_total: float | None = None,
    ancho_min: float = 2.0,
    ancho_max: float = 5.5,
) -> dict[str, Polygon]:
    """Coloca items en UNA sola fila lado a lado. Cada item ocupa toda la
    altura disponible y un ancho proporcional a su area objetivo.

    Esto garantiza que cada item comparte borde inferior (o superior) con el
    borde correspondiente del contenedor — perfecto para dorms/banos que
    deben tocar el pasillo. Sacrifica algo de aspect ratio para asegurar el
    acceso, que es una restriccion DURA del A2.2.
    """
    if not items or contenedor.is_empty:
        return {}
    minx, miny, maxx, maxy = contenedor.bounds
    H = altura_total if altura_total is not None else (maxy - miny)
    if H <= 0:
        return {}
    # Anchos por area objetivo, con clamp
    anchos = [max(ancho_min, min(ancho_max, it.area / H)) for it in items]
    W = maxx - minx
    total = sum(anchos)
    if total > W and total > 0:
        # Escalar para que quepa
        factor = W / total
        anchos = [a * factor for a in anchos]
    out: dict[str, Polygon] = {}
    x = minx
    for it, w in zip(items, anchos):
        r = box(x, miny, x + w, maxy).intersection(contenedor)
        if not r.is_empty:
            out[it.nombre] = r
        x += w
    return out


def aspect_ratio(geom: Polygon) -> float:
    """Aspect ratio del minimum_rotated_rectangle: lado_largo / lado_corto."""
    if geom.is_empty:
        return float('inf')
    mrr = geom.minimum_rotated_rectangle
    coords = list(mrr.exterior.coords)[:-1]
    import math
    edges = [math.dist(coords[i], coords[(i + 1) % 4]) for i in range(4)]
    largos = sorted(edges, reverse=True)
    if largos[2] < 1e-6:
        return float('inf')
    return largos[0] / largos[2]   # lado_largo / lado_corto
