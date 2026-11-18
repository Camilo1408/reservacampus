"""Relaciona lo que el usuario quiere hacer con los espacios que EXISTEN en la plataforma.

No hay respuestas fijas del tipo "no hay espacio para X": se buscan los espacios reales (tipo, nombre,
descripción y actividades permitidas que define el administrador). Si mañana se crea una "Sala Gamer" con la
actividad "videojuegos", el asistente la ofrecerá sin cambiar código.
"""
import re
from dataclasses import dataclass

from .reglas import normalizar

TIPOS = {"sala_estudio": "Salas de estudio", "laboratorio": "Laboratorios", "auditorio": "Auditorio",
         "cancha": "Canchas", "recreacion": "Salas recreativas"}


@dataclass(frozen=True)
class Actividad:
    nombre: str              # cómo se nombra en la respuesta ("videojuegos")
    claves: tuple            # cómo lo dice el usuario
    terminos: tuple          # qué buscar en nombre/descripción/actividades de un espacio
    tipos: tuple = ()        # tipos de espacio que la soportan por naturaleza


# Catálogo de actividades conocidas (ayuda a entender sinónimos). Las actividades nuevas que cree el admin
# también se reconocen aunque no estén aquí, comparando directamente con las etiquetas de cada espacio.
CATALOGO = [
    Actividad("deportes", ("futbol", "baloncesto", "basket", "basquet", "voleibol", "voley", "microfutbol",
                           "futsal", "fut sala", "deporte", "balon", "pelota", "entrenar", "partido de"),
              ("futbol", "baloncesto", "voleibol", "deporte", "cancha"), ("cancha",)),
    Actividad("videojuegos", ("videojuego", "video juego", "videjuego", "consola", "xbox", "playstation",
                              "play station", "nintendo", "gamer", "gaming", "fifa", "fortnite", "esports",
                              "lan party"),
              ("videojuego", "video juego", "consola", "gamer", "gaming", "esports")),
    Actividad("juegos de mesa", ("juego de mesa", "juegos de mesa", "ajedrez", "parques", "domino", "monopoly",
                                 "cartas", "naipes", "jenga"),
              ("juego de mesa", "juegos de mesa", "ajedrez", "parques", "domino")),
    Actividad("estudiar", ("estudiar", "estudio", "repasar", "tarea", "parcial", "examen", "trabajo en grupo",
                           "trabajos en grupo", "reunion", "exposicion", "lectura", "leer"),
              ("estudi", "lectura", "trabajos en grupo", "reunion"), ("sala_estudio",)),
    Actividad("programación y prácticas", ("programar", "programacion", "codigo", "computador", "computadora",
                                           "laboratorio", "practica de redes", "practicas de redes", "redes"),
              ("programacion", "computacion", "redes", "laboratorio"), ("laboratorio",)),
    Actividad("eventos", ("evento", "conferencia", "charla", "seminario", "foro", "ceremonia", "auditorio",
                          "presentacion grande"),
              ("evento", "conferencia", "seminario", "auditorio"), ("auditorio",)),
    Actividad("ver películas", ("pelicula", "cine", "series", "netflix", "proyeccion"),
              ("pelicula", "cine", "proyeccion")),
    Actividad("música y ensayos", ("ensayar", "ensayo", "musica", "banda", "tocar guitarra", "cantar", "karaoke"),
              ("musica", "ensayo", "banda", "karaoke")),
    Actividad("fiestas o celebraciones", ("fiesta", "rumba", "celebracion", "cumpleanos", "farra"),
              ("fiesta", "celebracion")),
    Actividad("comer", ("comer", "almorzar", "almuerzo", "cocinar", "cena", "desayunar"),
              ("comedor", "cocina", "almuerzo")),
    Actividad("descansar", ("dormir", "siesta", "descansar"), ("descanso", "siesta")),
]


def _compacto(t: str) -> str:
    return normalizar(t).replace(" ", "")


def etiquetas(espacio: dict) -> list[str]:
    return [normalizar(x).strip() for x in (espacio.get("actividades") or "").split(",") if x.strip()]


def texto_espacio(e: dict) -> str:
    return normalizar(f"{e.get('nombre', '')} {e.get('descripcion', '')} {e.get('actividades', '')}")


