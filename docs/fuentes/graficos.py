"""Gráficos del informe de pruebas a partir de los resultados reales de k6, cobertura y auditoría.

Uso: python docs/fuentes/graficos.py   ->  docs/img/graficos/*.png  y  docs/fuentes/metricas.json
"""
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
K6 = RAIZ / "tests" / "carga" / "resultados"
OUT = RAIZ / "docs" / "img" / "graficos"
OUT.mkdir(parents=True, exist_ok=True)

AZUL, AZUL2, ROJO, VERDE, AMBAR, GRIS = "#3b4cca", "#9aa6f0", "#c8364a", "#17915a", "#ffb547", "#5d6480"
plt.rcParams.update({"font.family": "Arial", "font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "axes.titlesize": 13, "figure.dpi": 150})
ENDPOINTS = ["disponibilidad", "espacios", "mis_reservas", "login", "chat"]
NOMBRE = {"disponibilidad": "GET /disponibilidad", "espacios": "GET /espacios", "mis_reservas": "GET /reservas/mias",
          "login": "POST /login", "chat": "POST /chat"}


def percentil(v, p):
    v = sorted(v)
    if not v:
        return 0
    k = (len(v) - 1) * p / 100
    f = int(k)
    return v[f] + (v[min(f + 1, len(v) - 1)] - v[f]) * (k - f)


def leer_serie(nombre):
    """Agrupa por ventanas de 5 s: latencias (ms) por endpoint y VUs."""
    lat, vus, por_ep = defaultdict(list), {}, defaultdict(list)
    t0 = None
    with open(K6 / f"{nombre}_serie.json", encoding="utf-8") as f:
        for linea in f:
            d = json.loads(linea)
            if d.get("type") != "Point":
                continue
            t = datetime.fromisoformat(d["data"]["time"].replace("Z", "+00:00")).timestamp()
            t0 = t0 or t
            ventana = int((t - t0) // 5) * 5
            if d["metric"] == "http_req_duration":
                ep = d["data"]["tags"].get("endpoint")
                if ep:
                    lat[ventana].append(d["data"]["value"])
                    por_ep[ep].append(d["data"]["value"])
            elif d["metric"] == "vus":
                vus[ventana] = d["data"]["value"]
    return lat, vus, por_ep


def resumen(nombre):
    d = json.loads((K6 / f"{nombre}_resumen.json").read_text(encoding="utf-8"))["metrics"]
    return {"p95_ms": d["http_req_duration"]["p(95)"], "med_ms": d["http_req_duration"]["med"],
            "avg_ms": d["http_req_duration"]["avg"], "rps": d["http_reqs"]["rate"], "total": d["http_reqs"]["count"],
            "fallidas": d["http_req_failed"]["value"], "checks": d["checks"]["value"] if "checks" in d else None,
            "vus_max": d["vus_max"]["max"]}


metricas = {"k6": {}, "k6_endpoints": {}}
for nombre in ["carga", "carga_despues", "estres", "estres_despues"]:
    metricas["k6"][nombre] = resumen(nombre)
    _, _, por_ep = leer_serie(nombre)
    metricas["k6_endpoints"][nombre] = {ep: {"p50": percentil(v, 50), "p95": percentil(v, 95), "n": len(v)}
                                        for ep, v in por_ep.items()}


# 1-2. Latencia p95 en el tiempo vs usuarios virtuales (antes y después)
def grafico_tiempo(escenario, titulo, archivo):
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax2 = ax.twinx()
    for nombre, color, etiqueta in [(escenario, ROJO, "Antes (N+1)"), (f"{escenario}_despues", AZUL, "Después (optimizado)")]:
        lat, vus, _ = leer_serie(nombre)
        xs = sorted(lat)
        ax.plot(xs, [percentil(lat[x], 95) / 1000 for x in xs], color=color, lw=2.2, label=f"p95 {etiqueta}")
        if nombre.endswith("_despues"):
            xv = sorted(vus)
            ax2.fill_between(xv, [vus[x] for x in xv], color=GRIS, alpha=0.12, step="mid", label="Usuarios virtuales")
    ax.set_xlabel("Tiempo de la prueba (s)")
    ax.set_ylabel("Latencia p95 (s)")
    ax2.set_ylabel("Usuarios virtuales", color=GRIS)
    ax2.spines["right"].set_visible(True)
    ax.axhline(2, color=AMBAR, ls="--", lw=1.3)
    ax.text(ax.get_xlim()[1] * 0.99, 2.05, "Umbral 2 s", color="#9a6b00", ha="right", fontsize=9)
    ax.set_title(titulo)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / archivo)
    plt.close(fig)


grafico_tiempo("carga", "Prueba de carga (hasta 20 usuarios): latencia p95 en el tiempo", "01_carga_tiempo.png")
grafico_tiempo("estres", "Prueba de estrés (hasta 60 usuarios): latencia p95 en el tiempo", "02_estres_tiempo.png")


# 3. p95 por endpoint antes / después
def barras_endpoints(escenario, archivo, titulo):
    antes, despues = metricas["k6_endpoints"][escenario], metricas["k6_endpoints"][f"{escenario}_despues"]
    eps = [e for e in ENDPOINTS if e in antes and e in despues]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    x = range(len(eps))
    b1 = ax.bar([i - 0.2 for i in x], [antes[e]["p95"] / 1000 for e in eps], 0.4, color=ROJO, label="Antes")
    b2 = ax.bar([i + 0.2 for i in x], [despues[e]["p95"] / 1000 for e in eps], 0.4, color=AZUL, label="Después")
    for barras in (b1, b2):
        for b in barras:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.04, f"{b.get_height():.2f}", ha="center", fontsize=9)
    ax.set_xticks(list(x), [NOMBRE[e] for e in eps], fontsize=9)
    ax.set_ylabel("Latencia p95 (s)")
    ax.set_title(titulo)
    ax.axhline(2, color=AMBAR, ls="--", lw=1.2)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / archivo)
    plt.close(fig)


