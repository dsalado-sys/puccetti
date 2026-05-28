"""Puccetti — Prefactibilidad de edificio PLURIFAMILIAR.

Calcula, sobre CUALQUIER parcela (de muestra, por referencia catastral o por
coordenadas), el número de viviendas posibles según la edificabilidad y propone
su disposición siguiendo el Anexo I (superficies) y el Anexo II (diseño) del PDF.

Lanzar con:   streamlit run app.py
"""
from __future__ import annotations
import json
import random
from dataclasses import replace

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from puccetti.parcelas import (
    cargar_parcelas, cargar_contexto, simplificar,
    clasificar_lados, resumen_lados, _orientacion_cardinal,
)
from puccetti.envolvente import construir_envolvente
from puccetti.macro_layout import generar_edificio
from puccetti.serializacion import (
    edificio_a_dict, tabla_superficies_por_planta, tabla_unidades,
)
from puccetti.svg_render import (
    render_planta_svg, leyenda_svg,
    render_planta_interiores_svg, leyenda_interiores_svg,
)
from puccetti.interiores import distribuir_planta_interiores
from puccetti.informe import generar_informe_pdf
from puccetti.viz import render_parcela_lados
from puccetti.config import (
    Parametros, ParametrosDiseno, ParametrosUrbanisticos, ParametrosPrograma,
)

st.set_page_config(page_title='Puccetti — Prefactibilidad', layout='wide')


# ======================================================================
#  Carga de parcelas (muestra offline + descarga del Catastro)
# ======================================================================
@st.cache_data
def _muestra():
    return cargar_parcelas()

@st.cache_data
def _contexto():
    return cargar_contexto()

@st.cache_data(show_spinner='Consultando el Catastro…')
def _fetch_rc(rc: str):
    from puccetti.catastro import parcela_y_entorno_por_rc
    return parcela_y_entorno_por_rc(rc)

@st.cache_data(show_spinner='Consultando el Catastro…')
def _fetch_coord(lon: float, lat: float):
    from puccetti.catastro import parcela_y_entorno_por_coord
    return parcela_y_entorno_por_coord(lon, lat)


# ======================================================================
#  SIDEBAR
# ======================================================================
st.sidebar.title('Puccetti  ·  Prefactibilidad')
st.sidebar.caption('Edificio plurifamiliar de vivienda sobre parcela catastral')

st.sidebar.subheader('Parcela')
fuente = st.sidebar.radio(
    'Origen', ['Referencia catastral', 'Coordenadas (lon, lat)', 'Muestra (offline)'],
    help='El motor calcula sobre cualquier parcela. RC y coordenadas la descargan '
         'del Catastro (INSPIRE WFS); la muestra son 10 parcelas cacheadas de Sevilla.')

parc = None
contexto = None
etiqueta = ''
try:
    if fuente == 'Muestra (offline)':
        muestra = _muestra()
        opciones = [
            f"p{r['parcela_id']} · RC {r['referencia_catastral']} · {r['area_m2_calc']:.0f} m²"
            for _, r in muestra.iterrows()]
        sel = st.sidebar.selectbox('Parcela de muestra', options=range(len(opciones)),
                                   format_func=lambda i: opciones[i])
        parc = simplificar(muestra.loc[sel].geometry, tolerancia=0.10)
        contexto = _contexto()
        etiqueta = f"RC {muestra.loc[sel]['referencia_catastral']}"
    elif fuente == 'Referencia catastral':
        rc = st.sidebar.text_input('Referencia catastral', '',
                                   help='14 caracteres, p. ej. 5136614TG3453E0001XY')
        if not rc.strip():
            st.info('Introduce una referencia catastral en la barra lateral para analizar la parcela.')
            st.stop()
        geom, contexto = _fetch_rc(rc.strip())
        parc = simplificar(geom, tolerancia=0.10)
        etiqueta = f"RC {rc.strip().upper()[:14]}"
    else:
        c1, c2 = st.sidebar.columns(2)
        lon = c1.number_input('Longitud', value=-5.9938, format='%.6f')
        lat = c2.number_input('Latitud', value=37.3829, format='%.6f')
        if st.sidebar.button('Buscar parcela', use_container_width=True) or st.session_state.get('_coord_done'):
            st.session_state['_coord_done'] = True
            geom, contexto = _fetch_coord(float(lon), float(lat))
            parc = simplificar(geom, tolerancia=0.10)
            etiqueta = f"({lon:.5f}, {lat:.5f})"
        else:
            st.info('Pulsa "Buscar parcela" tras introducir las coordenadas.')
            st.stop()
