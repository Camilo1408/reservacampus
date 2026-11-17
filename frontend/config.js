// URLs de los microservicios. En Docker Compose pasan por el gateway Nginx (rutas relativas).
// En Render este archivo se regenera en el build (build.sh) con las URLs públicas.
window.CONFIG = {
  AUTH_URL: "/api/auth",
  RESERVAS_URL: "/api/reservas",
  NOTIF_URL: "/api/notificaciones",
  CHAT_URL: "/api/chat",
};
