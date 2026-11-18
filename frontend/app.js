/* ReservaCampus - frontend (JavaScript sin frameworks) */
const C = window.CONFIG;
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);
const TIPOS = { sala_estudio: "Sala de estudio", laboratorio: "Laboratorio", auditorio: "Auditorio", cancha: "Cancha" };

const estado = {
  token: sessionStorage.getItem("token"),
  usuario: JSON.parse(sessionStorage.getItem("usuario") || "null"),
  espacios: [],
  espacioSel: null,
  historialChat: [],
};

// ---------------------------------------------------------------- utilidades
const hoyISO = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};
const escapar = (t) => String(t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const hhmm = (t) => t.slice(0, 5);
const aMin = (t) => +t.slice(0, 2) * 60 + +t.slice(3, 5);
const deMin = (m) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
const fechaLarga = (f) => new Date(f + "T12:00:00").toLocaleDateString("es-CO", { weekday: "long", day: "numeric", month: "long" });

function toast(msg, error = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast visible" + (error ? " error" : "");
  clearTimeout(t._t);
  t._t = setTimeout(() => (t.className = "toast"), 3500);
}

async function api(base, ruta, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && estado.token) headers.Authorization = `Bearer ${estado.token}`;
  const r = await fetch(base + ruta, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (r.status === 401 && auth && estado.token) { cerrarSesion(); throw new Error("Tu sesión expiró. Inicia sesión de nuevo."); }
  const datos = r.status === 204 ? null : await r.json().catch(() => null);
  if (!r.ok) {
    let msg = datos?.detail || `Error ${r.status}`;
    if (Array.isArray(msg)) msg = msg.map((e) => e.msg.replace("Value error, ", "")).join(". ");
    throw new Error(msg);
  }
  return datos;
}

// ---------------------------------------------------------------- sesión
function guardarSesion(token, usuario) {
  estado.token = token; estado.usuario = usuario;
  sessionStorage.setItem("token", token);
  sessionStorage.setItem("usuario", JSON.stringify(usuario));
}
function cerrarSesion() {
  estado.token = null; estado.usuario = null;
  sessionStorage.clear();
  pintarSesion();
}
function pintarSesion() {
  const dentro = !!estado.token;
  $("#vista-auth").classList.toggle("oculto", dentro);
  ["#nav", "#btn-salir", "#btn-notif"].forEach((s) => $(s).classList.toggle("oculto", !dentro));
  $("#usuario-nombre").textContent = dentro ? `Hola, ${estado.usuario.nombre.split(" ")[0]}` : "";
  $$(".solo-admin").forEach((e) => e.classList.toggle("oculto", estado.usuario?.rol !== "admin"));
  if (dentro) { mostrarVista("espacios"); cargarNotificaciones(); }
  else $$("main.vista").forEach((v) => v.id !== "vista-auth" && v.classList.add("oculto"));
}

$$(".tab").forEach((b) => b.addEventListener("click", () => {
  $$(".tab").forEach((t) => t.classList.toggle("activo", t === b));
  $("#form-login").classList.toggle("oculto", b.dataset.tab !== "login");
  $("#form-registro").classList.toggle("oculto", b.dataset.tab !== "registro");
  $("#auth-error").textContent = "";
}));

$("#form-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    const r = await api(C.AUTH_URL, "/login", { method: "POST", auth: false, body: Object.fromEntries(f) });
    guardarSesion(r.access_token, r.usuario);
    pintarSesion();
    toast(`Bienvenido, ${r.usuario.nombre}`);
  } catch (err) { $("#auth-error").textContent = err.message; }
});

$("#form-registro").addEventListener("submit", async (e) => {
  e.preventDefault();
  const datos = Object.fromEntries(new FormData(e.target));
  try {
    await api(C.AUTH_URL, "/registro", { method: "POST", auth: false, body: datos });
    const r = await api(C.AUTH_URL, "/login", { method: "POST", auth: false, body: { email: datos.email, password: datos.password } });
    guardarSesion(r.access_token, r.usuario);
    pintarSesion();
    toast("¡Cuenta creada! Ya puedes reservar.");
  } catch (err) { $("#auth-error").textContent = err.message; }
});
$("#btn-salir").addEventListener("click", cerrarSesion);

