"""Anexo I — Superficies mínimas por uso (Andalucía).

Cada tabla del Anexo I del PDF codificada como dict consultable. Los valores
son **superficies útiles mínimas en m²** según la normativa vigente en
Andalucía en el momento de redacción del documento de requisitos.

Convenciones:
- ``None`` significa que ese tipo de unidad no se contempla en esa categoría
  (las celdas marcadas con "—" en el PDF).
- Los identificadores de tipología son slugs en español, sin tildes ni
  caracteres especiales, para facilitar el uso desde la API.
"""
from __future__ import annotations


# ─── A1.1 — Hoteles, Hostales, Pensiones, Albergues ───────────────────────────

SUPERFICIES_HOTEL: dict[str, dict[str, float | None]] = {
    "hotel_5e": {
        "individual": 15, "doble": 20, "triple": 25, "cuadruple": 29,
        "salon": 12, "multiple": None,
    },
    "hotel_4e": {
        "individual": 13, "doble": 18, "triple": 22, "cuadruple": 26,
        "salon": 10, "multiple": None,
    },
    "hotel_3e": {
        "individual": 12, "doble": 17, "triple": 21, "cuadruple": 25,
        "salon": 10, "multiple": None,
    },
    "hotel_2e": {
        "individual": 10, "doble": 15, "triple": 19, "cuadruple": 22,
        "salon": 9, "multiple": None,
    },
    "hotel_1e": {
        "individual": 10, "doble": 14, "triple": 17, "cuadruple": 20,
        "salon": 8, "multiple": None,
    },
    "hostal_2e": {
        "individual": 9, "doble": 14, "triple": 17, "cuadruple": 20,
        "salon": 8, "multiple": None,
    },
    "hostal_1e": {
        "individual": 9, "doble": 13, "triple": 17, "cuadruple": 18,
        "salon": 8, "multiple": None,
    },
    "pension": {
        "individual": 9, "doble": 13, "triple": 16, "cuadruple": 18,
        "salon": 8, "multiple": None,
    },
    "albergue": {
        "individual": 9, "doble": 13, "triple": None, "cuadruple": None,
        "salon": None, "multiple": True,  # se admite habitación múltiple
    },
}


# Áreas sociales obligatorias en función del número de unidades de alojamiento.
# Valor expresado en m² por unidad de alojamiento (u.a.) — None = sin exigencia.
AREAS_SOCIALES_POR_UA: dict[str, float | None] = {
    "hotel_5e": 4.0,
    "hotel_4e": 3.2,
    "hotel_3e": 3.0,
    "hotel_2e": 2.0,
    "hotel_1e": 2.0,
    "hostal_2e": 1.5,
    "hostal_1e": None,
    "pension": None,
    "albergue": 1.0,  # 1 m² por plaza (no por u.a.)
}


# ─── A1.2 — Hoteles-Apartamento ───────────────────────────────────────────────

SUPERFICIES_HOTEL_APARTAMENTO: dict[str, dict[str, float | None]] = {
    "hotel_apt_5e": {
        "dormitorio_individual": 15, "dormitorio_doble": 18,
        "dormitorio_triple": 22, "dormitorio_cuadruple": 25,
        "estudio": 33, "salon_comedor_4p": 17,
    },
    "hotel_apt_4e": {
        "dormitorio_individual": 13, "dormitorio_doble": 16,
        "dormitorio_triple": 19, "dormitorio_cuadruple": 22,
        "estudio": 28, "salon_comedor_4p": 16,
    },
    "hotel_apt_3e": {
        "dormitorio_individual": 12, "dormitorio_doble": 15,
        "dormitorio_triple": 18, "dormitorio_cuadruple": 21,
        "estudio": 27, "salon_comedor_4p": 12,
    },
    "hotel_apt_2e": {
        "dormitorio_individual": 10, "dormitorio_doble": 14,
        "dormitorio_triple": 17, "dormitorio_cuadruple": 20,
        "estudio": 23, "salon_comedor_4p": 10,
    },
    "hotel_apt_1e": {
        "dormitorio_individual": 10, "dormitorio_doble": 14,
        "dormitorio_triple": 17, "dormitorio_cuadruple": 20,
        "estudio": 23, "salon_comedor_4p": 10,
    },
}


# ─── A1.3 — Apartamentos turísticos: grupo "edificios/complejos" ──────────────
# Decreto 194/2010 Junta de Andalucía.

