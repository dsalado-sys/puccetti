"""§2.9 — Análisis de viabilidad económica básica.

Dos modelos de negocio según uso:
- **Venta (vivienda)**: ingresos = m² útil × €/m² venta × factor_categoría.
- **Explotación (hotelero / apt turístico)**: NOI anual = renta·m²·12·ocupación
  − OPEX; valor = NOI × multiplicador. Ese valor es el ingreso patrimonial
  comparable al de venta.

Costes:
- Construcción = construida × €/m².
- Indirectos = % sobre construcción (honorarios, tasas, financiación).
- Suelo = parámetro opcional (0 = ignorar).

Salida:
- ingresos, coste_total, margen €, ROI %.
"""
from __future__ import annotations
from dataclasses import dataclass

from .modelo import Costes
from .normativa import FACTOR_PRECIO_CATEGORIA, CATALOGO_USOS


@dataclass
class Viabilidad:
    modelo_negocio: str           # "venta" | "explotacion"
    ingresos_eur: float
    coste_construccion_eur: float
    coste_indirectos_eur: float
    coste_suelo_eur: float
    coste_total_eur: float
    margen_eur: float
    roi_pct: float
    noi_anual_eur: float = 0.0    # solo en explotación
    desglose: dict = None


def calcular(uso: str, categoria: str, construida_m2: float,
             util_m2: float, n_unidades: int, costes: Costes) -> Viabilidad:
    factor = FACTOR_PRECIO_CATEGORIA.get(categoria, 1.0)
    coste_constr = construida_m2 * costes.coste_construccion_eur_m2
    coste_indir = coste_constr * costes.pct_costes_indirectos
    coste_total = coste_constr + coste_indir + costes.coste_suelo_eur

    modelo = CATALOGO_USOS[uso]["modelo_negocio"]
    if modelo == "venta":
        ingresos = util_m2 * costes.precio_venta_eur_m2 * factor
        noi = 0.0
    else:
        renta_mes = util_m2 * costes.renta_eur_m2_mes * factor
        ingresos_anuales = renta_mes * 12 * costes.ocupacion_anual_pct
        opex = ingresos_anuales * 0.35   # estándar hotelero ≈30-40%
        noi = ingresos_anuales - opex
        ingresos = noi * costes.multiplicador_valor_hotelero

    margen = ingresos - coste_total
    roi = (margen / coste_total * 100.0) if coste_total > 0 else 0.0

    return Viabilidad(
        modelo_negocio=modelo,
        ingresos_eur=round(ingresos, 0),
        coste_construccion_eur=round(coste_constr, 0),
        coste_indirectos_eur=round(coste_indir, 0),
        coste_suelo_eur=round(costes.coste_suelo_eur, 0),
        coste_total_eur=round(coste_total, 0),
        margen_eur=round(margen, 0),
        roi_pct=round(roi, 1),
        noi_anual_eur=round(noi, 0),
        desglose={
            "factor_categoria": factor,
            "n_unidades": n_unidades,
            "construida_m2": construida_m2,
            "util_m2": util_m2,
        },
    )
