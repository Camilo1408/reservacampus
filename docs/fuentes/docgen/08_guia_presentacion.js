const { p, h1, h2, h3, vinetas, pasos, imagen, tabla, nota, codigo, portada, toc, generar, URLS } = require("./lib");
const R = (ruta, linea) => `[${ruta}:${linea}](${URLS.repo}/blob/main/${ruta}#L${linea})`;

const contenido = [
  portada({ titulo: "Guía de Presentación", subtitulo: "Cómo explicar el proyecto, mostrar el código, hacer las demostraciones y probar la estabilidad",
    entregable: "Fase 5 — Defensa / presentación final del proyecto" }),
  toc(),

  h1("1. Plan de la sesión"),
  p("Duración sugerida: **30 minutos** (20 de exposición y demo + 10 de preguntas). La presentación es `07_Presentacion_Final.pptx`; cada diapositiva tiene **notas del orador** con lo que hay que decir."),
  tabla(["Min.", "Bloque", "Diapositivas", "Objetivo"], [
    ["0–2", "Problema", "1–2", "Que el jurado entienda el dolor real"],
    ["2–4", "Solución", "3", "Las 6 capacidades en una mirada"],
    ["4–10", "Arquitectura y diseño", "4–9", "Microservicios, eventos, datos, reglas, chatbot, admin"],
    ["10–18", "Demostración en vivo", "10", "Ver el sistema funcionando por rol (guion en la sección 4)"],
    ["18–22", "Calidad", "11–14", "Pruebas, rendimiento (antes/después), seguridad, usabilidad"],
    ["22–24", "Cierre", "15–17", "Despliegue, lecciones, enlaces"],
    ["24–30", "Preguntas", "—", "Respuestas preparadas en la sección 7"],
  ], [900, 2200, 1500, 4760]),
  h3("Reparto sugerido si el equipo es de varias personas"),
  tabla(["Persona", "Partes"], [
    ["A", "Problema, solución, arquitectura (diapositivas 1–6)"],
    ["B", "Reglas de negocio, chatbot y administración (7–9) + demo del estudiante y del chat"],
    ["C", "Demo del administrador, calidad, rendimiento y seguridad (10–14)"],
    ["Todos", "Cierre y preguntas"],
  ], [1600, 7760]),

  h1("2. Preparación (el día antes y 15 minutos antes)"),
  h2("2.1 El día antes"),
  ...pasos([
    "Verificar que el CI esté en verde: [" + URLS.ci + "](" + URLS.ci + ").",
    "Crear en producción (o confirmar que existen) dos cuentas: **estudiante.demo@universidad.edu** (regístrala desde la app) y el administrador `admin@reservacampus.edu`.",
    "Tener a mano el archivo `docs/horarios_ejemplo.csv`.",
    "Descargar la presentación y los PDF por si no hay internet.",
    "Plan B sin internet: `docker compose up --build` en el portátil (sección 8).",
  ]),
  h2("2.2 Quince minutos antes"),
  ...pasos([
    "**Despertar los servicios** (Render gratuito los duerme): abrir en el navegador la app y cada `/health`: " +
      `[auth](${URLS.auth}/health), [reservas](${URLS.reservas}/health), [notificaciones](${URLS.notif}/health), [chatbot](${URLS.chat}/health).`,
    "Abrir pestañas: (1) app como estudiante, (2) **ventana privada** con la app como administrador, (3) Swagger de reservas, (4) GitHub Actions, (5) el repositorio en `services/reservas/app/main.py`.",
    "Abrir el correo de la cuenta demo para mostrar los correos que llegan.",
    "Subir el zoom del navegador a 125 % para que se lea en el proyector.",
  ]),
  nota("Si una página tarda en cargar al inicio, es el servicio despertando: decirlo con naturalidad (\"es el plan gratuito de Render\") y continuar.", "consejo"),

  h1("3. Cómo explicar cómo está construido"),
  h2("3.1 La idea en 3 frases"),
  nota(["\"ReservaCampus son **4 microservicios** en Python con FastAPI: autenticación, reservas, notificaciones y un chatbot.",
    "Se hablan por **REST** cuando necesitan una respuesta inmediata y por **eventos en Redis Streams** cuando no (por ejemplo, avisar al usuario después de reservar).",
    "Cada servicio tiene sus propias tablas en PostgreSQL, está desplegado en Render y cada cambio pasa por pruebas automáticas antes de desplegarse.\""], "demo"),
  imagen("diagramas/02_c4_contenedores.png", "Apoyo visual: diagrama de contenedores", 420),
  h2("3.2 Recorrido por el código (qué abrir y qué decir)"),
  p("Abrir cada archivo en GitHub o en el editor y mostrar solo la función indicada. Mantener cada parada en menos de 1 minuto."),
  tabla(["#", "Qué mostrar", "Dónde", "Qué decir"], [
    ["1", "Crear reserva", R("services/reservas/app/main.py", 399), "Valida sanción y estado de la cuenta (llamada REST a auth), bloquea la fila con FOR UPDATE, revisa reglas y solapamientos, guarda y publica el evento"],
    ["2", "Reglas puras", R("services/reservas/app/reglas.py", 19), "La lógica de negocio no depende de la base de datos: por eso se prueba fácil"],
    ["3", "Publicar evento", R("services/reservas/app/eventos.py", 20), "XADD al stream; si Redis falla, la reserva no se cae"],
    ["4", "Consumir evento", R("services/notificaciones/app/consumidor.py", 113), "Idempotente por evento_id; luego XACK; manda el correo por Brevo"],
    ["5", "Sanciones", R("services/reservas/app/sanciones.py", 56), "Nivel según reincidencia: 1 día, 3 días, 1 semana, indefinida"],
    ["6", "Programador", R("services/reservas/app/tareas.py", 36), "Recorre la línea de tiempo: −10, 0, +10, +20 minutos; idempotente"],
    ["7", "Reportar ocupado", R("services/reservas/app/incidencias.py", 114), "Tolerancia de 10 min, busca la reserva anterior pegada y la sanciona"],
    ["8", "Chatbot", R("services/chatbot/app/main.py", 193), "Reglas → IA → respaldo (cadena de responsabilidad)"],
    ["9", "Actividades dinámicas", R("services/chatbot/app/actividades.py", 89), "Busca en los espacios reales: por eso reconoce salas nuevas"],
    ["10", "Seguridad", R("services/auth/app/security.py", 20), "PBKDF2 con sal; JWT con expiración"],
    ["11", "Frontend", R("frontend/ui.js", 15), "Componentes propios (dropdown, diálogos) sin frameworks"],
    ["12", "Infraestructura", `[render.yaml](${URLS.repo}/blob/main/render.yaml)`, "Toda la nube definida como código"],
  ], [500, 1500, 3200, 4160]),
  h3("Fragmento recomendado para proyectar"),
  codigo(`@app.post("/reservas", status_code=201)
def crear_reserva(datos: ReservaIn, request: Request, u = Depends(usuario_actual), db = Depends(get_db)):
    s = sanciones.sancion_activa(db, u.id, reloj.ahora())          # 1. ¿tiene sanción?
    if s: raise HTTPException(403, f"Tienes una sanción vigente ...")
    if estado_cuenta(request.headers.get("authorization")) in ("suspendido", "bloqueado"):
        raise HTTPException(403, "Tu cuenta está suspendida")      # 2. REST a auth-service
    espacio = db.scalar(select(Espacio).where(...).with_for_update())  # 3. evita dobles reservas
    validar_horario(...); validar_capacidad(...)                  # 4. reglas puras
    for f in ocupacion(db, espacio.id, datos.fecha):              # 5. clases y reservas
        if se_solapan(...): raise HTTPException(409, "...")
    db.add(reserva); db.commit()
    publicador.publicar("reserva.creada", evento_reserva(reserva))  # 6. evento asíncrono`, "Resumen de crear_reserva"),

  h1("4. Guion de las demostraciones"),
  p("Cada demo indica qué hacer, qué debe verse y qué decir. Están ordenadas para contar una historia."),
  h2("Demo 1 — Estudiante reserva (2 min)"),
  ...pasos([
    "En la pestaña del estudiante: mostrar la grilla y la **barra del día** (verde libre, naranja clase, rojo reservado).",
    "Filtrar por **Salas de estudio** con el dropdown.",
    "Pulsar **Reservar** en una sala para mañana. Mostrar que abajo aparecen las horas ocupadas.",
    "Intentar una hora que choca con una clase → mensaje claro (\"hay clase de …\"). Luego elegir una hora libre y confirmar.",
    "Mostrar la **campana** con la notificación y el **correo** que llegó.",
  ]),
  nota("Qué decir: \"La reserva se guardó al instante; el aviso lo generó otro microservicio a partir de un evento\".", "demo"),
  h2("Demo 2 — Asistente virtual (2 min)"),
  ...pasos([
    "Abrir el chat y preguntar: **¿hay cancha para fútbol mañana a las 4pm?** → responde por reglas con el motivo.",
    "Preguntar: **y para jugar videojuegos** → \"Por ahora no hay espacios para videojuegos\".",
    "Preguntar: **dame consejos para organizar un grupo de estudio** → respuesta con IA (etiqueta ✨).",
  ]),
  h2("Demo 3 — El admin crea un espacio y el chat lo reconoce (2 min)"),
  ...pasos([
    "En la ventana del administrador: **Administración → Espacios → + Nuevo espacio**.",
    "Crear \"Sala Gamer\", tipo **Sala recreativa**, actividades **videojuegos, juegos de mesa**.",
    "Volver al chat del estudiante y repetir **y para jugar videojuegos** → ahora la recomienda con sus horas libres.",
  ]),
  nota("Este es el momento \"wow\": muestra que el asistente usa datos reales y se adapta sin tocar código.", "consejo"),
  h2("Demo 4 — Horarios de clase con CSV (1 min)"),
  ...pasos(["**Horarios de clase → Descargar plantilla**, mostrarla.", "Arrastrar `horarios_ejemplo.csv` y **Cargar horarios** → \"10 bloques cargados\" y el horario semanal se actualiza."]),
  h2("Demo 5 — Gestión de usuarios y sanciones (2 min)"),
  ...pasos([
    "**Usuarios** → buscar la cuenta demo → **Gestionar** (mostrar historial, sanciones, reportes, avisos).",
    "**Suspender** con un motivo. En la pestaña del estudiante recargar: aparece el aviso naranja y al intentar reservar se rechaza.",
    "Volver al admin y **Reactivar**. Opcional: **Enviar alerta** con plantilla y mostrarla en la campana del estudiante.",
  ]),
  h2("Demo 6 — Confirmar llegada y reportar (opcional, 1 min)"),
  p("La confirmación solo se habilita desde 10 minutos antes del inicio. Opciones:"),
  ...vinetas([
    "**En vivo:** al iniciar la sesión, reservar el siguiente bloque de 30 min (p. ej. si son las 10:05, reservar 10:30–11:00); a las 10:20 aparecerá **Confirmar llegada**.",
    "**Con las capturas** del manual de usuario (Mis reservas con los botones y el reporte enviado).",
    "**En local con reloj simulado:** `APP_RELOJ_INICIO=2026-11-18T10:15` en el servicio de reservas (solo para demos).",
  ]),
  h2("Demo 7 — Swagger (1 min)"),
  ...pasos([`Abrir [${URLS.reservas}/docs](${URLS.reservas}/docs).`, "Mostrar los grupos (espacios, horarios, reservas, admin) y ejecutar `GET /disponibilidad` con una fecha."]),

  h1("5. Demostrar que el sistema se mantiene estable"),
  h2("5.1 Pruebas automáticas en vivo (2 min)"),
  codigo(`cd services/reservas
python -m pytest -q                 # 41 pruebas en ~4 s
python -m pytest -q -k sancion      # solo las de sanciones
cd ../..
python -m pytest tests/e2e -k chatbot_reconoce   # E2E: navegador real crea la Sala Gamer`, "Terminal"),
  p("Qué decir: \"Estas pruebas se ejecutan solas en cada cambio; si alguna falla, no se despliega\". Mostrar **GitHub Actions** con el CI en verde (pruebas contra PostgreSQL 16 y E2E)."),
  h2("5.2 Rendimiento"),
  p("No ejecutar k6 en vivo (tarda 3 minutos). Mostrar la diapositiva 12 y, si piden detalle, el **Informe de Pruebas**: el p95 de `/disponibilidad` bajó 63 % tras corregir el problema N+1."),
  h2("5.3 Seguridad"),
  p("Mostrar `tests/seguridad/resultados/owasp.json` o la tabla del informe (25/25)."),
  nota("No ejecutar la auditoría en vivo antes de la demo: la prueba de fuerza bruta bloquea la IP 5 minutos y no se podría iniciar sesión.", "alerta"),
  h2("5.4 Pruebas definidas para mantener el sistema estable"),
  tabla(["Cuándo", "Qué ejecutar", "Para qué"], [
    ["Cada push (automático)", "CI: unitarias ×4 con PostgreSQL + E2E", "Nada roto llega a producción"],
    ["Antes de una entrega", "Auditoría OWASP, Bandit, pip-audit", "Seguridad"],
    ["Tras cambios en consultas", "k6 carga y estrés", "Detectar regresiones de rendimiento"],
    ["Cada 10 minutos (automático)", "Cron del programador + `/health`", "Recordatorios e inasistencias al día"],
    ["Con cada nueva función", "Al menos una prueba unitaria y, si hay interfaz, una E2E", "Mantener la cobertura > 80 %"],
  ], [2500, 3600, 3260]),

  h1("6. Mensajes clave para el jurado"),
  ...vinetas([
    "**Distribuido de verdad:** 4 servicios independientes, comunicación síncrona y asíncrona, base por servicio.",
    "**Tolerante a fallas:** si Redis, auth o la IA fallan, el negocio sigue (degradación controlada).",
    "**Inteligente pero confiable:** el chatbot responde con datos reales; la IA solo complementa.",
    "**Calidad medida, no supuesta:** 136 pruebas, CI, k6 con antes/después, 25 controles de seguridad.",
    "**Operativo:** desplegado, con correos reales, programador y documentación completa.",
  ]),

  h1("7. Preguntas probables y respuestas"),
  tabla(["Pregunta", "Respuesta sugerida"], [
    ["¿Por qué microservicios y no un monolito?", "Para aislar fallas y escalar por separado: en la prueba de estrés el login siguió rápido aunque reservas estaba saturado. El costo es más complejidad, que mitigamos con Blueprint, Docker Compose y CI."],
    ["¿Qué pasa si se cae Redis?", "La reserva se guarda igual; el evento se registra. Cuando el consumidor vuelve, procesa los pendientes del grupo."],
    ["¿Cómo evitan dobles reservas simultáneas?", "Bloqueo pesimista `SELECT … FOR UPDATE` sobre el espacio y verificación de solapamientos en la misma transacción."],
    ["¿Cómo garantizan que no se dupliquen notificaciones?", "Consumidor idempotente: cada notificación guarda el id del evento con restricción única."],
    ["¿El chatbot puede inventar disponibilidad?", "No: la disponibilidad siempre sale de las reglas con datos reales; la IA tiene prohibido inventarla y solo responde preguntas abiertas."],
    ["¿Cómo funciona el programador si Render duerme los servicios?", "Hilo interno cada minuto mientras está despierto y un cron de GitHub Actions cada 10 min que lo despierta; las inasistencias se procesan al despertar."],
    ["¿Por qué Brevo y no SMTP?", "Render gratuito bloquea los puertos SMTP; Brevo es una API HTTP."],
    ["¿Cómo manejan las sesiones?", "JWT HS256 de 2 horas; cada servicio valida la firma sin consultar a auth. El estado de la cuenta se consulta al reservar para aplicar suspensiones al instante."],
    ["¿Qué encontraron en las pruebas de rendimiento?", "Un problema N+1 en disponibilidad; lo corregimos y el p95 bajó 63 %. El límite que queda es la CPU del plan gratuito."],
    ["¿Qué falta?", "Prueba SUS con usuarios, JWT asimétrico, caché, límite por usuario y respaldos (plan de mitigación)."],
  ], [3300, 6060]),

  h1("8. Plan B"),
  tabla(["Si…", "Entonces"], [
    ["Render está lento o caído", "Usar Docker local: `docker compose up --build` → `http://localhost:8080` (mismas funciones)"],
    ["No hay internet", "Docker local (el chat responde por reglas; la IA y el correo no estarán)"],
    ["Una demo falla en vivo", "Pasar a las capturas del Manual de Usuario y explicar qué debía ocurrir; seguir con la siguiente"],
    ["Se bloqueó el login (429)", "Esperar 5 minutos o usar la otra cuenta/ventana"],
    ["Groq no responde", "El chatbot muestra respuesta de respaldo: explicarlo como degradación controlada"],
  ], [3000, 6360]),

  h1("9. Lista de verificación final"),
  ...vinetas([
    "☐ CI en verde y servicios despiertos (`/health`)",
    "☐ Cuentas de estudiante y administrador probadas",
    "☐ Pestañas abiertas: app ×2, Swagger, GitHub Actions, código",
    "☐ `horarios_ejemplo.csv` a mano",
    "☐ Presentación y PDF descargados",
    "☐ Docker local probado como plan B",
    "☐ Cada integrante sabe sus diapositivas y su demo",
  ]),
];

generar("08_Guia_de_Presentacion.docx", "Guía de Presentación", contenido);
