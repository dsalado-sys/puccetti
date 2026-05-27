"""Núcleo de localización de activos inmobiliarios.

Extraído de ``Python/localizar_activo.ipynb`` para uso desde el backend FastAPI.

Notas sobre las URLs de Catastro:
- El notebook original usaba ``ovc.catastro.meta.minhap.es`` (el ``.meta.`` no
  resuelve DNS y provocaba ``ConnectionError`` en las celdas 27 y 31).
- ``ovc.catastro.minhap.es`` sí resuelve, pero su certificado SSL está emitido
  para ``ovc.catastro.meh.es`` (dominio histórico que sigue siendo canónico).
  Si usas ``minhap.es`` saltan ``SSLCertVerificationError`` por hostname mismatch.
- La forma robusta es usar directamente ``ovc.catastro.meh.es``.
"""
from __future__ import annotations

import os

# Permitir leer Shapefiles aunque el usuario solo aporte el .shp sin .shx.
os.environ.setdefault("SHAPE_RESTORE_SHX", "YES")

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple, Union

import geopandas as gpd
import requests
from shapely.geometry import Polygon as ShpPoly

from ESCatastroLib import MetaParcela, ParcelaCatastral
from ESCatastroLib.utils.exceptions import ErrorServidorCatastro


CATASTRO_RCCOOR = (
    "https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero/"
    "COVCCoordenadas.svc/json/Consulta_RCCOOR"
)
CATASTRO_DNPRC = (
    "https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero/"
    "COVCCallejero.svc/json/Consulta_DNPRC"
)
PNOA_WMS = "https://www.ign.es/wms-inspire/pnoa-ma"
CATASTRO_INSPIRE_WMS = (
    "https://ovc.catastro.meh.es/Cartografia/WMS/ServidorWMS.aspx"
)


