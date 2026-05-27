"""Distribuidor de estancias (§2.5).

Modelo original (sin ML, sin pasillos ramificados):

- Frame alineado al lado largo del footprint
- Vestibulo pegado a la fachada (extremo X minimo del frame)
- Zona publica (salon + cocina) en una franja tras el vestibulo, ocupando toda H
- Pasillo central horizontal UNICO atravesando la zona privada
- Zona privada: dormitorios arriba del pasillo + banos abajo, distribuidos con
  Squarified Treemap (aspect ratio cercano a 1)
- Fitness multicriterio (Anexo I.5 + A2.2): genera N candidatos con distintos
  seeds y devuelve el mejor por score.
"""
from __future__ import annotations
import math, random
from dataclasses import dataclass, field
from typing import Optional

from shapely.geometry import Polygon, box, MultiPolygon, Point, MultiPoint, LineString
from shapely.ops import unary_union
from shapely.affinity import rotate, translate

from .config import Parametros
from .envolvente import Planta
from .programa import Estancia, programa_vivienda
from .parcelas import LadoParcela
from .adyacencias import (
    grafo_adyacencias_fisicas, validar_a22, validar_conectividad,
    IncidenciaAdyacencia,
)
from .treemap import subdividir_squarified, TreemapItem
from .fitness import evaluar, Score


@dataclass
class EstanciaColocada:
    nombre: str
    categoria: str
    geometry: Polygon
    area_target_m2: float
    area_min_m2: float
    area_real_m2: float


@dataclass
class PlantaDistribuida:
    n: int
    estancias: list[EstanciaColocada]
    muros_perimetrales: Polygon
    muros_divisorios: Polygon
    incidencias_a22: list[IncidenciaAdyacencia] = field(default_factory=list)
    seed: int = 0
    util_total_m2: float = 0.0
    construida_m2: float = 0.0
    score: Optional[Score] = None
    score_alternativas: list[float] = field(default_factory=list)
    patios: list[Polygon] = field(default_factory=list)   # patio(s) integrados


def _frame_alineado(geom: Polygon) -> tuple[float, tuple[float, float]]:
    mrr = geom.minimum_rotated_rectangle
    coords = list(mrr.exterior.coords)[:-1]
    edges = [(coords[i], coords[(i + 1) % 4]) for i in range(4)]
    elens = [math.dist(a, b) for a, b in edges]
    li = max(range(4), key=lambda i: elens[i])
    a, b = edges[li]
    ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    return ang, (mrr.centroid.x, mrr.centroid.y)


def _fachada_x_minus(int_a: Polygon, lados: list[LadoParcela], al_func) -> bool:
    """True si la fachada principal cae en x = mnx del frame alineado."""
    fach = [l for l in lados if l.tipo == 'fachada']
    if not fach:
        return True
    fach = sorted(fach, key=lambda l: l.longitud_m, reverse=True)
    mid = Point((fach[0].p1[0] + fach[0].p2[0]) / 2,
                (fach[0].p1[1] + fach[0].p2[1]) / 2)
    pa = al_func(mid)
    minx, _, maxx, _ = int_a.bounds
    return abs(pa.x - minx) <= abs(pa.x - maxx)