def detectar_actividad(mensaje: str) -> Actividad | None:
    texto = f" {normalizar(mensaje)} "
    puntajes = [(sum(1 for c in a.claves if c in texto), -i, a) for i, a in enumerate(CATALOGO)]
    mejor = max(puntajes, key=lambda x: (x[0], x[1]))
    return mejor[2] if mejor[0] else None


def etiqueta_mencionada(mensaje: str, espacios: list[dict]) -> str | None:
    """Actividad definida por el admin en algún espacio que el usuario menciona literalmente
    (p. ej. 'yoga'). Compara también sin espacios: 'video juegos' == 'videojuegos'."""
    texto, compacto = f" {normalizar(mensaje)} ", _compacto(mensaje)
    for e in espacios:
        for original in (x.strip() for x in (e.get("actividades") or "").split(",") if x.strip()):
            tag = normalizar(original).strip()
            if len(tag) >= 3 and (re.search(rf"\b{re.escape(tag)}", texto) or tag.replace(" ", "") in compacto):
                return original  # tal como lo escribió el admin (con tildes)
    return None


def sirve_para(espacio: dict, actividad: Actividad | None, tag: str | None) -> bool:
    if tag and normalizar(tag).strip() in etiquetas(espacio):
        return True
    if actividad:
        if espacio.get("tipo") in actividad.tipos:
            return True
        texto = texto_espacio(espacio)
        compacto = texto.replace(" ", "")
        return any(t in texto or t.replace(" ", "") in compacto for t in actividad.terminos)
    return False


_NO_ACTIVIDAD = {"hoy", "manana", "pasado", "el", "la", "los", "las", "mi", "mis", "un", "una", "que", "cuando",
                 "reservar", "reserva", "personas", "nosotros", "todos", "grupo", "esta", "este", "semana",
                 "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo", "jugar", "ahora"}


def actividad_libre(mensaje: str) -> str | None:
    """Actividad no catalogada escrita como 'para (hacer|practicar|jugar) X' (p. ej. 'para hacer yoga')."""
    m = re.search(r"\bpara (?:hacer |practicar |jugar |tener |realizar )?(?:un |una |el |la )?([a-zn][a-zn ]{2,30})",
                  normalizar(mensaje))
    if not m:
        return None
    palabras = []
    for p in m.group(1).split():
        if p in _NO_ACTIVIDAD or p.isdigit() or p in ("a", "de", "con", "en", "y", "o"):
            break
        palabras.append(p)
    candidato = " ".join(palabras[:3])
    return candidato if len(candidato) >= 3 and candidato not in _NO_ACTIVIDAD else None


def espacios_que_mencionan(texto: str, espacios: list[dict]) -> list[dict]:
    return [e for e in espacios if texto in texto_espacio(e)]


_PIDE_ESPACIO = re.compile(
    r"\b(hay|habra|existe|libre|libres|disponib\w*|desocupad\w*|espacio|espacios|lugar|sala|salas|cancha|canchas|"
    r"laboratorio|auditorio|donde|necesito|necesitamos|busco|buscamos|quiero|queremos|reservar|reserva|"
    r"ocupad\w*|para jugar|para hacer|para practicar|tienen|ofrecen)\b")


def pide_espacio(mensaje: str) -> bool:
    """¿El mensaje busca un lugar/disponibilidad (y no solo menciona una actividad)?"""
    return bool(_PIDE_ESPACIO.search(normalizar(mensaje)))


def menciona_jugar(mensaje: str) -> bool:
    return bool(re.search(r"\bjug(ar|amos|ando|amos a)\b", normalizar(mensaje)))


def resumen_oferta(espacios: list[dict]) -> str:
    """Lista lo que SÍ existe, agrupado por tipo, con sus actividades."""
    por_tipo: dict[str, list[str]] = {}
    for e in espacios:
        acts = f" ({e['actividades']})" if e.get("actividades") else ""
        por_tipo.setdefault(e.get("tipo", ""), []).append(f"{e['nombre']}{acts}")
    return "\n".join(f"• **{TIPOS.get(t, t)}**: {'; '.join(v)}" for t, v in por_tipo.items())