@dataclass
class Activo:
    rc: str
    direccion: str
    provincia: str
    municipio: str
    superficie_catastral_m2: float
    centroide: Tuple[float, float]
    contorno_gdf: gpd.GeoDataFrame
    edificio: Optional[dict] = None
    uso_catastro: Optional[str] = None
    fuente: str = ""
    geometria_externa: Optional[gpd.GeoDataFrame] = None
    # Lista de subreferencias cuando la parcela física contiene varias unidades
    # (edificio con muchos pisos/locales). Cada item: {rc, localizacion, uso,
    # superficie_construida_m2}. Vacía cuando la parcela es una sola unidad.
    subreferencias: List[dict] = field(default_factory=list)

    @property
    def coordenadas_contorno(self):
        g = self.contorno_gdf
        if g.crs and str(g.crs).upper() != "EPSG:4326":
            g = g.to_crs(epsg=4326)
        geom = g.geometry.union_all()
        if geom.geom_type == "Polygon":
            return [list(geom.exterior.coords)]
        if geom.geom_type == "MultiPolygon":
            return [list(p.exterior.coords) for p in geom.geoms]
        return []

    def _gdf_4326(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        if gdf.crs and str(gdf.crs).upper() != "EPSG:4326":
            return gdf.to_crs(epsg=4326)
        return gdf

    def agregados_metaparcela(self) -> Optional[dict]:
        """Métricas del conjunto cuando la parcela contiene varias referencias.

        - ``suma_superficie_construida_m2``: Σ de la superficie construida de todas
          las subreferencias (sumatorio de las referencias catastrales).
        - ``edificabilidad_resultante_m2t_m2s``: techo construido / suelo de parcela.
          Es la edificabilidad **materializada** del edificio existente.
        - ``densidad_viviendas_viv_ha``: nº de unidades de uso residencial por
          hectárea de parcela.

        Devuelve ``None`` cuando no hay subreferencias (parcela de una sola unidad).
        """
        if not self.subreferencias:
            return None
        suma = sum(
            float(s.get("superficie_construida_m2") or 0) for s in self.subreferencias
        )
        sup_parcela = float(self.superficie_catastral_m2 or 0)
        n_viviendas = sum(
            1 for s in self.subreferencias if _uso_es_vivienda(s.get("uso", ""))
        )
        edificabilidad = (suma / sup_parcela) if sup_parcela else None
        densidad = (n_viviendas / (sup_parcela / 10_000)) if sup_parcela else None
        return {
            "num_referencias": len(self.subreferencias),
            "suma_superficie_construida_m2": suma,
            "edificabilidad_resultante_m2t_m2s": edificabilidad,
            "num_viviendas": n_viviendas,
            "densidad_viviendas_viv_ha": densidad,
        }

    def to_geojson(self) -> dict:
        gdf = self._gdf_4326(self.contorno_gdf)
        fc = {"type": "FeatureCollection", "features": []}
        props_catastro = {
            "rc": self.rc,
            "fuente": "catastro",
            "direccion": self.direccion,
            "municipio": self.municipio,
            "provincia": self.provincia,
            "uso_catastro": self.uso_catastro,
            "superficie_catastral_m2": self.superficie_catastral_m2,
        }
        if self.subreferencias:
            props_catastro["subreferencias"] = self.subreferencias
        for _, row in gdf.iterrows():
            fc["features"].append(
                {
                    "type": "Feature",
                    "geometry": row.geometry.__geo_interface__,
                    "properties": dict(props_catastro),
                }
            )
        if self.geometria_externa is not None:
            ext = self._gdf_4326(self.geometria_externa)
            for _, row in ext.iterrows():
                fc["features"].append(
                    {
                        "type": "Feature",
                        "geometry": row.geometry.__geo_interface__,
                        "properties": {"rc": self.rc, "fuente": "externa"},
                    }
                )
        return fc

    def to_dict(self) -> dict:
        lon, lat = self.centroide
        gdf = self._gdf_4326(self.contorno_gdf)
        bounds = gdf.total_bounds.tolist()
        return {
            "rc": self.rc,
            "direccion": self.direccion,
            "provincia": self.provincia,
            "municipio": self.municipio,
            "superficie_catastral_m2": self.superficie_catastral_m2,
            "uso_catastro": self.uso_catastro,
            # 'centroide' se mantiene en el payload para situar el marcador del
            # mapa, aunque ya no se muestre como propiedad en la ficha.
            "centroide": {"lon": lon, "lat": lat},
            "edificio": self.edificio,
            "fuente": self.fuente,
            "bounds": bounds,
            "geojson": self.to_geojson(),
            "subreferencias": self.subreferencias,
            "agregados": self.agregados_metaparcela(),
        }


def _extraer_rc20(rc_dict: dict) -> str:
    """Concatena las partes del RC (pc1 + pc2 + car + cc1 + cc2) en un string de 20 chars."""
    return "".join(rc_dict.get(k, "") or "" for k in ("pc1", "pc2", "car", "cc1", "cc2"))


def _uso_es_vivienda(uso: str) -> bool:
    """Heurística para contar unidades residenciales a partir del uso catastral.

    El campo ``luso`` del Catastro suele venir como texto ("Residencial",
    "Comercial", "Almacén-Estacionamiento"…) o como código corto ("V" = vivienda).
    Consideramos vivienda cuando el texto contiene 'residencial'/'vivienda' o es
    exactamente 'V'.
    """
    u = (uso or "").strip().lower()
    if not u:
        return False
    return "residencial" in u or "vivienda" in u or u == "v"


def _subref_de_item(item: dict) -> dict:
    """Convierte un item del array `rcdnp` de Catastro en nuestra estructura de subref."""
    rc20 = _extraer_rc20(item.get("rc", {}))
    dt = item.get("dt", {}) or {}
    debi = item.get("debi", {}) or {}
    # Localización descriptiva: escalera + planta + puerta dentro del edificio
    loint = (
        dt.get("locs", {}).get("lous", {}).get("lourb", {}).get("loint", {})
        or {}
    )
    partes = []
    es = (loint.get("es") or "").strip()
    pt = (loint.get("pt") or "").strip()
    pu = (loint.get("pu") or "").strip()
    if es:
        partes.append(f"Es {es}")
    if pt:
        partes.append(f"Pl {pt}")
    if pu:
        partes.append(f"Pt {pu}")
    try:
        sup = float(debi.get("sfc") or 0)
    except (TypeError, ValueError):
        sup = 0.0
    return {
        "rc": rc20,
        "localizacion": " · ".join(partes),
        "uso": (debi.get("luso") or "").strip(),
        "superficie_construida_m2": sup,
    }


def _subreferencias_por_rc14(rc14: str) -> List[dict]:
    """Devuelve la lista de subreferencias de una parcela física en 1 sola llamada.

    Si el RC ya es de 20 chars se trunca a los 14 primeros (la parcela física).
    """
    rc14 = (rc14 or "")[:14]
    if len(rc14) != 14:
        return []
    r = requests.get(CATASTRO_DNPRC, params={"RefCat": rc14}, timeout=30)
    _detectar_rate_limit(r)
    r.raise_for_status()
    try:
        data = r.json().get("consulta_dnprcResult", {})
    except ValueError:
        # Respuesta no-JSON: probablemente otro fallo del servidor; lo ignoramos
        # y devolvemos lista vacía (el activo principal seguirá funcionando).
        return []
    lrcdnp = data.get("lrcdnp") or {}
    rcdnp = lrcdnp.get("rcdnp")
    if rcdnp is None:
        return []
    if isinstance(rcdnp, dict):
        rcdnp = [rcdnp]
    return [_subref_de_item(it) for it in rcdnp if _extraer_rc20(it.get("rc", {}))]


def _resolver_parcela(rc=None, direccion=None):
    """Devuelve (parcela_representante, lista_subreferencias).

    ``lista_subreferencias`` está vacía cuando la parcela tiene una única RC.
    Cuando es un edificio con varias unidades (pisos/locales), contiene todas
    las RCs hijas con su localización (planta · puerta), uso y superficie.
    """
    try:
        if rc:
            return ParcelaCatastral(rc=rc), []
        return ParcelaCatastral(**direccion), []
    except (ValueError, ErrorServidorCatastro) as e:
        if "MetaParcela" not in str(e):
            raise

    # Es una MetaParcela: obtener subreferencias y un representante para geometría.
    if rc:
        # Camino rápido: 1 llamada para sacar todas las subref + 1 para la geometría.
        subref = _subreferencias_por_rc14(rc[:14])
        if not subref:
            raise RuntimeError("MetaParcela sin subreferencias resolubles")
        primer = ParcelaCatastral(rc=subref[0]["rc"])
        return primer, subref

    # Por dirección: usamos MetaParcela (más lento, pero ya tenemos la calle normalizada).
    mp = MetaParcela(**direccion)
    if not mp.parcelas:
        raise RuntimeError("MetaParcela sin parcelas internas")
    # Intentamos enriquecer la lista con localización/uso vía DNPRC (1 llamada extra).
    primer = mp.parcelas[0]
    subref = _subreferencias_por_rc14(primer.rc[:14])
    if not subref:
        subref = [
            {
                "rc": p.rc,
                "localizacion": "",
                "uso": (getattr(p, "uso", "") or "").strip(),
                "superficie_construida_m2": float(
                    getattr(p, "superficie_construida", 0) or 0
                ),
            }
            for p in mp.parcelas
        ]
    return primer, subref


def _centroide_lonlat(p, gdf):
    centro = getattr(p, "centroide", None) or {}
    lon = centro.get("longitud") or centro.get("lon") or centro.get("x")
    lat = centro.get("latitud") or centro.get("lat") or centro.get("y")
    if lon is None or lat is None:
        c = gdf.to_crs(epsg=4326).geometry.union_all().centroid
        lon, lat = c.x, c.y
    return float(lon), float(lat)


def _info_edificio(p):
    sup = getattr(p, "superficie_construida", 0) or 0
    anio = getattr(p, "antiguedad", None)
    try:
        plantas = p.numero_plantas
    except Exception:
        plantas = None
    if not (sup or anio or plantas):
        return None
    plantas = plantas or {}
    return {
        "plantas_sobre_rasante": plantas.get("plantas"),
        "sotanos": plantas.get("sotanos"),
        "plantas_total": plantas.get("total"),
        "anio_construccion": anio,
        "superficie_construida_m2": sup,
    }


def _parcela_a_activo(
    p, fuente: str, subreferencias: Optional[List[dict]] = None
) -> Activo:
    gdf = p.to_dataframe()
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)
    lon, lat = _centroide_lonlat(p, gdf)
    direccion = " ".join(
        x for x in [getattr(p, "tipo_via", ""), getattr(p, "calle", "")] if x
    ).strip()
    numero = getattr(p, "numero", "") or ""
    if numero:
        direccion = f"{direccion}, {numero}".strip(", ")
    return Activo(
        rc=getattr(p, "rc", "") or "",
        direccion=direccion,
        provincia=getattr(p, "provincia", "") or "",
        municipio=getattr(p, "municipio", "") or "",
        superficie_catastral_m2=float(getattr(p, "superficie_total", 0) or 0),
        centroide=(lon, lat),
        contorno_gdf=gdf,
        edificio=_info_edificio(p),
        uso_catastro=getattr(p, "uso", None),
        fuente=fuente,
        subreferencias=subreferencias or [],
    )


