"""FastAPI app — frontend para localización de activos.

Endpoints:
    POST /api/locate/rc            { rc }
    POST /api/locate/address       { provincia, municipio, tipo_via, calle, numero }
    POST /api/locate/coordinates   { lon, lat }
    POST /api/locate/file          multipart (file, crs_origen?)
    GET  /api/activo/{id}/pdf
    GET  /api/activo/{id}/geojson
    GET  /                          → index.html
"""
from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .exportar import activo_a_geojson_bytes, activo_a_pdf
from .localizar import (
    Activo,
    RateLimitCatastro,
    SinParcelaEnPunto,
    activo_simplificado_a_geojson_bytes,
    localizar_por_coordenadas,
    localizar_por_direccion,
    localizar_por_planimetria,
    localizar_por_rc,
    simplificar_contorno,
)
from .normativa import (
    REGLAS_ANEXO_II,
    catalogo_normativa,
    init_db,
    reset_db,
    update_valor,
)
from .proyecto import (
    actualizar_diseno,
    actualizar_urbanismo,
    actualizar_uso,
    calcular_alertas,
    obtener_o_crear,
    resetear_diseno,
)


ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
TEMPLATES_DIR = ROOT / "templates"

app = FastAPI(title="Puccetti · Localizar Activo", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def _startup():
    # Crea y siembra la BD de normativa si aún no existe.
    init_db()

_STORE: Dict[str, Activo] = {}


def _guardar(activo: Activo) -> str:
    aid = uuid.uuid4().hex[:12]
    _STORE[aid] = activo
    if len(_STORE) > 200:
        for k in list(_STORE.keys())[:-200]:
            _STORE.pop(k, None)
    return aid


def _serializar(activo: Activo) -> dict:
    payload = activo.to_dict()
    payload["id"] = _guardar(activo)
    return payload


class RCRequest(BaseModel):
    rc: str = Field(min_length=14, max_length=20)


class AddressRequest(BaseModel):
    provincia: str
    municipio: str
    tipo_via: str
    calle: str
    numero: str


class CoordsRequest(BaseModel):
    lon: float
    lat: float


def _wrap(fn, *args, **kwargs):
    try:
        return _serializar(fn(*args, **kwargs))
    except RateLimitCatastro as e:
        # 503: el servicio de terceros (Catastro) está temporalmente bloqueado.
        raise HTTPException(status_code=503, detail=str(e))
    except SinParcelaEnPunto as e:
        # 422: la petición es válida pero el punto no contiene parcela.
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.get("/", response_class=HTMLResponse)
def index():
    return (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")


@app.post("/api/locate/rc")
def api_rc(req: RCRequest):
    return _wrap(localizar_por_rc, req.rc.strip().upper())


@app.post("/api/locate/address")
def api_address(req: AddressRequest):
    return _wrap(
        localizar_por_direccion,
        provincia=req.provincia.strip(),
        municipio=req.municipio.strip(),
        tipo_via=req.tipo_via.strip(),
        calle=req.calle.strip(),
        numero=req.numero.strip(),
    )


@app.post("/api/locate/coordinates")
def api_coords(req: CoordsRequest):
    return _wrap(localizar_por_coordenadas, lon=req.lon, lat=req.lat)


_ENTRY_PRIORITY = (".shp", ".gpkg", ".geojson", ".json", ".kml", ".gml", ".dxf", ".zip")


def _elegir_archivo_entrada(paths: List[Path]) -> Path:
    """Selecciona el archivo principal entre varios subidos (caso típico: SHP)."""
    by_ext = {p.suffix.lower(): p for p in paths}
    for ext in _ENTRY_PRIORITY:
        if ext in by_ext:
            return by_ext[ext]
    return paths[0]


@app.post("/api/locate/file")
async def api_file(
    files: List[UploadFile] = File(...),
    crs_origen: Optional[str] = Form(default=None),
):
    """Acepta uno o varios archivos.

    - GeoJSON / KML / GPKG / DXF / ZIP: basta con uno.
    - Shapefile: hay que aportar **todos** los sidecars (.shp .shx .dbf .prj).
      Si solo viene el .shp, se intenta reconstruir el .shx vía
      ``SHAPE_RESTORE_SHX=YES`` (gestionado en ``localizar.py``).
    """
    if not files:
        raise HTTPException(status_code=400, detail="No se ha enviado ningún archivo.")

    tmpdir = Path(tempfile.mkdtemp(prefix="puccetti_"))
    try:
        saved: List[Path] = []
        for f in files:
            raw_name = Path(f.filename or "upload").name
            dest = tmpdir / raw_name
            with dest.open("wb") as out:
                out.write(await f.read())
            saved.append(dest)

        entrada = _elegir_archivo_entrada(saved)
        return _wrap(
            localizar_por_planimetria, str(entrada), crs_origen=crs_origen
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@app.get("/api/activo/{aid}/pdf")
def api_pdf(aid: str, tolerancia: float = 0.0):
    activo = _STORE.get(aid)
    if not activo:
        raise HTTPException(status_code=404, detail="Activo no encontrado o expirado.")
    pdf = activo_a_pdf(activo, tolerancia_m=tolerancia)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="ficha_{activo.rc or aid}.pdf"',
        },
    )


@app.get("/api/activo/{aid}/geojson")
def api_geojson(aid: str, tolerancia: float = 0.0):
    activo = _STORE.get(aid)
    if not activo:
        raise HTTPException(status_code=404, detail="Activo no encontrado o expirado.")
    if tolerancia and tolerancia > 0:
        data = activo_simplificado_a_geojson_bytes(activo, tolerancia)
        nombre = f"parcela_{activo.rc or aid}_simpl_{tolerancia:.2f}m.geojson"
    else:
        data = activo_a_geojson_bytes(activo)
        nombre = f"parcela_{activo.rc or aid}.geojson"
    return Response(
        content=data,
        media_type="application/geo+json",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@app.get("/api/activo/{aid}/simplificar")
def api_simplificar(aid: str, tolerancia: float = 0.0):
    """Devuelve el contorno simplificado con la tolerancia indicada (metros).

    Tolerancia 0 = sin simplificación, devuelve el original con sus estadísticas.
    Tolerancia válida en [0, 50]: por encima de 50 m el resultado degenera y no
    tiene sentido para parcelas urbanas o rústicas pequeñas.
    """
    activo = _STORE.get(aid)
    if not activo:
        raise HTTPException(status_code=404, detail="Activo no encontrado o expirado.")
    if tolerancia < 0 or tolerancia > 50:
        raise HTTPException(
            status_code=400, detail="La tolerancia debe estar entre 0 y 50 metros."
        )
    return simplificar_contorno(activo, tolerancia)


@app.get("/api/health")
def health():
    return {"status": "ok", "activos_en_cache": len(_STORE)}


# ─── §2.3 Urbanismo + §2.6 Diseño + Anexos ──────────────────────────────────


@app.get("/api/normativa")
def api_normativa():
    """Catálogo completo: usos, categorías, tablas del Anexo I, reglas Anexo II.

    Los valores numéricos del Anexo I se leen de la BD SQLite (editable).
    """
    return {
        "anexo_I": catalogo_normativa(),
        "anexo_II": REGLAS_ANEXO_II,
    }


class NormativaValorRequest(BaseModel):
    grupo: str
    categoria: str = "_"
    tipologia: str
    valor: Optional[float] = None


@app.put("/api/normativa/valor")
def api_normativa_valor(req: NormativaValorRequest):
    """Edita un valor de la tabla de superficies (Anexo I) y lo persiste en SQLite."""
    grupos_validos = {
        "hotel", "areas_sociales_hotel", "hotel_apartamento",
        "apt_edificios", "apt_conjuntos", "vivienda_maximas",
        "vivienda_estancias", "vivienda_reglas",
    }
    if req.grupo not in grupos_validos:
        raise HTTPException(status_code=400, detail=f"Grupo desconocido: {req.grupo}")
    update_valor(req.grupo, req.categoria, req.tipologia, req.valor)
    return {"ok": True, "anexo_I": catalogo_normativa()}


@app.post("/api/normativa/reset")
def api_normativa_reset():
    """Restaura todos los valores del Anexo I a los de fábrica."""
    reset_db()
    return {"ok": True, "anexo_I": catalogo_normativa()}


class UsoRequest(BaseModel):
    uso: Optional[str] = None
    categoria: Optional[str] = None


class UrbanismoRequest(BaseModel):
    edificabilidad_m2t_m2s: Optional[float] = None
    plantas_max: Optional[int] = None
    ocupacion_max_pct: Optional[float] = None
    retranqueos_m: Optional[Dict[str, float]] = None
    usos_permitidos: Optional[list[str]] = None
    patio_min_luz_recta_m: Optional[float] = None
    patio_min_superficie_m2: Optional[float] = None
    atico_computa_edificabilidad: Optional[bool] = None
    atico_computa_plantas: Optional[bool] = None
    sotano_computa_edificabilidad: Optional[bool] = None
    sotano_computa_plantas: Optional[bool] = None
    notas: Optional[str] = None
    fuente: Optional[str] = None
    fecha_consulta: Optional[str] = None


class DisenoRequest(BaseModel):
    muros: Optional[Dict[str, float]] = None
    circulacion: Optional[Dict[str, float]] = None
    patios: Optional[Dict[str, float]] = None


def _requiere_activo(aid: str) -> Activo:
    activo = _STORE.get(aid)
    if not activo:
        raise HTTPException(status_code=404, detail="Activo no encontrado o expirado.")
    return activo


@app.get("/api/activo/{aid}/proyecto")
def api_proyecto(aid: str):
    activo = _requiere_activo(aid)
    estado = obtener_o_crear(aid)
    return {
        "estado": estado.to_dict(),
        "alertas": calcular_alertas(activo, estado),
    }


@app.put("/api/activo/{aid}/uso")
def api_uso(aid: str, req: UsoRequest):
    activo = _requiere_activo(aid)
    try:
        estado = actualizar_uso(aid, req.uso, req.categoria)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"estado": estado.to_dict(), "alertas": calcular_alertas(activo, estado)}


@app.put("/api/activo/{aid}/urbanismo")
def api_urbanismo(aid: str, req: UrbanismoRequest):
    activo = _requiere_activo(aid)
    datos = {k: v for k, v in req.model_dump().items() if v is not None}
    estado = actualizar_urbanismo(aid, datos)
    return {"estado": estado.to_dict(), "alertas": calcular_alertas(activo, estado)}


@app.put("/api/activo/{aid}/diseno")
def api_diseno(aid: str, req: DisenoRequest):
    activo = _requiere_activo(aid)
    datos = {k: v for k, v in req.model_dump().items() if v is not None}
    estado = actualizar_diseno(aid, datos)
    return {"estado": estado.to_dict(), "alertas": calcular_alertas(activo, estado)}


@app.post("/api/activo/{aid}/diseno/reset")
def api_diseno_reset(aid: str):
    activo = _requiere_activo(aid)
    estado = resetear_diseno(aid)
    return {"estado": estado.to_dict(), "alertas": calcular_alertas(activo, estado)}
