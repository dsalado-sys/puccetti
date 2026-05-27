"""§2.6 — Parámetros de diseño interior + Anexo II — Reglas de diseño.

§2.6 son **defaults configurables** por el técnico para cada proyecto. Anexo II
recoge las reglas obligatorias que el generador debe respetar al producir
distribuciones (accesos, circulación vertical, tipos de muros, patios, etc.).
"""
from __future__ import annotations


# ─── §2.6 — Defaults de diseño interior ──────────────────────────────────────

PARAMETROS_DISENO_DEFAULTS: dict = {
    "muros": {
        "espesor_fachada_m": 0.25,
        "espesor_medianero_m": 0.25,
        "margen_regularizacion_medianero_m": 0.05,
        "espesor_separacion_unidades_m": 0.20,
        "espesor_tabique_interior_m": 0.07,
    },
    "circulacion": {
        "pasillo_min_ancho_m": 1.20,
        "pasillo_min_ancho_vivienda_m": 1.00,
        "vestibulo_diametro_min_m": 1.50,
        "puerta_radio_apertura_m": 0.80,
    },
    "patios": {
        "luz_recta_min_m": 3.0,
        "superficie_min_m2": 12.0,
    },
}


# ─── Anexo II — Reglas de diseño interior (constantes obligatorias) ──────────

# A2.1 — Sistemas de circulación vertical
TIPOLOGIAS_CIRCULACION_VERTICAL: dict[str, str] = {
    "nucleo_vertical": (
        "Escalera y ascensor concentrados en un núcleo, situado centrado o "
        "alineado al lateral. Desde el núcleo se accede a un vestíbulo de "
        "planta que distribuye a las unidades."
    ),
    "pasillos": (
        "El núcleo vertical da paso a pasillos interiores de distribución que "
        "recorren la planta y desde los que se accede a cada unidad. "
        "Tipología más habitual en hoteles y edificios de apartamentos."
    ),
    "galerias": (
        "Similar a pasillos, pero las galerías se sitúan en línea de fachada "
        "exterior o de patio interior, pudiendo ser abiertas. Las galerías "
        "abiertas computan a efectos de superficie de forma diferente a los "
        "espacios cerrados según la normativa urbanística aplicable."
    ),
}


# A2.2 — Reglas de distribución interior de VIVIENDA
REGLAS_DISTRIBUCION_VIVIENDA: list[str] = [
    "Acceso a la vivienda únicamente por el salón o por un vestíbulo de entrada "
    "que comunique directamente con el salón.",
    "Las habitaciones no se conectan directamente al salón ni a la cocina; "
    "siempre desde un pasillo o distribuidor.",
    "La cocina puede ser independiente o estar integrada en el salón (salón-cocina).",
    "Baños y aseos preferentemente con acceso desde el pasillo, no visibles desde el salón. "
    "Nunca se accede al baño desde la cocina.",
    "Al menos uno de los baños no será de acceso exclusivo desde dormitorio (no en suite).",
    "Ancho mínimo de pasillo interior de vivienda: 0,90 m.",
    "Toda estancia distinta de baño/aseo requiere iluminación y ventilación natural "
    "directa a exterior o a patio.",
]


# A2.3 — Reglas de distribución interior HOTELERO / APARTAMENTOS TURÍSTICOS
REGLAS_DISTRIBUCION_HOTELERO: list[str] = [
    "Cada unidad de alojamiento accede directamente desde pasillo o galería del "
    "edificio, nunca desde otra unidad.",
    "Cada unidad tiene su propio baño/aseo interior, salvo pensión y albergue "
    "(donde se admiten baños compartidos fuera de la unidad).",
    "Los núcleos de escaleras y ascensores son de uso exclusivo del establecimiento. "
    "En categorías de hotel, el establecimiento ocupa la totalidad del edificio "
    "o una parte independiente con accesos propios.",
    "Las zonas sociales obligatorias (vestíbulos, salones, desayuno) se sitúan en "
    "planta baja o en plantas accesibles desde el núcleo principal, separadas de "
    "las zonas de alojamiento.",
    "El número máximo de habitaciones/apartamentos por planta lo limita la "
    "capacidad del núcleo de comunicaciones y el ancho de los pasillos.",
]


