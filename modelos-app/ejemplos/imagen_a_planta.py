"""Extrae habitaciones (EstanciaPoly) de una imagen raster de un plano.

Pipeline de vision:
  1. Cargar y reducir la imagen (acelera todo).
  2. Cuantizar a colores dominantes (PIL median-cut).
  3. Descartar fondo (blanco) y texto/lineas/muro (muy oscuro).
  4. Por cada color dominante restante: mascara -> componentes conexos
     (scipy.ndimage.label) -> regiones con area suficiente.
  5. Vectorizar cada region a poligono (run-length por filas + shapely union)
     y simplificar.
  6. Normalizar al bbox global -> coords viewBox 0..100.
  7. Clasificar la categoria por cercania a la paleta Puccetti.
  8. Nombrar por categoria + tamaño y repartir el area total proporcional.

Funciona con los planos de Puccetti (colores conocidos) y, en general, con
cualquier plano de regiones de color solido.
"""
from __future__ import annotations
import math
from collections import defaultdict

import numpy as np
from PIL import Image
from shapely.geometry import box, MultiPolygon, Polygon
from shapely.ops import unary_union
from shapely.affinity import scale, translate as shp_translate

from .planta_demo import EstanciaPoly


# Paleta de referencia Puccetti (rgb) -> categoria. Para clasificar el color
# detectado por cercania. Si no encaja, se usa categoria 'otra'.
PALETA = {
    'publica':     [(244, 198, 107), (232, 168, 87)],
    'privada':     [(157, 189, 217), (127, 165, 199)],
    'servicio':    [(168, 213, 186)],
    'circulacion': [(217, 217, 217)],
}

# Nombres por categoria, ordenados de mayor a menor superficie.
NOMBRES = {
    'publica':     ['salon', 'cocina', 'comedor'],
    'privada':     ['dormitorio_1', 'dormitorio_2', 'dormitorio_3', 'dormitorio_4'],
    'servicio':    ['bano', 'aseo', 'despensa'],
    'circulacion': ['pasillo', 'vestibulo', 'distribuidor'],
    'otra':        ['zona_1', 'zona_2', 'zona_3'],
}


def _clasificar_color(rgb: tuple[int, int, int]) -> tuple[str, float]:
    """Devuelve (categoria, distancia) por color mas cercano de la paleta."""
    mejor_cat, mejor_d = 'otra', 1e9
    for cat, colores in PALETA.items():
        for c in colores:
            d = sum((a - b) ** 2 for a, b in zip(rgb, c)) ** 0.5
            if d < mejor_d:
                mejor_d, mejor_cat = d, cat
    return mejor_cat, mejor_d


def _luminancia(rgb) -> float:
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def _mascara_a_poligono(mask: np.ndarray) -> Polygon | None:
    """Vectoriza una mascara booleana a poligono via run-length por filas."""
    boxes = []
    H, W = mask.shape
    for y in range(H):
        row = mask[y]
        x = 0
        while x < W:
            if row[x]:
                x0 = x
                while x < W and row[x]:
                    x += 1
                boxes.append(box(x0, y, x, y + 1))
            else:
                x += 1
    if not boxes:
        return None
    poly = unary_union(boxes)
    if isinstance(poly, MultiPolygon):
        poly = max(poly.geoms, key=lambda g: g.area)
    return poly


def extraer_estancias(
    ruta_imagen: str,
    area_util_total_m2: float = 100.0,
    ancho_proc: int = 170,
    min_area_frac: float = 0.004,
    n_colores: int = 14,
) -> list[EstanciaPoly]:
    """Devuelve la lista de EstanciaPoly detectadas en la imagen."""
    img = Image.open(ruta_imagen).convert('RGB')
    # reducir manteniendo aspecto
    w0, h0 = img.size
    escala = ancho_proc / w0
    img = img.resize((ancho_proc, max(1, int(h0 * escala))), Image.NEAREST)

    # cuantizar a colores dominantes
    q = img.quantize(colors=n_colores, method=Image.MEDIANCUT).convert('RGB')
    arr = np.array(q)
    H, W, _ = arr.shape
    total_px = H * W

    from scipy import ndimage

    # colores presentes y su frecuencia
    flat = arr.reshape(-1, 3)
    colores, counts = np.unique(flat, axis=0, return_counts=True)

    regiones = []   # (categoria, color_hex, poligono_px, area_px, dist)
    for color, count in zip(colores, counts):
        rgb = tuple(int(c) for c in color)
        lum = _luminancia(rgb)
        # descartar fondo (muy claro) y texto/muro/lineas (muy oscuro)
        if lum > 235 or lum < 65:
            continue
        if count < total_px * min_area_frac:
            continue
        # mascara de este color (tolerancia pequeña por la cuantizacion)
        mask = np.all(np.abs(arr.astype(int) - np.array(rgb)) <= 8, axis=2)
        # componentes conexos
        lbl, n = ndimage.label(mask)
        for k in range(1, n + 1):
            comp = lbl == k
            area_px = int(comp.sum())
            if area_px < total_px * min_area_frac:
                continue
            poly = _mascara_a_poligono(comp)
            if poly is None or poly.area < 4:
                continue
            poly = poly.simplify(1.2, preserve_topology=True)
            if poly.is_empty:
                continue
            cat, dist = _clasificar_color(rgb)
            regiones.append({
                'categoria': cat,
                'color': '#{:02x}{:02x}{:02x}'.format(*rgb),
                'poly': poly,
                'area_px': area_px,
                'dist': dist,
            })

    if not regiones:
        return []

    # bbox global (huella de la planta) para normalizar a viewBox 0..100
    union_total = unary_union([r['poly'] for r in regiones])
    gx0, gy0, gx1, gy1 = union_total.bounds
    gw, gh = (gx1 - gx0) or 1, (gy1 - gy0) or 1
    # margen 5% dentro de 0..100
    def normaliza(p: Polygon) -> Polygon:
        p = shp_translate(p, xoff=-gx0, yoff=-gy0)
        p = scale(p, xfact=90 / gw, yfact=90 / gh, origin=(0, 0))
        return shp_translate(p, xoff=5, yoff=5)

    # area total de pixeles habitables -> reparto proporcional del area_util
    total_area_px = sum(r['area_px'] for r in regiones)

    # nombrar por categoria + tamaño
    por_cat = defaultdict(list)
    for r in regiones:
        por_cat[r['categoria']].append(r)
    for cat, lst in por_cat.items():
        lst.sort(key=lambda r: r['area_px'], reverse=True)

    estancias = []
    for cat, lst in por_cat.items():
        nombres = NOMBRES.get(cat, NOMBRES['otra'])
        for i, r in enumerate(lst):
            nombre = nombres[i] if i < len(nombres) else f'{cat}_{i+1}'
            pn = normaliza(r['poly'])
            if pn.is_empty:
                continue
            # exterior simplificado a lista de puntos
            ext = list(pn.exterior.coords)[:-1]
            pts = [(round(x, 1), round(y, 1)) for x, y in ext]
            area_m2 = area_util_total_m2 * r['area_px'] / total_area_px
            estancias.append(EstanciaPoly(
                nombre=nombre, categoria=cat, color=r['color'],
                puntos=pts, area_m2=round(area_m2, 1),
            ))
    return estancias