SUPERFICIES_APT_EDIFICIOS: dict[str, dict[str, float | None]] = {
    "apt_4llaves": {
        "vestibulo_por_ua_min15ua": 0.5,
        "areas_sociales_por_ua": 2.0,
        "dormitorio_individual": 9, "dormitorio_doble": 15,
        "dormitorio_triple": 21, "dormitorio_cuadruple": 27,
        "estudio": 24, "salon_comedor_4p": 16,
        "superficie_adicional_por_plaza": 4,
        "cocina": 8, "bano": 4,
    },
    "apt_3llaves": {
        "vestibulo_por_ua_min15ua": 0.4,
        "areas_sociales_por_ua": 1.5,
        "dormitorio_individual": 8, "dormitorio_doble": 12,
        "dormitorio_triple": 18, "dormitorio_cuadruple": 24,
        "estudio": 23, "salon_comedor_4p": 14,
        "superficie_adicional_por_plaza": 3,
        "cocina": 7, "bano": 3.5,
    },
    "apt_2llaves": {
        "vestibulo_por_ua_min15ua": 0.3,
        "areas_sociales_por_ua": None,
        "dormitorio_individual": 7, "dormitorio_doble": 10,
        "dormitorio_triple": 16, "dormitorio_cuadruple": 22,
        "estudio": 21, "salon_comedor_4p": 12,
        "superficie_adicional_por_plaza": 2.5,
        "cocina": 6, "bano": 3,
    },
    "apt_1llave": {
        "vestibulo_por_ua_min15ua": 0.2,
        "areas_sociales_por_ua": None,
        "dormitorio_individual": 7, "dormitorio_doble": 10,
        "dormitorio_triple": 16, "dormitorio_cuadruple": 22,
        "estudio": 20, "salon_comedor_4p": 10,
        "superficie_adicional_por_plaza": 2,
        "cocina": 5, "bano": 3,
    },
}


# ─── A1.4 — Apartamentos turísticos: grupo "conjuntos" ────────────────────────

SUPERFICIES_APT_CONJUNTOS: dict[str, dict[str, float | bool]] = {
    "apt_conj_2llaves": {
        "dormitorio_individual": 7, "dormitorio_doble": 10,
        "dormitorio_triple": 16, "dormitorio_cuadruple": 22,
        "estudio": 21, "salon_comedor_4p": 12,
        "superficie_adicional_por_plaza": 2.5,
        "cocina": 6, "bano": 3,
        "segundo_bano_obligatorio_si_mas_5_usuarios": True,
    },
    "apt_conj_1llave": {
        "dormitorio_individual": 7, "dormitorio_doble": 10,
        "dormitorio_triple": 16, "dormitorio_cuadruple": 22,
        "estudio": 20, "salon_comedor_4p": 10,
        "superficie_adicional_por_plaza": 2,
        "cocina": 5, "bano": 3,
        "segundo_bano_obligatorio_si_mas_5_usuarios": True,
    },
}


# ─── A1.5 — Vivienda (referencia VPO Junta de Andalucía) ──────────────────────

# Superficie útil MÁXIMA según número de dormitorios.
# El valor "None" significa "la máxima permitida por los Planes de Vivienda vigentes".
SUPERFICIES_VIVIENDA_MAXIMAS: dict[str, float | None] = {
    "estudio": 25,                  # mínimo, excluyendo servicios comunes
    "vivienda_1d": 60,
    "vivienda_2d": 70,
    "vivienda_3d": 90,
    "vivienda_4d_o_mas": None,
}

# Superficie mínima de la estancia principal y de la suma estancia+comedor+cocina.
SUPERFICIES_VIVIENDA_ESTANCIAS: dict[str, dict[str, float]] = {
    "vivienda_1d": {"estancia_min_m2": 14, "estancia_comedor_cocina_min_m2": 20},
    "vivienda_2d": {"estancia_min_m2": 16, "estancia_comedor_cocina_min_m2": 20},
    "vivienda_3d": {"estancia_min_m2": 18, "estancia_comedor_cocina_min_m2": 24},
    "vivienda_4d":  {"estancia_min_m2": 20, "estancia_comedor_cocina_min_m2": 24},
    "vivienda_5d_o_mas": {"estancia_min_m2": 24, "estancia_comedor_cocina_min_m2": 28},
}

# Otras reglas obligatorias de vivienda.
REGLAS_VIVIENDA: dict = {
    "dormitorio_min_m2": 8,
    "dormitorio_principal_min_m2": 12,
    "cocina_independiente_min_m2": 7,
    "pasillo_interior_min_ancho_m": 0.9,
    "iluminacion_min_pct_superficie_util": 10,
    "ventilacion_min_pct_superficie_util": 5,
    "dos_banos_si_superficie_mayor_m2": 70,
}


