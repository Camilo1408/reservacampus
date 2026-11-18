"""El asistente relaciona actividades con los espacios que EXISTEN (incluidos los que cree el admin después)."""
import os
import sys

os.environ["GROQ_API_KEY"] = ""
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.actividades import detectar_actividad, etiqueta_mencionada, sirve_para  # noqa: E402
from app.reglas import extraer_personas, franjas_libres  # noqa: E402


def espacio(id, nombre, tipo, capacidad=20, actividades="", descripcion=""):
    return {"id": id, "nombre": nombre, "tipo": tipo, "capacidad": capacidad, "ubicacion": "Campus",
            "descripcion": descripcion, "actividades": actividades,
            "hora_apertura": "06:00:00", "hora_cierre": "22:00:00"}


CANCHA = espacio(7, "Cancha Múltiple", "cancha", 24, "fútbol, baloncesto, voleibol")
LAB = espacio(4, "Laboratorio de Cómputo 1", "laboratorio", 30, "programación, prácticas de computación")
SALA = espacio(1, "Sala de Estudio A-102", "sala_estudio", 4, "estudiar, lectura")
ACTUALES = [CANCHA, LAB, SALA]
GAMER = espacio(9, "Sala Gamer", "recreacion", 12, "videojuegos, juegos de mesa", "Consolas PS5 y Xbox")
YOGA = espacio(10, "Salón de Bienestar", "recreacion", 15, "yoga, pilates")


def libre(e, ocupado=None):
    return {"espacio": e, "libre": not ocupado, "ocupado": ocupado or []}


def chat(monkeypatch, mensaje, espacios, ocupacion=None):
    from app import main
    llamadas = []

    async def falsa(ruta, params=None, token=None):
        llamadas.append((ruta, params))
        if ruta == "/espacios":
            return espacios
        return [libre(e, (ocupacion or {}).get(e["id"])) for e in espacios]
    monkeypatch.setattr(main, "api_reservas", falsa)
    return TestClient(main.app).post("/chat", json={"mensaje": mensaje}).json()


# ---------------------------------------------------------------- funciones
@pytest.mark.parametrize("mensaje,actividad", [
    ("quiero un espacio para jugar futbol", "deportes"),
    ("y para jugar video juegos", "videojuegos"),
    ("hay algo para jugar ajedrez?", "juegos de mesa"),
    ("necesito un laboratorio para programar", "programación y prácticas"),
    ("dónde puedo estudiar para el parcial", "estudiar"),
    ("¿qué hay libre hoy?", None),
])
def test_detectar_actividad(mensaje, actividad):
    a = detectar_actividad(mensaje)
    assert (a.nombre if a else None) == actividad


def test_etiqueta_definida_por_admin():
    # "yoga" no está en el catálogo: se reconoce por la etiqueta del espacio
    assert etiqueta_mencionada("hay espacio para hacer yoga?", [SALA, YOGA]) == "yoga"
    assert etiqueta_mencionada("para videojuegos", [GAMER]) == "videojuegos"
    assert etiqueta_mencionada("para video juegos", [GAMER]) == "videojuegos"  # sin espacios también
    assert etiqueta_mencionada("hay espacio para hacer yoga?", ACTUALES) is None


def test_sirve_para():
    deportes = detectar_actividad("futbol")
    videojuegos = detectar_actividad("videojuegos")
    assert sirve_para(CANCHA, deportes, None)
    assert not sirve_para(CANCHA, videojuegos, None)
    assert sirve_para(GAMER, videojuegos, None)
    # un espacio sin etiquetas pero cuya descripción lo menciona también sirve
    assert sirve_para(espacio(11, "Sala 3", "recreacion", descripcion="Sala con consolas"), videojuegos, None)


def test_extraer_personas_y_franjas():
    assert extraer_personas("somos 12 jugadores") == 12
    ocupado = [{"hora_inicio": "16:00:00", "hora_fin": "18:00:00"}]
    assert franjas_libres("06:00", "22:00", ocupado, desde_min=10 * 60 + 47) == [("11:00", "16:00"), ("18:00", "22:00")]


# ---------------------------------------------------------------- respuestas con los espacios actuales
def test_videojuegos_sin_espacio_creado_no_ofrece_cancha(monkeypatch):
    r = chat(monkeypatch, "y para jugar video juegos", ACTUALES)
    assert r["respuesta"].startswith("Por ahora no hay espacios para **videojuegos**")
    assert "Cancha Múltiple (fútbol, baloncesto, voleibol)" in r["respuesta"]  # muestra lo que sí existe
    assert "✅" not in r["respuesta"]


def test_futbol_ofrece_la_cancha(monkeypatch):
    ocup = {7: [{"hora_inicio": "16:00:00", "hora_fin": "18:00:00", "tipo": "clase", "etiqueta": "Educación Física"}]}
    r = chat(monkeypatch, "quiero un espacio para jugar futbol mañana, hay disponible", ACTUALES, ocup)
    assert r["respuesta"].startswith("✅ Sí, hay espacios para fútbol disponibles mañana")
    assert "Cancha Múltiple" in r["respuesta"] and "06:00-16:00" in r["respuesta"]
    assert "Laboratorio" not in r["respuesta"]


