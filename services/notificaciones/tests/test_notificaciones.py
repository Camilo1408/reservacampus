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
