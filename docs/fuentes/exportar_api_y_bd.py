"""Exporta la especificación OpenAPI de cada microservicio y el DDL de PostgreSQL de todas las tablas.

Uso: python docs/fuentes/exportar_api_y_bd.py
Genera: docs/api/<servicio>.openapi.json, docs/api/endpoints.json (resumen) y db/esquema_postgresql.sql
"""
import importlib
import json
import os
import sys
from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

RAIZ = Path(__file__).resolve().parents[2]
os.environ.update({"DATABASE_URL": "sqlite://", "REDIS_URL": "", "TAREAS_INTERVALO_SEG": "0", "GROQ_API_KEY": ""})

resumen, ddl = {}, ["-- ReservaCampus · Esquema PostgreSQL generado desde los modelos SQLAlchemy",
                    "-- Cada microservicio es dueño de sus tablas (en Render comparten instancia; en Docker",
                    "-- Compose cada servicio usa su propia base: auth_db, reservas_db, notificaciones_db).", ""]
for servicio in ["auth", "reservas", "notificaciones", "chatbot"]:
    for m in [k for k in sys.modules if k == "app" or k.startswith("app.")]:
        del sys.modules[m]
    sys.path.insert(0, str(RAIZ / "services" / servicio))
    main = importlib.import_module("app.main")
    esquema = main.app.openapi()
    (RAIZ / "docs" / "api" / f"{servicio}.openapi.json").write_text(json.dumps(esquema, indent=2, ensure_ascii=False),
                                                                     encoding="utf-8")
    resumen[servicio] = [{"metodo": metodo.upper(), "ruta": ruta, "resumen": op.get("summary", ""),
                          "descripcion": (op.get("description") or "").split("\n")[0], "etiqueta": (op.get("tags") or [""])[0]}
                         for ruta, ops in esquema["paths"].items() for metodo, op in ops.items()]
    try:
        db = importlib.import_module("app.database")
        ddl.append(f"-- ==================== {servicio}-service ====================")
        for tabla in db.Base.metadata.sorted_tables:
            ddl.append(str(CreateTable(tabla).compile(dialect=postgresql.dialect())).strip() + ";")
            for idx in tabla.indexes:
                ddl.append(str(CreateIndex(idx).compile(dialect=postgresql.dialect())).strip() + ";")
            ddl.append("")
    except ModuleNotFoundError:
        pass  # el chatbot no tiene base de datos
    sys.path.pop(0)
    print(servicio, len(resumen[servicio]), "endpoints")

(RAIZ / "docs" / "api" / "endpoints.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
(RAIZ / "db" / "esquema_postgresql.sql").write_text("\n".join(ddl), encoding="utf-8")
print("DDL:", sum(1 for x in ddl if x.startswith("CREATE TABLE")), "tablas")