except Exception as e:
    st.error(f'No se pudo obtener la parcela del Catastro: {e}')
    st.stop()

# ---- §2.1 Clasificación fachada/medianera (automática + corrección manual) ----
lados_auto = clasificar_lados(parc, parcelas_vecinas=contexto, dist_probe=1.0)
n_correcciones = 0
with st.sidebar.expander('§2.1 Fachadas / medianeras', expanded=False):
    df_lados = pd.DataFrame([
        {'lado': i, 'long_m': round(l.longitud_m, 1),
         'orient': _orientacion_cardinal(l.azimut), 'tipo': l.tipo}
        for i, l in enumerate(lados_auto)
    ])
    st.caption('Clasificación automática por cartografía. Corrige el `tipo` si hace '
               'falta — el nº de lado se ve sobre el mapa en la pestaña «Fachadas».')
    edit_lados = st.data_editor(
        df_lados, hide_index=True, width='stretch', key=f'lados_{etiqueta}',
        column_config={
            'lado':   st.column_config.NumberColumn('lado', disabled=True),
            'long_m': st.column_config.NumberColumn('long (m)', disabled=True),
            'orient': st.column_config.TextColumn('orient.', disabled=True),
            'tipo':   st.column_config.SelectboxColumn(
                'tipo', options=['fachada', 'medianera'], required=True),
        })
    # lados finales = automáticos con las correcciones del técnico aplicadas
    lados = [replace(l, tipo=str(edit_lados.iloc[i]['tipo']))
             for i, l in enumerate(lados_auto)]
    n_correcciones = sum(1 for a, l in zip(lados_auto, lados) if a.tipo != l.tipo)
    if n_correcciones:
        st.caption(f'✏️ {n_correcciones} lado(s) corregido(s) manualmente.')

with st.sidebar.expander('§2.3 Urbanismo', expanded=True):
    urb = ParametrosUrbanisticos(
        edificabilidad   = st.slider('Edificabilidad (m²t/m²s)', 0.5, 6.0, 2.5, 0.1),
        ocupacion_maxima = st.slider('Ocupación máxima',          0.30, 1.00, 1.00, 0.05),
        n_plantas_max    = st.slider('Nº máx. de plantas',        1, 8, 4),
        retranqueo_frontal = st.slider('Retranqueo frontal (m)',  0.0, 5.0, 0.0, 0.5),
        retranqueo_lateral = st.slider('Retranqueo lateral (m)',  0.0, 5.0, 0.0, 0.5),
        retranqueo_trasero = st.slider('Retranqueo trasero (m)',  0.0, 5.0, 0.0, 0.5),
        altura_planta      = 3.0,
    )

with st.sidebar.expander('Programa (§2.5 · vivienda)', expanded=True):
    n_dorms = st.slider('Dormitorios por vivienda', 0, 5, 2,
        help='Define el tamaño de vivienda (Anexo I.5) y, con ello, cuántas caben.')
    prog = ParametrosPrograma(
        uso='vivienda', n_dormitorios=n_dorms,
        n_plantas=urb.n_plantas_max, n_viviendas_por_planta=1,
    )
    # Por defecto el nº de viviendas/planta se CALCULA desde la edificabilidad.
    forzar_viv = st.checkbox(
        'Forzar nº de viviendas/planta', value=False,
        help='Por defecto se calcula desde la edificabilidad y el Anexo I.5. '
             'Márcalo para imponer un número manual.')
    viv_manual = (st.slider('Viviendas por planta (manual)', 1, 12, 4)
                  if forzar_viv else None)

