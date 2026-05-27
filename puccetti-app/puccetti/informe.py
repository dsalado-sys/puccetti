"""Informe de prefactibilidad en PDF (§2.10 del PDF de requisitos).

Estructura mínima exigida:
- Ficha del activo (localización, referencia catastral, imagen de situación).
- Resumen de parámetros urbanísticos aplicables.
- Planimetría de la propuesta: planta por planta, con superficies.
- Perspectiva volumétrica simplificada del edificio (bloque de masas 3D).
- Tabla de superficies completa.
- Alertas y condicionantes relevantes detectados.
- Sección reservada para que los asociados financieros añadan la rentabilidad.

Se construye con reportlab embebiendo planos renderizados con matplotlib (PNG),
ya que no hay conversor SVG→PNG instalado.
"""
from __future__ import annotations
import io
import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import geopandas as gpd
from shapely.geometry import LineString, Polygon

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle,
    PageBreak, HRFlowable,
)

from .config import Parametros
from .macro_layout import EdificioPlurifamiliar, PlantaPlurifamiliar
from .interiores import distribuir_planta_interiores
from .serializacion import tabla_superficies_por_planta, tabla_unidades

# identidad visual Puccetti
NEGRO = colors.HexColor("#0A0A0A")
DORADO = colors.HexColor("#B8960C")
GRIS = colors.HexColor("#666666")
CAT = {'publica': '#F4C66B', 'privada': '#9DBDD9',
       'servicio': '#A8D5BA', 'circulacion': '#E4E4E4'}
PAL = ['#F4C66B', '#9DBDD9', '#A8D5BA', '#E8A6A1', '#C9B8E0', '#F0CDA0']


