import time as _time
from collections import defaultdict, deque
from datetime import datetime, time, timedelta
from typing import Literal

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import config, ia
from .actividades import TIPOS as TIPOS_ESPACIO, actividad_libre, detectar_actividad, espacios_que_mencionan, etiqueta_mencionada, menciona_jugar, resumen_oferta, sirve_para
from .reglas import detectar, extraer_fecha, extraer_hora, extraer_personas, franjas_libres

app = FastAPI(
    title="Chatbot Service · ReservaCampus",
    description="Asistente virtual híbrido: motor de reglas determinista + IA (Groq) como respaldo.",
    version="1.0.0",
    root_path=config.ROOT_PATH,
)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

TIPOS = {"sala_estudio": "Sala de estudio", "laboratorio": "Laboratorio", "auditorio": "Auditorio", "cancha": "Cancha",
         "recreacion": "Sala recreativa"}
_uso: dict[str, deque] = defaultdict(deque)


class MensajeHistorial(BaseModel):
    rol: Literal["user", "assistant"]
    texto: str = Field(max_length=2000)


class ChatIn(BaseModel):
    mensaje: str = Field(min_length=1, max_length=500)
    historial: list[MensajeHistorial] = Field(default_factory=list, max_length=20)


class ChatOut(BaseModel):
    respuesta: str
    fuente: Literal["reglas", "ia", "respaldo"]
    intencion: str | None = None
    sugerencias: list[str] = []


def limitar(ip: str):
    cola = _uso[ip]
    ahora = _time.time()
    while cola and cola[0] < ahora - 60:
        cola.popleft()
    if len(cola) >= config.MAX_MENSAJES_POR_MINUTO:
        raise HTTPException(429, "Estás enviando mensajes muy rápido. Espera un momento.")
    cola.append(ahora)


async def api_reservas(ruta: str, params: dict | None = None, token: str | None = None):
    headers = {"Authorization": token} if token else {}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{config.RESERVAS_URL}{ruta}", params=params, headers=headers)
    if r.status_code == 401:
        return None
    r.raise_for_status()
    return r.json()


def fecha_texto(f) -> str:
    hoy = datetime.now(config.ZONA).date()
    if f == hoy:
        return "hoy"
    if f == hoy + timedelta(days=1):
        return "mañana"
    return f.strftime("%d/%m/%Y")


def _ocupacion_texto(ocupado: list[dict]) -> str:
    return ", ".join(f"{o['hora_inicio'][:5]}-{o['hora_fin'][:5]}"
                     + (f" ({o['etiqueta']})" if o.get("tipo") == "clase" else " (reservado)") for o in ocupado)


