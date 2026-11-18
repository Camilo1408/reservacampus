"""Diagramas del proyecto en Mermaid. Ejecutar: python docs/fuentes/diagramas.py  -> docs/img/diagramas/*.png"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SALIDA = Path(__file__).resolve().parents[1] / "img" / "diagramas"

DIAGRAMAS = {
    "01_c4_contexto": """
flowchart LR
  est["👤 Estudiante<br/><small>Reserva espacios, confirma llegada,<br/>reporta ocupación, usa el chat</small>"]
  adm["👤 Administrador<br/><small>Gestiona espacios, horarios,<br/>usuarios, sanciones y reportes</small>"]
  sis["🏫 ReservaCampus<br/><small>Plataforma distribuida de reserva<br/>de espacios universitarios</small>"]
  groq["🤖 Groq API<br/><small>Modelo de lenguaje (IA)</small>"]
  brevo["✉️ Brevo<br/><small>Envío de correos (API HTTP)</small>"]
  gh["⚙️ GitHub Actions<br/><small>CI y programador de tareas</small>"]
  est -- "HTTPS (navegador)" --> sis
  adm -- "HTTPS (navegador)" --> sis
  sis -- "REST · preguntas abiertas" --> groq
  sis -- "REST · correos transaccionales" --> brevo
  gh -- "POST /tareas/ejecutar cada 10 min" --> sis
  classDef persona fill:#3b4cca,color:#fff,stroke:#2a38a6
  classDef sistema fill:#1b2a8a,color:#fff,stroke:#111
  classDef externo fill:#eceef4,color:#15192b,stroke:#9aa0b8
  class est,adm persona
  class sis sistema
  class groq,brevo,gh externo
""",
    "02_c4_contenedores": """
flowchart TB
  user["👤 Usuarios (navegador)"]
  subgraph render["Render · nube (plan gratuito)          "]
    web["🖥️ Frontend<br/><small>HTML/CSS/JS · Static Site</small>"]
    auth["🔐 auth-service<br/><small>FastAPI · usuarios, JWT,<br/>estados, recuperación</small>"]
    res["📅 reservas-service<br/><small>FastAPI · espacios, horarios,<br/>reservas, sanciones, programador</small>"]
    notif["🔔 notificaciones-service<br/><small>FastAPI · consumidor de eventos,<br/>notificaciones, alertas</small>"]
    chat["💬 chatbot-service<br/><small>FastAPI · reglas + IA</small>"]
    redis[("🧵 Redis Streams<br/><small>eventos.reservas</small>")]
    pg[("🐘 PostgreSQL<br/><small>tablas por servicio</small>")]
  end
  groq["🤖 Groq"]
  brevo["✉️ Brevo"]
  user --> web
  web -- "REST + JWT" --> auth & res & notif & chat
  res -- "REST: estado de la cuenta (/me)" --> auth
  chat -- "REST: disponibilidad" --> res
  chat -- "REST" --> groq
  auth -- "XADD eventos" --> redis
  res -- "XADD eventos" --> redis
  redis -- "XREADGROUP" --> notif
  notif -- "API HTTP" --> brevo
  auth & res & notif --> pg
  classDef svc fill:#3b4cca,color:#fff,stroke:#2a38a6
  classDef dato fill:#fff3e0,color:#7a4100,stroke:#ffb547
  classDef ext fill:#eceef4,color:#15192b,stroke:#9aa0b8
  class web,auth,res,notif,chat svc
  class redis,pg dato
  class groq,brevo ext
""",
    "03_c4_componentes_reservas": """
flowchart TB
  subgraph reservas["reservas-service (FastAPI)"]
    api["main.py<br/><small>Endpoints de espacios, horarios,<br/>reservas, estadísticas</small>"]
    inc["incidencias.py<br/><small>Llegada, reportes, sanciones,<br/>vistas admin por usuario</small>"]
    reglas["reglas.py<br/><small>Reglas de negocio puras<br/>(horario, duración, capacidad)</small>"]
    sanc["sanciones.py<br/><small>Escalamiento 1d/3d/7d/indefinida</small>"]
    tareas["tareas.py<br/><small>Programador: recordatorios,<br/>avisos e inasistencias</small>"]
    deps["deps.py<br/><small>Validación JWT y roles</small>"]
    ev["eventos.py<br/><small>Publicador Redis Streams</small>"]
    orm["models.py + database.py<br/><small>SQLAlchemy ORM</small>"]
  end
  api --> reglas & deps & ev & orm
  inc --> sanc & deps & ev & orm
  tareas --> sanc & ev & orm
  sanc --> ev & orm
  ev --> redis[("Redis Streams")]
  orm --> pg[("PostgreSQL")]
  classDef c fill:#e8ecff,color:#15192b,stroke:#3b4cca
  class api,inc,reglas,sanc,tareas,deps,ev,orm c
