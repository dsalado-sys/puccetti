"""Renderizado de plantas y parcela con clasificacion fachadas/medianeras."""
from __future__ import annotations
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import geopandas as gpd

from shapely.geometry import LineString, Polygon

from .parcelas import LadoParcela
from .distributor import PlantaDistribuida
from .envolvente import Envolvente, Planta


COLOR = {
    'publica':     '#F4C66B',
    'privada':     '#9DBDD9',
    'servicio':    '#A8D5BA',
    'circulacion': '#D9D9D9',
}
COLOR_MURO = '#3A2F1B'
COLOR_PATIO = '#E6F2FF'
COLOR_FACHADA = '#1f77b4'
COLOR_MEDIANERA = '#d62728'


def render_parcela_lados(parcela: Polygon, lados: list[LadoParcela], ax=None):
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 8))
    gpd.GeoSeries([parcela]).plot(ax=ax, facecolor='#f8f8f8', edgecolor='none')
    for l in lados:
        color = COLOR_FACHADA if l.tipo == 'fachada' else COLOR_MEDIANERA
        seg = LineString([l.p1, l.p2])
        gpd.GeoSeries([seg]).plot(ax=ax, color=color, linewidth=3)
    legend = [
        mpatches.Patch(color=COLOR_FACHADA, label='fachada (vía pública)'),
        mpatches.Patch(color=COLOR_MEDIANERA, label='medianera (linda)'),
    ]
    ax.legend(handles=legend, loc='lower right', framealpha=0.9)
    ax.set_aspect('equal'); ax.set_axis_off()
    return ax


def render_planta_distribuida(
    parcela: Polygon,
    planta_env: Planta,
    planta_dist: PlantaDistribuida,
    titulo: str = '',
    ax=None,
):
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 9))

    gpd.GeoSeries([parcela]).plot(ax=ax, facecolor='none',
                                  edgecolor='#0A0A0A', linewidth=2)
    for ec in planta_dist.estancias:
        if ec.geometry.is_empty:
            continue
        gpd.GeoSeries([ec.geometry]).plot(
            ax=ax, color=COLOR.get(ec.categoria, '#cccccc'),
            edgecolor='#222', linewidth=0.4)
    # patio: VACIO recortado, antes de los muros para que el anillo lo enmarque
    patios_geom = ([p for p in planta_dist.patios]
                   if getattr(planta_dist, 'patios', None)
                   else [p.geometry for p in planta_env.patios])
    for g in patios_geom:
        if g.is_empty:
            continue
        gpd.GeoSeries([g]).plot(ax=ax, color=COLOR_PATIO, edgecolor='#5B86A8',
                                linewidth=1.0, hatch='///')
    for g in (planta_dist.muros_perimetrales, planta_dist.muros_divisorios):
        if not g.is_empty:
            gpd.GeoSeries([g]).plot(ax=ax, color=COLOR_MURO)

    # Etiquetas
    for ec in planta_dist.estancias:
        if ec.geometry.is_empty:
            continue
        c = ec.geometry.representative_point()
        flag = '' if ec.area_real_m2 + 1e-3 >= ec.area_min_m2 else ' !'
        ax.annotate(f"{ec.nombre}\n{ec.area_real_m2:.1f} m²{flag}",
                    (c.x, c.y), ha='center', va='center',
                    fontsize=8.5, color='#111')
    for g in patios_geom:
        if g.is_empty:
            continue
        c = g.representative_point()
        ax.annotate(f"patio\n{g.area:.1f} m²",
                    (c.x, c.y), ha='center', va='center',
                    fontsize=8.5, color='#1f4d80')

    parches = [mpatches.Patch(color=v, label=k) for k, v in COLOR.items()]
    parches += [
        mpatches.Patch(color=COLOR_MURO, label='muros'),
        mpatches.Patch(color=COLOR_PATIO, label='patio interior'),
    ]
    ax.legend(handles=parches, loc='lower right', framealpha=0.9, fontsize=8)
    if titulo:
        ax.set_title(titulo, fontsize=11)
    ax.set_aspect('equal'); ax.set_axis_off()
    return ax
