import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///./test_auth.db"
os.environ["JWT_SECRET"] = "secreto-test"
os.environ["REDIS_URL"] = ""
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def client():
    from app.database import Base, engine
    from app.main import app, limitador
    Base.metadata.drop_all(engine)
    limitador.fallos.clear()
    from app.main import limitador_recuperar
    limitador_recuperar.fallos.clear()
    with TestClient(app) as c:
        yield c