_CACHE_RC: dict = {}
_CACHE_DIR: dict = {}


def localizar_por_rc(rc: str) -> Activo:
    key = (rc or "").strip().upper()
    if key in _CACHE_RC:
        return _CACHE_RC[key]
    p, subref = _resolver_parcela(rc=key)
    activo = _parcela_a_activo(p, fuente="rc", subreferencias=subref)
    _CACHE_RC[key] = activo
    return activo


def localizar_por_direccion(
    provincia: str,
    municipio: str,
    tipo_via: str,
    calle: str,
    numero: Union[str, int],
) -> Activo:
    direccion = dict(
        provincia=provincia,
        municipio=municipio,
        tipo_via=tipo_via,
        calle=calle,
        numero=str(numero),
    )
    key = tuple(direccion.items())
    if key in _CACHE_DIR:
        return _CACHE_DIR[key]
    p, subref = _resolver_parcela(direccion=direccion)
    activo = _parcela_a_activo(p, fuente="direccion", subreferencias=subref)
    _CACHE_DIR[key] = activo
    return activo


class SinParcelaEnPunto(ValueError):
    """El punto no cae sobre ninguna parcela catastral (acera, vial, descampado…)."""


class RateLimitCatastro(RuntimeError):
    """El Catastro ha bloqueado nuestra IP por exceder el límite de peticiones por hora."""


