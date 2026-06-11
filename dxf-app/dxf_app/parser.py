"""Lectura de archivos DXF y extraccion de datos a tablas.

Usa ezdxf. No mantiene estado: cada funcion recibe el `doc` ya cargado.
Devuelve DataFrames listos para mostrar en Streamlit y/o exportar.
"""
from __future__ import annotations

import math
from typing import Any

import ezdxf
import pandas as pd
from ezdxf.bbox import extents
from ezdxf.document import Drawing

# Mapa AutoCAD Color Index (ACI) -> codigo hex aproximado para los 16 primeros.
# Para los demas devolvemos None y se renderizan en gris/dorado por defecto.
ACI_HEX = {
    0: '#000000', 1: '#FF0000', 2: '#FFFF00', 3: '#00FF00', 4: '#00FFFF',
    5: '#0000FF', 6: '#FF00FF', 7: '#FFFFFF', 8: '#414141', 9: '#808080',
    10: '#FF0000', 11: '#FFAAAA', 12: '#BD0000', 13: '#BD7E7E', 14: '#810000',
    15: '#815656',
}

UNIDADES = {
    0: 'sin definir', 1: 'pulgadas', 2: 'pies', 3: 'millas', 4: 'mm',
    5: 'cm', 6: 'm', 7: 'km', 8: 'micras', 9: 'mils', 10: 'yardas',
}


def cargar_dxf(path: str) -> Drawing:
    """Carga un archivo .dxf y lanza auditoria de recuperacion si falla."""
    try:
        return ezdxf.readfile(path)
    except ezdxf.DXFStructureError:
        from ezdxf import recover
        doc, _ = recover.readfile(path)
        return doc


# ---- Resumen general ------------------------------------------------------

def bounds_modelspace(doc: Drawing) -> tuple[float, float, float, float] | None:
    """Bounding box del modelspace en coordenadas DXF. None si no calculable."""
    try:
        ext = extents(doc.modelspace(), fast=True)
        if not ext.has_data:
            return None
        return (ext.extmin.x, ext.extmin.y, ext.extmax.x, ext.extmax.y)
    except Exception:
        return None


def resumen_general(doc: Drawing) -> dict[str, Any]:
    """KPIs de cabecera: version, unidades, n entidades/capas/bloques, bbox."""
    msp = doc.modelspace()
    n_entidades = sum(1 for _ in msp)
    n_capas = len(doc.layers)
    n_bloques = sum(1 for b in doc.blocks if not b.name.startswith('*'))
    unidades_id = doc.header.get('$INSUNITS', 0)

    bb = bounds_modelspace(doc)
    if bb is not None:
        ancho = bb[2] - bb[0]
        alto = bb[3] - bb[1]
    else:
        ancho = alto = None

    return {
        'version_dxf': doc.dxfversion,
        'release': ezdxf.const.acad_release.get(doc.dxfversion, '?'),
        'unidades': UNIDADES.get(unidades_id, f'codigo {unidades_id}'),
        'n_entidades_modelspace': n_entidades,
        'n_capas': n_capas,
        'n_bloques': n_bloques,
        'bbox': bb,
        'ancho': ancho,
        'alto': alto,
    }


# ---- Helpers de geometria -------------------------------------------------

def _aci_color(aci: int) -> str:
    """Devuelve hex aproximado del ACI; si no se conoce, gris medio."""
    return ACI_HEX.get(int(aci), '#888888')


def _longitud_lwpolyline(e) -> float:
    pts = list(e.get_points('xy'))
    if e.closed and pts:
        pts = pts + [pts[0]]
    return sum(math.hypot(pts[i + 1][0] - pts[i][0],
                          pts[i + 1][1] - pts[i][1])
               for i in range(len(pts) - 1))


def _longitud_polyline(e) -> float:
    pts = [v.dxf.location for v in e.vertices]
    if e.is_closed and pts:
        pts = pts + [pts[0]]
    return sum(math.hypot(pts[i + 1].x - pts[i].x,
                          pts[i + 1].y - pts[i].y)
               for i in range(len(pts) - 1))


def _area_lwpolyline(e) -> float:
    if not e.closed:
        return 0.0
    pts = list(e.get_points('xy'))
    n = len(pts)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def _metricas_entidad(e) -> tuple[float, float]:
    """Devuelve (longitud, area). 0 si no aplica al tipo."""
    t = e.dxftype()
    try:
        if t == 'LINE':
            d = e.dxf.start.distance(e.dxf.end)
            return d, 0.0
        if t == 'LWPOLYLINE':
            return _longitud_lwpolyline(e), _area_lwpolyline(e)
        if t == 'POLYLINE':
            return _longitud_polyline(e), 0.0
        if t == 'CIRCLE':
            r = e.dxf.radius
            return 2 * math.pi * r, math.pi * r * r
        if t == 'ARC':
            r = e.dxf.radius
            ang = (e.dxf.end_angle - e.dxf.start_angle) % 360
            return 2 * math.pi * r * ang / 360.0, 0.0
        if t == 'ELLIPSE':
            a = abs(e.dxf.major_axis.magnitude)
            b = a * e.dxf.ratio
            # aprox Ramanujan
            h = ((a - b) / (a + b)) ** 2 if (a + b) else 0
            per = math.pi * (a + b) * (1 + 3 * h / (10 + math.sqrt(4 - 3 * h)))
            return per, math.pi * a * b
    except Exception:
        pass
    return 0.0, 0.0


# ---- Tablas ---------------------------------------------------------------

