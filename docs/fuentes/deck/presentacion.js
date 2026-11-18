// Presentación final (defensa) de ReservaCampus. Uso: node presentacion.js
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.PPTX_SKILL + "/scripts/apply_theme.js");

const RAIZ = path.resolve(__dirname, "..", "..", "..");
const IMG = path.join(RAIZ, "docs", "img");
const met = JSON.parse(fs.readFileSync(path.join(RAIZ, "docs", "fuentes", "metricas.json"), "utf8"));
const owasp = JSON.parse(fs.readFileSync(path.join(RAIZ, "tests", "seguridad", "resultados", "owasp.json"), "utf8"));
const SALIDA = path.join(RAIZ, "docs", "entregables", "07_Presentacion_Final.pptx");

const THEME = {
  name: "ReservaCampus", headFontFace: "Arial", bodyFontFace: "Arial",
  colors: { dk1: "15192B", lt1: "FFFFFF", dk2: "1B2A8A", lt2: "F4F6FB", accent1: "3B4CCA", accent2: "FFB547",
    accent3: "17915A", accent4: "C8364A", accent5: "7B2CBF", accent6: "5D6480", hlink: "3B4CCA", folHlink: "7B2CBF" },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "ReservaCampus — Presentación final";
pres.author = "Equipo ReservaCampus";
const C = pres.SchemeColor;

// ---------------------------------------------------------------- layouts
pres.defineSlideMaster({
  title: "Portada", background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.2, w: 11.7, h: 1.4, fontSize: 54, bold: true, color: C.background1, valign: "bottom", align: "left" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 3.75, w: 11.7, h: 1.2, fontSize: 22, color: "CADCFC", valign: "top", align: "left" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "Seccion", background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 0.55, w: 11.7, h: 1.0, fontSize: 40, bold: true, color: C.background1 }, text: "" } },
  ],
  slideNumber: { x: 12.3, y: 7.0, w: 0.6, h: 0.3, fontSize: 11, color: "CADCFC" },
});
pres.defineSlideMaster({
  title: "Contenido", background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.9, fontSize: 36, bold: true, color: C.text2, valign: "middle" }, text: "" } },
    { text: { text: "ReservaCampus · Ingeniería de Software II", options: { x: 0.6, y: 7.0, w: 6, h: 0.3, fontSize: 10, color: C.accent6 } } },
  ],
  slideNumber: { x: 12.3, y: 7.0, w: 0.6, h: 0.3, fontSize: 10, color: C.accent6 },
});

