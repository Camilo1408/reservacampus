"""Genera las capturas de pantalla de los manuales recorriendo la app como cada rol.

Levanta los 4 servicios + frontend en local con SQLite temporal, siembra datos de demostración a través de la
API real y toma capturas con Playwright.  Uso: python docs/fuentes/capturas.py
"""
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
# Hora simulada de la demo (reloj del servicio de reservas y del navegador): hoy a las 10:15
HORA_DEMO = datetime.combine(date.today(), datetime.min.time()).replace(hour=10, minute=15)
OUT = RAIZ / "docs" / "img" / "capturas"
PY = sys.executable
P = {"auth": 9201, "reservas": 9202, "notificaciones": 9203, "chatbot": 9204}
WEB = 9280
BASE = f"http://127.0.0.1:{WEB}"
U = {s: f"http://127.0.0.1:{p}" for s, p in P.items()}
ADMIN = ("admin@reservacampus.edu", "Admin12345")
CLAVE = "Clave1234"


def leer_env():
    env = {}
    f = RAIZ / ".env"
    if f.exists():
        for linea in f.read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.startswith("#"):
                k, v = linea.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def esperar(puerto):
    for _ in range(150):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", puerto)) == 0:
                return
        time.sleep(0.2)
    raise RuntimeError(puerto)


