"""Normativa codificada como datos.

Fuente: ``Requisitos_Aplicacion_Arquitectura.pdf`` (Anexos I y II) + §2.6.
Base normativa: Decreto 194/2010 Junta de Andalucía (apartamentos turísticos),
VPO Junta de Andalucía (vivienda), CTE DB SUA, criterios del estudio.
"""
from .superficies import (
    AREAS_SOCIALES_POR_UA,
    REGLAS_VIVIENDA,
    SUPERFICIES_APT_CONJUNTOS,
    SUPERFICIES_APT_EDIFICIOS,
    SUPERFICIES_HOTEL,
    SUPERFICIES_HOTEL_APARTAMENTO,
    SUPERFICIES_VIVIENDA_MAXIMAS,
    SUPERFICIES_VIVIENDA_ESTANCIAS,
    USOS_DISPONIBLES,
    categorias_de_uso,
    tipologias_de_categoria,
)
from .diseno import (
    PARAMETROS_DISENO_DEFAULTS,
    REGLAS_ANEXO_II,
    URBANISMO_DEFAULTS,
)
from .db import (
    get_catalogo as catalogo_normativa,
    init_db,
    reset_db,
    update_valor,
)