// ---------------------------------------------------------------- utilidades
function tamPng(rel) {
  const b = fs.readFileSync(path.join(IMG, rel));
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
function imagen(slide, rel, x, y, w, h, nombre, sombra = true) {
  const t = tamPng(rel);
  let iw = w, ih = (t.h / t.w) * w;
  if (ih > h) { ih = h; iw = (t.w / t.h) * h; }
  slide.addImage({ path: path.join(IMG, rel), x: x + (w - iw) / 2, y: y + (h - ih) / 2, w: iw, h: ih, objectName: nombre, altText: nombre,
    shadow: sombra ? { type: "outer", color: "1B2A8A", opacity: 0.18, blur: 8, offset: 3, angle: 90 } : undefined });
}
function tarjeta(slide, { x, y, w, h, icono, titulo, texto, color = C.accent1, nombre, tam = 14 }) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: C.background2 }, line: { color: C.background2 }, objectName: `${nombre}-fondo` });
  slide.addShape(pres.shapes.OVAL, { x: x + 0.25, y: y + 0.25, w: 0.62, h: 0.62, fill: { color }, line: { color }, objectName: `${nombre}-circulo` });
  slide.addText(icono, { x: x + 0.25, y: y + 0.25, w: 0.62, h: 0.62, fontSize: 20, align: "center", valign: "middle", isTextBox: true, margin: 0, objectName: `${nombre}-icono` });
  slide.addText(titulo, { x: x + 1.0, y: y + 0.22, w: w - 1.15, h: 0.66, fontSize: 17, bold: true, color: C.text1, valign: "middle", isTextBox: true, margin: 0, objectName: `${nombre}-titulo` });
  slide.addText(texto, { x: x + 0.25, y: y + 1.0, w: w - 0.45, h: h - 1.15, fontSize: tam, color: C.accent6, valign: "top", isTextBox: true, margin: 0, objectName: `${nombre}-texto`, paraSpaceAfter: 4 });
}
function dato(slide, { x, y, w, valor, etiqueta, color = C.accent1, nombre }) {
  slide.addText(valor, { x, y, w, h: 0.95, fontSize: 48, bold: true, color, isTextBox: true, margin: 0, objectName: `${nombre}-valor` });
  slide.addText(etiqueta, { x, y: y + 0.95, w, h: 0.6, fontSize: 14, color: C.accent6, isTextBox: true, margin: 0, objectName: `${nombre}-etiqueta`, valign: "top" });
}
function vinetas(slide, items, op) {
  slide.addText(items.map((t, i) => ({ text: t, options: { bullet: { indent: 18 }, breakLine: i < items.length - 1 } })),
    { fontSize: 16, color: C.text1, paraSpaceAfter: 9, valign: "top", isTextBox: true, ...op });
}
const contenido = (titulo, seccion) => { const s = pres.addSlide({ masterName: "Contenido", sectionTitle: seccion }); s.addText(titulo, { placeholder: "title" }); return s; };
const seg = (ms) => (ms / 1000).toFixed(2).replace(".", ",") + " s";

// ================================================================ 1. Portada
pres.addSection({ title: "Inicio" });
let s = pres.addSlide({ masterName: "Portada", sectionTitle: "Inicio" });
s.addText("ReservaCampus", { placeholder: "title" });
s.addText("Plataforma distribuida e inteligente para reservar espacios universitarios", { placeholder: "body" });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.8, y: 1.2, w: 0.95, h: 0.95, rectRadius: 0.18, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: "logo" });
s.addText("RC", { x: 0.8, y: 1.2, w: 0.95, h: 0.95, fontSize: 30, bold: true, color: C.background1, align: "center", valign: "middle", isTextBox: true, margin: 0, objectName: "logo-texto" });
s.addText("Electiva de Ingeniería de Software II · Trabajo final", { x: 0.8, y: 6.2, w: 8, h: 0.4, fontSize: 16, color: "CADCFC", isTextBox: true, margin: 0, objectName: "curso" });
s.addText("reservacampus-web-gcr3.onrender.com", { x: 7.5, y: 6.2, w: 5, h: 0.4, fontSize: 16, color: C.accent2, align: "right", isTextBox: true, margin: 0, objectName: "url",
  hyperlink: { url: "https://reservacampus-web-gcr3.onrender.com" } });
s.addNotes("Presentación del equipo y del proyecto. Una frase: ReservaCampus permite reservar salas, laboratorios, auditorio y cancha de la universidad, evita choques de horario y asegura que los espacios reservados se usen de verdad. Duración total: ~20 minutos + demo.");

// ================================================================ 2. Problema
pres.addSection({ title: "Problema y solución" });
s = contenido("El problema: espacios mal aprovechados", "Problema y solución");
tarjeta(s, { x: 0.6, y: 1.6, w: 3.9, h: 2.4, icono: "📅", titulo: "Choques de horario", texto: "Reservas por correo o en papel: dos grupos llegan al mismo salón, o chocan con una clase.", color: C.accent4, nombre: "p1" });
tarjeta(s, { x: 4.72, y: 1.6, w: 3.9, h: 2.4, icono: "🚪", titulo: "Salas reservadas vacías", texto: "Se reserva \"por si acaso\" y nadie llega. Otros estudiantes se quedan sin espacio.", color: C.accent2, nombre: "p2" });
tarjeta(s, { x: 8.84, y: 1.6, w: 3.9, h: 2.4, icono: "⏰", titulo: "No entregan a tiempo", texto: "El grupo anterior sigue en el salón y no hay cómo reportarlo ni consecuencias.", color: C.accent5, nombre: "p3" });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 4.45, w: 12.14, h: 2.2, rectRadius: 0.12, fill: { color: C.text2 }, line: { color: C.text2 }, objectName: "pregunta-fondo" });
s.addText([{ text: "Pregunta guía\n", options: { fontSize: 16, color: C.accent2, bold: true, breakLine: true } },
  { text: "¿Cómo lograr que cada espacio se reserve sin conflictos, se use realmente y se libere a tiempo, con un sistema confiable aunque una parte falle?", options: { fontSize: 24, color: C.background1 } }],
  { x: 1.0, y: 4.6, w: 11.3, h: 1.9, valign: "middle", isTextBox: true, margin: 0, objectName: "pregunta" });
