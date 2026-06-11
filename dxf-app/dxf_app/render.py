"""Render grafico del DXF usando ezdxf + matplotlib.

Devuelve PNG en bytes (usable directamente con st.image / st.download_button).
"""
from __future__ import annotations

import io

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.document import Drawing


def _filtrar_capas(doc: Drawing, capas: list[str] | None) -> None:
    """Apaga (en memoria) las capas no incluidas en la lista."""
    if capas is None:
        return
    permitidas = set(capas)
    for capa in doc.layers:
        if capa.dxf.name not in permitidas:
            capa.off()


def _render(doc: Drawing, capas: list[str] | None,
            fondo: str, ancho_px: int, dpi: int) -> bytes:
    if capas is not None:
        _filtrar_capas(doc, capas)

    fig, ax = plt.subplots(figsize=(ancho_px / dpi, ancho_px / dpi), dpi=dpi)
    fig.patch.set_facecolor(fondo)
    ax.set_facecolor(fondo)

    ctx = RenderContext(doc)
    backend = MatplotlibBackend(ax)
    Frontend(ctx, backend).draw_layout(doc.modelspace(), finalize=True)

    ax.set_aspect('equal')
    ax.axis('off')

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight',
                facecolor=fondo, pad_inches=0.1)
    plt.close(fig)
    return buf.getvalue()


def render_png(doc: Drawing, fondo: str = '#FFFFFF',
               ancho_px: int = 1400, dpi: int = 150) -> bytes:
    """Render completo del modelspace."""
    return _render(doc, None, fondo, ancho_px, dpi)


def render_capa_png(doc: Drawing, capas: list[str],
                    fondo: str = '#FFFFFF',
                    ancho_px: int = 1400, dpi: int = 150) -> bytes:
    """Render solo de las capas indicadas.

    NOTA: apaga capas en el doc (en memoria). Si vas a renderizar varias
    selecciones distintas, recarga el doc con `cargar_dxf` entre llamadas.
    """
    return _render(doc, capas, fondo, ancho_px, dpi)
