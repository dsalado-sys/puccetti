"""Exportadores: PDF (ReportLab) y GeoJSON."""
from __future__ import annotations

import io
import json

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .localizar import Activo, simplificar_contorno


NEGRO = colors.HexColor("#0A0A0A")
DORADO = colors.HexColor("#B8960C")
DORADO_CLARO = colors.HexColor("#C9A84C")
BLANCO = colors.HexColor("#FFFFFF")
GRIS_SUAVE = colors.HexColor("#F5F2EA")


def _styles():
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "h1",
            parent=base["Title"],
            textColor=NEGRO,
            fontName="Helvetica-Bold",
            fontSize=20,
            spaceAfter=2,
            alignment=0,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            textColor=DORADO,
            fontName="Helvetica-Bold",
            fontSize=10,
            spaceAfter=16,
            alignment=0,
        ),
        "section": ParagraphStyle(
            "section",
            parent=base["Heading2"],
            textColor=DORADO,
            fontName="Helvetica-Bold",
            fontSize=12,
            spaceBefore=14,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            textColor=NEGRO,
            fontName="Helvetica",
            fontSize=10,
            leading=14,
        ),
    }


def _fmt_num(n, dec=2) -> str:
    if n is None:
        return "—"
    try:
        return f"{float(n):,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(n)


def _tabla(filas, styles):
    data = [[Paragraph(k, styles["body"]), Paragraph(str(v), styles["body"])] for k, v in filas]
    t = Table(data, colWidths=[55 * mm, 100 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), GRIS_SUAVE),
                ("TEXTCOLOR", (0, 0), (-1, -1), NEGRO),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, DORADO_CLARO),
            ]
        )
    )
    return t


def _banda_dorada(canv, doc):
    canv.saveState()
    canv.setFillColor(NEGRO)
    canv.rect(0, A4[1] - 18 * mm, A4[0], 18 * mm, fill=1, stroke=0)
    canv.setFillColor(DORADO)
    canv.rect(0, A4[1] - 20 * mm, A4[0], 2 * mm, fill=1, stroke=0)
    canv.setFillColor(BLANCO)
    canv.setFont("Helvetica-Bold", 13)
    canv.drawString(20 * mm, A4[1] - 12 * mm, "PUCCETTI")
    canv.setFillColor(DORADO_CLARO)
    canv.setFont("Helvetica", 9)
    canv.drawString(20 * mm, A4[1] - 16 * mm, "Localización de activos inmobiliarios")
    canv.setFillColor(colors.HexColor("#888888"))
    canv.setFont("Helvetica", 8)
    canv.drawRightString(
        A4[0] - 20 * mm,
        12 * mm,
        f"Página {canv.getPageNumber()} · Ficha generada automáticamente",
    )
    canv.restoreState()