s.addNotes("Contar el escenario real: hoy los espacios se piden de forma informal. Tres dolores: choques de horario (incluso con clases), salas reservadas que nadie usa, y grupos que no entregan a tiempo. Esto motiva las reglas de llegada y sanciones.");

// ================================================================ 3. Solución
s = contenido("La solución: ReservaCampus", "Problema y solución");
const funciones = [
  ["🔎", "Disponibilidad real", "Reservas + clases fijas, barra del día por espacio"],
  ["✅", "Reglas automáticas", "Bloques de 30 min, máx. 3 h, capacidad, 3 activas"],
  ["📍", "Llegada y reportes", "Confirmar llegada; reportar si no entregan (10 min)"],
  ["⚖️", "Sanciones escalonadas", "1 día → 3 días → 1 semana → suspensión"],
  ["💬", "Asistente híbrido", "Reglas con datos reales + IA (Groq)"],
  ["🛠️", "Panel de administración", "Espacios, horarios CSV, usuarios, incidencias"],
];
funciones.forEach(([ic, t, d], i) => {
  const col = i % 3, fila = Math.floor(i / 3);
  tarjeta(s, { x: 0.6 + col * 4.12, y: 1.55 + fila * 2.6, w: 3.9, h: 2.35, icono: ic, titulo: t, texto: d, color: [C.accent1, C.accent3, C.accent2, C.accent4, C.accent5, C.text2][i], nombre: `f${i}` });
});
s.addNotes("Seis capacidades. Resaltar que la disponibilidad considera los horarios de clase y que el chatbot responde con datos reales, no inventados. Todo funciona en celular.");

// ================================================================ 4. Arquitectura
pres.addSection({ title: "Arquitectura" });
s = contenido("Arquitectura: 4 microservicios + eventos", "Arquitectura");
imagen(s, "diagramas/02_c4_contenedores.png", 0.6, 1.4, 6.6, 5.5, "Diagrama de contenedores");
vinetas(s, [
  "auth: usuarios, JWT, estados de cuenta, recuperación",
  "reservas: espacios, horarios, reservas, sanciones, programador",
  "notificaciones: consume eventos, app + correo (Brevo)",
  "chatbot: reglas + IA (Groq)",
  "PostgreSQL con tablas por servicio · Redis Streams para eventos",
  "Desplegado en Render · Docker Compose en local",
], { x: 7.5, y: 1.6, w: 5.2, h: 5.0 });
s.addNotes("Explicar el modelo C4 nivel 2. Cada servicio es independiente: si el chatbot o la IA fallan, se puede seguir reservando. La comunicación es REST para lo síncrono y Redis Streams para lo asíncrono. Mostrar render.yaml como infraestructura como código si preguntan.");