""",
    "04_despliegue": """
flowchart LR
  dev["💻 Desarrollador"] -- "git push" --> gh["GitHub<br/>Camilo1408/reservacampus"]
  gh -- "CI: pytest + PostgreSQL 16 + Playwright" --> ci["GitHub Actions"]
  gh -- "Blueprint render.yaml" --> rnd
  ci -- "cron cada 10 min" --> resv
  subgraph rnd["Render · región Oregon"]
    st["Static Site<br/>reservacampus-web-gcr3"]
    a["Web Service<br/>auth-gcr3"]
    resv["Web Service<br/>reservas-gcr3"]
    n["Web Service<br/>notificaciones-gcr3"]
    c["Web Service<br/>chatbot-gcr3"]
    kv[("Key Value<br/>cola-gcr3")]
    db[("PostgreSQL 18<br/>db-gcr3")]
  end
  a & resv & n --> db
  a & resv --> kv --> n
""",
    "05_secuencia_reserva": """
sequenceDiagram
  autonumber
  actor E as Estudiante
  participant W as Frontend
  participant R as reservas-service
  participant A as auth-service
  participant Q as Redis Streams
  participant N as notificaciones-service
  participant B as Brevo
  E->>W: Elige espacio, fecha y hora
  W->>R: POST /reservas (Bearer JWT)
  R->>R: Valida JWT, sanción vigente, reglas y solapamientos (SELECT ... FOR UPDATE)
  R->>A: GET /me (estado de la cuenta)
  A-->>R: activo
  R->>R: INSERT reserva
  R->>Q: XADD reserva.creada
  R-->>W: 201 Reserva confirmada
  Q-->>N: XREADGROUP (grupo notificaciones)
  N->>N: Crea notificación (idempotente)
  N->>B: POST /v3/smtp/email
  N->>Q: XACK
  W->>N: GET /notificaciones
""",
    "06_secuencia_chatbot": """
sequenceDiagram
  autonumber
  actor U as Usuario
  participant W as Widget de chat
  participant C as chatbot-service
  participant R as reservas-service
  participant G as Groq (IA)
  U->>W: "¿hay cancha para fútbol mañana a las 4?"
  W->>C: POST /chat {mensaje, historial}
  C->>C: Límite de mensajes · detectar intención y actividad
  alt Regla aplicable (disponibilidad, mis reservas, reglas…)
    C->>R: GET /disponibilidad?fecha&hora
    R-->>C: Espacios y ocupación
    C-->>W: Respuesta por reglas (sí/no + franjas)
  else Pregunta abierta
    C->>R: GET /espacios (contexto)
    C->>G: chat/completions (prompt de sistema + espacios)
    G-->>C: Respuesta
    C-->>W: Respuesta con IA
  end
""",
    "07_linea_tiempo_llegada": """
flowchart LR
  a["−10 min<br/>📧 Recordatorio<br/>con botón Confirmar"] --> b["0 min<br/>📧 Confirma que<br/>estás en el espacio"]
  b --> c["+10 min<br/>📧 Último aviso<br/>· se habilita Reportar"]
  c --> d{"+20 min<br/>¿Confirmó?"}
  d -- "Sí" --> e["✅ Reserva en uso"]
  d -- "No" --> f["❌ Inasistencia<br/>+ sanción escalonada"]
  classDef ok fill:#e5f6ee,stroke:#17915a
  classDef mal fill:#fdecef,stroke:#c8364a
  class e ok
  class f mal
""",
    "08_escalamiento_sanciones": """
