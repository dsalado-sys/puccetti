"""restricciones_app — cálculo de prefactibilidad inmobiliaria.

Núcleo: dada una parcela y sus restricciones (urbanísticas, normativas,
diseño y económicas), encuentra el escenario que maximiza el objetivo
elegido (margen €, m² útil o nº unidades).
"""
from .modelo import Parcela, PGOU, ProgramaInversor, Costes, Resultado
from .escenarios import comparar_escenarios
from .optimizador import optimizar

__all__ = [
    "Parcela", "PGOU", "ProgramaInversor", "Costes", "Resultado",
    "comparar_escenarios", "optimizar",
]
