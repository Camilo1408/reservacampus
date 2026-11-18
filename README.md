# ReservaCampus — Plataforma distribuida de reserva de espacios universitarios

Proyecto final de Ingeniería de Software II. Los estudiantes reservan salas de estudio, laboratorios,
auditorios y canchas. Incluye un asistente virtual híbrido (reglas + IA con Groq).

## Arquitectura

```
                 ┌──────────────── Navegador (HTML/CSS/JS) ────────────────┐
                 │  login · espacios · mis reservas · admin · chat widget  │
                 └───────────────┬─────────────────────────────────────────┘
                                 │ HTTPS/REST + JWT
                       ┌─────────▼─────────┐   (Nginx en Docker / URLs públicas en Render)
                       │    API Gateway    │
                       └─┬──────┬──────┬───┴──────────────┐
            ┌────────────▼┐ ┌───▼──────────┐ ┌──────────▼──────┐ ┌──────────────┐
            │ auth-service│ │reservas-svc  │ │notificaciones   │ │ chatbot-svc  │
            │ JWT, usuarios│ │espacios,     │ │consumidor de    │ │ reglas + IA  │
            │             │ │reservas      │ │eventos + SMTP   │ │ ──► Groq API │
            └──────┬──────┘ └──┬────────┬──┘ └──▲──────────┬───┘ └──────┬───────┘
                   │           │        │ XADD  │ XREADGROUP│            │ REST
                   │           │     ┌──▼───────┴──┐        │            │ (consulta
                   │           │     │ Redis Stream│        │            │ disponibilidad)
                   │           │     │ eventos.    │        │            ▼
                   ▼           ▼     │ reservas    │        ▼      reservas-svc
              [auth_db]  [reservas_db] └───────────┘ [notificaciones_db]
                         PostgreSQL (una base por servicio)
```

| Servicio | Responsabilidad | Comunicación |
|---|---|---|
| **auth** | Registro, login, emisión de JWT (HS256), rol admin, bloqueo por intentos fallidos | REST síncrono |
| **reservas** | CRUD de espacios, disponibilidad, reservas, reglas de negocio, estadísticas | REST + publica eventos `reserva.creada` / `reserva.cancelada` |
| **notificaciones** | Consume eventos (grupo de consumidores, idempotente), notificaciones in-app, correo SMTP opcional | Asíncrono (Redis Streams) |
| **chatbot** | Motor de reglas (intenciones por palabras clave) + Groq como respaldo; consulta disponibilidad real | REST a reservas + API externa Groq |

**Stack:** Python 3.12, FastAPI, SQLAlchemy 2 (ORM), PostgreSQL 16, Redis 7 (Streams), PyJWT, Nginx, Docker Compose, Render.

## Ejecutar localmente con Docker

```bash
cp .env.example .env      # y pon tu GROQ_API_KEY
docker compose up --build
```
- App: http://localhost:8080 — admin demo `admin@reservacampus.edu` / `Admin12345`
- Swagger: http://localhost:8080/api/auth/docs, `/api/reservas/docs`, `/api/notificaciones/docs`, `/api/chat/docs`

Sin Docker (SQLite, sin cola): `sh scripts/dev_local.sh` (puertos 8001-8004).

## Pruebas automatizadas
| Tipo | Ubicación | Qué cubre |
|---|---|---|
| Unitarias + API (pytest) | `services/*/tests` | Reglas de negocio, JWT, roles, horarios de clase, carga CSV, revocación, CRUD de espacios, consumidor de eventos, intenciones del chatbot |
| End-to-end (Playwright) | `tests/e2e` | Registro/login, filtros, reservar/cancelar, bloqueo por clase, CRUD de espacios, clases y CSV, revocación vista por el estudiante, chatbot, sin desborde en móvil |
| Carga (k6) | `tests/carga` | Tiempos de respuesta bajo 20→100 usuarios concurrentes |

```bash
cd services/reservas && python -m pytest -q        # igual para auth, notificaciones, chatbot
pip install pytest-playwright && playwright install chromium
python -m pytest tests/e2e                          # levanta todo el sistema solo, con SQLite temporal
E2E_BASE_URL=https://reservacampus-web-gcr3.onrender.com python -m pytest tests/e2e   # contra Render
k6 run -e BASE=http://localhost:8080/api tests/carga/k6-reservas.js
```

## Administración
- **Espacios:** crear, editar, deshabilitar (deja de aparecer para reservar) y eliminar.
- **Horarios de clase:** bloques semanales fijos que bloquean el espacio; se crean uno a uno o con un CSV
  (`docs/horarios_ejemplo.csv`). Si chocan con reservas existentes, el sistema lo avisa y permite revocarlas.
- **Revocar reservas:** con justificación obligatoria; el usuario la recibe en la app y por correo (Brevo).

## Correo
Render gratuito bloquea SMTP, así que el correo sale por la API HTTP de **Brevo** (300 correos/día gratis):
define `BREVO_API_KEY` y `MAIL_FROM` (remitente verificado) en el servicio de notificaciones.

## Reglas de negocio
Bloques de 30 min · duración 30 min–3 h · hasta 30 días de anticipación · máx. 3 reservas activas por usuario ·
capacidad del espacio · sin solapamientos (bloqueo `SELECT … FOR UPDATE` contra dobles reservas concurrentes).

## Seguridad (OWASP Top 10)
- A01 Control de acceso: roles, solo el dueño o admin cancela (respuesta 404 para evitar enumeración/IDOR).
- A02 Criptografía: contraseñas con PBKDF2-SHA256 + sal, JWT firmado con secreto generado por Render.
- A03 Inyección: ORM con consultas parametrizadas, validación Pydantic, escape de HTML en el frontend.
- A05 Configuración: cabeceras de seguridad, CORS restringido, secretos solo en variables de entorno.
- A07 Autenticación: bloqueo tras 5 intentos fallidos, contraseñas con letras y números.
- Chatbot: límite de mensajes por minuto, longitud máxima, prompt de sistema resistente a inyección.

## Despliegue en Render
`render.yaml` (Blueprint) crea: PostgreSQL, Key Value (Redis), 4 web services Python y el sitio estático.
La variable `GROQ_API_KEY` se ingresa en el dashboard (no está en el repositorio).
