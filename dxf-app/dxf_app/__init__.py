"""dxf-app — lector, tablas y visor grafico de archivos DXF."""
from .parser import (
    cargar_dxf, resumen_general, bounds_modelspace,
    tabla_capas, tabla_entidades, tabla_bloques, tabla_textos, tabla_dimensiones,
)
from .render import render_png, render_capa_png

__all__ = [
    'cargar_dxf', 'resumen_general', 'bounds_modelspace',
    'tabla_capas', 'tabla_entidades', 'tabla_bloques', 'tabla_textos', 'tabla_dimensiones',
    'render_png', 'render_capa_png',
]
