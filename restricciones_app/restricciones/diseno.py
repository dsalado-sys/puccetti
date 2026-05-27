"""§2.6 — Parámetros de diseño interior configurables.

Defaults: criterios Anexo II + buenas prácticas Sevilla casco. Todos editables
desde la UI. El optimizador los lee como parámetros, no como hard-codes.
"""
from __future__ import annotations
from pydantic import BaseModel, Field


class ParametrosDiseno(BaseModel):
    # Espesores de muros
    espesor_muro_fachada_m: float        = Field(0.30, ge=0.10, le=0.60)
    espesor_muro_medianero_m: float      = Field(0.30, ge=0.10, le=0.60)
    espesor_separacion_unidades_m: float = Field(0.20, ge=0.10, le=0.40)
    espesor_tabiqueria_m: float          = Field(0.10, ge=0.05, le=0.20)

    # Anchos mínimos (A1.5 + A2.2 + DB-SUA)
    ancho_min_pasillo_comun_m: float     = Field(1.20, ge=0.90, le=2.50)
    ancho_min_pasillo_unidad_m: float    = Field(1.00, ge=0.90, le=2.00)
    diametro_min_vestibulo_m: float      = Field(1.50, ge=1.20, le=2.50)

    # Patios interiores (A2.5)
    luz_recta_patio_min_m: float         = Field(3.00, ge=2.00, le=8.00)
    area_patio_min_m2: float             = Field(12.00, ge=6.00, le=40.00)
    profundidad_max_sin_patio_m: float   = Field(12.00, ge=8.00, le=20.00)

    # Circulación y núcleos verticales
    pct_circulacion_planta: float        = Field(0.12, ge=0.05, le=0.30,
        description="Fracción de la planta destinada a circulación (pasillos+vestíbulo).")
    area_nucleo_vertical_m2: float       = Field(20.0, ge=10.0, le=60.0,
        description="Escalera + ascensor + rellano por núcleo y planta.")
    nucleos_por_unidades: int            = Field(8, ge=4, le=20,
        description="1 núcleo cada N unidades (≈ Anexo II).")

    # Accesibilidad (Consideración §2.5)
    pct_unidades_accesibles_min: float   = Field(0.04, ge=0.0, le=1.0,
        description="DB-SUA: ≥4% unidades adaptadas en residencial público.")


DEFAULT = ParametrosDiseno()
