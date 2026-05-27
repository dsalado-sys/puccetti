"""Estructuras de planta + ejemplo hardcoded de respaldo.

EstanciaPoly es la estructura comun que consumen los renders 2D/3D: una
habitacion definida por su POLIGONO (lista de puntos en viewBox 0..100), su
categoria, color y area. Tanto el ejemplo hardcoded como el extractor de
imagenes (imagen_a_planta.py) producen EstanciaPoly.
"""
from __future__ import annotations
from dataclasses import dataclass, field


# ---- ejemplo rectangular de respaldo (cuando no se sube imagen) ----
@dataclass
class Estancia:
    nombre: str
    x: float
    y: float
    w: float
    h: float
    color: str
    area_m2: float


PARCELA_VIEWBOX = (5, 5, 90, 90)

PLANTA_EJEMPLO = [
    Estancia('Vestibulo',    5,  5, 18, 35, '#D9D9D9', 8.0),
    Estancia('Salon',       23,  5, 40, 35, '#F4C66B', 24.0),
    Estancia('Cocina',      63,  5, 32, 35, '#E8A857', 9.0),
    Estancia('Pasillo',      5, 40, 90, 12, '#D9D9D9', 6.5),
    Estancia('Dormitorio 1', 5, 52, 38, 43, '#9DBDD9', 16.0),
    Estancia('Dormitorio 2',43, 52, 30, 43, '#7FA5C7', 12.0),
    Estancia('Bano',        73, 52, 22, 43, '#A8D5BA', 5.0),
]


# ---- estructura poligonal comun ----
@dataclass
class EstanciaPoly:
    nombre: str
    categoria: str            # publica | privada | servicio | circulacion | otra
    color: str                # hex "#rrggbb"
    puntos: list             # [(x, y), ...] en viewBox 0..100
    area_m2: float = 0.0

    def bbox(self) -> tuple[float, float, float, float]:
        xs = [p[0] for p in self.puntos]
        ys = [p[1] for p in self.puntos]
        return min(xs), min(ys), max(xs), max(ys)

    def centroide(self) -> tuple[float, float]:
        n = len(self.puntos)
        return (sum(p[0] for p in self.puntos) / n,
                sum(p[1] for p in self.puntos) / n)


def _categoria_de_nombre(nombre: str) -> str:
    n = nombre.lower()
    if n.startswith('salon') or n.startswith('cocina') or n.startswith('comedor'):
        return 'publica'
    if n.startswith('dormitorio') or n.startswith('vestidor'):
        return 'privada'
    if n.startswith('bano') or n.startswith('aseo') or n.startswith('despensa'):
        return 'servicio'
    if n.startswith('pasillo') or n.startswith('vestibulo') or n.startswith('distribuidor'):
        return 'circulacion'
    return 'otra'


def ejemplo_como_poligonos() -> list[EstanciaPoly]:
    """Convierte el PLANTA_EJEMPLO (rectangulos) a EstanciaPoly (4 puntos)."""
    out = []
    for e in PLANTA_EJEMPLO:
        pts = [(e.x, e.y), (e.x + e.w, e.y),
               (e.x + e.w, e.y + e.h), (e.x, e.y + e.h)]
        out.append(EstanciaPoly(
            nombre=e.nombre, categoria=_categoria_de_nombre(e.nombre),
            color=e.color, puntos=pts, area_m2=e.area_m2,
        ))
    return out