def api(metodo, url, cuerpo=None, token=None):
    req = urllib.request.Request(url, method=metodo, data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{metodo} {url} -> {e.code} {e.read()[:300]}")


def login(email, clave=CLAVE):
    return api("POST", f"{U['auth']}/login", {"email": email, "password": clave})["access_token"]


def main():
    tmp = Path(tempfile.mkdtemp(prefix="capturas_"))
    env_local = leer_env()
    comun = {**os.environ, "JWT_SECRET": "capturas-secreto-0123456789-0123456789", "REDIS_URL": "", "CORS_ORIGINS": "*",
             "BREVO_API_KEY": "", "SMTP_HOST": "", "TAREAS_INTERVALO_SEG": "0",
             "GROQ_API_KEY": env_local.get("GROQ_API_KEY", ""), "GROQ_MODEL": env_local.get("GROQ_MODEL", "openai/gpt-oss-20b"),
             "RESERVAS_URL": U["reservas"], "AUTH_URL": U["auth"], "FRONTEND_URL": BASE,
             "APP_RELOJ_INICIO": HORA_DEMO.isoformat(timespec="minutes")}
    dbs = {s: tmp / f"{s}.db" for s in P}
    procs = []
    for s, puerto in P.items():
        procs.append(subprocess.Popen([PY, "-m", "uvicorn", "app.main:app", "--port", str(puerto), "--log-level", "warning"],
                                      cwd=RAIZ / "services" / s, env={**comun, "DATABASE_URL": f"sqlite:///{dbs[s].as_posix()}"}))
    web = tmp / "web"
    shutil.copytree(RAIZ / "frontend", web)
    (web / "config.js").write_text("window.CONFIG = {" + ",".join(
        f'{k}: "{U[s]}"' for k, s in [("AUTH_URL", "auth"), ("RESERVAS_URL", "reservas"), ("NOTIF_URL", "notificaciones"),
                                      ("CHAT_URL", "chatbot")]) + "};", encoding="utf-8")
    procs.append(subprocess.Popen([PY, "-m", "http.server", str(WEB), "--bind", "127.0.0.1"], cwd=web,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    try:
        for p in [*P.values(), WEB]:
            esperar(p)
        datos = sembrar(dbs)
        capturar(datos)
    finally:
        for p in procs:
            p.terminate()
        shutil.rmtree(tmp, ignore_errors=True)


def sembrar(dbs):
    usuarios = [("Laura Gómez", "laura.gomez@universidad.edu"), ("Pedro Ruiz", "pedro.ruiz@universidad.edu"),
                ("Valentina Torres", "valentina.torres@universidad.edu"), ("Andrés Mejía", "andres.mejia@universidad.edu"),
                ("Sofía Rojas", "sofia.rojas@universidad.edu")]
    ids = {}
    for nombre, email in usuarios:
        ids[email] = api("POST", f"{U['auth']}/registro", {"nombre": nombre, "email": email, "password": CLAVE})["id"]
    ta = login(*ADMIN)
    tl, tp, ts = login("laura.gomez@universidad.edu"), login("pedro.ruiz@universidad.edu"), login("sofia.rojas@universidad.edu")
    m = date.today() + timedelta(days=1)
    pm = date.today() + timedelta(days=2)
    reservar = lambda t, e, f, i, fi, n=2, mot="": api("POST", f"{U['reservas']}/reservas", {
        "espacio_id": e, "fecha": f.isoformat(), "hora_inicio": i, "hora_fin": fi, "asistentes": n, "motivo": mot}, t)
    reservar(tl, 3, m, "15:00", "17:00", 6, "Repaso parcial de Cálculo")
    reservar(ts, 1, m, "09:00", "10:30", 4, "Proyecto de Ingeniería de Software")
    reservar(ts, 6, pm, "10:00", "12:00", 80, "Ensayo de sustentación")
    revocable = reservar(tp, 2, m, "11:00", "12:00", 3, "Grupo de estudio")

    # Reserva "en curso" de Laura (empezó hace 15 min) precedida por una de Pedro que no entregó el espacio:
    # se inserta directo en la BD local porque la API no permite crear reservas en el pasado.
    ahora = HORA_DEMO
    ini = ahora - timedelta(minutes=15)
    fin = ini + timedelta(hours=1)
    ini_p = ini - timedelta(hours=1)
    with sqlite3.connect(dbs["reservas"]) as con:
        sql = ("INSERT INTO reservas (espacio_id, usuario_id, usuario_email, usuario_nombre, fecha, hora_inicio, hora_fin, "
               "asistentes, motivo, estado, creada_en, aviso_previo, aviso_inicio, aviso_final) "
               "VALUES (?,?,?,?,?,?,?,?,?, 'confirmada', ?, 1, 1, 0)")
        hoy = date.today().isoformat()
        con.execute(sql, (1, ids["pedro.ruiz@universidad.edu"], "pedro.ruiz@universidad.edu", "Pedro Ruiz", hoy,
                          ini_p.strftime("%H:%M:%S.000000"), ini.strftime("%H:%M:%S.000000"), 3, "Taller", datetime.utcnow().isoformat()))
        cur = con.execute(sql, (1, ids["laura.gomez@universidad.edu"], "laura.gomez@universidad.edu", "Laura Gómez", hoy,
                                ini.strftime("%H:%M:%S.000000"), fin.strftime("%H:%M:%S.000000"), 4, "Estudio en grupo",
                                datetime.utcnow().isoformat()))
        en_curso = cur.lastrowid

    # Andrés: dos inasistencias (nivel 2) — sanción creada por la regla real del sistema
    sys.path.insert(0, str(RAIZ / "services" / "reservas"))
    os.environ["DATABASE_URL"] = f"sqlite:///{dbs['reservas'].as_posix()}"
    # Valentina suspendida y Sofía sin problemas
    api("PATCH", f"{U['auth']}/usuarios/{ids['valentina.torres@universidad.edu']}/estado",
        {"estado": "suspendido", "motivo": "Tres inasistencias sin cancelar la reserva"}, ta)
    for d in (1, 3):
        api("POST", f"{U['reservas']}/admin/sanciones", {"usuario_id": ids["andres.mejia@universidad.edu"],
            "usuario_email": "andres.mejia@universidad.edu", "usuario_nombre": "Andrés Mejía",
            "motivo": "No confirmó su llegada al Laboratorio de Redes en dos ocasiones", "dias": d}, ta)

    # Notificaciones de ejemplo procesadas por el código real del consumidor
    notif = {"usuario_id": ids["laura.gomez@universidad.edu"], "usuario_email": "laura.gomez@universidad.edu",
             "usuario_nombre": "Laura Gómez", "espacio": "Sala de Estudio B-201", "fecha": m.isoformat(),
             "hora_inicio": "15:00", "hora_fin": "17:00"}
    codigo = ("import json,sys; sys.path.insert(0,'.'); from app.database import Base,engine,SessionLocal;"
              "Base.metadata.create_all(engine); from app.consumidor import procesar_evento; d=json.loads(sys.argv[1]);"
              "s=SessionLocal(); [procesar_evento(s, f'demo-{i}', t, d) for i,t in enumerate(['reserva.creada','reserva.recordatorio'])]")
    subprocess.run([PY, "-c", codigo, json.dumps({**notif, "enlace": f"{BASE}/?confirmar=1"})],
                   cwd=RAIZ / "services" / "notificaciones", check=True,
                   env={**os.environ, "DATABASE_URL": f"sqlite:///{dbs['notificaciones'].as_posix()}", "REDIS_URL": "",
                        "BREVO_API_KEY": "", "SMTP_HOST": ""})
    api("POST", f"{U['notificaciones']}/alertas", {"usuario_id": ids["laura.gomez@universidad.edu"],
        "usuario_email": "laura.gomez@universidad.edu", "usuario_nombre": "Laura Gómez", "asunto": "Bienvenida a ReservaCampus",
        "mensaje": "Recuerda confirmar tu llegada en cada reserva y cancelar si no vas a asistir.", "enviar_correo": False}, ta)
    return {"ids": ids, "en_curso": en_curso, "revocable": revocable["id"], "ta": ta}


def capturar(datos):
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1366, "height": 800}, device_scale_factor=2.5, locale="es-CO")
        pg = ctx.new_page()
        pg.clock.install(time=HORA_DEMO)
        pg.clock.resume()
        pg.set_default_timeout(15000)

        def foto(nombre, selector=None, completa=False, espera=600):
            pg.wait_for_timeout(espera)
            destino = str(OUT / f"{nombre}.png")
            if selector:
                pg.locator(selector).first.screenshot(path=destino)
            else:
                pg.screenshot(path=destino, full_page=completa)
            print("📸", nombre)

        def entrar(email, clave=CLAVE):
            pg.goto(BASE)
            pg.evaluate("sessionStorage.clear()")
            pg.goto(BASE)
            pg.fill("#form-login [name=email]", email)
            pg.fill("#form-login [name=password]", clave)
            pg.click("#form-login button[type=submit]")
            pg.wait_for_selector("#vista-espacios:not(.oculto)")
            pg.wait_for_timeout(800)

        def elegir(select_css, texto):
            caja = pg.locator(select_css).locator("xpath=following-sibling::div[contains(@class,'sel')][1]")
            caja.locator(".sel-boton").click()
            caja.locator(".sel-lista li", has_text=texto).first.click()

        def cerrar_modales():
            pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d => d.close())")

        # ---------------------------------------------------------------- público
        pg.goto(BASE)
        foto("e01_login")
        pg.click(".tab[data-tab=registro]")
        pg.fill("#form-registro [name=nombre]", "Camila Pérez")
        pg.fill("#form-registro [name=email]", "camila.perez@universidad.edu")
        pg.fill("#form-registro [name=password]", "MiClave2026")
        pg.locator("#form-registro .pass-toggle").click()
        foto("e02_registro", ".auth-tarjeta")
        pg.click(".tab[data-tab=login]")
        pg.click("#btn-olvide")
        pg.fill("#form-recuperar [name=email]", "laura.gomez@universidad.edu")
        foto("e03_recuperar", "#modal-recuperar")
        cerrar_modales()
        pg.goto(f"{BASE}/?reset=enlace-de-ejemplo-0123456789")
        pg.fill("#form-restablecer [name=password]", "NuevaClave2026")
        pg.fill("#form-restablecer [name=password2]", "NuevaClave2026")
        foto("e04_restablecer", "#modal-restablecer")
        cerrar_modales()

        # ---------------------------------------------------------------- estudiante
        entrar("laura.gomez@universidad.edu")
        foto("e05_espacios")
        elegir("#filtro-tipo", "Laboratorios")
        pg.wait_for_timeout(500)
        caja = pg.locator("#filtro-tipo").locator("xpath=following-sibling::div[contains(@class,'sel')][1]")
        caja.locator(".sel-boton").click()
        foto("e06_filtro_tipo", espera=400)
        caja.locator(".sel-lista li", has_text="Todos los tipos").click()
        pg.locator("article.espacio", has_text="Sala de Estudio A-102").locator("[data-reservar]").click()
        pg.fill("#form-reserva [name=fecha]", (date.today() + timedelta(days=3)).isoformat())
        pg.dispatch_event("#form-reserva [name=fecha]", "change")
        elegir("#form-reserva [name=hora_inicio]", "14:00")
        elegir("#form-reserva [name=hora_fin]", "15:30")
        pg.fill("#form-reserva [name=asistentes]", "3")
        pg.fill("#form-reserva [name=motivo]", "Preparar exposición de Redes")
        foto("e07_modal_reserva", "#modal-reserva")
        pg.click("#form-reserva button[type=submit]")
        pg.wait_for_selector("#toast.visible")
        foto("e08_reserva_confirmada", espera=300)
        pg.click(".nav [data-vista=mis-reservas]")
        pg.wait_for_selector("[data-llegada]")
        foto("e09_mis_reservas")
        pg.locator("[data-reportar]").first.click()
        pg.fill(".dialogo-texto textarea", "El grupo anterior sigue en la sala y no ha salido.")
        foto("e10_reportar_dialogo", ".dialogo-texto")
        pg.click(".dialogo-texto button[type=submit]")
        pg.wait_for_selector("#toast.visible")
        foto("e11_reporte_enviado", "#lista-mis-reservas", espera=900)
        pg.click("#btn-notif")
        foto("e12_notificaciones", "#panel-notif")
        pg.click("body", position={"x": 5, "y": 400})
        pg.click("#chat-toggle")
        for msg in ["quiero un espacio para jugar fútbol mañana, hay disponible?", "¿hay cancha mañana a las 4pm?"]:
            pg.fill("#chat-input", msg)
            pg.press("#chat-input", "Enter")
            pg.wait_for_timeout(1500)
        foto("e13_chat_disponibilidad", "#chat")
        pg.fill("#chat-input", "y para jugar videojuegos")
        pg.press("#chat-input", "Enter")
        pg.wait_for_timeout(1500)
        foto("e14_chat_sin_espacio", "#chat")
        pg.fill("#chat-input", "dame consejos para organizar un grupo de estudio eficiente")
        pg.press("#chat-input", "Enter")
        pg.wait_for_function("document.querySelectorAll('.msg.bot .fuente').length && "
                             "[...document.querySelectorAll('.msg.bot')].pop().innerText.includes('RESPUESTA')", timeout=40000)
        foto("e15_chat_ia", "#chat", espera=500)
        pg.click("#chat-cerrar")

        entrar("pedro.ruiz@universidad.edu")
        foto("e16_banner_sancion")
        pg.click(".nav [data-vista=mis-reservas]")
        pg.wait_for_selector("#mis-sanciones:not(.oculto)")
        pg.locator("#mis-sanciones").scroll_into_view_if_needed()
        foto("e17_mis_sanciones", "#mis-sanciones")
        entrar("valentina.torres@universidad.edu")
        foto("e18_cuenta_suspendida")

        # móvil
        movil = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True)
        pm = movil.new_page()
        pm.clock.install(time=HORA_DEMO)
        pm.clock.resume()
        pm.goto(BASE)
        pm.fill("#form-login [name=email]", "laura.gomez@universidad.edu")
        pm.fill("#form-login [name=password]", CLAVE)
        pm.click("#form-login button[type=submit]")
        pm.wait_for_selector("#vista-espacios:not(.oculto)")
        pm.wait_for_timeout(900)
        pm.screenshot(path=str(OUT / "e19_movil_espacios.png"))
        pm.click(".nav [data-vista=mis-reservas]")
        pm.wait_for_timeout(1200)
        pm.screenshot(path=str(OUT / "e20_movil_mis_reservas.png"))
        print("📸 móvil")

        # ---------------------------------------------------------------- administrador
        entrar(*ADMIN)
        pg.click(".nav [data-vista=admin]")
        pg.wait_for_selector("#tabla-reservas tbody tr")
        foto("a01_panel_reservas")
        pg.locator(f"[data-revocar='{datos['revocable']}']").click()
        pg.fill("#form-revocar [name=justificacion]", "La sala estará en mantenimiento eléctrico ese día.")
        foto("a02_revocar", "#modal-revocar")
        pg.click("#form-revocar button[type=submit]")
        pg.wait_for_timeout(900)
        pg.click(".subtab[data-sub=espacios]")
        pg.wait_for_selector("#tabla-espacios tbody tr")
        foto("a03_espacios")
        pg.click("#btn-nuevo-espacio")
        f = pg.locator("#form-espacio")
        f.locator("[name=nombre]").fill("Sala Gamer")
        elegir("#form-espacio [name=tipo]", "Sala recreativa")
        f.locator("[name=capacidad]").fill("12")
        f.locator("[name=ubicacion]").fill("Bienestar Universitario, piso 2")
        f.locator("[name=descripcion]").fill("Consolas PS5 y Xbox, mesas de juego")
        f.locator("[name=actividades]").fill("videojuegos, juegos de mesa")
        foto("a04_nuevo_espacio", "#modal-espacio")
        f.locator("button[type=submit]").click()
        pg.wait_for_timeout(900)
        pg.click(".subtab[data-sub=horarios]")
        pg.wait_for_selector(".clase")
        foto("a05_horarios")
        pg.set_input_files("#form-csv [name=archivo]", str(RAIZ / "docs" / "horarios_ejemplo.csv"))
        pg.click("#form-csv button[type=submit]")
        pg.wait_for_selector("#resultado-csv .aviso")
        foto("a06_carga_csv", "#form-csv >> xpath=..", espera=700)
        pg.click("#btn-nuevo-horario")
        elegir("#form-horario [name=espacio_id]", "Auditorio Principal")
        pg.fill("#form-horario [name=materia]", "Semana de la Ingeniería")
        pg.fill("#form-horario [name=docente]", "Decanatura")
        elegir("#form-horario [name=dia_semana]", "Viernes")
        foto("a07_nueva_clase", "#modal-horario")
        cerrar_modales()
        pg.click(".subtab[data-sub=usuarios]")
        pg.wait_for_selector("#tabla-usuarios tbody tr")
        foto("a08_usuarios")
        pg.locator("#tabla-usuarios tr", has_text="Pedro Ruiz").locator("[data-ver-usuario]").click()
        pg.wait_for_selector("#u-contenido .tabla-resp, #u-contenido .item-linea, #u-contenido .vacio")
        foto("a09_ficha_usuario", "#modal-usuario", espera=900)
        pg.click(".subtabs-u [data-u=sanciones]")
        foto("a10_ficha_sanciones", "#modal-usuario")
        pg.click(".subtabs-u [data-u=reportes]")
        foto("a11_ficha_reportes", "#modal-usuario")
        pg.click("[data-uaccion=suspendido]")
        pg.fill(".dialogo-texto textarea", "Reincidencia en no entregar los espacios a tiempo")
        foto("a12_suspender", ".dialogo-texto")
        pg.locator(".dialogo-texto [data-r='0']").click()
        pg.click("[data-uaccion=alerta]")
        elegir("#plantilla-alerta", "No entregar el espacio a tiempo")
        foto("a13_alerta", "#modal-alerta")
        cerrar_modales()
        pg.click(".subtab[data-sub=incidencias]")
        pg.wait_for_selector("#tabla-sanciones tbody tr")
        foto("a14_incidencias")
        pg.click(".subtab[data-sub=usuarios]")
        pg.locator("#tabla-usuarios tr", has_text="Laura Gómez").locator("[data-ver-usuario]").click()
        pg.wait_for_timeout(1000)
        pg.click("[data-uaccion=reset]")
        pg.locator(".dialogo-confirmar [data-r='1']").click()
        pg.wait_for_timeout(800)
        foto("a15_enlace_recuperacion", ".dialogo-confirmar")
        pg.locator(".dialogo-confirmar [data-r='0']").click()

        pm2 = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True).new_page()
        pm2.goto(BASE)
        pm2.fill("#form-login [name=email]", ADMIN[0])
        pm2.fill("#form-login [name=password]", ADMIN[1])
        pm2.click("#form-login button[type=submit]")
        pm2.wait_for_selector("#vista-espacios:not(.oculto)")
        pm2.click(".nav [data-vista=admin]")
        pm2.click(".subtab[data-sub=usuarios]")
        pm2.wait_for_timeout(1200)
        pm2.screenshot(path=str(OUT / "a16_movil_admin.png"))

        # ---------------------------------------------------------------- documentación técnica (Swagger)
        for s in ["auth", "reservas"]:
            pg.goto(f"{U[s]}/docs")
            pg.wait_for_selector(".opblock", timeout=30000)
            pg.wait_for_timeout(800)
            pg.screenshot(path=str(OUT / f"t01_swagger_{s}.png"))
            print("📸 swagger", s)
        b.close()


if __name__ == "__main__":
    main()
