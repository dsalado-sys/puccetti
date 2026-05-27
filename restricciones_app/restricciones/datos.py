"""Carga de parcelas.

Dos fuentes:
1. `puccetti-app/data/parcelas_sevilla.gpkg` — 10 parcelas catastrales de Sevilla.
2. Formulario manual — el usuario introduce superficie/perímetro/dimensiones.

Convierte ambas en un `Parcela` (modelo unificado).
"""
from __future__ import annotations
import pathlib
from typing import Optional

from .modelo import Parcela

GPKG_PUCCETTI = (
    pathlib.Path(__file__).resolve().parents[2]
    / "puccetti-app" / "data" / "parcelas_sevilla.gpkg"
)


def gpkg_disponible() -> bool:
    return GPKG_PUCCETTI.exists()


def listar_parcelas_puccetti() -> list[dict]:
    """Devuelve dicts con referencia + superficie de cada parcela disponible.

    No carga geopandas si no hace falta: si la dependencia no está disponible,
    devolvemos lista vacía y la UI lo señala como tal.
    """
    if not gpkg_disponible():
        return []
    try:
        import geopandas as gpd
    except ImportError:
        return []
    try:
        gdf = gpd.read_file(GPKG_PUCCETTI, layer="muestra")
    except Exception:
        return []

    out = []
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        # En GPKG el CRS suele ser EPSG:25830 (UTM metros). Comprobamos.
        try:
            if gdf.crs and gdf.crs.is_geographic:
                geom_m = gpd.GeoSeries([geom], crs=gdf.crs).to_crs(25830).iloc[0]
            else:
                geom_m = geom
        except Exception:
            geom_m = geom

        sup = float(geom_m.area)
        perim = float(geom_m.length)
        mrr = geom_m.minimum_rotated_rectangle
        coords = list(mrr.exterior.coords)[:-1]
        edges = [(coords[i], coords[(i + 1) % 4]) for i in range(4)]
        lados = sorted(
            ((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2) ** 0.5
            for p1, p2 in edges
        )
        frente_est = lados[-1]
        fondo_est = lados[0]
        ref = str(
            row.get("referencia_catastral")
            or row.get("refcat") or row.get("REFCAT")
            or row.get("parcela_id") or row.get("id") or "?"
        )
        out.append({
            "referencia": ref,
            "superficie_m2": round(sup, 1),
            "perimetro_m": round(perim, 1),
            "frente_m": round(frente_est, 1),
            "fondo_m": round(fondo_est, 1),
        })
    return out


def parcela_desde_gpkg(referencia: str) -> Optional[Parcela]:
    pl = listar_parcelas_puccetti()
    for p in pl:
        if p["referencia"] == referencia:
            return Parcela(
                referencia=referencia,
                superficie_m2=p["superficie_m2"],
                perimetro_m=p["perimetro_m"],
                longitud_fachada_m=p["frente_m"],
                profundidad_media_m=p["fondo_m"],
                longitud_medianera_m=2 * p["fondo_m"],
            )
    return None


def parcela_manual(
    superficie_m2: float,
    longitud_fachada_m: float | None = None,
    profundidad_media_m: float | None = None,
    perimetro_m: float | None = None,
    orientacion: str | None = None,
    proteccion: str = "ninguna",
    edificio_preexistente: bool = False,
) -> Parcela:
    return Parcela(
        referencia="manual",
        superficie_m2=superficie_m2,
        perimetro_m=perimetro_m,
        longitud_fachada_m=longitud_fachada_m,
        profundidad_media_m=profundidad_media_m,
        orientacion_fachada_principal=orientacion,
        proteccion_patrimonial=proteccion,
        tiene_edificio_preexistente=edificio_preexistente,
    )