# A2.4 — Clasificación de muros y separaciones
TIPOS_MURO: dict[str, dict] = {
    "fachada": {
        "etiqueta": "Muro de fachada",
        "descripcion": "Separa el interior del exterior (vía pública, jardín…). "
                       "Puede contener huecos: ventanas, balcones, puerta principal.",
        "admite_huecos": True,
    },
    "medianero": {
        "etiqueta": "Muro medianero",
        "descripcion": "En contacto con edificio colindante o límite de parcela sin "
                       "vía pública. **No admite huecos** (ni ventanas ni puertas).",
        "admite_huecos": False,
    },
    "separacion_unidades": {
        "etiqueta": "Separación entre unidades",
        "descripcion": "Separa dos unidades independientes (viviendas, habitaciones, "
                       "unidad y zona común). Mayor exigencia acústica que la tabiquería.",
        "admite_huecos": True,  # solo puerta entre unidad y zona común
    },
    "tabique_interior": {
        "etiqueta": "Tabiquería interior",
        "descripcion": "Separa estancias dentro de la misma unidad. Menor espesor. "
                       "Sin exigencia acústica entre vecinos.",
        "admite_huecos": True,
    },
    "cerramiento_patio": {
        "etiqueta": "Cerramiento de patio",
        "descripcion": "Puede tratarse como fachada si el patio cumple las "
                       "condiciones normativas de dimensión y ventilación.",
        "admite_huecos": True,
    },
}


# A2.5 — Condiciones de patios interiores
REGLAS_PATIO: dict = {
    "luz_recta_min_m": 3.0,
    "superficie_min_m2": 12.0,
    "ventilacion_estancias_no_principales": True,  # baños, aseos, cocinas, escaleras
    "ventilacion_estancias_principales": False,    # requieren patio mayor o fachada
    "nota": "La normativa urbanística municipal puede establecer condiciones "
            "adicionales en función de la altura del edificio.",
}


REGLAS_ANEXO_II: dict = {
    "circulacion_vertical": TIPOLOGIAS_CIRCULACION_VERTICAL,
    "distribucion_vivienda": REGLAS_DISTRIBUCION_VIVIENDA,
    "distribucion_hotelero": REGLAS_DISTRIBUCION_HOTELERO,
    "tipos_muro": TIPOS_MURO,
    "patios": REGLAS_PATIO,
}


# ─── §2.3 — Defaults de urbanismo ────────────────────────────────────────────
#
# La mayoría de PGOUs españoles no están digitalizados de forma homogénea, así
# que el técnico introducirá estos valores manualmente tras consultar el PGOU
# del municipio. Estos defaults marcan los campos esperados con valores neutros
# (o nulos) para que el formulario sea autoexplicativo.

USOS_URBANISTICOS_PERMITIDOS: list[str] = [
    "residencial",
    "hotelero",
    "terciario",
    "mixto",
    "industrial",
    "equipamiento",
    "sin_definir",
]


URBANISMO_DEFAULTS: dict = {
    "edificabilidad_m2t_m2s": None,
    "plantas_max": None,
    "ocupacion_max_pct": None,
    "retranqueos_m": {
        "frontal": 0,
        "lateral_izquierdo": 0,
        "lateral_derecho": 0,
        "trasero": 0,
    },
    "usos_permitidos": [],
    "patio_min_luz_recta_m": REGLAS_PATIO["luz_recta_min_m"],
    "patio_min_superficie_m2": REGLAS_PATIO["superficie_min_m2"],
    "atico_computa_edificabilidad": False,
    "atico_computa_plantas": True,
    "sotano_computa_edificabilidad": False,
    "sotano_computa_plantas": False,
    "notas": "",
    "fuente": "",       # "PGOU 2018", "input manual del técnico", etc.
    "fecha_consulta": "",  # fecha en la que se consultó el PGOU
}
