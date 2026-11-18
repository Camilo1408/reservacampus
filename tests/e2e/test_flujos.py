"""Pruebas end-to-end de ReservaCampus: recorren la interfaz como lo haría un usuario real."""
import uuid
from datetime import date, timedelta

from playwright.sync_api import expect

from conftest import ADMIN, abrir, elegir, iniciar_sesion, ir_admin, registrar


def unico(prefijo="u"):
    return f"{prefijo}{uuid.uuid4().hex[:8]}"


def proximo(dia_semana: int) -> date:
    d = date.today() + timedelta(days=1)
    while d.weekday() != dia_semana:
        d += timedelta(days=1)
    return d


def reservar(page, espacio, fecha: date, inicio, fin, asistentes=1):
    page.click(".nav [data-vista=espacios]")
    tarjeta = page.locator("article.espacio", has_text=espacio)
    tarjeta.locator("[data-reservar]").click()
    page.fill("#form-reserva [name=fecha]", fecha.isoformat())
    page.dispatch_event("#form-reserva [name=fecha]", "change")
    elegir(page, "#form-reserva [name=hora_inicio]", inicio)
    elegir(page, "#form-reserva [name=hora_fin]", fin)
    page.fill("#form-reserva [name=asistentes]", str(asistentes))
    page.click("#form-reserva button[type=submit]")


# ------------------------------------------------------------------ autenticación
def test_registro_login_y_validaciones(pagina):
    pagina.click(".tab[data-tab=registro]")
    pagina.fill("#form-registro [name=nombre]", "Ana Prueba")
    pagina.fill("#form-registro [name=email]", f"{unico()}@u.edu")
    pagina.fill("#form-registro [name=password]", "sololetras")
    pagina.click("#form-registro button[type=submit]")
    expect(pagina.locator("#auth-error")).to_contain_text("letras y números")

    registrar(pagina, "Ana Prueba", f"{unico()}@u.edu")
    expect(pagina.locator("#usuario-nombre")).to_contain_text("Ana")
    expect(pagina.locator(".nav [data-vista=admin]")).to_be_hidden()  # un estudiante no ve Administración


def test_login_incorrecto(pagina):
    pagina.fill("#form-login [name=email]", "nadie@u.edu")
    pagina.fill("#form-login [name=password]", "Mala1234")
    pagina.click("#form-login button[type=submit]")
    expect(pagina.locator("#auth-error")).to_contain_text("incorrectos")


# ------------------------------------------------------------------ estudiante
def test_filtro_con_select_personalizado(pagina):
    registrar(pagina, "Filtro Prueba", f"{unico()}@u.edu")
    elegir(pagina, "#filtro-tipo", "Laboratorios")
    expect(pagina.locator("article.espacio")).to_have_count(2)
    expect(pagina.locator(".filtros .sel-texto")).to_have_text("Laboratorios")


def test_reservar_y_cancelar_con_dialogo(pagina):
    registrar(pagina, "Carlos Reserva", f"{unico()}@u.edu")
    manana = date.today() + timedelta(days=1)
    reservar(pagina, "Sala de Estudio A-102", manana, "07:00", "08:00", asistentes=2)
    expect(pagina.locator("#toast")).to_contain_text("Reserva confirmada")

    pagina.click(".nav [data-vista=mis-reservas]")
    fila = pagina.locator("article.reserva", has_text="Sala de Estudio A-102")
    expect(fila.locator(".estado")).to_have_text("confirmada")
    fila.locator("[data-cancelar]").click()
    dialogo = pagina.locator(".dialogo-confirmar")
    expect(dialogo).to_be_visible()
    dialogo.locator("[data-r='1']").click()
    expect(fila.locator(".estado")).to_have_text("cancelada")


def test_capacidad_excedida_muestra_error(pagina):
    registrar(pagina, "Grupo Grande", f"{unico()}@u.edu")
    # El navegador limita el campo a la capacidad; se quita el límite para comprobar la validación del servidor
    pagina.locator("article.espacio", has_text="Sala de Estudio A-102").locator("[data-reservar]").click()
    pagina.fill("#form-reserva [name=fecha]", (date.today() + timedelta(days=2)).isoformat())
    elegir(pagina, "#form-reserva [name=hora_inicio]", "09:00")
    elegir(pagina, "#form-reserva [name=hora_fin]", "10:00")
    pagina.evaluate("document.querySelector('#form-reserva [name=asistentes]').removeAttribute('max')")
    pagina.fill("#form-reserva [name=asistentes]", "9")
    pagina.click("#form-reserva button[type=submit]")
    expect(pagina.locator("#reserva-error")).to_contain_text("capacidad para 4")


