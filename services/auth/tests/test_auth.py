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
