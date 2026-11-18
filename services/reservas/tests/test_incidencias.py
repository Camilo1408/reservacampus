"""Llegada, reportes de espacio no entregado, sanciones escalonadas y programador de tareas (con reloj simulado)."""
import json
from datetime import date, datetime, time, timedelta

import pytest
from conftest import token

MANANA = date.today() + timedelta(days=1)
A = dict(uid=1, nombre="Ana", email="ana@u.edu")
B = dict(uid=2, nombre="Beto", email="beto@u.edu")
ADMIN = token(99, "admin", "Admin", "admin@u.edu")


def h(u):
    return token(u["uid"], nombre=u["nombre"], email=u["email"])


@pytest.fixture()
def reloj(monkeypatch):
    """Permite fijar la hora del sistema: reloj(datetime(...))."""
    from app import reloj as modulo
    estado = {"ahora": datetime.combine(date.today(), time(6, 0))}
    monkeypatch.setattr(modulo, "ahora", lambda: estado["ahora"])

    def fijar(valor: datetime):
        estado["ahora"] = valor
    return fijar


def en(hh, mm=0, dia=MANANA):
    return datetime.combine(dia, time(hh, mm))


def reservar(client, u, ini, fin, espacio=1, fecha=MANANA):
    r = client.post("/reservas", headers=h(u), json={"espacio_id": espacio, "fecha": fecha.isoformat(),
                                                    "hora_inicio": ini, "hora_fin": fin})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def tareas(client):
    return client.post("/tareas/ejecutar", headers={"X-Tareas-Token": "token-tareas-test"}).json()


def eventos(tipo):
    from app.eventos import publicador
    return [json.loads(e["datos"]) for e in publicador.enviados if e["tipo"] == tipo]


# ---------------------------------------------------------------- confirmación de llegada
def test_confirmar_llegada_solo_en_la_ventana(client, reloj):
    rid = reservar(client, A, "10:00", "11:00")
    reloj(en(9, 45))
    r = client.post(f"/reservas/{rid}/confirmar-llegada", headers=h(A))
    assert r.status_code == 409 and "09:50" in r.json()["detail"]
    reloj(en(9, 55))
    assert client.post(f"/reservas/{rid}/confirmar-llegada", headers=h(B)).status_code == 404  # no es suya
    assert client.post(f"/reservas/{rid}/confirmar-llegada", headers=h(A)).status_code == 200
    mia = client.get("/reservas/mias", headers=h(A)).json()[0]
    assert mia["llegada_confirmada_en"] is not None


def test_confirmar_tarde_no_se_permite(client, reloj):
    rid = reservar(client, A, "10:00", "11:00")
    reloj(en(10, 21))
    assert client.post(f"/reservas/{rid}/confirmar-llegada", headers=h(A)).status_code == 409


# ---------------------------------------------------------------- programador de tareas
def test_linea_de_tiempo_sin_confirmar_termina_en_sancion(client, reloj):
    rid = reservar(client, A, "10:00", "11:00")
    reloj(en(9, 51))
    assert tareas(client)["recordatorios"] == 1
    assert tareas(client)["recordatorios"] == 0  # idempotente
    reloj(en(10, 1))
    assert tareas(client)["avisos_inicio"] == 1
    reloj(en(10, 12))
    assert tareas(client)["avisos_finales"] == 1
    assert eventos("reserva.aviso_inasistencia")[0]["limite"] == "10:20"
    reloj(en(10, 21))
    assert tareas(client)["inasistencias"] == 1
    assert client.get("/reservas/mias", headers=h(A)).json()[0]["estado"] == "inasistencia"
    sanc = client.get("/sanciones/mias", headers=h(A)).json()
    assert sanc[0]["tipo"] == "inasistencia" and sanc[0]["nivel"] == 1 and sanc[0]["activa"]
    assert eventos("sancion.aplicada")[0]["usuario_email"] == "ana@u.edu"
    assert eventos("reserva.recordatorio")[0]["enlace"].endswith(f"?confirmar={rid}")


def test_confirmada_no_genera_avisos_ni_sancion(client, reloj):
    rid = reservar(client, A, "10:00", "11:00")
    reloj(en(10, 2))
    client.post(f"/reservas/{rid}/confirmar-llegada", headers=h(A))
    reloj(en(10, 30))
    assert tareas(client) == {"recordatorios": 0, "avisos_inicio": 0, "avisos_finales": 0, "inasistencias": 0}


def test_servicio_dormido_procesa_inasistencia_al_despertar(client, reloj):
    reservar(client, A, "10:00", "11:00")
    reloj(en(13, 0))  # el programador no corrió durante la reserva
    res = tareas(client)
    assert res["inasistencias"] == 1 and res["recordatorios"] == 0  # avisos vencidos se omiten


def test_endpoint_tareas_requiere_token(client):
    assert client.post("/tareas/ejecutar").status_code == 403
    assert client.post("/tareas/ejecutar", headers={"X-Tareas-Token": "malo"}).status_code == 403


