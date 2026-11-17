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
        return `<span style="left:${izq}%;width:${ancho}%" title="${hhmm(o.hora_inicio)}-${hhmm(o.hora_fin)}"></span>`;
      }).join("");
      return `<article class="tarjeta espacio">
        <div class="espacio-cab"><h3>${escapar(e.nombre)}</h3><span class="chip ${e.tipo}">${TIPOS[e.tipo]}</span></div>
        <div class="meta"><span>👥 ${e.capacidad} personas</span><span>📍 ${escapar(e.ubicacion)}</span></div>
        <p class="desc">${escapar(e.descripcion || "")}</p>
        <div><div class="barra-dia">${bloques}</div>
          <div class="leyenda"><span>${hhmm(e.hora_apertura)}</span><span>${ocupado.length ? `${ocupado.length} reserva(s)` : "Libre todo el día"}</span><span>${hhmm(e.hora_cierre)}</span></div></div>
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
      ? `<b>Ocupado ese día:</b> ${occ.map((o) => `${hhmm(o.hora_inicio)}–${hhmm(o.hora_fin)}`).join(", ")}`
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
          <p class="sub">${fechaLarga(r.fecha)} · ${hhmm(r.hora_inicio)}–${hhmm(r.hora_fin)} · ${r.asistentes} asistente(s)${r.motivo ? " · " + escapar(r.motivo) : ""}</p></div>
        <div style="display:flex;gap:.6rem;align-items:center">
          <span class="estado ${r.estado}">${r.estado}</span>
          ${r.estado === "confirmada" && r.fecha >= hoy ? `<button class="btn peligro" data-cancelar="${r.id}">Cancelar</button>` : ""}
        </div>
      </article>`).join("");
    $$("[data-cancelar]").forEach((b) => b.addEventListener("click", () => cancelar(+b.dataset.cancelar, cargarMisReservas)));
  } catch (err) { cont.innerHTML = `<p class="vacio">${escapar(err.message)}</p>`; }
}

async function cancelar(id, luego) {
  if (!confirm("¿Seguro que quieres cancelar esta reserva?")) return;
  try {
    await api(C.RESERVAS_URL, `/reservas/${id}/cancelar`, { method: "POST" });
    toast("Reserva cancelada");
    luego();
    setTimeout(cargarNotificaciones, 1500);
  } catch (err) { toast(err.message, true); }
}

// ---------------------------------------------------------------- admin
async function cargarAdmin() {
  try {
    const [st, rs] = await Promise.all([api(C.RESERVAS_URL, "/estadisticas"), api(C.RESERVAS_URL, "/reservas")]);
    const top = st.por_espacio[0];
    $("#stats").innerHTML = `
      <div class="tarjeta stat"><b>${st.total_reservas}</b><span>Reservas totales</span></div>
      <div class="tarjeta stat"><b>${st.total_reservas - st.canceladas}</b><span>Confirmadas</span></div>
      <div class="tarjeta stat"><b>${st.canceladas}</b><span>Canceladas</span></div>
      <div class="tarjeta stat"><b style="font-size:1.1rem">${top ? escapar(top.espacio) : "—"}</b><span>Espacio más usado</span></div>`;
    $("#tabla-reservas tbody").innerHTML = rs.map((r) => `<tr>
      <td>${escapar(r.espacio_nombre)}</td><td>${escapar(r.usuario_nombre)}<br><small>${escapar(r.usuario_email)}</small></td>
      <td>${r.fecha}</td><td>${hhmm(r.hora_inicio)}–${hhmm(r.hora_fin)}</td>
      <td><span class="estado ${r.estado}">${r.estado}</span></td>
      <td>${r.estado === "confirmada" ? `<button class="enlace" data-acancelar="${r.id}">Cancelar</button>` : ""}</td></tr>`).join("")
      || `<tr><td colspan="6" class="vacio">Sin reservas</td></tr>`;
    $$("[data-acancelar]").forEach((b) => b.addEventListener("click", () => cancelar(+b.dataset.acancelar, cargarAdmin)));
  } catch (err) { toast(err.message, true); }
}

$("#form-espacio").addEventListener("submit", async (e) => {
  e.preventDefault();
  const d = Object.fromEntries(new FormData(e.target));
  try {
    await api(C.RESERVAS_URL, "/espacios", { method: "POST", body: { ...d, capacidad: +d.capacidad } });
    toast("Espacio creado");
    e.target.reset();
  } catch (err) { toast(err.message, true); }
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
