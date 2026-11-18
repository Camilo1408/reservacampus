import os
import sys
from datetime import datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "sqlite:///./test_reservas.db"
os.environ["JWT_SECRET"] = "secreto-test"
os.environ["REDIS_URL"] = ""
os.environ["TAREAS_INTERVALO_SEG"] = "0"
os.environ["TAREAS_TOKEN"] = "token-tareas-test"
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def token(uid=1, rol="estudiante", nombre="Ana", email="ana@u.edu"):
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    t = jwt.encode({"sub": str(uid), "email": email, "nombre": nombre, "rol": rol, "exp": exp},
                   "secreto-test", algorithm="HS256")
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture()
def client():
    from app.database import Base, engine
    from app.eventos import publicador
    from app.main import app
    Base.metadata.drop_all(engine)
    publicador.enviados.clear()
    with TestClient(app) as c:
        yield c
