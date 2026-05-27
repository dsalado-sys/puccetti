"""Render SVG de la planta tipo plurifamiliar (§2.5 — resultado esperado).

Dibuja: contorno de fachada vs medianera, muros perimetrales y divisorios,
patios interiores, pasillo comun, nucleo vertical (escalera + ascensor +
vestibulo con su circulo libre Ø1.50) y el perimetro etiquetado de cada
vivienda. Sin dependencias de JS: devuelve una cadena SVG autocontenida.
"""
from __future__ import annotations
from typing import Callable

from shapely.geometry import Polygon, LineString, MultiLineString

from .macro_layout import PlantaPlurifamiliar
from .parcelas import LadoParcela

# --- identidad visual Puccetti ---
NEGRO       = "#0A0A0A"
DORADO      = "#B8960C"
DORADO_CLAR = "#C9A84C"
BLANCO      = "#FFFFFF"

C_MURO      = "#2B2B2B"
C_MEDIANERA = "#0A0A0A"
C_FACHADA   = DORADO
C_PATIO     = "#DCEBF7"
C_PATIO_BRD = "#5B86A8"
C_PASILLO   = "#E4E4E4"
C_NUCLEO    = "#CBB68B"
C_NUCLEO_BRD = "#8A7430"
C_TEXTO     = "#111111"

# paleta de viviendas (se cicla)
PALETA_UNIDAD = ["#F4C66B", "#9DBDD9", "#A8D5BA", "#E8A6A1",
                 "#C9B8E0", "#F0CDA0", "#9FD3CB", "#D8C18C"]


def _build_transform(footprint: Polygon, width_px: float, margen_m: float):
    minx, miny, maxx, maxy = footprint.bounds
    W = (maxx - minx) + 2 * margen_m
    H = (maxy - miny) + 2 * margen_m
    scale = width_px / W
    height_px = H * scale
    ox, oy = minx - margen_m, miny - margen_m

    def T(x: float, y: float) -> tuple[float, float]:
        return ((x - ox) * scale, height_px - (y - oy) * scale)

    return T, scale, height_px


def _path_d(poly: Polygon, T: Callable) -> str:
    if poly is None or poly.is_empty:
        return ""
    parts = []
    rings = [poly.exterior] + list(poly.interiors)
    for ring in rings:
        pts = list(ring.coords)
        if not pts:
            continue
        d = "M " + " L ".join(f"{T(x, y)[0]:.2f},{T(x, y)[1]:.2f}" for x, y in pts) + " Z"
        parts.append(d)
    return " ".join(parts)


def _line_svg(line, T, color, w, dash=""):
    geoms = line.geoms if isinstance(line, MultiLineString) else [line]
    out = []
    da = f' stroke-dasharray="{dash}"' if dash else ""
    for g in geoms:
        pts = list(g.coords)
        if len(pts) < 2:
            continue
        d = "M " + " L ".join(f"{T(x, y)[0]:.2f},{T(x, y)[1]:.2f}" for x, y in pts)
        out.append(f'<path d="{d}" stroke="{color}" stroke-width="{w}" '
                   f'fill="none" stroke-linecap="round"{da}/>')
    return "\n".join(out)


