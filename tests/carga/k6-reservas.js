// Prueba de carga/estrés con k6.  Uso:
//   k6 run -e BASE=http://localhost:8080/api tests/carga/k6-reservas.js
// En Render: -e AUTH=https://reservacampus-auth.onrender.com -e RES=https://reservacampus-reservas.onrender.com
import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE || "http://localhost:8080/api";
const AUTH = __ENV.AUTH || `${BASE}/auth`;
const RES = __ENV.RES || `${BASE}/reservas`;

export const options = {
  scenarios: {
    carga: { executor: "ramping-vus", startVUs: 0, stages: [
      { duration: "30s", target: 20 },   // calentamiento
      { duration: "1m", target: 50 },    // carga normal
      { duration: "30s", target: 100 },  // estrés
      { duration: "20s", target: 0 },
    ] },
  },
  thresholds: {
    http_req_failed: ["rate<0.02"],
    "http_req_duration{endpoint:disponibilidad}": ["p(95)<800"],
    "http_req_duration{endpoint:login}": ["p(95)<1500"],
  },
};

export function setup() {
  const r = http.post(`${AUTH}/login`, JSON.stringify({ email: "admin@reservacampus.edu", password: "Admin12345" }),
    { headers: { "Content-Type": "application/json" } });
  return { token: r.json("access_token") };
}

export default function (data) {
  const fecha = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  const r1 = http.get(`${RES}/disponibilidad?fecha=${fecha}`, { tags: { endpoint: "disponibilidad" } });
  check(r1, { "disponibilidad 200": (r) => r.status === 200 });

  const r2 = http.get(`${RES}/espacios`, { tags: { endpoint: "espacios" } });
  check(r2, { "espacios 200": (r) => r.status === 200 });

  if (__ITER % 10 === 0) {
    const r3 = http.post(`${AUTH}/login`, JSON.stringify({ email: "admin@reservacampus.edu", password: "Admin12345" }),
      { headers: { "Content-Type": "application/json" }, tags: { endpoint: "login" } });
    check(r3, { "login 200": (r) => r.status === 200 });
  }

  const r4 = http.get(`${RES}/reservas/mias`, { headers: { Authorization: `Bearer ${data.token}` }, tags: { endpoint: "mis_reservas" } });
  check(r4, { "mis reservas 200": (r) => r.status === 200 });
  sleep(1);
}
