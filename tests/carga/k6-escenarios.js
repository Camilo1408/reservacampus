// Pruebas de rendimiento de ReservaCampus con k6.
//   k6 run -e ESCENARIO=carga  -e AUTH=<url auth> -e RES=<url reservas> -e CHAT=<url chatbot> tests/carga/k6-escenarios.js
//   k6 run -e ESCENARIO=estres ...
// Exportar resultados: --summary-export resumen.json --out json=serie.json
import http from "k6/http";
import { check, group, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const AUTH = __ENV.AUTH || "https://reservacampus-auth-gcr3.onrender.com";
const RES = __ENV.RES || "https://reservacampus-reservas-gcr3.onrender.com";
const CHAT = __ENV.CHAT || "https://reservacampus-chatbot-gcr3.onrender.com";
const ESCENARIO = __ENV.ESCENARIO || "carga";

const errores = new Rate("errores_negocio");
const tDisp = new Trend("t_disponibilidad", true);
const tEsp = new Trend("t_espacios", true);
const tMias = new Trend("t_mis_reservas", true);
const tLogin = new Trend("t_login", true);
const tChat = new Trend("t_chat", true);

const ETAPAS = {
  // Carga normal: uso típico de una hora pico en la universidad
  carga: [{ duration: "30s", target: 10 }, { duration: "1m30s", target: 20 }, { duration: "30s", target: 0 }],
  // Estrés: se sube la concurrencia hasta encontrar el punto de degradación
  estres: [{ duration: "30s", target: 20 }, { duration: "45s", target: 40 }, { duration: "45s", target: 60 },
           { duration: "30s", target: 0 }],
};

export const options = {
  scenarios: { [ESCENARIO]: { executor: "ramping-vus", startVUs: 0, stages: ETAPAS[ESCENARIO] } },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    t_disponibilidad: ["p(95)<2000"],
    t_espacios: ["p(95)<1500"],
  },
  summaryTrendStats: ["avg", "min", "med", "p(90)", "p(95)", "p(99)", "max"],
};

export function setup() {
  // Calentar los servicios (Render gratuito los duerme tras 15 min sin tráfico)
  for (const url of [`${AUTH}/health`, `${RES}/health`, `${CHAT}/health`]) http.get(url, { timeout: "90s" });
  const r = http.post(`${AUTH}/login`, JSON.stringify({ email: "admin@reservacampus.edu", password: "Admin12345" }),
    { headers: { "Content-Type": "application/json" }, timeout: "60s" });
  return { token: r.json("access_token") };
}

export default function (datos) {
  const fecha = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  const auth = { headers: { Authorization: `Bearer ${datos.token}` }, tags: { endpoint: "mis_reservas" } };

  group("consultas", () => {
    let r = http.get(`${RES}/disponibilidad?fecha=${fecha}`, { tags: { endpoint: "disponibilidad" } });
    tDisp.add(r.timings.duration);
    errores.add(!check(r, { "disponibilidad 200": (x) => x.status === 200 }));

    r = http.get(`${RES}/espacios`, { tags: { endpoint: "espacios" } });
    tEsp.add(r.timings.duration);
    errores.add(!check(r, { "espacios 200": (x) => x.status === 200 }));

    r = http.get(`${RES}/reservas/mias`, auth);
    tMias.add(r.timings.duration);
    errores.add(!check(r, { "mis reservas 200": (x) => x.status === 200 }));
  });

  // 1 de cada 10 iteraciones inicia sesión (operación costosa: PBKDF2 120 000 iteraciones)
  if (__ITER % 10 === 0) {
    const r = http.post(`${AUTH}/login`, JSON.stringify({ email: "admin@reservacampus.edu", password: "Admin12345" }),
      { headers: { "Content-Type": "application/json" }, tags: { endpoint: "login" } });
    tLogin.add(r.timings.duration);
    errores.add(!check(r, { "login 200": (x) => x.status === 200 }));
  }
  // 1 de cada 15 iteraciones usa el chatbot por reglas (consulta a reservas por dentro)
  if (__ITER % 15 === 5) {
    const r = http.post(`${CHAT}/chat`, JSON.stringify({ mensaje: "¿qué está libre mañana a las 10?" }),
      { headers: { "Content-Type": "application/json" }, tags: { endpoint: "chat" } });
    tChat.add(r.timings.duration);
    errores.add(!check(r, { "chat 200 o 429": (x) => x.status === 200 || x.status === 429 }));
  }
  sleep(1);
}
