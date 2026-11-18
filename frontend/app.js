/* ReservaCampus - frontend (JavaScript sin frameworks) */
const C = window.CONFIG;
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);
const TIPOS = { sala_estudio: "Sala de estudio", laboratorio: "Laboratorio", auditorio: "Auditorio", cancha: "Cancha", recreacion: "Sala recreativa" };

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
  estado.token = null; estado.usuario = null; estado.sanciones = [];
  sessionStorage.clear();
  $(".tab[data-tab=login]").click();  // volver siempre a "Iniciar sesión"
  $$("#vista-auth form").forEach((f) => f.reset());
  pintarSesion();
}
function pintarSesion() {
  const dentro = !!estado.token;
  $("#vista-auth").classList.toggle("oculto", dentro);
  ["#nav", "#btn-salir", "#btn-notif"].forEach((s) => $(s).classList.toggle("oculto", !dentro));
  $("#usuario-nombre").textContent = dentro ? `Hola, ${estado.usuario.nombre.split(" ")[0]}` : "";
  $$(".solo-admin").forEach((e) => e.classList.toggle("oculto", estado.usuario?.rol !== "admin"));
  if (dentro) { mostrarVista("espacios"); cargarNotificaciones(); cargarEstadoCuenta(); confirmarPendiente(); }
  else {
    $("#banner-sancion").classList.add("oculto");
    $$("main.vista").forEach((v) => v.id !== "vista-auth" && v.classList.add("oculto"));
  }
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
        ${e.actividades ? `<div class="tags">${e.actividades.split(",").map((a) => a.trim()).filter(Boolean).map((a) => `<span>${escapar(a)}</span>`).join("")}</div>` : ""}
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
  cargarEstadoCuenta().then(pintarMisSanciones);
  try {
    const rs = await api(C.RESERVAS_URL, "/reservas/mias");
    if (!rs.length) { cont.innerHTML = `<div class="tarjeta vacio">Aún no tienes reservas. ¡Explora los espacios!</div>`; return; }
    cont.innerHTML = rs.map((r) => `
      <article class="tarjeta reserva">
        <div><h3>${escapar(r.espacio_nombre)}</h3>
          <p class="sub">${fechaLarga(r.fecha)} · ${hhmm(r.hora_inicio)}–${hhmm(r.hora_fin)} · ${r.asistentes} asistente(s)${r.motivo ? " · " + escapar(r.motivo) : ""}</p>
          ${r.motivo_revocacion ? `<span class="motivo">Revocada por la administración: ${escapar(r.motivo_revocacion)}</span>` : ""}</div>
        <div class="reserva-acciones">
          <span class="estado ${r.estado}">${r.estado}</span>
          ${accionesReserva(r)}
        </div>
      </article>`).join("");
    $$("[data-cancelar]").forEach((b) => b.addEventListener("click", () => cancelar(+b.dataset.cancelar, cargarMisReservas)));
    $$("[data-llegada]").forEach((b) => b.addEventListener("click", () => confirmarLlegada(+b.dataset.llegada)));
    $$("[data-reportar]").forEach((b) => b.addEventListener("click", () => reportarOcupado(+b.dataset.reportar)));
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

$$(".subtab[data-sub]").forEach((b) => b.addEventListener("click", () => {
  admin.sub = b.dataset.sub;
  $$(".subtab[data-sub]").forEach((t) => t.classList.toggle("activo", t === b));
  ["reservas", "espacios", "horarios", "usuarios", "incidencias"].forEach((n) => $(`#sub-${n}`).classList.toggle("oculto", n !== admin.sub));
  cargarAdmin();
}));

async function cargarAdmin() {
  try {
    const st = await api(C.RESERVAS_URL, "/estadisticas");
    $("#stats").innerHTML = [
      [st.confirmadas, "Reservas activas"], [st.revocadas, "Revocadas"], [st.inasistencias, "Inasistencias"],
      [st.sanciones_activas, "Sanciones vigentes"], [st.espacios_activos, "Espacios activos"], [st.horarios_clase, "Bloques de clase"],
    ].map(([n, t]) => `<div class="tarjeta stat"><b>${n}</b><span>${t}</span></div>`).join("");
    admin.espacios = await api(C.RESERVAS_URL, "/admin/espacios");
    if (admin.sub === "reservas") await cargarReservasAdmin();
    if (admin.sub === "espacios") pintarEspaciosAdmin();
    if (admin.sub === "horarios") await cargarHorarios();
    if (admin.sub === "usuarios") await cargarUsuarios();
    if (admin.sub === "incidencias") await cargarIncidencias();
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
      <td data-label="Tipo"><span>${TIPOS[e.tipo]}${e.actividades ? `<br><small>${escapar(e.actividades)}</small>` : ""}</span></td>
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
    ["nombre", "tipo", "capacidad", "ubicacion", "descripcion", "actividades"].forEach((k) => (f[k].value = e[k] ?? ""));
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
    descripcion: f.descripcion.value, actividades: f.actividades.value, hora_apertura: f.hora_apertura.value, hora_cierre: f.hora_cierre.value, activo: f.activo.checked,
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

// ---------------------------------------------------------------- llegada, reportes y sanciones (usuario)
const minDe = (fecha, hora) => new Date(`${fecha}T${hhmm(hora)}:00`).getTime();
const MIN = 60000;

function accionesReserva(r) {
  if (r.estado !== "confirmada") return "";
  const ahora = Date.now(), ini = minDe(r.fecha, r.hora_inicio), fin = minDe(r.fecha, r.hora_fin);
  const b = [];
  if (r.llegada_confirmada_en) b.push(`<span class="estado llegada">✓ Llegada confirmada</span>`);
  else if (ahora >= ini - 10 * MIN && ahora <= ini + 20 * MIN)
    b.push(`<button class="btn primario" data-llegada="${r.id}">Confirmar llegada</button>`);
  if (ahora >= ini + 10 * MIN && ahora <= fin)
    b.push(`<button class="btn secundario" data-reportar="${r.id}">Reportar espacio ocupado</button>`);
  if (ahora < ini) b.push(`<button class="btn peligro" data-cancelar="${r.id}">Cancelar</button>`);
  return b.join("");
}

async function confirmarLlegada(id, silencioso = false) {
  try {
    const r = await api(C.RESERVAS_URL, `/reservas/${id}/confirmar-llegada`, { method: "POST" });
    toast(r.mensaje);
  } catch (err) { if (!silencioso) toast(err.message, true); else toast(err.message, true); }
  cargarMisReservas();
}

async function reportarOcupado(id) {
  const comentario = await UI.pedirTexto({
    titulo: "Reportar espacio ocupado",
    mensaje: "Úsalo solo si la reserva anterior no ha entregado el espacio pasados 10 minutos del inicio de la tuya. Se sancionará a esa persona y tu llegada quedará confirmada.",
    etiqueta: "¿Qué está pasando? (opcional)", aceptar: "Enviar reporte", minimo: 0, peligro: true,
  });
  if (comentario === null) return;
  try {
    await api(C.RESERVAS_URL, `/reservas/${id}/reportar-ocupado`, { method: "POST", body: { comentario } });
    toast("Reporte enviado. Tu llegada quedó confirmada.");
    cargarMisReservas();
  } catch (err) { toast(err.message, true); }
}

const NIVEL = { 0: "Manual", 1: "Nivel 1 · 1 día", 2: "Nivel 2 · 3 días", 3: "Nivel 3 · 1 semana", 4: "Nivel 4 · Suspensión" };
const TIPO_SANCION = { ocupacion: "No entregó el espacio", inasistencia: "No confirmó llegada", manual: "Sanción manual" };
const fechaHora = (iso) => iso ? new Date(iso).toLocaleString("es-CO", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "Indefinida";

async function cargarEstadoCuenta() {
  const banner = $("#banner-sancion");
  if (!estado.token || estado.usuario?.rol === "admin") { banner.classList.add("oculto"); return; }
  try {
    const [yo, sanciones] = await Promise.all([api(C.AUTH_URL, "/me"), api(C.RESERVAS_URL, "/sanciones/mias")]);
    estado.sanciones = sanciones;
    const activa = sanciones.find((s) => s.activa);
    let html = "";
    if (yo.estado === "suspendido")
      html = `<b>Tu cuenta está suspendida.</b> No puedes hacer reservas. Motivo: ${escapar(yo.motivo_estado || "—")}`;
    else if (activa)
      html = `<b>Tienes una sanción vigente ${activa.hasta ? `hasta el ${fechaHora(activa.hasta)}` : "hasta que la administración la levante"}.</b> ${escapar(activa.motivo)}`;
    banner.innerHTML = html ? `<span class="banner-icono">!</span><div>${html}</div>` : "";
    banner.classList.toggle("oculto", !html);
  } catch { banner.classList.add("oculto"); }
}

function pintarMisSanciones() {
  const lista = estado.sanciones || [];
  $("#mis-sanciones").classList.toggle("oculto", !lista.length);
  $("#lista-mis-sanciones").innerHTML = lista.map((s) => `
    <article class="tarjeta reserva">
      <div><h3>${TIPO_SANCION[s.tipo]} <small class="chip-nivel n${s.nivel}">${NIVEL[s.nivel]}</small></h3>
        <p class="sub">${escapar(s.motivo)}</p>
        <p class="sub">${escapar(s.descripcion)} · desde ${fechaHora(s.desde)} hasta ${fechaHora(s.hasta)}</p>
        ${s.nota_admin ? `<span class="motivo">${escapar(s.nota_admin)}</span>` : ""}</div>
      <span class="estado ${s.activa ? "revocada" : s.estado === "anulada" ? "inactivo" : "activo"}">${s.activa ? "vigente" : s.estado === "vigente" ? "cumplida" : s.estado}</span>
    </article>`).join("");
}

// ---------------------------------------------------------------- recuperar contraseña
$("#btn-olvide").addEventListener("click", () => {
  const f = $("#form-recuperar");
  f.reset();
  errorEn(f);
  f.email.value = $("#form-login [name=email]").value;
  $("#modal-recuperar").showModal();
});
$("#form-recuperar").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const r = await api(C.AUTH_URL, "/recuperar", { method: "POST", auth: false, body: { email: e.target.email.value } });
    cerrarModales();
    toast(r.mensaje);
  } catch (err) { errorEn(e.target, err.message); }
});
$("#form-restablecer").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  if (f.password.value !== f.password2.value) return errorEn(f, "Las contraseñas no coinciden");
  try {
    const r = await api(C.AUTH_URL, "/restablecer", { method: "POST", auth: false, body: { token: estado.tokenReset, password: f.password.value } });
    cerrarModales();
    toast(r.mensaje);
  } catch (err) { errorEn(f, err.message); }
});

