"""Estado mutable por proyecto (activo).

Cada ``ProyectoEstado`` envuelve un ``Activo`` (datos catastrales inmutables)
con la información que el técnico va introduciendo y editando durante el
análisis: uso deseado, parámetros urbanísticos, parámetros de diseño.

Persistencia: por ahora vive en memoria (``_PROYECTOS`` dict). Cuando se
implemente §2.11 se sustituirá por SQLite/Postgres, manteniendo esta misma
API pública.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, Optional

from .normativa import (
    PARAMETROS_DISENO_DEFAULTS,
    URBANISMO_DEFAULTS,
    USOS_DISPONIBLES,
)


@dataclass
class ProyectoEstado:
    activo_id: str
    uso: Optional[str] = None             # clave en USOS_DISPONIBLES
    categoria: Optional[str] = None       # clave en USOS_DISPONIBLES[uso]["categorias"]
    urbanismo: dict = field(default_factory=lambda: copy.deepcopy(URBANISMO_DEFAULTS))
    diseno: dict = field(default_factory=lambda: copy.deepcopy(PARAMETROS_DISENO_DEFAULTS))

    def to_dict(self) -> dict:
        return {
            "activo_id": self.activo_id,
            "uso": self.uso,
            "categoria": self.categoria,
            "urbanismo": self.urbanismo,
            "diseno": self.diseno,
        }


_PROYECTOS: Dict[str, ProyectoEstado] = {}


def obtener_o_crear(activo_id: str) -> ProyectoEstado:
    estado = _PROYECTOS.get(activo_id)
    if estado is None:
        estado = ProyectoEstado(activo_id=activo_id)
        _PROYECTOS[activo_id] = estado
    return estado


def actualizar_uso(activo_id: str, uso: Optional[str], categoria: Optional[str]) -> ProyectoEstado:
    estado = obtener_o_crear(activo_id)
    if uso is not None and uso not in USOS_DISPONIBLES:
        raise ValueError(f"Uso desconocido: {uso!r}")
    if uso and categoria and categoria not in USOS_DISPONIBLES[uso]["categorias"]:
        raise ValueError(
            f"Categoría {categoria!r} no válida para el uso {uso!r}"
        )
    estado.uso = uso
    estado.categoria = categoria
    return estado


def actualizar_urbanismo(activo_id: str, datos: dict) -> ProyectoEstado:
    """Merge profundo en el dict de urbanismo del proyecto.

    Solo se actualizan las claves presentes en ``datos`` (PATCH semántico),
    no se sobrescribe el dict completo.
    """
    estado = obtener_o_crear(activo_id)
    _merge_dict(estado.urbanismo, datos)
    return estado


def actualizar_diseno(activo_id: str, datos: dict) -> ProyectoEstado:
    estado = obtener_o_crear(activo_id)
    _merge_dict(estado.diseno, datos)
    return estado


def resetear_diseno(activo_id: str) -> ProyectoEstado:
    estado = obtener_o_crear(activo_id)
    estado.diseno = copy.deepcopy(PARAMETROS_DISENO_DEFAULTS)
    return estado


def _merge_dict(destino: dict, origen: dict) -> None:
    for k, v in origen.items():
        if isinstance(v, dict) and isinstance(destino.get(k), dict):
            _merge_dict(destino[k], v)
        else:
            destino[k] = v


# ─── Alertas urbanísticas ────────────────────────────────────────────────────

# Superficie mínima orientativa por uso (m² de parcela) para detectar parcelas
# claramente inadecuadas en fase de prefactibilidad. Son valores conservadores
# de "viabilidad operativa", no normativos.
SUPERFICIE_PARCELA_MIN_ORIENTATIVA: dict[str, float] = {
    "hotelero": 200,
    "hotel_apartamento": 200,
    "apartamentos_turisticos": 200,
    "apartamentos_turisticos_conjunto": 400,
    "vivienda": 80,
}


def calcular_alertas(activo, estado: ProyectoEstado) -> list[dict]:
    """Genera la lista de alertas urbanísticas para el activo + estado actual.

    Cada alerta tiene la forma:
        {"nivel": "info|aviso|error", "mensaje": str, "campo": str|None}

    En esta fase (sin envolvente edificatoria todavía calculada) las alertas
    son las que pueden derivarse directamente de la parcela + parámetros:
      - uso seleccionado dentro de los usos permitidos por urbanismo
      - superficie de la parcela suficiente para el uso
      - cumplimiento de mínimos de patio si se han introducido
      - presencia de edificio existente cuando se selecciona obra nueva
    """
    alertas: list[dict] = []
    urb = estado.urbanismo or {}
    uso = estado.uso

    if uso:
        permitidos = urb.get("usos_permitidos") or []
        # Mapeo flexible: hotelero y hotel_apartamento ambos casan con "hotelero"
        uso_urb = uso
        if uso in ("hotelero", "hotel_apartamento"):
            uso_urb_candidatos = ("hotelero",)
        elif uso in ("apartamentos_turisticos", "apartamentos_turisticos_conjunto"):
            uso_urb_candidatos = ("hotelero", "terciario", "residencial")
        elif uso == "vivienda":
            uso_urb_candidatos = ("residencial",)
        else:
            uso_urb_candidatos = (uso,)
        if permitidos and not any(c in permitidos for c in uso_urb_candidatos):
            alertas.append({
                "nivel": "error",
                "mensaje": (
                    f"El uso seleccionado ({USOS_DISPONIBLES[uso]['etiqueta']}) "
                    f"no figura entre los usos permitidos por el planeamiento."
                ),
                "campo": "uso",
            })

        sup_min = SUPERFICIE_PARCELA_MIN_ORIENTATIVA.get(uso)
        sup_parcela = getattr(activo, "superficie_catastral_m2", 0) or 0
        if sup_min and sup_parcela and sup_parcela < sup_min:
            alertas.append({
                "nivel": "aviso",
                "mensaje": (
                    f"Superficie de parcela ({sup_parcela:.0f} m²) por debajo del "
                    f"mínimo orientativo para este uso ({sup_min:.0f} m²)."
                ),
                "campo": "superficie_catastral",
            })

    luz = urb.get("patio_min_luz_recta_m")
    sup_patio = urb.get("patio_min_superficie_m2")
    if luz is not None and luz < 3:
        alertas.append({
            "nivel": "aviso",
            "mensaje": "La luz recta mínima de patio definida (<3 m) es inferior al "
                       "criterio del estudio (Anexo II, A2.5).",
            "campo": "patio_min_luz_recta_m",
        })
    if sup_patio is not None and sup_patio < 12:
        alertas.append({
            "nivel": "aviso",
            "mensaje": "La superficie mínima de patio definida (<12 m²) es inferior al "
                       "criterio del estudio (Anexo II, A2.5).",
            "campo": "patio_min_superficie_m2",
        })

    if not urb.get("edificabilidad_m2t_m2s"):
        alertas.append({
            "nivel": "info",
            "mensaje": "Edificabilidad sin definir. Consulta el PGOU del municipio "
                       "e introduce el valor para poder calcular la envolvente.",
            "campo": "edificabilidad_m2t_m2s",
        })
    if not urb.get("plantas_max"):
        alertas.append({
            "nivel": "info",
            "mensaje": "Número máximo de plantas sin definir.",
            "campo": "plantas_max",
        })
    if not urb.get("ocupacion_max_pct"):
        alertas.append({
            "nivel": "info",
            "mensaje": "Ocupación máxima sin definir.",
            "campo": "ocupacion_max_pct",
        })

    if getattr(activo, "edificio", None):
        alertas.append({
            "nivel": "info",
            "mensaje": (
                "Existe edificación catastral registrada. Recuerda indicar si se "
                "parte de solar libre o si se aprovecha el edificio existente "
                "(§2.2)."
            ),
            "campo": "edificio_existente",
        })

    return alertas