def _detectar_rate_limit(respuesta: requests.Response) -> None:
    """Lanza RateLimitCatastro si la respuesta indica bloqueo por límite horario.

    El Catastro lo señaliza de dos formas distintas según el endpoint:
    - HTTP 403 Forbidden en endpoints REST puros.
    - XML ``<error>Peticion denegada. Ha superado el limite de peticiones por hora.</error>``
      con HTTP 200 en endpoints SOAP/WCF (incluso cuando pedimos JSON).
    """
    if respuesta.status_code == 403:
        raise RateLimitCatastro(
            "El Catastro ha bloqueado temporalmente las peticiones desde esta IP "
            "por exceder el límite horario. Inténtalo de nuevo en ~1 hora."
        )
    txt = (respuesta.text or "")[:400].lower()
    if "limite de peticiones" in txt or "petici&#243;n denegada" in txt:
        raise RateLimitCatastro(
            "El Catastro ha bloqueado temporalmente las peticiones desde esta IP "
            "por exceder el límite horario. Inténtalo de nuevo en ~1 hora."
        )


def _rc_desde_coordenadas(lon: float, lat: float, srs: str = "EPSG:4326") -> str:
    """Devuelve la RC de la parcela que contiene exactamente el punto.

    ⚠ Nombres correctos de los parámetros HTTP: ``CoorX`` / ``CoorY`` (no
    ``Coordenada_X`` / ``Coordenada_Y``, que era el bug del notebook original
    causante del error 76 "LA COORDENADA X OBLIGATORIA").
    """
    r = requests.get(
        CATASTRO_RCCOOR,
        params={"SRS": srs, "CoorX": lon, "CoorY": lat},
        timeout=30,
    )
    _detectar_rate_limit(r)
    r.raise_for_status()
    data = r.json().get("Consulta_RCCOORResult", {})
    control = data.get("control", {})
    if control.get("cuerr", 0) and not control.get("cucoor"):
        raise SinParcelaEnPunto(
            "El punto no está sobre ninguna parcela del Catastro. "
            "Haz click dentro de una parcela."
        )
    coords = data.get("coordenadas", {}).get("coord", [])
    if not coords:
        raise SinParcelaEnPunto(
            "El punto no está sobre ninguna parcela del Catastro. "
            "Haz click dentro de una parcela."
        )
    pc = coords[0].get("pc", {})
    rc = f"{pc.get('pc1', '')}{pc.get('pc2', '')}"
    if not rc:
        raise SinParcelaEnPunto(
            "El punto no está sobre ninguna parcela del Catastro. "
            "Haz click dentro de una parcela."
        )
    return rc