// ================================================================ 5. Comunicación
s = contenido("Comunicación síncrona y asíncrona", "Arquitectura");
imagen(s, "diagramas/05_secuencia_reserva.png", 0.6, 1.35, 8.0, 5.5, "Secuencia de una reserva");
tarjeta(s, { x: 8.9, y: 1.5, w: 3.85, h: 2.45, icono: "⇄", titulo: "REST (síncrono)", texto: "Frontend → servicios con JWT. Reservas consulta a auth el estado de la cuenta.", color: C.accent1, nombre: "c1" });
tarjeta(s, { x: 8.9, y: 4.2, w: 3.85, h: 2.6, icono: "🧵", titulo: "Eventos (asíncrono)", texto: "XADD → XREADGROUP → XACK. Idempotente, reintenta pendientes, tolera caídas.", color: C.accent2, nombre: "c2" });
s.addNotes("Recorrer la secuencia: el usuario reserva, se valida sanción, reglas y solapamientos con SELECT FOR UPDATE, se guarda y se publica reserva.creada. El servicio de notificaciones la consume después: la reserva no espera al correo. Si Redis cae, la reserva igual se guarda.");

// ================================================================ 6. Datos
s = contenido("Persistencia: una base por servicio", "Arquitectura");
const filasTablas = [["Tabla", "Servicio", "Guarda"], ["usuarios", "auth", "Cuentas, rol, estado, hash de contraseña"], ["espacios", "reservas", "Tipo, capacidad, horario, actividades"],
  ["horarios_clase", "reservas", "Clases fijas que bloquean el espacio"], ["reservas", "reservas", "Estado, llegada confirmada, avisos"],
  ["sanciones", "reservas", "Nivel, vigencia, estado"], ["reportes", "reservas", "Espacio no entregado y su sanción"], ["notificaciones", "notificaciones", "Avisos con evento_id único"]];
s.addTable(filasTablas.map((f, i) => f.map((t) => ({ text: t, options: i === 0 ? { bold: true, color: C.background1, fill: { color: C.accent1 } } : { color: C.text1, fill: { color: i % 2 ? C.background2 : C.background1 } } }))),
  { x: 0.6, y: 1.55, w: 7.4, colW: [1.9, 1.7, 3.8], fontSize: 14, rowH: 0.55, border: { type: "solid", pt: 0.5, color: "D9DEEC" }, valign: "middle", objectName: "tabla-datos" });
vinetas(s, [
  "Cada servicio es dueño de sus tablas (7 tablas)",
  "Sin claves foráneas entre servicios: copias controladas (nombre, correo)",
  "SQLAlchemy ORM: consultas parametrizadas",
  "SELECT … FOR UPDATE evita dobles reservas",
  "Migraciones automáticas al desplegar",
  "Scripts: db/esquema_postgresql.sql y datos_semilla.sql",
], { x: 8.3, y: 1.6, w: 4.4, h: 5.0 });
s.addNotes("Explicar el patrón database-per-service. En Docker cada servicio tiene su base; en Render comparten instancia pero no tablas. Mencionar que el CI prueba con PostgreSQL real, lo que detectó un error que SQLite ocultaba.");

// ================================================================ 7. Reglas de llegada
s = contenido("Llegada, reportes y sanciones", "Arquitectura");
imagen(s, "diagramas/07_linea_tiempo_llegada.png", 0.6, 1.4, 12.1, 2.6, "Línea de tiempo de la reserva", false);
imagen(s, "diagramas/08_escalamiento_sanciones.png", 0.6, 4.25, 12.1, 2.5, "Escalamiento de sanciones", false);
s.addNotes("El programador revisa cada minuto: −10 min recordatorio, inicio, +10 último aviso y habilita reportar, +20 inasistencia y sanción. Las sanciones escalan por reincidencia. Un reporte anulado por el admin no cuenta. Como Render duerme los servicios, un cron de GitHub Actions lo despierta cada 10 minutos.");

