#!/bin/sh
# Levanta los 4 servicios sin Docker (SQLite, sin Redis) para desarrollo rápido.
cd "$(dirname "$0")/.."
mkdir -p .local
set -a; [ -f .env ] && . ./.env; set +a
export JWT_SECRET=local-secret-0123456789-0123456789-xx RESERVAS_URL=http://localhost:8002 AUTH_URL=http://localhost:8001 FRONTEND_URL=http://localhost:8080 REDIS_URL=
P="$PWD/.venv/Scripts/python"
[ -x "$P" ] || P="$PWD/.venv/bin/python"
(cd services/auth && DATABASE_URL=sqlite:///../../.local/auth.db "$P" -m uvicorn app.main:app --port 8001) &
(cd services/reservas && DATABASE_URL=sqlite:///../../.local/res.db "$P" -m uvicorn app.main:app --port 8002) &
(cd services/notificaciones && DATABASE_URL=sqlite:///../../.local/not.db "$P" -m uvicorn app.main:app --port 8003) &
(cd services/chatbot && "$P" -m uvicorn app.main:app --port 8004) &
wait
