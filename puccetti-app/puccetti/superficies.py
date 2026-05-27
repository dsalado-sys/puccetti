"""Tabla de superficies (§2.7) — vinculada al modelo, recalculable en tiempo real."""
from __future__ import annotations
import pandas as pd

from .distributor import PlantaDistribuida
from .envolvente import Envolvente


def tabla_estancias(plantas: list[PlantaDistribuida]) -> pd.DataFrame:
    """DataFrame con una fila por estancia (planta x estancia)."""
    rows = []
    for pl in plantas:
        for ec in pl.estancias:
            rows.append({
                'planta': pl.n,
                'estancia': ec.nombre,
                'categoria': ec.categoria,
                'area_min_m2': round(ec.area_min_m2, 2),
                'area_target_m2': round(ec.area_target_m2, 2),
                'area_real_m2': round(ec.area_real_m2, 2),
                'cumple_min': ec.area_real_m2 + 1e-3 >= ec.area_min_m2,
                'delta_vs_target_m2': round(ec.area_real_m2 - ec.area_target_m2, 2),
            })
    return pd.DataFrame(rows)


def tabla_por_planta(
    envol: Envolvente,
    plantas_dist: list[PlantaDistribuida],
) -> pd.DataFrame:
    """Resumen por planta: construida, util, comun, pasillo, muros."""
    rows = []
    for envol_p, dist in zip(envol.plantas, plantas_dist):
        util = sum(ec.area_real_m2 for ec in dist.estancias
                   if ec.categoria in ('publica', 'privada', 'servicio'))
        circ = sum(ec.area_real_m2 for ec in dist.estancias
                   if ec.categoria == 'circulacion')
        muros = dist.muros_perimetrales.area + dist.muros_divisorios.area
        patios = sum(p.area_m2 for p in envol_p.patios)
        rows.append({
            'planta': dist.n,
            'construida_m2':       round(envol_p.area_construida_m2, 2),
            'util_m2':             round(util, 2),
            'circulacion_m2':      round(circ, 2),
            'muros_m2':            round(muros, 2),
            'patios_m2':           round(patios, 2),
            'eficiencia_util_pct': round(100 * util / envol_p.area_construida_m2, 1)
                                   if envol_p.area_construida_m2 else 0,
        })
    return pd.DataFrame(rows)


def resumen_global(
    envol: Envolvente,
    plantas_dist: list[PlantaDistribuida],
) -> dict:
    construida = sum(p.area_construida_m2 for p in envol.plantas)
    util = sum(ec.area_real_m2 for d in plantas_dist for ec in d.estancias
               if ec.categoria in ('publica', 'privada', 'servicio'))
    edif_max = envol.edificabilidad_max
    return {
        'parcela_m2':            round(envol.parcela.area, 2),
        'plantas':               len(envol.plantas),
        'construida_total_m2':   round(construida, 2),
        'util_total_m2':         round(util, 2),
        'edificabilidad_max_m2': round(edif_max, 2),
        'edificabilidad_usada_pct': round(100 * construida / edif_max, 1) if edif_max else 0,
        'incidencias_a22':       sum(len(d.incidencias_a22) for d in plantas_dist),
    }