def _generar_candidato(
    planta: Planta,
    lados: list[LadoParcela],
    params: Parametros,
    seed: int,
) -> PlantaDistribuida:
    rng = random.Random(seed)
    espesor_div = params.diseno.espesor_tabiqueria
    pasillo_w = params.diseno.ancho_min_pasillo_vivienda

    footprint = planta.footprint
    # interior util COMPLETO (huella - muro de fachada); el patio lo coloca y
    # recorta el propio distribuidor, integrado con el layout (no la envolvente).
    interior = footprint.buffer(-params.diseno.espesor_muro_fachada)
    if isinstance(interior, MultiPolygon) and not interior.is_empty:
        interior = max(interior.geoms, key=lambda g: g.area)
    if interior.is_empty:
        interior = planta.interior
    necesita_patio = len(planta.patios) > 0
    angulo, (cx, cy) = _frame_alineado(footprint)

    def al(g):  return rotate(translate(g, xoff=-cx, yoff=-cy), -angulo, origin=(0, 0))
    def mu(g):  return translate(rotate(g, angulo, origin=(0, 0)), xoff=cx, yoff=cy)

    int_a = al(interior)
    fp_a = al(footprint)
    mnx, mny, mxx, mxy = int_a.bounds
    W, H = mxx - mnx, mxy - mny

    # Si la fachada esta en el otro extremo, volteamos para que la entrada quede
    # siempre en x = mnx (asi el resto del algoritmo es uniforme).
    fachada_izq = _fachada_x_minus(int_a, lados, al)
    if not fachada_izq:
        int_a = rotate(int_a, 180, origin=(0, 0))
        fp_a  = rotate(fp_a,  180, origin=(0, 0))
        angulo_back = angulo + 180
        def mu(g, _a=angulo_back):
            return translate(rotate(g, _a, origin=(0, 0)), xoff=cx, yoff=cy)
        mnx, mny, mxx, mxy = int_a.bounds

    # Programa segun n_dorms y superficie util disponible
    util_disp = int_a.area * 0.85
    prog = programa_vivienda(
        n_dorms=params.programa.n_dormitorios,
        util_disponible=util_disp,
        salon_cocina_open=params.programa.salon_cocina_open,
    )
    publicas = [e for e in prog if e.categoria == 'publica']
    privadas = [e for e in prog if e.categoria in ('privada', 'servicio')]
    rng.shuffle(privadas)   # variabilidad de orden lateral

    estancias_colocadas: list[EstanciaColocada] = []

    # 1) Vestibulo pegado a la fachada (extremo X minimo)
    ANCHO_VEST = max(params.diseno.diametro_min_vestibulo, 1.4)
    vest_geom = box(mnx, mny, mnx + ANCHO_VEST, mxy).intersection(int_a)
    if not vest_geom.is_empty:
        estancias_colocadas.append(EstanciaColocada(
            'vestibulo', 'circulacion', vest_geom,
            ANCHO_VEST * H, 1.5, vest_geom.area,
        ))

    # 2) Zona publica (salon + cocina): franja vertical tras el vestibulo,
    #    ocupa toda H. Squarified Treemap si son 2 estancias (salon y cocina);
    #    un solo bloque si es salon-cocina integrado.
    pub_target = sum(e.area_target_m2 for e in publicas)
    pub_w = max(3.0, pub_target / H)
    pub_w = min(pub_w, W * 0.50)
    x_pub0 = mnx + ANCHO_VEST
    x_pub1 = x_pub0 + pub_w
    contenedor_pub = box(x_pub0, mny, x_pub1, mxy).intersection(int_a)
    if not contenedor_pub.is_empty:
        if len(publicas) == 1:
            e = publicas[0]
            estancias_colocadas.append(EstanciaColocada(
                e.nombre, e.categoria, contenedor_pub,
                e.area_target_m2, e.area_min_m2, contenedor_pub.area,
            ))
        else:
            items = [TreemapItem(e.nombre, e.area_target_m2,
                                 {'cat': e.categoria, 'min': e.area_min_m2})
                     for e in publicas]
            for e, g in zip(publicas, [subdividir_squarified(contenedor_pub, items).get(e.nombre) for e in publicas]):
                if g and not g.is_empty:
                    estancias_colocadas.append(EstanciaColocada(
                        e.nombre, e.categoria, g,
                        e.area_target_m2, e.area_min_m2, g.area,
                    ))

    # 3) Zona privada: pasillo unico recto + dorms arriba + banos abajo (Squarified)
    x_priv0 = x_pub1
    if x_priv0 < mxx - 1.0:
        pas_y0 = -pasillo_w / 2
        pas_y1 = +pasillo_w / 2
        top_y0, top_y1 = pas_y1, mxy
        bot_y0, bot_y1 = mny, pas_y0
        x_priv_max = mxx

        dorms = [e for e in privadas if e.categoria == 'privada']
        banos = [e for e in privadas if e.categoria == 'servicio']

        contenedor_dorms = box(x_priv0, top_y0, x_priv_max, top_y1).intersection(int_a)
        contenedor_banos = box(x_priv0, bot_y0, x_priv_max, bot_y1).intersection(int_a)

        # Pasillo unico: rectangulo horizontal centrado en y=0, atraviesa toda la zona privada
        pas_geom = box(x_priv0, pas_y0, x_priv_max, pas_y1).intersection(int_a)
        if not pas_geom.is_empty:
            estancias_colocadas.append(EstanciaColocada(
                'pasillo', 'circulacion', pas_geom,
                pas_geom.area, pasillo_w * 1.5, pas_geom.area,
            ))

        # Dorms: Squarified Treemap dentro de contenedor_dorms
        if dorms and not contenedor_dorms.is_empty:
            items = [TreemapItem(e.nombre, e.area_target_m2,
                                 {'cat': e.categoria, 'min': e.area_min_m2})
                     for e in dorms]
            subdiv = subdividir_squarified(contenedor_dorms, items)
            for e in dorms:
                g = subdiv.get(e.nombre)
                if g and not g.is_empty:
                    estancias_colocadas.append(EstanciaColocada(
                        e.nombre, e.categoria, g,
                        e.area_target_m2, e.area_min_m2, g.area,
                    ))

        # Banos: Squarified Treemap dentro de contenedor_banos
        if banos and not contenedor_banos.is_empty:
            items = [TreemapItem(e.nombre, e.area_target_m2,
                                 {'cat': e.categoria, 'min': e.area_min_m2})
                     for e in banos]
            subdiv = subdividir_squarified(contenedor_banos, items)
            for e in banos:
                g = subdiv.get(e.nombre)
                if g and not g.is_empty:
                    estancias_colocadas.append(EstanciaColocada(
                        e.nombre, e.categoria, g,
                        e.area_target_m2, e.area_min_m2, g.area,
                    ))

    # --- patio interior integrado: vacio pegado al pasillo (y=0), centrado en la
    #     zona privada; recortado de las estancias. Solo si la envolvente lo exige. ---
    patios_aligned: list[Polygon] = []
    if necesita_patio:
        luz = params.diseno.luz_recta_patio_min
        Lp = max(luz, params.diseno.area_patio_min / luz)
        px = min(max((x_pub1 + mxx) / 2.0, x_pub1 + luz), mxx - luz)
        for (yy0, yy1) in ((pasillo_w / 2, pasillo_w / 2 + Lp),
                           (-pasillo_w / 2 - Lp, -pasillo_w / 2)):
            cand = box(px - luz / 2, yy0, px + luz / 2, yy1).intersection(int_a)
            if isinstance(cand, MultiPolygon) and not cand.is_empty:
                cand = max(cand.geoms, key=lambda g: g.area)
            if not cand.is_empty and cand.area >= 0.6 * params.diseno.area_patio_min:
                patios_aligned = [cand]
                for ec in estancias_colocadas:
                    try:
                        ec.geometry = ec.geometry.difference(cand)
                    except Exception:
                        pass
                break

    # Rotar todo al frame del mundo
    for ec in estancias_colocadas:
        ec.geometry = mu(ec.geometry)
    patios_world = [mu(p) for p in patios_aligned]

    # Muros divisorios (espacio entre estancias)
    all_geoms = [ec.geometry for ec in estancias_colocadas if not ec.geometry.is_empty]
    if all_geoms:
        bordes = unary_union([g.boundary for g in all_geoms])
        muros_div = bordes.buffer(espesor_div / 2).intersection(interior)
        for ec in estancias_colocadas:
            try:
                ec.geometry = ec.geometry.difference(muros_div)
            except Exception:
                pass
            ec.area_real_m2 = ec.geometry.area
    else:
        muros_div = Polygon()

    # anillo de muro (0.25) que cierra el patio -> lee como vacio enclaustrado
    if patios_world:
        anillo = unary_union([p.boundary for p in patios_world]).buffer(
            params.diseno.espesor_muro_fachada / 2).intersection(interior)
        muros_div = unary_union([muros_div, anillo]) if not muros_div.is_empty else anillo
        pu = unary_union(patios_world)
        for ec in estancias_colocadas:
            try:
                ec.geometry = ec.geometry.difference(pu)
            except Exception:
                pass
            ec.area_real_m2 = ec.geometry.area

    muros_perim = footprint.difference(interior)

    # Validacion A2.2
    geom_map = {ec.nombre: ec.geometry for ec in estancias_colocadas
                if not ec.geometry.is_empty}
    g_fis = grafo_adyacencias_fisicas(
        geom_map, buffer_muro=espesor_div + 0.05, min_overlap_m=0.40,
    )
    incidencias = validar_a22(g_fis) + validar_conectividad(g_fis)

    util_total = sum(
        ec.area_real_m2 for ec in estancias_colocadas
        if ec.categoria in ('publica', 'privada', 'servicio')
    )
    return PlantaDistribuida(
        n=planta.n,
        estancias=estancias_colocadas,
        muros_perimetrales=muros_perim,
        muros_divisorios=muros_div,
        incidencias_a22=incidencias,
        seed=seed,
        util_total_m2=util_total,
        construida_m2=footprint.area,
        patios=patios_world,
    )


def distribuir_planta(
    planta: Planta,
    lados: list[LadoParcela],
    params: Parametros,
    seed: int | None = None,
    n_candidatos: int = 8,
) -> PlantaDistribuida:
    """Genera N candidatos con seeds distintos y devuelve el mejor por fitness."""
    base_seed = seed if seed is not None else random.randint(0, 10**6)
    candidatos: list[tuple[float, PlantaDistribuida]] = []
    for k in range(n_candidatos):
        sd = base_seed + k * 1009
        cand = _generar_candidato(planta, lados, params, sd)
        score = evaluar(cand.estancias, planta.interior, lados)
        cand.score = score
        candidatos.append((score.total, cand))
    candidatos.sort(key=lambda t: t[0], reverse=True)
    mejor_score, mejor = candidatos[0]
    mejor.score_alternativas = [s for s, _ in candidatos]
    return mejor