def activo_a_pdf(activo: Activo, tolerancia_m: float = 0.0) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=30 * mm,
        bottomMargin=20 * mm,
        title=f"Ficha catastral {activo.rc}",
    )
    styles = _styles()
    story = []

    story.append(Paragraph("Ficha del activo", styles["h1"]))
    story.append(
        Paragraph(
            f"Referencia catastral · {activo.rc or '—'}",
            styles["subtitle"],
        )
    )

    lon, lat = activo.centroide
    story.append(Paragraph("Identificación", styles["section"]))
    story.append(
        _tabla(
            [
                ("Referencia catastral", activo.rc or "—"),
                ("Dirección", activo.direccion or "—"),
                ("Municipio", activo.municipio or "—"),
                ("Provincia", activo.provincia or "—"),
                ("Uso catastral", activo.uso_catastro or "—"),
                ("Fuente de búsqueda", activo.fuente or "—"),
            ],
            styles,
        )
    )

    story.append(Paragraph("Geometría y superficie", styles["section"]))
    rings = activo.coordenadas_contorno
    n_vertices = sum(len(r) for r in rings)
    story.append(
        _tabla(
            [
                ("Superficie catastral", f"{_fmt_num(activo.superficie_catastral_m2)} m²"),
                ("Centroide (lon, lat)", f"{lon:.6f}, {lat:.6f}"),
                ("Anillos de contorno", str(len(rings))),
                ("Vértices totales", str(n_vertices)),
            ],
            styles,
        )
    )

    story.append(Paragraph("Edificación", styles["section"]))
    e = activo.edificio or {}
    if activo.edificio:
        story.append(
            _tabla(
                [
                    (
                        "Plantas (total)",
                        str(e.get("plantas_total") or e.get("plantas_sobre_rasante") or "—"),
                    ),
                    ("Sótanos", str(e.get("sotanos") or "—")),
                    ("Año de construcción", str(e.get("anio_construccion") or "—")),
                    (
                        "Superficie construida",
                        f"{_fmt_num(e.get('superficie_construida_m2'))} m²",
                    ),
                ],
                styles,
            )
        )
    else:
        story.append(
            Paragraph(
                "Sin edificación registrada / parcela sin construcciones.",
                styles["body"],
            )
        )

    if tolerancia_m and tolerancia_m > 0:
        try:
            simp = simplificar_contorno(activo, tolerancia_m)
            story.append(Paragraph("Contorno simplificado", styles["section"]))
            story.append(
                _tabla(
                    [
                        ("Tolerancia aplicada", f"{tolerancia_m:.2f} m"),
                        (
                            "Superficie original",
                            f"{_fmt_num(simp['superficie_original_m2'])} m²",
                        ),
                        (
                            "Superficie simplificada",
                            f"{_fmt_num(simp['superficie_simplificada_m2'])} m²",
                        ),
                        (
                            "Diferencia",
                            f"{_fmt_num(simp['diferencia_m2'])} m² "
                            f"({simp['diferencia_pct']:+.2f} %)",
                        ),
                        (
                            "Vértices",
                            f"{simp['vertices_original']} → {simp['vertices_simplificado']}",
                        ),
                    ],
                    styles,
                )
            )
        except Exception:
            # Si por cualquier motivo falla la simplificación, no rompemos el PDF.
            pass

    if activo.subreferencias:
        story.append(
            Paragraph(
                f"Referencias catastrales del edificio ({len(activo.subreferencias)})",
                styles["section"],
            )
        )
        sub_data = [
            [
                Paragraph("<b>Referencia</b>", styles["body"]),
                Paragraph("<b>Localización</b>", styles["body"]),
                Paragraph("<b>Uso</b>", styles["body"]),
                Paragraph("<b>Sup. m²</b>", styles["body"]),
            ]
        ]
        for s in activo.subreferencias:
            sub_data.append(
                [
                    Paragraph(
                        f"<font face='Courier' size='8'>{s.get('rc','')}</font>",
                        styles["body"],
                    ),
                    Paragraph(s.get("localizacion") or "—", styles["body"]),
                    Paragraph(s.get("uso") or "—", styles["body"]),
                    Paragraph(
                        _fmt_num(s.get("superficie_construida_m2"), 0),
                        styles["body"],
                    ),
                ]
            )
        sub_table = Table(
            sub_data,
            colWidths=[45 * mm, 35 * mm, 50 * mm, 25 * mm],
            repeatRows=1,
        )
        sub_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), NEGRO),
                    ("TEXTCOLOR", (0, 0), (-1, 0), DORADO),
                    ("ALIGN", (3, 1), (3, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LINEBELOW", (0, 1), (-1, -1), 0.3, DORADO_CLARO),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BLANCO, GRIS_SUAVE]),
                ]
            )
        )
        story.append(sub_table)

    story.append(Spacer(1, 8 * mm))
    story.append(
        Paragraph(
            "Datos obtenidos del Catastro español (DGC) e Instituto Geográfico Nacional.",
            ParagraphStyle(
                "footnote",
                fontName="Helvetica-Oblique",
                fontSize=8,
                textColor=colors.HexColor("#666666"),
            ),
        )
    )

    doc.build(story, onFirstPage=_banda_dorada, onLaterPages=_banda_dorada)
    return buf.getvalue()


def activo_a_geojson_bytes(activo: Activo) -> bytes:
    payload = activo.to_geojson()
    payload.setdefault("crs", {"type": "name", "properties": {"name": "EPSG:4326"}})
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