def localizar_por_coordenadas(lon: float, lat: float) -> Activo:
    rc = _rc_desde_coordenadas(lon, lat)
    p, subref = _resolver_parcela(rc=rc)
    return _parcela_a_activo(p, fuente="mapa", subreferencias=subref)


def _cargar_geometria(path, crs_origen: Optional[str] = None) -> gpd.GeoDataFrame:
    path = Path(path)
    if path.suffix.lower() in {".dxf", ".dwg"}:
        import ezdxf

        if path.suffix.lower() == ".dwg":
            raise ValueError(
                "Convierte el DWG a DXF primero (ver autocad_a_multipolygon.ipynb)."
            )
        doc = ezdxf.readfile(str(path))
        polys = []
        for e in doc.modelspace():
            t = e.dxftype()
            if t == "LWPOLYLINE" and e.closed:
                pts = [(p[0], p[1]) for p in e.get_points("xy")]
                if len(pts) >= 3:
                    polys.append(ShpPoly(pts))
            elif t == "POLYLINE" and getattr(e, "is_closed", False):
                pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
                if len(pts) >= 3:
                    polys.append(ShpPoly(pts))
        if not polys:
            raise ValueError(
                f"No se encontraron polígonos cerrados en {path.name}."
            )
        gdf = gpd.GeoDataFrame({"geometry": polys}, geometry="geometry")
    else:
        gdf = gpd.read_file(path)

    if gdf.crs is None:
        if crs_origen is None:
            raise ValueError(
                'La planimetría no incluye CRS. Indica crs_origen, p.ej. "EPSG:25830".'
            )
        gdf.set_crs(crs_origen, inplace=True)
    return gdf


def localizar_por_planimetria(
    path, crs_origen: Optional[str] = None
) -> Activo:
    gdf_ext = _cargar_geometria(path, crs_origen=crs_origen)
    centro = gdf_ext.to_crs(epsg=4326).geometry.union_all().centroid
    activo = localizar_por_coordenadas(centro.x, centro.y)
    activo.fuente = "planimetria"
    activo.geometria_externa = gdf_ext.to_crs(epsg=4326)
    return activo


# ─── Simplificación de contorno ───────────────────────────────────────────────


def _utm_srs_para_lon(lon: float) -> str:
    """Devuelve el SRS UTM ETRS89 adecuado para la longitud (España peninsular + Canarias)."""
    if lon < -12:
        return "EPSG:4083"  # REGCAN95 UTM 28N
    if lon < -6:
        return "EPSG:25829"
    if lon < 0:
        return "EPSG:25830"
    return "EPSG:25831"


