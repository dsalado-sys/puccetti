"""Reglas de adyacencia interior (A2.2) y validador automatico.

A2.2 (vivienda):
- El acceso a la vivienda se realiza solo por el salon o vestibulo->salon.
- Habitaciones NO conectan directamente con salon ni con cocina (siempre via pasillo).
- Cocina puede integrarse en el salon (salon-cocina).
- Baños accesibles desde pasillo, no desde cocina.
- Al menos un baño no en suite exclusivo.
- Ancho minimo pasillo vivienda 0.90 m.
- Toda estancia que no sea baño/aseo necesita ventilacion natural directa.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

import networkx as nx
from shapely.geometry import Polygon
from shapely.ops import unary_union


# (a, b) -> permitido conectarse directamente?
# Categoria de cada estancia: publica / privada / servicio / circulacion.
ADYACENCIAS_PROHIBIDAS = {
    # habitaciones nunca conectadas a salon ni a cocina
    ('publica',  'privada'),
    ('privada',  'publica'),
    # cocina nunca con baño/aseo
    ('publica',  'servicio'),    # solo si la publica es cocina; matiz abajo
    ('servicio', 'publica'),
}

# Excepciones: salon SI puede conectar con cocina (salon-cocina open plan).
# Excepciones: baño SI puede tener acceso por dormitorio (en suite), si hay
# otro baño accesible desde pasillo.

@dataclass
class IncidenciaAdyacencia:
    estancia_a: str
    estancia_b: str
    motivo: str   # texto explicando que regla A2.2 se incumple


def _cat_de(nombre: str) -> str:
    if nombre.startswith('salon') or nombre == 'cocina' or nombre == 'comedor':
        return 'publica'
    if nombre.startswith('dormitorio') or nombre == 'vestidor':
        return 'privada'
    if nombre.startswith('bano') or nombre == 'aseo':
        return 'servicio'
    if nombre in ('pasillo', 'vestibulo', 'distribuidor'):
        return 'circulacion'
    return 'otra'


def grafo_adyacencias_fisicas(
    estancias: dict[str, Polygon],
    buffer_muro: float = 0.30,
    min_overlap_m: float = 0.30,
) -> nx.Graph:
    """Construye un grafo donde a-b son vecinas si los buffers de cada estancia
    se solapan en una zona lineal de al menos `min_overlap_m` metros.

    Como las estancias estan separadas por muros divisorios (~10-30 cm), no se
    tocan directamente. Bufferamos cada estancia y miramos si los buffers se
    cruzan en una banda comun. Esto modela "comparten muro divisorio".
    """
    g = nx.Graph()
    items = list(estancias.items())
    for nombre, geom in items:
        g.add_node(nombre, categoria=_cat_de(nombre), area_m2=geom.area)
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a_name, a = items[i]
            b_name, b = items[j]
            if a.is_empty or b.is_empty:
                continue
            inter = a.buffer(buffer_muro).intersection(b.buffer(buffer_muro))
            if inter.is_empty or inter.area < min_overlap_m * buffer_muro:
                continue
            g.add_edge(a_name, b_name, overlap_m2=inter.area)
    return g


def validar_a22(g: nx.Graph) -> list[IncidenciaAdyacencia]:
    """Aplica las reglas A2.2 sobre el grafo de adyacencias fisicas.

    Devuelve la lista de incumplimientos (vacia = ok).
    """
    incidencias: list[IncidenciaAdyacencia] = []

    for a, b in g.edges():
        ca = g.nodes[a]['categoria']
        cb = g.nodes[b]['categoria']

        # Salon-cocina open plan -> permitido. publica-publica.
        if ca == 'publica' and cb == 'publica':
            continue

        # Habitacion (privada) NO con salon/cocina (publica).
        if {ca, cb} == {'publica', 'privada'}:
            # Excepcion: salon-cocina junto al pasillo, no junto al dormitorio.
            # Comprobamos que no sea salon directo con dormitorio.
            if 'salon' in a or 'salon' in b or a == 'cocina' or b == 'cocina':
                incidencias.append(IncidenciaAdyacencia(
                    a, b,
                    "A2.2: habitacion no puede conectar directamente con salon/cocina; debe acceder desde pasillo"
                ))

        # Bano (servicio) NO con cocina.
        if {ca, cb} == {'publica', 'servicio'}:
            if 'cocina' in (a, b):
                incidencias.append(IncidenciaAdyacencia(
                    a, b, "A2.2: no se accede al bano desde la cocina"
                ))

    # Comprobacion adicional: todas las habitaciones deben ser alcanzables desde
    # la entrada (salon/vestibulo) via circulacion publica.
    return incidencias


def validar_conectividad(g: nx.Graph) -> list[IncidenciaAdyacencia]:
    """Toda estancia habitable debe ser alcanzable desde una circulacion."""
    incidencias = []
    if not g.nodes:
        return incidencias
    nodos_circ = [n for n, d in g.nodes(data=True) if d['categoria'] == 'circulacion']
    if not nodos_circ:
        return [IncidenciaAdyacencia('-', '-', "A2.1: no hay pasillo/vestibulo en la planta")]
    # BFS desde cualquier nodo de circulacion.
    alcanzables = set()
    for c in nodos_circ:
        alcanzables.update(nx.descendants(g, c))
        alcanzables.add(c)
    no_alcanzables = [n for n in g.nodes() if n not in alcanzables]
    for n in no_alcanzables:
        incidencias.append(IncidenciaAdyacencia(
            n, '-', f"A2.2: {n} no es alcanzable desde pasillo/vestibulo"
        ))
    return incidencias