// Enlaces que llegan por correo: ?reset=TOKEN y ?confirmar=ID
function procesarEnlaces() {
  const q = new URLSearchParams(location.search);
  if (q.get("reset")) {
    estado.tokenReset = q.get("reset");
    $("#form-restablecer").reset();
    errorEn($("#form-restablecer"));
    $("#modal-restablecer").showModal();
  }
  if (q.get("confirmar")) sessionStorage.setItem("confirmarPendiente", q.get("confirmar"));
  if (q.toString()) history.replaceState(null, "", location.pathname);
}
function confirmarPendiente() {
  const id = sessionStorage.getItem("confirmarPendiente");
  if (!id || !estado.token) {
    if (id) toast("Inicia sesión para confirmar tu llegada");
    return;
  }
  sessionStorage.removeItem("confirmarPendiente");
  mostrarVista("mis-reservas");
  confirmarLlegada(+id, true);
}

// ---------------------------------------------------------------- admin: usuarios
admin.usuarios = [];
admin.resumen = {};
let temporizadorBusqueda;
$("#buscar-usuario").addEventListener("input", () => { clearTimeout(temporizadorBusqueda); temporizadorBusqueda = setTimeout(pintarUsuarios, 200); });
$("#filtro-estado-usuario").addEventListener("change", pintarUsuarios);