// ---------------------------------------------------------------- navegación
function mostrarVista(nombre) {
  $$("main.vista").forEach((v) => v.classList.toggle("oculto", v.id !== `vista-${nombre}`));
  $$(".nav button").forEach((b) => b.classList.toggle("activo", b.dataset.vista === nombre));
  if (nombre === "espacios") cargarEspacios();
  if (nombre === "mis-reservas") cargarMisReservas();
  if (nombre === "admin") cargarAdmin();
}
$$("[data-vista]").forEach((b) => b.addEventListener("click", (e) => { e.preventDefault(); if (estado.token) mostrarVista(b.dataset.vista); }));

// ---------------------------------------------------------------- espacios
$("#filtro-fecha").value = hoyISO();
$("#filtro-fecha").min = hoyISO();
$("#filtro-fecha").addEventListener("change", cargarEspacios);
$("#filtro-tipo").addEventListener("change", cargarEspacios);

async function cargarEspacios() {
  const grid = $("#grid-espacios");
  grid.innerHTML = `<p class="vacio">Cargando espacios…</p>`;
  try {
    const fecha = $("#filtro-fecha").value || hoyISO();
    const tipo = $("#filtro-tipo").value;
    const disp = await api(C.RESERVAS_URL, `/disponibilidad?fecha=${fecha}${tipo ? `&tipo=${tipo}` : ""}`, { auth: false });
    estado.espacios = disp.map((d) => d.espacio);
    if (!disp.length) { grid.innerHTML = `<p class="vacio">No hay espacios de este tipo.</p>`; return; }
    grid.innerHTML = disp.map(({ espacio: e, ocupado }) => {
      const ini = aMin(e.hora_apertura), fin = aMin(e.hora_cierre), total = fin - ini;
      const bloques = ocupado.map((o) => {
        const izq = ((aMin(o.hora_inicio) - ini) / total) * 100, ancho = ((aMin(o.hora_fin) - aMin(o.hora_inicio)) / total) * 100;
        return `<span class="${o.tipo === "clase" ? "clase-b" : ""}" style="left:${izq}%;width:${ancho}%" title="${hhmm(o.hora_inicio)}-${hhmm(o.hora_fin)} ${escapar(o.etiqueta || "")}"></span>`;
      }).join("");
      return `<article class="tarjeta espacio">
        <div class="espacio-cab"><h3>${escapar(e.nombre)}</h3><span class="chip ${e.tipo}">${TIPOS[e.tipo]}</span></div>
        <div class="meta"><span>👥 ${e.capacidad} personas</span><span>📍 ${escapar(e.ubicacion)}</span></div>
        <p class="desc">${escapar(e.descripcion || "")}</p>
        <div><div class="barra-dia">${bloques}</div>
          <div class="leyenda"><span>${hhmm(e.hora_apertura)}</span><span>${ocupado.length ? `${ocupado.filter((o) => o.tipo === "clase").length} clase(s) · ${ocupado.filter((o) => o.tipo !== "clase").length} reserva(s)` : "Libre todo el día"}</span><span>${hhmm(e.hora_cierre)}</span></div></div>
        <button class="btn primario" data-reservar="${e.id}">Reservar</button>
      </article>`;
    }).join("");
    $$("[data-reservar]").forEach((b) => b.addEventListener("click", () => abrirModal(+b.dataset.reservar)));
  } catch (err) { grid.innerHTML = `<p class="vacio">No se pudieron cargar los espacios: ${escapar(err.message)}</p>`; }
}

// ---------------------------------------------------------------- modal reserva
const modal = $("#modal-reserva");
const formR = $("#form-reserva");

function opcionesHora(e) {
  const ini = aMin(e.hora_apertura), fin = aMin(e.hora_cierre);
  const desde = [], hasta = [];
  for (let m = ini; m < fin; m += 30) desde.push(deMin(m));
  for (let m = ini + 30; m <= fin; m += 30) hasta.push(deMin(m));
  formR.hora_inicio.innerHTML = desde.map((h) => `<option>${h}</option>`).join("");
  formR.hora_fin.innerHTML = hasta.map((h) => `<option>${h}</option>`).join("");
  formR.hora_fin.selectedIndex = Math.min(1, hasta.length - 1);
}

