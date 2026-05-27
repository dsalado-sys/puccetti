# restricciones_app

Calculadora de prefactibilidad inmobiliaria centrada en **maximizar** el
aprovechamiento de una parcela dadas sus restricciones urbanísticas y normativas
de diseño interior (Anexos I/II — Andalucía).

Cubre las secciones §2.3 a §2.10 del documento `Requisitos_Aplicacion_Arquitectura.pdf`
con foco en cálculo (no representación gráfica).

## Alcance

| §    | Funcionalidad                                                            |
| ---- | ------------------------------------------------------------------------ |
| 2.3  | Análisis urbanístico (edificabilidad, ocupación, plantas, retranqueos)   |
| 2.4  | Cálculo de envolvente edificatoria (huella, plantas, patios)             |
| 2.5  | Distribución paramétrica (programa por uso, nº unidades, áreas mínimas)  |
| 2.6  | Parámetros de diseño interior configurables                              |
| 2.7  | Tabla de superficies agregada (construida, útil, circulación, muros)     |
| 2.8  | Panel de parámetros activos + comparador de escenarios (3 objetivos)     |
| 2.9  | Viabilidad económica básica (ingresos, costes, margen, ROI)              |
| 2.10 | Generación de informe PDF + exportación XLSX                             |

## Objetivos de optimización

El optimizador devuelve el escenario óptimo según tres objetivos en paralelo:

1. **Margen económico (€)** — ingresos por venta o renta − coste de construcción
2. **Superficie útil (m²)** — m² útil total de unidades dentro de los mínimos
3. **Nº unidades** — máximo número de viviendas, habitaciones o llaves

## Modos de entrada de datos

- **Desde `puccetti-app`**: lee `puccetti-app/data/parcelas_sevilla.gpkg` (10
  parcelas de muestra de Sevilla) y permite elegir una.
- **Manual**: formulario para superficie, perímetro, profundidad media,
  orientación fachada principal y nº de fachadas vs medianeras.

## Quick start

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Estructura

```
restricciones_app/
├── app.py                          Streamlit UI
├── requirements.txt
└── restricciones/
    ├── modelo.py                   Pydantic: Parcela, PGOU, Programa, Costes
    ├── normativa.py                Anexo I (superficies mínimas Andalucía)
    ├── diseno.py        §2.6       Parámetros de diseño interior
    ├── urbanismo.py     §2.3       Validación urbanística + alertas
    ├── envolvente.py    §2.4       Cálculo edificabilidad/ocupación/patios
    ├── distribucion.py  §2.5       Programa por uso + nº unidades
    ├── superficies.py   §2.7       Tabla agregada
    ├── viabilidad.py    §2.9       Cálculo financiero
    ├── optimizador.py              Búsqueda del óptimo
    ├── escenarios.py    §2.8       Comparador 3 objetivos
    ├── informe.py       §2.10      PDF + XLSX
    └── datos.py                    Carga parcelas (GPKG o manual)
```
