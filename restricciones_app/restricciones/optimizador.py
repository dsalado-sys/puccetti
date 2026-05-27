"""Núcleo del proyecto — búsqueda del escenario óptimo.

Pasos por escenario candidato:
1. urbanismo.analizar → topes y alertas (§2.3)
2. envolvente.calcular para una (n_plantas, huella) → m² por planta (§2.4)
3. distribucion.distribuir → nº unidades, áreas (§2.5)
4. viabilidad.calcular → margen, ROI (§2.9)
5. Score según objetivo elegido

Espacio de búsqueda:
- categorías permitidas del uso elegido
- n_plantas ∈ [1, n_plantas_max] (o el fijado por el inversor)
- huella ∈ {huella_max, huella_max·0.85, huella_max·0.70} (densificación)

Suficientemente pequeño (~ N×9×3 ≈ 100-300 candidatos) para fuerza bruta.
"""
from __future__ import annotations
from typing import Literal
from itertools import product

from .modelo import Parcela, PGOU, ProgramaInversor, Costes, Resultado, Unidad
from .diseno import ParametrosDiseno
from .normativa import CATALOGO_USOS
from .urbanismo import analizar as analizar_urbanismo
from .envolvente import calcular as calcular_envolvente
from .distribucion import distribuir
from .viabilidad import calcular as calcular_viabilidad

Objetivo = Literal["margen", "m2_util", "n_unidades"]


def _score(resultado: Resultado, objetivo: Objetivo) -> float:
    if objetivo == "margen":
        return resultado.margen_eur
    if objetivo == "m2_util":
        return resultado.superficie_util_total_m2
    if objetivo == "n_unidades":
        return float(resultado.n_unidades_total)
    raise ValueError(f"Objetivo desconocido: {objetivo}")


def _evaluar_candidato(parcela: Parcela, pgou: PGOU, diseno: ParametrosDiseno,
                       costes: Costes, programa: ProgramaInversor,
                       uso: str, categoria: str, n_plantas: int,
                       fraccion_huella: float) -> Resultado | None:
    techos = analizar_urbanismo(parcela, pgou,
        ProgramaInversor(uso=uso, categoria=categoria,
                         n_plantas_objetivo=n_plantas))
    if techos.huella_max_m2 <= 0:
        return None

    huella_obj = techos.huella_max_m2 * fraccion_huella
    try:
        env = calcular_envolvente(parcela, pgou, diseno, techos,
                                  n_plantas=n_plantas,
                                  huella_objetivo_m2=huella_obj)
    except ValueError:
        return None
    if env.n_plantas == 0:
        return None

    dist = distribuir([p.area_util_neta_m2 for p in env.plantas],
                      uso=uso, categoria=categoria, diseno=diseno)
    if dist.n_unidades_total == 0:
        return None

    via = calcular_viabilidad(uso, categoria,
                              env.superficie_construida_total_m2,
                              dist.superficie_util_total_m2,
                              dist.n_unidades_total, costes)

    # Aplanar unidades sumando cantidades por tipo
    agreg: dict[tuple[str, float, int], int] = {}
    for dp in dist.plantas:
        for u in dp.unidades:
            k = (u.tipo, u.area_util_unidad_m2, u.plazas)
            agreg[k] = agreg.get(k, 0) + u.cantidad
    unidades_planas = [Unidad(tipo=t, cantidad=c, area_util_unidad_m2=a, plazas=p)
                       for (t, a, p), c in agreg.items()]

    muros_perim_total = sum(
        p.area_construida_m2 - p.area_interior_bruta_m2 for p in env.plantas)
    muros_total = muros_perim_total + dist.superficie_muros_divisorios_total_m2

    pct_ocup = (env.huella_efectiva_m2 / parcela.superficie_m2 * 100
                if parcela.superficie_m2 else 0.0)
    pct_edif = (env.superficie_construida_total_m2 / techos.edificabilidad_max_m2t * 100
                if techos.edificabilidad_max_m2t else 0.0)

    return Resultado(
        uso=uso, categoria=categoria, n_plantas=n_plantas,
        n_unidades_total=dist.n_unidades_total,
        unidades=unidades_planas,
        superficie_parcela_m2=parcela.superficie_m2,
        huella_max_m2=techos.huella_max_m2,
        huella_efectiva_m2=env.huella_efectiva_m2,
        superficie_construida_total_m2=env.superficie_construida_total_m2,
        superficie_util_total_m2=dist.superficie_util_total_m2,
        superficie_circulacion_total_m2=dist.superficie_circulacion_total_m2,
        superficie_muros_total_m2=muros_total,
        superficie_patios_total_m2=env.superficie_patios_total_m2,
        n_patios=sum(len(p.patios) for p in env.plantas),
        edificabilidad_consumida_m2t_m2s=env.edificabilidad_consumida_m2t_m2s,
        edificabilidad_max_m2t_m2s=pgou.edificabilidad,
        pct_edificabilidad_usada=round(pct_edif, 1),
        pct_ocupacion=round(pct_ocup, 1),
        ingresos_eur=via.ingresos_eur,
        coste_construccion_eur=via.coste_construccion_eur,
        coste_total_eur=via.coste_total_eur,
        margen_eur=via.margen_eur,
        roi_pct=via.roi_pct,
        cumple_normativa=dist.cumple_minimos and not techos.alertas,
        alertas=techos.alertas + dist.alertas,
    )


def _candidatos(programa: ProgramaInversor, pgou: PGOU):
    """Espacio de búsqueda en función del programa del inversor."""
    if programa.uso not in pgou.usos_permitidos:
        usos = [programa.uso]   # no es permitido — devolvemos uno solo para alertar
    else:
        usos = [programa.uso]

    fracs = [1.0, 0.85, 0.70]

    for uso in usos:
        cat_fijada = programa.categoria
        categorias = [cat_fijada] if cat_fijada else CATALOGO_USOS[uso]["categorias"]
        n_objetivo = programa.n_plantas_objetivo
        plantas_range = ([n_objetivo] if n_objetivo
                         else range(1, pgou.n_plantas_max + 1))
        for cat, n_pl, fr in product(categorias, plantas_range, fracs):
            yield uso, cat, n_pl, fr


def optimizar(parcela: Parcela, pgou: PGOU, diseno: ParametrosDiseno,
              costes: Costes, programa: ProgramaInversor,
              objetivo: Objetivo = "margen") -> Resultado:
    """Devuelve el mejor candidato según `objetivo`. Lanza si ninguno es viable."""
    mejor: Resultado | None = None
    mejor_score = float("-inf")
    for uso, cat, n_pl, fr in _candidatos(programa, pgou):
        r = _evaluar_candidato(parcela, pgou, diseno, costes, programa,
                               uso, cat, n_pl, fr)
        if r is None:
            continue
        s = _score(r, objetivo)
        if s > mejor_score:
            mejor_score = s
            r.objetivo = objetivo
            r.score = round(s, 1)
            mejor = r

    if mejor is None:
        raise RuntimeError(
            "Ningún candidato es viable con los parámetros dados."
            " Revisa PGOU, retranqueos o programa.")
    return mejor
