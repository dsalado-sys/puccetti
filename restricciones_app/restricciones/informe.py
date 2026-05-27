"""§2.10 — Generación del informe y exportación.

PDF con identidad Puccetti (negro #0A0A0A, dorado #B8960C/#C9A84C) que recoge:
- ficha de parcela
- topes urbanísticos
- tabla por planta
- tabla por unidad
- viabilidad económica
- 3 escenarios óptimos del comparador

Adicionalmente, exportación a Excel multi-hoja con las mismas tablas.
"""
from __future__ import annotations
import io
import pathlib

import pandas as pd

from .modelo import Parcela, PGOU, Costes, Resultado
from .escenarios import Escenarios

NEGRO = (10 / 255, 10 / 255, 10 / 255)
DORADO = (184 / 255, 150 / 255, 12 / 255)
DORADO_CLARO = (201 / 255, 168 / 255, 76 / 255)


def _resultado_a_dict(r: Resultado) -> dict:
    return {
        "uso": r.uso, "categoria": r.categoria,
        "n_plantas": r.n_plantas, "n_unidades": r.n_unidades_total,
        "construida_m2": r.superficie_construida_total_m2,
        "util_m2": r.superficie_util_total_m2,
        "pct_edif_usada": r.pct_edificabilidad_usada,
        "pct_ocupacion": r.pct_ocupacion,
        "ingresos_eur": r.ingresos_eur,
        "coste_total_eur": r.coste_total_eur,
        "margen_eur": r.margen_eur,
        "roi_pct": r.roi_pct,
        "cumple": r.cumple_normativa,
    }


def exportar_excel(parcela: Parcela, pgou: PGOU, costes: Costes,
                   escenarios: Escenarios,
                   tabla_plantas: pd.DataFrame,
                   tabla_unidades: pd.DataFrame,
                   resumen: dict,
                   path: pathlib.Path) -> pathlib.Path:
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        pd.DataFrame([parcela.model_dump()]).to_excel(w, sheet_name="Parcela", index=False)
        pd.DataFrame([pgou.model_dump()]).to_excel(w, sheet_name="PGOU", index=False)
        pd.DataFrame([costes.model_dump()]).to_excel(w, sheet_name="Costes", index=False)
        pd.DataFrame([resumen]).to_excel(w, sheet_name="Resumen", index=False)
        tabla_plantas.to_excel(w, sheet_name="Por_planta", index=False)
        tabla_unidades.to_excel(w, sheet_name="Por_unidad", index=False)
        pd.DataFrame([
            {"escenario": "Máx. margen €",        **_resultado_a_dict(escenarios.max_margen)},
            {"escenario": "Máx. m² útil",         **_resultado_a_dict(escenarios.max_m2_util)},
            {"escenario": "Máx. nº unidades",     **_resultado_a_dict(escenarios.max_unidades)},
        ]).to_excel(w, sheet_name="Escenarios", index=False)
    return path


