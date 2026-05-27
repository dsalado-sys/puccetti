"""§2.7 — Tabla de superficies en tiempo real.

Recibe la envolvente (§2.4) y la distribución (§2.5) y devuelve dos tablas
en pandas listas para mostrar y exportar:
- por planta: construida / útil unidades / circulación / muros / patios
- por unidad: tipo / cantidad / m² unidad / m² total
- agregado global

La tabla se recalcula cada vez que cambia un parámetro (la app la genera de
nuevo en cada interacción del Streamlit).
"""
from __future__ import annotations
import pandas as pd

from .envolvente import EnvolventeCalculo
from .distribucion import DistribucionEdificio


def tabla_por_planta(env: EnvolventeCalculo,
                     dist: DistribucionEdificio) -> pd.DataFrame:
    rows = []
    for ep, dp in zip(env.plantas, dist.plantas):
        muros_perim = ep.area_construida_m2 - ep.area_interior_bruta_m2
        rows.append({
            "planta": ep.n,
            "construida_m2": round(ep.area_construida_m2, 1),
            "util_unidades_m2": round(dp.area_unidades_m2, 1),
            "circulacion_m2": round(dp.area_circulacion_m2, 1),
            "servicios_comunes_m2": round(dp.area_servicios_comunes_m2, 1),
            "muros_perim_m2": round(muros_perim, 1),
            "muros_divisorios_m2": round(dp.area_muros_divisorios_m2, 1),
            "patios_m2": round(sum(p.area_m2 for p in ep.patios), 1),
            "n_patios": len(ep.patios),
            "eficiencia_util_pct": round(
                100 * dp.area_unidades_m2 / ep.area_construida_m2, 1)
                if ep.area_construida_m2 else 0.0,
        })
    return pd.DataFrame(rows)


def tabla_unidades(dist: DistribucionEdificio) -> pd.DataFrame:
    """Una fila por tipo de unidad distinto. Si todas las plantas son iguales,
    agrupa por tipo y área. Si no, lista por planta."""
    rows = []
    for dp in dist.plantas:
        for u in dp.unidades:
            rows.append({
                "planta": dp.n,
                "tipo": u.tipo,
                "cantidad": u.cantidad,
                "area_unidad_m2": u.area_util_unidad_m2,
                "area_total_m2": round(u.cantidad * u.area_util_unidad_m2, 1),
                "plazas_unidad": u.plazas,
                "plazas_total": u.cantidad * u.plazas,
            })
    if not rows:
        return pd.DataFrame(columns=[
            "planta", "tipo", "cantidad", "area_unidad_m2",
            "area_total_m2", "plazas_unidad", "plazas_total",
        ])
    return pd.DataFrame(rows)


def resumen(env: EnvolventeCalculo, dist: DistribucionEdificio,
            edificabilidad_max_m2t: float, parcela_m2: float) -> dict:
    muros_perim_total = sum(
        p.area_construida_m2 - p.area_interior_bruta_m2 for p in env.plantas
    )
    return {
        "parcela_m2": round(parcela_m2, 1),
        "n_plantas": env.n_plantas,
        "construida_total_m2": round(env.superficie_construida_total_m2, 1),
        "util_unidades_total_m2": round(dist.superficie_util_total_m2, 1),
        "circulacion_total_m2": round(dist.superficie_circulacion_total_m2, 1),
        "servicios_comunes_total_m2": round(dist.superficie_servicios_comunes_total_m2, 1),
        "muros_perim_total_m2": round(muros_perim_total, 1),
        "muros_divisorios_total_m2": round(dist.superficie_muros_divisorios_total_m2, 1),
        "patios_total_m2": round(env.superficie_patios_total_m2, 1),
        "n_unidades_total": dist.n_unidades_total,
        "edificabilidad_max_m2t": round(edificabilidad_max_m2t, 1),
        "pct_edificabilidad_usada":
            round(100 * env.superficie_construida_total_m2 / edificabilidad_max_m2t, 1)
            if edificabilidad_max_m2t else 0.0,
        "ratio_util_vs_construida_pct":
            round(100 * dist.superficie_util_total_m2 / env.superficie_construida_total_m2, 1)
            if env.superficie_construida_total_m2 else 0.0,
    }
