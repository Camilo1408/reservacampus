// Generador de documentos Word (docx) con estilo uniforme para los entregables de ReservaCampus.
const fs = require("fs");
const path = require("path");
const D = require("docx");

const RAIZ = path.resolve(__dirname, "..", "..", "..");
const IMG = path.join(RAIZ, "docs", "img");
const AZUL = "3B4CCA", AZUL_OSC = "1B2A8A", GRIS = "5D6480", BORDE = "D9DEEC", FONDO = "F4F6FB";
const ANCHO = 9360; // Carta con márgenes de 1": 12240 - 2*1440

const URLS = {
  web: "https://reservacampus-web-gcr3.onrender.com",
  auth: "https://reservacampus-auth-gcr3.onrender.com",
  reservas: "https://reservacampus-reservas-gcr3.onrender.com",
  notif: "https://reservacampus-notificaciones-gcr3.onrender.com",
  chat: "https://reservacampus-chatbot-gcr3.onrender.com",
  repo: "https://github.com/Camilo1408/reservacampus",
  ci: "https://github.com/Camilo1408/reservacampus/actions",
};

// ---------------------------------------------------------------- texto con marcas en línea
// **negrita**, `código`, [texto](url)
function runs(texto, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;
  let ultimo = 0, m;
  while ((m = re.exec(texto))) {
    if (m.index > ultimo) out.push(new D.TextRun({ text: texto.slice(ultimo, m.index), ...base }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new D.TextRun({ text: t.slice(2, -2), bold: true, ...base }));
    else if (t.startsWith("`")) out.push(new D.TextRun({ text: t.slice(1, -1), font: "Consolas", size: 19, color: AZUL_OSC, shading: { type: D.ShadingType.CLEAR, fill: "EEF0FB", color: "auto" }, ...base }));
    else {
      const [, txt, url] = t.match(/\[([^\]]+)\]\(([^)]+)\)/);
      out.push(new D.ExternalHyperlink({ link: url, children: [new D.TextRun({ text: txt, style: "Hyperlink", ...base })] }));
    }
    ultimo = m.index + t.length;
  }
  if (ultimo < texto.length) out.push(new D.TextRun({ text: texto.slice(ultimo), ...base }));
  return out;
}

const p = (texto, op = {}) => new D.Paragraph({ children: runs(texto, op.run || {}), spacing: { after: 120, line: 288 }, alignment: op.centro ? D.AlignmentType.CENTER : op.justificar === false ? undefined : D.AlignmentType.JUSTIFIED, ...op.par });
const h1 = (t) => new D.Paragraph({ heading: D.HeadingLevel.HEADING_1, children: [new D.TextRun(t)], pageBreakBefore: true });
const h1SinSalto = (t) => new D.Paragraph({ heading: D.HeadingLevel.HEADING_1, children: [new D.TextRun(t)] });
const h2 = (t) => new D.Paragraph({ heading: D.HeadingLevel.HEADING_2, children: [new D.TextRun(t)] });
const h3 = (t) => new D.Paragraph({ heading: D.HeadingLevel.HEADING_3, children: [new D.TextRun(t)] });
const vineta = (texto, nivel = 0) => new D.Paragraph({ children: runs(texto), numbering: { reference: "vinetas", level: nivel }, spacing: { after: 60, line: 276 } });
const vinetas = (lista) => lista.map((x) => (Array.isArray(x) ? x.map((y) => vineta(y, 1)) : vineta(x))).flat();
let contadorPasos = 0;
function pasos(lista) {
  contadorPasos += 1;
  const ref = `pasos${contadorPasos}`;
  pasosRefs.push(ref);
  return lista.map((t) => new D.Paragraph({ children: runs(t), numbering: { reference: ref, level: 0 }, spacing: { after: 80, line: 276 } }));
}
const pasosRefs = [];
const salto = () => new D.Paragraph({ children: [new D.PageBreak()] });
const espacio = (n = 1) => Array.from({ length: n }, () => new D.Paragraph({ children: [] }));

// ---------------------------------------------------------------- imágenes
function imagen(ruta, pie, anchoPx = 600) {
  const abs = path.isAbsolute(ruta) ? ruta : path.join(IMG, ruta);
  const datos = fs.readFileSync(abs);
  const ancho = datos.readUInt32BE(16), alto = datos.readUInt32BE(20); // PNG IHDR
  const maxAlto = 620;
  let w = anchoPx, h = Math.round((alto / ancho) * anchoPx);
  if (h > maxAlto) { w = Math.round((maxAlto / h) * w); h = maxAlto; }
  const out = [new D.Paragraph({ alignment: D.AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: !!pie,
    children: [new D.ImageRun({ type: "png", data: datos, transformation: { width: w, height: h },
      altText: { title: pie || path.basename(ruta), description: pie || path.basename(ruta), name: path.basename(ruta) } })] })];
  if (pie) out.push(new D.Paragraph({ alignment: D.AlignmentType.CENTER, spacing: { after: 200 },
    children: [new D.TextRun({ text: pie, italics: true, size: 18, color: GRIS })] }));
  return out;
}