with st.sidebar.expander('§2.6 Diseño (Anexo II)', expanded=False):
    diseno = ParametrosDiseno(
        espesor_muro_fachada      = st.slider('Espesor muro fachada (m)',   0.10, 0.50, 0.25, 0.05),
        espesor_muro_medianero    = st.slider('Espesor muro medianero (m)', 0.10, 0.50, 0.25, 0.05),
        espesor_separacion_unidades = st.slider('Espesor separación entre viviendas (m)', 0.10, 0.40, 0.20, 0.05),
        espesor_tabiqueria        = 0.10,
        ancho_min_pasillo_comun   = st.slider('Ancho mín. pasillo común (m)', 1.00, 2.00, 1.20, 0.05),
        ancho_min_pasillo_vivienda = 1.00,
        diametro_min_vestibulo    = st.slider('Ø mín. vestíbulo (m)',   1.20, 2.50, 1.50, 0.10),
        radio_apertura_puerta     = 0.80,
        luz_recta_patio_min       = st.slider('Luz recta patio (m)',    2.00, 6.00, 3.00, 0.50),
        area_patio_min            = st.slider('Área mínima patio (m²)', 6.0, 30.0, 12.0, 1.0),
        profundidad_max_sin_patio = st.slider('Profundidad máx. sin patio (m)', 8.0, 18.0, 12.0, 0.5),
    )

with st.sidebar.expander('Solver', expanded=False):
    n_cand = st.slider('Candidatos a evaluar', 4, 32, 12,
        help='Explora estrategias (eje del pasillo × single/double) y devuelve la mejor.')
    seed_input = st.text_input('Seed (vacío = aleatorio)', value='42')
    seed_val = int(seed_input) if seed_input.strip().lstrip('-').isdigit() else random.randint(1, 10**6)

params = Parametros(diseno=diseno, urbanismo=urb, programa=prog, seed=seed_val)


# ======================================================================
#  PIPELINE  (usa `lados`, ya clasificados + corregidos en la barra lateral)
# ======================================================================
rl = resumen_lados(lados)
envol = construir_envolvente(parc, params)
edif = generar_edificio(envol, lados, params, n_viviendas_por_planta=viv_manual,
                        seed=seed_val, n_candidatos=n_cand)
cap = edif.capacidad

st.title('Edificio plurifamiliar — prefactibilidad')
st.caption(f'{etiqueta} · parcela {parc.area:.1f} m² · '
           f'{cap.n_plantas_edificables} plantas · seed={seed_val}')

# ---- KPIs ----
k1, k2, k3, k4 = st.columns(4)
k1.metric('Viviendas (dispuestas)', edif.n_viviendas_total,
          help='Las que caben respetando núcleo, pasillo, acceso y ventilación (Anexo II).')
k2.metric('Objetivo por edificabilidad', cap.n_viviendas_objetivo,
          help='Nº de viviendas que permite la edificabilidad con el tamaño del Anexo I.5.')
k3.metric('Plantas', f'{cap.n_plantas_edificables}',
          delta=(None if cap.n_plantas_edificables == cap.n_plantas_solicitadas
                 else f'limita: {cap.factor_limitante}'),
          delta_color='off')
edif_pct = (100 * edif.edificabilidad_consumida / edif.edificabilidad_max
            if edif.edificabilidad_max else 0)
k4.metric('Edificabilidad usada', f'{edif_pct:.0f} %')

incidencias_tot = sum(len(p.incidencias) for p in edif.plantas)

(tab_planta, tab_int, tab_fach, tab_cap,
 tab_tabla, tab_val, tab_json) = st.tabs([
    'Planta(s)', 'Interiores', 'Fachadas / medianeras', 'Capacidad (edificabilidad)',
    'Tabla de superficies', 'Validación (Anexo II)', 'JSON / parámetros',
])

# === Planta(s) ===
with tab_planta:
    st.caption(
        f'Cada color es una **vivienda independiente** con su superficie útil. '
        f'Núcleo (escalera + ascensor) con círculo libre Ø{diseno.diametro_min_vestibulo:.2f} m, '
        f'pasillo común ≥{diseno.ancho_min_pasillo_comun:.2f} m, patios como vacíos '
        f'enclaustrados. Dorado = fachada · negro = medianera (sin huecos, A2.4).')
    st.image(leyenda_svg(width_px=900), width='stretch')
    cols = st.columns(max(len(edif.plantas), 1))
    for i, p in enumerate(edif.plantas):
        with cols[i]:
            svg = render_planta_svg(
                p, lados=lados, width_px=470,
                titulo=(f"{'PB' if p.n==0 else 'P'+str(p.n)} · {len(p.unidades)} viviendas "
                        f"· {p.tipologia} · score {p.score}"))
            st.image(svg, width='stretch')
            for inc in p.incidencias:
                st.warning(f'• {inc}')

