/* Componentes de UI propios: select personalizado, selector de archivo y diálogos de confirmación. */
(() => {
  const proto = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value");
  const flecha = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>`;
  const check = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`;
  let abierto = null;

  function cerrar() {
    if (!abierto) return;
    abierto.classList.remove("abierto");
    abierto.querySelector(".sel-boton").setAttribute("aria-expanded", "false");
    abierto = null;
  }

  function mejorarSelect(select) {
    if (select._sel) return;
    const caja = document.createElement("div");
    caja.className = "sel";
    caja.innerHTML = `<button type="button" class="sel-boton" aria-haspopup="listbox" aria-expanded="false">
        <span class="sel-texto"></span><span class="sel-flecha">${flecha}</span></button>
      <ul class="sel-lista" role="listbox" tabindex="-1"></ul>`;
    select.after(caja);
    select.classList.add("sel-nativo");
    select.tabIndex = -1;
    select._sel = caja;
    const boton = caja.querySelector(".sel-boton");
    const lista = caja.querySelector(".sel-lista");
    if (select.getAttribute("aria-label")) boton.setAttribute("aria-label", select.getAttribute("aria-label"));

    const pintar = () => {
      const op = select.options[select.selectedIndex];
      caja.querySelector(".sel-texto").textContent = op ? op.textContent : "";
      lista.innerHTML = [...select.options].map((o, i) =>
        `<li role="option" data-i="${i}" aria-selected="${i === select.selectedIndex}" class="${i === select.selectedIndex ? "activo" : ""}">
          <span></span>${check}</li>`).join("");
      lista.querySelectorAll("li").forEach((li, i) => (li.querySelector("span").textContent = select.options[i].textContent));
    };
    const elegir = (i) => {
      if (i !== select.selectedIndex) {
        select.selectedIndex = i;
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
      pintar();
      cerrar();
      boton.focus();
    };
    const resaltar = (i) => {
      const items = lista.querySelectorAll("li");
      items.forEach((li) => li.classList.remove("foco"));
      const li = items[Math.max(0, Math.min(i, items.length - 1))];
      if (li) { li.classList.add("foco"); li.scrollIntoView({ block: "nearest" }); }
    };
    const abrir = () => {
      cerrar();
      pintar();
      caja.classList.add("abierto");
      // Abre hacia arriba si no cabe abajo
      const r = boton.getBoundingClientRect();
      caja.classList.toggle("arriba", window.innerHeight - r.bottom < 240 && r.top > 240);
      boton.setAttribute("aria-expanded", "true");
      abierto = caja;
      resaltar(select.selectedIndex);
    };

    boton.addEventListener("click", (e) => { e.stopPropagation(); caja.classList.contains("abierto") ? cerrar() : abrir(); });
    lista.addEventListener("click", (e) => { e.stopPropagation(); const li = e.target.closest("li"); if (li) elegir(+li.dataset.i); });
    boton.addEventListener("keydown", (e) => {
      const items = [...lista.querySelectorAll("li")];
      const actual = items.findIndex((li) => li.classList.contains("foco"));
      if (["ArrowDown", "ArrowUp"].includes(e.key)) {
        e.preventDefault();
        if (!caja.classList.contains("abierto")) return abrir();
        resaltar(actual + (e.key === "ArrowDown" ? 1 : -1));
      } else if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        caja.classList.contains("abierto") ? elegir(actual < 0 ? select.selectedIndex : actual) : abrir();
      } else if (e.key === "Escape" || e.key === "Tab") cerrar();
    });

    // Mantener sincronizado cuando el código cambia el valor u opciones
    Object.defineProperty(select, "value", {
      get() { return proto.get.call(this); },
      set(v) { proto.set.call(this, v); pintar(); },
    });
    new MutationObserver(pintar).observe(select, { childList: true, subtree: true });
    select.form?.addEventListener("reset", () => setTimeout(pintar));
    select.addEventListener("change", pintar);
    pintar();
  }

  function mejorarArchivo(input) {
    if (input._arch) return;
    const caja = document.createElement("div");
    caja.className = "archivo";
    caja.innerHTML = `<div class="archivo-icono"><svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/></svg></div>
      <div class="archivo-texto"><b>Arrastra tu CSV aquí</b><small>o haz clic para seleccionarlo</small></div>`;
    input.after(caja);
    input.classList.add("archivo-nativo");
    input._arch = caja;
    const pintar = () => {
      const f = input.files[0];
      caja.classList.toggle("con-archivo", !!f);
      caja.querySelector("b").textContent = f ? f.name : "Arrastra tu CSV aquí";
      caja.querySelector("small").textContent = f ? `${(f.size / 1024).toFixed(1)} KB · clic para cambiarlo` : "o haz clic para seleccionarlo";
    };
    caja.addEventListener("click", () => input.click());
    caja.addEventListener("dragover", (e) => { e.preventDefault(); caja.classList.add("arrastrando"); });
    caja.addEventListener("dragleave", () => caja.classList.remove("arrastrando"));
    caja.addEventListener("drop", (e) => {
      e.preventDefault();
      caja.classList.remove("arrastrando");
      if (e.dataTransfer.files.length) { input.files = e.dataTransfer.files; pintar(); }
    });
    input.addEventListener("change", pintar);
    input.form?.addEventListener("reset", () => setTimeout(pintar));
    // permitir que el código asigne archivos (pruebas)
    const desc = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "files");
    Object.defineProperty(input, "files", { get() { return desc.get.call(this); }, set(v) { desc.set.call(this, v); pintar(); } });
  }

  // Botón para mostrar/ocultar contraseñas
  const ojo = `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>`;
  const ojoTachado = `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.9 4.2A10.4 10.4 0 0 1 12 4c6.4 0 10 8 10 8a17.6 17.6 0 0 1-2.2 3.2M6.6 6.6C3.8 8.5 2 12 2 12s3.6 8 10 8a9.7 9.7 0 0 0 5.4-1.6"/><path d="M14.1 14.1a3 3 0 0 1-4.2-4.2"/><path d="m2 2 20 20"/></svg>`;

  function mejorarPassword(input) {
    if (input._pass) return;
    const caja = document.createElement("span");
    caja.className = "pass-caja";
    input.before(caja);
    caja.append(input);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "pass-toggle";
    caja.append(btn);
    input._pass = btn;
    const pintar = () => {
      const visible = input.type === "text";
      btn.innerHTML = visible ? ojoTachado : ojo;
      btn.setAttribute("aria-label", visible ? "Ocultar contraseña" : "Mostrar contraseña");
      btn.title = visible ? "Ocultar contraseña" : "Mostrar contraseña";
      btn.setAttribute("aria-pressed", String(visible));
    };
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const pos = input.selectionStart;
      input.type = input.type === "password" ? "text" : "password";
      pintar();
      input.focus();
      try { input.setSelectionRange(pos, pos); } catch { /* algunos tipos no lo permiten */ }
    });
    // Al reiniciar el formulario o enviarlo, la contraseña vuelve a quedar oculta
    input.form?.addEventListener("reset", () => { input.type = "password"; pintar(); });
    input.form?.addEventListener("submit", () => { input.type = "password"; pintar(); });
    pintar();
  }

  // Diálogo de confirmación con estilo propio (reemplaza window.confirm)
  function confirmar({ titulo = "¿Estás seguro?", mensaje = "", aceptar = "Confirmar", cancelar = "Cancelar", peligro = false } = {}) {
    return new Promise((resolver) => {
      const d = document.createElement("dialog");
      d.className = "modal dialogo-confirmar";
      d.innerHTML = `<div class="dialogo-icono ${peligro ? "peligro" : ""}">${peligro ? "!" : "?"}</div>
        <h3></h3><p class="sub"></p>
        <div class="modal-acciones"><button type="button" class="btn secundario" data-r="0"></button>
        <button type="button" class="btn ${peligro ? "peligro-solido" : "primario"}" data-r="1"></button></div>`;
      d.querySelector("h3").textContent = titulo;
      d.querySelector("p").textContent = mensaje;
      d.querySelector('[data-r="0"]').textContent = cancelar;
      d.querySelector('[data-r="1"]').textContent = aceptar;
      document.body.append(d);
      const fin = (v) => { d.close(); d.remove(); resolver(v); };
      d.addEventListener("click", (e) => {
        e.stopPropagation();
        const b = e.target.closest("[data-r]");
        if (b) return fin(b.dataset.r === "1");
        const r = d.getBoundingClientRect();
        if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) fin(false);
      });
      d.addEventListener("cancel", (e) => { e.preventDefault(); fin(false); });
      d.showModal();
      d.querySelector('[data-r="1"]').focus();
    });
  }

  // Diálogo que pide un texto (motivo, nota). Devuelve el texto o null si se cancela.
  function pedirTexto({ titulo, mensaje = "", etiqueta = "Motivo", aceptar = "Guardar", minimo = 10, peligro = false, valor = "" } = {}) {
    return new Promise((resolver) => {
      const d = document.createElement("dialog");
      d.className = "modal dialogo-confirmar dialogo-texto";
      d.innerHTML = `<div class="dialogo-icono ${peligro ? "peligro" : ""}">${peligro ? "!" : "✎"}</div>
        <h3></h3><p class="sub"></p>
        <form class="form" method="dialog">
          <label><span class="etq"></span><textarea rows="3" required maxlength="300"></textarea></label>
          <p class="error" role="alert"></p>
          <div class="modal-acciones"><button type="button" class="btn secundario" data-r="0">Cancelar</button>
          <button type="submit" class="btn ${peligro ? "peligro-solido" : "primario"}"></button></div>
        </form>`;
      d.querySelector("h3").textContent = titulo;
      d.querySelector("p.sub").textContent = mensaje;
      d.querySelector(".etq").textContent = etiqueta;
      d.querySelector("button[type=submit]").textContent = aceptar;
      const ta = d.querySelector("textarea");
      ta.minLength = minimo;
      ta.value = valor;
      document.body.append(d);
      const fin = (v) => { d.close(); d.remove(); resolver(v); };
      d.querySelector("form").addEventListener("submit", (e) => {
        e.preventDefault();
        const v = ta.value.trim();
        if (v.length < minimo) { d.querySelector(".error").textContent = `Escribe al menos ${minimo} caracteres.`; return; }
        fin(v);
      });
      d.querySelector('[data-r="0"]').addEventListener("click", () => fin(null));
      d.addEventListener("click", (e) => e.stopPropagation());
      d.addEventListener("cancel", (e) => { e.preventDefault(); fin(null); });
      d.showModal();
      ta.focus();
    });
  }

  // Cerrar cualquier diálogo .modal al hacer clic en el fondo
  document.addEventListener("click", (e) => {
    cerrar();
    const d = e.target;
    if (d.matches("dialog.modal[open]") && !d.classList.contains("dialogo-confirmar")) {
      const r = d.getBoundingClientRect();
      const fuera = e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
      if (fuera) d.close();
    }
  });
  window.addEventListener("resize", cerrar);

  window.UI = {
    confirmar,
    pedirTexto,
    mejorar(raiz = document) {
      raiz.querySelectorAll("select").forEach(mejorarSelect);
      raiz.querySelectorAll('input[type="file"]').forEach(mejorarArchivo);
      raiz.querySelectorAll('input[type="password"]').forEach(mejorarPassword);
    },
  };
  document.addEventListener("DOMContentLoaded", () => window.UI.mejorar());
})();

// ---------- modo oscuro ----------
(function () {
  const raiz = document.documentElement;
  const btn = document.getElementById("btn-tema");
  const etiquetar = () => {
    const oscuro = raiz.getAttribute("data-tema") === "oscuro";
    if (btn) { btn.setAttribute("aria-label", oscuro ? "Cambiar a modo claro" : "Cambiar a modo oscuro"); btn.setAttribute("aria-pressed", String(oscuro)); }
  };
  etiquetar();
  if (btn) btn.addEventListener("click", () => {
    const nuevo = raiz.getAttribute("data-tema") === "oscuro" ? "claro" : "oscuro";
    raiz.setAttribute("data-tema", nuevo);
    try { localStorage.setItem("rc_tema", nuevo); } catch (e) { /* sin almacenamiento: solo esta sesión */ }
    etiquetar();
  });
})();