// ---------------------------------------------------------------- tablas
const bordes = { top: { style: D.BorderStyle.SINGLE, size: 4, color: BORDE }, bottom: { style: D.BorderStyle.SINGLE, size: 4, color: BORDE },
  left: { style: D.BorderStyle.SINGLE, size: 4, color: BORDE }, right: { style: D.BorderStyle.SINGLE, size: 4, color: BORDE } };
function tabla(encabezados, filas, anchos) {
  anchos = anchos || encabezados.map(() => Math.floor(ANCHO / encabezados.length));
  const total = anchos.reduce((a, b) => a + b, 0);
  const celda = (texto, i, enc, par) => new D.TableCell({
    width: { size: anchos[i], type: D.WidthType.DXA }, borders: bordes,
    shading: { type: D.ShadingType.CLEAR, fill: enc ? AZUL : par ? FONDO : "FFFFFF", color: "auto" },
    margins: { top: 70, bottom: 70, left: 110, right: 110 },
    children: String(texto).split("\n").map((linea) => new D.Paragraph({ spacing: { after: 0, line: 252 },
      children: runs(linea, enc ? { bold: true, color: "FFFFFF", size: 19 } : { size: 19 }) })),
  });
  return new D.Table({
    width: { size: total, type: D.WidthType.DXA }, columnWidths: anchos,
    rows: [new D.TableRow({ tableHeader: true, children: encabezados.map((e, i) => celda(e, i, true)) }),
      ...filas.map((f, j) => new D.TableRow({ cantSplit: true, children: f.map((c, i) => celda(c, i, false, j % 2 === 1)) }))],
  });
}

// Recuadro de nota/consejo/advertencia
function nota(texto, tipo = "nota") {
  const estilos = { nota: ["EEF0FB", AZUL, "ℹ️ "], consejo: ["E5F6EE", "17915A", "💡 "], alerta: ["FFF3E0", "B25E00", "⚠️ "], demo: ["F3E8FF", "7B2CBF", "🎤 "] };
  const [fondo, color, icono] = estilos[tipo];
  const lineas = Array.isArray(texto) ? texto : [texto];
  return new D.Table({
    width: { size: ANCHO, type: D.WidthType.DXA }, columnWidths: [ANCHO],
    rows: [new D.TableRow({ children: [new D.TableCell({
      width: { size: ANCHO, type: D.WidthType.DXA }, shading: { type: D.ShadingType.CLEAR, fill: fondo, color: "auto" },
      borders: { top: { style: D.BorderStyle.NONE, size: 0, color: "FFFFFF" }, bottom: { style: D.BorderStyle.NONE, size: 0, color: "FFFFFF" },
        right: { style: D.BorderStyle.NONE, size: 0, color: "FFFFFF" }, left: { style: D.BorderStyle.SINGLE, size: 24, color } },
      margins: { top: 100, bottom: 100, left: 180, right: 160 },
      children: lineas.map((l, i) => new D.Paragraph({ spacing: { after: i === lineas.length - 1 ? 0 : 80, line: 270 },
        children: i === 0 ? [new D.TextRun({ text: icono }), ...runs(l)] : runs(l) })),
    })] })],
  });
}
const sep = () => new D.Paragraph({ spacing: { after: 160 }, children: [] });

// Bloque de código
function codigo(texto, titulo) {
  const lineas = texto.replace(/\t/g, "    ").split("\n");
  const filas = [];
  if (titulo) filas.push(new D.Paragraph({ spacing: { after: 60 }, children: [new D.TextRun({ text: titulo, bold: true, size: 17, color: "C9D1FF", font: "Consolas" })] }));
  for (const l of lineas) filas.push(new D.Paragraph({ spacing: { after: 0, line: 240 }, children: [new D.TextRun({ text: l || " ", font: "Consolas", size: 17, color: "E8EAF6" })] }));
  return new D.Table({
    width: { size: ANCHO, type: D.WidthType.DXA }, columnWidths: [ANCHO],
    rows: [new D.TableRow({ cantSplit: lineas.length < 30, children: [new D.TableCell({
      width: { size: ANCHO, type: D.WidthType.DXA }, shading: { type: D.ShadingType.CLEAR, fill: "1E2235", color: "auto" },
      borders: { top: { style: D.BorderStyle.NONE, size: 0, color: "FFFFFF" }, bottom: { style: D.BorderStyle.NONE, size: 0, color: "FFFFFF" },
        left: { style: D.BorderStyle.NONE, size: 0, color: "FFFFFF" }, right: { style: D.BorderStyle.NONE, size: 0, color: "FFFFFF" } },
      margins: { top: 120, bottom: 120, left: 180, right: 160 }, children: filas })] })],
  });
}