def _contar_vertices(gdf: gpd.GeoDataFrame) -> int:
    total = 0
    for geom in gdf.geometry:
        if geom is None:
            continue
        if geom.geom_type == "Polygon":
            total += len(geom.exterior.coords)
            for ring in geom.interiors:
                total += len(ring.coords)
        elif geom.geom_type == "MultiPolygon":
            for p in geom.geoms:
                total += len(p.exterior.coords)
                for ring in p.interiors:
                    total += len(ring.coords)
        elif hasattr(geom, "coords"):
            total += len(geom.coords)
    return total


def simplificar_contorno(activo: Activo, tolerancia_m: float) -> dict:
    """Simplifica el contorno catastral con Douglas-Peucker y tolerancia en metros.

    La tolerancia representa la desviación máxima (en metros) permitida entre el
    contorno original y el simplificado. Aplicamos el algoritmo sobre la
    proyección UTM ETRS89 adecuada al centroide para que la unidad sea metros, y
    devolvemos el resultado de vuelta a EPSG:4326 para el mapa web.

    Cuando ``tolerancia_m == 0`` no se aplica simplificación (se devuelve el
    contorno original con sus estadísticas).
    """
    if tolerancia_m < 0:
        tolerancia_m = 0.0

    gdf = activo.contorno_gdf
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    gdf_4326 = gdf.to_crs(epsg=4326)
    centro = gdf_4326.geometry.union_all().centroid
    srs_utm = _utm_srs_para_lon(centro.x)
    gdf_utm = gdf_4326.to_crs(srs_utm)

    if tolerancia_m > 0:
        gdf_simp_utm = gdf_utm.copy()
        gdf_simp_utm["geometry"] = gdf_utm.geometry.simplify(
            tolerancia_m, preserve_topology=True
        )
    else:
        gdf_simp_utm = gdf_utm

    sup_orig = float(gdf_utm.geometry.area.sum())
    sup_simp = float(gdf_simp_utm.geometry.area.sum())
    vert_orig = _contar_vertices(gdf_utm)
    vert_simp = _contar_vertices(gdf_simp_utm)

    gdf_simp_4326 = gdf_simp_utm.to_crs(epsg=4326)
    features = []
    for _, row in gdf_simp_4326.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": row.geometry.__geo_interface__,
                "properties": {
                    "rc": activo.rc,
                    "fuente": "catastro_simplificado",
                    "tolerancia_m": tolerancia_m,
                },
            }
        )
    geojson = {"type": "FeatureCollection", "features": features}
    bounds = gdf_simp_4326.total_bounds.tolist()

    diff_m2 = sup_simp - sup_orig
    diff_pct = (diff_m2 / sup_orig * 100.0) if sup_orig else 0.0

    return {
        "geojson": geojson,
        "bounds": bounds,
        "tolerancia_m": tolerancia_m,
        "superficie_original_m2": sup_orig,
        "superficie_simplificada_m2": sup_simp,
        "diferencia_m2": diff_m2,
        "diferencia_pct": diff_pct,
        "vertices_original": vert_orig,
        "vertices_simplificado": vert_simp,
        "srs_metrico": srs_utm,
    }


def activo_simplificado_a_geojson_bytes(activo: Activo, tolerancia_m: float) -> bytes:
    """Genera el GeoJSON exportable del contorno simplificado."""
    import json

    res = simplificar_contorno(activo, tolerancia_m)
    out = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": res["geojson"]["features"],
        "puccetti_metadata": {
            "rc": activo.rc,
            "tolerancia_m": tolerancia_m,
            "superficie_original_m2": res["superficie_original_m2"],
            "superficie_simplificada_m2": res["superficie_simplificada_m2"],
            "vertices_original": res["vertices_original"],
            "vertices_simplificado": res["vertices_simplificado"],
        },
    }
    return json.dumps(out, ensure_ascii=False, indent=2).encode("utf-8")
