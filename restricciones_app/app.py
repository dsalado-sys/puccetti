"""Streamlit UI — restricciones_app.

Identidad Puccetti: negro #0A0A0A, dorado #B8960C / #C9A84C, blanco.

Layout:
1. Sidebar — entrada de parcela (GPKG puccetti-app o manual), PGOU, programa,
   parámetros de diseño y costes.
2. Tabs:
   - §2.3 Análisis urbanístico
   - §2.4 Envolvente edificatoria (cálculo)
   - §2.5–§2.7 Distribución y tabla de superficies
   - §2.8 Comparador de escenarios
   - §2.9 Viabilidad económica
   - §2.10 Informe (descarga PDF y XLSX)
"""
from __future__ import annotations
import io
import pathlib
import tempfile

import streamlit as st
import pandas as pd

from restricciones.modelo import (
    Parcela, PGOU, ProgramaInversor, Costes, UsoEdificio,
)
from restricciones.diseno import ParametrosDiseno, DEFAULT as DISENO_DEFAULT
from restricciones import datos
from restricciones.urbanismo import analizar as analizar_urbanismo
from restricciones.envolvente import calcular as calcular_envolvente
from restricciones.distribucion import distribuir
from restricciones.viabilidad import calcular as calcular_viabilidad
from restricciones import superficies as sup
from restricciones.escenarios import comparar_escenarios
from restricciones.optimizador import optimizar
from restricciones.normativa import CATALOGO_USOS
from restricciones.informe import exportar_pdf, exportar_excel


# ───────────────────────── Theme / CSS ─────────────────────────
NEGRO = "#0A0A0A"
DORADO = "#B8960C"
DORADO_CLARO = "#C9A84C"
BLANCO = "#FFFFFF"

