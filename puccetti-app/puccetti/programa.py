"""Programa arquitectonico — Anexo I.5 del PDF (vivienda, Decreto Junta Andalucia).

Devuelve la lista de estancias objetivo dado: numero de dormitorios, superficie
util disponible, y si la cocina va integrada (open plan) o independiente.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

Categoria = Literal["publica", "privada", "servicio", "circulacion"]


@dataclass(frozen=True)
class Estancia:
    nombre: str
    categoria: Categoria
    area_min_m2: float       # del Anexo I.5
    area_target_m2: float    # nuestro objetivo (>= minimo)

    def __repr__(self) -> str:
        return f"{self.nombre}({self.categoria},{self.area_target_m2:.1f}m2)"


# Anexo I.5 — superficies minimas vivienda VPO Junta de Andalucia.
MIN_DORM_INDIVIDUAL = 8.0      # Anexo I.5: "Dormitorio minimo 8 m2"
MIN_DORM_DOBLE      = 12.0     # Anexo I.5: "Al menos uno de los dormitorios >=12 m2"
MIN_COCINA          = 7.0      # "Cocina independiente 7 m2 minimo"
MIN_BANO            = 3.0      # baño completo
MIN_ASEO            = 1.5      # aseo
# Salon segun n_dormitorios:
SALON_MIN = {1: 14, 2: 16, 3: 18, 4: 20, 5: 24}
SALON_MAS_COCINA_MIN = {1: 20, 2: 20, 3: 24, 4: 24, 5: 28}

# Superficie util maxima de referencia (VPO):
UTIL_MAX = {0: 35, 1: 60, 2: 70, 3: 90, 4: 110, 5: 130, 6: 150}


def programa_vivienda(
    n_dorms: int,
    util_disponible: float,
    salon_cocina_open: bool = False,
) -> list[Estancia]:
    """§2.5 + Anexo I.5 — devuelve la lista de estancias para una vivienda.

    n_dorms = 0 -> estudio.
    """
    if n_dorms == 0:
        # Estudio: salón-cocina + dormitorio + baño. Minimo 25 m2 util (Anexo I.5).
        return [
            Estancia('salon_cocina', 'publica', 20.0, max(20.0, util_disponible*0.55)),
            Estancia('dormitorio',   'privada', MIN_DORM_DOBLE, max(MIN_DORM_DOBLE, util_disponible*0.30)),
            Estancia('bano',         'servicio', MIN_BANO, MIN_BANO + 1.0),
        ]

    estancias: list[Estancia] = []

    # Salon (+ cocina si open) o salon + cocina separados.
    salon_min = SALON_MIN.get(n_dorms, 24)
    cocina_min = MIN_COCINA
    if salon_cocina_open:
        target = max(SALON_MAS_COCINA_MIN.get(n_dorms, 28), util_disponible * 0.30)
        estancias.append(Estancia('salon_cocina', 'publica', salon_min + cocina_min, target))
    else:
        estancias.append(Estancia('salon', 'publica', salon_min, salon_min + 2.0))
        estancias.append(Estancia('cocina','publica', cocina_min, cocina_min + 1.0))

    # Dormitorios: 1º principal (>=12), resto >=8.
    for i in range(n_dorms):
        if i == 0:
            estancias.append(Estancia(f'dormitorio_1', 'privada', MIN_DORM_DOBLE, MIN_DORM_DOBLE + 1.0))
        else:
            estancias.append(Estancia(f'dormitorio_{i+1}', 'privada', MIN_DORM_INDIVIDUAL, MIN_DORM_INDIVIDUAL + 2.0))

    # Banos: > 70 m2 util obligatorio 2; aqui escalamos con n_dorms tambien.
    if util_disponible > 70 or n_dorms >= 3:
        estancias.append(Estancia('bano_1', 'servicio', MIN_BANO, MIN_BANO + 2.0))
        estancias.append(Estancia('aseo',   'servicio', MIN_ASEO, MIN_ASEO + 1.0))
    else:
        estancias.append(Estancia('bano', 'servicio', MIN_BANO, MIN_BANO + 2.0))

    return estancias


def util_maximo(n_dorms: int) -> float:
    return UTIL_MAX.get(n_dorms, 150)