def render_planta_svg(
    pl: PlantaPlurifamiliar,
    lados: list[LadoParcela] | None = None,
    width_px: int = 860,
    margen_m: float = 1.6,
    titulo: str = "",
) -> str:
    T, scale, height_px = _build_transform(pl.footprint, width_px, margen_m)
    el: list[str] = []

    # 0) huella (relleno claro) + muros perimetrales (relleno oscuro)
    el.append(f'<path d="{_path_d(pl.footprint, T)}" fill="#FAF8F2" '
              f'stroke="none"/>')
    if not pl.muros_perimetrales.is_empty:
        muros = (pl.muros_perimetrales.geoms
                 if pl.muros_perimetrales.geom_type == "MultiPolygon"
                 else [pl.muros_perimetrales])
        for m in muros:
            el.append(f'<path d="{_path_d(m, T)}" fill="{C_MURO}" '
                      f'fill-rule="evenodd" stroke="none"/>')

    # 1) pasillo comun
    for p in pl.pasillos:
        el.append(f'<path d="{_path_d(p.geometry, T)}" fill="{C_PASILLO}" '
                  f'stroke="#B8B8B8" stroke-width="0.6"/>')

    # 2) viviendas
    for i, u in enumerate(pl.unidades):
        color = PALETA_UNIDAD[i % len(PALETA_UNIDAD)]
        ok = u.cumple_min and u.ventila_ok and u.acceso_pasillo
        stroke = "#222" if ok else "#C0392B"
        el.append(f'<path d="{_path_d(u.geometry, T)}" fill="{color}" '
                  f'fill-opacity="0.82" fill-rule="evenodd" '
                  f'stroke="{stroke}" stroke-width="{1.4 if not ok else 0.8}"/>')

    # 3) patios interiores: VACIO recortado en la planta (se pinta antes de los
    #    muros para que el anillo de muro lo enmarque, no como pegatina encima)
    if pl.patios:
        el.append('<defs><pattern id="hatch" width="6" height="6" '
                  'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
                  f'<line x1="0" y1="0" x2="0" y2="6" stroke="{C_PATIO_BRD}" '
                  'stroke-width="1"/></pattern></defs>')
        for p in pl.patios:
            d = _path_d(p.geometry, T)
            # fondo blanco (vacio) + trama de patio, sin tapar nada por encima
            el.append(f'<path d="{d}" fill="{BLANCO}" stroke="none"/>')
            el.append(f'<path d="{d}" fill="{C_PATIO}" fill-opacity="0.65" '
                      f'stroke="none"/>')
            el.append(f'<path d="{d}" fill="url(#hatch)" stroke="{C_PATIO_BRD}" '
                      f'stroke-width="1.0"/>')

    # 4) muros divisorios (0.20) — incluye el anillo que cierra el patio
    if not pl.muros_divisorios.is_empty:
        divs = (pl.muros_divisorios.geoms
                if pl.muros_divisorios.geom_type == "MultiPolygon"
                else [pl.muros_divisorios])
        for m in divs:
            el.append(f'<path d="{_path_d(m, T)}" fill="{C_MURO}" '
                      f'fill-rule="evenodd" stroke="none"/>')

    # 5) nucleo vertical
    nuc = pl.nucleo
    if nuc is not None:
        el.append(f'<path d="{_path_d(nuc.geometry, T)}" fill="{C_NUCLEO}" '
                  f'stroke="{C_NUCLEO_BRD}" stroke-width="1.2"/>')
        # escalera: peldanos
        if not nuc.escalera.is_empty:
            el.append(f'<path d="{_path_d(nuc.escalera, T)}" fill="none" '
                      f'stroke="{C_NUCLEO_BRD}" stroke-width="0.8"/>')
            exb = nuc.escalera.bounds
            x0, y0, x1, y1 = exb
            n_p = 8
            for k in range(1, n_p):
                yy = y0 + (y1 - y0) * k / n_p
                el.append(_line_svg(LineString([(x0, yy), (x1, yy)]), T,
                                    C_NUCLEO_BRD, 0.5))
        # ascensor: recuadro con aspa
        if not nuc.ascensor.is_empty:
            ab = nuc.ascensor.bounds
            el.append(f'<path d="{_path_d(nuc.ascensor, T)}" fill="#EFE6CF" '
                      f'stroke="{C_NUCLEO_BRD}" stroke-width="0.8"/>')
            el.append(_line_svg(LineString([(ab[0], ab[1]), (ab[2], ab[3])]), T,
                                C_NUCLEO_BRD, 0.5))
            el.append(_line_svg(LineString([(ab[0], ab[3]), (ab[2], ab[1])]), T,
                                C_NUCLEO_BRD, 0.5))
        # circulo libre Ø del vestibulo
        cx, cy = T(*nuc.circulo_centro)
        r_px = nuc.circulo_radio * scale
        c_col = "#1E8449" if nuc.circulo_ok else "#C0392B"
        el.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r_px:.2f}" '
                  f'fill="none" stroke="{c_col}" stroke-width="1.4" '
                  f'stroke-dasharray="4 3"/>')

    # 6) contorno fachada / medianera (sobre lados clasificados, mundo)
    if lados:
        for l in lados:
            seg = LineString([l.p1, l.p2])
            if l.tipo == "fachada":
                el.append(_line_svg(seg, T, C_FACHADA, 4.0))
            else:
                el.append(_line_svg(seg, T, C_MEDIANERA, 4.0))
    else:
        el.append(f'<path d="{_path_d(pl.footprint, T)}" fill="none" '
                  f'stroke="{NEGRO}" stroke-width="2"/>')

    # 7) etiquetas de viviendas
    for i, u in enumerate(pl.unidades):
        c = u.geometry.representative_point()
        tx, ty = T(c.x, c.y)
        flag = "" if (u.cumple_min and u.ventila_ok) else "  ⚠"
        el.append(
            f'<text x="{tx:.1f}" y="{ty - 4:.1f}" text-anchor="middle" '
            f'font-family="Inter,Segoe UI,sans-serif" font-size="12" '
            f'font-weight="600" fill="{C_TEXTO}">{u.id}{flag}</text>')
        el.append(
            f'<text x="{tx:.1f}" y="{ty + 11:.1f}" text-anchor="middle" '
            f'font-family="Inter,Segoe UI,sans-serif" font-size="10.5" '
            f'fill="#444">{u.area_util_m2:.1f} m² · {u.ventilacion_tipo}</text>')

    # patio labels
    for p in pl.patios:
        c = p.geometry.representative_point()
        tx, ty = T(c.x, c.y)
        el.append(
            f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle" '
            f'font-family="Inter,Segoe UI,sans-serif" font-size="10" '
            f'fill="{C_PATIO_BRD}">patio {p.area_m2:.0f} m²</text>')

    # nucleo label
    if nuc is not None:
        c = nuc.vestibulo.representative_point()
        tx, ty = T(c.x, c.y)
        el.append(
            f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle" '
            f'font-family="Inter,Segoe UI,sans-serif" font-size="9.5" '
            f'fill="#5A4B1E">núcleo</text>')

    # titulo
    header = ""
    if titulo:
        header = (f'<text x="10" y="20" font-family="Inter,Segoe UI,sans-serif" '
                  f'font-size="14" font-weight="700" fill="{NEGRO}">{titulo}</text>')
        height_px += 26
        el = [f'<g transform="translate(0,26)">'] + el + ['</g>']

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px}" '
        f'height="{height_px:.0f}" viewBox="0 0 {width_px} {height_px:.0f}">'
        f'<rect width="100%" height="100%" fill="{BLANCO}"/>'
        f'{header}{"".join(el)}</svg>'
    )
    return svg


