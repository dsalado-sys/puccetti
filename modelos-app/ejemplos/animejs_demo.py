"""Renders 2D y 3D con anime.js a partir de EstanciaPoly (poligonos reales).

  construir_html(estancias)     -> plano 2D animado (SVG polygons)
  construir_html_3d(estancias)  -> casa 3D: cada habitacion se extruye como
                                   PRISMA del poligono real (suelo+techo con
                                   clip-path + una pared por arista).

Si no se pasan estancias, usa el ejemplo de respaldo. anime.js (MIT/CDN) anima
construccion + orbita; el 3D se hace con CSS 3D transforms.
"""
from __future__ import annotations
import math
from .planta_demo import EstanciaPoly, ejemplo_como_poligonos

ANIMEJS_CDN = "https://cdnjs.cloudflare.com/ajax/libs/animejs/3.2.2/anime.min.js"
ALTURA_PLANTA = 22   # unidades de viewBox

COLOR_CAT = {
    'publica': '#F4C66B', 'privada': '#9DBDD9', 'servicio': '#A8D5BA',
    'circulacion': '#D9D9D9', 'otra': '#cccccc',
}


def _color(e: EstanciaPoly) -> str:
    return e.color or COLOR_CAT.get(e.categoria, '#cccccc')


# ============================================================
#  2D — plano animado con poligonos reales
# ============================================================
def construir_html(estancias: list[EstanciaPoly] | None = None) -> str:
    estancias = estancias or ejemplo_como_poligonos()
    total_area = sum(e.area_m2 for e in estancias)

    polys, labels = [], []
    for i, e in enumerate(estancias):
        pts = ' '.join(f'{x:.1f},{y:.1f}' for x, y in e.puntos)
        polys.append(
            f'<polygon class="room" data-idx="{i}" points="{pts}" '
            f'fill="{_color(e)}" stroke="#222" stroke-width="0.4" '
            f'opacity="0" />'
        )
        cx, cy = e.centroide()
        labels.append(
            f'<text class="lbl" data-idx="{i}" x="{cx:.1f}" y="{cy:.1f}" '
            f'text-anchor="middle" dominant-baseline="middle" '
            f'font-size="2.4" fill="#111" opacity="0">{e.nombre}</text>'
        )
    polys_svg, labels_svg = "\n".join(polys), "\n".join(labels)

    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f'<script src="{ANIMEJS_CDN}"></script>'
        '<style>'
        'body{margin:0;font-family:Segoe UI,sans-serif;background:#fafafa;}'
        '.wrap{display:flex;gap:24px;align-items:center;padding:16px;}'
        'svg{background:#fff;border:1px solid #eee;border-radius:8px;}'
        '.contador{font-size:40px;font-weight:700;color:#B8960C;}'
        '.sub{color:#666;font-size:13px;}'
        'button{background:#0A0A0A;color:#fff;border:none;padding:10px 18px;'
        'border-radius:6px;cursor:pointer;font-size:14px;margin-top:12px;}'
        '</style></head><body><div class="wrap">'
        '<svg viewBox="0 0 100 100" width="440" height="440">'
        f'{polys_svg}{labels_svg}</svg>'
        '<div class="panel"><div class="sub">Superficie util detectada</div>'
        '<div class="contador"><span id="cuenta">0</span> m&sup2;</div>'
        f'<div class="sub">{len(estancias)} estancias</div>'
        '<button onclick="reproducir()">&#9654; Reproducir</button></div></div>'
        '<script>'
        f'const TOTAL={total_area:.1f};'
        'function reproducir(){'
        "anime.set('.room',{opacity:0,scale:0.5});anime.set('.lbl',{opacity:0});"
        "document.getElementById('cuenta').innerHTML='0';"
        "anime({targets:'.room',opacity:[0,0.9],scale:[0.5,1],"
        "delay:anime.stagger(140),duration:600,easing:'easeOutBack',"
        "transformOrigin:'50% 50%'});"
        "anime({targets:'.lbl',opacity:[0,1],delay:anime.stagger(140,{start:250}),duration:400});"
        "anime({targets:{v:0},v:TOTAL,duration:1800,easing:'easeOutQuad',"
        "update:function(a){document.getElementById('cuenta').innerHTML=a.animations[0].currentValue.toFixed(1);}});"
        '}'
        'window.addEventListener("load",()=>setTimeout(reproducir,300));'
        '</script></body></html>'
    )