async function pintarOcupacionModal() {
  const e = estado.espacioSel, fecha = formR.fecha.value;
  const box = $("#ocupacion-modal");
  try {
    const occ = await api(C.RESERVAS_URL, `/espacios/${e.id}/ocupacion?fecha=${fecha}`, { auth: false });
    box.innerHTML = occ.length
      ? `<b>Ocupado ese día:</b> ${occ.map((o) => `${hhmm(o.hora_inicio)}–${hhmm(o.hora_fin)}${o.tipo === "clase" ? ` (clase: ${escapar(o.etiqueta)})` : ""}`).join(", ")}`
      : "✅ Este espacio no tiene reservas ese día.";
  } catch { box.textContent = ""; }
}

function abrirModal(id) {
  const e = estado.espacios.find((x) => x.id === id);
  estado.espacioSel = e;
  $("#modal-titulo").textContent = `Reservar ${e.nombre}`;
  $("#modal-detalle").textContent = `${TIPOS[e.tipo]} · ${e.capacidad} personas · ${e.ubicacion} · ${hhmm(e.hora_apertura)}–${hhmm(e.hora_cierre)}`;
  formR.fecha.value = $("#filtro-fecha").value || hoyISO();
  formR.fecha.min = hoyISO();
  formR.asistentes.max = e.capacidad;
  formR.asistentes.value = 1;
  formR.motivo.value = "";
  $("#reserva-error").textContent = "";
  opcionesHora(e);
  pintarOcupacionModal();
  modal.showModal();
}
formR.fecha.addEventListener("change", pintarOcupacionModal);
$("#cerrar-modal").addEventListener("click", () => modal.close());

formR.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const d = Object.fromEntries(new FormData(formR));
  try {
    const r = await api(C.RESERVAS_URL, "/reservas", { method: "POST", body: { ...d, espacio_id: estado.espacioSel.id, asistentes: +d.asistentes } });
    modal.close();
    toast(`Reserva confirmada: ${r.espacio_nombre}, ${hhmm(r.hora_inicio)}–${hhmm(r.hora_fin)}`);
    cargarEspacios();
    setTimeout(cargarNotificaciones, 1500);
  } catch (err) { $("#reserva-error").textContent = err.message; }
});

// ---------------------------------------------------------------- mis reservas
async function cargarMisReservas() {
  const cont = $("#lista-mis-reservas");
  cont.innerHTML = `<p class="vacio">Cargando…</p>`;
  try {
    const rs = await api(C.RESERVAS_URL, "/reservas/mias");
    if (!rs.length) { cont.innerHTML = `<div class="tarjeta vacio">Aún no tienes reservas. ¡Explora los espacios!</div>`; return; }
    const hoy = hoyISO();
    cont.innerHTML = rs.map((r) => `
      <article class="tarjeta reserva">
        <div><h3>${escapar(r.espacio_nombre)}</h3>
          <p class="sub">${fechaLarga(r.fecha)} · ${hhmm(r.hora_inicio)}–${hhmm(r.hora_fin)} · ${r.asistentes} asistente(s)${r.motivo ? " · " + escapar(r.motivo) : ""}</p>
          ${r.motivo_revocacion ? `<span class="motivo">Revocada por la administración: ${escapar(r.motivo_revocacion)}</span>` : ""}</div>
        <div style="display:flex;gap:.6rem;align-items:center">
          <span class="estado ${r.estado}">${r.estado}</span>
          ${r.estado === "confirmada" && r.fecha >= hoy ? `<button class="btn peligro" data-cancelar="${r.id}">Cancelar</button>` : ""}
        </div>
      </article>`).join("");
    $$("[data-cancelar]").forEach((b) => b.addEventListener("click", () => cancelar(+b.dataset.cancelar, cargarMisReservas)));
  } catch (err) { cont.innerHTML = `<p class="vacio">${escapar(err.message)}</p>`; }
}

