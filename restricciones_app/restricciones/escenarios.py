"""§2.8 — Comparador de escenarios.

Lanza el optimizador 3 veces con los 3 objetivos en paralelo y devuelve los
resultados juntos para que la UI los muestre lado a lado.
"""
from __future__ import annotations
from dataclasses import dataclass

from .modelo import Parcela, PGOU, ProgramaInversor, Costes, Resultado
from .diseno import ParametrosDiseno
from .optimizador import optimizar


@dataclass
class Escenarios:
    max_margen: Resultado
    max_m2_util: Resultado
    max_unidades: Resultado

    def como_lista(self) -> list[tuple[str, Resultado]]:
        return [
            ("Máx. margen económico (€)", self.max_margen),
            ("Máx. superficie útil (m²)", self.max_m2_util),
            ("Máx. nº de unidades", self.max_unidades),
        ]


def comparar_escenarios(parcela: Parcela, pgou: PGOU,
                        diseno: ParametrosDiseno, costes: Costes,
                        programa: ProgramaInversor) -> Escenarios:
    return Escenarios(
        max_margen=optimizar(parcela, pgou, diseno, costes, programa, "margen"),
        max_m2_util=optimizar(parcela, pgou, diseno, costes, programa, "m2_util"),
        max_unidades=optimizar(parcela, pgou, diseno, costes, programa, "n_unidades"),
    )
