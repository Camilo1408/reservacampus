"""E2E de gestión de usuarios, sanciones, alertas y recuperación de contraseña."""
import re
import uuid
from datetime import date, timedelta

from playwright.sync_api import expect

from conftest import ADMIN, iniciar_sesion, ir_admin, registrar


def unico():
    return f"e2e{uuid.uuid4().hex[:8]}@u.edu"


def nueva_sesion(browser, base_url):
    ctx = browser.new_context()
    p = ctx.new_page()
    p.set_default_timeout(10000)
    p.goto(base_url)
    return ctx, p


def abrir_ficha(adm, email):
    ir_admin(adm, "usuarios")
    adm.fill("#buscar-usuario", email)
    fila = adm.locator("#tabla-usuarios tr", has_text=email)
    fila.locator("[data-ver-usuario]").click()
    expect(adm.locator("#modal-usuario")).to_be_visible()
    expect(adm.locator("#u-email")).to_contain_text(email)


def intentar_reservar(page):
    page.click(".nav [data-vista=espacios]")
    page.locator("article.espacio", has_text="Sala de Estudio A-102").locator("[data-reservar]").click()
    page.fill("#form-reserva [name=fecha]", (date.today() + timedelta(days=4)).isoformat())
    page.click("#form-reserva button[type=submit]")


def test_admin_suspende_y_reactiva_usuario(pagina, browser, base_url):
    email = unico()
    registrar(pagina, "Sofía Suspendida", email)
    ctx, adm = nueva_sesion(browser, base_url)
    iniciar_sesion(adm, *ADMIN)
    abrir_ficha(adm, email)
    adm.click("[data-uaccion=suspendido]")
    adm.fill(".dialogo-texto textarea", "Reincidencia en no entregar espacios")
    adm.click(".dialogo-texto button[type=submit]")
    expect(adm.locator("#u-chips")).to_contain_text("suspendido")

    intentar_reservar(pagina)
    expect(pagina.locator("#reserva-error")).to_contain_text("suspendido")
    pagina.keyboard.press("Escape")
    pagina.reload()
    expect(pagina.locator("#banner-sancion")).to_contain_text("suspendida")

    adm.click("[data-uaccion=activo]")
    adm.locator(".dialogo-confirmar [data-r='1']").click()
    expect(adm.locator("#u-chips")).to_contain_text("activo")
    ctx.close()


def test_admin_bloquea_y_no_puede_iniciar_sesion(pagina, browser, base_url):
    email = unico()
    registrar(pagina, "Bruno Bloqueado", email)
    pagina.click("#btn-salir")
    ctx, adm = nueva_sesion(browser, base_url)
    iniciar_sesion(adm, *ADMIN)
    abrir_ficha(adm, email)
    adm.click("[data-uaccion=bloqueado]")
    adm.fill(".dialogo-texto textarea", "Daños reiterados al mobiliario")
    adm.click(".dialogo-texto button[type=submit]")
    expect(adm.locator("#u-chips")).to_contain_text("bloqueado")
    ctx.close()

    pagina.fill("#form-login [name=email]", email)
    pagina.fill("#form-login [name=password]", "Clave1234")
    pagina.click("#form-login button[type=submit]")
    expect(pagina.locator("#auth-error")).to_contain_text("bloqueada")
    expect(pagina.locator("#auth-error")).to_contain_text("Daños reiterados")


def test_admin_restablece_contrasena_con_enlace(pagina, browser, base_url):
    email = unico()
    registrar(pagina, "Rita Reset", email)
    pagina.click("#btn-salir")
    ctx, adm = nueva_sesion(browser, base_url)
    iniciar_sesion(adm, *ADMIN)
    abrir_ficha(adm, email)
    adm.click("[data-uaccion=reset]")
    adm.locator(".dialogo-confirmar [data-r='1']").click()
    texto = adm.locator(".dialogo-confirmar p.sub").inner_text()
    enlace = re.search(r"https?://\S+\?reset=\S+", texto).group(0)
    ctx.close()

    pagina.goto(enlace)
    expect(pagina.locator("#modal-restablecer")).to_be_visible()
    pagina.fill("#form-restablecer [name=password]", "NuevaClave123")
    pagina.fill("#form-restablecer [name=password2]", "OtraCosa123")
    pagina.click("#form-restablecer button[type=submit]")
    expect(pagina.locator("#form-restablecer .error")).to_contain_text("no coinciden")
    pagina.fill("#form-restablecer [name=password2]", "NuevaClave123")
    pagina.click("#form-restablecer button[type=submit]")
    expect(pagina.locator("#toast")).to_contain_text("Contraseña actualizada")
    iniciar_sesion(pagina, email, "NuevaClave123")


