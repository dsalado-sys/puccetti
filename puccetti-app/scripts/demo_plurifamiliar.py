"""Demo del motor plurifamiliar SIN tocar el Catastro: usa el gpkg ya cacheado
(`data/parcelas_sevilla.gpkg`). Vuelca SVG + JSON a `output/`.

Uso:
    python scripts/demo_plurifamiliar.py [parcela_idx] [n_viviendas] [n_dorms]

Si no hay gpkg, cae a una parcela sintetica entre medianeras (12 x 28 m).
"""
from __future__ import annotations
import json
import pathlib
import sys

from shapely.geometry import Polygon

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from puccetti.config import (
    Parametros, ParametrosDiseno, ParametrosUrbanisticos, ParametrosPrograma,
)
from puccetti.envolvente import construir_envolvente
from puccetti.macro_layout import generar_edificio
from puccetti.serializacion import (
    edificio_a_dict, tabla_superficies_por_planta, tabla_unidades,
)
from puccetti.svg_render import render_planta_svg, leyenda_svg
from puccetti.parcelas import LadoParcela, simplificar, clasificar_lados


def _parcela_sintetica() -> tuple[Polygon, list[LadoParcela]]:
    """Entre medianeras: 12 m de fachada (frente/fondo) x 28 m de fondo.
    Lados cortos = fachada (calle delante, patio de manzana detras), largos =
    medianera."""
    poly = Polygon([(0, 0), (12, 0), (12, 28), (0, 28)])
    coords = list(poly.exterior.coords)[:-1]
    tipos = ["fachada", "medianera", "fachada", "medianera"]  # y=0, x=12, y=28, x=0
    lados = []
    import math
    for i, p1 in enumerate(coords):
        p2 = coords[(i + 1) % len(coords)]
        lados.append(LadoParcela(
            p1=p1, p2=p2, tipo=tipos[i],
            longitud_m=math.dist(p1, p2),
            azimut=0.0,
        ))
    return poly, lados


def _cargar_real(idx: int):
    from puccetti.parcelas import cargar_parcelas, cargar_contexto
    muestra = cargar_parcelas()
    contexto = cargar_contexto()
    # ordenar por area desc para coger una grande por defecto
    muestra = muestra.assign(_a=muestra.geometry.area).sort_values("_a", ascending=False)
    row = muestra.iloc[min(idx, len(muestra) - 1)]
    parc = simplificar(row.geometry, tolerancia=0.10)
    lados = clasificar_lados(parc, parcelas_vecinas=contexto, dist_probe=1.0)
    rc = row.get("referencia_catastral", "—")
    return parc, lados, str(rc)


def main():
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    n_viv = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    n_dorms = int(sys.argv[3]) if len(sys.argv) > 3 else 2

    try:
        parc, lados, rc = _cargar_real(idx)
        origen = f"gpkg cacheado · RC {rc}"
    except Exception as e:
        print(f"[aviso] sin gpkg ({e}); uso parcela sintetica entre medianeras")
        parc, lados = _parcela_sintetica()
        origen = "sintetica 12x28"

    params = Parametros(
        diseno=ParametrosDiseno(),
        urbanismo=ParametrosUrbanisticos(n_plantas_max=4),
        programa=ParametrosPrograma(
            uso="vivienda", n_dormitorios=n_dorms,
            n_plantas=2, n_viviendas_por_planta=n_viv,
        ),
        seed=42,
    )

    envol = construir_envolvente(parc, lados, params)
    edif = generar_edificio(envol, lados, params, n_viviendas_por_planta=n_viv,
                            seed=42, n_candidatos=10)

    print(f"\n=== Parcela: {origen} · {parc.area:.1f} m² ===")
    print(f"Fachadas: {sum(1 for l in lados if l.tipo=='fachada')}  "
          f"Medianeras: {sum(1 for l in lados if l.tipo=='medianera')}")
    print(f"Plantas: {len(edif.plantas)}  ·  Viviendas totales: {edif.n_viviendas_total}")

    for p in edif.plantas:
        print(f"\n-- {('PB' if p.n==0 else 'P'+str(p.n))}  "
              f"[{p.tipologia}]  score={p.score}  edges={p.edges}")
        nuc = "sí" if p.nucleo and p.nucleo.circulo_ok else "NO"
        print(f"   nucleo circulo libre Ø1.50 ok: {nuc}  ·  "
              f"viviendas: {len(p.unidades)}")
        for u in p.unidades:
            print(f"   {u.id}: util {u.area_util_m2:>5.1f} m² (min {u.area_min_m2:.1f}) "
                  f"acceso={u.acceso_pasillo} vent={u.ventilacion_tipo}"
                  f"({'ok' if u.ventila_ok else 'NO'}) "
                  f"{'CUMPLE' if (u.cumple_min and u.ventila_ok and u.acceso_pasillo) else 'incid.'}")
        if p.incidencias:
            for inc in p.incidencias:
                print(f"   ! {inc}")

    print("\n=== Tabla de superficies por planta ===")
    print(tabla_superficies_por_planta(edif).to_string(index=False))
    print("\n=== Viviendas ===")
    print(tabla_unidades(edif).to_string(index=False))

    # --- volcado ---
    out = ROOT / "output"
    out.mkdir(exist_ok=True)
    data = edificio_a_dict(edif, params)
    (out / "edificio.json").write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    for p in edif.plantas:
        svg = render_planta_svg(
            p, lados=lados,
            titulo=f"{'PB' if p.n==0 else 'P'+str(p.n)} · {len(p.unidades)} viviendas "
                   f"· {p.tipologia} · score {p.score}")
        (out / f"planta_P{p.n}.svg").write_text(svg, encoding="utf-8")
    (out / "leyenda.svg").write_text(leyenda_svg(), encoding="utf-8")
    print(f"\n[ok] escrito en {out}: edificio.json, planta_P*.svg, leyenda.svg")


if __name__ == "__main__":
    main()