// ---------------------------------------------------------------- portada
function portada({ titulo, subtitulo, entregable, version = "1.0" }) {
  const hoy = new Date().toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric" });
  return [
    ...espacio(3),
    new D.Paragraph({ alignment: D.AlignmentType.LEFT, children: [new D.TextRun({ text: "RESERVACAMPUS", bold: true, size: 26, color: AZUL, characterSpacing: 60 })] }),
    new D.Paragraph({ border: { bottom: { style: D.BorderStyle.SINGLE, size: 18, color: AZUL, space: 6 } }, spacing: { after: 300 }, children: [] }),
    new D.Paragraph({ spacing: { after: 200 }, children: [new D.TextRun({ text: titulo, bold: true, size: 56, color: "15192B" })] }),
    new D.Paragraph({ spacing: { after: 600 }, children: [new D.TextRun({ text: subtitulo, size: 28, color: GRIS })] }),
    tabla(["Campo", "Detalle"], [
      ["Proyecto", "Plataforma distribuida de reserva de espacios universitarios"],
      ["Asignatura", "Electiva de Ingeniería de Software II — Trabajo final"],
      ["Entregable", entregable],
      ["Aplicación desplegada", `[${URLS.web}](${URLS.web})`],
      ["Repositorio", `[${URLS.repo}](${URLS.repo})`],
      ["Versión / fecha", `${version} — ${hoy}`],
    ], [2600, 6760]),
  ];
}

function toc() {
  return [new D.Paragraph({ pageBreakBefore: true, children: [new D.TextRun({ text: "Contenido", bold: true, size: 32, color: "15192B" })], spacing: { after: 200 } }),
    new D.TableOfContents("Contenido", { hyperlink: true, headingStyleRange: "1-2" }),
    new D.Paragraph({ children: [new D.TextRun({ text: "Si el índice aparece vacío, en Word: clic derecho sobre él → Actualizar campos.", italics: true, size: 16, color: GRIS })] })];
}

// ---------------------------------------------------------------- documento
async function generar(nombreArchivo, tituloCorto, secciones) {
  const estiloTitulo = (size, color, before, after) => ({ run: { font: "Arial", size, bold: true, color }, paragraph: { spacing: { before, after }, keepNext: true, keepLines: true } });
  const numeracion = [{ reference: "vinetas", levels: [
    { level: 0, format: D.LevelFormat.BULLET, text: "•", alignment: D.AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } }, run: { color: AZUL } } },
    { level: 1, format: D.LevelFormat.BULLET, text: "◦", alignment: D.AlignmentType.LEFT, style: { paragraph: { indent: { left: 1080, hanging: 270 } } } }] },
    ...pasosRefs.map((ref) => ({ reference: ref, levels: [{ level: 0, format: D.LevelFormat.DECIMAL, text: "%1.", alignment: D.AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 360 } }, run: { bold: true, color: AZUL } } }] }))];
  const doc = new D.Document({
    creator: "Equipo ReservaCampus", title: tituloCorto, description: tituloCorto,
    styles: {
      default: { document: { run: { font: "Arial", size: 21, color: "1F2333" } } },
      paragraphStyles: [
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, ...estiloTitulo(34, AZUL_OSC, 240, 160), paragraph: { spacing: { before: 240, after: 160 }, keepNext: true, keepLines: true, outlineLevel: 0, border: { bottom: { style: D.BorderStyle.SINGLE, size: 8, color: AZUL, space: 4 } } } },
        { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, ...estiloTitulo(27, AZUL, 280, 120), paragraph: { spacing: { before: 280, after: 120 }, keepNext: true, keepLines: true, outlineLevel: 1 } },
        { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, ...estiloTitulo(23, "15192B", 200, 80), paragraph: { spacing: { before: 200, after: 80 }, keepNext: true, keepLines: true, outlineLevel: 2 } },
      ],
    },
    numbering: { config: numeracion },
    features: { updateFields: true },
    sections: [{
      properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1300, bottom: 1200, left: 1440, right: 1440, header: 600, footer: 600 } }, titlePage: true },
      headers: { default: new D.Header({ children: [new D.Paragraph({ border: { bottom: { style: D.BorderStyle.SINGLE, size: 4, color: BORDE, space: 4 } },
        children: [new D.TextRun({ text: "ReservaCampus · ", bold: true, size: 16, color: AZUL }), new D.TextRun({ text: tituloCorto, size: 16, color: GRIS })] })] }) },
      footers: { default: new D.Footer({ children: [new D.Paragraph({ alignment: D.AlignmentType.RIGHT,
        children: [new D.TextRun({ text: "Página ", size: 16, color: GRIS }), new D.TextRun({ children: [D.PageNumber.CURRENT], size: 16, color: GRIS }),
          new D.TextRun({ text: " de ", size: 16, color: GRIS }), new D.TextRun({ children: [D.PageNumber.TOTAL_PAGES], size: 16, color: GRIS })] })] }) },
      children: secciones.flat(Infinity),
    }],
  });
  const destino = path.join(RAIZ, "docs", "entregables", nombreArchivo);
  fs.mkdirSync(path.dirname(destino), { recursive: true });
  fs.writeFileSync(destino, await D.Packer.toBuffer(doc));
  console.log("docx:", destino);
}

const leerJSON = (rel) => JSON.parse(fs.readFileSync(path.join(RAIZ, rel), "utf8"));
module.exports = { D, URLS, RAIZ, p, h1, h1SinSalto, h2, h3, vineta, vinetas, pasos, salto, espacio, imagen, tabla, nota, sep, codigo, portada, toc, generar, leerJSON, ANCHO };