# color por categoría de estancia (interiores)
CAT_COLOR = {
    'publica':     '#F4C66B',
    'privada':     '#9DBDD9',
    'servicio':    '#A8D5BA',
    'circulacion': '#E4E4E4',
}


def render_planta_interiores_svg(
    pl: PlantaPlurifamiliar,
    viviendas,                       # list[ViviendaInterior]
    lados: list[LadoParcela] | None = None,
    width_px: int = 860,
    margen_m: float = 1.6,
    titulo: str = "",
) -> str:
    """Igual que render_planta_svg pero, en vez de pintar cada vivienda como un
    bloque, dibuja sus estancias interiores (Anexo II) coloreadas por categoría."""
    T, scale, height_px = _build_transform(pl.footprint, width_px, margen_m)
    el: list[str] = []

    el.append(f'<path d="{_path_d(pl.footprint, T)}" fill="#FAF8F2" stroke="none"/>')
    if not pl.muros_perimetrales.is_empty:
        muros = (pl.muros_perimetrales.geoms
                 if pl.muros_perimetrales.geom_type == "MultiPolygon"
                 else [pl.muros_perimetrales])
        for m in muros:
            el.append(f'<path d="{_path_d(m, T)}" fill="{C_MURO}" '
                      f'fill-rule="evenodd" stroke="none"/>')

    # pasillo común
    for p in pl.pasillos:
        el.append(f'<path d="{_path_d(p.geometry, T)}" fill="{C_PASILLO}" '
                  f'stroke="#B8B8B8" stroke-width="0.6"/>')

    # estancias interiores de cada vivienda
    for vi in viviendas:
        for e in vi.estancias:
            if e.geometry.is_empty:
                continue
            col = CAT_COLOR.get(e.categoria, '#cccccc')
            el.append(f'<path d="{_path_d(e.geometry, T)}" fill="{col}" '
                      f'fill-opacity="0.85" fill-rule="evenodd" '
                      f'stroke="#555" stroke-width="0.4"/>')
        # tabiquería interior
        if getattr(vi, 'muros', None) is not None and not vi.muros.is_empty:
            ms = (vi.muros.geoms if vi.muros.geom_type == "MultiPolygon" else [vi.muros])
            for m in ms:
                el.append(f'<path d="{_path_d(m, T)}" fill="{C_MURO}" '
                          f'fill-rule="evenodd" stroke="none"/>')

    # separación entre viviendas (perímetro de cada unidad, resaltado)
    for u in pl.unidades:
        el.append(f'<path d="{_path_d(u.geometry, T)}" fill="none" '
                  f'stroke="#222" stroke-width="1.6"/>')

    # patios como vacío
    if pl.patios:
        el.append('<defs><pattern id="hatch2" width="6" height="6" '
                  'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
                  f'<line x1="0" y1="0" x2="0" y2="6" stroke="{C_PATIO_BRD}" '
                  'stroke-width="1"/></pattern></defs>')
        for p in pl.patios:
            d = _path_d(p.geometry, T)
            el.append(f'<path d="{d}" fill="{BLANCO}" stroke="none"/>')
            el.append(f'<path d="{d}" fill="url(#hatch2)" stroke="{C_PATIO_BRD}" '
                      f'stroke-width="1.0"/>')

    # núcleo
    nuc = pl.nucleo
    if nuc is not None:
        el.append(f'<path d="{_path_d(nuc.geometry, T)}" fill="{C_NUCLEO}" '
                  f'stroke="{C_NUCLEO_BRD}" stroke-width="1.2"/>')
        cx, cy = T(*nuc.circulo_centro)
        c_col = "#1E8449" if nuc.circulo_ok else "#C0392B"
        el.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{nuc.circulo_radio*scale:.2f}" '
                  f'fill="none" stroke="{c_col}" stroke-width="1.4" stroke-dasharray="4 3"/>')

    # fachada / medianera
    if lados:
        for l in lados:
            seg = LineString([l.p1, l.p2])
            el.append(_line_svg(seg, T, C_FACHADA if l.tipo == "fachada" else C_MEDIANERA, 4.0))

    # etiquetas de estancias
    for vi in viviendas:
        for e in vi.estancias:
            if e.geometry.is_empty or e.area_m2 < 2.0:
                continue
            c = e.geometry.representative_point()
            tx, ty = T(c.x, c.y)
            nombre = e.nombre.replace('_', ' ')
            el.append(
                f'<text x="{tx:.1f}" y="{ty-2:.1f}" text-anchor="middle" '
                f'font-family="Inter,Segoe UI,sans-serif" font-size="8.5" '
                f'fill="{C_TEXTO}">{nombre}</text>')
            el.append(
                f'<text x="{tx:.1f}" y="{ty+8:.1f}" text-anchor="middle" '
                f'font-family="Inter,Segoe UI,sans-serif" font-size="7.5" '
                f'fill="#555">{e.area_m2:.1f} m²</text>')
    # id de vivienda en una esquina
    for u in pl.unidades:
        b = u.geometry.bounds
        tx, ty = T(b[0], b[3])
        el.append(f'<text x="{tx+3:.1f}" y="{ty+11:.1f}" '
                  f'font-family="Inter,Segoe UI,sans-serif" font-size="9.5" '
                  f'font-weight="700" fill="#7A5C00">{u.id}</text>')

    header = ""
    if titulo:
        header = (f'<text x="10" y="20" font-family="Inter,Segoe UI,sans-serif" '
                  f'font-size="14" font-weight="700" fill="{NEGRO}">{titulo}</text>')
        height_px += 26
        el = ['<g transform="translate(0,26)">'] + el + ['</g>']

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px}" '
        f'height="{height_px:.0f}" viewBox="0 0 {width_px} {height_px:.0f}">'
        f'<rect width="100%" height="100%" fill="{BLANCO}"/>'
        f'{header}{"".join(el)}</svg>'
    )


