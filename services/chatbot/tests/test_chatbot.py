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
    ("¿cómo confirmo llegada?", "llegada"),
    ("la sala sigue ocupada y no han salido", "reporte"),
    ("¿por qué estoy sancionado?", "sanciones"),
    ("necesito un laboratorio mañana para 25 personas", "disponibilidad"),
    ("busco una sala para estudiar", "disponibilidad"),
    ("¿qué laboratorios hay?", "tipos"),
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


# ---------------- disponibilidad por tipo de espacio
from app.reglas import extraer_personas, extraer_tipo, franjas_libres  # noqa: E402


@pytest.mark.parametrize("mensaje,tipo", [
    ("quiero un espacio para jugar futbol, hay disponible", "cancha"),
    ("¿hay cancha para baloncesto mañana?", "cancha"),
    ("necesito un laboratorio para programar", "laboratorio"),
    ("dónde puedo estudiar para el parcial", "sala_estudio"),
    ("¿el auditorio está libre para una conferencia?", "auditorio"),
    ("¿qué hay libre hoy?", None),
])
def test_extraer_tipo(mensaje, tipo):
    assert extraer_tipo(mensaje) == tipo


def test_extraer_personas():
    assert extraer_personas("sala para 8 personas") == 8
    assert extraer_personas("somos 12 jugadores") == 12
    assert extraer_personas("una sala") is None


def test_franjas_libres():
    ocupado = [{"hora_inicio": "08:00:00", "hora_fin": "10:00:00"}, {"hora_inicio": "16:00:00", "hora_fin": "18:00:00"}]
    assert franjas_libres("06:00", "22:00", ocupado) == [("06:00", "08:00"), ("10:00", "16:00"), ("18:00", "22:00")]
    # hoy a las 10:47 -> desde el siguiente bloque de 30 min
    assert franjas_libres("06:00", "22:00", ocupado, desde_min=10 * 60 + 47) == [("11:00", "16:00"), ("18:00", "22:00")]
    assert franjas_libres("06:00", "22:00", [], desde_min=21 * 60 + 40) == []


CANCHA = {"id": 7, "nombre": "Cancha Múltiple", "tipo": "cancha", "capacidad": 24, "ubicacion": "Zona deportiva",
          "hora_apertura": "06:00:00", "hora_cierre": "22:00:00"}


def chat_con(monkeypatch, mensaje, disponibilidad):
    from app import main
    llamadas = []

    async def falsa(ruta, params=None, token=None):
        llamadas.append((ruta, params))
        return disponibilidad
    monkeypatch.setattr(main, "api_reservas", falsa)
    r = TestClient(main.app).post("/chat", json={"mensaje": mensaje}).json()
    return r, llamadas


def test_futbol_responde_si_con_franjas_de_la_cancha(monkeypatch):
    disp = [{"espacio": CANCHA, "libre": False, "ocupado": [
        {"hora_inicio": "16:00:00", "hora_fin": "18:00:00", "tipo": "clase", "etiqueta": "Educación Física"}]}]
    r, llamadas = chat_con(monkeypatch, "quiero un espacio para jugar futbol mañana, hay disponible", disp)
    assert llamadas[0][1]["tipo"] == "cancha"
    assert r["respuesta"].startswith("✅ Sí, hay canchas disponibles mañana")
    assert "Cancha Múltiple" in r["respuesta"] and "06:00-16:00" in r["respuesta"] and "18:00-22:00" in r["respuesta"]
    assert "Laboratorio" not in r["respuesta"]


def test_futbol_a_una_hora_ocupada_responde_no(monkeypatch):
    disp = [{"espacio": CANCHA, "libre": False, "ocupado": [
        {"hora_inicio": "16:00:00", "hora_fin": "18:00:00", "tipo": "clase", "etiqueta": "Educación Física"}]}]
    r, _ = chat_con(monkeypatch, "¿hay cancha para futbol mañana a las 4pm?", disp)
    assert r["respuesta"].startswith("❌ No hay canchas libres mañana de 16:00 a 17:00")
    assert "Educación Física" in r["respuesta"]


def test_filtra_por_capacidad(monkeypatch):
    sala = {**CANCHA, "id": 1, "nombre": "Sala A-102", "tipo": "sala_estudio", "capacidad": 4}
    r, _ = chat_con(monkeypatch, "necesito una sala libre mañana para estudiar 8 personas",
                    [{"espacio": sala, "libre": True, "ocupado": []}])
    assert r["respuesta"].startswith("No hay salas de estudio disponibles para 8 personas")