async function cancelar(id, luego) {
  if (!(await UI.confirmar({ titulo: "Cancelar reserva", mensaje: "El horario quedará libre para otras personas. Esta acción no se puede deshacer.",
    aceptar: "Sí, cancelar", cancelar: "Volver", peligro: true }))) return;
  try {
    await api(C.RESERVAS_URL, `/reservas/${id}/cancelar`, { method: "POST" });
    toast("Reserva cancelada");
    luego();
    setTimeout(cargarNotificaciones, 1500);
  } catch (err) { toast(err.message, true); }
}

// ---------------------------------------------------------------- admin
const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const admin = { sub: "reservas", espacios: [], reservas: [], horarios: [] };
const cerrarModales = () => $$("dialog[open]").forEach((d) => d.close());
$$("[data-cerrar]").forEach((b) => b.addEventListener("click", cerrarModales));
const errorEn = (form, msg) => (form.querySelector(".error").textContent = msg || "");

$$(".subtab").forEach((b) => b.addEventListener("click", () => {
  admin.sub = b.dataset.sub;
  $$(".subtab").forEach((t) => t.classList.toggle("activo", t === b));
  ["reservas", "espacios", "horarios"].forEach((n) => $(`#sub-${n}`).classList.toggle("oculto", n !== admin.sub));
  cargarAdmin();
}));

async function cargarAdmin() {
  try {
    const st = await api(C.RESERVAS_URL, "/estadisticas");
    $("#stats").innerHTML = [
      [st.confirmadas, "Reservas activas"], [st.revocadas, "Revocadas"], [st.canceladas, "Canceladas"],
      [st.espacios_activos, "Espacios activos"], [st.horarios_clase, "Bloques de clase"],
    ].map(([n, t]) => `<div class="tarjeta stat"><b>${n}</b><span>${t}</span></div>`).join("");
    admin.espacios = await api(C.RESERVAS_URL, "/admin/espacios");
    if (admin.sub === "reservas") await cargarReservasAdmin();
    if (admin.sub === "espacios") pintarEspaciosAdmin();
    if (admin.sub === "horarios") await cargarHorarios();
  } catch (err) { toast(err.message, true); }
}

// ----- reservas
$("#filtro-estado").addEventListener("change", cargarReservasAdmin);
$("#filtro-fecha-admin").addEventListener("change", cargarReservasAdmin);
async function cargarReservasAdmin() {
  const q = new URLSearchParams();
  if ($("#filtro-estado").value) q.set("estado", $("#filtro-estado").value);
  if ($("#filtro-fecha-admin").value) q.set("fecha", $("#filtro-fecha-admin").value);
  admin.reservas = await api(C.RESERVAS_URL, `/reservas?${q}`);
  const hoy = hoyISO();
  $("#tabla-reservas tbody").innerHTML = admin.reservas.map((r) => `<tr>
      <td data-label="Espacio">${escapar(r.espacio_nombre)}</td>
      <td data-label="Usuario"><span>${escapar(r.usuario_nombre)}<br><small>${escapar(r.usuario_email)}</small></span></td>
      <td data-label="Fecha">${r.fecha}</td>
      <td data-label="Horario">${hhmm(r.hora_inicio)}–${hhmm(r.hora_fin)}</td>
      <td data-label="Estado"><span><span class="estado ${r.estado}">${r.estado}</span>${r.motivo_revocacion ? `<span class="motivo">${escapar(r.motivo_revocacion)}</span>` : ""}</span></td>
      <td class="acc">${r.estado === "confirmada" && r.fecha >= hoy ? `<button class="btn-mini rojo" data-revocar="${r.id}">Revocar</button>` : ""}</td></tr>`).join("")
    || `<tr><td colspan="6" class="vacio">No hay reservas con esos filtros</td></tr>`;
  $$("[data-revocar]").forEach((b) => b.addEventListener("click", () => abrirRevocar(+b.dataset.revocar)));
}

