"""§2.5 — Distribución paramétrica (sólo cálculos, no geometría).

Dado:
- envolvente: m² útil por planta tras muros y patios
- uso + categoría: define la unidad típica
- parámetros de diseño: circulación + núcleo vertical + accesibilidad

Devuelve cuántas unidades caben, cuánto consumen y cuánto se va a circulación
y muros divisorios. La adjudicación de qué tipo va dónde es geométrica y vive
fuera de este módulo (puccetti-app o un módulo gráfico).
"""
from __future__ import annotations
from dataclasses import dataclass

from .modelo import Unidad
from .diseno import ParametrosDiseno
from .normativa import (
    area_unidad_objetivo, areas_sociales_por_unidad,
    SUPERFICIES_HOTEL, SUPERFICIES_HOTEL_APARTAMENTO,
    SUPERFICIES_APT_EDIFICIOS, SUPERFICIES_VIVIENDA_MINIMAS,
)


@dataclass
class DistribucionPlanta:
    n: int
    area_disponible_m2: float          # área útil neta tras muros perimetrales y patios
    area_servicios_comunes_m2: float   # núcleo vertical + áreas sociales asignables a esta planta
    area_circulacion_m2: float         # pasillos + vestíbulo
    area_muros_divisorios_m2: float
    area_unidades_m2: float            # suma de areas útiles de unidades
    unidades: list[Unidad]


@dataclass
class DistribucionEdificio:
    plantas: list[DistribucionPlanta]
    n_unidades_total: int
    superficie_util_total_m2: float
    superficie_circulacion_total_m2: float
    superficie_muros_divisorios_total_m2: float
    superficie_servicios_comunes_total_m2: float
    cumple_minimos: bool
    alertas: list[str]


def _area_por_unidad(uso: str, categoria: str, diseno: ParametrosDiseno) -> float:
    """Área útil objetivo por unidad incluyendo el reparto de área social del uso."""
    base = area_unidad_objetivo(uso, categoria)
    social = areas_sociales_por_unidad(uso, categoria)
    return base + social


def distribuir(plantas_areas_utiles: list[float], uso: str, categoria: str,
               diseno: ParametrosDiseno) -> DistribucionEdificio:
    """Calcula cuántas unidades caben repartidas en N plantas.

    Modelo simplificado por uso:
    - **Vivienda**: una vivienda ocupa `area_unidad_objetivo`. La planta se
      llena de viviendas iguales hasta agotar el área útil neta. Núcleo
      vertical descontado de la planta. Multiplicidad = unidades por planta.
    - **Hotelero**: cada unidad = una habitación doble. Áreas sociales (lobby,
      restaurante…) consumen una fracción adicional. Núcleo vertical descontado.
    - **Apt turísticos**: apartamento de 1 dormitorio (salón+cocina+baño+dorm).
      Áreas sociales si el reglamento las exige (4 y 3 llaves).
    """
    alertas: list[str] = []
    area_unidad = _area_por_unidad(uso, categoria, diseno)
    if area_unidad <= 0:
        return DistribucionEdificio([], 0, 0, 0, 0, 0, False,
                                    ["Área por unidad no calculable"])

    plantas: list[DistribucionPlanta] = []
    n_plantas = len(plantas_areas_utiles)
    total_unidades = 0
    total_util = 0.0
    total_circ = 0.0
    total_div = 0.0
    total_com = 0.0

    for n, util_neta in enumerate(plantas_areas_utiles):
        if util_neta <= 0:
            plantas.append(DistribucionPlanta(n, 0, 0, 0, 0, 0, []))
            continue

        # Núcleo vertical en cada planta
        nucleo = diseno.area_nucleo_vertical_m2
        disponible = max(0.0, util_neta - nucleo)

        # Circulación (pasillos + vestíbulo) proporcional
        circ = disponible * diseno.pct_circulacion_planta
        disponible_post_circ = max(0.0, disponible - circ)

        # Muros divisorios entre unidades: ~5% del área restante
        muros_div = disponible_post_circ * 0.05
        disponible_para_unidades = max(0.0, disponible_post_circ - muros_div)

        n_unidades_planta = int(disponible_para_unidades // area_unidad)

        unidades_pl: list[Unidad] = []
        if n_unidades_planta > 0:
            # Plazas por unidad según uso (≈ doble = 2 plazas)
            plazas = 2 if uso != "vivienda" else _plazas_vivienda(categoria)
            unidades_pl.append(Unidad(
                tipo=_tipo_unidad(uso, categoria),
                cantidad=n_unidades_planta,
                area_util_unidad_m2=round(area_unidad, 2),
                plazas=plazas,
            ))
            area_unidades_m2 = n_unidades_planta * area_unidad
        else:
            area_unidades_m2 = 0.0
            if util_neta > nucleo + circ + muros_div:
                alertas.append(
                    f"Planta {n}: útil {util_neta:.1f} m² insuficiente para una"
                    f" unidad de {area_unidad:.1f} m² (uso {uso}/{categoria}).")

        plantas.append(DistribucionPlanta(
            n=n,
            area_disponible_m2=util_neta,
            area_servicios_comunes_m2=nucleo,
            area_circulacion_m2=circ,
            area_muros_divisorios_m2=muros_div,
            area_unidades_m2=area_unidades_m2,
            unidades=unidades_pl,
        ))
        total_unidades += n_unidades_planta
        total_util += area_unidades_m2
        total_circ += circ
        total_div += muros_div
        total_com += nucleo

    # Accesibilidad — ≥4% unidades adaptadas en residencial público
    if uso != "vivienda" and total_unidades > 0:
        n_acc_min = max(1, int(diseno.pct_unidades_accesibles_min * total_unidades))
        if total_unidades < n_acc_min:
            alertas.append(
                f"Se requiere al menos {n_acc_min} unidad(es) accesible(s) DB-SUA.")

    cumple = total_unidades > 0 and not any("insuficiente" in a for a in alertas)

    return DistribucionEdificio(
        plantas=plantas,
        n_unidades_total=total_unidades,
        superficie_util_total_m2=total_util,
        superficie_circulacion_total_m2=total_circ,
        superficie_muros_divisorios_total_m2=total_div,
        superficie_servicios_comunes_total_m2=total_com,
        cumple_minimos=cumple,
        alertas=alertas,
    )


def _plazas_vivienda(categoria: str) -> int:
    return {"estudio": 1, "vivienda_1d": 2, "vivienda_2d": 4,
            "vivienda_3d": 6, "vivienda_4d_o_mas": 8}.get(categoria, 4)


def _tipo_unidad(uso: str, categoria: str) -> str:
    if uso == "vivienda":
        return categoria
    if uso == "hotelero":
        return f"{categoria}/doble"
    if uso == "hotel_apartamento":
        return f"{categoria}/estudio"
    if uso in ("apartamentos_turisticos", "apartamentos_turisticos_conjunto"):
        return f"{categoria}/apt_1dorm"
    return categoria
