"""Grafo de adyacencias REQUERIDAS (no solo prohibidas) — A2.2 + criterios funcionales.

Mejora 2 del feedback: antes de colocar geometria, definimos un grafo de
relaciones obligatorias entre estancias. El distribuidor lee este grafo para
agrupar estancias adyacentes en el espacio fisico.

Distingue tres tipos de aristas:
  REQUERIDA   = debe haber adyacencia fisica (compartir muro)
  PERMITIDA   = puede existir adyacencia (no penaliza si la hay)
  PROHIBIDA   = no debe haber adyacencia (penalizacion fuerte)
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

import networkx as nx


class TipoArista(Enum):
    REQUERIDA = 'requerida'
    PERMITIDA = 'permitida'
    PROHIBIDA = 'prohibida'


# Reglas para uso vivienda (A2.2 PDF + buena practica arquitectonica).
# A2.2 textual: "El acceso a la vivienda se realiza unicamente por el salon o
# por un vestibulo de entrada que comunica directamente con el salon."
# => vestibulo->salon REQUERIDA. salon->pasillo REQUERIDA. NO vestibulo->pasillo directo.
REGLAS_VIVIENDA: list[tuple[str, str, TipoArista]] = [
    # Acceso por vestibulo -> salon (A2.2)
    ('vestibulo',    'salon',         TipoArista.REQUERIDA),
    ('vestibulo',    'salon_cocina',  TipoArista.REQUERIDA),
    # Salon junto a cocina (si separados) — open plan ya esta integrado
    ('salon',        'cocina',        TipoArista.REQUERIDA),
    # Pasillo arranca del salon/vestibulo
    ('salon',        'pasillo',       TipoArista.REQUERIDA),
    ('salon_cocina', 'pasillo',       TipoArista.REQUERIDA),
    ('vestibulo',    'pasillo',       TipoArista.PERMITIDA),  # alternativa via vestibulo
    # Dormitorios y banos cuelgan del pasillo (no del salon)
    ('pasillo',      'dormitorio_*',  TipoArista.REQUERIDA),
    ('pasillo',      'bano_*',        TipoArista.REQUERIDA),
    ('pasillo',      'aseo',          TipoArista.REQUERIDA),
    ('pasillo',      'bano',          TipoArista.REQUERIDA),

    # PROHIBIDAS
    ('salon',        'dormitorio_*',  TipoArista.PROHIBIDA),
    ('cocina',       'dormitorio_*',  TipoArista.PROHIBIDA),
    ('cocina',       'bano_*',        TipoArista.PROHIBIDA),
    ('cocina',       'aseo',          TipoArista.PROHIBIDA),
    ('cocina',       'bano',          TipoArista.PROHIBIDA),
]


def _coincide(patron: str, nombre: str) -> bool:
    if patron.endswith('*'):
        return nombre.startswith(patron[:-1])
    return patron == nombre


def construir_grafo_funcional(
    estancias_nombres: list[str],
    reglas: list[tuple[str, str, TipoArista]] | None = None,
) -> nx.Graph:
    """Construye el grafo expandiendo los patrones (dormitorio_* -> dormitorio_1, _2,...)."""
    if reglas is None:
        reglas = REGLAS_VIVIENDA
    g = nx.Graph()
    for n in estancias_nombres:
        g.add_node(n)
    for a_pat, b_pat, tipo in reglas:
        for a in estancias_nombres:
            if not _coincide(a_pat, a):
                continue
            for b in estancias_nombres:
                if a == b or not _coincide(b_pat, b):
                    continue
                # Si ya hay arista, no degradar nivel
                if g.has_edge(a, b):
                    actual = g[a][b]['tipo']
                    # Prohibida prevalece
                    if actual == TipoArista.PROHIBIDA:
                        continue
                g.add_edge(a, b, tipo=tipo)
    return g


def aristas_requeridas(g: nx.Graph) -> list[tuple[str, str]]:
    return [(a, b) for a, b, d in g.edges(data=True) if d['tipo'] == TipoArista.REQUERIDA]


def aristas_prohibidas(g: nx.Graph) -> list[tuple[str, str]]:
    return [(a, b) for a, b, d in g.edges(data=True) if d['tipo'] == TipoArista.PROHIBIDA]


def ordenar_por_topologia(
    grafo_funcional: nx.Graph,
    estancia_inicial: str = 'vestibulo',
) -> list[str]:
    """BFS desde vestibulo via aristas REQUERIDAS. Da el orden natural en que
    deberian colocarse las estancias (cerca de la entrada las primeras)."""
    if estancia_inicial not in grafo_funcional:
        # cualquier nodo como semilla
        if not grafo_funcional.nodes:
            return []
        estancia_inicial = next(iter(grafo_funcional.nodes))
    sub_req = grafo_funcional.edge_subgraph(
        (a, b) for a, b, d in grafo_funcional.edges(data=True)
        if d['tipo'] == TipoArista.REQUERIDA
    )
    if estancia_inicial not in sub_req:
        return list(grafo_funcional.nodes)
    orden = list(nx.bfs_tree(sub_req, estancia_inicial).nodes)
    # añadir nodos sueltos al final
    sueltos = [n for n in grafo_funcional.nodes if n not in orden]
    return orden + sueltos
