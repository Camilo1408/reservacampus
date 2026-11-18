"""Levanta el sistema completo (4 microservicios + frontend) en puertos de prueba con SQLite temporal.

Uso:  python -m pytest tests/e2e            (requiere: pip install pytest-playwright && playwright install chromium)
      E2E_BASE_URL=https://... para correr contra un entorno ya desplegado (no levanta servidores).
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PUERTOS = {"auth": 9101, "reservas": 9102, "notificaciones": 9103, "chatbot": 9104}
PUERTO_WEB = 9180
ADMIN = ("admin@reservacampus.edu", "Admin12345")


def _esperar(puerto: int, segundos: int = 40):
    limite = time.time() + segundos
    while time.time() < limite:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", puerto)) == 0:
                return
        time.sleep(0.3)
    raise RuntimeError(f"El puerto {puerto} no respondió")


@pytest.fixture(scope="session")
def base_url():
    if os.getenv("E2E_BASE_URL"):
        yield os.environ["E2E_BASE_URL"].rstrip("/")
        return
    tmp = Path(tempfile.mkdtemp(prefix="e2e_reservas_"))
    env_comun = {**os.environ, "JWT_SECRET": "e2e-secreto-0123456789-0123456789-abcdef", "REDIS_URL": "",
                 "GROQ_API_KEY": "", "CORS_ORIGINS": "*", "PYTHONUNBUFFERED": "1",
                 "RESERVAS_URL": f"http://127.0.0.1:{PUERTOS['reservas']}",
                 "AUTH_URL": f"http://127.0.0.1:{PUERTOS['auth']}",
                 "FRONTEND_URL": f"http://127.0.0.1:{PUERTO_WEB}"}
    procesos = []
    for servicio, puerto in PUERTOS.items():
        env = {**env_comun, "DATABASE_URL": f"sqlite:///{(tmp / f'{servicio}.db').as_posix()}"}
        procesos.append(subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(puerto), "--log-level", "warning"],
            cwd=RAIZ / "services" / servicio, env=env))
    # Frontend con config.js apuntando a los puertos de prueba
    web = tmp / "web"
    shutil.copytree(RAIZ / "frontend", web)
    (web / "config.js").write_text(
        "window.CONFIG = {" + ",".join(f'{k}: "http://127.0.0.1:{PUERTOS[s]}"' for k, s in
                                       [("AUTH_URL", "auth"), ("RESERVAS_URL", "reservas"),
                                        ("NOTIF_URL", "notificaciones"), ("CHAT_URL", "chatbot")]) + "};",
        encoding="utf-8")
    procesos.append(subprocess.Popen([sys.executable, "-m", "http.server", str(PUERTO_WEB), "--bind", "127.0.0.1"],
                                     cwd=web, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    try:
        for p in [*PUERTOS.values(), PUERTO_WEB]:
            _esperar(p)
        yield f"http://127.0.0.1:{PUERTO_WEB}"
    finally:
        for p in procesos:
            p.terminate()
        for p in procesos:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture()
def pagina(page, base_url):
    page.set_default_timeout(10000)
    page.goto(base_url)
    return page


def iniciar_sesion(page, email, password):
    page.fill("#form-login [name=email]", email)
    page.fill("#form-login [name=password]", password)
    page.click("#form-login button[type=submit]")
    page.wait_for_selector("#vista-espacios:not(.oculto)")


def registrar(page, nombre, email, password="Clave1234"):
    page.click(".tab[data-tab=registro]")
    page.fill("#form-registro [name=nombre]", nombre)
    page.fill("#form-registro [name=email]", email)
    page.fill("#form-registro [name=password]", password)
    page.click("#form-registro button[type=submit]")
    page.wait_for_selector("#vista-espacios:not(.oculto)")


def elegir(page, select_css, texto):
    """Selecciona una opción en el select personalizado (como lo haría el usuario)."""
    caja = page.locator(select_css).locator("xpath=following-sibling::div[contains(@class,'sel')][1]")
    caja.locator(".sel-boton").click()
    caja.locator(".sel-lista li", has_text=texto).first.click()


def ir_admin(page, sub):
    page.click(".nav [data-vista=admin]")
    page.click(f".subtab[data-sub={sub}]")
    page.wait_for_selector(f"#sub-{sub}:not(.oculto)")
