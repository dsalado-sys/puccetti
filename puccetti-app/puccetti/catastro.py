"""Cliente del WFS INSPIRE de la Sede del Catastro.

El motor de Puccetti calcula sobre CUALQUIER parcela. Este modulo la obtiene del
Catastro a partir de su referencia catastral o de unas coordenadas, junto con su
entorno (parcelas vecinas, necesarias para clasificar fachadas/medianeras).

Cada analisis hace 1-2 consultas WFS, cacheadas por la app. El GPKG de muestra
sigue disponible como modo offline para no depender de la red.
"""
from __future__ import annotations
import geopandas as gpd
from shapely.geometry import Point

# Servicios INSPIRE oficiales (no usar ".meta." — eso era un mirror caido)
WFS_PARCELS_URL = "http://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx"
WFS_BUILDINGS_URL = "http://ovc.catastro.meh.es/INSPIRE/wfsBU.aspx"

DEFAULT_TIMEOUT = 60   # s


def fetch_parcels_bbox(
    bbox_25830: tuple[float, float, float, float],
    max_features: int = 50,
) -> gpd.GeoDataFrame:
    """Una llamada WFS GetFeature al endpoint de parcelas catastrales (INSPIRE).

    bbox_25830: (xmin, ymin, xmax, ymax) en EPSG:25830 (UTM 30N, metros).
    Devuelve un GeoDataFrame con geometria, refcat, area_catastral.
    """
    xmin, ymin, xmax, ymax = bbox_25830
    url = (
        f"{WFS_PARCELS_URL}"
        f"?service=WFS&version=2.0.0&request=GetFeature"
        f"&typeNames=cp:CadastralParcel"
        f"&srsName=urn:ogc:def:crs:EPSG::25830"
        f"&bbox={xmin},{ymin},{xmax},{ymax},urn:ogc:def:crs:EPSG::25830"
        f"&count={max_features}"
    )
    gdf = gpd.read_file(url)
    if gdf.crs is None:
        gdf = gdf.set_crs(25830)
    else:
        gdf = gdf.to_crs(25830)
    return gdf


def fetch_parcela_por_rc(rc: str) -> gpd.GeoDataFrame:
    """Geometria de UNA parcela por referencia catastral (stored query INSPIRE
    GetParcel). Acepta la RC de 14 o 20 caracteres (se usa el cargo de 14)."""
    rc = "".join(rc.split()).upper()[:14]
    url = (
        f"{WFS_PARCELS_URL}"
        f"?service=WFS&version=2.0.0&request=GetFeature"
        f"&STOREDQUERY_ID=GetParcel&refcat={rc}"
        f"&srsname=urn:ogc:def:crs:EPSG::25830"
    )
    gdf = gpd.read_file(url)
    if gdf.empty:
        raise ValueError(f"El Catastro no devolvió ninguna parcela para la RC '{rc}'.")
    if gdf.crs is None:
        gdf = gdf.set_crs(25830)
    else:
        gdf = gdf.to_crs(25830)
    return gdf


def parcela_y_entorno_por_rc(rc: str, margen: float = 45.0):
    """(parcela_geom, parcelas_vecinas) a partir de una referencia catastral.
    Dos consultas WFS: GetParcel + GetFeature por bbox para las colindantes."""
    parc = fetch_parcela_por_rc(rc)
    geom = parc.geometry.iloc[0]
    xmin, ymin, xmax, ymax = geom.buffer(margen).bounds
    entorno = fetch_parcels_bbox((xmin, ymin, xmax, ymax), max_features=120)
    return geom, entorno


def parcela_y_entorno_por_coord(lon: float, lat: float, margen: float = 45.0):
    """(parcela_geom, parcelas_vecinas) a partir de coordenadas geográficas
    (lon, lat en EPSG:4326). Una consulta WFS por bbox; la parcela es la que
    contiene el punto."""
    pt = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(25830).iloc[0]
    bbox = (pt.x - margen, pt.y - margen, pt.x + margen, pt.y + margen)
    entorno = fetch_parcels_bbox(bbox, max_features=120)
    if entorno.empty:
        raise ValueError("El Catastro no devolvió parcelas en esas coordenadas.")
    contiene = entorno[entorno.geometry.contains(pt)]
    if contiene.empty:
        idx = entorno.geometry.distance(pt).idxmin()
        contiene = entorno.loc[[idx]]
    return contiene.geometry.iloc[0], entorno


def fetch_buildings_bbox(
    bbox_25830: tuple[float, float, float, float],
    max_features: int = 200,
) -> gpd.GeoDataFrame:
    """Edificios catastrales (Building) en el mismo BBOX. Opcional."""
    xmin, ymin, xmax, ymax = bbox_25830
    url = (
        f"{WFS_BUILDINGS_URL}"
        f"?service=WFS&version=2.0.0&request=GetFeature"
        f"&typeNames=bu-ext2d:Building"
        f"&srsName=urn:ogc:def:crs:EPSG::25830"
        f"&bbox={xmin},{ymin},{xmax},{ymax},urn:ogc:def:crs:EPSG::25830"
        f"&count={max_features}"
    )
    gdf = gpd.read_file(url)
    if gdf.crs is None:
        gdf = gdf.set_crs(25830)
    else:
        gdf = gdf.to_crs(25830)
    return gdf
