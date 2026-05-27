"""Anexo I — Superficies mínimas Andalucía (Decreto 194/2010 + VPO).

Copia consolidada de las tablas para que `restricciones_app` sea autocontenido.
Fuente original: `frontend/backend/normativa/superficies.py`.
"""
from __future__ import annotations

SUPERFICIES_HOTEL: dict[str, dict[str, float | None]] = {
    "hotel_5e": {"individual": 15, "doble": 20, "triple": 25, "cuadruple": 29, "salon": 12},
    "hotel_4e": {"individual": 13, "doble": 18, "triple": 22, "cuadruple": 26, "salon": 10},
    "hotel_3e": {"individual": 12, "doble": 17, "triple": 21, "cuadruple": 25, "salon": 10},
    "hotel_2e": {"individual": 10, "doble": 15, "triple": 19, "cuadruple": 22, "salon": 9},
    "hotel_1e": {"individual": 10, "doble": 14, "triple": 17, "cuadruple": 20, "salon": 8},
    "hostal_2e": {"individual": 9, "doble": 14, "triple": 17, "cuadruple": 20, "salon": 8},
    "hostal_1e": {"individual": 9, "doble": 13, "triple": 17, "cuadruple": 18, "salon": 8},
    "pension":   {"individual": 9, "doble": 13, "triple": 16, "cuadruple": 18, "salon": 8},
}

AREAS_SOCIALES_POR_UA: dict[str, float | None] = {
    "hotel_5e": 4.0, "hotel_4e": 3.2, "hotel_3e": 3.0,
    "hotel_2e": 2.0, "hotel_1e": 2.0,
    "hostal_2e": 1.5, "hostal_1e": None, "pension": None,
}

SUPERFICIES_HOTEL_APARTAMENTO: dict[str, dict[str, float]] = {
    "hotel_apt_5e": {"dormitorio_doble": 18, "estudio": 33, "salon_comedor_4p": 17},
    "hotel_apt_4e": {"dormitorio_doble": 16, "estudio": 28, "salon_comedor_4p": 16},
    "hotel_apt_3e": {"dormitorio_doble": 15, "estudio": 27, "salon_comedor_4p": 12},
    "hotel_apt_2e": {"dormitorio_doble": 14, "estudio": 23, "salon_comedor_4p": 10},
    "hotel_apt_1e": {"dormitorio_doble": 14, "estudio": 23, "salon_comedor_4p": 10},
}

SUPERFICIES_APT_EDIFICIOS: dict[str, dict[str, float]] = {
    "apt_4llaves": {"estudio": 24, "salon_comedor_4p": 16, "cocina": 8, "bano": 4,
                    "dormitorio_doble": 15, "areas_sociales_por_ua": 2.0,
                    "vestibulo_por_ua_min15ua": 0.5},
    "apt_3llaves": {"estudio": 23, "salon_comedor_4p": 14, "cocina": 7, "bano": 3.5,
                    "dormitorio_doble": 12, "areas_sociales_por_ua": 1.5,
                    "vestibulo_por_ua_min15ua": 0.4},
    "apt_2llaves": {"estudio": 21, "salon_comedor_4p": 12, "cocina": 6, "bano": 3,
                    "dormitorio_doble": 10, "areas_sociales_por_ua": 0.0,
                    "vestibulo_por_ua_min15ua": 0.3},
    "apt_1llave":  {"estudio": 20, "salon_comedor_4p": 10, "cocina": 5, "bano": 3,
                    "dormitorio_doble": 10, "areas_sociales_por_ua": 0.0,
                    "vestibulo_por_ua_min15ua": 0.2},
}

SUPERFICIES_VIVIENDA_MAXIMAS: dict[str, float | None] = {
    "estudio": 25, "vivienda_1d": 60, "vivienda_2d": 70,
    "vivienda_3d": 90, "vivienda_4d_o_mas": 120,
}

# Mínimo útil por tipología de vivienda — práctico, ≥ min Anexo I.5
SUPERFICIES_VIVIENDA_MINIMAS: dict[str, float] = {
    "estudio": 25, "vivienda_1d": 40, "vivienda_2d": 55,
    "vivienda_3d": 70, "vivienda_4d_o_mas": 90,
}

SUPERFICIES_VIVIENDA_ESTANCIAS: dict[str, dict[str, float]] = {
    "vivienda_1d": {"estancia_min_m2": 14, "estancia_comedor_cocina_min_m2": 20},
    "vivienda_2d": {"estancia_min_m2": 16, "estancia_comedor_cocina_min_m2": 20},
    "vivienda_3d": {"estancia_min_m2": 18, "estancia_comedor_cocina_min_m2": 24},
    "vivienda_4d_o_mas": {"estancia_min_m2": 20, "estancia_comedor_cocina_min_m2": 24},
}