// ================================================================ 8. Chatbot
s = contenido("Asistente virtual: reglas primero, IA después", "Arquitectura");
imagen(s, "capturas/e13_chat_disponibilidad.png", 0.6, 1.35, 3.6, 5.5, "Chat respondiendo disponibilidad");
imagen(s, "capturas/e14_chat_sin_espacio.png", 4.4, 1.35, 3.6, 5.5, "Chat sin espacio para la actividad");
vinetas(s, [
  "Reglas: intenciones + datos reales (disponibilidad, mis reservas, reglas)",
  "Reconoce actividades y busca en los espacios existentes",
  "Si el admin crea una \"Sala Gamer\", la recomienda sin cambiar código",
  "IA (Groq) solo para preguntas abiertas",
  "Seguro: límite de mensajes, prompt anti-inyección",
], { x: 8.3, y: 1.6, w: 4.4, h: 5.0 });
s.addNotes("Mostrar que pedir fútbol responde con la cancha y sus horas libres, y que para videojuegos dice que no existe un espacio. Explicar la cadena de responsabilidad: reglas, luego IA, luego respaldo. La etiqueta debajo indica si respondió por reglas o con IA.");

// ================================================================ 9. Administración
s = contenido("Panel de administración", "Arquitectura");
imagen(s, "capturas/a09_ficha_usuario.png", 0.6, 1.4, 6.3, 3.9, "Ficha de usuario");
imagen(s, "capturas/a05_horarios.png", 7.1, 1.4, 5.6, 3.9, "Horario semanal");
const admin = [["👥", "Usuarios", "Suspender, bloquear, restablecer, alertas"], ["🗓️", "Horarios", "Clases fijas y carga CSV"], ["⚖️", "Incidencias", "Levantar sanciones, anular reportes"]];
admin.forEach(([ic, t, d], i) => {
  s.addShape(pres.shapes.OVAL, { x: 0.6 + i * 4.12, y: 5.65, w: 0.55, h: 0.55, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: `adm${i}-circulo` });
  s.addText(ic, { x: 0.6 + i * 4.12, y: 5.65, w: 0.55, h: 0.55, fontSize: 16, align: "center", valign: "middle", isTextBox: true, margin: 0, objectName: `adm${i}-icono` });
  s.addText([{ text: t + "  ", options: { bold: true, color: C.text1 } }, { text: d, options: { color: C.accent6 } }],
    { x: 1.3 + i * 4.12, y: 5.55, w: 3.4, h: 0.75, fontSize: 14, valign: "middle", isTextBox: true, margin: 0, objectName: `adm${i}-texto` });
});
s.addNotes("La ficha del usuario reúne historial de reservas con hora de llegada, sanciones, reportes y avisos. Desde ahí se suspende, bloquea, restablece contraseña o envía alertas. Los horarios de clase bloquean los espacios y se cargan por CSV con validación todo o nada.");

// ================================================================ 10. Demo
pres.addSection({ title: "Demostración" });
s = pres.addSlide({ masterName: "Seccion", sectionTitle: "Demostración" });
s.addText("Demostración en vivo", { placeholder: "title" });
const demo = [["1", "Estudiante: reservar una sala y ver la notificación"], ["2", "Asistente: ¿hay cancha mañana a las 4? · videojuegos"], ["3", "Llegada: confirmar y reportar espacio ocupado"],
  ["4", "Admin: crear Sala Gamer → el chat la recomienda"], ["5", "Admin: suspender un usuario y verlo bloqueado al reservar"], ["6", "Swagger y GitHub Actions en verde"]];
demo.forEach(([n, t], i) => {
  const col = i % 2, fila = Math.floor(i / 2);
  const x = 0.8 + col * 6.1, y = 1.9 + fila * 1.6;
  s.addShape(pres.shapes.OVAL, { x, y, w: 0.8, h: 0.8, fill: { color: C.accent2 }, line: { color: C.accent2 }, objectName: `demo${n}-circulo` });
  s.addText(n, { x, y, w: 0.8, h: 0.8, fontSize: 24, bold: true, color: C.text2, align: "center", valign: "middle", isTextBox: true, margin: 0, objectName: `demo${n}-num` });
  s.addText(t, { x: x + 1.0, y, w: 4.9, h: 0.8, fontSize: 18, color: C.background1, valign: "middle", isTextBox: true, margin: 0, objectName: `demo${n}-texto` });
});
s.addNotes("Seguir el guion de la Guía de Presentación. Tener abiertos antes: la app con estudiante, otra ventana privada con admin, Swagger de reservas y GitHub Actions. Despertar los servicios 5 minutos antes.");

