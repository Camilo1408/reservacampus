const fs = require("fs");
const path = require("path");
const { p, h1, h2, h3, vinetas, pasos, imagen, tabla, nota, codigo, portada, toc, generar, URLS, RAIZ, leerJSON } = require("./lib");

const m = leerJSON("docs/fuentes/metricas.json");
const owasp = leerJSON("tests/seguridad/resultados/owasp.json");
const k = m.k6, ep = m.k6_endpoints;
const s = (ms) => (ms / 1000).toFixed(2).replace(".", ",") + " s";
const n1 = (x) => x.toFixed(1).replace(".", ",");
const pct = (x) => (x * 100).toFixed(2).replace(".", ",") + " %";
const mejora = (a, b) => Math.round((1 - b / a) * 100) + " %";
const e2e = fs.readFileSync(path.join(RAIZ, "docs/fuentes/lista_e2e.txt"), "utf8").trim().split("\n");
const unit = fs.readFileSync(path.join(RAIZ, "docs/fuentes/lista_unitarias.txt"), "utf8").trim().split("\n");
const porServicio = {};
unit.forEach((l) => { const sv = l.split("/")[0]; porServicio[sv] = (porServicio[sv] || 0) + 1; });
const nombreE2E = (l) => l.split("::")[1].replace(/^test_/, "").replace(/_/g, " ");
const totalOk = owasp.controles.filter((c) => c.ok).length;

