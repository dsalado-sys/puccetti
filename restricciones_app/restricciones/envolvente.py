"""§2.4 — Cálculo de envolvente edificatoria (sin representación gráfica).

Devuelve por planta los valores numéricos relevantes:
- área construida (huella)
- área útil tras descontar muros perimetrales y patios
- nº de patios y su superficie

No genera ni shapely ni planos. Trabaja con dimensiones derivadas de la parcela
y los retranqueos. Usa un modelo de parcela rectangular equivalente (frente·fondo)
suficiente para la prefactibilidad — la representación 2D/3D queda fuera de
este módulo por requisito explícito del briefing.
"""
from __future__ import annotations
from dataclasses import dataclass

from .modelo import Parcela, PGOU
from .diseno import ParametrosDiseno
from .urbanismo import TechosUrbanisticos


@dataclass
class PatioCalculo:
    area_m2: float
    luz_recta_m: float


@dataclass
class PlantaCalculo:
    n: int                                  # 0 = PB
    area_construida_m2: float               # huella
    area_interior_bruta_m2: float           # tras muros perimetrales
    area_util_neta_m2: float                # tras muros + patios
    patios: list[PatioCalculo]


@dataclass
class EnvolventeCalculo:
    plantas: list[PlantaCalculo]
    huella_efectiva_m2: float
    n_plantas: int
    superficie_construida_total_m2: float
    superficie_util_total_m2: float
    superficie_patios_total_m2: float
    edificabilidad_consumida_m2t_m2s: float


def _dimensiones_huella(parcela: Parcela, pgou: PGOU,
                        huella_objetivo_m2: float) -> tuple[float, float]:
    """Frente·fondo efectivos para una huella objetivo manteniendo proporción."""
    frente, fondo = parcela.lado_estimado()
    # Tras retranqueos
    f_eff = max(1.0, frente - 2 * pgou.retranqueo_lateral_m)
    d_eff = max(1.0, fondo - pgou.retranqueo_frontal_m - pgou.retranqueo_trasero_m)
    huella_geom = f_eff * d_eff
    if huella_geom <= 0 or huella_objetivo_m2 <= 0:
        return 0.0, 0.0
    escala = (huella_objetivo_m2 / huella_geom) ** 0.5
    return f_eff * escala, d_eff * escala


def _calcular_patios(frente_int: float, fondo_int: float,
                     diseno: ParametrosDiseno) -> list[PatioCalculo]:
    """Si la profundidad interior supera el umbral sin patio, abrimos patios.

    Lógica: si fondo_int > profundidad_max_sin_patio, hace falta un patio cada
    `profundidad_max_sin_patio` metros (modelo simplificado tipo Sevilla).
    """
    if fondo_int <= diseno.profundidad_max_sin_patio_m:
        return []
    n_patios = int(fondo_int // diseno.profundidad_max_sin_patio_m)
    # Patio rectangular de lado = luz_recta y ancho ajustado para cumplir área mín
    lr = diseno.luz_recta_patio_min_m
    lado_b = max(lr, diseno.area_patio_min_m2 / lr)
    # Limitar lado_b al frente interior disponible (no puede ser más ancho que la planta)
    lado_b = min(lado_b, max(lr, frente_int * 0.6))
    area = lr * lado_b
    return [PatioCalculo(area_m2=area, luz_recta_m=lr) for _ in range(n_patios)]


def calcular(parcela: Parcela, pgou: PGOU, diseno: ParametrosDiseno,
             techos: TechosUrbanisticos,
             n_plantas: int, huella_objetivo_m2: float | None = None,
             ) -> EnvolventeCalculo:
    """Calcula la envolvente para n_plantas y una huella objetivo.

    Si `huella_objetivo_m2` es None, usa la huella máxima permitida.
    Si la suma de huellas excede la edificabilidad, recorta proporcionalmente.
    """
    if n_plantas <= 0:
        raise ValueError("n_plantas debe ser ≥ 1")
    if n_plantas > pgou.n_plantas_max:
        raise ValueError(f"n_plantas {n_plantas} > tope PGOU {pgou.n_plantas_max}")

    huella = min(huella_objetivo_m2 or techos.huella_max_m2, techos.huella_max_m2)

    # Restricción de edificabilidad: si n_plantas × huella > edificabilidad_max,
    # reducimos huella para encajar.
    edif_max = techos.edificabilidad_max_m2t
    if huella * n_plantas > edif_max:
        huella = edif_max / n_plantas

    frente_eff, fondo_eff = _dimensiones_huella(parcela, pgou, huella)
    if frente_eff <= 0:
        return EnvolventeCalculo([], 0.0, 0, 0.0, 0.0, 0.0, 0.0)

    # Muros perimetrales: reducen el frente y fondo interiores
    frente_int = max(0.0, frente_eff - 2 * diseno.espesor_muro_medianero_m)
    fondo_int = max(0.0, fondo_eff - 2 * diseno.espesor_muro_fachada_m)
    interior_bruta = frente_int * fondo_int

    plantas: list[PlantaCalculo] = []
    for n in range(n_plantas):
        patios = _calcular_patios(frente_int, fondo_int, diseno)
        area_patios = sum(p.area_m2 for p in patios)
        util_neta = max(0.0, interior_bruta - area_patios)
        plantas.append(PlantaCalculo(
            n=n,
            area_construida_m2=huella,
            area_interior_bruta_m2=interior_bruta,
            area_util_neta_m2=util_neta,
            patios=patios,
        ))

    construida_total = sum(p.area_construida_m2 for p in plantas)
    util_total = sum(p.area_util_neta_m2 for p in plantas)
    patios_total = sum(pat.area_m2 for p in plantas for pat in p.patios)

    edif_consumida = construida_total / parcela.superficie_m2 if parcela.superficie_m2 else 0

    return EnvolventeCalculo(
        plantas=plantas,
        huella_efectiva_m2=huella,
        n_plantas=n_plantas,
        superficie_construida_total_m2=construida_total,
        superficie_util_total_m2=util_total,
        superficie_patios_total_m2=patios_total,
        edificabilidad_consumida_m2t_m2s=edif_consumida,
    )
