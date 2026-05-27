"""Carga 10 parcelas reales del Catastro INSPIRE WFS en UNA sola consulta.

Idempotente: si ya existe data/parcelas_sevilla.gpkg sale sin volver a tocar la API
(respeta el rate limit del Catastro: ver feedback_no_quemar_api_catastro).
"""
from __future__ import annotations
import os, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import geopandas as gpd

from puccetti.catastro import fetch_parcels_bbox

OUT = ROOT / "data" / "parcelas_sevilla.gpkg"

# BBOX en EPSG:25830 (UTM 30N) en San Lorenzo / Feria (Sevilla casco residencial).
# Parcelario fragmentado tipico: viviendas unifamiliares de 60-200 m2.
BBOX = (234900, 4143200, 235200, 4143450)


def main(n_target: int = 10) -> None:
    if OUT.exists():
        existing = gpd.read_file(OUT, layer='muestra')
        print(f"OK ya existe {OUT}  ({len(existing)} en muestra).  No re-consulto Catastro.")
        return

    print(f"Una consulta al Catastro WFS sobre BBOX {BBOX} EPSG:25830 ...")
    gdf_all = fetch_parcels_bbox(BBOX, max_features=200)
    print(f"  recibidas {len(gdf_all)} features. Columnas: {list(gdf_all.columns)[:8]}...")

    # Normalizar columnas.
    keep = {}
    for cand in ['localId', 'localid', 'gml:identifier', 'identifier']:
        if cand in gdf_all.columns:
            keep[cand] = 'referencia_catastral'; break
    for cand in ['label', 'nationalCadastralReference']:
        if cand in gdf_all.columns:
            keep[cand] = 'etiqueta'; break
    for cand in ['areaValue', 'area']:
        if cand in gdf_all.columns:
            keep[cand] = 'area_catastral_m2'; break

    gdf_all = gdf_all.rename(columns=keep)
    cols = ['geometry'] + [c for c in keep.values() if c in gdf_all.columns]
    gdf_all = gdf_all[cols].copy()
    gdf_all = gdf_all[gdf_all.geometry.is_valid & ~gdf_all.geometry.is_empty]
    gdf_all['area_m2_calc'] = gdf_all.geometry.area

    # Contexto: todas las parcelas del BBOX (para clasificar fachadas/medianeras).
    contexto = gdf_all.reset_index(drop=True)
    contexto['parcela_id'] = range(len(contexto))

    # Muestra: 10 parcelas de tamano vivienda urbana (50-250 m2), mezcla grandes/chicas.
    muestra = gdf_all[(gdf_all['area_m2_calc'] >= 50)
                      & (gdf_all['area_m2_calc'] <= 250)].copy()
    muestra = muestra.sort_values('area_m2_calc', ascending=False)
    if len(muestra) > n_target:
        idx = list(range(n_target // 2)) + list(range(-(n_target - n_target // 2), 0))
        muestra = muestra.iloc[idx]
    muestra = muestra.head(n_target).reset_index(drop=True)
    muestra['parcela_id'] = range(len(muestra))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    muestra.to_file(OUT, layer='muestra', driver='GPKG')
    contexto.to_file(OUT, layer='contexto', driver='GPKG')
    print(f"OK guardadas {len(muestra)} en muestra + {len(contexto)} en contexto, en {OUT}")
    print(muestra.drop(columns='geometry'))


if __name__ == '__main__':
    main()