async function cargarUsuarios() {
  const [usuarios, resumen] = await Promise.all([api(C.AUTH_URL, "/usuarios"), api(C.RESERVAS_URL, "/admin/usuarios/resumen")]);
  admin.usuarios = usuarios;
  admin.resumen = resumen;
  pintarUsuarios();
}
const resumenDe = (id) => admin.resumen[id] || { reservas: 0, activas: 0, inasistencias: 0, reportes_recibidos: 0, sanciones: 0, sancion_activa: null };
const chipEstado = (u) => `<span class="estado ${u.estado === "activo" ? "activo" : u.estado === "suspendido" ? "revocada" : "cancelada"}">${u.estado}</span>`;
const chipSancion = (s) => s ? `<span class="estado revocada" title="Vigente hasta ${fechaHora(s.hasta)}">${NIVEL[s.nivel]}</span>` : `<span class="sub">—</span>`;

function pintarUsuarios() {
  const q = $("#buscar-usuario").value.trim().toLowerCase();
  const filtro = $("#filtro-estado-usuario").value;
  const lista = admin.usuarios.filter((u) => {
    const r = resumenDe(u.id);
    if (q && !`${u.nombre} ${u.email}`.toLowerCase().includes(q)) return false;
    if (filtro === "sancionado") return !!r.sancion_activa;
    return !filtro || u.estado === filtro;
  });
  $("#tabla-usuarios tbody").innerHTML = lista.map((u) => {
    const r = resumenDe(u.id);
    return `<tr>
      <td data-label="Usuario"><span><b>${escapar(u.nombre)}</b><br><small>${escapar(u.email)}</small></span></td>
      <td data-label="Rol">${u.rol === "admin" ? `<span class="estado llegada">admin</span>` : "estudiante"}</td>
      <td data-label="Estado">${chipEstado(u)}</td>
      <td data-label="Reservas">${r.reservas} <small>(${r.activas} activas)</small></td>
      <td data-label="Inasistencias">${r.inasistencias}</td>
      <td data-label="Reportes">${r.reportes_recibidos}</td>
      <td data-label="Sanción">${chipSancion(r.sancion_activa)}</td>
      <td class="acc"><button class="btn-mini" data-ver-usuario="${u.id}">Gestionar</button></td></tr>`;
  }).join("") || `<tr><td colspan="8" class="vacio">No hay usuarios con esos filtros</td></tr>`;
  $$("[data-ver-usuario]").forEach((b) => b.addEventListener("click", () => abrirUsuario(+b.dataset.verUsuario)));
}

