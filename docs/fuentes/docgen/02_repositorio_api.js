const fs = require("fs");
const path = require("path");
const { p, h1, h2, h3, vinetas, pasos, imagen, tabla, nota, sep, codigo, portada, toc, generar, URLS, RAIZ, leerJSON } = require("./lib");

const endpoints = leerJSON("docs/api/endpoints.json");
const DESC = require("./descripciones");
const sql = fs.readFileSync(path.join(RAIZ, "db", "esquema_postgresql.sql"), "utf8");
const tablaReservas = sql.slice(sql.indexOf("CREATE TABLE reservas"), sql.indexOf(";", sql.indexOf("CREATE TABLE reservas")) + 1);
const BASE = { auth: URLS.auth, reservas: URLS.reservas, notificaciones: URLS.notif, chatbot: URLS.chat };

function tablaEndpoints(servicio) {
  const filas = endpoints[servicio].map((e) => [e.metodo, `\`${e.ruta}\``, DESC[`${e.metodo} ${e.ruta}`] || e.descripcion || e.resumen, e.etiqueta]);
  return tabla(["Método", "Ruta", "Descripción", "Grupo"], filas, [900, 3300, 3960, 1200]);
}

const contenido = [
  portada({ titulo: "Repositorio, API y Base de Datos", subtitulo: "Código fuente del MVP, documentación OpenAPI/Swagger y scripts de base de datos",
    entregable: "Fase 2 — Repositorio de código fuente con el MVP funcional, documentación de API y scripts de base de datos" }),
  toc(),

  h1("1. Enlaces del entregable"),
  tabla(["Recurso", "Enlace"], [
    ["Repositorio (código fuente)", `[${URLS.repo}](${URLS.repo})`],
    ["Aplicación en producción", `[${URLS.web}](${URLS.web})`],
    ["Swagger · auth-service", `[${URLS.auth}/docs](${URLS.auth}/docs)`],
    ["Swagger · reservas-service", `[${URLS.reservas}/docs](${URLS.reservas}/docs)`],
    ["Swagger · notificaciones-service", `[${URLS.notif}/docs](${URLS.notif}/docs)`],
    ["Swagger · chatbot-service", `[${URLS.chat}/docs](${URLS.chat}/docs)`],
    ["Especificaciones OpenAPI (JSON)", `[docs/api/](${URLS.repo}/tree/main/docs/api)`],
    ["Script de esquema PostgreSQL", `[db/esquema_postgresql.sql](${URLS.repo}/blob/main/db/esquema_postgresql.sql)`],
    ["Script de datos iniciales", `[db/datos_semilla.sql](${URLS.repo}/blob/main/db/datos_semilla.sql)`],
    ["Integración continua", `[${URLS.ci}](${URLS.ci})`],
  ], [3300, 6060]),
  nota("Los servicios gratuitos de Render se duermen tras 15 minutos sin uso: el primer acceso puede tardar cerca de un minuto. Abre la aplicación y los Swagger unos minutos antes de una demostración.", "alerta"),

  h1("2. Estructura del repositorio"),
  codigo(`reservacampus/
├── services/                    # Un microservicio por carpeta (FastAPI)
│   ├── auth/                    # Usuarios, JWT, estados, recuperación de contraseña
│   │   ├── app/  main.py  models.py  schemas.py  security.py  eventos.py  config.py
│   │   ├── tests/               # Pruebas unitarias y de API (pytest)
│   │   ├── requirements.txt  Dockerfile
│   ├── reservas/                # Espacios, horarios, reservas, llegada, reportes, sanciones
│   │   └── app/ main.py incidencias.py reglas.py sanciones.py tareas.py eventos.py semilla.py ...
│   ├── notificaciones/          # Consumidor de eventos, notificaciones, alertas, correo (Brevo)
│   └── chatbot/                 # Motor de reglas + IA (Groq) + actividades
├── frontend/                    # index.html, app.js, ui.js (componentes), styles.css, build.sh
├── gateway/nginx.conf           # API Gateway para Docker Compose
├── db/                          # init/, esquema_postgresql.sql, datos_semilla.sql
├── tests/
│   ├── e2e/                     # Pruebas end-to-end (Playwright)
│   ├── carga/                   # Pruebas de rendimiento (k6) y resultados
│   └── seguridad/               # Auditoría OWASP automatizada y resultados
├── docs/                        # Entregables, diagramas, capturas, OpenAPI
├── .github/workflows/           # ci.yml (pruebas) y tareas.yml (programador)
├── docker-compose.yml           # Entorno local completo
└── render.yaml                  # Infraestructura como código (Render Blueprint)`, "Árbol principal"),

  h1("3. Tecnologías"),
  tabla(["Capa", "Tecnología", "Uso"], [
    ["Backend", "Python 3.12 · FastAPI · Uvicorn", "APIs REST asíncronas con documentación OpenAPI automática"],
    ["ORM", "SQLAlchemy 2", "Persistencia con consultas parametrizadas y modelos tipados"],
    ["Validación", "Pydantic 2", "Esquemas de entrada/salida (DTO) y validación de datos"],
    ["Seguridad", "PyJWT · PBKDF2 (hashlib)", "Sesiones sin estado con JWT y contraseñas con sal"],
    ["Base de datos", "PostgreSQL 16/18 (SQLite en pruebas)", "Persistencia por servicio"],
    ["Mensajería", "Redis Streams", "Eventos asíncronos con grupos de consumidores"],
    ["Frontend", "HTML · CSS · JavaScript", "Interfaz responsiva sin frameworks; componentes propios"],
    ["IA", "Groq (modelo openai/gpt-oss-20b)", "Respuestas abiertas del asistente"],
    ["Correo", "Brevo (API HTTP)", "Notificaciones por correo"],
    ["Pruebas", "pytest · Playwright · k6 · Bandit · pip-audit", "Unitarias, E2E, rendimiento y seguridad"],
    ["Infraestructura", "Docker Compose · Render · GitHub Actions", "Local, nube y CI/CD"],
  ], [1700, 3300, 4360]),

  h1("4. Cómo ejecutar el MVP"),
  h2("4.1 Opción A — Docker Compose (sistema completo)"),
  ...pasos([
    "Clonar el repositorio: `git clone " + URLS.repo + "`",
    "Copiar `.env.example` como `.env` y escribir la `GROQ_API_KEY` (y opcionalmente `BREVO_API_KEY` y `MAIL_FROM`).",
    "Ejecutar `docker compose up --build`.",
    "Abrir `http://localhost:8080`. Swagger: `http://localhost:8080/api/reservas/docs` (igual para auth, notificaciones y chat).",
    "Ingresar como administrador: `admin@reservacampus.edu` / `Admin12345`.",
  ]),
  h2("4.2 Opción B — Sin Docker (desarrollo rápido)"),
  codigo(`python -m venv .venv
.venv\\Scripts\\pip install -r services/auth/requirements.txt -r services/reservas/requirements.txt ^
                          -r services/notificaciones/requirements.txt -r services/chatbot/requirements.txt
sh scripts/dev_local.sh          # servicios en los puertos 8001-8004 con SQLite`, "Terminal"),
  h2("4.3 Opción C — Render (producción)"),
  p("El archivo `render.yaml` crea toda la infraestructura: base de datos, Redis, 4 servicios web, el sitio estático y un grupo de variables compartidas (el secreto JWT se genera automáticamente). Las claves externas (`GROQ_API_KEY`, `BREVO_API_KEY`, `MAIL_FROM`, `TAREAS_TOKEN`) se cargan en el panel de Render y nunca se guardan en el repositorio."),

  h1("5. Patrones de diseño aplicados"),
  tabla(["Patrón", "Dónde", "Para qué"], [
    ["Microservicios / Database per service", "Arquitectura general", "Aislar fallas y responsabilidades"],
    ["Publicador–Suscriptor (event-driven)", "`eventos.py` → `consumidor.py`", "Desacoplar reservas de notificaciones"],
    ["Consumidor idempotente", "`procesar_evento` con `evento_id` único", "Entrega al menos una vez sin duplicados"],
    ["Inyección de dependencias", "`Depends(get_db)`, `Depends(usuario_actual)`", "Sesiones y seguridad desacopladas de los endpoints"],
    ["DTO (Data Transfer Object)", "`schemas.py` (Pydantic)", "Contratos de entrada y salida validados"],
    ["Data Mapper / ORM", "`models.py` (SQLAlchemy)", "Separar dominio y SQL"],
    ["Reglas puras (Domain logic)", "`reglas.py`, `sanciones.py`", "Lógica de negocio probable sin base de datos"],
    ["Cadena de responsabilidad", "Chatbot: reglas → IA → respaldo", "Responder con la fuente más confiable disponible"],
    ["Middleware", "Cabeceras de seguridad y CORS", "Comportamiento transversal en todas las respuestas"],
    ["Plantillas (Template)", "`PLANTILLAS` de notificaciones", "Mensajes uniformes por tipo de evento"],
    ["Reloj inyectable", "`reloj.py`", "Probar reglas dependientes del tiempo"],
  ], [2800, 3300, 3260]),

  h1("6. Seguridad de sesiones (JWT)"),
  p("Al iniciar sesión, auth-service devuelve un **JWT firmado (HS256)** válido por 120 minutos. El frontend lo envía en cada petición con el encabezado `Authorization: Bearer <token>`. Los demás servicios validan la firma con el secreto compartido sin consultar a auth (sesiones sin estado)."),
  codigo(`# auth-service · app/security.py
payload = {"sub": str(usuario.id), "email": usuario.email, "nombre": usuario.nombre,
           "rol": usuario.rol, "iat": ahora, "exp": ahora + timedelta(minutes=JWT_EXP_MIN)}
return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

# reservas-service · app/deps.py
d = jwt.decode(cred.credentials, config.JWT_SECRET, algorithms=["HS256"])   # rechaza "none" y firmas falsas`, "Emisión y validación del token"),
  ...vinetas([
    "Contraseñas: PBKDF2-SHA256 con 120 000 iteraciones y sal aleatoria; comparación en tiempo constante.",
    "Recuperación: token aleatorio de un solo uso; en la base solo se guarda su hash SHA-256; vence en 30 minutos.",
    "Estado de la cuenta: un usuario bloqueado no puede iniciar sesión; uno suspendido no puede reservar.",
  ]),

  h1("7. Documentación de la API (OpenAPI / Swagger)"),
  p("Cada servicio publica su especificación **OpenAPI 3** en `/openapi.json` y una interfaz interactiva **Swagger UI** en `/docs`, donde se puede probar cada endpoint. Las especificaciones exportadas también están en `docs/api/` del repositorio."),
  imagen("capturas/t01_swagger_reservas.png", "Figura 1. Swagger UI de reservas-service", 600),
  h3("Cómo probar un endpoint protegido en Swagger"),
  ...pasos([
    "Abrir `/docs` del servicio de auth y ejecutar `POST /login` con el correo y la contraseña.",
    "Copiar el valor `access_token` de la respuesta.",
    "Abrir `/docs` del servicio que se quiere probar y pulsar **Authorize** (candado).",
    "Pegar el token y confirmar. Desde ese momento las peticiones llevan el encabezado `Authorization`.",
  ]),
  h2("7.1 auth-service"),
  p(`Base: [${BASE.auth}](${BASE.auth}) · ${endpoints.auth.length} endpoints`),
  tablaEndpoints("auth"),
  h2("7.2 reservas-service"),
  p(`Base: [${BASE.reservas}](${BASE.reservas}) · ${endpoints.reservas.length} endpoints`),
  tablaEndpoints("reservas"),
  h2("7.3 notificaciones-service"),
  p(`Base: [${BASE.notificaciones}](${BASE.notificaciones}) · ${endpoints.notificaciones.length} endpoints`),
  tablaEndpoints("notificaciones"),
  h2("7.4 chatbot-service"),
  p(`Base: [${BASE.chatbot}](${BASE.chatbot}) · ${endpoints.chatbot.length} endpoints`),
  tablaEndpoints("chatbot"),
  h2("7.5 Ejemplos de uso"),
  codigo(`# 1) Iniciar sesión
curl -X POST ${URLS.auth}/login -H "Content-Type: application/json" \\
     -d '{"email":"admin@reservacampus.edu","password":"Admin12345"}'

# 2) Disponibilidad de canchas mañana entre 16:00 y 17:00
curl "${URLS.reservas}/disponibilidad?fecha=2026-11-19&hora_inicio=16:00&hora_fin=17:00&tipo=cancha"

# 3) Crear una reserva
curl -X POST ${URLS.reservas}/reservas -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \\
     -d '{"espacio_id":1,"fecha":"2026-11-20","hora_inicio":"10:00","hora_fin":"11:00","asistentes":4}'

# 4) Preguntar al asistente
curl -X POST ${URLS.chat}/chat -H "Content-Type: application/json" -d '{"mensaje":"¿hay cancha mañana a las 4pm?"}'`, "Peticiones de ejemplo"),
  h2("7.6 Códigos de respuesta"),
  tabla(["Código", "Significado en ReservaCampus"], [
    ["200 / 201 / 204", "Operación exitosa / recurso creado / eliminado"],
    ["401", "Falta el token o es inválido / expirado"],
    ["403", "Sin permiso (rol), cuenta suspendida/bloqueada o sanción vigente"],
    ["404", "No existe o no pertenece al usuario (evita revelar recursos ajenos)"],
    ["409", "Conflicto de negocio: horario ocupado, clase, máximo de reservas, ya reportado…"],
    ["422", "Datos inválidos (validación Pydantic o regla de negocio)"],
    ["429", "Demasiados intentos (login o chat)"],
  ], [2000, 7360]),

  h1("8. Base de datos y scripts"),
  tabla(["Script", "Contenido"], [
    ["`db/init/01-crear-bases.sql`", "Crea `auth_db`, `reservas_db` y `notificaciones_db` en Docker Compose"],
    ["`db/esquema_postgresql.sql`", "DDL completo de las 7 tablas e índices, generado desde los modelos SQLAlchemy"],
    ["`db/datos_semilla.sql`", "7 espacios con sus actividades y 14 bloques de clase de ejemplo"],
    ["`docs/horarios_ejemplo.csv`", "Archivo de ejemplo para la carga masiva de horarios desde el panel"],
    ["`docs/fuentes/exportar_api_y_bd.py`", "Regenera los scripts y las especificaciones OpenAPI desde el código"],
  ], [3600, 5760]),
  imagen("diagramas/10_modelo_datos.png", "Figura 2. Modelo entidad-relación", 560),
  codigo(tablaReservas, "Extracto de db/esquema_postgresql.sql — tabla reservas"),
  h3("Migraciones"),
  p("Al iniciar, cada servicio ejecuta `Base.metadata.create_all()` y una migración ligera que agrega columnas nuevas a tablas existentes (`ALTER TABLE … ADD COLUMN`), de forma idempotente. Así las versiones nuevas se despliegan sin perder datos."),

  h1("9. Integración con servicios externos"),
  tabla(["Servicio", "Integración", "Configuración"], [
    ["Groq (IA)", "chatbot-service → `POST /openai/v1/chat/completions`", "`GROQ_API_KEY`, `GROQ_MODEL`"],
    ["Brevo (correo)", "notificaciones-service → `POST /v3/smtp/email`", "`BREVO_API_KEY`, `MAIL_FROM`"],
    ["Render", "Despliegue por Blueprint y health checks", "`render.yaml`"],
    ["GitHub Actions", "CI y programador de tareas cada 10 min", "Secreto `TAREAS_TOKEN`"],
  ], [1800, 4400, 3160]),

  h1("10. Calidad del código"),
  tabla(["Indicador", "Valor"], [
    ["Pruebas unitarias y de API", "auth 14 · reservas 41 · notificaciones 10 · chatbot 50"],
    ["Pruebas end-to-end", "21 (Playwright, sistema completo)"],
    ["Cobertura de líneas", "reservas 87,9 % · auth 85,4 % · chatbot 83,3 % · notificaciones 75,3 %"],
    ["Análisis estático (Bandit)", "0 hallazgos tras la mitigación"],
    ["Dependencias vulnerables (pip-audit)", "0 en 104 paquetes"],
    ["CI", "Cada push ejecuta todo contra PostgreSQL 16 real"],
  ], [3800, 5560]),
  p("El detalle está en el **Informe de Pruebas**."),
];

generar("02_Repositorio_API_Base_de_Datos.docx", "Repositorio, API y Base de Datos", contenido);
