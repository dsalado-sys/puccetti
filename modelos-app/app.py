"""modelos-app — de una imagen de plano a su plano 2D animado y su casa 3D.

Sube un PNG de un plano (o elige uno de los generados por puccetti-app). La app
detecta las habitaciones por color (vision), reconstruye sus poligonos y genera:
  - 📐 Plano 2D animado (anime.js)
  - 🏠 Casa 3D extruida (CSS 3D + anime.js, con sliders de camara)

No hay datos hardcoded: todo sale de la imagen.
"""
from __future__ import annotations
import glob
import os
import tempfile

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from ejemplos.imagen_a_planta import extraer_estancias
from ejemplos.animejs_demo import construir_html, construir_html_3d

st.set_page_config(page_title='Plano → 2D + 3D', layout='wide')

st.title('De imagen de plano a 2D animado + casa 3D')
st.caption(
    'Detecta habitaciones por color (vision), reconstruye poligonos y los anima '
    'con anime.js. Sin hardcode — todo sale de la imagen que subas.'
)

# ---- Fuente de la imagen ----
st.sidebar.title('Imagen del plano')

# planos generados por puccetti-app (si existen)
candidatos = sorted(glob.glob(os.path.join('..', 'Python', 'output', 'planta_*.png')))
opciones = ['(subir una imagen)'] + [os.path.basename(p) for p in candidatos]
elegido = st.sidebar.selectbox('Plano de ejemplo', opciones)

subida = st.sidebar.file_uploader('...o sube un PNG/JPG', type=['png', 'jpg', 'jpeg'])

area_total = st.sidebar.slider('Superficie util total (m²)', 20, 300, 80, 5,
    help='El area se reparte proporcional al tamaño de cada habitacion detectada.')

st.sidebar.divider()
st.sidebar.caption(
    'La deteccion segmenta por color: dorado→publica, azul→privada, '
    'verde→servicio, gris→circulacion. Funciona con los planos de puccetti-app '
    'y con cualquier plano de regiones de color solido.'
)

# Resolver la ruta de la imagen a procesar
ruta = None
if subida is not None:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(subida.name)[1])
    tmp.write(subida.read()); tmp.close()
    ruta = tmp.name
    st.caption(f'Procesando imagen subida: **{subida.name}**')
elif elegido != '(subir una imagen)':
    idx = opciones.index(elegido) - 1
    ruta = candidatos[idx]
    st.caption(f'Procesando plano de ejemplo: **{elegido}**')

if ruta is None:
    st.info('Selecciona un plano de ejemplo en la barra lateral o sube una imagen.')
    st.stop()

# ---- Vision: extraer estancias ----
with st.spinner('Detectando habitaciones por color...'):
    estancias = extraer_estancias(ruta, area_util_total_m2=area_total)

if not estancias:
    st.error('No se detectaron regiones de color. ¿Es un plano con habitaciones '
             'coloreadas? Prueba otra imagen.')
    st.stop()

# KPIs
k1, k2, k3 = st.columns(3)
k1.metric('Habitaciones detectadas', len(estancias))
k2.metric('Superficie util (m²)', f'{sum(e.area_m2 for e in estancias):.1f}')
k3.metric('Categorias', len({e.categoria for e in estancias}))

col_img, col_tabla = st.columns([1, 1])
with col_img:
    st.image(ruta, caption='Imagen original', use_container_width=True)
with col_tabla:
    st.markdown('**Estancias detectadas**')
    st.dataframe(pd.DataFrame([{
        'nombre': e.nombre, 'categoria': e.categoria,
        'color': e.color, 'vertices': len(e.puntos),
        'area_m2': e.area_m2,
    } for e in estancias]), use_container_width=True, hide_index=True)

st.divider()

# ---- Renders ----
tab_2d, tab_3d = st.tabs(['📐 Plano 2D', '🏠 Casa 3D'])

with tab_2d:
    st.subheader('Plano 2D reconstruido (poligonos reales)')
    components.html(construir_html(estancias), height=500, scrolling=False)

with tab_3d:
    st.subheader('Casa 3D — prisma extruido de cada habitacion')
    st.markdown(
        '**PDF §2.4**: *"volumetria tridimensional simplificada... imagen '
        'intuitiva del edificio al inversor."*'
    )
    components.html(construir_html_3d(estancias), height=600, scrolling=False)

st.divider()
st.caption(
    'El area por estancia es proporcional a sus pixeles × la superficie total '
    'que indiques (no se hace OCR del texto). La geometria sí es fiel al plano.'
)