# === Interiores (distribución de estancias por vivienda) ===
with tab_int:
    st.caption(
        'La **misma distribución de viviendas** de la pestaña anterior, ahora con '
        'el diseño interior del Anexo II: estancias principales (salón, '
        'dormitorios) **a fachada**; cocina y baños al interior/patio; habitaciones '
        'desde un **pasillo ≥0,90 m**; acceso por vestíbulo. Tamaños del Anexo I.5.')
    st.image(leyenda_interiores_svg(width_px=900), width='stretch')
    cols = st.columns(max(len(edif.plantas), 1))
    for i, p in enumerate(edif.plantas):
        with cols[i]:
            viv_int = distribuir_planta_interiores(p, lados, params)
            svg = render_planta_interiores_svg(
                p, viv_int, lados=lados, width_px=470,
                titulo=f"{'PB' if p.n==0 else 'P'+str(p.n)} · interiores · {len(p.unidades)} viviendas")
            st.image(svg, width='stretch')

# === Fachadas / medianeras ===
with tab_fach:
    col1, col2 = st.columns([2, 1])
    with col1:
        fig, ax = plt.subplots(figsize=(8, 8))
        render_parcela_lados(parc, lados, ax=ax)
        # nº de cada lado, para casarlo con la tabla de corrección de la barra lateral
        for i, l in enumerate(lados):
            mx, my = (l.p1[0] + l.p2[0]) / 2, (l.p1[1] + l.p2[1]) / 2
            ax.annotate(str(i), (mx, my), ha='center', va='center', fontsize=8,
                        fontweight='bold', color='#0A0A0A', zorder=5,
                        bbox=dict(boxstyle='circle,pad=0.2', fc='white',
                                  ec='#888', lw=0.6, alpha=0.9))
        ax.set_title('Clasificación de lados — corrige el tipo en la barra lateral')
        st.pyplot(fig, clear_figure=True)
    with col2:
        st.subheader('Resumen')
        st.write({
            'fachadas (n)':       rl['n_fachadas'],
            'medianeras (n)':     rl['n_medianeras'],
            'long. fachada (m)':  round(rl['long_fachada_total'], 1),
            'long. medianera (m)': round(rl['long_medianera_total'], 1),
            'orientaciones':      rl['orientaciones_fachada'],
        })
        st.caption('Solo se abren huecos (ventanas, accesos) en fachada. Las '
                   'estancias principales exigen fachada (A2.5).')

# === Capacidad ===
with tab_cap:
    st.subheader('Número de viviendas según la edificabilidad')
    st.caption('El número de viviendas no se fija a mano: se deriva de los '
               'parámetros urbanísticos y del tamaño de vivienda del Anexo I.5.')
    izda, dcha = st.columns(2)
    with izda:
        st.markdown('**Edificabilidad**')
        st.dataframe(pd.DataFrame([
            ('Superficie de parcela', f'{cap.superficie_parcela_m2:.0f} m²'),
            ('Edificabilidad', f'{cap.edificabilidad:.2f} m²t/m²s'),
            ('Techo máximo', f'{cap.techo_max_m2:.0f} m²t'),
            ('Huella (× ocupación)', f'{cap.huella_efectiva_m2:.0f} m²'),
            ('Plantas solicitadas → edificables', f'{cap.n_plantas_solicitadas} → {cap.n_plantas_edificables}'),
            ('Factor limitante', cap.factor_limitante),
            ('Construida prevista', f'{cap.construida_prevista_m2:.0f} m²'),
        ], columns=['parámetro', 'valor']), hide_index=True, width='stretch')
    with dcha:
        st.markdown('**Viviendas**')
        st.dataframe(pd.DataFrame([
            ('Tipología', f'{cap.n_dormitorios} dorm.'),
            ('Útil objetivo / vivienda', f'{cap.util_objetivo_viv_m2:.0f} m² (máx. Anexo I.5)'),
            ('Útil disponible / planta', f'{cap.util_planta_disponible_m2:.0f} m²'),
            ('Viviendas / planta (objetivo)', str(cap.viv_por_planta_objetivo)),
            ('Viviendas totales (objetivo)', str(cap.n_viviendas_objetivo)),
            ('Viviendas / planta (dispuestas)', str(edif.viv_por_planta_dispuestas)),
            ('Viviendas totales (dispuestas)', str(edif.n_viviendas_total)),
        ], columns=['parámetro', 'valor']), hide_index=True, width='stretch')
    if edif.n_viviendas_total < cap.n_viviendas_objetivo:
        st.warning('Se disponen menos viviendas que el objetivo por edificabilidad: '
                   'la geometría de la parcela y el acceso a fachada (Anexo II) lo limitan.')

