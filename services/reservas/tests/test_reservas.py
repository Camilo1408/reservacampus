from datetime import date, datetime, time, timedelta

import pytest
from conftest import token

from app.reglas import ReglaVioladaError, se_solapan, validar_horario

MANANA = (date.today() + timedelta(days=1)).isoformat()


def reserva(espacio_id=1, inicio="10:00", fin="11:00", fecha=MANANA, asistentes=2):
    return {"espacio_id": espacio_id, "fecha": fecha, "hora_inicio": inicio, "hora_fin": fin,
            "asistentes": asistentes, "motivo": "Estudio parcial"}


# ---------------- reglas puras
def test_solapamiento():
    assert se_solapan(time(10), time(11), time(10, 30), time(12))
    assert not se_solapan(time(10), time(11), time(11), time(12))


@pytest.mark.parametrize("ini,fin", [(time(11), time(10)), (time(10, 15), time(11)), (time(8), time(12)),
                                     (time(6), time(7))])
def test_horarios_invalidos(ini, fin):
    with pytest.raises(ReglaVioladaError):
        validar_horario(date.today() + timedelta(days=1), ini, fin, time(7), time(21))


def test_no_reservar_en_pasado():
    ayer = datetime.now() - timedelta(days=1)
    with pytest.raises(ReglaVioladaError):
        validar_horario(ayer.date(), time(10), time(11), time(7), time(21))


# ---------------- API
def test_lista_espacios_sembrados(client):
    r = client.get("/espacios")
    assert r.status_code == 200 and len(r.json()) >= 5


def test_crear_reserva_publica_evento(client):
    from app.eventos import publicador
    r = client.post("/reservas", json=reserva(), headers=token())
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "confirmada"
    assert publicador.enviados[-1]["tipo"] == "reserva.creada"


def test_requiere_login(client):
    assert client.post("/reservas", json=reserva()).status_code == 401


def test_conflicto_de_horario(client):
    assert client.post("/reservas", json=reserva(), headers=token(1)).status_code == 201
    r = client.post("/reservas", json=reserva(inicio="10:30", fin="11:30"), headers=token(2))
    assert r.status_code == 409


def test_capacidad_excedida(client):
    assert client.post("/reservas", json=reserva(asistentes=50), headers=token()).status_code == 422


def test_maximo_reservas_activas(client):
    for i, h in enumerate(["08:00", "09:00", "10:00"]):
        fin = f"{int(h[:2]) + 1:02d}:00"
        assert client.post("/reservas", json=reserva(inicio=h, fin=fin), headers=token()).status_code == 201
    assert client.post("/reservas", json=reserva(inicio="12:00", fin="13:00"), headers=token()).status_code == 409


def test_cancelar_solo_dueno(client):
    rid = client.post("/reservas", json=reserva(), headers=token(1)).json()["id"]
    assert client.post(f"/reservas/{rid}/cancelar", headers=token(2)).status_code == 404
    r = client.post(f"/reservas/{rid}/cancelar", headers=token(1))
    assert r.status_code == 200 and r.json()["estado"] == "cancelada"
    # el horario queda libre otra vez
    assert client.post("/reservas", json=reserva(), headers=token(2)).status_code == 201


def test_disponibilidad(client):
    client.post("/reservas", json=reserva(), headers=token())
    r = client.get("/disponibilidad", params={"fecha": MANANA, "hora_inicio": "10:00", "hora_fin": "11:00"})
    sala = next(d for d in r.json() if d["espacio"]["id"] == 1)
    assert sala["libre"] is False


def test_crear_espacio_solo_admin(client):
    nuevo = {"nombre": "Sala Nueva", "tipo": "sala_estudio", "capacidad": 5, "ubicacion": "Piso 3"}
    assert client.post("/espacios", json=nuevo, headers=token()).status_code == 403
    assert client.post("/espacios", json=nuevo, headers=token(99, "admin")).status_code == 201


# ---------------- horarios de clase, administración y revocación
def proximo(dia_semana: int) -> str:
    d = date.today() + timedelta(days=1)
    while d.weekday() != dia_semana:
        d += timedelta(days=1)
    return d.isoformat()


