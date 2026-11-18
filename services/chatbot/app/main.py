import time as _time
from collections import defaultdict, deque
from datetime import datetime, time, timedelta
from typing import Literal

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import config, ia
from .reglas import NOMBRE_TIPO, actividad_no_disponible, detectar, menciona_jugar, extraer_fecha, extraer_hora, extraer_personas, extraer_tipo, franjas_libres

app = FastAPI(
    title="Chatbot Service · ReservaCampus",
    description="Asistente virtual híbrido: motor de reglas determinista + IA (Groq) como respaldo.",
    version="1.0.0",
    root_path=config.ROOT_PATH,
)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

TIPOS = {"sala_estudio": "Sala de estudio", "laboratorio": "Laboratorio", "auditorio": "Auditorio", "cancha": "Cancha"}
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


def responder_actividad_no_disponible(actividad: str) -> ChatOut:
    return ChatOut(
        respuesta=f"❌ No hay espacios para {actividad} en ReservaCampus. Los espacios son para actividades "
                  "académicas y deportivas:\n"
                  "• **Salas de estudio**: estudiar, reuniones y trabajos en grupo\n"
                  "• **Laboratorios**: prácticas de computación y redes\n"
                  "• **Auditorio**: eventos y conferencias\n"
                  "• **Cancha**: fútbol, baloncesto y voleibol",
        fuente="reglas", intencion="actividad_no_disponible",
        sugerencias=["¿Hay cancha para fútbol hoy?", "¿Qué salas de estudio están libres?"])


async def responder_disponibilidad(mensaje: str) -> ChatOut:
    ahora = datetime.now(config.ZONA)
    hoy = ahora.date()
    fecha = extraer_fecha(mensaje, hoy)
    hora = extraer_hora(mensaje)
    tipo = extraer_tipo(mensaje)
    personas = extraer_personas(mensaje)
    if not tipo and menciona_jugar(mensaje):
        return ChatOut(respuesta="¿Qué quieres jugar? 🙂 Para deportes como fútbol, baloncesto o voleibol tenemos "
                                 "la **Cancha Múltiple**. Para otro tipo de juegos (como videojuegos) no hay espacios "
                                 "en la plataforma.", fuente="reglas", intencion="disponibilidad",
                       sugerencias=["¿Hay cancha para fútbol hoy?", "¿Hay cancha para baloncesto mañana?"])
    params = {"fecha": fecha.isoformat()}
    if tipo:
        params["tipo"] = tipo
    if hora:
        fin = (datetime.combine(fecha, hora) + timedelta(hours=1)).time()
        params |= {"hora_inicio": hora.strftime("%H:%M"), "hora_fin": fin.strftime("%H:%M")}
    datos = await api_reservas("/disponibilidad", params)
    if personas:
        datos = [d for d in datos if d["espacio"]["capacidad"] >= personas]

    que = NOMBRE_TIPO.get(tipo, "espacios")
    para = f" para {personas} personas" if personas else ""
    cuando = fecha_texto(fecha)
    sugerencias = ["¿Cómo reservo?", "¿Cuáles son las reglas?"]

    if not datos:
        return ChatOut(respuesta=f"No hay {que} disponibles{para} en la plataforma. Prueba con otro tipo de espacio.",
                       fuente="reglas", intencion="disponibilidad", sugerencias=["¿Qué espacios hay?"])

    # Con hora concreta: respuesta directa sí/no
    if hora:
        rango = f"{cuando} de {hora:%H:%M} a {fin:%H:%M}"
        libres = [d for d in datos if d["libre"]]
        if libres:
            lineas = [f"• {d['espacio']['nombre']} ({d['espacio']['capacidad']} personas, {d['espacio']['ubicacion']})"
                      for d in libres]
            return ChatOut(respuesta=f"✅ Sí, hay {que} libres {rango}{para}:\n" + "\n".join(lineas),
                           fuente="reglas", intencion="disponibilidad", sugerencias=sugerencias)
        lineas = [f"• {d['espacio']['nombre']}: {_ocupacion_texto(d['ocupado']) or 'fuera de su horario'}"
                  for d in datos]
        return ChatOut(respuesta=f"❌ No hay {que} libres {rango}{para}.\n" + "\n".join(lineas) +
                       "\nPrueba con otra hora o pregúntame qué está libre ese día.",
                       fuente="reglas", intencion="disponibilidad",
                       sugerencias=[f"¿Qué {que} están libres {cuando}?"])

    # Sin hora: franjas libres por espacio (si es hoy, desde la hora actual)
    desde = ahora.hour * 60 + ahora.minute if fecha == hoy else 0
    con_hueco, sin_hueco = [], []
    for d in datos:
        e = d["espacio"]
        huecos = franjas_libres(e["hora_apertura"][:5], e["hora_cierre"][:5], d["ocupado"], desde)
        if huecos:
            texto = ", ".join(f"{a}-{b}" for a, b in huecos)
            con_hueco.append(f"• **{e['nombre']}** ({e['capacidad']} personas): libre {texto}")
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
    no_disponible = actividad_no_disponible(datos.mensaje)
    if no_disponible:
        return responder_actividad_no_disponible(no_disponible)
    intencion = detectar(datos.mensaje)
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
                              f"{e['ubicacion']}" for e in espacios]
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
                             f"{e['ubicacion']}, {e['hora_apertura'][:5]}-{e['hora_cierre'][:5]})"
                             for e in espacios) or "(no disponible)"
    respuesta = await ia.preguntar(datos.mensaje, [h.model_dump() for h in datos.historial], espacios_txt)
    if respuesta:
        return ChatOut(respuesta=respuesta, fuente="ia")
    return ChatOut(respuesta="No estoy seguro de cómo ayudarte con eso. Prueba con alguna de estas opciones:",
                   fuente="respaldo", sugerencias=["¿Qué espacios están libres hoy?", "¿Cómo reservo?",
                                                    "¿Cuáles son las reglas?", "Contacto de soporte"])