async def responder_disponibilidad(mensaje: str, forzar: bool = False) -> ChatOut:
    """Disponibilidad filtrada por la actividad que el usuario quiere hacer, usando los espacios reales."""
    ahora = datetime.now(config.ZONA)
    hoy = ahora.date()
    fecha = extraer_fecha(mensaje, hoy)
    hora = extraer_hora(mensaje)
    personas = extraer_personas(mensaje)
    params = {"fecha": fecha.isoformat()}
    if hora:
        fin = (datetime.combine(fecha, hora) + timedelta(hours=1)).time()
        params |= {"hora_inicio": hora.strftime("%H:%M"), "hora_fin": fin.strftime("%H:%M")}
    todos = await api_reservas("/disponibilidad", params)
    espacios = [d["espacio"] for d in todos]

    actividad = detectar_actividad(mensaje)
    tag = etiqueta_mencionada(mensaje, espacios)
    libre_txt = None if (actividad or tag) else actividad_libre(mensaje)
    que_busca = tag or (actividad.nombre if actividad else None) or libre_txt
    if que_busca:
        if libre_txt:  # actividad no catalogada: sirve el espacio que la mencione en nombre o descripción
            ids = {e["id"] for e in espacios_que_mencionan(libre_txt, espacios)}
            datos = [d for d in todos if d["espacio"]["id"] in ids]
        else:
            datos = [d for d in todos if sirve_para(d["espacio"], actividad, tag)]
        if not datos:
            return ChatOut(
                respuesta=f"Por ahora no hay espacios para **{que_busca}** en ReservaCampus. "
                          f"Estos son los espacios que existen actualmente:\n{resumen_oferta(espacios)}\n"
                          "Si crees que hace falta uno, puedes sugerirlo a soporte@reservacampus.edu.",
                fuente="reglas", intencion="sin_espacio_para_actividad",
                sugerencias=["¿Qué espacios hay?", "¿Hay cancha para fútbol hoy?"])
    elif menciona_jugar(mensaje):
        recreativos = [e for e in espacios if e.get("tipo") in ("cancha", "recreacion")]
        opciones = "\n".join(f"• **{e['nombre']}**: {e.get('actividades') or e.get('descripcion', '')}"
                             for e in recreativos) or "• (no hay espacios recreativos ni deportivos registrados)"
        return ChatOut(respuesta=f"¿Qué quieres jugar? 🙂 Estos son los espacios para jugar que existen:\n{opciones}",
                       fuente="reglas", intencion="disponibilidad",
                       sugerencias=["¿Hay cancha para fútbol hoy?"])
    else:
        datos = todos

    if personas:
        datos = [d for d in datos if d["espacio"]["capacidad"] >= personas]
    que = f"espacios para {que_busca}" if que_busca else "espacios"
    para = f" para {personas} personas" if personas else ""
    cuando = fecha_texto(fecha)
    sugerencias = ["¿Cómo reservo?", "¿Cuáles son las reglas?"]
    if not datos:
        return ChatOut(respuesta=f"No hay {que} con capacidad{para}. Prueba con un grupo más pequeño.",
                       fuente="reglas", intencion="disponibilidad", sugerencias=["¿Qué espacios hay?"])

    # Con hora concreta: respuesta directa sí/no
    if hora:
        rango = f"{cuando} de {hora:%H:%M} a {fin:%H:%M}"
        libres = [d for d in datos if d["libre"]]
        if libres:
            lineas = [f"• **{d['espacio']['nombre']}** ({d['espacio']['capacidad']} personas, "
                      f"{d['espacio']['ubicacion']})" for d in libres]
            return ChatOut(respuesta=f"✅ Sí, hay {que} libres {rango}{para}:\n" + "\n".join(lineas),
                           fuente="reglas", intencion="disponibilidad", sugerencias=sugerencias)
        lineas = [f"• {d['espacio']['nombre']}: {_ocupacion_texto(d['ocupado']) or 'fuera de su horario'}"
                  for d in datos]
        return ChatOut(respuesta=f"❌ No hay {que} libres {rango}{para}.\n" + "\n".join(lineas) +
                       "\nPrueba con otra hora o pregúntame qué está libre ese día.",
                       fuente="reglas", intencion="disponibilidad", sugerencias=[f"¿Qué está libre {cuando}?"])

    # Sin hora: franjas libres por espacio (si es hoy, desde la hora actual)
    desde = ahora.hour * 60 + ahora.minute if fecha == hoy else 0
    con_hueco, sin_hueco = [], []
    for d in datos:
        e = d["espacio"]
        huecos = franjas_libres(e["hora_apertura"][:5], e["hora_cierre"][:5], d["ocupado"], desde)
        if huecos:
            con_hueco.append(f"• **{e['nombre']}** ({e['capacidad']} personas): libre "
                             + ", ".join(f"{a}-{b}" for a, b in huecos))
        else:
            sin_hueco.append(e["nombre"])
    if not con_hueco:
        return ChatOut(respuesta=f"❌ No quedan {que} libres {cuando}{para}. "
                                 f"Ocupados: {', '.join(sin_hueco)}. Prueba con otro día.",
                       fuente="reglas", intencion="disponibilidad", sugerencias=["¿Y mañana?"])
    respuesta = f"✅ Sí, hay {que} disponibles {cuando}{para}:\n" + "\n".join(con_hueco)
    if sin_hueco:
        respuesta += f"\nSin horario libre {cuando}: {', '.join(sin_hueco)}."
    return ChatOut(respuesta=respuesta, fuente="reglas", intencion="disponibilidad", sugerencias=sugerencias)


async def responder_mis_reservas(token: str | None) -> ChatOut:
    if not token:
        return ChatOut(respuesta="Para ver tus reservas primero inicia sesión. 🔐", fuente="reglas",
                       intencion="mis_reservas")
    datos = await api_reservas("/reservas/mias", {"solo_activas": "true"}, token)
    if datos is None:
        return ChatOut(respuesta="Tu sesión expiró. Vuelve a iniciar sesión.", fuente="reglas", intencion="mis_reservas")
    if not datos:
        return ChatOut(respuesta="No tienes reservas activas. ¿Quieres ver qué hay libre hoy?", fuente="reglas",
                       intencion="mis_reservas", sugerencias=["¿Qué espacios están libres hoy?"])
    lineas = [f"• {r['espacio_nombre']} — {r['fecha']} de {r['hora_inicio'][:5]} a {r['hora_fin'][:5]}" for r in datos]
    return ChatOut(respuesta="Tus reservas activas:\n" + "\n".join(lineas), fuente="reglas", intencion="mis_reservas")