let reservaARevocar = null;
function abrirRevocar(id) {
  const r = admin.reservas.find((x) => x.id === id);
  reservaARevocar = id;
  $("#detalle-revocar").textContent = r
    ? `${r.espacio_nombre} · ${r.fecha} · ${hhmm(r.hora_inicio)}–${hhmm(r.hora_fin)} · ${r.usuario_nombre} (${r.usuario_email})`
    : `Reserva #${id}`;
  $("#form-revocar").reset();
  errorEn($("#form-revocar"));
  $("#modal-revocar").showModal();
}
$("#form-revocar").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api(C.RESERVAS_URL, `/reservas/${reservaARevocar}/revocar`, { method: "POST", body: { justificacion: e.target.justificacion.value.trim() } });
    cerrarModales();
    toast("Reserva revocada. Se notificó al usuario.");
    cargarAdmin();
  } catch (err) { errorEn(e.target, err.message); }
});

// ----- espacios
function pintarEspaciosAdmin() {
  $("#tabla-espacios tbody").innerHTML = admin.espacios.map((e) => `<tr>
      <td data-label="Nombre"><b>${escapar(e.nombre)}</b></td>
      <td data-label="Tipo">${TIPOS[e.tipo]}</td>
      <td data-label="Capacidad">${e.capacidad}</td>
      <td data-label="Ubicación">${escapar(e.ubicacion)}</td>
      <td data-label="Horario">${hhmm(e.hora_apertura)}–${hhmm(e.hora_cierre)}</td>
      <td data-label="Estado"><span class="estado ${e.activo ? "activo" : "inactivo"}">${e.activo ? "Habilitado" : "Deshabilitado"}</span></td>
      <td class="acc"><div class="acciones-fila">
        <button class="btn-mini" data-editar="${e.id}">Editar</button>
        <button class="btn-mini" data-toggle="${e.id}">${e.activo ? "Deshabilitar" : "Habilitar"}</button>
        <button class="btn-mini rojo" data-eliminar="${e.id}">Eliminar</button></div></td></tr>`).join("");
  $$("[data-editar]").forEach((b) => b.addEventListener("click", () => abrirEspacio(+b.dataset.editar)));
  $$("[data-toggle]").forEach((b) => b.addEventListener("click", () => toggleEspacio(+b.dataset.toggle)));
  $$("[data-eliminar]").forEach((b) => b.addEventListener("click", () => eliminarEspacio(+b.dataset.eliminar)));
}

let espacioEditando = null;
function abrirEspacio(id = null) {
  const f = $("#form-espacio");
  f.reset();
  errorEn(f);
  espacioEditando = id;
  $("#titulo-espacio").textContent = id ? "Editar espacio" : "Nuevo espacio";
  if (id) {
    const e = admin.espacios.find((x) => x.id === id);
    ["nombre", "tipo", "capacidad", "ubicacion", "descripcion"].forEach((k) => (f[k].value = e[k] ?? ""));
    f.hora_apertura.value = hhmm(e.hora_apertura);
    f.hora_cierre.value = hhmm(e.hora_cierre);
    f.activo.checked = e.activo;
  }
  $("#modal-espacio").showModal();
}
$("#btn-nuevo-espacio").addEventListener("click", () => abrirEspacio());
$("#form-espacio").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const body = {
    nombre: f.nombre.value, tipo: f.tipo.value, capacidad: +f.capacidad.value, ubicacion: f.ubicacion.value,
    descripcion: f.descripcion.value, hora_apertura: f.hora_apertura.value, hora_cierre: f.hora_cierre.value, activo: f.activo.checked,
  };
  try {
    await api(C.RESERVAS_URL, espacioEditando ? `/espacios/${espacioEditando}` : "/espacios", { method: espacioEditando ? "PUT" : "POST", body });
    cerrarModales();
    toast(espacioEditando ? "Espacio actualizado" : "Espacio creado");
    cargarAdmin();
  } catch (err) { errorEn(f, err.message); }
});
async function toggleEspacio(id) {
  const e = admin.espacios.find((x) => x.id === id);
  try {
    await api(C.RESERVAS_URL, `/espacios/${id}/estado`, { method: "PATCH", body: { activo: !e.activo } });
    toast(e.activo ? "Espacio deshabilitado: ya no aparece para reservar" : "Espacio habilitado");
    cargarAdmin();
  } catch (err) { toast(err.message, true); }
}
async function eliminarEspacio(id) {
  const e = admin.espacios.find((x) => x.id === id);
  if (!(await UI.confirmar({ titulo: `Eliminar "${e.nombre}"`, mensaje: "Se borrarán el espacio, su historial de reservas y sus horarios de clase. Si solo quieres ocultarlo, usa Deshabilitar.",
    aceptar: "Eliminar", peligro: true }))) return;
  try {
    await api(C.RESERVAS_URL, `/espacios/${id}`, { method: "DELETE" });
    toast("Espacio eliminado");
    cargarAdmin();
  } catch (err) { toast(err.message, true); }
}