// ================================================================ 11. Calidad
pres.addSection({ title: "Calidad" });
s = contenido("Calidad: 136 pruebas automatizadas", "Calidad");
dato(s, { x: 0.6, y: 1.6, w: 2.9, valor: "115", etiqueta: "pruebas unitarias y de API", nombre: "d1" });
dato(s, { x: 3.65, y: 1.6, w: 2.9, valor: "21", etiqueta: "pruebas end-to-end (Playwright)", color: C.accent5, nombre: "d2" });
dato(s, { x: 6.7, y: 1.6, w: 2.9, valor: `${met.cobertura.reservas.porcentaje.toFixed(1).replace(".", ",")} %`, etiqueta: "cobertura del servicio de reservas", color: C.accent3, nombre: "d3" });
dato(s, { x: 9.75, y: 1.6, w: 3.0, valor: `${owasp.controles.filter((c) => c.ok).length}/${owasp.controles.length}`, etiqueta: "controles OWASP superados", color: C.accent4, nombre: "d4" });
["git push", "Unitarias ×4\n(PostgreSQL 16)", "End-to-end\n(Playwright)", "Despliegue\nen Render"].forEach((t, i) => {
  const x = 0.6 + i * 3.15;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 4.0, w: 2.6, h: 1.25, rectRadius: 0.12, fill: { color: i === 3 ? C.accent3 : C.accent1 }, line: { color: i === 3 ? C.accent3 : C.accent1 }, objectName: `ci${i}` });
  s.addText(t, { x, y: 4.0, w: 2.6, h: 1.25, fontSize: 17, bold: true, color: C.background1, align: "center", valign: "middle", isTextBox: true, margin: 0, objectName: `ci${i}-texto` });
  if (i < 3) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 2.68, y: 4.4, w: 0.42, h: 0.45, fill: { color: C.accent6 }, line: { color: C.accent6 }, objectName: `ci${i}-flecha` });
});
s.addText("Cada push ejecuta todo contra PostgreSQL 16 real; si algo falla, no se despliega.", { x: 0.6, y: 5.75, w: 12.1, h: 0.5, fontSize: 16, italic: true, color: C.accent6, align: "center", isTextBox: true, margin: 0, objectName: "ci-nota" });
s.addNotes("Pirámide de pruebas: unitarias (reglas, sanciones con reloj simulado), E2E con navegador real, rendimiento con k6 y seguridad. El CI encontró un error que solo pasaba en PostgreSQL.");

// ================================================================ 12. Rendimiento (gráfico nativo)
s = contenido("Rendimiento: un cuello de botella corregido", "Calidad");
const ep = met.k6_endpoints;
const eps = ["disponibilidad", "espacios", "mis_reservas", "chat"];
const etiquetas = ["/disponibilidad", "/espacios", "/reservas/mias", "/chat"];
s.addChart(pres.charts.BAR, [
  { name: "Antes", labels: etiquetas, values: eps.map((e) => +(ep.carga[e].p95 / 1000).toFixed(2)) },
  { name: "Después", labels: etiquetas, values: eps.map((e) => +(ep.carga_despues[e].p95 / 1000).toFixed(2)) },
], { x: 0.6, y: 1.4, w: 7.6, h: 5.4, barDir: "col", chartColors: [HEX.accent4, HEX.accent1], showLegend: true, legendPos: "b", legendFontSize: 12, legendFontFace: "+mn-lt",
  showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelFontFace: "+mn-lt", dataLabelColor: HEX.dk1, dataLabelFormatCode: "0.00",
  showTitle: true, title: "Latencia p95 con 20 usuarios (segundos)", titleFontSize: 14, titleFontFace: "+mn-lt", titleColor: HEX.dk1,
  catAxisLabelColor: HEX.accent6, valAxisLabelColor: HEX.accent6, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", catAxisLabelFontSize: 12, valAxisLabelFontSize: 11,
  valGridLine: { color: "E2E6F0", size: 0.75 }, catGridLine: { style: "none" }, objectName: "grafico-rendimiento" });