def test_clase_fija_bloquea_reserva(pagina):
    registrar(pagina, "Bloqueo Clase", f"{unico()}@u.edu")
    lunes = proximo(0)  # semilla: Laboratorio de Cómputo 1 tiene Programación I los lunes 08:00-10:00
    reservar(pagina, "Laboratorio de Cómputo 1", lunes, "08:00", "09:00")
    expect(pagina.locator("#reserva-error")).to_contain_text("clase de Programación I")
    expect(pagina.locator("#ocupacion-modal")).to_contain_text("clase: Programación I")


# ------------------------------------------------------------------ administrador
def test_admin_crea_edita_deshabilita_y_elimina_espacio(pagina):
    iniciar_sesion(pagina, *ADMIN)
    ir_admin(pagina, "espacios")
    nombre = f"Sala E2E {unico('')}"
    pagina.click("#btn-nuevo-espacio")
    f = pagina.locator("#form-espacio")
    f.locator("[name=nombre]").fill(nombre)
    elegir(pagina, "#form-espacio [name=tipo]", "Laboratorio")
    f.locator("[name=capacidad]").fill("12")
    f.locator("[name=ubicacion]").fill("Bloque E2E")
    f.locator("button[type=submit]").click()
    fila = pagina.locator("#tabla-espacios tr", has_text=nombre)
    expect(fila).to_contain_text("Laboratorio")

    fila.locator("[data-editar]").click()
    f.locator("[name=capacidad]").fill("15")
    f.locator("button[type=submit]").click()
    expect(fila).to_contain_text("15")

    fila.locator("[data-toggle]").click()
    expect(fila.locator(".estado")).to_have_text("Deshabilitado")
    pagina.click(".nav [data-vista=espacios]")
    expect(pagina.locator("article.espacio", has_text=nombre)).to_have_count(0)

    ir_admin(pagina, "espacios")
    fila.locator("[data-eliminar]").click()
    pagina.locator(".dialogo-confirmar [data-r='1']").click()
    expect(fila).to_have_count(0)


def test_admin_agrega_clase_y_carga_csv(pagina, tmp_path):
    iniciar_sesion(pagina, *ADMIN)
    ir_admin(pagina, "horarios")
    pagina.wait_for_selector(".clase")
    antes = pagina.locator(".clase").count()

    pagina.click("#btn-nuevo-horario")
    elegir(pagina, "#form-horario [name=espacio_id]", "Sala de Estudio A-102")
    pagina.fill("#form-horario [name=materia]", "Clase E2E")
    elegir(pagina, "#form-horario [name=dia_semana]", "Sábado")
    pagina.fill("#form-horario [name=hora_inicio]", "08:00")
    pagina.fill("#form-horario [name=hora_fin]", "09:00")
    pagina.click("#form-horario button[type=submit]")
    expect(pagina.locator(".clase", has_text="Clase E2E")).to_be_visible()

    csv = tmp_path / "horarios.csv"
    csv.write_text("espacio,dia,hora_inicio,hora_fin,materia,docente\n"
                   "Sala de Estudio A-101,sabado,08:00,10:00,Taller CSV,Docente E2E\n"
                   "Auditorio Principal,6,09:00,11:00,Evento CSV,\n", encoding="utf-8")
    pagina.set_input_files("#form-csv [name=archivo]", str(csv))
    expect(pagina.locator(".archivo b")).to_have_text("horarios.csv")
    pagina.click("#form-csv button[type=submit]")
    expect(pagina.locator("#resultado-csv")).to_contain_text("2 bloque(s)")
    expect(pagina.locator(".clase")).to_have_count(antes + 3)


def test_csv_con_errores_no_carga_nada(pagina, tmp_path):
    iniciar_sesion(pagina, *ADMIN)
    ir_admin(pagina, "horarios")
    csv = tmp_path / "malo.csv"
    csv.write_text("espacio,dia,hora_inicio,hora_fin,materia\nNo Existe,lunes,08:00,09:00,X\n", encoding="utf-8")
    pagina.set_input_files("#form-csv [name=archivo]", str(csv))
    pagina.click("#form-csv button[type=submit]")
    expect(pagina.locator("#resultado-csv .aviso.mal")).to_contain_text("no existe")