// ----- horarios de clase
const selEspHorario = $("#filtro-espacio-horario");
selEspHorario.addEventListener("change", cargarHorarios);
function opcionesEspacios(select, conTodos) {
  const actual = select.value;
  select.innerHTML = (conTodos ? `<option value="">Todos los espacios</option>` : "") +
    admin.espacios.map((e) => `<option value="${e.id}">${escapar(e.nombre)}</option>`).join("");
  if ([...select.options].some((o) => o.value === actual)) select.value = actual;
}
async function cargarHorarios() {
  opcionesEspacios(selEspHorario, true);
  const id = selEspHorario.value;
  admin.horarios = await api(C.RESERVAS_URL, `/horarios${id ? `?espacio_id=${id}` : ""}`, { auth: false });
  $("#semana").innerHTML = DIAS.map((d, i) => {
    const clases = admin.horarios.filter((h) => h.dia_semana === i);
    return `<div class="dia"><h4>${d}</h4>${clases.map((h) => `<button class="clase" data-horario="${h.id}">
        <b>${hhmm(h.hora_inicio)}–${hhmm(h.hora_fin)}</b>${escapar(h.materia)}${id ? "" : `<br><small>${escapar(h.espacio_nombre)}</small>`}
      </button>`).join("") || `<small class="sub">Sin clases</small>`}</div>`;
  }).join("");
  $$("[data-horario]").forEach((b) => b.addEventListener("click", () => abrirHorario(+b.dataset.horario)));
}

let horarioEditando = null;
function abrirHorario(id = null) {
  const f = $("#form-horario");
  f.reset();
  errorEn(f);
  opcionesEspacios(f.espacio_id, false);
  horarioEditando = id;
  $("#titulo-horario").textContent = id ? "Editar clase" : "Agregar clase";
  $("#btn-borrar-horario").classList.toggle("oculto", !id);
  if (id) {
    const h = admin.horarios.find((x) => x.id === id);
    ["espacio_id", "dia_semana", "materia", "docente"].forEach((k) => (f[k].value = h[k]));
    f.hora_inicio.value = hhmm(h.hora_inicio);
    f.hora_fin.value = hhmm(h.hora_fin);
    f.vigente_desde.value = h.vigente_desde || "";
    f.vigente_hasta.value = h.vigente_hasta || "";
  } else if (selEspHorario.value) f.espacio_id.value = selEspHorario.value;
  $("#modal-horario").showModal();
}
$("#btn-nuevo-horario").addEventListener("click", () => abrirHorario());
$("#form-horario").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const body = {
    espacio_id: +f.espacio_id.value, dia_semana: +f.dia_semana.value, materia: f.materia.value, docente: f.docente.value,
    hora_inicio: f.hora_inicio.value, hora_fin: f.hora_fin.value,
    vigente_desde: f.vigente_desde.value || null, vigente_hasta: f.vigente_hasta.value || null,
  };
  try {
    const r = await api(C.RESERVAS_URL, horarioEditando ? `/horarios/${horarioEditando}` : "/horarios", { method: horarioEditando ? "PUT" : "POST", body });
    cerrarModales();
    toast("Horario guardado");
    mostrarResultado(r);
    cargarAdmin();
  } catch (err) { errorEn(f, err.message); }
});
$("#btn-borrar-horario").addEventListener("click", async () => {
  if (!(await UI.confirmar({ titulo: "Eliminar clase", mensaje: "El espacio quedará disponible para reservas en esa franja.",
    aceptar: "Eliminar", peligro: true }))) return;
  try {
    await api(C.RESERVAS_URL, `/horarios/${horarioEditando}`, { method: "DELETE" });
    cerrarModales();
    toast("Clase eliminada");
    cargarAdmin();
  } catch (err) { toast(err.message, true); }
});