def exportar_pdf(parcela: Parcela, pgou: PGOU, costes: Costes,
                 escenarios: Escenarios,
                 tabla_plantas: pd.DataFrame,
                 tabla_unidades: pd.DataFrame,
                 resumen: dict,
                 path: pathlib.Path) -> pathlib.Path:
    """Informe PDF en paleta corporativa Puccetti."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    )
    from reportlab.lib.units import mm

    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    titulo = ParagraphStyle("titulo", parent=styles["Heading1"],
        textColor=colors.Color(*DORADO), fontSize=20, spaceAfter=12)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"],
        textColor=colors.Color(*NEGRO), fontSize=13, spaceAfter=6)
    normal = styles["BodyText"]

    story = []
    story.append(Paragraph("Estudio de prefactibilidad — Puccetti", titulo))
    story.append(Paragraph(
        f"Parcela: <b>{parcela.referencia}</b> &nbsp;·&nbsp; "
        f"Superficie: <b>{parcela.superficie_m2:.0f} m²</b>", normal))
    story.append(Spacer(1, 8))

    # Ficha PGOU
    story.append(Paragraph("§2.3 — Parámetros urbanísticos", h2))
    story.append(_tabla_kv({
        "Edificabilidad (m²t/m²s)": pgou.edificabilidad,
        "Ocupación máxima": f"{pgou.ocupacion_maxima*100:.0f}%",
        "Nº plantas máx.": pgou.n_plantas_max,
        "Altura planta (m)": pgou.altura_planta_m,
        "Retranqueos (F/L/T m)":
            f"{pgou.retranqueo_frontal_m}/{pgou.retranqueo_lateral_m}/{pgou.retranqueo_trasero_m}",
        "Usos permitidos": ", ".join(pgou.usos_permitidos),
    }))

    # Escenarios
    story.append(Spacer(1, 12))
    story.append(Paragraph("§2.8 — Escenarios óptimos", h2))
    head = ["", "Máx. margen €", "Máx. m² útil", "Máx. nº unidades"]
    e = escenarios
    data = [head]
    for clave, k in [
        ("Uso · categoría",        lambda r: f"{r.uso}\n{r.categoria}"),
        ("Nº plantas",             lambda r: r.n_plantas),
        ("Nº unidades",            lambda r: r.n_unidades_total),
        ("Construida (m²)",        lambda r: f"{r.superficie_construida_total_m2:,.0f}"),
        ("Útil unidades (m²)",     lambda r: f"{r.superficie_util_total_m2:,.0f}"),
        ("% Edificabilidad usada", lambda r: f"{r.pct_edificabilidad_usada}%"),
        ("Margen económico (€)",   lambda r: f"{r.margen_eur:,.0f}"),
        ("ROI",                    lambda r: f"{r.roi_pct}%"),
        ("Cumple normativa",       lambda r: "Sí" if r.cumple_normativa else "Revisar"),
    ]:
        data.append([clave, k(e.max_margen), k(e.max_m2_util), k(e.max_unidades)])
    t = Table(data, repeatRows=1)
    t.setStyle(_estilo_tabla())
    story.append(t)

    # Resumen y por planta
    story.append(PageBreak())
    story.append(Paragraph("§2.7 — Tabla de superficies", h2))
    story.append(_df_to_table(tabla_plantas))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Desglose por unidad", h2))
    if len(tabla_unidades):
        story.append(_df_to_table(tabla_unidades))
    else:
        story.append(Paragraph("Sin unidades viables para los parámetros dados.", normal))

    # Viabilidad
    story.append(PageBreak())
    story.append(Paragraph("§2.9 — Viabilidad económica (escenario máx. margen)", h2))
    r = escenarios.max_margen
    story.append(_tabla_kv({
        "Modelo de negocio": "venta" if r.uso == "vivienda" else "explotación",
        "Ingresos (€)": f"{r.ingresos_eur:,.0f}",
        "Coste construcción (€)": f"{r.coste_construccion_eur:,.0f}",
        "Coste total (€)": f"{r.coste_total_eur:,.0f}",
        "Margen (€)": f"{r.margen_eur:,.0f}",
        "ROI": f"{r.roi_pct}%",
        "Coste constr. unit. (€/m²)": f"{costes.coste_construccion_eur_m2:,.0f}",
        "Precio venta unit. (€/m²)": f"{costes.precio_venta_eur_m2:,.0f}",
    }))

    # Alertas
    alertas_all = list({a for esc in (e.max_margen, e.max_m2_util, e.max_unidades)
                        for a in esc.alertas})
    if alertas_all:
        story.append(Spacer(1, 10))
        story.append(Paragraph("Alertas", h2))
        for a in alertas_all:
            story.append(Paragraph("• " + a, normal))

    doc.build(story)
    return path


def _estilo_tabla():
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(*NEGRO)),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.Color(*DORADO)),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.Color(0.96, 0.96, 0.96)]),
        ("LINEBELOW", (0, 0), (-1, 0), 1.0, colors.Color(*DORADO)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ])


def _df_to_table(df: pd.DataFrame):
    from reportlab.platypus import Table
    data = [list(df.columns)] + df.astype(str).values.tolist()
    t = Table(data, repeatRows=1)
    t.setStyle(_estilo_tabla())
    return t


def _tabla_kv(kv: dict):
    from reportlab.platypus import Table
    from reportlab.lib.units import mm
    data = [[k, str(v)] for k, v in kv.items()]
    t = Table(data, colWidths=[60 * mm, None])
    t.setStyle(_estilo_tabla())
    return t
