# puccetti-app

App de prefactibilidad inmobiliaria para **edificio plurifamiliar de vivienda**
sobre **cualquier parcela catastral** (por referencia catastral, por coordenadas
o desde la muestra cacheada de Sevilla).

Cumple el alcance acordado:

- **Parcela**: por **referencia catastral** o **coordenadas** (descarga del
  Catastro INSPIRE WFS, 1-2 consultas) o desde la muestra offline. El motor
  calcula sobre cualquier polígono.
- **§2.1** Clasificación automática de fachadas vs medianeras (sondeo perpendicular)
- **§2.3/§2.4** Nº de viviendas **calculado desde la edificabilidad** (no a mano):
  techo máximo, plantas que caben, y tamaño de vivienda del Anexo I.5 → nº de unidades.
- **§2.4** Huella + plantas + patios interiores cuando la profundidad lo exige
- **§2.5** Edificio **plurifamiliar**: núcleo vertical + pasillo común + troceado
  en N viviendas (Anexo II). *La vivienda unifamiliar se ha retirado del flujo.*
- **§2.6** Parámetros de diseño configurables desde la UI
- **§2.7** Tabla de superficies en tiempo real (construida vs útil)

Reglas del Anexo II aplicadas al pie de la letra: **A2.1** núcleo con vestíbulo de
círculo libre Ø1.50; **A2.3** acceso de cada vivienda desde el pasillo común;
**A2.4** medianeras sin huecos; **A2.5** las estancias principales (salón,
dormitorios) ventilan **a fachada** — el patio mínimo de 12 m² solo ventila
cocina/baños, nunca sustituye a la fachada de una vivienda.

## Algoritmo de distribución

1. Frame alineado al lado largo del footprint
2. Vestíbulo pegado a la fachada (extremo X mínimo)
3. Zona pública (salón + cocina): franja vertical tras el vestíbulo
4. **Pasillo único recto** horizontal central
5. Dormitorios arriba + baños abajo del pasillo, distribuidos con Squarified
   Treemap (aspect ratio cercano a 1)
6. Fitness multicriterio: genera N candidatos con seeds distintos y devuelve el mejor

## Quick start

```powershell
pip install -r requirements.txt
python scripts/fetch_parcelas.py        # 1 consulta al Catastro, idempotente
streamlit run app.py
```

## Estructura

```
puccetti-app/
├── app.py                                  Streamlit UI
├── requirements.txt
├── data/
│   └── parcelas_sevilla.gpkg               10 muestra + 200 contexto
├── scripts/
│   └── fetch_parcelas.py                   single-shot WFS INSPIRE
└── puccetti/
    ├── catastro.py                         cliente WFS
    ├── config.py            §2.6           ParametrosDiseno/Urbanismo/Programa
    ├── parcelas.py          §2.1           load + simplify + fachadas
    ├── envolvente.py        §2.4           huella + plantas + patios
    ├── programa.py          Anexo I.5      programa por n_dorms y área
    ├── adyacencias.py       A2.2           grafo físico + validación
    ├── grafo_funcional.py   A2.2           grafo de adyacencias REQUERIDAS
    ├── treemap.py                          Squarified Treemap
    ├── fitness.py                          score multicriterio 0-100
    ├── distributor.py                      rule-based + N candidatos (unifamiliar)
    ├── macro_layout.py      §2.4/§2.5      PLURIFAMILIAR: núcleo + pasillo + N viviendas
    ├── serializacion.py     §2.5/§2.7      JSON del edificio + tabla superficies/planta
    ├── svg_render.py        §2.5           render SVG de la planta tipo
    └── viz.py                              render matplotlib
└── scripts/
    └── demo_plurifamiliar.py               demo sin API (gpkg cacheado) -> output/
```

## Plurifamiliar (§2.4/§2.5) — varias viviendas por planta

`macro_layout.py` opera un nivel por encima de `distributor.py`: en vez de tratar
la planta como una sola vivienda, la **trocea en N unidades** servidas por:

- **Núcleo vertical** (escalera + ascensor + vestíbulo con círculo libre Ø1.50 m
  verificado por radio inscrito real), pegado a la fachada de acceso.
- **Pasillo común** recto ≥1.20 m que conecta el núcleo con todas las viviendas.
- **Troceado** en bandas a lo largo del pasillo. Explora 4 estrategias
  (eje X/Y × single/double-loaded) y devuelve la de mayor *fitness*.

Cada vivienda se valida: acceso directo al pasillo, ventilación con un lado en
**fachada o patio** (hueco ≥10% del útil) y mínimos del Anexo I.5. El área
sobrante de los salientes del polígono se **absorbe** en la vivienda adyacente
para no dejar huecos muertos. Salida: estructura **JSON** + **SVG** de la planta
tipo + cuadro de superficies por planta (construida vs útil). Pestaña
"Plurifamiliar (SVG)" en la app.

Pruébalo sin tocar el Catastro:

```powershell
python scripts/demo_plurifamiliar.py 0 2 1   # parcela_idx  n_viviendas  n_dorms
```

## Programa de vivienda configurable (§2.5 Anexo I.5)

Según el PDF, el usuario controla:

- **n_dormitorios**: 0 (estudio), 1, 2, 3, 4, 5 — slider en la UI
- **salón-cocina open plan**: integrado o independiente (A2.2 lo permite)

El resto del programa se deriva automáticamente del Anexo I.5:

- **Salón**: tamaño mínimo según n_dormitorios (14, 16, 18, 20, 24 m²)
- **Cocina**: ≥7 m² independiente
- **Baños**: 1 si vivienda <70 m², 2 si >70 m² (regla dura)
- **Dormitorios**: ≥8 m² individual, ≥12 m² al menos uno
- **Pasillo**: ≥0.90 m de ancho libre

## Limitaciones

- El troceado plurifamiliar usa bandas rectangulares: en polígonos muy
  irregulares las viviendas salen no convexas (las absorbe, pero no optimiza
  forma). Las viviendas no llevan aún distribución interior de estancias
  (reutilizar `distributor.py` por unidad es el siguiente paso natural).
- El **patio** se abre cuando la envolvente detecta profundidad excesiva
  (`profundidad_max_sin_patio`, slider) y el macro-layout lo coloca como vacío
  pegado al pasillo en la banda ciega. Es **un solo patio**: viviendas alejadas
  de él pueden quedar sin ventilar y se marcan como incidencia.
- La **planta tipo** se genera una vez y se replica en todos los niveles (misma
  huella por planta); no hay aún ático retranqueado ni PB diferenciada.
- Sin uso hotelero ni apartamentos turísticos (sólo vivienda)
- Sin informe PDF/DXF (§2.10) pendiente
- Sin persistencia de proyectos (§2.11) pendiente
