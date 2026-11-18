import os
import sys
from datetime import datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "sqlite:///./test_notif.db"
os.environ["JWT_SECRET"] = "secreto-test"
os.environ["REDIS_URL"] = ""
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

EVENTO = {"reserva_id": 1, "usuario_id": 7, "usuario_email": "ana@u.edu", "usuario_nombre": "Ana",
          "espacio": "Sala A-101", "fecha": "2026-11-20", "hora_inicio": "10:00", "hora_fin": "11:00"}


def headers(uid):
    t = jwt.encode({"sub": str(uid), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                   "secreto-test", algorithm="HS256")
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture()
def client():
    from app.database import Base, engine
    from app.main import app
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:
        yield c


def test_evento_genera_notificacion_idempotente(client):
    from app.consumidor import procesar_evento
    from app.database import SessionLocal
    with SessionLocal() as db:
        assert procesar_evento(db, "1-0", "reserva.creada", EVENTO) is not None
        assert procesar_evento(db, "1-0", "reserva.creada", EVENTO) is None  # duplicado ignorado
    r = client.get("/notificaciones", headers=headers(7))
    assert len(r.json()) == 1 and "Sala A-101" in r.json()[0]["mensaje"]
    assert client.get("/notificaciones", headers=headers(8)).json() == []


def test_marcar_leida_solo_dueno(client):
    from app.consumidor import procesar_evento
    from app.database import SessionLocal
    with SessionLocal() as db:
        nid = procesar_evento(db, "2-0", "reserva.cancelada", EVENTO).id
    assert client.post(f"/notificaciones/{nid}/leer", headers=headers(8)).status_code == 404
    assert client.post(f"/notificaciones/{nid}/leer", headers=headers(7)).json()["leida"] is True


def test_revocacion_incluye_justificacion(client, monkeypatch):
    from app import consumidor
    enviados = []
    monkeypatch.setattr(consumidor, "enviar_correo", lambda *a: enviados.append(a) or True)
    from app.database import SessionLocal
    with SessionLocal() as db:
        n = consumidor.procesar_evento(db, "3-0", "reserva.revocada", {**EVENTO, "justificacion": "Evento institucional"})
    assert "Evento institucional" in n.mensaje and n.correo_enviado
    assert enviados[0][0] == "ana@u.edu"


def test_html_escapa_contenido():
    from app.consumidor import html_correo
    assert "<script>" not in html_correo("<script>", "t", "m")


def admin_headers():
    t = jwt.encode({"sub": "99", "rol": "admin", "nombre": "Admin", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                   "secreto-test", algorithm="HS256")
    return {"Authorization": f"Bearer {t}"}


def test_admin_envia_alerta(client, monkeypatch):
    from app import main
    enviados = []
    monkeypatch.setattr(main, "enviar_correo", lambda *a: enviados.append(a) or True)
    alerta = {"usuario_id": 7, "usuario_email": "ana@u.edu", "usuario_nombre": "Ana",
              "asunto": "Uso del espacio", "mensaje": "Recuerda entregar la sala a tiempo."}
    assert client.post("/alertas", json=alerta, headers=headers(7)).status_code == 403
    r = client.post("/alertas", json=alerta, headers=admin_headers())
    assert r.status_code == 201 and r.json()["correo_enviado"] and enviados[0][0] == "ana@u.edu"
    assert client.get("/notificaciones", headers=headers(7)).json()[0]["titulo"].endswith("Uso del espacio")
    assert len(client.get("/admin/usuarios/7/notificaciones", headers=admin_headers()).json()) == 1


@pytest.mark.parametrize("tipo,datos,texto", [
    ("reserva.recordatorio", {"hora_inicio": "10:00"}, "10:00"),
    ("sancion.aplicada", {"nivel": 2, "motivo": "No entregaste", "descripcion": "3 días.", "hasta": "21/11"}, "nivel 2"),
    ("usuario.password_reset", {"minutos": 30, "enlace": "https://x/?reset=abc"}, "30 minutos"),
    ("usuario.estado_cambiado", {"estado": "suspendido", "motivo": "Reincidencia"}, "suspendido"),
])
def test_plantillas_nuevas(client, monkeypatch, tipo, datos, texto):
    from app import consumidor
    correos = []
    monkeypatch.setattr(consumidor, "enviar_correo", lambda *a: correos.append(a) or True)
    from app.database import SessionLocal
    with SessionLocal() as db:
        n = consumidor.procesar_evento(db, f"{tipo}-1", tipo, {**EVENTO, **datos})
    assert texto in n.titulo + n.mensaje
    if "enlace" in datos:
        assert correos[0][4] == datos["enlace"] and correos[0][5]  # botón con enlace


def test_boton_solo_con_url_http():
    from app.consumidor import html_correo
    assert "href" not in html_correo("A", "t", "m", "javascript:alert(1)", "Ir")
    assert 'href="https://x"' in html_correo("A", "t", "m", "https://x", "Ir")