# ============================================================
#  3D — prisma extruido del poligono real
# ============================================================
def _caras_prisma(e: EstanciaPoly, esc: float, H: float) -> str:
    pts = e.puntos
    if len(pts) < 3:
        return ''
    bx0 = min(p[0] for p in pts); by0 = min(p[1] for p in pts)
    bx1 = max(p[0] for p in pts); by1 = max(p[1] for p in pts)
    bw = (bx1 - bx0) or 0.1
    bh = (by1 - by0) or 0.1
    col = _color(e)
    Hpx = H * esc

    # clip-path del suelo/techo relativo al bbox
    clip = 'polygon(' + ', '.join(
        f'{(x - bx0) / bw * 100:.1f}% {(y - by0) / bh * 100:.1f}%' for x, y in pts
    ) + ')'

    base_xy = (f'left:{bx0*esc:.1f}px;top:{by0*esc:.1f}px;'
               f'width:{bw*esc:.1f}px;height:{bh*esc:.1f}px;')

    suelo = (f'<div class="cara" style="{base_xy}background:{col};'
             f'filter:brightness(0.7);clip-path:{clip};transform:translateZ(0px);"></div>')
    techo = (f'<div class="cara" style="{base_xy}background:{col};'
             f'opacity:0.55;clip-path:{clip};transform:translateZ({Hpx:.1f}px);"></div>')

    # una pared por arista
    paredes = []
    n = len(pts)
    for k in range(n):
        x1, y1 = pts[k]
        x2, y2 = pts[(k + 1) % n]
        dx, dy = (x2 - x1) * esc, (y2 - y1) * esc
        L = math.hypot(dx, dy)
        if L < 0.5:
            continue
        ang = math.degrees(math.atan2(dy, dx))
        paredes.append(
            f'<div class="cara" style="left:0;top:0;width:{L:.1f}px;height:{Hpx:.1f}px;'
            f'background:{col};filter:brightness(0.86);transform-origin:0 0;'
            f'transform:translate3d({x1*esc:.1f}px,{y1*esc:.1f}px,0) '
            f'rotateZ({ang:.1f}deg) rotateX(-90deg);"></div>'
        )
    return suelo + techo + ''.join(paredes)


