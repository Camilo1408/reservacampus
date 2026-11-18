const { p, h1, h2, h3, vinetas, pasos, imagen, tabla, nota, codigo, portada, toc, generar, URLS } = require("./lib");

const contenido = [
  portada({ titulo: "Manual Técnico", subtitulo: "Instalación, configuración, despliegue, operación y mantenimiento",
    entregable: "Fase 5 — Software desplegado y operativo · Manual técnico" }),
  toc(),

  h1("1. Visión general"),
  p("ReservaCampus está compuesto por 4 microservicios Python (FastAPI), un frontend estático, PostgreSQL y Redis. Este manual explica cómo instalarlo, configurarlo, desplegarlo y mantenerlo. La arquitectura completa está en el documento **Especificación de Arquitectura**."),
  imagen("diagramas/02_c4_contenedores.png", "Figura 1. Contenedores del sistema", 460),
  tabla(["Componente", "Puerto local", "Producción"], [
    ["Frontend + gateway (Docker)", "8080", URLS.web],
    ["auth-service", "8001 (sin Docker)", URLS.auth],
    ["reservas-service", "8002 (sin Docker)", URLS.reservas],
    ["notificaciones-service", "8003 (sin Docker)", URLS.notif],
    ["chatbot-service", "8004 (sin Docker)", URLS.chat],
  ], [3000, 2000, 4360]),

  h1("2. Requisitos"),
  tabla(["Para", "Necesitas"], [
    ["Ejecutar con Docker", "Docker Desktop 4+ (Docker Compose v2)"],
    ["Ejecutar sin Docker / desarrollar", "Python 3.12+ y Git"],
    ["Pruebas E2E", "`pip install -r tests/requirements-dev.txt` y `playwright install chromium`"],
    ["Pruebas de carga", "k6 (https://k6.io)"],
    ["Desplegar", "Cuenta de GitHub y de Render (plan gratuito)"],
    ["IA y correo (opcional)", "API key de Groq y de Brevo (con remitente verificado)"],
  ], [3000, 6360]),

  h1("3. Instalación local"),
  h2("3.1 Con Docker Compose (recomendado)"),
  ...pasos([
    "`git clone " + URLS.repo + "` y entrar a la carpeta.",
    "Copiar `.env.example` como `.env` y completar las claves (ver sección 4).",
    "`docker compose up --build` — levanta PostgreSQL, Redis, los 4 servicios y Nginx.",
    "Abrir `http://localhost:8080` e ingresar con `admin@reservacampus.edu` / `Admin12345`.",
  ]),
  p("Nginx actúa como **API Gateway**: sirve el frontend y enruta `/api/auth`, `/api/reservas`, `/api/notificaciones` y `/api/chat` a cada servicio. Cada servicio usa su propia base (`auth_db`, `reservas_db`, `notificaciones_db`), creadas por `db/init/01-crear-bases.sql`."),
  h2("3.2 Sin Docker (desarrollo)"),
  codigo(`python -m venv .venv
.venv\\Scripts\\activate              # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r services/auth/requirements.txt -r services/reservas/requirements.txt \\
            -r services/notificaciones/requirements.txt -r services/chatbot/requirements.txt
sh scripts/dev_local.sh             # 4 servicios con SQLite en los puertos 8001-8004`, "Terminal"),
  nota("Sin Docker no hay Redis: las reservas funcionan pero las notificaciones por eventos no se generan (el sistema lo tolera y lo registra en el log).", "nota"),

  h1("4. Configuración (variables de entorno)"),
  tabla(["Variable", "Servicios", "Descripción"], [
    ["`DATABASE_URL`", "auth, reservas, notificaciones", "Conexión PostgreSQL (acepta `postgres://`; por defecto SQLite local)"],
    ["`REDIS_URL`", "auth, reservas, notificaciones", "Redis para el stream de eventos (vacío = sin eventos)"],
    ["`JWT_SECRET`", "todos con JWT", "Secreto de firma de tokens (Render lo genera)"],
    ["`CORS_ORIGINS`", "todos", "Orígenes permitidos (URL del frontend)"],
    ["`APP_TZ`", "reservas, chatbot", "Zona horaria (America/Bogota)"],
    ["`AUTH_URL`, `NOTIF_URL`, `FRONTEND_URL`", "reservas, auth", "URLs para llamadas entre servicios y enlaces en correos"],
    ["`ADMIN_EMAIL`, `ADMIN_PASSWORD`", "auth", "Administrador inicial (se crea al arrancar si no existe)"],
    ["`RESERVAS_URL`", "chatbot", "URL del servicio de reservas"],
    ["`GROQ_API_KEY`, `GROQ_MODEL`", "chatbot", "IA (sin clave el chatbot funciona solo con reglas)"],
    ["`BREVO_API_KEY`, `MAIL_FROM`", "notificaciones", "Correo por API HTTP (remitente verificado en Brevo)"],
    ["`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`", "notificaciones", "Alternativa SMTP (no funciona en Render gratuito)"],
    ["`TAREAS_TOKEN`", "reservas", "Protege `POST /tareas/ejecutar`; también es secreto de GitHub Actions"],
    ["`TAREAS_INTERVALO_SEG`", "reservas", "Frecuencia del programador interno (60 s; 0 lo desactiva)"],
    ["`CHAT_RATE_LIMIT`", "chatbot", "Mensajes por minuto por IP (15)"],
    ["`APP_RELOJ_INICIO`", "reservas", "Solo demos/pruebas: hora simulada. **Nunca en producción**"],
  ], [3400, 2400, 3560]),
  nota("Las claves reales solo van en `.env` (excluido de git) o en el panel de Render. Nunca en el repositorio.", "alerta"),

  h1("5. Despliegue en Render"),
  h2("5.1 Primera vez (Blueprint)"),
  ...pasos([
    "Subir el repositorio a GitHub.",
    "En Render: **New → Blueprint** y seleccionar el repositorio. Render lee `render.yaml`.",
    "Completar las variables manuales: `GROQ_API_KEY`, `BREVO_API_KEY`, `MAIL_FROM`, `TAREAS_TOKEN`.",
    "Aprobar el plan. Se crean la base de datos, Redis, 4 servicios web y el sitio estático.",
    "Si Render agrega un sufijo a los nombres (p. ej. `-gcr3`), actualizar las URLs en `render.yaml` (CORS, frontend, chatbot) y volver a sincronizar.",
    "En GitHub → Settings → Secrets, crear `TAREAS_TOKEN` con el mismo valor (lo usa el cron).",
  ]),
  h2("5.2 Actualizar"),
  p("Hacer push a `main`: el CI ejecuta las pruebas. Luego desplegar desde Render (**Manual Deploy → Deploy latest commit**) en los servicios modificados. El frontend se reconstruye con `build.sh`, que genera `config.js` con las URLs de los servicios."),
  h2("5.3 Programador de tareas"),
  p("El servicio de reservas revisa cada minuto los recordatorios, avisos e inasistencias. Como Render gratuito duerme los servicios, el workflow `.github/workflows/tareas.yml` llama a `POST /tareas/ejecutar` cada 10 minutos entre 6:00 y 22:00 (hora de Colombia), lo que además mantiene el servicio despierto (~480 de las 750 horas gratuitas al mes)."),

  h1("6. Operación y monitoreo"),
  tabla(["Qué revisar", "Cómo"], [
    ["Salud de cada servicio", "`GET /health` (reservas indica cola de eventos y último resultado del programador; notificaciones indica si el correo está configurado)"],
    ["Logs", "Render → servicio → Logs (o `docker compose logs -f <servicio>`)"],
    ["Correos enviados", "Panel de Brevo → Transactional → Logs; en la app, la notificación muestra \"📧 enviado por correo\""],
    ["Ejecución del cron", "GitHub → Actions → \"Programador de tareas\""],
    ["Calidad del código", "GitHub → Actions → \"CI\" (pruebas unitarias con PostgreSQL y E2E)"],
  ], [2600, 6760]),

  h1("7. Solución de problemas"),
  tabla(["Síntoma", "Causa probable", "Solución"], [
    ["El navegador muestra \"bloqueado por CORS\"", "Casi siempre es un **error 500** del servidor (las respuestas 500 no llevan cabeceras CORS)", "Revisar los logs del servicio en Render"],
    ["La primera carga tarda ~1 minuto", "Render gratuito durmió el servicio", "Esperar; abrir la app unos minutos antes de una demo"],
    ["Los correos no llegan", "Brevo bloquea IPs no autorizadas o el remitente no está verificado", "Brevo → Security → Authorised IPs (desactivar) y verificar el remitente"],
    ["\"Demasiados intentos fallidos\" (429)", "Bloqueo de 5 min tras 5 logins fallidos desde la misma IP", "Esperar 5 minutos"],
    ["No se pueden crear reservas", "Usuario con sanción vigente o cuenta suspendida", "Revisar Administración → Usuarios / Incidencias"],
    ["Funciona en local pero falla en producción", "Diferencias SQLite vs PostgreSQL", "El CI prueba con PostgreSQL: revisar su resultado"],
    ["Docker Desktop no arranca (dockerInference)", "Archivo de socket viejo", "Cerrar Docker, `wsl --shutdown`, renombrar `%LOCALAPPDATA%\\Docker\\run` y abrir de nuevo"],
    ["La base de datos de Render dejó de funcionar", "La base gratuita expira a los 30 días", "Pasar a plan pago o crear una nueva y volver a sincronizar el Blueprint"],
  ], [2700, 3300, 3360]),

  h1("8. Mantenimiento y extensión"),
  tabla(["Tarea", "Pasos"], [
    ["Agregar un tipo de espacio", "1) `TipoEspacio` en `services/reservas/app/schemas.py` · 2) `TIPOS` en `frontend/app.js` y las opciones de los selects en `index.html` · 3) `TIPOS` del chatbot"],
    ["Agregar una regla de negocio", "Función en `reglas.py` + prueba en `tests/test_reservas.py`"],
    ["Agregar una intención al chatbot", "`Intencion(...)` en `services/chatbot/app/reglas.py` + prueba"],
    ["Nuevo tipo de notificación", "Publicar el evento en el servicio y agregar la plantilla en `PLANTILLAS` de `consumidor.py`"],
    ["Agregar una columna", "Modelo SQLAlchemy + entrada en `COLUMNAS_NUEVAS` (migración ligera)"],
    ["Regenerar documentación", "`python docs/fuentes/exportar_api_y_bd.py` · `diagramas.py` · `capturas.py` · `graficos.py` y `node docs/fuentes/docgen/<doc>.js`"],
    ["Rotar claves", "Cambiar en Render (y en GitHub para `TAREAS_TOKEN`); cambiar `JWT_SECRET` cierra todas las sesiones"],
  ], [2800, 6560]),

  h1("9. Pruebas"),
  codigo(`cd services/<servicio> && python -m pytest -q        # unitarias de un servicio
python -m pytest tests/e2e                             # end-to-end (levanta todo solo)
k6 run -e ESCENARIO=carga tests/carga/k6-escenarios.js # rendimiento
python tests/seguridad/auditoria_owasp.py              # seguridad`, "Comandos"),
  p("El detalle de estrategia, métricas y resultados está en el **Informe de Pruebas**."),

  h1("10. Seguridad operativa"),
  ...vinetas([
    "Cambiar la contraseña del administrador inicial después del primer ingreso.",
    "Mantener la restricción de CORS al dominio del frontend.",
    "Revisar mensualmente `pip-audit` y actualizar dependencias.",
    "No definir `APP_RELOJ_INICIO` en producción.",
    "Proteger o desactivar `/docs` en producción si la API no debe ser pública (ver plan de mitigación M-09).",
  ]),
];

generar("05_Manual_Tecnico.docx", "Manual Técnico", contenido);