# ======================================================================
#  Planos (matplotlib → PNG)
# ======================================================================
def _png(fig, dpi: int = 130) -> tuple[io.BytesIO, float]:
    """Guarda la figura a PNG y devuelve (buffer, aspecto alto/ancho)."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    w, h = fig.get_size_inches()
    return buf, h / w


def _draw_comunes(ax, p: PlantaPlurifamiliar, lados):
    gpd.GeoSeries([p.footprint]).plot(ax=ax, facecolor="#FAF8F2", edgecolor="none")
    if not p.muros_perimetrales.is_empty:
        gpd.GeoSeries([p.muros_perimetrales]).plot(ax=ax, color="#2B2B2B")
    for pas in p.pasillos:
        gpd.GeoSeries([pas.geometry]).plot(ax=ax, color="#E4E4E4", edgecolor="#999", linewidth=0.5)


def _draw_patios_nucleo_fachada(ax, p: PlantaPlurifamiliar, lados):
    if not p.muros_divisorios.is_empty:
        gpd.GeoSeries([p.muros_divisorios]).plot(ax=ax, color="#2B2B2B")
    for pt in p.patios:
        gpd.GeoSeries([pt.geometry]).plot(ax=ax, facecolor="white", edgecolor="#5B86A8",
                                          hatch="///", linewidth=1.0)
        c = pt.geometry.representative_point()
        ax.annotate(f"patio\n{pt.area_m2:.0f} m²", (c.x, c.y), ha="center", va="center",
                    fontsize=6, color="#1f4d80")
    if p.nucleo is not None:
        gpd.GeoSeries([p.nucleo.geometry]).plot(ax=ax, color="#CBB68B", edgecolor="#8A7430")
        ax.add_patch(mpatches.Circle(p.nucleo.circulo_centro, p.nucleo.circulo_radio,
                                     fill=False, ec="#1E8449", ls="--", lw=1.2))
    for l in lados:
        seg = LineString([l.p1, l.p2])
        ax.plot(*seg.xy, color=("#B8960C" if l.tipo == "fachada" else "#0A0A0A"), lw=2.5)
    ax.set_aspect("equal"); ax.set_axis_off()


def plano_viviendas(p: PlantaPlurifamiliar, lados) -> tuple[io.BytesIO, float]:
    fig, ax = plt.subplots(figsize=(6.4, 6.4))
    _draw_comunes(ax, p, lados)
    for i, u in enumerate(p.unidades):
        gpd.GeoSeries([u.geometry]).plot(ax=ax, color=PAL[i % len(PAL)],
                                         edgecolor="#222", linewidth=0.5, alpha=0.85)
        c = u.geometry.representative_point()
        ax.annotate(f"{u.id}\n{u.area_util_m2:.0f} m²", (c.x, c.y), ha="center",
                    va="center", fontsize=7)
    _draw_patios_nucleo_fachada(ax, p, lados)
    return _png(fig)


def plano_interiores(p: PlantaPlurifamiliar, viviendas, lados) -> tuple[io.BytesIO, float]:
    fig, ax = plt.subplots(figsize=(6.4, 6.4))
    _draw_comunes(ax, p, lados)
    for vi in viviendas:
        for e in vi.estancias:
            gpd.GeoSeries([e.geometry]).plot(ax=ax, color=CAT.get(e.categoria, "#ccc"),
                                             edgecolor="#555", linewidth=0.4, alpha=0.85)
            if e.area_m2 >= 3:
                c = e.geometry.representative_point()
                ax.annotate(f"{e.nombre.replace('_',' ')}\n{e.area_m2:.0f}", (c.x, c.y),
                            ha="center", va="center", fontsize=5.5)
        if not vi.muros.is_empty:
            gpd.GeoSeries([vi.muros]).plot(ax=ax, color="#2B2B2B")
    for u in p.unidades:
        gpd.GeoSeries([u.geometry.boundary]).plot(ax=ax, color="#222", linewidth=1.4)
    _draw_patios_nucleo_fachada(ax, p, lados)
    return _png(fig)


def plano_fachadas(parc: Polygon, lados) -> tuple[io.BytesIO, float]:
    fig, ax = plt.subplots(figsize=(6.4, 6.4))
    gpd.GeoSeries([parc]).plot(ax=ax, facecolor="#f8f8f8", edgecolor="none")
    for i, l in enumerate(lados):
        seg = LineString([l.p1, l.p2])
        ax.plot(*seg.xy, color=("#B8960C" if l.tipo == "fachada" else "#0A0A0A"), lw=3)
        mx, my = (l.p1[0] + l.p2[0]) / 2, (l.p1[1] + l.p2[1]) / 2
        ax.annotate(str(i), (mx, my), ha="center", va="center", fontsize=6,
                    bbox=dict(boxstyle="circle,pad=0.15", fc="white", ec="#888", lw=0.5))
    ax.plot([], [], color="#B8960C", lw=3, label="fachada (huecos)")
    ax.plot([], [], color="#0A0A0A", lw=3, label="medianera (ciega)")
    ax.legend(loc="lower right", fontsize=7, framealpha=0.9)
    ax.set_aspect("equal"); ax.set_axis_off()
    return _png(fig)


def volumetria_3d(edif: EdificioPlurifamiliar, params: Parametros) -> tuple[io.BytesIO, float]:
    """Bloque de masas: extrusión de la huella por el nº de plantas edificables."""
    p0 = edif.plantas[0]
    ring = list(p0.footprint.exterior.coords)
    h = params.urbanismo.altura_planta
    n = len(edif.plantas)
    H = h * n

    fig = plt.figure(figsize=(6.4, 5.2))
    ax = fig.add_subplot(111, projection="3d")
    xs = [c[0] for c in ring]; ys = [c[1] for c in ring]
    base = [(x, y, 0.0) for x, y in ring]
    techo = [(x, y, H) for x, y in ring]
    caras = [base, techo]
    for i in range(len(ring) - 1):
        caras.append([base[i], base[i + 1], techo[i + 1], techo[i]])
    # forjados intermedios (líneas de planta)
    pc = Poly3DCollection(caras, facecolor="#D9C79A", edgecolor="#6E5B28",
                          linewidths=0.5, alpha=0.55)
    ax.add_collection3d(pc)
    for k in range(1, n):
        z = h * k
        ax.plot([c[0] for c in ring], [c[1] for c in ring], [z] * len(ring),
                color="#6E5B28", lw=0.4)
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    r = max(max(xs) - min(xs), max(ys) - min(ys)) / 1.8
    ax.set_xlim(cx - r, cx + r); ax.set_ylim(cy - r, cy + r); ax.set_zlim(0, max(H, 1) * 1.2)
    try:
        ax.set_box_aspect((1, 1, 0.6))
    except Exception:
        pass
    ax.view_init(elev=22, azim=-60)
    ax.set_axis_off()
    ax.set_title(f"{n} plantas · {H:.1f} m", fontsize=9)
    return _png(fig)


# ======================================================================
#  Documento PDF
# ======================================================================
def _img(flow_buf_aspect, ancho_mm: float):
    buf, aspect = flow_buf_aspect
    w = ancho_mm * mm
    return RLImage(buf, width=w, height=w * aspect)


def _tabla(df, font=7.5):
    data = [list(df.columns)] + df.astype(str).values.tolist()
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NEGRO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), font),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F4EC")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def generar_informe_pdf(
    edif: EdificioPlurifamiliar, params: Parametros, lados, parc: Polygon,
    etiqueta: str,
) -> bytes:
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], textColor=NEGRO, fontSize=18, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=DORADO, fontSize=12,
                        spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("body", parent=ss["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("small", parent=ss["BodyText"], fontSize=7.5, textColor=GRIS)

    cap = edif.capacidad
    hoy = datetime.date.today().isoformat()
    story = []

    # ---------- Ficha del activo ----------
    story.append(Paragraph("Estudio de prefactibilidad — Edificio plurifamiliar", h1))
    story.append(Paragraph(f"Puccetti · {hoy}", small))
    story.append(HRFlowable(width="100%", color=DORADO, thickness=1.5, spaceAfter=8))
    story.append(Paragraph("1 · Ficha del activo", h2))
    ficha = [
        ["Localización / referencia", etiqueta],
        ["Superficie de parcela", f"{parc.area:.1f} m²"],
        ["Fachadas / medianeras", f"{sum(1 for l in lados if l.tipo=='fachada')} / "
                                  f"{sum(1 for l in lados if l.tipo=='medianera')}"],
        ["Uso", "Vivienda (plurifamiliar)"],
        ["Viviendas propuestas", f"{edif.n_viviendas_total} "
                                 f"({edif.viv_por_planta_dispuestas}/planta × {len(edif.plantas)})"],
    ]
    story.append(_tabla(__import__("pandas").DataFrame(ficha, columns=["concepto", "valor"]), font=9))
    story.append(Spacer(1, 6))
    story.append(_img(plano_fachadas(parc, lados), ancho_mm=95))
    story.append(Paragraph("Situación: clasificación de lados (dorado = fachada, "
                           "negro = medianera).", small))

    # ---------- Parámetros urbanísticos ----------
    story.append(Paragraph("2 · Parámetros urbanísticos aplicados", h2))
    urb = params.urbanismo
    purb = [
        ["Edificabilidad", f"{urb.edificabilidad:.2f} m²t/m²s"],
        ["Ocupación máxima", f"{urb.ocupacion_maxima*100:.0f} %"],
        ["Nº máx. de plantas", str(urb.n_plantas_max)],
        ["Retranqueos (frontal/lateral/trasero)",
         f"{urb.retranqueo_frontal} / {urb.retranqueo_lateral} / {urb.retranqueo_trasero} m"],
        ["Techo máximo edificable", f"{cap.techo_max_m2:.0f} m²t"],
        ["Plantas edificables (factor limitante)",
         f"{cap.n_plantas_edificables}  ({cap.factor_limitante})"],
        ["Construida prevista", f"{cap.construida_prevista_m2:.0f} m²"],
    ]
    story.append(_tabla(__import__("pandas").DataFrame(purb, columns=["parámetro", "valor"]), font=8.5))

    # ---------- Volumetría 3D ----------
    story.append(Paragraph("3 · Volumetría simplificada (bloque de masas)", h2))
    story.append(_img(volumetria_3d(edif, params), ancho_mm=120))

    story.append(PageBreak())

    # ---------- Planimetría por planta ----------
    story.append(Paragraph("4 · Planimetría de la propuesta", h2))
    for p in edif.plantas:
        nombre = "Planta baja" if p.n == 0 else f"Planta {p.n}"
        story.append(Paragraph(f"<b>{nombre}</b> — {len(p.unidades)} viviendas · "
                               f"{p.tipologia} · útil {p.util_unidades_m2:.0f} m²", body))
        viv_int = distribuir_planta_interiores(p, lados, params)
        fila = Table([[_img(plano_viviendas(p, lados), ancho_mm=85),
                       _img(plano_interiores(p, viv_int, lados), ancho_mm=85)]],
                     colWidths=[88 * mm, 88 * mm])
        fila.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(fila)
        story.append(Paragraph("Izq.: distribución de viviendas. Der.: diseño interior "
                               "(salón y dormitorios a fachada; cocina y baños al interior; "
                               "pasillo ≥0,90 m). Verde = círculo libre Ø1,50 del vestíbulo.", small))
        story.append(Spacer(1, 6))

    story.append(PageBreak())

    # ---------- Tabla de superficies ----------
    story.append(Paragraph("5 · Tabla de superficies", h2))
    story.append(Paragraph("Por planta (construida vs útil)", body))
    story.append(_tabla(tabla_superficies_por_planta(edif), font=7.5))
    story.append(Spacer(1, 6))
    df_u = tabla_unidades(edif)
    if not df_u.empty:
        story.append(Paragraph("Viviendas", body))
        story.append(_tabla(df_u, font=7))
    construida = sum(p.construida_m2 for p in edif.plantas)
    util = sum(p.util_unidades_m2 for p in edif.plantas)
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"<b>Totales del edificio:</b> construida {construida:.0f} m² · "
        f"útil viviendas {util:.0f} m² · {edif.n_viviendas_total} viviendas · "
        f"edificabilidad usada {100*edif.edificabilidad_consumida/edif.edificabilidad_max:.0f} %"
        if edif.edificabilidad_max else "", body))

    # ---------- Alertas y condicionantes ----------
    story.append(Paragraph("6 · Alertas y condicionantes", h2))
    alertas = []
    if cap.n_plantas_edificables < cap.n_plantas_solicitadas:
        alertas.append(f"La edificabilidad limita la altura a {cap.n_plantas_edificables} "
                       f"plantas completas (solicitadas {cap.n_plantas_solicitadas}).")
    if edif.n_viviendas_total < cap.n_viviendas_objetivo:
        alertas.append(f"Se disponen {edif.n_viviendas_total} viviendas de las "
                       f"{cap.n_viviendas_objetivo} que permitiría la edificabilidad: la "
                       f"geometría y el acceso a fachada (Anexo II) lo limitan.")
    for p in edif.plantas:
        for inc in p.incidencias:
            alertas.append(inc)
    if not alertas:
        alertas.append("Sin incidencias: todas las viviendas cumplen acceso, "
                       "ventilación a fachada y superficies mínimas.")
    for a in alertas:
        story.append(Paragraph(f"• {a}", body))

    # ---------- Sección rentabilidad (reservada) ----------
    story.append(Paragraph("7 · Análisis de rentabilidad (a completar por el área financiera)", h2))
    story.append(Paragraph(
        "Sección reservada para que los asociados financieros incorporen el análisis de "
        "rentabilidad (precio de venta/renta por m², coste de construcción, margen).", small))
    rent = [["Concepto", "Valor"],
            ["Precio venta/renta (€/m²)", ""],
            ["Coste construcción (€/m²)", ""],
            ["Ingresos estimados (€)", ""],
            ["Coste total estimado (€)", ""],
            ["Margen bruto (€)", ""]]
    tr = Table(rent, colWidths=[90 * mm, 70 * mm], rowHeights=[8 * mm] * len(rent))
    tr.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEE8D8")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(tr)
    story.append(Spacer(1, 8))
    story.append(Paragraph("Informe preliminar generado automáticamente por Puccetti. "
                           "Los valores de diseño son una propuesta de prefactibilidad sujeta "
                           "a verificación técnica.", small))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="Informe Puccetti",
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm)
    doc.build(story)
    return buf.getvalue()