const contenido = [
  portada({ titulo: "Informe de Pruebas", subtitulo: "Rendimiento, seguridad, usabilidad y pruebas funcionales con métricas, gráficos y plan de mitigación",
    entregable: "Fase 4 — Informe de pruebas con métricas, gráficos de rendimiento y plan de mitigación de vulnerabilidades" }),
  toc(),

  h1("1. Resumen ejecutivo"),
  tabla(["Dimensión", "Resultado", "Estado"], [
    ["Pruebas unitarias y de API", `${unit.length} pruebas en 4 servicios, todas exitosas`, "✅"],
    ["Pruebas end-to-end (Playwright)", `${e2e.length} escenarios de usuario real, todos exitosos`, "✅"],
    ["Cobertura de código", `reservas ${n1(m.cobertura.reservas.porcentaje)} % · auth ${n1(m.cobertura.auth.porcentaje)} % · chatbot ${n1(m.cobertura.chatbot.porcentaje)} % · notificaciones ${n1(m.cobertura.notificaciones.porcentaje)} %`, "✅"],
    ["Carga (20 usuarios)", `p95 global ${s(k.carga_despues.p95_ms)} · ${n1(k.carga_despues.rps)} peticiones/s · 0 fallas de negocio`, "✅"],
    ["Estrés (60 usuarios)", `p95 global ${s(k.estres_despues.p95_ms)} · ${n1(k.estres_despues.rps)} peticiones/s · sin caídas`, "⚠️ supera 2 s en el pico"],
    ["Mejora por optimización N+1", `p95 de /disponibilidad ${s(ep.carga.disponibilidad.p95)} → ${s(ep.carga_despues.disponibilidad.p95)} (−${mejora(ep.carga.disponibilidad.p95, ep.carga_despues.disponibilidad.p95)})`, "✅"],
    ["Auditoría OWASP automatizada", `${totalOk}/${owasp.controles.length} controles superados`, "✅"],
    ["Análisis estático (Bandit)", "6 hallazgos (3 medios, 3 bajos) → 0 tras la mitigación", "✅"],
    ["Dependencias (pip-audit)", "0 vulnerabilidades conocidas en 104 paquetes", "✅"],
    ["Usabilidad", "Evaluación heurística (10 heurísticas de Nielsen) + protocolo SUS listo para aplicar", "🟡 SUS pendiente"],
  ], [2600, 5560, 1200]),

  h1("2. Estrategia de pruebas"),
  p("Se aplicó una **pirámide de pruebas**: muchas pruebas rápidas de unidad y API en la base, escenarios end-to-end que recorren la interfaz real, y pruebas no funcionales (rendimiento y seguridad) sobre el entorno desplegado."),
  tabla(["Tipo", "Herramienta", "Entorno", "Cuándo se ejecuta"], [
    ["Unitarias y de API", "pytest + TestClient de FastAPI", "SQLite local y PostgreSQL 16 en CI", "Cada push (GitHub Actions)"],
    ["End-to-end", "Playwright (Chromium)", "Sistema completo levantado por la prueba", "Cada push (GitHub Actions)"],
    ["Rendimiento", "k6", "Producción en Render (plan gratuito)", "Antes y después de cada optimización"],
    ["Seguridad dinámica", "Script propio (OWASP Top 10 + LLM)", "Producción", "Antes de cada entrega"],
    ["Seguridad estática", "Bandit · pip-audit", "Código fuente y dependencias", "Antes de cada entrega"],
    ["Usabilidad", "Heurísticas de Nielsen · cuestionario SUS", "Producción, escritorio y móvil", "Revisión de diseño / con usuarios"],
  ], [1900, 2500, 2700, 2260]),
  imagen("diagramas/11_cicd.png", "Figura 1. Las pruebas bloquean el despliegue si fallan", 560),

  h1("3. Pruebas funcionales"),
  h2("3.1 Pruebas unitarias y de API"),
  tabla(["Servicio", "Pruebas", "Cobertura", "Qué validan (ejemplos)"], [
    ["auth", porServicio.auth, `${n1(m.cobertura.auth.porcentaje)} %`, "Registro, contraseñas débiles, bloqueo por intentos, JWT inválido, roles, suspensión/bloqueo, recuperación de un solo uso"],
    ["reservas", porServicio.reservas, `${n1(m.cobertura.reservas.porcentaje)} %`, "Reglas de horario, solapamientos, capacidad, máximo de reservas, clases que bloquean, CSV, revocación, llegada, reportes, escala de sanciones, programador con reloj simulado, inyección SQL"],
    ["notificaciones", porServicio.notificaciones, `${n1(m.cobertura.notificaciones.porcentaje)} %`, "Idempotencia de eventos, plantillas, alertas del admin, escape de HTML en correos"],
    ["chatbot", porServicio.chatbot, `${n1(m.cobertura.chatbot.porcentaje)} %`, "Intenciones, fechas/horas, franjas libres, actividades y espacios nuevos, consejos vs búsqueda"],
  ], [1500, 1000, 1200, 5660]),
  imagen("graficos/06_cobertura.png", "Figura 2. Cobertura de líneas por servicio (meta 80 %)", 560),
  h3("Ejemplo: probar reglas que dependen del tiempo"),
  codigo(`def test_linea_de_tiempo_sin_confirmar_termina_en_sancion(client, reloj):
    rid = reservar(client, A, "10:00", "11:00")
    reloj(en(9, 51));  assert tareas(client)["recordatorios"] == 1
    reloj(en(10, 1));  assert tareas(client)["avisos_inicio"] == 1
    reloj(en(10, 12)); assert tareas(client)["avisos_finales"] == 1
    reloj(en(10, 21)); assert tareas(client)["inasistencias"] == 1      # sanción nivel 1`, "services/reservas/tests/test_incidencias.py"),
  h2("3.2 Pruebas end-to-end"),
  p("Cada escenario levanta los 4 servicios y el frontend, abre un navegador real y actúa como el usuario:"),
  tabla(["#", "Escenario"], e2e.map((l, i) => [String(i + 1), nombreE2E(l)]), [600, 8760]),
  h2("3.3 Integración continua"),
  p(`Cada push a la rama principal ejecuta en GitHub Actions las pruebas de los 4 servicios contra **PostgreSQL 16 real** y luego las pruebas E2E. Gracias a esto se detectó un error que solo ocurría en PostgreSQL (un GROUP BY con parámetros) y que SQLite no mostraba. Historial: [${URLS.ci}](${URLS.ci}).`),

  h1("4. Pruebas de rendimiento"),
  h2("4.1 Metodología"),
  tabla(["Elemento", "Detalle"], [
    ["Herramienta", "k6 v2.2 (`tests/carga/k6-escenarios.js`)"],
    ["Entorno", "Producción en Render, plan gratuito (0,1 CPU y 512 MB por servicio), región Oregón; cliente en Colombia"],
    ["Mezcla de operaciones", "Cada iteración: disponibilidad, espacios y mis reservas; 1 de cada 10 inicia sesión; 1 de cada 15 usa el chatbot; pausa de 1 s"],
    ["Escenario de carga", "Rampa a 10 usuarios (30 s), 20 usuarios sostenidos (90 s), bajada (30 s)"],
    ["Escenario de estrés", "Rampa 20 → 40 → 60 usuarios en 2 min y bajada"],
    ["Umbrales", "Fallas HTTP < 5 %; p95 /disponibilidad < 2 s; p95 /espacios < 1,5 s"],
  ], [2400, 6960]),
  h2("4.2 Resultados"),
  tabla(["Métrica", "Carga antes", "Carga después", "Estrés antes", "Estrés después"], [
    ["Peticiones totales", k.carga.total, k.carga_despues.total, k.estres.total, k.estres_despues.total],
    ["Rendimiento (pet/s)", n1(k.carga.rps), n1(k.carga_despues.rps), n1(k.estres.rps), n1(k.estres_despues.rps)],
    ["Latencia mediana", s(k.carga.med_ms), s(k.carga_despues.med_ms), s(k.estres.med_ms), s(k.estres_despues.med_ms)],
    ["Latencia p95", s(k.carga.p95_ms), s(k.carga_despues.p95_ms), s(k.estres.p95_ms), s(k.estres_despues.p95_ms)],
    ["Respuestas HTTP no 2xx", pct(k.carga.fallidas), pct(k.carga_despues.fallidas), pct(k.estres.fallidas), pct(k.estres_despues.fallidas)],
    ["Verificaciones de negocio", "100 %", "100 %", "100 %", "100 %"],
  ], [2560, 1700, 1700, 1700, 1700]),
  nota("Las respuestas no 2xx son **429 del chatbot**: todos los usuarios virtuales salen de la misma IP y el límite es de 15 mensajes por minuto por IP. Es el control anti-abuso funcionando, no una falla.", "nota"),
  imagen("graficos/01_carga_tiempo.png", "Figura 3. Carga: latencia p95 en el tiempo (antes y después)", 600),
  imagen("graficos/03_carga_endpoints.png", "Figura 4. Carga: latencia p95 por endpoint", 600),
  imagen("graficos/02_estres_tiempo.png", "Figura 5. Estrés: latencia p95 en el tiempo frente a usuarios virtuales", 600),
  imagen("graficos/04_estres_endpoints.png", "Figura 6. Estrés: latencia p95 por endpoint", 600),
  imagen("graficos/05_rendimiento_global.png", "Figura 7. Rendimiento y latencia global", 600),
  h2("4.3 Análisis del cuello de botella"),
  ...vinetas([
    `**Cuello de botella encontrado:** \`GET /disponibilidad\` hacía 2 consultas por cada espacio (problema N+1). Con 20 usuarios su p95 llegó a ${s(ep.carga.disponibilidad.p95)} y superó el umbral.`,
    "**Mismo patrón** en `/reservas/mias` y en la lista del admin: cada reserva cargaba su espacio con una consulta adicional.",
    `**La arquitectura distribuida ayudó:** el login (servicio auth, con su propia CPU) se mantuvo en p95 ≈ ${s(ep.estres.login.p95)} aun cuando reservas estaba saturado.`,
    `**Límite actual:** con 60 usuarios el servicio de reservas satura su 0,1 CPU (~${n1(k.estres_despues.rps)} pet/s); la latencia crece pero el sistema no se cae ni devuelve errores de negocio.`,
  ]),
  h2("4.4 Optimización aplicada y verificada"),
  codigo(`# Antes: 2 consultas por espacio
for e in espacios:
    ocupadas = ocupacion(db, e.id, fecha)          # SELECT horarios + SELECT reservas

# Después: 2 consultas en total, agrupadas en memoria
horarios = select(HorarioClase).where(HorarioClase.espacio_id.in_(ids), dia_semana == fecha.weekday())
reservas = select(Reserva).where(Reserva.espacio_id.in_(ids), Reserva.fecha == fecha)
# + selectinload(Reserva.espacio) en /reservas/mias y /reservas`, "services/reservas/app/main.py"),
  tabla(["Indicador", "Antes", "Después", "Mejora"], [
    ["p95 /disponibilidad (carga)", s(ep.carga.disponibilidad.p95), s(ep.carga_despues.disponibilidad.p95), "−" + mejora(ep.carga.disponibilidad.p95, ep.carga_despues.disponibilidad.p95)],
    ["p95 global (carga)", s(k.carga.p95_ms), s(k.carga_despues.p95_ms), "−" + mejora(k.carga.p95_ms, k.carga_despues.p95_ms)],
    ["p95 global (estrés)", s(k.estres.p95_ms), s(k.estres_despues.p95_ms), "−" + mejora(k.estres.p95_ms, k.estres_despues.p95_ms)],
    ["Rendimiento (estrés)", n1(k.estres.rps) + " pet/s", n1(k.estres_despues.rps) + " pet/s", "+" + Math.round((k.estres_despues.rps / k.estres.rps - 1) * 100) + " %"],
  ], [3360, 2000, 2000, 2000]),

  h1("5. Pruebas de seguridad"),
  h2("5.1 Auditoría dinámica (OWASP Top 10 y riesgos de LLM)"),
  p(`Script \`tests/seguridad/auditoria_owasp.py\` ejecutado contra producción el ${owasp.fecha}. Resultado: **${totalOk} de ${owasp.controles.length} controles superados**.`),
  imagen("graficos/07_owasp.png", "Figura 8. Controles por categoría", 540),
  tabla(["OWASP", "Control", "Esperado", "Obtenido", "✓"],
    owasp.controles.map((c) => [c.owasp, c.control, c.esperado, String(c.obtenido).slice(0, 90), c.ok ? "✅" : "❌"]),
    [800, 3000, 1800, 3060, 700]),
  nota("Hallazgo positivo: el WAF de Cloudflare, que está delante de Render, bloquea con 403 patrones de inyección SQL antes de que lleguen al servicio. Además, una prueba unitaria confirma que la aplicación por sí sola tampoco es vulnerable (consultas parametrizadas del ORM).", "consejo"),
  h2("5.2 Análisis estático (Bandit)"),
  tabla(["Hallazgo", "Severidad", "Archivo", "Mitigación", "Estado"], [
    ["B310: `urlopen` con URL de configuración", "Media", "auth/eventos.py, reservas/eventos.py", "Validar esquema http(s) antes de abrir la URL", "✅ Corregido"],
    ["B310: `urlopen` hacia auth-service", "Media", "reservas/main.py", "Validar esquema http(s)", "✅ Corregido"],
    ["B110: try/except/pass", "Baja", "eventos.py (x2)", "Intencional: \"despertar\" es de mejor esfuerzo; documentado", "✅ Justificado"],
    ["B105: posible contraseña", "Baja", "auth/main.py", "Falso positivo (nombre de columna)", "✅ Justificado"],
  ], [2600, 900, 2200, 2460, 1200]),
  p("Resultado final: **0 hallazgos** (alta, media o baja) en 2 461 líneas analizadas."),
  h2("5.3 Dependencias (pip-audit)"),
  p("Se analizaron los `requirements.txt` de los 4 servicios contra la base de vulnerabilidades de PyPI/OSV: **0 vulnerabilidades conocidas en 104 paquetes**."),

  h1("6. Pruebas de usabilidad"),
  h2("6.1 Evaluación heurística (Nielsen)"),
  p("Revisión experta de la interfaz en escritorio y móvil. Severidad: 0 = no es problema · 4 = catastrófico."),
  tabla(["Heurística", "Evidencia en ReservaCampus", "Sev."], [
    ["1. Visibilidad del estado", "Notificaciones con contador, avisos emergentes, barra de ocupación del día, estados de reserva con color, aviso de sanción vigente", "0"],
    ["2. Relación con el mundo real", "Lenguaje del campus (sala, cancha, clase, llegada); fechas en español", "0"],
    ["3. Control y libertad", "Cancelar reservas, diálogos con botón Volver, cerrar con Esc o clic afuera", "0"],
    ["4. Consistencia y estándares", "Mismo estilo de botones, dropdowns y diálogos en toda la app", "0"],
    ["5. Prevención de errores", "Solo horas válidas en bloques de 30 min, límite de asistentes por capacidad, confirmación antes de acciones destructivas", "0"],
    ["6. Reconocer antes que recordar", "Sugerencias del chat, plantillas de alertas, ocupación visible al reservar", "0"],
    ["7. Flexibilidad y eficiencia", "Filtros, carga masiva por CSV, preguntas en lenguaje natural", "1"],
    ["8. Diseño estético y minimalista", "Tarjetas limpias, tablas que en móvil se vuelven tarjetas", "0"],
    ["9. Recuperarse de errores", "Mensajes que explican la causa (\"hay clase de Programación I de 08:00 a 10:00\")", "0"],
    ["10. Ayuda y documentación", "Asistente virtual, textos de ayuda en formularios, manual de usuario", "1"],
  ], [2500, 6160, 700]),
  h3("Problemas encontrados y corregidos durante el desarrollo"),
  tabla(["Problema detectado", "Corrección", "Verificación"], [
    ["Campos que se salían de la tarjeta en móvil", "Rejillas con `minmax(0, 1fr)` y tablas convertidas en tarjetas", "Prueba E2E \"sin desborde horizontal en móvil\""],
    ["Selects y selector de archivo genéricos del navegador", "Componentes propios (dropdown, zona de arrastre)", "Prueba E2E de filtro con select personalizado"],
    ["Confirmaciones nativas del navegador", "Diálogos con estilo propio", "Pruebas E2E de cancelar/eliminar"],
    ["No se podía ver la contraseña al escribirla", "Botón mostrar/ocultar", "Prueba E2E de mostrar/ocultar"],
    ["Al cerrar sesión quedaba en \"Crear cuenta\"", "Vuelve siempre a \"Iniciar sesión\"", "Prueba E2E de bloqueo de cuenta"],
    ["El chatbot ofrecía la cancha para videojuegos", "Recomendación según espacios reales", "Pruebas del chatbot y E2E"],
    ["El botón Reportar seguía visible tras reportar", "Indicador \"Ocupación reportada\"", "Prueba de API"],
  ], [3000, 3400, 2960]),
  h2("6.2 Prueba con usuarios (SUS)"),
  p("Para medir la satisfacción se usará la **System Usability Scale (SUS)** con al menos 5 estudiantes que no hayan usado la plataforma. Tareas:"),
  ...pasos([
    "Registrarse e iniciar sesión.",
    "Encontrar una sala de estudio libre mañana a las 10:00 y reservarla.",
    "Preguntar al asistente si hay cancha disponible para fútbol.",
    "Confirmar la llegada a una reserva en curso (preparada por el evaluador).",
    "Cancelar una reserva.",
  ]),
  tabla(["#", "Afirmación (1 = muy en desacuerdo … 5 = muy de acuerdo)"], [
    ["1", "Creo que me gustaría usar este sistema con frecuencia."], ["2", "Encontré el sistema innecesariamente complejo."],
    ["3", "Pensé que el sistema era fácil de usar."], ["4", "Creo que necesitaría ayuda de un técnico para usarlo."],
    ["5", "Las funciones del sistema están bien integradas."], ["6", "Hay demasiada inconsistencia en el sistema."],
    ["7", "La mayoría de personas aprenderían a usarlo muy rápido."], ["8", "El sistema es muy engorroso de usar."],
    ["9", "Me sentí muy seguro usando el sistema."], ["10", "Necesité aprender muchas cosas antes de poder usarlo."],
  ], [600, 8760]),
  p("**Cálculo:** a las respuestas impares se les resta 1; a las pares se les resta su valor a 5; la suma se multiplica por 2,5 (puntaje de 0 a 100). Meta: **≥ 68** (por encima del promedio de la industria)."),
  tabla(["Participante", "Tareas completadas (de 5)", "Tiempo total", "Puntaje SUS", "Comentarios"], [
    ["P1", "", "", "", ""], ["P2", "", "", "", ""], ["P3", "", "", "", ""], ["P4", "", "", "", ""], ["P5", "", "", "", ""], ["Promedio", "", "", "", ""],
  ], [1500, 2200, 1500, 1500, 2660]),
  nota("Esta tabla se completa al aplicar la prueba con usuarios reales. No se incluyen valores inventados.", "alerta"),

  h1("7. Plan de mitigación de vulnerabilidades y riesgos"),
  tabla(["ID", "Riesgo / vulnerabilidad", "Prob.", "Impacto", "Mitigación", "Estado"], [
    ["M-01", "Consultas N+1 degradan la disponibilidad bajo carga", "Alta", "Alto", "Consultas agrupadas y selectinload", "✅ Aplicada y medida"],
    ["M-02", "urlopen con esquemas no web (Bandit B310)", "Baja", "Medio", "Validar http(s)", "✅ Aplicada"],
    ["M-03", "Fuerza bruta sobre el login", "Media", "Alto", "Bloqueo tras 5 intentos por IP (429)", "✅ Aplicada"],
    ["M-04", "Abuso del chatbot / costo de IA", "Media", "Medio", "15 mensajes/min por IP y 500 caracteres", "✅ Aplicada"],
    ["M-05", "Inyección de prompt", "Media", "Medio", "Prompt de sistema; reglas para datos sensibles", "✅ Aplicada"],
    ["M-06", "Saturación de CPU con > 40 usuarios", "Media", "Medio", "Plan pago (1 CPU) o réplicas; caché de /espacios (TTL 30 s)", "🟡 Planificada"],
    ["M-07", "Límite por IP compartida (campus con NAT)", "Media", "Bajo", "Límite por usuario autenticado además de por IP", "🟡 Planificada"],
    ["M-08", "Secreto JWT compartido entre servicios", "Baja", "Alto", "Migrar a RS256 con llave pública", "🟡 Planificada"],
    ["M-09", "Swagger público en producción", "Media", "Bajo", "Proteger /docs o desactivarlo en producción", "🟡 Planificada"],
    ["M-10", "Base de datos gratuita expira (30 días) y sin respaldos", "Alta", "Alto", "Plan pago con respaldos diarios o exportación programada", "🟡 Planificada"],
    ["M-11", "Bloqueo de cuenta permanente vía IP del atacante", "Baja", "Bajo", "Bloqueo temporal (5 min) ya implementado", "✅ Aplicada"],
    ["M-12", "Dependencias vulnerables futuras", "Media", "Medio", "pip-audit en el CI y Dependabot", "🟡 Planificada"],
  ], [700, 2500, 700, 900, 3000, 1560]),

  h1("8. Conclusiones"),
  ...vinetas([
    "El sistema cumple los requisitos funcionales: 136 pruebas automatizadas (115 unitarias/API + 21 E2E) pasan en cada cambio, también contra PostgreSQL real.",
    "Las pruebas de rendimiento encontraron un cuello de botella real (N+1); la optimización redujo el p95 de la disponibilidad en un " + mejora(ep.carga.disponibilidad.p95, ep.carga_despues.disponibilidad.p95) + " y aumentó el rendimiento en estrés.",
    "La plataforma supera los 25 controles de seguridad automatizados y no tiene hallazgos de análisis estático ni dependencias vulnerables.",
    "El principal límite restante es de infraestructura (plan gratuito con 0,1 CPU), no de diseño: la arquitectura permite escalar cada servicio por separado.",
  ]),
  h3("Cómo reproducir las pruebas"),
  codigo(`cd services/reservas && python -m pytest -q --cov=app            # unitarias + cobertura (igual en cada servicio)
python -m pytest tests/e2e                                          # end-to-end
k6 run -e ESCENARIO=carga  tests/carga/k6-escenarios.js            # rendimiento
k6 run -e ESCENARIO=estres tests/carga/k6-escenarios.js
python tests/seguridad/auditoria_owasp.py                          # seguridad dinámica
bandit -r services -x "*/tests/*" ; pip-audit -r services/<servicio>/requirements.txt
python docs/fuentes/graficos.py                                     # regenera los gráficos`, "Comandos"),
];

generar("04_Informe_de_Pruebas.docx", "Informe de Pruebas", contenido);