def test_clase_bloquea_reserva(client):
    # Semilla: Laboratorio de Cómputo 1 (id 4) tiene Programación I los lunes 8-10
    r = client.post("/reservas", json=reserva(espacio_id=4, inicio="09:00", fin="10:00", fecha=proximo(0)), headers=token())
    assert r.status_code == 409 and "clase" in r.json()["detail"]
    occ = client.get("/espacios/4/ocupacion", params={"fecha": proximo(0)}).json()
    assert any(f["tipo"] == "clase" for f in occ)


def test_crear_horario_reporta_conflictos(client):
    rid = client.post("/reservas", json=reserva(), headers=token()).json()["id"]
    dia = date.fromisoformat(MANANA).weekday()
    h = {"espacio_id": 1, "dia_semana": dia, "hora_inicio": "09:00", "hora_fin": "12:00", "materia": "Cálculo"}
    assert client.post("/horarios", json=h, headers=token()).status_code == 403
    r = client.post("/horarios", json=h, headers=token(99, "admin"))
    assert r.status_code == 201 and r.json()["conflictos"][0]["reserva_id"] == rid


def test_carga_masiva_csv(client):
    filas = [{"espacio": "Sala de Estudio A-102", "dia": "martes", "hora_inicio": "08:00", "hora_fin": "10:00",
              "materia": "Álgebra"},
             {"espacio": "No existe", "dia": "lunes", "hora_inicio": "08:00", "hora_fin": "09:00", "materia": "X"}]
    r = client.post("/horarios/carga", json={"filas": filas}, headers=token(99, "admin"))
    assert r.json()["creados"] == 0 and "Fila 3" in r.json()["errores"][0]  # todo o nada
    r = client.post("/horarios/carga", json={"filas": filas[:1], "reemplazar": True}, headers=token(99, "admin"))
    assert r.json()["creados"] == 1
    assert len(client.get("/horarios", params={"espacio_id": 2}).json()) == 1


def test_revocar_con_justificacion(client):
    from app.eventos import publicador
    rid = client.post("/reservas", json=reserva(), headers=token(1)).json()["id"]
    assert client.post(f"/reservas/{rid}/revocar", json={"justificacion": "Mantenimiento eléctrico"},
                       headers=token(1)).status_code == 403
    assert client.post(f"/reservas/{rid}/revocar", json={"justificacion": "corta"},
                       headers=token(99, "admin")).status_code == 422
    r = client.post(f"/reservas/{rid}/revocar", json={"justificacion": "Mantenimiento eléctrico del bloque"},
                    headers=token(99, "admin"))
    assert r.json()["estado"] == "revocada" and r.json()["motivo_revocacion"].startswith("Mantenimiento")
    ev = publicador.enviados[-1]
    assert ev["tipo"] == "reserva.revocada" and "Mantenimiento" in ev["datos"]


def test_deshabilitar_y_eliminar_espacio(client):
    adm = token(99, "admin")
    assert client.patch("/espacios/2/estado", json={"activo": False}, headers=adm).json()["activo"] is False
    assert all(e["id"] != 2 for e in client.get("/espacios").json())
    assert any(e["id"] == 2 for e in client.get("/admin/espacios", headers=adm).json())
    assert client.post("/reservas", json=reserva(espacio_id=2), headers=token()).status_code == 404
    # no se elimina con reservas futuras
    client.post("/reservas", json=reserva(espacio_id=1), headers=token())
    assert client.delete("/espacios/1", headers=adm).status_code == 409
    assert client.delete("/espacios/2", headers=adm).status_code == 204


def test_editar_espacio(client):
    adm = token(99, "admin")
    e = client.get("/espacios/1").json()
    e.update(capacidad=8, nombre="Sala A-101 Renovada")
    r = client.put("/espacios/1", json=e, headers=adm)
    assert r.status_code == 200 and r.json()["capacidad"] == 8


def test_espacio_recreativo_con_actividades(client):
    nuevo = {"nombre": "Sala Gamer", "tipo": "recreacion", "capacidad": 12, "ubicacion": "Bienestar, piso 2",
             "actividades": "videojuegos, juegos de mesa"}
    r = client.post("/espacios", json=nuevo, headers=token(99, "admin"))
    assert r.status_code == 201 and r.json()["actividades"] == "videojuegos, juegos de mesa"
    assert any(e["nombre"] == "Sala Gamer" for e in client.get("/espacios", params={"tipo": "recreacion"}).json())
