const { p, h1, h2, h3, vinetas, pasos, imagen, tabla, nota, codigo, portada, toc, generar, URLS } = require("./lib");

const contenido = [
  portada({ titulo: "Módulo de Asistente Virtual", subtitulo: "Chatbot híbrido (reglas + IA) integrado en la interfaz y conectado al backend",
    entregable: "Fase 3 — Módulo de chat integrado en la interfaz de usuario con su lógica de negocio conectada al backend" }),
  toc(),

  h1("1. Resumen"),
  p("El asistente de ReservaCampus es un **microservicio independiente** (`chatbot-service`) y un **widget de chat** presente en todas las pantallas. Combina dos mecanismos:"),
  ...vinetas([
    "**Motor de reglas determinista:** reconoce intenciones (disponibilidad, mis reservas, reglas, horarios, cancelar, llegada, reportes, sanciones…) y responde con **datos reales** consultando al servicio de reservas. Es exacto, rápido y no consume cuota de IA.",
    "**IA generativa (Groq, modelo `openai/gpt-oss-20b`):** responde preguntas abiertas cuando ninguna regla aplica, con un prompt de sistema que limita el tema a la plataforma e incluye la lista real de espacios.",
    "**Respaldo:** si la IA o el servicio de reservas no responden, ofrece sugerencias en lugar de fallar.",
  ]),
  p("Cada respuesta indica su origen en la interfaz: **⚙️ respuesta por reglas**, **✨ respuesta con IA** o **ℹ️ respuesta de respaldo**."),
  imagen("capturas/e13_chat_disponibilidad.png", "Figura 1. Respuesta por reglas: disponibilidad real de la cancha", 340),

  h1("2. Arquitectura del módulo"),
  imagen("diagramas/06_secuencia_chatbot.png", "Figura 2. Flujo de una consulta", 620),
  tabla(["Archivo", "Responsabilidad"], [
    ["`services/chatbot/app/main.py`", "Endpoint `POST /chat`, límite de mensajes, enrutamiento reglas → IA → respaldo, respuestas de disponibilidad"],
    ["`services/chatbot/app/reglas.py`", "Normalización de texto, intenciones por palabras clave, extracción de fecha, hora, personas y franjas libres"],
    ["`services/chatbot/app/actividades.py`", "Relaciona actividades del usuario con los **espacios existentes** (tipo, nombre, descripción y actividades definidas por el admin)"],
    ["`services/chatbot/app/ia.py`", "Cliente de Groq con prompt de sistema y contexto de espacios"],
    ["`frontend/index.html` + `app.js`", "Widget: botón flotante, historial, sugerencias, envío con token si hay sesión"],
  ], [3300, 6060]),

  h1("3. Lógica de negocio"),
  h2("3.1 Intenciones reconocidas"),
  tabla(["Intención", "Ejemplos de preguntas", "Qué hace"], [
    ["disponibilidad", "¿qué está libre mañana a las 10? · necesito un laboratorio para 25 personas", "Consulta `/disponibilidad` y responde sí/no con franjas libres"],
    ["mis_reservas", "mis reservas · ¿tengo alguna reserva?", "Consulta `/reservas/mias` con el token del usuario"],
    ["como_reservar", "¿cómo reservo?", "Explica los pasos"],
    ["cancelar", "quiero cancelar mi reserva", "Explica cómo cancelar"],
    ["reglas", "¿cuál es la duración máxima?", "Bloques de 30 min, 3 h máx., 30 días, 3 activas, capacidad, clases"],
    ["horarios / tipos", "¿a qué hora abre el laboratorio? · ¿qué espacios hay?", "Lista horarios o espacios reales con sus actividades"],
    ["llegada", "¿cómo confirmo llegada?", "Explica la ventana −10/+20 min y la sanción"],
    ["reporte", "la sala sigue ocupada y no han salido", "Explica la tolerancia de 10 min y el botón de reporte"],
    ["sanciones", "¿por qué estoy sancionado?", "Explica la escala 1 día · 3 días · 1 semana · suspensión"],
    ["contacto / ayuda / saludo", "hola · ¿qué puedes hacer?", "Orientación y sugerencias"],
  ], [1700, 3900, 3760]),
  h2("3.2 Actividades y espacios dinámicos"),
  p("El asistente **no tiene respuestas fijas por actividad**: busca en los espacios que existen en ese momento. Si el administrador crea una \"Sala Gamer\" con la actividad *videojuegos*, el asistente la ofrecerá sin cambiar código."),
  ...pasos([
    "Detecta si el mensaje **pide un espacio** (\"¿hay…?\", \"necesito…\", \"busco…\", \"para jugar…\"). \"Dame consejos para estudiar\" no pide espacio y va a la IA.",
    "Identifica la actividad con un catálogo de sinónimos (fútbol → deportes, consola → videojuegos, ajedrez → juegos de mesa…) o con las **etiquetas que el admin escribió** en cada espacio (p. ej. *yoga*).",
    "Filtra los espacios que sirven: por tipo, nombre, descripción o actividades permitidas.",
    "Si hay espacios: responde ✅ con franjas libres (desde la hora actual si es hoy). Si no: \"Por ahora no hay espacios para X\" y muestra lo que sí existe.",
  ]),
  imagen("capturas/e14_chat_sin_espacio.png", "Figura 3. Actividad sin espacio: lo dice y muestra lo que sí existe", 340),
  codigo(`def sirve_para(espacio, actividad, tag):
    if tag and normalizar(tag) in etiquetas(espacio):      # actividad escrita por el admin
        return True
    if actividad:
        if espacio["tipo"] in actividad.tipos:              # p. ej. deportes -> cancha
            return True
        texto = texto_espacio(espacio)                      # nombre + descripción + actividades
        return any(t in texto for t in actividad.terminos)
    return False`, "services/chatbot/app/actividades.py"),
  h2("3.3 Respuesta con IA"),
  p("Cuando ninguna regla aplica, se envían a Groq: un **prompt de sistema** (rol, reglas de la plataforma, prohibición de inventar espacios o disponibilidad y de revelar instrucciones), la **lista real de espacios** con sus actividades y los últimos 6 mensajes del historial."),
  imagen("capturas/e15_chat_ia.png", "Figura 4. Respuesta con IA a una pregunta abierta", 340),

  h1("4. Integración en la interfaz"),
  ...vinetas([
    "Botón flotante en la esquina inferior derecha, disponible en todas las pantallas y en móvil.",
    "Si el usuario inició sesión, el widget envía su token: así puede responder **\"mis reservas\"**.",
    "Muestra sugerencias clicables después de cada respuesta.",
    "El texto se inserta de forma segura (sin `innerHTML`), solo se interpreta **negrita**.",
  ]),
  h2("4.1 Contrato de la API"),
  codigo(`POST ${URLS.chat}/chat
Authorization: Bearer <token>        (opcional)
{ "mensaje": "¿hay cancha mañana a las 4pm?",
  "historial": [{"rol": "user", "texto": "..."}, {"rol": "assistant", "texto": "..."}] }

200 OK
{ "respuesta": "❌ No hay espacios para deportes libres mañana de 16:00 a 17:00. ...",
  "fuente": "reglas",            // reglas | ia | respaldo
  "intencion": "disponibilidad",
  "sugerencias": ["¿Qué está libre mañana?"] }`, "Petición y respuesta"),

  h1("5. Seguridad del asistente"),
  tabla(["Riesgo", "Control"], [
    ["Inyección de prompt", "Prompt de sistema que ignora instrucciones del usuario; verificado en la auditoría (no revela sus instrucciones)"],
    ["Abuso / costo de IA", "Máximo 15 mensajes por minuto por IP (429) y 500 caracteres por mensaje (422)"],
    ["Datos personales", "La IA solo recibe la lista de espacios; las reservas del usuario se consultan por reglas con su propio token"],
    ["Alucinaciones", "Disponibilidad y reservas siempre por reglas con datos reales; la IA tiene prohibido inventarlas"],
    ["XSS en el widget", "Inserción de texto con `textContent`"],
  ], [2600, 6760]),

  h1("6. Pruebas del módulo"),
  p("El chatbot tiene **50 pruebas automatizadas** (cobertura 83,3 %) y 2 pruebas end-to-end. Entre ellas:"),
  ...vinetas([
    "Detección de cada intención y extracción de fecha, hora y número de personas.",
    "Cálculo de franjas libres (incluye redondeo al siguiente bloque de 30 min).",
    "Fútbol → cancha; videojuegos sin sala → \"por ahora no hay\"; al crear una Sala Gamer → la ofrece.",
    "Actividades no catalogadas (yoga, danza) reconocidas por las etiquetas del admin.",
    "\"Dame consejos…\" no se confunde con una búsqueda de espacio.",
    "E2E: el admin crea una sala recreativa desde el panel y el asistente pasa a recomendarla.",
  ]),

  h1("7. Cómo extender el asistente"),
  tabla(["Quiero…", "Cómo"], [
    ["Que recomiende un espacio para una actividad nueva", "Sin programar: en Administración → Espacios, escribir la actividad en **Actividades permitidas**"],
    ["Agregar sinónimos de una actividad", "Editar `CATALOGO` en `actividades.py`"],
    ["Una nueva intención con respuesta fija", "Agregar una `Intencion(...)` en `reglas.py` con palabras clave y respuesta"],
    ["Cambiar el modelo de IA", "Variable `GROQ_MODEL` en Render (sin tocar código)"],
  ], [3600, 5760]),
];

generar("03_Modulo_Chatbot.docx", "Módulo de Asistente Virtual", contenido);