// ----- carga CSV
function parsearCSV(texto) {
  const lineas = texto.replace(/^﻿/, "").split(/\r?\n/).filter((l) => l.trim());
  if (!lineas.length) throw new Error("El archivo está vacío");
  const sep = (lineas[0].match(/;/g) || []).length > (lineas[0].match(/,/g) || []).length ? ";" : ",";
  const celdas = (l) => {
    const out = []; let cur = "", q = false;
    for (const ch of l) {
      if (ch === '"') q = !q;
      else if (ch === sep && !q) { out.push(cur.trim()); cur = ""; }
      else cur += ch;
    }
    out.push(cur.trim());
    return out;
  };
  const cab = celdas(lineas[0]).map((c) => c.toLowerCase());
  const faltan = ["espacio", "dia", "hora_inicio", "hora_fin", "materia"].filter((c) => !cab.includes(c));
  if (faltan.length) throw new Error(`Faltan columnas en el encabezado: ${faltan.join(", ")}`);
  return lineas.slice(1).map((l) => {
    const v = celdas(l);
    return Object.fromEntries(["espacio", "dia", "hora_inicio", "hora_fin", "materia", "docente"]
      .map((k) => [k, cab.includes(k) ? v[cab.indexOf(k)] ?? "" : ""]));
  });
}
function mostrarResultado(r) {
  const box = $("#resultado-csv");
  let html = "";
  if (r.errores?.length) html += `<div class="aviso mal"><b>No se cargó nada. Revisa:</b><ul>${r.errores.map((e) => `<li>${escapar(e)}</li>`).join("")}</ul></div>`;
  else if (r.creados) html += `<div class="aviso ok">✅ ${r.creados} bloque(s) de clase cargados.</div>`;
  if (r.conflictos?.length) {
    html += `<div class="aviso alerta"><b>⚠️ ${r.conflictos.length} reserva(s) chocan con las clases.</b> Puedes revocarlas:<ul>${r.conflictos.map((c) =>
      `<li>${escapar(c.espacio)} · ${c.fecha} ${hhmm(c.hora_inicio)}–${hhmm(c.hora_fin)} · ${escapar(c.usuario_nombre)}
        <button class="btn-mini rojo" data-revocar-c="${c.reserva_id}">Revocar</button></li>`).join("")}</ul></div>`;
  }
  box.innerHTML = html;
  $$("[data-revocar-c]").forEach((b) => b.addEventListener("click", () => {
    abrirRevocar(+b.dataset.revocarC);
    $("#form-revocar").justificacion.value = "El espacio fue asignado a un horario de clase fijo en esa franja.";
  }));
}
$("#form-csv").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  try {
    const filas = parsearCSV(await f.archivo.files[0].text());
    if (!filas.length) throw new Error("El archivo no tiene filas de datos");
    const r = await api(C.RESERVAS_URL, "/horarios/carga", { method: "POST", body: {
      filas, reemplazar: f.reemplazar.checked, vigente_desde: f.vigente_desde.value || null, vigente_hasta: f.vigente_hasta.value || null,
    } });
    mostrarResultado(r);
    if (r.creados) { toast(`${r.creados} clases cargadas`); f.reset(); cargarAdmin(); }
  } catch (err) { mostrarResultado({ errores: [err.message] }); }
});
$("#btn-plantilla").addEventListener("click", () => {
  const csv = "espacio,dia,hora_inicio,hora_fin,materia,docente\n" +
    "Laboratorio de Cómputo 1,lunes,08:00,10:00,Programación I,Ing. Laura Gómez\n" +
    "Laboratorio de Redes,miercoles,10:00,12:00,Redes de Computadores,Ing. Paula Díaz\n" +
    "Sala de Estudio B-201,jueves,14:00,16:00,Tutoría de Cálculo,Monitoría\n";
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
  a.download = "plantilla_horarios.csv";
  a.click();
});