flowchart LR
  i["Infracción<br/><small>no entregar el espacio<br/>o no confirmar llegada</small>"] --> n1
  n1["Nivel 1<br/>sin reservar el día siguiente"] -- "reincide" --> n2["Nivel 2<br/>3 días"]
  n2 -- "reincide" --> n3["Nivel 3<br/>1 semana"]
  n3 -- "reincide" --> n4["Nivel 4<br/>suspensión hasta que<br/>el admin la levante"]
  classDef a fill:#fff8e1,stroke:#9a6b00
  classDef b fill:#fff3e0,stroke:#b25e00
  classDef c fill:#fdecef,stroke:#c8364a
  classDef d fill:#c8364a,color:#fff,stroke:#8a1f2e
  class n1 a
  class n2 b
  class n3 c
  class n4 d
""",
    "09_estados_reserva": """
stateDiagram-v2
  [*] --> confirmada: POST /reservas
  confirmada --> cancelada: el usuario cancela
  confirmada --> revocada: el admin revoca (con justificación)
  confirmada --> inasistencia: +20 min sin confirmar llegada
  confirmada --> confirmada: confirma llegada / reporta ocupación
  cancelada --> [*]
  revocada --> [*]
  inasistencia --> [*]
""",
    "10_modelo_datos": """
erDiagram
  USUARIOS {
    int id PK
    string nombre
    string email UK
    string password_hash
    string rol
    string estado
    string motivo_estado
    string reset_token_hash
    datetime reset_expira
  }
  ESPACIOS {
    int id PK
    string nombre UK
    string tipo
    int capacidad
    string ubicacion
    string actividades
    time hora_apertura
    time hora_cierre
    bool activo
  }
  RESERVAS {
    int id PK
    int espacio_id FK
    int usuario_id
    date fecha
    time hora_inicio
    time hora_fin
    string estado
    datetime llegada_confirmada_en
    string motivo_revocacion
  }
  HORARIOS_CLASE {
    int id PK
    int espacio_id FK
    int dia_semana
    time hora_inicio
    time hora_fin
    string materia
  }
  SANCIONES {
    int id PK
    int usuario_id
    int nivel
    string tipo
    datetime hasta
    string estado
  }
  REPORTES {
    int id PK
    int reserva_id
    int reportante_id
    int reportado_id
    int sancion_id
    string estado
  }
  NOTIFICACIONES {
    int id PK
    int usuario_id
    string tipo
    string titulo
    bool leida
    bool correo_enviado
    string evento_id UK
  }
  ESPACIOS ||--o{ RESERVAS : tiene
  ESPACIOS ||--o{ HORARIOS_CLASE : bloquea
  USUARIOS ||..o{ RESERVAS : "hace (otro servicio)"
  USUARIOS ||..o{ SANCIONES : recibe
  USUARIOS ||..o{ NOTIFICACIONES : recibe
  RESERVAS ||--o| REPORTES : genera
  REPORTES ||--o| SANCIONES : origina
""",
    "11_cicd": """
flowchart LR
  p["git push a main"] --> u["Pruebas unitarias x4<br/><small>pytest + PostgreSQL 16</small>"]
  u --> e["Pruebas E2E<br/><small>Playwright · sistema completo</small>"]
  e --> ok{"¿Todo verde?"}
  ok -- "sí" --> d["Despliegue en Render"]
  ok -- "no" --> x["Se corrige antes de desplegar"]
""",
}

HTML = """<!doctype html><html><head><meta charset="utf-8">
<style>body{margin:0;background:#fff;font-family:Arial,sans-serif} #d{display:inline-block;padding:24px}</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"></script></head>
<body><div id="d"><pre class="mermaid">%s</pre></div>
<script>mermaid.initialize({startOnLoad:true, theme:'default', securityLevel:'loose',
 themeVariables:{fontFamily:'Arial', fontSize:'16px'}, flowchart:{htmlLabels:true, curve:'basis', useMaxWidth:false},
 sequence:{useMaxWidth:false}, er:{useMaxWidth:false}, state:{useMaxWidth:false}, gantt:{useMaxWidth:false}});</script></body></html>"""


def main(solo=None):
    SALIDA.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(device_scale_factor=3, viewport={"width": 2400, "height": 1200})
        for nombre, codigo in DIAGRAMAS.items():
            if solo and nombre not in solo:
                continue
            pg.set_content(HTML % codigo.strip())
            pg.wait_for_selector("#d svg", timeout=30000)
            pg.locator("#d").screenshot(path=str(SALIDA / f"{nombre}.png"))
            print("ok", nombre)
        b.close()


if __name__ == "__main__":
    main(sys.argv[1:] or None)