def construir_html_3d(estancias: list[EstanciaPoly] | None = None) -> str:
    estancias = estancias or ejemplo_como_poligonos()
    esc = 3.4
    H = ALTURA_PLANTA
    centro = 50 * esc

    bloques = []
    for i, e in enumerate(estancias):
        caras = _caras_prisma(e, esc, H)
        bloques.append(f'<div class="bloque" data-idx="{i}">{caras}</div>')
    bloques_html = "\n".join(bloques)

    css = (
        'body{margin:0;font-family:Segoe UI,sans-serif;background:#f2f0ec;overflow:hidden;}'
        '.stage{display:flex;gap:20px;align-items:flex-start;padding:16px;}'
        '.viewport{width:520px;height:520px;perspective:1500px;'
        'background:radial-gradient(circle at 50% 40%,#fff,#e7e3db);'
        'border:1px solid #ddd;border-radius:10px;overflow:hidden;}'
        '.casa{position:absolute;left:50%;top:50%;width:0;height:0;'
        'transform-style:preserve-3d;'
        'transform:translate(-50%,-50%) rotateX(58deg) rotateZ(0deg);}'
        f'.planta{{position:absolute;transform-style:preserve-3d;'
        f'transform:translate(-{centro:.1f}px,-{centro:.1f}px);}}'
        '.bloque{position:absolute;transform-style:preserve-3d;'
        'transform:translateZ(-160px);opacity:0;}'
        '.cara{position:absolute;transform-origin:0 0;'
        'border:0.4px solid rgba(0,0,0,0.30);box-sizing:border-box;}'
        '.panel{min-width:210px;}'
        '.sub{color:#666;font-size:13px;line-height:1.5;}'
        'h3{margin:0 0 4px 0;color:#0A0A0A;}'
        'button{background:#0A0A0A;color:#fff;border:none;padding:9px 16px;'
        'border-radius:6px;cursor:pointer;font-size:14px;margin:6px 6px 0 0;}'
        '.ctrl{margin-top:12px;}'
        '.ctrl label{display:block;font-size:12px;color:#333;margin-bottom:3px;font-weight:600;}'
        '.ctrl input[type=range]{width:100%;accent-color:#B8960C;}'
        '.val{color:#B8960C;font-weight:700;}'
    )

    js = (
        'let tiltX=58,velX=0,velZ=30,rotX=0,rotZ=0,paused=false;'
        "const casa=()=>document.querySelector('.casa');"
        "function aplicar(){casa().style.transform="
        "'translate(-50%,-50%) rotateX('+(tiltX+rotX)+'deg) rotateZ('+rotZ+'deg)';}"
        'function frame(){if(!paused){rotZ+=velZ/60;rotX+=velX/60;}aplicar();requestAnimationFrame(frame);}'
        "function construir(){anime.remove('.bloque');"
        "anime.set('.bloque',{translateZ:-160,opacity:0});"
        "anime({targets:'.bloque',translateZ:[-160,0],opacity:[0,1],"
        "delay:anime.stagger(150,{start:300}),duration:900,easing:'easeOutCubic'});}"
        'function toggle(){paused=!paused;}'
        "function setTilt(v){tiltX=parseFloat(v);document.getElementById('vt').innerHTML=v;aplicar();}"
        "function setVelZ(v){velZ=parseFloat(v);document.getElementById('vz').innerHTML=v;}"
        "function setVelX(v){velX=parseFloat(v);document.getElementById('vx').innerHTML=v;}"
        "window.addEventListener('load',()=>{setTimeout(construir,200);requestAnimationFrame(frame);});"
    )

    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f'<script src="{ANIMEJS_CDN}"></script>'
        f'<style>{css}</style></head><body><div class="stage">'
        '<div class="viewport"><div class="casa"><div class="planta">'
        f'{bloques_html}'
        '</div></div></div>'
        '<div class="panel"><h3>Casa 3D (prisma extruido)</h3>'
        '<div class="sub">Cada habitacion se extruye como prisma de su poligono '
        'real. anime.js anima la construccion; los sliders controlan la camara.</div>'
        '<button onclick="construir()">&#9654; Reconstruir</button>'
        '<button onclick="toggle()">&#9208; Pausar / reanudar</button>'
        '<div class="ctrl"><label>Punto de vista &mdash; inclinacion eje X: '
        '<span class="val" id="vt">58</span>&deg;</label>'
        '<input type="range" min="0" max="90" value="58" oninput="setTilt(this.value)"></div>'
        '<div class="ctrl"><label>Velocidad rotacion eje Z: '
        '<span class="val" id="vz">30</span> &deg;/s</label>'
        '<input type="range" min="-120" max="120" value="30" oninput="setVelZ(this.value)"></div>'
        '<div class="ctrl"><label>Velocidad rotacion eje X: '
        '<span class="val" id="vx">0</span> &deg;/s</label>'
        '<input type="range" min="-120" max="120" value="0" oninput="setVelX(this.value)"></div>'
        '</div></div>'
        f'<script>{js}</script></body></html>'
    )