// ----- ficha del usuario
const ficha = { usuario: null, historial: null, avisos: [], pestana: "reservas" };
$$(".subtabs-u .subtab").forEach((b) => b.addEventListener("click", () => {
  ficha.pestana = b.dataset.u;
  $$(".subtabs-u .subtab").forEach((t) => t.classList.toggle("activo", t === b));
  pintarFicha();
}));

async function abrirUsuario(id) {
  ficha.usuario = admin.usuarios.find((u) => u.id === id);
  ficha.pestana = "reservas";
  $$(".subtabs-u .subtab").forEach((t) => t.classList.toggle("activo", t.dataset.u === "reservas"));
  $("#u-contenido").innerHTML = `<p class="vacio">Cargando…</p>`;
  if (!$("#modal-usuario").open) $("#modal-usuario").showModal();
  pintarCabeceraUsuario();
  try {
    const [historial, avisos] = await Promise.all([
      api(C.RESERVAS_URL, `/admin/usuarios/${id}/historial`),
      api(C.NOTIF_URL, `/admin/usuarios/${id}/notificaciones`).catch(() => []),
    ]);
    ficha.historial = historial;
    ficha.avisos = avisos;
    pintarCabeceraUsuario();
    pintarFicha();
  } catch (err) { $("#u-contenido").innerHTML = `<p class="vacio">${escapar(err.message)}</p>`; }
}