def test_recuperar_contrasena_respuesta_generica(pagina):
    pagina.click("#btn-olvide")
    pagina.fill("#form-recuperar [name=email]", unico())
    pagina.click("#form-recuperar button[type=submit]")
    expect(pagina.locator("#toast")).to_contain_text("Si el correo está registrado")


def test_sancion_manual_bloquea_y_se_levanta_desde_incidencias(pagina, browser, base_url):
    email = unico()
    registrar(pagina, "Mario Sancionado", email)
    ctx, adm = nueva_sesion(browser, base_url)
    iniciar_sesion(adm, *ADMIN)
    abrir_ficha(adm, email)
    adm.click("[data-uaccion=sancion]")
    adm.fill("#form-sancion [name=motivo]", "Dejó el laboratorio desordenado")
    adm.click("#form-sancion button[type=submit]")
    expect(adm.locator("#u-chips")).to_contain_text("Manual")

    pagina.reload()
    expect(pagina.locator("#banner-sancion")).to_contain_text("sanción vigente")
    intentar_reservar(pagina)
    expect(pagina.locator("#reserva-error")).to_contain_text("sanción vigente")
    pagina.keyboard.press("Escape")

    adm.keyboard.press("Escape")
    ir_admin(adm, "incidencias")
    fila = adm.locator("#tabla-sanciones tr", has_text=email)
    fila.locator("[data-levantar]").click()
    adm.fill(".dialogo-texto textarea", "Ordenó el laboratorio")
    adm.click(".dialogo-texto button[type=submit]")
    expect(adm.locator("#tabla-sanciones tr", has_text=email)).to_have_count(0)  # filtro: solo vigentes
    ctx.close()

    pagina.reload()
    expect(pagina.locator("#banner-sancion")).to_be_hidden()
    pagina.click(".nav [data-vista=mis-reservas]")
    expect(pagina.locator("#mis-sanciones")).to_contain_text("Ordenó el laboratorio")


def test_admin_envia_alerta_con_plantilla(pagina, browser, base_url):
    email = unico()
    registrar(pagina, "Alba Alertada", email)
    ctx, adm = nueva_sesion(browser, base_url)
    iniciar_sesion(adm, *ADMIN)
    abrir_ficha(adm, email)
    adm.click("[data-uaccion=alerta]")
    caja = adm.locator("#plantilla-alerta").locator("xpath=following-sibling::div[contains(@class,'sel')][1]")
    caja.locator(".sel-boton").click()
    caja.locator(".sel-lista li", has_text="No confirmar llegada").click()
    expect(adm.locator("#form-alerta [name=asunto]")).to_have_value("Confirma tu llegada a las reservas")
    adm.click("#form-alerta button[type=submit]")
    expect(adm.locator("#toast")).to_contain_text("Alerta enviada")
    adm.click(".subtabs-u [data-u=avisos]")
    expect(adm.locator("#u-contenido")).to_contain_text("Confirma tu llegada")
    ctx.close()

    pagina.click("#btn-notif")
    expect(pagina.locator("#lista-notif")).to_contain_text("Confirma tu llegada a las reservas")


def test_ficha_y_paneles_sin_desborde_en_movil(pagina):
    pagina.set_viewport_size({"width": 375, "height": 812})
    iniciar_sesion(pagina, *ADMIN)
    for sub in ["usuarios", "incidencias"]:
        ir_admin(pagina, sub)
        assert pagina.evaluate("document.documentElement.scrollWidth") <= 375, sub
    ir_admin(pagina, "usuarios")
    pagina.locator("[data-ver-usuario]").first.click()
    expect(pagina.locator("#modal-usuario")).to_be_visible()
    ancho = pagina.evaluate("document.querySelector('#modal-usuario').scrollWidth")
    assert ancho <= 375