st.set_page_config(page_title="Puccetti · Restricciones", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown(f"""
<style>
    .block-container {{ padding-top: 1.5rem; }}
    h1, h2, h3 {{ color: {NEGRO} !important; }}
    .puccetti-h {{
        color: {DORADO};
        font-weight: 600;
        border-bottom: 2px solid {DORADO};
        padding-bottom: 6px; margin-bottom: 12px;
    }}
    [data-testid="stMetricValue"] {{ color: {NEGRO}; }}
    [data-testid="stMetricLabel"] {{ color: {DORADO}; }}
    .stTabs [data-baseweb="tab-list"] {{ background: {NEGRO}; padding: 4px; border-radius: 4px; }}
    .stTabs [data-baseweb="tab"] {{ color: {DORADO_CLARO}; }}
    .stTabs [aria-selected="true"] {{ color: {BLANCO} !important; background: {DORADO}; border-radius: 2px; }}
    button[kind="primary"] {{ background: {DORADO}; border-color: {DORADO}; }}
    button[kind="primary"]:hover {{ background: {DORADO_CLARO} !important; border-color: {DORADO_CLARO} !important; }}
</style>
""", unsafe_allow_html=True)

st.markdown(
    f"<h1 style='color:{NEGRO};margin-bottom:0'>"
    f"<span style='color:{DORADO}'>P</span>uccetti · Restricciones"
    f"</h1>", unsafe_allow_html=True)
st.caption("Maximiza el aprovechamiento de tu parcela dadas las restricciones "
           "urbanísticas y normativas (Anexos I/II — Andalucía).")


# ───────────────────────── Sidebar — entradas ─────────────────────────
with st.sidebar:
    st.markdown(f"<div class='puccetti-h'>Origen de datos</div>",
                unsafe_allow_html=True)
    fuentes = ["Manual (formulario)"]
    if datos.gpkg_disponible():
        fuentes.insert(0, "puccetti-app (GPKG Sevilla)")
    fuente = st.radio("Fuente de la parcela", fuentes, index=0)

    if fuente.startswith("puccetti-app"):
        parcelas_disp = datos.listar_parcelas_puccetti()
        if not parcelas_disp:
            st.warning("No se pudo leer el GPKG. Cambia a modo manual.")
            st.stop()
        opciones = {f"{p['referencia']} — {p['superficie_m2']:.0f} m²": p
                    for p in parcelas_disp}
        sel = st.selectbox("Parcela", list(opciones.keys()))
        parc_sel = opciones[sel]
        parcela = datos.parcela_desde_gpkg(parc_sel["referencia"])
        st.success(f"Parcela cargada: {parc_sel['referencia']}")
        st.write(f"Superficie: **{parc_sel['superficie_m2']:.0f} m²** · "
                 f"frente ≈ {parc_sel['frente_m']:.1f} m · "
                 f"fondo ≈ {parc_sel['fondo_m']:.1f} m")
    else:
        st.markdown(f"<div class='puccetti-h'>Parcela manual</div>",
                    unsafe_allow_html=True)
        superficie = st.number_input("Superficie (m²)", value=240.0,
                                     min_value=20.0, step=10.0)
        col1, col2 = st.columns(2)
        with col1:
            frente = st.number_input("Frente (m)", value=10.0, min_value=2.0, step=0.5)
        with col2:
            fondo = st.number_input("Fondo medio (m)", value=24.0, min_value=2.0, step=0.5)
        orient = st.selectbox("Orientación fachada principal",
                              ["", "N", "NE", "E", "SE", "S", "SW", "W", "NW"], index=0)
        proteccion = st.selectbox("Protección patrimonial",
                                  ["ninguna", "municipal", "bic"], index=0)
        edif_pre = st.checkbox("Edificio preexistente", value=False)
        parcela = datos.parcela_manual(
            superficie_m2=superficie,
            longitud_fachada_m=frente,
            profundidad_media_m=fondo,
            orientacion=orient or None,
            proteccion=proteccion,
            edificio_preexistente=edif_pre,
        )

    st.markdown(f"<div class='puccetti-h'>§2.3 PGOU</div>",
                unsafe_allow_html=True)
    edif = st.number_input("Edificabilidad (m²t/m²s)", value=2.5, min_value=0.5, max_value=8.0, step=0.1)
    ocup = st.slider("Ocupación máxima", 0.30, 1.00, 1.00, step=0.05)
    n_pl_max = st.number_input("Nº plantas máx.", value=4, min_value=1, max_value=15)
    altura_pl = st.number_input("Altura planta (m)", value=3.0, min_value=2.5, max_value=4.5, step=0.1)
    col_r1, col_r2, col_r3 = st.columns(3)
    with col_r1: rf = st.number_input("Retr. F", value=0.0, min_value=0.0, step=0.5)
    with col_r2: rl = st.number_input("Retr. L", value=0.0, min_value=0.0, step=0.5)
    with col_r3: rt = st.number_input("Retr. T", value=0.0, min_value=0.0, step=0.5)
    usos_perm = st.multiselect("Usos permitidos por PGOU",
        ["vivienda", "hotelero", "hotel_apartamento",
         "apartamentos_turisticos", "apartamentos_turisticos_conjunto"],
        default=["vivienda", "hotelero", "apartamentos_turisticos"])
    pgou = PGOU(
        edificabilidad=edif, ocupacion_maxima=ocup,
        n_plantas_max=int(n_pl_max), altura_planta_m=altura_pl,
        retranqueo_frontal_m=rf, retranqueo_lateral_m=rl, retranqueo_trasero_m=rt,
        usos_permitidos=usos_perm,
    )

    st.markdown(f"<div class='puccetti-h'>Programa inversor</div>",
                unsafe_allow_html=True)
    uso_sel: UsoEdificio = st.selectbox(
        "Uso", ["vivienda", "hotelero", "hotel_apartamento",
                "apartamentos_turisticos", "apartamentos_turisticos_conjunto"],
        index=0)
    cats_disponibles = ["(optimizar)"] + CATALOGO_USOS[uso_sel]["categorias"]
    cat_sel = st.selectbox("Categoría", cats_disponibles, index=0)
    n_pl_obj = st.selectbox("Nº plantas",
        ["(optimizar)"] + list(range(1, int(n_pl_max) + 1)), index=0)
    programa = ProgramaInversor(
        uso=uso_sel,
        categoria=None if cat_sel == "(optimizar)" else cat_sel,
        n_plantas_objetivo=None if n_pl_obj == "(optimizar)" else int(n_pl_obj),
    )

    with st.expander("§2.6 Parámetros de diseño interior", expanded=False):
        d = DISENO_DEFAULT
        e_fach = st.number_input("Espesor muro fachada (m)", value=d.espesor_muro_fachada_m, min_value=0.10, max_value=0.60, step=0.05)
        e_med = st.number_input("Espesor muro medianero (m)", value=d.espesor_muro_medianero_m, min_value=0.10, max_value=0.60, step=0.05)
        e_tab = st.number_input("Espesor tabiquería (m)", value=d.espesor_tabiqueria_m, min_value=0.05, max_value=0.20, step=0.01)
        anc_com = st.number_input("Ancho min. pasillo común (m)", value=d.ancho_min_pasillo_comun_m, min_value=0.90, max_value=2.50, step=0.05)
        anc_un = st.number_input("Ancho min. pasillo unidad (m)", value=d.ancho_min_pasillo_unidad_m, min_value=0.90, max_value=2.00, step=0.05)
        diam_vest = st.number_input("Diámetro min. vestíbulo (m)", value=d.diametro_min_vestibulo_m, min_value=1.20, max_value=2.50, step=0.05)
        lr_patio = st.number_input("Luz recta patio (m)", value=d.luz_recta_patio_min_m, min_value=2.0, max_value=8.0, step=0.5)
        a_patio = st.number_input("Área min. patio (m²)", value=d.area_patio_min_m2, min_value=6.0, max_value=40.0, step=1.0)
        prof_max = st.number_input("Profundidad max. sin patio (m)", value=d.profundidad_max_sin_patio_m, min_value=8.0, max_value=20.0, step=0.5)
        pct_circ = st.slider("% planta para circulación", 0.05, 0.30, d.pct_circulacion_planta, step=0.01)
        a_nucleo = st.number_input("Área núcleo vertical (m²/planta)", value=d.area_nucleo_vertical_m2, min_value=10.0, max_value=60.0, step=2.0)
    diseno = ParametrosDiseno(
        espesor_muro_fachada_m=e_fach, espesor_muro_medianero_m=e_med,
        espesor_tabiqueria_m=e_tab,
        ancho_min_pasillo_comun_m=anc_com, ancho_min_pasillo_unidad_m=anc_un,
        diametro_min_vestibulo_m=diam_vest,
        luz_recta_patio_min_m=lr_patio, area_patio_min_m2=a_patio,
        profundidad_max_sin_patio_m=prof_max,
        pct_circulacion_planta=pct_circ,
        area_nucleo_vertical_m2=a_nucleo,
    )

    with st.expander("§2.9 Parámetros económicos", expanded=False):
        c = Costes()
        coste_m2 = st.number_input("Coste construcción €/m²", value=c.coste_construccion_eur_m2, min_value=400.0, step=50.0)
        precio_m2 = st.number_input("Precio venta €/m² (vivienda)", value=c.precio_venta_eur_m2, min_value=500.0, step=50.0)
        renta_m2 = st.number_input("Renta €/m²·mes (hotelero/apt)", value=c.renta_eur_m2_mes, min_value=2.0, step=1.0)
        ocup_pct = st.slider("Ocupación anual hotelero/apt", 0.0, 1.0, c.ocupacion_anual_pct, step=0.05)
        mult = st.number_input("Múltiplo NOI → valor patrimonial", value=c.multiplicador_valor_hotelero, min_value=4.0, max_value=25.0, step=0.5)
        coste_suelo = st.number_input("Coste suelo (€)", value=0.0, min_value=0.0, step=10000.0)
        pct_indir = st.slider("% costes indirectos", 0.0, 0.50, c.pct_costes_indirectos, step=0.01)
    costes = Costes(
        coste_construccion_eur_m2=coste_m2,
        precio_venta_eur_m2=precio_m2,
        renta_eur_m2_mes=renta_m2,
        ocupacion_anual_pct=ocup_pct,
        multiplicador_valor_hotelero=mult,
        coste_suelo_eur=coste_suelo,
        pct_costes_indirectos=pct_indir,
    )


# ───────────────────────── Tabs ─────────────────────────
tab_urb, tab_env, tab_dist, tab_esc, tab_via, tab_inf = st.tabs([
    "§2.3 Urbanismo",
    "§2.4 Envolvente",
    "§2.5–2.7 Distribución",
    "§2.8 Escenarios",
    "§2.9 Viabilidad",
    "§2.10 Informe",
])


# §2.3 ----------------------------------------------------------------------
with tab_urb:
    techos = analizar_urbanismo(parcela, pgou, programa)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Superficie parcela", f"{techos.superficie_parcela_m2:,.0f} m²")
    c2.metric("Huella máx. (post retranqueos)", f"{techos.huella_max_m2:,.0f} m²")
    c3.metric("Edificabilidad máx.", f"{techos.edificabilidad_max_m2t:,.0f} m²t")
    c4.metric("Altura máx.", f"{techos.altura_max_m:.1f} m  ({techos.n_plantas_max} plantas)")
    if techos.alertas:
        st.warning("Alertas urbanísticas:\n- " + "\n- ".join(techos.alertas))
    else:
        st.success("Sin incompatibilidades urbanísticas detectadas.")
    st.markdown("**Lados estimados de la parcela** (modelo rectangular equivalente):")
    frente_est, fondo_est = parcela.lado_estimado()
    st.write(f"Frente ≈ {frente_est:.1f} m  ·  Fondo ≈ {fondo_est:.1f} m")


# §2.4 ----------------------------------------------------------------------
with tab_env:
    n_pl_show = programa.n_plantas_objetivo or pgou.n_plantas_max
    try:
        env = calcular_envolvente(parcela, pgou, diseno, techos,
                                  n_plantas=n_pl_show)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Huella efectiva", f"{env.huella_efectiva_m2:,.0f} m²")
        c2.metric("Construida total", f"{env.superficie_construida_total_m2:,.0f} m²")
        c3.metric("Útil total (post patios)", f"{env.superficie_util_total_m2:,.0f} m²")
        c4.metric("Patios", f"{env.superficie_patios_total_m2:,.0f} m²  "
                            f"({sum(len(p.patios) for p in env.plantas)})")
        rows = []
        for p in env.plantas:
            rows.append({
                "planta": p.n,
                "construida_m2": round(p.area_construida_m2, 1),
                "interior_bruta_m2": round(p.area_interior_bruta_m2, 1),
                "util_neta_m2": round(p.area_util_neta_m2, 1),
                "n_patios": len(p.patios),
                "patios_m2": round(sum(pt.area_m2 for pt in p.patios), 1),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
        st.caption(f"Edificabilidad consumida: "
                   f"{env.edificabilidad_consumida_m2t_m2s:.2f} m²t/m²s "
                   f"({100*env.edificabilidad_consumida_m2t_m2s/pgou.edificabilidad:.1f}% del techo)")
    except ValueError as e:
        st.error(str(e))


# §2.5–2.7 ------------------------------------------------------------------
with tab_dist:
    # Si la categoría no está fijada usamos la primera del catálogo como preview
    cat_preview = programa.categoria or CATALOGO_USOS[programa.uso]["categorias"][0]
    try:
        env = calcular_envolvente(parcela, pgou, diseno, techos,
                                  n_plantas=programa.n_plantas_objetivo or pgou.n_plantas_max)
        dist = distribuir([p.area_util_neta_m2 for p in env.plantas],
                          uso=programa.uso, categoria=cat_preview, diseno=diseno)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Nº unidades", dist.n_unidades_total)
        c2.metric("Útil unidades", f"{dist.superficie_util_total_m2:,.0f} m²")
        c3.metric("Circulación", f"{dist.superficie_circulacion_total_m2:,.0f} m²")
        c4.metric("Servicios comunes", f"{dist.superficie_servicios_comunes_total_m2:,.0f} m²")

        st.markdown(f"<div class='puccetti-h'>§2.7 Tabla por planta</div>",
                    unsafe_allow_html=True)
        tabla_plantas = sup.tabla_por_planta(env, dist)
        st.dataframe(tabla_plantas, use_container_width=True)

        st.markdown(f"<div class='puccetti-h'>Tabla por unidad</div>",
                    unsafe_allow_html=True)
        tabla_uds = sup.tabla_unidades(dist)
        st.dataframe(tabla_uds, use_container_width=True)

        if dist.alertas:
            st.warning("\n".join("• " + a for a in dist.alertas))
    except ValueError as e:
        st.error(str(e))


# §2.8 ----------------------------------------------------------------------
with tab_esc:
    st.markdown(f"<div class='puccetti-h'>Comparador de 3 objetivos</div>",
                unsafe_allow_html=True)
    try:
        escenarios = comparar_escenarios(parcela, pgou, diseno, costes, programa)
        cols = st.columns(3)
        for col, (titulo, r) in zip(cols, escenarios.como_lista()):
            with col:
                st.markdown(f"**{titulo}**")
                st.metric("Margen €", f"{r.margen_eur:,.0f} €")
                st.metric("Útil unidades", f"{r.superficie_util_total_m2:,.0f} m²")
                st.metric("Nº unidades", r.n_unidades_total)
                st.write(f"**Uso:** {r.uso}  ·  **Categoría:** {r.categoria}")
                st.write(f"**Plantas:** {r.n_plantas}  ·  "
                         f"**Edif. usada:** {r.pct_edificabilidad_usada}%")
                st.write(f"**ROI:** {r.roi_pct}%")
                if not r.cumple_normativa:
                    st.warning("Revisar alertas normativas.")
        st.session_state["escenarios"] = escenarios
    except Exception as e:
        st.error(f"No se pudo optimizar: {e}")
        st.session_state.pop("escenarios", None)


# §2.9 ----------------------------------------------------------------------
with tab_via:
    st.markdown(f"<div class='puccetti-h'>Viabilidad económica del óptimo (máx. margen)</div>",
                unsafe_allow_html=True)
    if "escenarios" not in st.session_state:
        st.info("Calculando escenarios…")
    else:
        r = st.session_state["escenarios"].max_margen
        via = calcular_viabilidad(r.uso, r.categoria,
            r.superficie_construida_total_m2, r.superficie_util_total_m2,
            r.n_unidades_total, costes)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ingresos", f"{via.ingresos_eur:,.0f} €")
        c2.metric("Coste construcción", f"{via.coste_construccion_eur:,.0f} €")
        c3.metric("Coste total", f"{via.coste_total_eur:,.0f} €")
        c4.metric("Margen", f"{via.margen_eur:,.0f} €",
                  delta=f"ROI {via.roi_pct}%")
        st.write(f"**Modelo de negocio:** {via.modelo_negocio}")
        if via.modelo_negocio == "explotacion":
            st.write(f"**NOI anual estimado:** {via.noi_anual_eur:,.0f} €  "
                     f"·  Multiplicador aplicado: ×{costes.multiplicador_valor_hotelero}")
        with st.expander("Desglose"):
            st.json({
                "ingresos_eur": via.ingresos_eur,
                "coste_construccion_eur": via.coste_construccion_eur,
                "coste_indirectos_eur": via.coste_indirectos_eur,
                "coste_suelo_eur": via.coste_suelo_eur,
                "coste_total_eur": via.coste_total_eur,
                "margen_eur": via.margen_eur,
                "roi_pct": via.roi_pct,
                "factor_categoria": via.desglose["factor_categoria"],
            })


# §2.10 ---------------------------------------------------------------------
with tab_inf:
    st.markdown(f"<div class='puccetti-h'>Generar informe</div>",
                unsafe_allow_html=True)
    if "escenarios" not in st.session_state:
        st.info("Primero calcula escenarios en la pestaña §2.8.")
    else:
        escenarios = st.session_state["escenarios"]
        r = escenarios.max_margen
        env = calcular_envolvente(parcela, pgou, diseno, techos,
            n_plantas=r.n_plantas, huella_objetivo_m2=r.huella_efectiva_m2)
        dist = distribuir([p.area_util_neta_m2 for p in env.plantas],
            uso=r.uso, categoria=r.categoria, diseno=diseno)
        tabla_plantas = sup.tabla_por_planta(env, dist)
        tabla_uds = sup.tabla_unidades(dist)
        resumen = sup.resumen(env, dist, techos.edificabilidad_max_m2t,
                              parcela.superficie_m2)

        out_dir = pathlib.Path(tempfile.gettempdir()) / "puccetti_restricciones"
        out_dir.mkdir(parents=True, exist_ok=True)
        ref_safe = "".join(c if c.isalnum() else "_" for c in parcela.referencia)
        pdf_path = out_dir / f"informe_{ref_safe}.pdf"
        xlsx_path = out_dir / f"superficies_{ref_safe}.xlsx"

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Generar PDF", type="primary", use_container_width=True):
                exportar_pdf(parcela, pgou, costes, escenarios,
                             tabla_plantas, tabla_uds, resumen, pdf_path)
                st.success(f"PDF generado: {pdf_path.name}")
            if pdf_path.exists():
                with open(pdf_path, "rb") as f:
                    st.download_button("Descargar PDF", f, file_name=pdf_path.name,
                                       mime="application/pdf",
                                       use_container_width=True)
        with col2:
            if st.button("Generar XLSX", type="primary", use_container_width=True):
                exportar_excel(parcela, pgou, costes, escenarios,
                               tabla_plantas, tabla_uds, resumen, xlsx_path)
                st.success(f"XLSX generado: {xlsx_path.name}")
            if xlsx_path.exists():
                with open(xlsx_path, "rb") as f:
                    st.download_button("Descargar XLSX", f, file_name=xlsx_path.name,
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                       use_container_width=True)

        st.markdown("---")
        st.markdown(f"<div class='puccetti-h'>Vista previa del contenido</div>",
                    unsafe_allow_html=True)
        st.json({"resumen": resumen,
                 "escenarios": {
                     "max_margen":   {"uso": r.uso, "cat": r.categoria,
                                      "margen_eur": r.margen_eur, "n_uds": r.n_unidades_total},
                     "max_m2_util":  {"uso": escenarios.max_m2_util.uso,
                                      "cat": escenarios.max_m2_util.categoria,
                                      "util_m2": escenarios.max_m2_util.superficie_util_total_m2,
                                      "n_uds": escenarios.max_m2_util.n_unidades_total},
                     "max_unidades": {"uso": escenarios.max_unidades.uso,
                                      "cat": escenarios.max_unidades.categoria,
                                      "n_uds": escenarios.max_unidades.n_unidades_total,
                                      "margen_eur": escenarios.max_unidades.margen_eur},
                 }})