async def listado_espacios() -> list[dict]:
    try:
        return await api_reservas("/espacios") or []
    except Exception:
        return []


@app.get("/health", tags=["sistema"])
def health():
    return {"servicio": "chatbot", "estado": "ok", "ia_configurada": ia.ia_disponible(), "modelo": config.GROQ_MODEL}


@app.post("/chat", response_model=ChatOut, tags=["chat"])
async def chat(datos: ChatIn, request: Request, authorization: str | None = Header(default=None)):
    limitar(request.client.host if request.client else "desconocido")
    # Si menciona una actividad (conocida o definida por el admin en un espacio), se responde con los
    # espacios reales que sirven para ella, salvo que la intención sea otra acción (cancelar, mis reservas...)
    mencion_actividad = (detectar_actividad(datos.mensaje) or menciona_jugar(datos.mensaje)
                         or actividad_libre(datos.mensaje))
    intencion = detectar(datos.mensaje)
    if not mencion_actividad and (not intencion or intencion.nombre in ("disponibilidad", "tipos")):
        try:
            mencion_actividad = bool(etiqueta_mencionada(datos.mensaje, await listado_espacios()))
        except Exception:
            mencion_actividad = False
    if mencion_actividad and (not intencion or intencion.nombre in ("disponibilidad", "tipos", "como_reservar",
                                                                    "saludo")):
        try:
            return await responder_disponibilidad(datos.mensaje)
        except httpx.HTTPError:
            return ChatOut(respuesta="No pude consultar el servicio de reservas en este momento. Intenta de nuevo "
                                     "en unos segundos.", fuente="respaldo", intencion="disponibilidad")
    try:
        if intencion:
            if intencion.nombre == "disponibilidad":
                return await responder_disponibilidad(datos.mensaje)
            if intencion.nombre == "mis_reservas":
                return await responder_mis_reservas(authorization)
            if intencion.nombre in ("horarios", "tipos"):
                espacios = await listado_espacios()
                if intencion.nombre == "horarios":
                    lineas = [f"• {e['nombre']}: {e['hora_apertura'][:5]} a {e['hora_cierre'][:5]}" for e in espacios]
                    texto = "Horarios de atención:\n" + "\n".join(lineas)
                else:
                    lineas = [f"• {e['nombre']} — {TIPOS.get(e['tipo'], e['tipo'])}, {e['capacidad']} personas, "
                              f"{e['ubicacion']}" + (f". Para: {e['actividades']}" if e.get("actividades") else "")
                              for e in espacios]
                    texto = "Estos son los espacios que puedes reservar:\n" + "\n".join(lineas)
                return ChatOut(respuesta=texto, fuente="reglas", intencion=intencion.nombre,
                               sugerencias=["¿Qué espacios están libres hoy?"])
            return ChatOut(respuesta=intencion.respuesta, fuente="reglas", intencion=intencion.nombre,
                           sugerencias=intencion.sugerencias)
    except httpx.HTTPError:
        return ChatOut(respuesta="No pude consultar el servicio de reservas en este momento. Intenta de nuevo en "
                                 "unos segundos.", fuente="respaldo", intencion=intencion.nombre)

    # Sin regla aplicable -> IA (Groq)
    espacios = await listado_espacios()
    espacios_txt = "\n".join(f"- {e['nombre']} ({TIPOS.get(e['tipo'], e['tipo'])}, {e['capacidad']} personas, "
                             f"{e['ubicacion']}, {e['hora_apertura'][:5]}-{e['hora_cierre'][:5]}"
                             + (f"; actividades: {e['actividades']}" if e.get("actividades") else "") + ")"
                             for e in espacios) or "(no disponible)"
    respuesta = await ia.preguntar(datos.mensaje, [h.model_dump() for h in datos.historial], espacios_txt)
    if respuesta:
        return ChatOut(respuesta=respuesta, fuente="ia")
    return ChatOut(respuesta="No estoy seguro de cómo ayudarte con eso. Prueba con alguna de estas opciones:",
                   fuente="respaldo", sugerencias=["¿Qué espacios están libres hoy?", "¿Cómo reservo?",
                                                    "¿Cuáles son las reglas?", "Contacto de soporte"])