def tabla_capas(doc: Drawing) -> pd.DataFrame:
    """Por capa: color, estado, nº entidades, longitud y area totales."""
    msp = doc.modelspace()
    stats: dict[str, dict[str, Any]] = {}
    for e in msp:
        capa = e.dxf.layer
        d = stats.setdefault(capa, {'n': 0, 'long': 0.0, 'area': 0.0, 'tipos': set()})
        L, A = _metricas_entidad(e)
        d['n'] += 1
        d['long'] += L
        d['area'] += A
        d['tipos'].add(e.dxftype())

    filas = []
    for capa in doc.layers:
        nombre = capa.dxf.name
        d = stats.get(nombre, {'n': 0, 'long': 0.0, 'area': 0.0, 'tipos': set()})
        filas.append({
            'capa': nombre,
            'color_aci': capa.dxf.color,
            'color_hex': _aci_color(capa.dxf.color),
            'visible': not capa.is_off(),
            'congelada': capa.is_frozen(),
            'bloqueada': capa.is_locked(),
            'n_entidades': d['n'],
            'longitud_total': round(d['long'], 3),
            'area_total': round(d['area'], 3),
            'tipos': ', '.join(sorted(d['tipos'])) if d['tipos'] else '',
        })
    return pd.DataFrame(filas).sort_values('n_entidades', ascending=False).reset_index(drop=True)


def tabla_entidades(doc: Drawing, capa: str | None = None) -> pd.DataFrame:
    """Una fila por entidad del modelspace. Filtra opcionalmente por capa."""
    msp = doc.modelspace()
    filas = []
    for e in msp:
        if capa is not None and e.dxf.layer != capa:
            continue
        L, A = _metricas_entidad(e)
        t = e.dxftype()
        info: dict[str, Any] = {
            'handle': e.dxf.handle,
            'tipo': t,
            'capa': e.dxf.layer,
            'color_aci': getattr(e.dxf, 'color', 256),
            'longitud': round(L, 3) if L else None,
            'area': round(A, 3) if A else None,
        }
        try:
            if t == 'LINE':
                info['x1'], info['y1'] = round(e.dxf.start.x, 3), round(e.dxf.start.y, 3)
                info['x2'], info['y2'] = round(e.dxf.end.x, 3), round(e.dxf.end.y, 3)
            elif t in ('CIRCLE', 'ARC'):
                info['cx'], info['cy'] = round(e.dxf.center.x, 3), round(e.dxf.center.y, 3)
                info['radio'] = round(e.dxf.radius, 3)
                if t == 'ARC':
                    info['ang_ini'] = round(e.dxf.start_angle, 2)
                    info['ang_fin'] = round(e.dxf.end_angle, 2)
            elif t == 'LWPOLYLINE':
                info['n_vertices'] = len(e)
                info['cerrada'] = bool(e.closed)
            elif t == 'POLYLINE':
                info['n_vertices'] = len(list(e.vertices))
                info['cerrada'] = bool(e.is_closed)
            elif t == 'INSERT':
                info['bloque'] = e.dxf.name
                info['x'], info['y'] = round(e.dxf.insert.x, 3), round(e.dxf.insert.y, 3)
            elif t in ('TEXT', 'MTEXT'):
                txt = e.dxf.text if t == 'TEXT' else e.text
                info['texto'] = (txt or '')[:80]
        except Exception:
            pass
        filas.append(info)
    return pd.DataFrame(filas)


def tabla_bloques(doc: Drawing) -> pd.DataFrame:
    """Bloques definidos: nombre, nº entidades, nº inserts en modelspace."""
    inserts_por_bloque: dict[str, int] = {}
    for e in doc.modelspace():
        if e.dxftype() == 'INSERT':
            inserts_por_bloque[e.dxf.name] = inserts_por_bloque.get(e.dxf.name, 0) + 1

    filas = []
    for b in doc.blocks:
        if b.name.startswith('*'):
            continue
        n_ent = sum(1 for _ in b)
        filas.append({
            'bloque': b.name,
            'n_entidades': n_ent,
            'n_inserts_modelspace': inserts_por_bloque.get(b.name, 0),
        })
    return pd.DataFrame(filas).sort_values('n_inserts_modelspace', ascending=False).reset_index(drop=True)


def tabla_textos(doc: Drawing) -> pd.DataFrame:
    """Todos los TEXT/MTEXT del modelspace con posicion y altura."""
    filas = []
    for e in doc.modelspace():
        t = e.dxftype()
        if t == 'TEXT':
            filas.append({
                'tipo': 'TEXT', 'capa': e.dxf.layer,
                'texto': e.dxf.text,
                'x': round(e.dxf.insert.x, 3), 'y': round(e.dxf.insert.y, 3),
                'altura': round(e.dxf.height, 3),
                'rotacion': round(e.dxf.rotation, 2),
            })
        elif t == 'MTEXT':
            filas.append({
                'tipo': 'MTEXT', 'capa': e.dxf.layer,
                'texto': (e.text or '').replace('\n', ' / ')[:200],
                'x': round(e.dxf.insert.x, 3), 'y': round(e.dxf.insert.y, 3),
                'altura': round(e.dxf.char_height, 3),
                'rotacion': round(e.dxf.rotation, 2),
            })
    return pd.DataFrame(filas)


def tabla_dimensiones(doc: Drawing) -> pd.DataFrame:
    """Entidades DIMENSION: tipo, capa, valor medido."""
    filas = []
    for e in doc.modelspace():
        if e.dxftype() != 'DIMENSION':
            continue
        try:
            medida = e.get_measurement()
        except Exception:
            medida = None
        filas.append({
            'capa': e.dxf.layer,
            'estilo': getattr(e.dxf, 'dimstyle', ''),
            'medida': round(medida, 3) if isinstance(medida, (int, float)) else medida,
            'texto': getattr(e.dxf, 'text', '') or '',
        })
    return pd.DataFrame(filas)