function pintarCabeceraUsuario() {
  const u = ficha.usuario, r = resumenDe(u.id), yo = estado.usuario.id === u.id;
  $("#u-avatar").textContent = u.nombre.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  $("#u-nombre").textContent = u.nombre;
  $("#u-email").textContent = `${u.email} · registrado el ${new Date(u.creado_en).toLocaleDateString("es-CO")}` +
    (u.ultimo_acceso ? ` · último acceso ${fechaHora(u.ultimo_acceso)}` : "");
  $("#u-chips").innerHTML = chipEstado(u) + (u.rol === "admin" ? ` <span class="estado llegada">admin</span>` : "") +
    (r.sancion_activa ? ` ${chipSancion(r.sancion_activa)}` : "") +
    (u.motivo_estado ? `<span class="motivo">${escapar(u.motivo_estado)}</span>` : "");
  const btn = (accion, texto, clase = "") => `<button class="btn-accion ${clase}" data-uaccion="${accion}">${texto}</button>`;
  $("#u-acciones").innerHTML = yo ? `<p class="sub">Esta es tu cuenta de administrador.</p>` : [
    u.estado !== "activo" ? btn("activo", "✓ Reactivar cuenta", "verde") : "",
    u.estado !== "suspendido" ? btn("suspendido", "⏸ Suspender", "ambar") : "",
    u.estado !== "bloqueado" ? btn("bloqueado", "⛔ Bloquear", "rojo") : "",
    btn("reset", "🔑 Restablecer contraseña"),
    btn("alerta", "✉ Enviar alerta"),
    btn("sancion", "⚖ Aplicar sanción", "rojo"),
    btn("rol", u.rol === "admin" ? "Quitar rol admin" : "Hacer administrador"),
  ].join("");
  $("#u-metricas").innerHTML = [
    [r.reservas, "Reservas"], [r.activas, "Activas"], [r.inasistencias, "Inasistencias"],
    [r.reportes_recibidos, "Reportes recibidos"], [r.sanciones, "Sanciones"],
  ].map(([n, t]) => `<div><b>${n}</b><span>${t}</span></div>`).join("");
  $$("[data-uaccion]").forEach((b) => b.addEventListener("click", () => accionUsuario(b.dataset.uaccion)));
}

function pintarFicha() {
  const h = ficha.historial, c = $("#u-contenido");
  if (!h) return;
  const vacio = (t) => `<p class="vacio">${t}</p>`;
  if (ficha.pestana === "reservas") {
    c.innerHTML = h.reservas.length ? `<div class="tabla-resp"><table><thead><tr><th>Espacio</th><th>Fecha</th><th>Horario</th><th>Llegada</th><th>Estado</th></tr></thead><tbody>${
      h.reservas.map((r) => `<tr><td data-label="Espacio">${escapar(r.espacio_nombre)}</td><td data-label="Fecha">${r.fecha}</td>
        <td data-label="Horario">${hhmm(r.hora_inicio)}–${hhmm(r.hora_fin)}</td>
        <td data-label="Llegada">${r.llegada_confirmada_en ? `✓ ${new Date(r.llegada_confirmada_en).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" })}` : "—"}</td>
        <td data-label="Estado"><span class="estado ${r.estado}">${r.estado}</span></td></tr>`).join("")}</tbody></table></div>` : vacio("Sin reservas");
  } else if (ficha.pestana === "sanciones") {
    c.innerHTML = h.sanciones.length ? h.sanciones.map((s) => `<div class="item-linea">
      <div><b>${TIPO_SANCION[s.tipo]}</b> <small class="chip-nivel n${s.nivel}">${NIVEL[s.nivel]}</small>
        <p class="sub">${escapar(s.motivo)}</p><small class="sub">${fechaHora(s.desde)} → ${fechaHora(s.hasta)} · por ${escapar(s.creada_por)}</small>
        ${s.nota_admin ? `<span class="motivo">${escapar(s.nota_admin)}</span>` : ""}</div>
      <div class="acciones-fila"><span class="estado ${s.activa ? "revocada" : "inactivo"}">${s.activa ? "vigente" : s.estado === "vigente" ? "cumplida" : s.estado}</span>
        ${s.activa ? `<button class="btn-mini" data-levantar="${s.id}">Levantar</button>` : ""}</div></div>`).join("") : vacio("Sin sanciones");
  } else if (ficha.pestana === "reportes") {
    const fila = (r, recibido) => `<div class="item-linea"><div><b>${recibido ? "Reportado por" : "Reportó a"} ${escapar(recibido ? r.reportante_nombre : r.reportado_nombre)}</b>
      <p class="sub">${escapar(r.espacio)} · ${fechaHora(r.creado_en)}${r.comentario ? ` · “${escapar(r.comentario)}”` : ""}</p></div>
      <div class="acciones-fila"><span class="estado ${r.estado === "valido" ? "revocada" : "inactivo"}">${r.estado}</span>
      ${recibido && r.estado === "valido" ? `<button class="btn-mini" data-anular="${r.id}">Anular</button>` : ""}</div></div>`;
    c.innerHTML = (h.reportes_recibidos.map((r) => fila(r, true)).join("") + h.reportes_hechos.map((r) => fila(r, false)).join("")) || vacio("Sin reportes");
  } else {
    c.innerHTML = ficha.avisos.length ? ficha.avisos.map((n) => `<div class="item-linea"><div><b>${escapar(n.titulo)}</b>
      <p class="sub">${escapar(n.mensaje)}</p><small class="sub">${fechaHora(n.creada_en)}${n.correo_enviado ? " · 📧 enviado por correo" : ""}</small></div>
      <span class="estado ${n.leida ? "inactivo" : "llegada"}">${n.leida ? "leída" : "no leída"}</span></div>`).join("") : vacio("Sin avisos");
  }
  $$("[data-levantar]").forEach((b) => b.addEventListener("click", () => levantarSancion(+b.dataset.levantar)));
  $$("[data-anular]").forEach((b) => b.addEventListener("click", () => anularReporte(+b.dataset.anular)));
}