dato(s, { x: 8.6, y: 1.6, w: 4.1, valor: "−" + Math.round((1 - ep.carga_despues.disponibilidad.p95 / ep.carga.disponibilidad.p95) * 100) + " %", etiqueta: "latencia p95 de /disponibilidad", color: C.accent3, nombre: "r1" });
dato(s, { x: 8.6, y: 3.3, w: 4.1, valor: "+" + Math.round((met.k6.estres_despues.rps / met.k6.estres.rps - 1) * 100) + " %", etiqueta: "peticiones/s en estrés (60 usuarios)", color: C.accent1, nombre: "r2" });
s.addText("Causa: consultas N+1 (2 por espacio). Solución: 2 consultas en total y carga anticipada.", { x: 8.6, y: 5.1, w: 4.1, h: 1.5, fontSize: 15, color: C.text1, valign: "top", isTextBox: true, margin: 0, objectName: "r-causa" });
s.addNotes(`k6 contra producción. Antes, /disponibilidad tenía p95 de ${seg(ep.carga.disponibilidad.p95)} con 20 usuarios. Se identificó el problema N+1 y se optimizó: bajó a ${seg(ep.carga_despues.disponibilidad.p95)}. El límite restante es la CPU del plan gratuito (0,1 CPU): con 60 usuarios la latencia sube pero el sistema no se cae. El login no se afectó porque auth es otro servicio.`);

// ================================================================ 13. Seguridad
s = contenido("Seguridad: OWASP Top 10 + riesgos de IA", "Calidad");
const seg4 = [
  ["🔐", "Acceso y sesiones", "JWT firmado, roles, anti-IDOR, bloqueo tras 5 intentos"],
  ["🧪", "Entrada", "ORM parametrizado, validación Pydantic, XSS escapado"],
  ["🌐", "Configuración", "HTTPS, CORS restringido, cabeceras de seguridad"],
  ["🤖", "IA", "Anti prompt-injection, 15 mensajes/min, 500 caracteres"],
];
seg4.forEach(([ic, t, d], i) => tarjeta(s, { x: 0.6 + (i % 2) * 4.15, y: 1.55 + Math.floor(i / 2) * 2.6, w: 3.95, h: 2.35, icono: ic, titulo: t, texto: d, color: [C.accent1, C.accent3, C.accent5, C.accent2][i], nombre: `s${i}` }));
dato(s, { x: 9.2, y: 1.6, w: 3.5, valor: `${owasp.controles.filter((c) => c.ok).length}/${owasp.controles.length}`, etiqueta: "controles dinámicos superados", color: C.accent3, nombre: "s-owasp" });
dato(s, { x: 9.2, y: 3.4, w: 3.5, valor: "0", etiqueta: "hallazgos Bandit tras mitigar", color: C.accent1, nombre: "s-bandit" });
dato(s, { x: 9.2, y: 5.2, w: 3.5, valor: "0", etiqueta: "dependencias vulnerables (pip-audit)", color: C.accent5, nombre: "s-audit" });
s.addNotes("Auditoría automatizada contra producción: 25 controles. Hallazgo curioso: Cloudflare (delante de Render) bloquea la inyección SQL con 403, y además una prueba unitaria demuestra que la app por sí sola no es vulnerable. Bandit encontró 3 hallazgos medios que se corrigieron.");

// ================================================================ 14. Usabilidad
s = contenido("Usabilidad: escritorio y celular", "Calidad");
imagen(s, "capturas/e19_movil_espacios.png", 0.6, 1.35, 2.75, 5.5, "Vista móvil de espacios");
imagen(s, "capturas/e20_movil_mis_reservas.png", 3.55, 1.35, 2.75, 5.5, "Vista móvil de mis reservas");
vinetas(s, [
  "Evaluación heurística de Nielsen: sin problemas graves",
  "Diseño responsivo: tablas → tarjetas, sin desborde (probado en E2E)",
  "Componentes propios: dropdowns, diálogos, mostrar contraseña",
  "Mensajes que explican el porqué (\"hay clase de Programación I\")",
  "Prueba SUS con 5 usuarios: protocolo listo (meta ≥ 68)",
], { x: 6.7, y: 1.6, w: 6.0, h: 5.0 });
s.addNotes("Mostrar el celular. Las mejoras de usabilidad salieron de revisiones: se corrigieron desbordes, se reemplazaron los controles genéricos del navegador. Ser honestos: la prueba SUS con usuarios queda planificada con su protocolo.");

