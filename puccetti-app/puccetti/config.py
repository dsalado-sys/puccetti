"""Parametros configurables del proyecto (PDF §2.6).

Pydantic Settings: por defecto los valores son los del PDF. La UI Streamlit los
deja editar y los inyecta en cada funcion del pipeline.
"""
from __future__ import annotations
from pydantic import BaseModel, Field


class ParametrosDiseno(BaseModel):
    """§2.6 — parametros configurables de diseno interior."""

    # Espesores de muros (§2.6 + A2.4)
    espesor_muro_fachada: float       = Field(0.25, ge=0.10, le=0.60)
    espesor_muro_medianero: float     = Field(0.25, ge=0.10, le=0.60)
    espesor_separacion_unidades: float = Field(0.20, ge=0.10, le=0.40)
    espesor_tabiqueria: float         = Field(0.10, ge=0.05, le=0.20)

    # Anchos minimos (A1.5 + A2.2)
    ancho_min_pasillo_comun: float    = Field(1.20, ge=0.90, le=2.00)
    ancho_min_pasillo_vivienda: float = Field(1.00, ge=0.90, le=2.00)
    diametro_min_vestibulo: float     = Field(1.50, ge=1.20, le=2.50)
    radio_apertura_puerta: float      = Field(0.80, ge=0.60, le=1.20)

    # Patios interiores (A2.5)
    luz_recta_patio_min: float        = Field(3.00, ge=2.00, le=8.00)
    area_patio_min: float             = Field(12.00, ge=6.00, le=40.00)
    profundidad_max_sin_patio: float  = Field(12.00, ge=8.00, le=20.00)


class ParametrosUrbanisticos(BaseModel):
    """§2.3 — analisis urbanistico. Defaults para Sevilla casco."""
    edificabilidad: float    = Field(2.5, ge=0.5, le=8.0)   # m2t / m2s
    ocupacion_maxima: float  = Field(1.00, ge=0.30, le=1.00) # 100% en casco
    n_plantas_max: int       = Field(3, ge=1, le=10)
    retranqueo_frontal: float = Field(0.0, ge=0.0, le=10.0)
    retranqueo_lateral: float = Field(0.0, ge=0.0, le=10.0)
    retranqueo_trasero: float = Field(0.0, ge=0.0, le=10.0)
    altura_planta: float     = Field(3.0, ge=2.5, le=4.5)


class ParametrosPrograma(BaseModel):
    """Programa arquitectonico del proyecto."""
    uso: str             = Field("vivienda", pattern="^(vivienda|hotel|apartamento)$")
    n_dormitorios: int   = Field(2, ge=0, le=6)        # 0 = estudio
    salon_cocina_open: bool = Field(False)
    n_plantas: int       = Field(1, ge=1, le=20)       # alineado con n_plantas_max urbanístico
    n_viviendas_por_planta: int = Field(1, ge=1, le=20)


class Parametros(BaseModel):
    """Bundle global."""
    diseno: ParametrosDiseno         = Field(default_factory=ParametrosDiseno)
    urbanismo: ParametrosUrbanisticos = Field(default_factory=ParametrosUrbanisticos)
    programa: ParametrosPrograma     = Field(default_factory=ParametrosPrograma)
    seed: int | None                 = Field(None, description="None = aleatorio")


DEFAULT = Parametros()
