#!/bin/sh
# Genera config.js a partir de variables de entorno (usado por Render Static Site).
set -e
cat > config.js <<EOF
window.CONFIG = {
  AUTH_URL: "${AUTH_URL:-/api/auth}",
  RESERVAS_URL: "${RESERVAS_URL:-/api/reservas}",
  NOTIF_URL: "${NOTIF_URL:-/api/notificaciones}",
  CHAT_URL: "${CHAT_URL:-/api/chat}",
};
EOF
echo "config.js generado:"
cat config.js