# ---------------------------------------------------------------- reporte de espacio no entregado
def test_reportar_ocupante_anterior(client, reloj):
    reservar(client, A, "07:00", "08:00")
    rid_b = reservar(client, B, "08:00", "09:00")
    reloj(en(8, 5))
    r = client.post(f"/reservas/{rid_b}/reportar-ocupado", json={"comentario": "Siguen adentro"}, headers=h(B))
    assert r.status_code == 409 and "08:10" in r.json()["detail"]  # tolerancia de 10 min
    reloj(en(8, 12))
    r = client.post(f"/reservas/{rid_b}/reportar-ocupado", json={"comentario": "Siguen adentro"}, headers=h(B))
    assert r.status_code == 201 and r.json()["reportado_id"] == 1
    assert client.post(f"/reservas/{rid_b}/reportar-ocupado", json={}, headers=h(B)).status_code == 409  # duplicado
    # A queda sancionado (nivel 1: no puede reservar al día siguiente) y B cuenta como presente
    sanc = client.get("/sanciones/mias", headers=h(A)).json()[0]
    assert sanc["tipo"] == "ocupacion" and sanc["nivel"] == 1
    assert sanc["hasta"].startswith((MANANA + timedelta(days=2)).isoformat())
    r = client.post("/reservas", headers=h(A), json={"espacio_id": 2, "fecha": (MANANA + timedelta(days=1)).isoformat(),
                                                     "hora_inicio": "10:00", "hora_fin": "11:00"})
    assert r.status_code == 403 and "sanción vigente" in r.json()["detail"]
    assert client.get("/reservas/mias", headers=h(B)).json()[0]["llegada_confirmada_en"] is not None


def test_no_se_puede_reportar_sin_reserva_anterior(client, reloj):
    rid = reservar(client, B, "08:00", "09:00")
    reloj(en(8, 15))
    r = client.post(f"/reservas/{rid}/reportar-ocupado", json={}, headers=h(B))
    assert r.status_code == 409 and "inmediatamente anterior" in r.json()["detail"]


# ---------------------------------------------------------------- escalamiento
@pytest.mark.parametrize("n,nivel,dias", [(1, 1, None), (2, 2, 3), (3, 3, 7), (4, 4, None), (5, 4, None)])
def test_escalamiento_de_sanciones(client, n, nivel, dias):
    from app import sanciones
    from app.database import SessionLocal
    ahora = datetime(2026, 11, 18, 10, 0)
    with SessionLocal() as db:
        for _ in range(n):
            s = sanciones.aplicar(db, usuario_id=7, email="x@u.edu", nombre="X", tipo="inasistencia",
                                  motivo="prueba", ahora=ahora)
    assert s.nivel == nivel
    if nivel == 1:
        assert s.hasta == datetime(2026, 11, 20, 0, 0)  # todo el día siguiente
    elif nivel == 4:
        assert s.hasta is None  # suspensión hasta que el admin la levante
    else:
        assert s.hasta == ahora + timedelta(days=dias)


def test_reporte_anulado_no_cuenta_para_reincidencia(client, reloj):
    reservar(client, A, "07:00", "08:00")
    rid_b = reservar(client, B, "08:00", "09:00")
    reloj(en(8, 15))
    rep = client.post(f"/reservas/{rid_b}/reportar-ocupado", json={}, headers=h(B)).json()
    r = client.post(f"/admin/reportes/{rep['id']}/anular", json={"nota": "El espacio estaba libre"}, headers=ADMIN)
    assert r.json()["estado"] == "anulado"
    assert client.get("/sanciones/mias", headers=h(A)).json()[0]["estado"] == "anulada"
    from app import sanciones
    from app.database import SessionLocal
    with SessionLocal() as db:
        assert sanciones.nivel_siguiente(db, 1) == 1


# ---------------------------------------------------------------- administración
def test_admin_sancion_manual_y_levantar(client, reloj):
    reloj(en(7, 0, date.today()))
    s = client.post("/admin/sanciones", headers=ADMIN, json={"usuario_id": 1, "usuario_email": "ana@u.edu",
                                                            "usuario_nombre": "Ana", "motivo": "Daño al mobiliario"})
    assert s.status_code == 201 and s.json()["hasta"] is None and s.json()["activa"]
    r = client.post("/reservas", headers=h(A), json={"espacio_id": 1, "fecha": MANANA.isoformat(),
                                                     "hora_inicio": "10:00", "hora_fin": "11:00"})
    assert r.status_code == 403
    assert client.post(f"/admin/sanciones/{s.json()['id']}/levantar", json={"nota": "Pagó el daño"},
                       headers=h(A)).status_code == 403
    r = client.post(f"/admin/sanciones/{s.json()['id']}/levantar", json={"nota": "Pagó el daño"}, headers=ADMIN)
    assert r.json()["estado"] == "levantada" and not r.json()["activa"]
    assert eventos("sancion.levantada")
    reservar(client, A, "10:00", "11:00")


def test_admin_resumen_e_historial(client, reloj):
    reservar(client, A, "07:00", "08:00")
    rid_b = reservar(client, B, "08:00", "09:00")
    reloj(en(8, 15))
    client.post(f"/reservas/{rid_b}/reportar-ocupado", json={}, headers=h(B))
    res = client.get("/admin/usuarios/resumen", headers=ADMIN).json()
    assert res["1"]["reportes_recibidos"] == 1 and res["1"]["sancion_activa"]["nivel"] == 1
    assert res["2"]["reservas"] == 1
    hist = client.get("/admin/usuarios/1/historial", headers=ADMIN).json()
    assert len(hist["reservas"]) == 1 and len(hist["sanciones"]) == 1 and len(hist["reportes_recibidos"]) == 1
    assert client.get("/admin/usuarios/resumen", headers=h(A)).status_code == 403
    st = client.get("/estadisticas", headers=ADMIN).json()
    assert st["sanciones_activas"] == 1 and st["reportes"] == 1