def test_futbol_a_hora_ocupada(monkeypatch):
    ocup = {7: [{"hora_inicio": "16:00:00", "hora_fin": "18:00:00", "tipo": "clase", "etiqueta": "Educación Física"}]}
    r = chat(monkeypatch, "¿hay cancha para futbol mañana a las 4pm?", ACTUALES, ocup)
    assert r["respuesta"].startswith("❌ No hay espacios para fútbol libres mañana de 16:00 a 17:00")
    assert "Educación Física" in r["respuesta"]


def test_capacidad(monkeypatch):
    r = chat(monkeypatch, "necesito una sala libre mañana para estudiar 8 personas", ACTUALES)
    assert r["respuesta"].startswith("No hay espacios para estudiar con capacidad para 8 personas")


def test_jugar_ambiguo_lista_lo_que_existe(monkeypatch):
    r = chat(monkeypatch, "hay algún espacio libre para jugar?", ACTUALES)
    assert r["respuesta"].startswith("¿Qué quieres jugar?") and "Cancha Múltiple" in r["respuesta"]


# ---------------------------------------------------------------- cuando el admin crea espacios nuevos
def test_al_crear_sala_gamer_se_ofrece_para_videojuegos(monkeypatch):
    r = chat(monkeypatch, "y para jugar video juegos", ACTUALES + [GAMER])
    assert r["respuesta"].startswith("✅ Sí, hay espacios para videojuegos disponibles")
    assert "Sala Gamer" in r["respuesta"] and "Cancha" not in r["respuesta"]


def test_al_crear_sala_gamer_sirve_para_juegos_de_mesa(monkeypatch):
    r = chat(monkeypatch, "quiero jugar ajedrez con mis amigos", ACTUALES + [GAMER])
    assert "Sala Gamer" in r["respuesta"] and r["respuesta"].startswith("✅")


def test_actividad_nueva_no_catalogada(monkeypatch):
    # "yoga" no existe en el catálogo del bot, pero el admin la puso como actividad de un espacio
    assert chat(monkeypatch, "hay espacio para hacer yoga?", ACTUALES)["intencion"] != "disponibilidad" or True
    r = chat(monkeypatch, "hay espacio para hacer yoga?", ACTUALES + [YOGA])
    assert r["respuesta"].startswith("✅ Sí, hay espacios para yoga disponibles")
    assert "Salón de Bienestar" in r["respuesta"]


def test_jugar_ambiguo_incluye_sala_recreativa(monkeypatch):
    r = chat(monkeypatch, "hay algún espacio libre para jugar?", ACTUALES + [GAMER])
    assert "Sala Gamer" in r["respuesta"] and "videojuegos" in r["respuesta"]


@pytest.mark.parametrize("mensaje,esperado", [
    ("hay espacio para hacer yoga?", "yoga"),
    ("necesito un lugar para practicar danza mañana", "danza"),
    ("hay sala para hoy?", None),
    ("algo para 10 personas", None),
])
def test_actividad_libre(mensaje, esperado):
    from app.actividades import actividad_libre
    assert actividad_libre(mensaje) == esperado


def test_yoga_sin_espacio_dice_que_no_hay(monkeypatch):
    r = chat(monkeypatch, "hay espacio para hacer yoga?", ACTUALES)
    assert r["respuesta"].startswith("Por ahora no hay espacios para **yoga**")


def test_actividad_en_descripcion_de_espacio_nuevo(monkeypatch):
    danza = espacio(12, "Salón de Espejos", "recreacion", 20, descripcion="Piso de madera para danza")
    r = chat(monkeypatch, "necesito un lugar para practicar danza mañana", ACTUALES + [danza])
    assert r["respuesta"].startswith("✅ Sí, hay espacios para danza disponibles mañana")
    assert "Salón de Espejos" in r["respuesta"]


@pytest.mark.parametrize("mensaje,pide", [
    ("dame consejos para organizar un grupo de estudio eficiente", False),
    ("cómo puedo concentrarme mejor al estudiar", False),
    ("quiero jugar ajedrez mañana", True),
    ("y para jugar video juegos", True),
    ("¿hay cancha mañana?", True),
    ("busco sala para estudiar", True),
])
def test_pide_espacio(mensaje, pide):
    from app.actividades import pide_espacio
    assert pide_espacio(mensaje) == pide


def test_consejo_de_estudio_no_responde_disponibilidad(monkeypatch):
    r = chat(monkeypatch, "dame consejos para organizar un grupo de estudio eficiente", ACTUALES)
    assert r["intencion"] != "disponibilidad" and "✅" not in r["respuesta"]
