# dxf-app — visor de archivos DXF (tabla + grafica)

Sube un `.dxf` y la app extrae sus datos y los presenta de dos formas:

- **Tabular / numerica** — capas, entidades, bloques, textos y cotas, con
  longitudes y areas calculadas por entidad y resumen por tipo. Exportable a CSV.
- **Grafica** — render del modelspace con el motor de dibujo de
  [ezdxf](https://ezdxf.readthedocs.io/) sobre matplotlib, con filtro por capas
  y descarga del PNG.

## Quick start

```powershell
cd Modulos\dxf-app
pip install -r requirements.txt
streamlit run app.py
```

## Estructura

```
dxf-app/
├── README.md
├── requirements.txt
├── app.py                       Streamlit: uploader + 6 pestañas
└── dxf_app/
    ├── __init__.py
    ├── parser.py                cargar_dxf + tablas (capas, entidades, ...)
    └── render.py                render PNG del modelspace
```

## Pestañas

| Pestaña      | Que muestra                                                       |
|--------------|-------------------------------------------------------------------|
| Vista grafica| Render del modelspace. Multiselect de capas. Descarga PNG.        |
| Capas        | Nombre, color ACI, visibilidad, n entidades, longitud y area total|
| Entidades    | Una fila por entidad (handle, tipo, capa, geometria clave). Filtro|
| Bloques      | Bloques definidos y nº de INSERT en modelspace                    |
| Textos       | TEXT / MTEXT con posicion, altura y rotacion                      |
| Dimensiones  | Entidades DIMENSION con medida calculada                          |

## Que calcula

Para cada entidad se intenta extraer longitud y area cuando aplica:

- `LINE` — longitud
- `LWPOLYLINE` / `POLYLINE` — longitud (suma de segmentos); area si esta cerrada
- `CIRCLE` — circunferencia y area
- `ARC` — longitud de arco
- `ELLIPSE` — perimetro (aprox. Ramanujan) y area

Las demas entidades (INSERT, TEXT, SPLINE, HATCH, ...) se inventarian pero no
se les calcula metrica.

## Notas

- El render apaga capas no seleccionadas modificando el `doc` en memoria; la
  app recarga el archivo entre selecciones para que no se acumulen filtros.
- Los KPIs y el bbox usan `$INSUNITS` del header DXF para mostrar la unidad.
- Las cotas (`DIMENSION.get_measurement()`) pueden devolver `None` para tipos
  no soportados por ezdxf — se muestran tal cual.