# ─── Catálogo y helpers ───────────────────────────────────────────────────────

# Estructura del catálogo de usos disponibles, ordenada y con etiquetas legibles
# para la UI. La clave interna se usa en API; la etiqueta para mostrar al técnico.
USOS_DISPONIBLES: dict[str, dict] = {
    "hotelero": {
        "etiqueta": "Hotelero",
        "categorias": {
            "hotel_5e": "Hotel 5★",
            "hotel_4e": "Hotel 4★",
            "hotel_3e": "Hotel 3★",
            "hotel_2e": "Hotel 2★",
            "hotel_1e": "Hotel 1★",
            "hostal_2e": "Hostal 2★",
            "hostal_1e": "Hostal 1★",
            "pension": "Pensión",
            "albergue": "Albergue",
        },
        "tipologias": ("individual", "doble", "triple", "cuadruple", "salon", "multiple"),
        "tabla": "SUPERFICIES_HOTEL",
    },
    "hotel_apartamento": {
        "etiqueta": "Hotel-Apartamento",
        "categorias": {
            "hotel_apt_5e": "Hotel-Apto 5★",
            "hotel_apt_4e": "Hotel-Apto 4★",
            "hotel_apt_3e": "Hotel-Apto 3★",
            "hotel_apt_2e": "Hotel-Apto 2★",
            "hotel_apt_1e": "Hotel-Apto 1★",
        },
        "tipologias": (
            "dormitorio_individual", "dormitorio_doble",
            "dormitorio_triple", "dormitorio_cuadruple",
            "estudio", "salon_comedor_4p",
        ),
        "tabla": "SUPERFICIES_HOTEL_APARTAMENTO",
    },
    "apartamentos_turisticos": {
        "etiqueta": "Apartamentos turísticos (edificios/complejos)",
        "categorias": {
            "apt_4llaves": "4 llaves",
            "apt_3llaves": "3 llaves",
            "apt_2llaves": "2 llaves",
            "apt_1llave": "1 llave",
        },
        "tipologias": (
            "dormitorio_individual", "dormitorio_doble",
            "dormitorio_triple", "dormitorio_cuadruple",
            "estudio", "salon_comedor_4p", "cocina", "bano",
        ),
        "tabla": "SUPERFICIES_APT_EDIFICIOS",
    },
    "apartamentos_turisticos_conjunto": {
        "etiqueta": "Apartamentos turísticos (conjuntos)",
        "categorias": {
            "apt_conj_2llaves": "Conjunto 2 llaves",
            "apt_conj_1llave": "Conjunto 1 llave",
        },
        "tipologias": (
            "dormitorio_individual", "dormitorio_doble",
            "dormitorio_triple", "dormitorio_cuadruple",
            "estudio", "salon_comedor_4p", "cocina", "bano",
        ),
        "tabla": "SUPERFICIES_APT_CONJUNTOS",
    },
    "vivienda": {
        "etiqueta": "Vivienda (referencia VPO Andalucía)",
        "categorias": {
            "estudio": "Estudio",
            "vivienda_1d": "1 dormitorio",
            "vivienda_2d": "2 dormitorios",
            "vivienda_3d": "3 dormitorios",
            "vivienda_4d_o_mas": "4 dormitorios o más",
        },
        "tipologias": (),
        "tabla": "SUPERFICIES_VIVIENDA_MAXIMAS",
    },
}


_TABLAS = {
    "SUPERFICIES_HOTEL": SUPERFICIES_HOTEL,
    "SUPERFICIES_HOTEL_APARTAMENTO": SUPERFICIES_HOTEL_APARTAMENTO,
    "SUPERFICIES_APT_EDIFICIOS": SUPERFICIES_APT_EDIFICIOS,
    "SUPERFICIES_APT_CONJUNTOS": SUPERFICIES_APT_CONJUNTOS,
    "SUPERFICIES_VIVIENDA_MAXIMAS": SUPERFICIES_VIVIENDA_MAXIMAS,
}


def categorias_de_uso(uso: str) -> dict[str, str]:
    return USOS_DISPONIBLES[uso]["categorias"]


def tipologias_de_categoria(uso: str) -> tuple[str, ...]:
    return USOS_DISPONIBLES[uso]["tipologias"]


# Nota: el catálogo serializable (usos + tablas con valores) lo construye ahora
# ``db.get_catalogo()``, que lee los valores numéricos desde SQLite. Estos dicts
# son la fuente de los valores por defecto (seed/reset de la BD).