async function refrescarFicha() {
  await cargarUsuarios();
  if ($("#modal-usuario").open && ficha.usuario) await abrirUsuario(ficha.usuario.id);
}

async function accionUsuario(accion) {
  const u = ficha.usuario;
  try {
    if (["activo", "suspendido", "bloqueado"].includes(accion)) {
      let motivo = "";
      if (accion !== "activo") {
        motivo = await UI.pedirTexto({
          titulo: accion === "bloqueado" ? `Bloquear a ${u.nombre}` : `Suspender a ${u.nombre}`,
          mensaje: accion === "bloqueado" ? "No podrá iniciar sesión hasta que reactives la cuenta." : "Podrá iniciar sesión, pero no hacer reservas.",
          etiqueta: "Motivo (se le enviará por correo)", aceptar: accion === "bloqueado" ? "Bloquear" : "Suspender", peligro: true,
        });
        if (motivo === null) return;
      } else {
        const r = resumenDe(u.id);
        if (!(await UI.confirmar({ titulo: `Reactivar a ${u.nombre}`, mensaje: r.sancion_activa ? "La cuenta quedará activa. Ojo: tiene una sanción vigente; levántala en la pestaña Sanciones si corresponde." : "La cuenta volverá a funcionar con normalidad.", aceptar: "Reactivar" }))) return;
      }
      await api(C.AUTH_URL, `/usuarios/${u.id}/estado`, { method: "PATCH", body: { estado: accion, motivo } });
      toast(`Cuenta ${accion === "activo" ? "reactivada" : accion}`);
    } else if (accion === "reset") {
      if (!(await UI.confirmar({ titulo: "Restablecer contraseña", mensaje: `Se enviará a ${u.email} un enlace válido por 30 minutos para crear una nueva contraseña.`, aceptar: "Enviar enlace" }))) return;
      const r = await api(C.AUTH_URL, `/usuarios/${u.id}/restablecer`, { method: "POST" });
      await UI.confirmar({ titulo: "Enlace enviado", mensaje: `${r.mensaje}. Si el correo no llega, comparte este enlace por otro medio: ${r.enlace}`, aceptar: "Entendido", cancelar: "Cerrar" });
      return;
    } else if (accion === "alerta") {
      return abrirAlerta(u);
    } else if (accion === "sancion") {
      const f = $("#form-sancion");
      f.reset();
      errorEn(f);
      $("#sancion-destino").textContent = `${u.nombre} · ${u.email}`;
      return $("#modal-sancion").showModal();
    } else if (accion === "rol") {
      const nuevo = u.rol === "admin" ? "estudiante" : "admin";
      if (!(await UI.confirmar({ titulo: nuevo === "admin" ? "Dar rol de administrador" : "Quitar rol de administrador", mensaje: `${u.nombre} ${nuevo === "admin" ? "podrá gestionar espacios, reservas y usuarios" : "volverá a ser estudiante"}.`, aceptar: "Confirmar" }))) return;
      await api(C.AUTH_URL, `/usuarios/${u.id}/rol`, { method: "PATCH", body: { rol: nuevo } });
      toast("Rol actualizado");
    }
    await refrescarFicha();
  } catch (err) { toast(err.message, true); }
}