def leyenda_interiores_svg(width_px: int = 860) -> str:
    items = [(CAT_COLOR['publica'], 'salón / cocina'),
             (CAT_COLOR['privada'], 'dormitorios'),
             (CAT_COLOR['servicio'], 'baños / aseos'),
             (CAT_COLOR['circulacion'], 'vestíbulo / pasillo'),
             (C_PATIO, 'patio'), (C_NUCLEO, 'núcleo')]
    x = 10
    boxes = []
    for color, label in items:
        boxes.append(
            f'<rect x="{x}" y="8" width="14" height="14" fill="{color}" '
            f'stroke="#888" stroke-width="0.5"/>'
            f'<text x="{x+19}" y="19" font-family="Inter,Segoe UI,sans-serif" '
            f'font-size="11" fill="#222">{label}</text>')
        x += 24 + len(label) * 6.6
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{max(width_px,int(x))}" '
            f'height="30"><rect width="100%" height="100%" fill="{BLANCO}"/>'
            f'{"".join(boxes)}</svg>')


def leyenda_svg(width_px: int = 860) -> str:
    """Banda de leyenda independiente (para informe / debug)."""
    items = [
        (C_FACHADA, "fachada (hueco permitido)"),
        (C_MEDIANERA, "medianera (ciega)"),
        (C_MURO, "muros"),
        (C_PASILLO, "pasillo común ≥1.20 m"),
        (C_NUCLEO, "núcleo (escalera+ascensor)"),
        (C_PATIO, "patio interior"),
        (PALETA_UNIDAD[0], "vivienda"),
    ]
    x = 10
    boxes = []
    for color, label in items:
        boxes.append(
            f'<rect x="{x}" y="8" width="14" height="14" fill="{color}" '
            f'stroke="#888" stroke-width="0.5"/>'
            f'<text x="{x + 19}" y="19" font-family="Inter,Segoe UI,sans-serif" '
            f'font-size="11" fill="#222">{label}</text>')
        x += 24 + len(label) * 6.6
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{max(width_px, int(x))}" '
            f'height="30"><rect width="100%" height="100%" fill="{BLANCO}"/>'
            f'{"".join(boxes)}</svg>')
