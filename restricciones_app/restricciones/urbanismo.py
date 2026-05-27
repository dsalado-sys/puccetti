"""§2.3 — Análisis urbanístico.

Aplica al PGOU y produce:
- los topes derivados (huella máxima, edificabilidad máxima total)
- alertas de incompatibilidad (uso no permitido, parcela orientativa pequeña,
  retranqueos que aniquilan la huella, protección patrimonial…).
"""
from __future__ import annotations
from dataclasses import dataclass

from .modelo import Parcela, PGOU, ProgramaInversor


@dataclass
class TechosUrbanisticos:
    """Topes que el PGOU impone sobre esta parcela concreta."""
    superficie_parcela_m2: float
    huella_max_m2: float                  # ocupación × parcela − retranqueos
    edificabilidad_max_m2t: float         # edificabilidad × parcela
    n_plantas_max: int
    altura_max_m: float
    alertas: list[str]


def _huella_post_retranqueos(parcela: Parcela, pgou: PGOU) -> float:
    """Calcula la huella máxima tras aplicar retranqueos sobre lados estimados."""
    frente, fondo = parcela.lado_estimado()
    r_lat = pgou.retranqueo_lateral_m
    frente_efectivo = max(0.0, frente - 2 * r_lat)
    fondo_efectivo = max(0.0,
        fondo - pgou.retranqueo_frontal_m - pgou.retranqueo_trasero_m)
    huella_geom = frente_efectivo * fondo_efectivo
    huella_pgou = pgou.ocupacion_maxima * parcela.superficie_m2
    return min(huella_geom, huella_pgou)


def analizar(parcela: Parcela, pgou: PGOU,
             programa: ProgramaInversor) -> TechosUrbanisticos:
    alertas: list[str] = []

    if programa.uso not in pgou.usos_permitidos:
        alertas.append(
            f"Uso '{programa.uso}' no figura entre los usos permitidos del PGOU"
            f" {pgou.usos_permitidos}.")

    huella_max = _huella_post_retranqueos(parcela, pgou)
    if huella_max <= 0:
        alertas.append("Los retranqueos eliminan la huella edificable.")

    edif_max = pgou.edificabilidad * parcela.superficie_m2
    altura_max = pgou.n_plantas_max * pgou.altura_planta_m

    if parcela.superficie_m2 < 80:
        alertas.append(
            f"Parcela {parcela.superficie_m2:.0f} m² es marginal — el PGOU"
            " municipal habitualmente exige superficie mínima de parcela.")

    if parcela.proteccion_patrimonial == "bic":
        alertas.append(
            "Protección BIC: cualquier intervención requiere informe favorable"
            " de la Comisión Provincial de Patrimonio.")
    elif parcela.proteccion_patrimonial == "municipal":
        alertas.append(
            "Catalogación municipal: revisar grado de protección antes de"
            " plantear demolición o nueva planta.")

    if parcela.tiene_edificio_preexistente:
        alertas.append(
            "Edificio preexistente — evaluar viabilidad de rehabilitación vs"
            " demolición + nueva planta (§2.2).")

    return TechosUrbanisticos(
        superficie_parcela_m2=parcela.superficie_m2,
        huella_max_m2=huella_max,
        edificabilidad_max_m2t=edif_max,
        n_plantas_max=pgou.n_plantas_max,
        altura_max_m=altura_max,
        alertas=alertas,
    )