$("#form-sancion").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target, u = ficha.usuario;
  try {
    await api(C.RESERVAS_URL, "/admin/sanciones", { method: "POST", body: {
      usuario_id: u.id, usuario_email: u.email, usuario_nombre: u.nombre, motivo: f.motivo.value.trim(), dias: f.dias.value ? +f.dias.value : null } });
    $("#modal-sancion").close();
    toast("Sanción aplicada y notificada");
    await refrescarFicha();
  } catch (err) { errorEn(f, err.message); }
});

async function levantarSancion(id) {
  const nota = await UI.pedirTexto({ titulo: "Levantar sanción", mensaje: "El usuario podrá volver a reservar. La sanción seguirá contando como antecedente.", etiqueta: "Motivo", aceptar: "Levantar", minimo: 5 });
  if (nota === null) return;
  try {
    await api(C.RESERVAS_URL, `/admin/sanciones/${id}/levantar`, { method: "POST", body: { nota } });
    toast("Sanción levantada");
    admin.sub === "incidencias" ? cargarIncidencias() : null;
    await refrescarFicha();
  } catch (err) { toast(err.message, true); }
}

async function anularReporte(id) {
  const nota = await UI.pedirTexto({ titulo: "Anular reporte", mensaje: "Se anulará también la sanción que generó y no contará como reincidencia.", etiqueta: "Motivo", aceptar: "Anular", minimo: 5, peligro: true });
  if (nota === null) return;
  try {
    await api(C.RESERVAS_URL, `/admin/reportes/${id}/anular`, { method: "POST", body: { nota } });
    toast("Reporte anulado");
    admin.sub === "incidencias" ? cargarIncidencias() : null;
    if ($("#modal-usuario").open) await refrescarFicha();
  } catch (err) { toast(err.message, true); }
}

// ----- alertas
const PLANTILLAS_ALERTA = {
  entrega: ["Entrega puntual de los espacios", "Hemos registrado que no entregaste un espacio a tiempo. Recuerda desocuparlo a la hora de finalización: la siguiente persona puede reportarlo y se aplicarán sanciones."],
  llegada: ["Confirma tu llegada a las reservas", "Tienes reservas sin confirmación de llegada. Confirma tu asistencia en la app dentro de los primeros 20 minutos o cancela la reserva si no vas a asistir."],
  uso: ["Uso adecuado de los espacios", "Recibimos reportes sobre el uso del espacio reservado. Te pedimos cuidar el mobiliario, mantener el orden y respetar la capacidad máxima."],
  reincidencia: ["Advertencia por reincidencia", "Tu historial muestra varias infracciones. Una nueva falta puede llevar a la suspensión de tu cuenta hasta que la administración la reactive."],
};
let alertaPara = null;
function abrirAlerta(u) {
  alertaPara = u;
  const f = $("#form-alerta");
  f.reset();
  errorEn(f);
  $("#alerta-destino").textContent = `Para: ${u.nombre} · ${u.email}`;
  $("#modal-alerta").showModal();
}
$("#plantilla-alerta").addEventListener("change", (e) => {
  const p = PLANTILLAS_ALERTA[e.target.value];
  if (p) { $("#form-alerta").asunto.value = p[0]; $("#form-alerta").mensaje.value = p[1]; }
});
$("#form-alerta").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target, u = alertaPara;
  try {
    const r = await api(C.NOTIF_URL, "/alertas", { method: "POST", body: {
      usuario_id: u.id, usuario_email: u.email, usuario_nombre: u.nombre, asunto: f.asunto.value.trim(),
      mensaje: f.mensaje.value.trim(), enviar_correo: f.enviar_correo.checked } });
    $("#modal-alerta").close();
    toast(r.correo_enviado ? "Alerta enviada (app y correo)" : "Alerta enviada en la app");
    if ($("#modal-usuario").open) await abrirUsuario(u.id);
  } catch (err) { errorEn(f, err.message); }
});

