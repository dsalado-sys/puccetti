"""dxf-app — UI Streamlit. Sube un .dxf y explora sus datos de forma
tabular (capas, entidades, bloques, textos, dimensiones) y grafica
(render del modelspace, con filtro de capas).

Identidad Puccetti: negro #0A0A0A, dorado #B8960C / #C9A84C, blanco.
"""
from __future__ import annotations

import os
import tempfile

import pandas as pd
import streamlit as st

from dxf_app import (
    cargar_dxf, resumen_general,
    tabla_capas, tabla_entidades, tabla_bloques, tabla_textos, tabla_dimensiones,
    render_png, render_capa_png,
)

# ───────────────────────── Theme ─────────────────────────
NEGRO = '#0A0A0A'
DORADO = '#B8960C'
DORADO_CLARO = '#C9A84C'
BLANCO = '#FFFFFF'

st.set_page_config(page_title='Puccetti · DXF Viewer', layout='wide',
                   initial_sidebar_state='expanded')

st.markdown(f"""
<style>
    .block-container {{ padding-top: 1.5rem; }}
    h1, h2, h3 {{ color: {NEGRO} !important; }}
    .puccetti-h {{
        color: {DORADO}; font-weight: 600;
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
    f"<span style='color:{DORADO}'>P</span>uccetti · DXF Viewer"
    f"</h1>", unsafe_allow_html=True)
st.caption('Carga un archivo .dxf y explora sus datos en forma tabular y '
           'grafica. Sin hardcode — todo sale del archivo.')


# ───────────────────────── Sidebar: archivo ─────────────────────────
with st.sidebar:
    st.markdown(f"<div class='puccetti-h'>Archivo DXF</div>",
                unsafe_allow_html=True)
    subida = st.file_uploader('Sube un .dxf', type=['dxf'])
    fondo = st.color_picker('Color de fondo del render', BLANCO)
    ancho = st.slider('Ancho del render (px)', 600, 2400, 1400, 100)

if subida is None:
    st.info('Sube un archivo .dxf en la barra lateral para comenzar.')
    st.stop()

# Guarda el upload en un fichero temporal (ezdxf lee desde ruta).
suffix = os.path.splitext(subida.name)[1] or '.dxf'
with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
    tmp.write(subida.read())
    ruta_dxf = tmp.name

with st.spinner(f'Leyendo {subida.name}...'):
    try:
        doc = cargar_dxf(ruta_dxf)
    except Exception as e:
        st.error(f'No se pudo leer el DXF: {e}')
        st.stop()

resumen = resumen_general(doc)

# ───────────────────────── KPIs ─────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric('Version DXF', f"{resumen['version_dxf']} ({resumen['release']})")
c2.metric('Entidades (modelspace)', resumen['n_entidades_modelspace'])
c3.metric('Capas', resumen['n_capas'])
c4.metric('Bloques', resumen['n_bloques'])
c5.metric('Unidades', resumen['unidades'])

if resumen['bbox'] is not None:
    bb = resumen['bbox']
    st.caption(
        f"Bounding box modelspace: "
        f"X [{bb[0]:.2f} .. {bb[2]:.2f}]  ·  "
        f"Y [{bb[1]:.2f} .. {bb[3]:.2f}]  ·  "
        f"ancho **{resumen['ancho']:.2f}** × alto **{resumen['alto']:.2f}** "
        f"({resumen['unidades']})"
    )

st.divider()

# ───────────────────────── Tabs ─────────────────────────
tab_grafica, tab_capas, tab_entidades, tab_bloques, tab_texto, tab_dim = st.tabs([
    'Vista grafica',
    'Capas',
    'Entidades',
    'Bloques',
    'Textos',
    'Dimensiones',
])


with tab_grafica:
    st.markdown(f"<div class='puccetti-h'>Render del modelspace</div>",
                unsafe_allow_html=True)

    capas_disponibles = sorted([c.dxf.name for c in doc.layers])
    capas_sel = st.multiselect(
        'Capas a mostrar (vacio = todas)', capas_disponibles, default=[]
    )

    col_btn, col_dl = st.columns([1, 1])
    with col_btn:
        renderizar = st.button('Renderizar', type='primary',
                               use_container_width=True)

    if renderizar:
        with st.spinner('Renderizando...'):
            if capas_sel:
                # Recarga el doc para no arrastrar mutaciones de filtrados previos.
                doc_render = cargar_dxf(ruta_dxf)
                png = render_capa_png(doc_render, capas_sel,
                                      fondo=fondo, ancho_px=ancho)
            else:
                png = render_png(doc, fondo=fondo, ancho_px=ancho)
        st.session_state['_dxf_png'] = png

    png = st.session_state.get('_dxf_png')
    if png:
        st.image(png, use_container_width=True,
                 caption=f"{subida.name}"
                         f"{' — capas: ' + ', '.join(capas_sel) if capas_sel else ''}")
        with col_dl:
            st.download_button(
                'Descargar PNG', png,
                file_name=os.path.splitext(subida.name)[0] + '.png',
                mime='image/png', use_container_width=True,
            )
    else:
        st.caption('Pulsa **Renderizar** para generar la vista grafica.')


with tab_capas:
    st.markdown(f"<div class='puccetti-h'>Capas del archivo</div>",
                unsafe_allow_html=True)
    df_capas = tabla_capas(doc)
    st.dataframe(df_capas, use_container_width=True, hide_index=True)
    st.download_button(
        'Descargar capas (CSV)', df_capas.to_csv(index=False).encode('utf-8'),
        file_name='capas.csv', mime='text/csv',
    )


with tab_entidades:
    st.markdown(f"<div class='puccetti-h'>Entidades del modelspace</div>",
                unsafe_allow_html=True)
    capas_disponibles = ['(todas)'] + sorted([c.dxf.name for c in doc.layers])
    capa_filtro = st.selectbox('Filtrar por capa', capas_disponibles, index=0)
    df_ent = tabla_entidades(doc,
                             capa=None if capa_filtro == '(todas)' else capa_filtro)
    st.caption(f'{len(df_ent)} entidades')
    if not df_ent.empty:
        st.dataframe(df_ent, use_container_width=True, hide_index=True)
        # Resumen por tipo
        st.markdown('**Conteo por tipo de entidad**')
        st.dataframe(
            df_ent.groupby('tipo').size().reset_index(name='n')
                  .sort_values('n', ascending=False),
            use_container_width=True, hide_index=True,
        )
        st.download_button(
            'Descargar entidades (CSV)',
            df_ent.to_csv(index=False).encode('utf-8'),
            file_name='entidades.csv', mime='text/csv',
        )
    else:
        st.info('No hay entidades para esta seleccion.')


with tab_bloques:
    st.markdown(f"<div class='puccetti-h'>Bloques definidos</div>",
                unsafe_allow_html=True)
    df_bk = tabla_bloques(doc)
    if df_bk.empty:
        st.info('El archivo no tiene bloques de usuario.')
    else:
        st.dataframe(df_bk, use_container_width=True, hide_index=True)
        st.download_button(
            'Descargar bloques (CSV)', df_bk.to_csv(index=False).encode('utf-8'),
            file_name='bloques.csv', mime='text/csv',
        )


with tab_texto:
    st.markdown(f"<div class='puccetti-h'>Textos (TEXT / MTEXT)</div>",
                unsafe_allow_html=True)
    df_tx = tabla_textos(doc)
    if df_tx.empty:
        st.info('No hay entidades de texto en el modelspace.')
    else:
        st.dataframe(df_tx, use_container_width=True, hide_index=True)
        st.download_button(
            'Descargar textos (CSV)', df_tx.to_csv(index=False).encode('utf-8'),
            file_name='textos.csv', mime='text/csv',
        )


with tab_dim:
    st.markdown(f"<div class='puccetti-h'>Cotas (DIMENSION)</div>",
                unsafe_allow_html=True)
    df_dim = tabla_dimensiones(doc)
    if df_dim.empty:
        st.info('No hay entidades DIMENSION en el modelspace.')
    else:
        st.dataframe(df_dim, use_container_width=True, hide_index=True)
        st.download_button(
            'Descargar cotas (CSV)', df_dim.to_csv(index=False).encode('utf-8'),
            file_name='dimensiones.csv', mime='text/csv',
        )


st.divider()
st.caption(
    'Geometria: longitudes y areas se calculan por entidad cuando aplica '
    '(LINE, LWPOLYLINE, POLYLINE, CIRCLE, ARC, ELLIPSE). El render usa el '
    'motor de dibujo de ezdxf sobre matplotlib.'
)
