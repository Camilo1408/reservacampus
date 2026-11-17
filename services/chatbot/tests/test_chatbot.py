import os
import sys
from datetime import date, time

os.environ["GROQ_API_KEY"] = ""  # las pruebas no llaman a la IA real
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.reglas import detectar, extraer_fecha, extraer_hora  # noqa: E402


@pytest.mark.parametrize("mensaje,esperada", [
    ("hola", "saludo"),
    ("¿Cómo reservo una sala?", "como_reservar"),
    ("quiero cancelar mi reserva", "cancelar"),
    ("¿qué salas están libres mañana?", "disponibilidad"),
    ("muéstrame mis reservas", "mis_reservas"),
    ("cuál es la duración máxima", "reglas"),
    ("a qué hora abre el laboratorio", "horarios"),
    ("gracias!", "despedida"),
])
def test_detectar_intencion(mensaje, esperada):
    assert detectar(mensaje).nombre == esperada


def test_sin_intencion():
    assert detectar("explícame la teoría de la relatividad") is None


def test_saludo_largo_no_es_saludo():
    assert detectar("hola, necesito saber cómo reservar el auditorio") .nombre == "como_reservar"


def test_extraer_fecha_y_hora():
    lunes = date(2026, 11, 16)
    assert extraer_fecha("libre mañana", lunes) == date(2026, 11, 17)
    assert extraer_fecha("el viernes", lunes) == date(2026, 11, 20)
    assert extraer_hora("a las 3") == time(15, 0)
    assert extraer_hora("10:30") == time(10, 30)
    assert extraer_hora("9am") == time(9, 0)
    assert extraer_hora("sin hora") is None


def test_endpoint_reglas_y_respaldo():
    from app.main import app
    c = TestClient(app)
    r = c.post("/chat", json={"mensaje": "¿Cuáles son las reglas?"})
    assert r.json()["fuente"] == "reglas"
    r = c.post("/chat", json={"mensaje": "¿quién ganó el mundial?"})
    assert r.json()["fuente"] == "respaldo"  # sin API key ni reservas -> respaldo


def test_mensaje_demasiado_largo():
    from app.main import app
    assert TestClient(app).post("/chat", json={"mensaje": "x" * 501}).status_code == 422
