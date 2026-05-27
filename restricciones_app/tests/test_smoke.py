"""Test de humo: pipeline completo con parámetros razonables."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from restricciones.modelo import Parcela, PGOU, ProgramaInversor, Costes
from restricciones.diseno import DEFAULT as DISENO
from restricciones.escenarios import comparar_escenarios


def test_pipeline_vivienda():
    parcela = Parcela(
        referencia="test_240",
        superficie_m2=240.0,
        longitud_fachada_m=10.0,
        profundidad_media_m=24.0,
    )
    pgou = PGOU(edificabilidad=2.5, ocupacion_maxima=1.0, n_plantas_max=4)
    programa = ProgramaInversor(uso="vivienda")
    costes = Costes()
    escenarios = comparar_escenarios(parcela, pgou, DISENO, costes, programa)

    assert escenarios.max_margen.n_unidades_total >= 1
    assert escenarios.max_margen.margen_eur != 0
    assert escenarios.max_m2_util.superficie_util_total_m2 > 0
    assert escenarios.max_unidades.n_unidades_total >= escenarios.max_margen.n_unidades_total \
        or escenarios.max_unidades.n_unidades_total >= 1


def test_pipeline_hotelero():
    parcela = Parcela(
        referencia="test_800",
        superficie_m2=800.0,
        longitud_fachada_m=20.0,
        profundidad_media_m=40.0,
    )
    pgou = PGOU(edificabilidad=3.5, ocupacion_maxima=1.0, n_plantas_max=5,
                usos_permitidos=["hotelero", "vivienda"])
    programa = ProgramaInversor(uso="hotelero")
    costes = Costes()
    escenarios = comparar_escenarios(parcela, pgou, DISENO, costes, programa)

    assert escenarios.max_margen.uso == "hotelero"
    assert escenarios.max_margen.n_unidades_total >= 5


if __name__ == "__main__":
    test_pipeline_vivienda()
    test_pipeline_hotelero()
    print("OK")