REGLAS_VIVIENDA: dict = {
    "dormitorio_min_m2": 8.0,
    "dormitorio_principal_min_m2": 12.0,
    "cocina_independiente_min_m2": 7.0,
    "pasillo_interior_min_ancho_m": 0.9,
    "dos_banos_si_superficie_mayor_m2": 70.0,
}


# Catálogo por uso. Cada entrada: superficie útil "objetivo" por unidad y
# coste/precio relativo. El optimizador itera sobre estas categorías cuando
# el inversor no fija una.
CATALOGO_USOS: dict[str, dict] = {
    "vivienda": {
        "categorias": ["estudio", "vivienda_1d", "vivienda_2d", "vivienda_3d", "vivienda_4d_o_mas"],
        "min": SUPERFICIES_VIVIENDA_MINIMAS,
        "max": SUPERFICIES_VIVIENDA_MAXIMAS,
        "modelo_negocio": "venta",
    },
    "hotelero": {
        "categorias": list(SUPERFICIES_HOTEL.keys()),
        "tipo_principal": "doble",
        "modelo_negocio": "explotacion",
    },
    "hotel_apartamento": {
        "categorias": list(SUPERFICIES_HOTEL_APARTAMENTO.keys()),
        "tipo_principal": "estudio",
        "modelo_negocio": "explotacion",
    },
    "apartamentos_turisticos": {
        "categorias": list(SUPERFICIES_APT_EDIFICIOS.keys()),
        "tipo_principal": "salon_comedor_4p",  # apto 1 dormitorio + salón
        "modelo_negocio": "explotacion",
    },
    "apartamentos_turisticos_conjunto": {
        "categorias": ["apt_2llaves", "apt_1llave"],
        "tipo_principal": "salon_comedor_4p",
        "modelo_negocio": "explotacion",
    },
}


# Factor de precio relativo por categoría (escala 1.0 = base sobre precio_venta_eur_m2).
# Una categoría más alta cobra más €/m².
FACTOR_PRECIO_CATEGORIA: dict[str, float] = {
    "hotel_5e": 1.80, "hotel_4e": 1.45, "hotel_3e": 1.15, "hotel_2e": 0.95, "hotel_1e": 0.85,
    "hostal_2e": 0.80, "hostal_1e": 0.70, "pension": 0.65,
    "hotel_apt_5e": 1.65, "hotel_apt_4e": 1.35, "hotel_apt_3e": 1.10,
    "hotel_apt_2e": 0.95, "hotel_apt_1e": 0.85,
    "apt_4llaves": 1.45, "apt_3llaves": 1.20, "apt_2llaves": 1.00, "apt_1llave": 0.85,
    "apt_conj_2llaves": 1.00, "apt_conj_1llave": 0.85,
    "estudio": 0.90, "vivienda_1d": 0.95, "vivienda_2d": 1.00,
    "vivienda_3d": 1.05, "vivienda_4d_o_mas": 1.10,
}


def area_unidad_objetivo(uso: str, categoria: str) -> float:
    """Devuelve la superficie útil mínima por unidad típica del uso/categoría.

    Para vivienda usa el mínimo práctico. Para hotelero, una doble. Para apt,
    un apartamento de 1 dormitorio (salón_comedor_4p + 1 dormitorio).
    """
    if uso == "vivienda":
        return SUPERFICIES_VIVIENDA_MINIMAS[categoria]
    if uso == "hotelero":
        return SUPERFICIES_HOTEL[categoria]["doble"]
    if uso == "hotel_apartamento":
        return SUPERFICIES_HOTEL_APARTAMENTO[categoria]["estudio"]
    if uso in ("apartamentos_turisticos", "apartamentos_turisticos_conjunto"):
        tabla = SUPERFICIES_APT_EDIFICIOS if uso == "apartamentos_turisticos" else \
            {"apt_2llaves": SUPERFICIES_APT_EDIFICIOS["apt_2llaves"],
             "apt_1llave":  SUPERFICIES_APT_EDIFICIOS["apt_1llave"]}
        c = tabla[categoria]
        # Apartamento 1 dorm = salón + cocina + baño + dormitorio
        return c["salon_comedor_4p"] + c["cocina"] + c["bano"] + c["dormitorio_doble"]
    raise ValueError(f"uso desconocido: {uso}")


def areas_sociales_por_unidad(uso: str, categoria: str) -> float:
    """Superficie de áreas sociales obligatoria por u.a. (recepción, salones...)."""
    if uso == "hotelero":
        v = AREAS_SOCIALES_POR_UA.get(categoria)
        return v or 0.0
    if uso == "apartamentos_turisticos":
        return SUPERFICIES_APT_EDIFICIOS[categoria].get("areas_sociales_por_ua", 0.0) or 0.0
    return 0.0
