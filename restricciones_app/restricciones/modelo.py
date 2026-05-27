"""Modelo de datos del proyecto.

Tres entradas principales:
- Parcela: lo que tenemos físicamente (geometría o medidas equivalentes).
- PGOU: lo que el planeamiento permite (§2.3).
- ProgramaInversor: lo que el inversor pretende (uso, gama, mix).
- Costes: parámetros económicos (§2.9).

Una salida:
- Resultado: solución óptima con todo lo necesario para el informe.
"""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field

UsoEdificio = Literal["vivienda", "hotelero", "hotel_apartamento",
                      "apartamentos_turisticos", "apartamentos_turisticos_conjunto"]


class Parcela(BaseModel):
    """Datos físicos de la parcela. Aceptamos dos formas equivalentes."""
    referencia: str = Field("manual", description="RC catastral o id")
    superficie_m2: float = Field(..., gt=0, description="Superficie del solar")
    perimetro_m: Optional[float] = Field(None, gt=0)
    profundidad_media_m: Optional[float] = Field(
        None, gt=0,
        description="Profundidad media solar→fondo. Se usa para detectar patios.",
    )
    longitud_fachada_m: Optional[float] = Field(None, ge=0)
    longitud_medianera_m: Optional[float] = Field(None, ge=0)
    orientacion_fachada_principal: Optional[
        Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    ] = None
    tiene_edificio_preexistente: bool = False
    proteccion_patrimonial: Literal["ninguna", "municipal", "bic"] = "ninguna"

    def lado_estimado(self) -> tuple[float, float]:
        """Devuelve (frente, fondo) estimados asumiendo parcela rectangular."""
        if self.longitud_fachada_m and self.profundidad_media_m:
            return float(self.longitud_fachada_m), float(self.profundidad_media_m)
        # Si solo tenemos superficie+perímetro, resolvemos sistema 2(a+b)=P, a·b=S
        if self.perimetro_m:
            P, S = self.perimetro_m, self.superficie_m2
            disc = (P / 2) ** 2 - 4 * S
            if disc >= 0:
                root = disc ** 0.5
                a = (P / 2 + root) / 2
                b = (P / 2 - root) / 2
                return max(a, b), min(a, b)
        # Fallback: cuadrado
        lado = self.superficie_m2 ** 0.5
        return lado, lado


class PGOU(BaseModel):
    """§2.3 — Parámetros urbanísticos del planeamiento municipal."""
    edificabilidad: float = Field(2.5, gt=0, le=10, description="m²t / m²s")
    ocupacion_maxima: float = Field(1.0, gt=0, le=1.0, description="Fracción 0–1")
    n_plantas_max: int = Field(3, ge=1, le=20)
    altura_planta_m: float = Field(3.0, ge=2.5, le=5.0)
    retranqueo_frontal_m: float = Field(0.0, ge=0.0)
    retranqueo_lateral_m: float = Field(0.0, ge=0.0)
    retranqueo_trasero_m: float = Field(0.0, ge=0.0)
    usos_permitidos: list[UsoEdificio] = Field(
        default_factory=lambda: ["vivienda", "hotelero", "apartamentos_turisticos"]
    )


class ProgramaInversor(BaseModel):
    """Intención del inversor. El optimizador respeta esto pero busca dentro."""
    uso: UsoEdificio = "vivienda"
    categoria: Optional[str] = Field(
        None, description="hotel_4e, apt_2llaves, vivienda_2d… (None = optimizar)",
    )
    n_plantas_objetivo: Optional[int] = Field(
        None, description="None = optimizar dentro del máximo del PGOU",
    )
    mix_dormitorios: Optional[dict[int, float]] = Field(
        None, description="Vivienda: {1: 0.3, 2: 0.5, 3: 0.2}. None = elige uno fijo.",
    )


class Costes(BaseModel):
    """§2.9 — Parámetros económicos. Valores por defecto razonables para Sevilla 2026."""
    coste_construccion_eur_m2: float = Field(1400.0, gt=0)
    precio_venta_eur_m2: float = Field(3200.0, gt=0,
        description="Vivienda: precio venta. Hotel/apt: usar renta_eur_m2_mes")
    renta_eur_m2_mes: float = Field(15.0, gt=0,
        description="€/m² mes de explotación; aplica a hotelero/apt turístico")
    ocupacion_anual_pct: float = Field(0.65, ge=0, le=1,
        description="Tasa ocupación hotelero/apt — 0..1")
    multiplicador_valor_hotelero: float = Field(12.0, gt=0,
        description="Múltiplo NOI anual → valor patrimonial (cap rate inverso)")
    coste_suelo_eur: float = Field(0.0, ge=0, description="0 = ignorar")
    pct_costes_indirectos: float = Field(0.18, ge=0, le=0.5,
        description="Honorarios + tasas + financiación sobre coste constr.")


class Unidad(BaseModel):
    """Una unidad de alojamiento concreta (vivienda, habitación, apt llave)."""
    tipo: str            # "vivienda_2d", "doble", "estudio"…
    cantidad: int        # cuántas iguales hay
    area_util_unidad_m2: float
    plazas: int = 1


class Resultado(BaseModel):
    """Salida de optimizar() — todo lo necesario para informe y comparación."""
    # Decisión
    uso: UsoEdificio
    categoria: str
    n_plantas: int
    n_unidades_total: int
    unidades: list[Unidad]
    # §2.4 cálculo envolvente
    superficie_parcela_m2: float
    huella_max_m2: float
    huella_efectiva_m2: float
    superficie_construida_total_m2: float
    superficie_util_total_m2: float
    superficie_circulacion_total_m2: float
    superficie_muros_total_m2: float
    superficie_patios_total_m2: float
    n_patios: int
    # Aprovechamiento urbanístico
    edificabilidad_consumida_m2t_m2s: float
    edificabilidad_max_m2t_m2s: float
    pct_edificabilidad_usada: float
    pct_ocupacion: float
    # §2.9 viabilidad
    ingresos_eur: float
    coste_construccion_eur: float
    coste_total_eur: float
    margen_eur: float
    roi_pct: float
    # Diagnóstico
    cumple_normativa: bool
    alertas: list[str] = []
    # Metadatos
    objetivo: Literal["margen", "m2_util", "n_unidades"] = "margen"
    score: float = 0.0
