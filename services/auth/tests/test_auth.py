def registrar(client, email="ana@u.edu", password="Clave1234"):
    return client.post("/registro", json={"nombre": "Ana Pérez", "email": email, "password": password})


def test_registro_y_login(client):
    assert registrar(client).status_code == 201
    r = client.post("/login", json={"email": "ana@u.edu", "password": "Clave1234"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["email"] == "ana@u.edu"
    assert me.json()["rol"] == "estudiante"


def test_correo_duplicado(client):
    registrar(client)
    assert registrar(client).status_code == 409


def test_password_debil(client):
    assert registrar(client, password="solo-letras").status_code == 422


def test_nombre_con_script_rechazado(client):
    r = client.post("/registro", json={"nombre": "<script>", "email": "x@u.edu", "password": "Clave1234"})
    assert r.status_code == 422


def test_login_incorrecto_y_bloqueo(client):
    registrar(client)
    for _ in range(5):
        assert client.post("/login", json={"email": "ana@u.edu", "password": "mala123"}).status_code == 401
    assert client.post("/login", json={"email": "ana@u.edu", "password": "Clave1234"}).status_code == 429


def test_token_invalido(client):
    assert client.get("/me", headers={"Authorization": "Bearer basura"}).status_code == 401


def test_solo_admin_lista_usuarios(client):
    registrar(client)
    t = client.post("/login", json={"email": "ana@u.edu", "password": "Clave1234"}).json()["access_token"]
    assert client.get("/usuarios", headers={"Authorization": f"Bearer {t}"}).status_code == 403
    ta = client.post("/login", json={"email": "admin@reservacampus.edu", "password": "Admin12345"}).json()["access_token"]
    assert client.get("/usuarios", headers={"Authorization": f"Bearer {ta}"}).status_code == 200


# ---------------- gestión de usuarios (admin)
def admin_h(client):
    t = client.post("/login", json={"email": "admin@reservacampus.edu", "password": "Admin12345"}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


def login_h(client, email="ana@u.edu", password="Clave1234"):
    r = client.post("/login", json={"email": email, "password": password})
    return r, ({"Authorization": f"Bearer {r.json()['access_token']}"} if r.status_code == 200 else None)


def test_admin_busca_usuarios(client):
    registrar(client)
    registrar(client, email="beto@u.edu")
    r = client.get("/usuarios", params={"q": "beto"}, headers=admin_h(client))
    assert [u["email"] for u in r.json()] == ["beto@u.edu"]


def test_bloquear_impide_login_y_reactivar(client):
    uid = registrar(client).json()["id"]
    adm = admin_h(client)
    assert client.patch(f"/usuarios/{uid}/estado", json={"estado": "bloqueado", "motivo": "corto"},
                        headers=adm).status_code == 422
    r = client.patch(f"/usuarios/{uid}/estado", json={"estado": "bloqueado", "motivo": "Uso indebido de espacios"},
                     headers=adm)
    assert r.json()["estado"] == "bloqueado"
    r, _ = login_h(client)
    assert r.status_code == 403 and "Uso indebido" in r.json()["detail"]
    client.patch(f"/usuarios/{uid}/estado", json={"estado": "activo"}, headers=adm)
    assert login_h(client)[0].status_code == 200


def test_suspendido_puede_entrar_y_me_lo_informa(client):
    from app.eventos import publicador
    uid = registrar(client).json()["id"]
    client.patch(f"/usuarios/{uid}/estado", json={"estado": "suspendido", "motivo": "Inasistencias repetidas"},
                 headers=admin_h(client))
    assert publicador.enviados[-1]["tipo"] == "usuario.estado_cambiado"
    r, h = login_h(client)
    assert r.status_code == 200 and client.get("/me", headers=h).json()["estado"] == "suspendido"


def test_admin_no_se_bloquea_a_si_mismo(client):
    adm = admin_h(client)
    me = client.get("/me", headers=adm).json()
    r = client.patch(f"/usuarios/{me['id']}/estado", json={"estado": "bloqueado", "motivo": "prueba de bloqueo"},
                     headers=adm)
    assert r.status_code == 409


def test_recuperar_password_con_enlace(client):
    from app.eventos import publicador
    registrar(client)
    r = client.post("/recuperar", json={"email": "ana@u.edu"})
    assert r.status_code == 200
    # respuesta idéntica para un correo inexistente (no revela usuarios)
    assert client.post("/recuperar", json={"email": "nadie@u.edu"}).json() == r.json()
    import json
    enlace = json.loads(publicador.enviados[-1]["datos"])["enlace"]
    token = enlace.split("reset=")[1]
    assert client.post("/restablecer", json={"token": token, "password": "Nueva12345"}).status_code == 200
    assert login_h(client, password="Nueva12345")[0].status_code == 200
    # el token es de un solo uso
    assert client.post("/restablecer", json={"token": token, "password": "Otra12345"}).status_code == 400


def test_admin_genera_enlace_de_recuperacion(client):
    uid = registrar(client).json()["id"]
    r = client.post(f"/usuarios/{uid}/restablecer", headers=admin_h(client))
    assert "reset=" in r.json()["enlace"]
    _, h = login_h(client)
    assert client.post(f"/usuarios/{uid}/restablecer", headers=h).status_code == 403


def test_cambiar_password_propia(client):
    registrar(client)
    _, h = login_h(client)
    assert client.post("/me/password", json={"actual": "mala", "nueva": "Nueva12345"}, headers=h).status_code == 400
    assert client.post("/me/password", json={"actual": "Clave1234", "nueva": "Nueva12345"}, headers=h).status_code == 200