// ================================================================ 15. Despliegue
pres.addSection({ title: "Cierre" });
s = contenido("Despliegue y operación", "Cierre");
imagen(s, "diagramas/04_despliegue.png", 0.6, 1.35, 12.1, 3.75, "Diagrama de despliegue");
vinetas(s, ["Infraestructura como código: render.yaml", "Local completo: docker compose up --build", "Secretos solo en variables de entorno"], { x: 0.6, y: 5.3, w: 6.0, h: 1.5 });
vinetas(s, ["Correo por API HTTP (Render bloquea SMTP)", "Cron de GitHub Actions mantiene vivo el programador", "Health checks y reinicio automático"], { x: 6.8, y: 5.3, w: 5.9, h: 1.5 });
s.addNotes("Explicar las decisiones forzadas por el plan gratuito: SMTP bloqueado → Brevo por HTTP; servicios que duermen → cron cada 10 minutos y despertar al consumidor al publicar eventos.");

// ================================================================ 16. Lecciones
s = contenido("Lecciones aprendidas y siguientes pasos", "Cierre");
tarjeta(s, { x: 0.6, y: 1.55, w: 5.95, h: 5.1, icono: "💡", titulo: "Aprendimos", color: C.accent3, nombre: "l1", tam: 19,
  texto: "• Probar con la misma base de datos que producción (PostgreSQL)\n• Medir antes de optimizar: k6 mostró el N+1\n• Un chatbot confiable responde con datos reales\n• Diseñar para fallas: el negocio sigue si cae Redis o la IA" });
tarjeta(s, { x: 6.8, y: 1.55, w: 5.95, h: 5.1, icono: "🚀", titulo: "Siguientes pasos", color: C.accent1, nombre: "l2", tam: 19,
  texto: "• Plan con más CPU o réplicas; caché de /espacios\n• JWT con llaves asimétricas (RS256)\n• Límite de peticiones por usuario además de por IP\n• Aplicar la prueba SUS con estudiantes\n• Respaldos automáticos de la base de datos" });
s.addNotes("Cerrar con aprendizajes concretos y el plan de mitigación pendiente del informe de pruebas.");

// ================================================================ 17. Gracias
s = pres.addSlide({ masterName: "Portada", sectionTitle: "Cierre" });
s.addText("¡Gracias!", { placeholder: "title" });
s.addText("¿Preguntas?", { placeholder: "body" });
[["Aplicación", "reservacampus-web-gcr3.onrender.com", "https://reservacampus-web-gcr3.onrender.com"],
 ["Repositorio", "github.com/Camilo1408/reservacampus", "https://github.com/Camilo1408/reservacampus"],
 ["API", "reservacampus-reservas-gcr3.onrender.com/docs", "https://reservacampus-reservas-gcr3.onrender.com/docs"]].forEach(([k, v, url], i) => {
  s.addText([{ text: k + ": ", options: { bold: true, color: C.accent2 } }, { text: v, options: { color: C.background1, hyperlink: { url } } }],
    { x: 0.8, y: 5.3 + i * 0.45, w: 11.7, h: 0.4, fontSize: 16, isTextBox: true, margin: 0, objectName: `enlace${i}` });
});
s.addNotes("Agradecer y abrir preguntas. Tener a mano el Informe de Pruebas y el Manual Técnico por si preguntan detalles.");

(async () => {
  await pres.writeFile({ fileName: SALIDA });
  await applyTheme(SALIDA, THEME);
  console.log("pptx:", SALIDA);
})();
