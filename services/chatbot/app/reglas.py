"""Motor de reglas determinista: detecta la intención del usuario por palabras clave."""
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9: ]", " ", t)


@dataclass
class Intencion:
    nombre: str
    claves: list[str]
    prioridad: int = 0
    respuesta: str = ""
    sugerencias: list[str] = field(default_factory=list)
    max_palabras: int | None = None  # p.ej. un saludo solo si el mensaje es corto


INTENCIONES = [
    Intencion("disponibilidad", ["disponible", "disponibles", "disponibilidad", "libre", "libres", "desocupad",
                                 "hay espacio", "hay sala", "esta ocupad", "ocupado", "ocupada"], prioridad=9),
    Intencion("mis_reservas", ["mis reservas", "mi reserva", "tengo reserva", "tengo alguna", "reserve",
                               "mis proximas"], prioridad=8),
    Intencion("cancelar", ["cancelar", "cancelo", "anular", "anulo", "eliminar reserva", "borrar reserva"], prioridad=10,
              respuesta="Para cancelar una reserva ve a **Mis reservas**, ubica la reserva y pulsa **Cancelar**. "
                        "El horario queda libre de inmediato y recibirás una notificación de confirmación."),
    Intencion("como_reservar", ["como reserv", "reservar", "hacer una reserva", "apartar", "separar una",
                                "agendar"], prioridad=6,
              respuesta="Reservar es fácil:\n1. Inicia sesión.\n2. En **Espacios** elige el que necesitas.\n"
                        "3. Pulsa **Reservar**, escoge fecha, hora de inicio y fin, y número de asistentes.\n"
                        "4. Confirma. Te llegará una notificación con el detalle.",
              sugerencias=["¿Qué espacios están libres hoy?", "¿Cuáles son las reglas?"]),
    Intencion("reglas", ["regla", "reglas", "politica", "maximo", "maxima", "minimo", "cuanto tiempo",
                         "limite", "duracion", "anticipacion", "cuantas reservas"], prioridad=5,
              respuesta="Reglas de reserva:\n• Bloques de 30 minutos, mínimo 30 min y máximo 3 horas.\n"
                        "• Hasta 30 días de anticipación.\n• Máximo 3 reservas activas por persona.\n"
                        "• No se puede superar la capacidad del espacio.\n"
                        "• Si no vas a usar el espacio, cancélalo para que otros lo aprovechen."),
    Intencion("horarios", ["horario", "horarios", "a que hora abre", "abre", "cierra", "apertura", "cierre"],
              prioridad=4),
    Intencion("tipos", ["tipos de espacio", "que espacios", "cuales espacios", "laboratorio", "auditorio",
                        "cancha", "salas de estudio", "lista de espacios"], prioridad=3),
    Intencion("contacto", ["contacto", "soporte", "correo", "telefono", "humano", "persona", "queja"], prioridad=2,
              respuesta="Puedes escribir a **soporte@reservacampus.edu** o acercarte a la oficina de "
                        "Bienestar Universitario (Bloque A, piso 1) de lunes a viernes, 8:00 a 17:00."),
    Intencion("ayuda", ["ayuda", "que puedes hacer", "opciones", "menu", "como funciona"], prioridad=1,
              respuesta="Puedo ayudarte con:\n• Ver qué espacios están libres (hoy, mañana o a una hora)\n"
                        "• Consultar tus reservas\n• Explicarte cómo reservar o cancelar\n"
                        "• Reglas y horarios de los espacios\nTambién puedo responder otras dudas con IA.",
              sugerencias=["¿Qué está libre mañana a las 10?", "Mis reservas", "¿Cómo reservo?"]),
    Intencion("saludo", ["hola", "buenas", "buenos dias", "buenas tardes", "buenas noches", "hey", "que tal"],
              prioridad=0, max_palabras=4,
              respuesta="¡Hola! 👋 Soy el asistente de ReservaCampus. ¿En qué te ayudo?",
              sugerencias=["¿Qué espacios están libres hoy?", "¿Cómo reservo?", "Mis reservas"]),
    Intencion("despedida", ["gracias", "chao", "adios", "hasta luego", "nos vemos"], prioridad=0, max_palabras=5,
              respuesta="¡Con gusto! Si necesitas algo más, aquí estaré. 😊"),
]


def detectar(mensaje: str) -> Intencion | None:
    texto = normalizar(mensaje)
    palabras = len(texto.split())
    mejor, mejor_puntaje = None, (0, -1)
    for it in INTENCIONES:
        if it.max_palabras and palabras > it.max_palabras:
            continue
        aciertos = sum(1 for c in it.claves if c in texto)
        if aciertos and (aciertos, it.prioridad) > mejor_puntaje:
            mejor, mejor_puntaje = it, (aciertos, it.prioridad)
    return mejor


DIAS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}


def extraer_fecha(mensaje: str, hoy: date) -> date:
    t = normalizar(mensaje)
    if "pasado manana" in t:
        return hoy + timedelta(days=2)
    if "manana" in t and "de la manana" not in t.replace("manana a", "").replace("manana en", ""):
        return hoy + timedelta(days=1)
    for nombre, idx in DIAS.items():
        if nombre in t:
            delta = (idx - hoy.weekday()) % 7 or 7
            return hoy + timedelta(days=delta)
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", mensaje)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    return hoy


def extraer_hora(mensaje: str) -> time | None:
    """Reconoce '10:30', 'a las 3', '3pm', '15 horas'. Horas 1-6 sin am/pm se asumen de la tarde."""
    t = normalizar(mensaje)
    m = re.search(r"\b(\d{1,2}):(\d{2})\b", t) or re.search(r"\b(\d{1,2})\s*(am|pm|de la tarde|de la manana|h|horas)\b", t) \
        or re.search(r"\ba las (\d{1,2})\b", t)
    if not m:
        return None
    h = int(m.group(1))
    sufijo = m.group(2) if m.lastindex and m.lastindex >= 2 else ""
    minutos = int(sufijo) if sufijo and sufijo.isdigit() else 0
    if sufijo in ("pm", "de la tarde") and h < 12:
        h += 12
    elif not sufijo and 1 <= h <= 6:
        h += 12
    if not 0 <= h <= 23 or not 0 <= minutos <= 59:
        return None
    return time(h, minutos)


def ahora_local(zona) -> datetime:
    return datetime.now(zona)