def test_admin_revoca_reserva_y_estudiante_ve_justificacion(pagina, browser, base_url):
    # 1) El estudiante reserva
    email = f"{unico()}@u.edu"
    registrar(pagina, "Laura Revocada", email)
    reservar(pagina, "Cancha Múltiple", date.today() + timedelta(days=3), "19:00", "20:00")
    expect(pagina.locator("#toast")).to_contain_text("Reserva confirmada")

    # 2) El administrador revoca con justificación (otra sesión de navegador)
    ctx = browser.new_context()
    adm = ctx.new_page()
    abrir(adm, base_url)
    iniciar_sesion(adm, *ADMIN)
    ir_admin(adm, "reservas")
    fila = adm.locator("#tabla-reservas tr", has_text=email)
    fila.locator("[data-revocar]").click()
    adm.fill("#form-revocar [name=justificacion]", "corta")
    adm.click("#form-revocar button[type=submit]")
    # La justificación es obligatoria (mín. 10 caracteres): el formulario no se envía
    assert adm.evaluate("document.querySelector('#form-revocar').checkValidity()") is False
    expect(adm.locator("#modal-revocar")).to_be_visible()
    adm.fill("#form-revocar [name=justificacion]", "Torneo deportivo programado por Bienestar.")
    adm.click("#form-revocar button[type=submit]")
    expect(fila.locator(".estado")).to_have_text("revocada")
    ctx.close()

    # 3) El estudiante ve la reserva revocada con el motivo
    pagina.click(".nav [data-vista=mis-reservas]")
    tarjeta = pagina.locator("article.reserva", has_text="Cancha Múltiple")
    expect(tarjeta.locator(".estado")).to_have_text("revocada")
    expect(tarjeta.locator(".motivo")).to_contain_text("Torneo deportivo")


# ------------------------------------------------------------------ chatbot
def test_chatbot_responde_por_reglas(pagina):
    registrar(pagina, "Chat Prueba", f"{unico()}@u.edu")
    pagina.click("#chat-toggle")
    pagina.fill("#chat-input", "¿Cuáles son las reglas?")
    pagina.press("#chat-input", "Enter")
    respuesta = pagina.locator(".msg.bot").last
    expect(respuesta).to_contain_text("Bloques de 30 minutos")
    expect(respuesta.locator(".fuente")).to_contain_text("reglas")


# ------------------------------------------------------------------ responsividad
def test_sin_desborde_horizontal_en_movil(pagina):
    pagina.set_viewport_size({"width": 375, "height": 812})
    iniciar_sesion(pagina, *ADMIN)
    for sub in ["reservas", "espacios", "horarios"]:
        ir_admin(pagina, sub)
        ancho = pagina.evaluate("document.documentElement.scrollWidth")
        assert ancho <= 375, f"La pestaña {sub} desborda: {ancho}px"
    pagina.click("#btn-nuevo-horario")
    assert pagina.evaluate("document.documentElement.scrollWidth") <= 375


def test_chatbot_reconoce_espacio_nuevo_creado_por_admin(pagina):
    iniciar_sesion(pagina, *ADMIN)

    def preguntar(texto):
        pagina.fill("#chat-input", texto)
        pagina.press("#chat-input", "Enter")
        return pagina.locator(".msg.bot").last

    pagina.click("#chat-toggle")
    nombre = f"Sala Gamer {unico('')}"
    # Antes de crearla: no hay espacio para videojuegos (y no ofrece la cancha)
    r = preguntar("y para jugar video juegos")
    expect(r).to_contain_text("no hay espacios para")
    expect(r).not_to_contain_text("✅")
    pagina.click("#chat-cerrar")

    # El admin crea la sala recreativa con sus actividades
    ir_admin(pagina, "espacios")
    pagina.click("#btn-nuevo-espacio")
    f = pagina.locator("#form-espacio")
    f.locator("[name=nombre]").fill(nombre)
    elegir(pagina, "#form-espacio [name=tipo]", "Sala recreativa")
    f.locator("[name=capacidad]").fill("12")
    f.locator("[name=ubicacion]").fill("Bienestar, piso 2")
    f.locator("[name=actividades]").fill("videojuegos, juegos de mesa")
    f.locator("button[type=submit]").click()
    expect(pagina.locator("#tabla-espacios tr", has_text=nombre)).to_contain_text("videojuegos")

    # Ahora el asistente la recomienda
    pagina.click("#chat-toggle")
    r = preguntar("y para jugar video juegos mañana")
    expect(r).to_contain_text("✅ Sí, hay espacios para videojuegos")
    expect(r).to_contain_text(nombre)
    r = preguntar("quiero jugar ajedrez mañana")
    expect(r).to_contain_text(nombre)


def test_mostrar_y_ocultar_contrasena(pagina):
    campo = pagina.locator("#form-login [name=password]")
    boton = pagina.locator("#form-login .pass-toggle")
    campo.fill("Secreta123")
    expect(campo).to_have_attribute("type", "password")
    boton.click()
    expect(campo).to_have_attribute("type", "text")
    expect(boton).to_have_attribute("aria-label", "Ocultar contraseña")
    expect(campo).to_have_value("Secreta123")  # no se pierde lo escrito
    boton.click()
    expect(campo).to_have_attribute("type", "password")
    # todos los campos de contraseña tienen su botón
    assert pagina.locator("input[name^=password]").count() == pagina.locator(".pass-toggle").count()