// ---------------------------------------------------------------- admin: incidencias
$("#filtro-sanciones").addEventListener("change", cargarIncidencias);
async function cargarIncidencias() {
  const [sanciones, reportes] = await Promise.all([
    api(C.RESERVAS_URL, `/admin/sanciones${$("#filtro-sanciones").value ? "?solo_activas=true" : ""}`),
    api(C.RESERVAS_URL, "/admin/reportes"),
  ]);
  $("#tabla-sanciones tbody").innerHTML = sanciones.map((s) => `<tr>
    <td data-label="Usuario"><span><b>${escapar(s.usuario_nombre)}</b><br><small>${escapar(s.usuario_email)}</small></span></td>
    <td data-label="Nivel"><small class="chip-nivel n${s.nivel}">${NIVEL[s.nivel]}</small></td>
    <td data-label="Tipo">${TIPO_SANCION[s.tipo]}</td>
    <td data-label="Motivo" class="celda-texto">${escapar(s.motivo)}</td>
    <td data-label="Hasta">${fechaHora(s.hasta)}</td>
    <td data-label="Estado"><span class="estado ${s.activa ? "revocada" : "inactivo"}">${s.activa ? "vigente" : s.estado === "vigente" ? "cumplida" : s.estado}</span></td>
    <td class="acc"><div class="acciones-fila">
      <button class="btn-mini" data-alerta-u="${s.usuario_id}" data-n="${escapar(s.usuario_nombre)}" data-e="${escapar(s.usuario_email)}">Alertar</button>
      ${s.activa ? `<button class="btn-mini" data-levantar="${s.id}">Levantar</button>` : ""}</div></td></tr>`).join("")
    || `<tr><td colspan="7" class="vacio">No hay sanciones</td></tr>`;
  $("#tabla-reportes tbody").innerHTML = reportes.map((r) => `<tr>
    <td data-label="Fecha">${fechaHora(r.creado_en)}</td>
    <td data-label="Espacio">${escapar(r.espacio)}</td>
    <td data-label="Reportó">${escapar(r.reportante_nombre)}</td>
    <td data-label="Reportado"><span><b>${escapar(r.reportado_nombre)}</b><br><small>${escapar(r.reportado_email)}</small></span></td>
    <td data-label="Comentario" class="celda-texto">${escapar(r.comentario || "—")}</td>
    <td data-label="Estado"><span class="estado ${r.estado === "valido" ? "revocada" : "inactivo"}">${r.estado}</span></td>
    <td class="acc">${r.estado === "valido" ? `<button class="btn-mini" data-anular="${r.id}">Anular</button>` : ""}</td></tr>`).join("")
    || `<tr><td colspan="7" class="vacio">No hay reportes</td></tr>`;
  $$("#sub-incidencias [data-levantar]").forEach((b) => b.addEventListener("click", () => levantarSancion(+b.dataset.levantar)));
  $$("#sub-incidencias [data-anular]").forEach((b) => b.addEventListener("click", () => anularReporte(+b.dataset.anular)));
  $$("[data-alerta-u]").forEach((b) => b.addEventListener("click", () =>
    abrirAlerta({ id: +b.dataset.alertaU, nombre: b.dataset.n, email: b.dataset.e })));
}

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

procesarEnlaces();
pintarSesion();
