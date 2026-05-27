# modelos-app — de imagen de plano a 2D animado + casa 3D

Sube un PNG de un plano (o elige uno de los generados por `puccetti-app`) y la
app **detecta las habitaciones por visión** (segmentación de color), reconstruye
sus polígonos y genera con **anime.js**:

- 📐 **Plano 2D animado** — polígonos reales, aparición secuencial, contador de m²
- 🏠 **Casa 3D** — cada habitación extruida como prisma de su polígono, con
  sliders de cámara (punto de vista + velocidad de rotación en eje X y Z)

**Sin datos hardcoded**: todo sale de la imagen.

## Cómo funciona la visión

`ejemplos/imagen_a_planta.py`:

1. Carga y reduce la imagen (acelera)
2. Cuantiza a colores dominantes (PIL median-cut)
3. Descarta fondo (blanco) y texto/muro/líneas (muy oscuro)
4. Por cada color: máscara → componentes conexos (`scipy.ndimage.label`)
5. Vectoriza cada región a polígono (run-length por filas + `shapely.unary_union`) y simplifica
6. Normaliza al bbox global → coords viewBox 0..100
7. Clasifica categoría por cercanía a la paleta Puccetti (dorado→pública,
   azul→privada, verde→servicio, gris→circulación)
8. Nombra por categoría + tamaño y reparte el área total proporcional a píxeles

Probado sobre `planta_mz410911124245_p0.png` y `_p10.png`: reconstruye 8
estancias cada uno, con áreas casi idénticas a las reales (salón 20.3 vs 20.0).

## Quick start

```powershell
cd modelos-app
pip install -r requirements.txt
streamlit run app.py
```

En la barra lateral: elige un plano de ejemplo (busca en `../Python/output/`)
o sube tu propio PNG/JPG. Ajusta la superficie útil total con el slider.

## Estructura

```
modelos-app/
├── README.md
├── requirements.txt
├── app.py                       Streamlit: uploader + 2 pestañas (2D / 3D)
└── ejemplos/
    ├── planta_demo.py           EstanciaPoly + ejemplo de respaldo
    ├── imagen_a_planta.py       VISIÓN: imagen → list[EstanciaPoly]
    └── animejs_demo.py          render 2D (SVG) + 3D (prisma extruido)
```

## Sliders de la casa 3D

| Slider | Qué controla |
|---|---|
| Punto de vista (inclinación eje X) | ángulo de cámara, 0-90° |
| Velocidad rotación eje Z | órbita horizontal, −120 a 120 °/s |
| Velocidad rotación eje X | vuelco vertical, −120 a 120 °/s |

## Limitaciones honestas

- **El área es proporcional a píxeles × superficie total** que indiques; no se
  hace OCR del texto del plano. La **geometría sí es fiel**
- Detecta **regiones de color sólido**. Planos en blanco y negro (solo líneas)
  no funcionan — necesitan otro pipeline (detección de líneas/Hough)
- Si dos habitaciones comparten exactamente el mismo color y se tocan, se
  fusionan en una región (limitación de la segmentación por color)
- El 3D es un *massing model* con CSS 3D; sin z-buffer real puede haber
  solapes de orden en ángulos extremos. Suficiente para prefactibilidad