// ---------------------------------------------------------------- notificaciones
async function cargarNotificaciones() {
  if (!estado.token) return;
  try {
    const ns = await api(C.NOTIF_URL, "/notificaciones");
    const nuevas = ns.filter((n) => !n.leida).length;
    $("#notif-badge").textContent = nuevas;
    $("#notif-badge").classList.toggle("oculto", !nuevas);
    $("#lista-notif").innerHTML = ns.length
      ? ns.map((n) => `<li class="${n.leida ? "" : "nueva"}"><b>${escapar(n.titulo)}</b><br>${escapar(n.mensaje)}
          <small>${new Date(n.creada_en).toLocaleString("es-CO")}${n.correo_enviado ? " · 📧 enviado por correo" : ""}</small></li>`).join("")
      : `<li class="vacio">Sin notificaciones</li>`;
  } catch { /* el servicio puede estar despertando */ }
}
$("#btn-notif").addEventListener("click", (e) => { e.stopPropagation(); $("#panel-notif").classList.toggle("oculto"); cargarNotificaciones(); });
document.addEventListener("click", (e) => { if (!$("#panel-notif").contains(e.target)) $("#panel-notif").classList.add("oculto"); });
$("#leer-todas").addEventListener("click", async () => { await api(C.NOTIF_URL, "/notificaciones/leer-todas", { method: "POST" }); cargarNotificaciones(); });
setInterval(cargarNotificaciones, 20000);

// ---------------------------------------------------------------- chat
const chatBox = $("#chat-mensajes");
function agregarMsg(texto, rol, fuente) {
  const div = document.createElement("div");
  div.className = `msg ${rol}`;
  // Texto seguro (sin innerHTML) + soporte de **negritas**
  texto.split(/(\*\*[^*]+\*\*)/).forEach((p) => {
    if (p.startsWith("**") && p.endsWith("**")) { const b = document.createElement("b"); b.textContent = p.slice(2, -2); div.append(b); }
    else div.append(document.createTextNode(p));
  });
  if (fuente) { const s = document.createElement("span"); s.className = "fuente"; s.textContent = { reglas: "⚙️ respuesta por reglas", ia: "✨ respuesta con IA", respaldo: "ℹ️ respuesta de respaldo" }[fuente]; div.append(s); }
  chatBox.append(div);
  chatBox.scrollTop = chatBox.scrollHeight;
  return div;
}
function sugerencias(lista) {
  const c = $("#chat-sugerencias");
  c.innerHTML = "";
  (lista || []).forEach((s) => { const b = document.createElement("button"); b.textContent = s; b.onclick = () => enviarChat(s); c.append(b); });
}
async function enviarChat(texto) {
  agregarMsg(texto, "user");
  sugerencias([]);
  const esperando = agregarMsg("Escribiendo…", "bot escribiendo");
  try {
    const headers = { "Content-Type": "application/json" };
    if (estado.token) headers.Authorization = `Bearer ${estado.token}`;
    const r = await fetch(C.CHAT_URL + "/chat", { method: "POST", headers, body: JSON.stringify({ mensaje: texto, historial: estado.historialChat.slice(-6) }) });
    const d = await r.json();
    esperando.remove();
    if (!r.ok) throw new Error(d.detail || "Error del asistente");
    agregarMsg(d.respuesta, "bot", d.fuente);
    sugerencias(d.sugerencias);
    estado.historialChat.push({ rol: "user", texto }, { rol: "assistant", texto: d.respuesta });
  } catch (err) {
    esperando.remove();
    agregarMsg(typeof err.message === "string" ? err.message : "El asistente no está disponible ahora.", "bot", "respaldo");
  }
}
$("#chat-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const t = $("#chat-input").value.trim();
  if (t) { $("#chat-input").value = ""; enviarChat(t); }
});
$("#chat-toggle").addEventListener("click", () => {
  const c = $("#chat");
  c.classList.toggle("oculto");
  if (!chatBox.children.length) {
    agregarMsg("¡Hola! 👋 Soy el asistente de ReservaCampus. Puedo decirte qué espacios están libres, mostrar tus reservas o resolver dudas.", "bot");
    sugerencias(["¿Qué espacios están libres hoy?", "¿Cómo reservo?", "Mis reservas", "¿Cuáles son las reglas?"]);
  }
  if (!c.classList.contains("oculto")) $("#chat-input").focus();
});
$("#chat-cerrar").addEventListener("click", () => $("#chat").classList.add("oculto"));

pintarSesion();