barras_endpoints("carga", "03_carga_endpoints.png", "Carga: latencia p95 por endpoint")
barras_endpoints("estres", "04_estres_endpoints.png", "Estrés: latencia p95 por endpoint")

# 5. Throughput y p95 global
fig, axs = plt.subplots(1, 2, figsize=(9, 3.8))
etq = ["Carga\nantes", "Carga\ndespués", "Estrés\nantes", "Estrés\ndespués"]
nombres = ["carga", "carga_despues", "estres", "estres_despues"]
cols = [ROJO, AZUL, ROJO, AZUL]
for ax, clave, titulo, fmt in [(axs[0], "rps", "Rendimiento (peticiones/s)", "{:.1f}"),
                               (axs[1], "p95_ms", "Latencia p95 global (s)", "{:.2f}")]:
    vals = [metricas["k6"][n][clave] / (1000 if clave == "p95_ms" else 1) for n in nombres]
    bs = ax.bar(etq, vals, color=cols)
    for b, v in zip(bs, vals):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() * 1.02, fmt.format(v), ha="center", fontsize=10)
    ax.set_title(titulo)
fig.tight_layout()
fig.savefig(OUT / "05_rendimiento_global.png")
plt.close(fig)

# 6. Cobertura por servicio
cob = {}
for s in ["auth", "reservas", "notificaciones", "chatbot"]:
    t = json.loads((RAIZ / "tests" / "resultados" / f"cobertura_{s}.json").read_text(encoding="utf-8"))["totals"]
    cob[s] = {"porcentaje": round(t["percent_covered"], 1), "lineas": t["num_statements"]}
metricas["cobertura"] = cob
fig, ax = plt.subplots(figsize=(8, 3.6))
bs = ax.barh([f"{s}-service" for s in cob], [c["porcentaje"] for c in cob.values()], color=AZUL)
for b, c in zip(bs, cob.values()):
    ax.text(b.get_width() + 1, b.get_y() + b.get_height() / 2, f"{c['porcentaje']} %  ({c['lineas']} líneas)",
            va="center", fontsize=10)
ax.axvline(80, color=AMBAR, ls="--", lw=1.2)
ax.set_xlim(0, 115)
ax.set_xlabel("Cobertura de líneas (%)")
ax.set_title("Cobertura de código de las pruebas unitarias")
ax.invert_yaxis()
fig.tight_layout()
fig.savefig(OUT / "06_cobertura.png")
plt.close(fig)

# 7. Auditoría OWASP por categoría
owasp = json.loads((RAIZ / "tests" / "seguridad" / "resultados" / "owasp.json").read_text(encoding="utf-8"))
metricas["owasp"] = owasp
por_cat = defaultdict(lambda: [0, 0])
for c in owasp["controles"]:
    por_cat[c["owasp"]][0 if c["ok"] else 1] += 1
cats = sorted(por_cat)
fig, ax = plt.subplots(figsize=(8, 3.6))
ok = [por_cat[c][0] for c in cats]
mal = [por_cat[c][1] for c in cats]
ax.bar(cats, ok, color=VERDE, label="Superado")
ax.bar(cats, mal, bottom=ok, color=ROJO, label="Fallido")
for i, c in enumerate(cats):
    ax.text(i, ok[i] + mal[i] + 0.1, f"{ok[i]}/{ok[i] + mal[i]}", ha="center", fontsize=10)
ax.set_ylabel("Controles")
ax.set_title("Auditoría de seguridad automatizada (OWASP Top 10 + LLM)")
ax.legend(frameon=False)
fig.tight_layout()
fig.savefig(OUT / "07_owasp.png")
plt.close(fig)

# 8. Pirámide de pruebas
piramide = {"Unitarias / API (pytest)": 0, "End-to-end (Playwright)": 21, "Seguridad (auditoría)": len(owasp["controles"]),
            "Rendimiento (escenarios k6)": 4}
for s in ["auth", "reservas", "notificaciones", "chatbot"]:
    piramide["Unitarias / API (pytest)"] += json.loads((RAIZ / "tests" / "resultados" / f"cobertura_{s}.json")
                                                       .read_text(encoding="utf-8")).get("conteo_pruebas", 0)
metricas["piramide"] = piramide
(RAIZ / "docs" / "fuentes" / "metricas.json").write_text(json.dumps(metricas, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(metricas["k6"], indent=1))
print("gráficos:", sorted(p.name for p in OUT.glob("*.png")))