# === Tabla de superficies (§2.7) ===
with tab_tabla:
    st.subheader('Cuadro de superficies por planta (construida vs útil)')
    st.dataframe(tabla_superficies_por_planta(edif), hide_index=True, width='stretch')
    st.subheader('Viviendas')
    df_u = tabla_unidades(edif)
    def _hl_u(row):
        bad = (not row['cumple_min']) or (not row['ventila_ok']) or (not row['acceso'])
        return ['background-color: #ffe6e6' if bad else '' for _ in row]
    if not df_u.empty:
        st.dataframe(df_u.style.apply(_hl_u, axis=1), width='stretch')
    st.caption(f'Útil máximo de referencia (Anexo I.5) para {n_dorms} dorm.: '
               f'{cap.util_objetivo_viv_m2:.0f} m².')

# === Validación (Anexo II) ===
with tab_val:
    st.subheader('Cumplimiento del Anexo II')
    if incidencias_tot == 0:
        st.success('Sin incidencias: todas las viviendas tienen acceso al pasillo, '
                   'ventilación a fachada y cumplen los mínimos.')
    else:
        for p in edif.plantas:
            if p.incidencias:
                st.markdown(f"**{'PB' if p.n==0 else 'P'+str(p.n)}**")
                for inc in p.incidencias:
                    st.warning(f'• {inc}')
    st.divider()
    st.caption(
        'Reglas verificadas — A2.1: núcleo con vestíbulo de círculo libre Ø1.50 m. '
        'A2.3: cada vivienda con acceso directo al pasillo común. '
        'A2.4: medianeras sin huecos. '
        'A2.5: las estancias principales ventilan a fachada (el patio mínimo de '
        '12 m² solo ventila cocina/baños).')

# === Informe / JSON ===
with tab_json:
    st.subheader('Informe PDF (§2.10)')
    st.caption('Ficha del activo · parámetros urbanísticos · volumetría · planimetría '
               'planta por planta · tabla de superficies · alertas · sección de rentabilidad.')
    if st.button('Generar informe PDF', type='primary'):
        with st.spinner('Generando informe…'):
            st.session_state['informe_pdf'] = generar_informe_pdf(
                edif, params, lados, parc, etiqueta)
    if st.session_state.get('informe_pdf'):
        st.download_button('Descargar informe_puccetti.pdf',
                           st.session_state['informe_pdf'],
                           file_name='informe_puccetti.pdf', mime='application/pdf')
        st.caption('Si cambias parámetros, vuelve a pulsar «Generar informe PDF».')

    st.divider()
    st.subheader('Datos (JSON)')
    data = edificio_a_dict(edif, params)
    st.download_button('Descargar edificio.json',
                       json.dumps(data, ensure_ascii=False, indent=2),
                       file_name='edificio.json', mime='application/json')
    st.code(json.dumps(data['totales'] | data['edificabilidad'], ensure_ascii=False, indent=2),
            language='json')
    st.code(params.model_dump_json(indent=2), language='json')

st.sidebar.divider()
st.sidebar.caption('RC y coordenadas consultan el Catastro (INSPIRE WFS). '
                   'La muestra usa `data/parcelas_sevilla.gpkg` (offline).')
