from app import keepalive


def test_keepalive_inactivo_sin_url(monkeypatch):
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("KEEPALIVE_URL", raising=False)
    assert keepalive.iniciar() is False


def test_keepalive_se_puede_apagar(monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://ejemplo.onrender.com")
    monkeypatch.setenv("KEEPALIVE", "0")
    assert keepalive.iniciar() is False


def test_keepalive_franja_horaria():
    assert keepalive._en_franja("0-24") is True
    assert keepalive._en_franja("5-5") is False
    assert keepalive._en_franja("mal") is True
