# Entregables del proyecto final — ReservaCampus

Cada documento está en **Word (.docx, editable)** y **PDF (para entregar)**.

| Fase | Entregable | Archivo |
|---|---|---|
| 1 | Documento de Especificación de Arquitectura y diagramas de componentes distribuidos (C4) | `01_Especificacion_Arquitectura` |
| 2 | Repositorio de código, documentación de API (OpenAPI/Swagger) y scripts de base de datos | `02_Repositorio_API_Base_de_Datos` |
| 3 | Módulo de chat integrado con su lógica de negocio conectada al backend | `03_Modulo_Chatbot` |
| 4 | Informe de pruebas con métricas, gráficos de rendimiento y plan de mitigación de vulnerabilidades | `04_Informe_de_Pruebas` |
| 5 | Manual técnico | `05_Manual_Tecnico` |
| 5 | Manual de usuario (paso a paso por rol, con capturas) | `06_Manual_de_Usuario` |
| 5 | Presentación final (con notas del orador) | `07_Presentacion_Final.pptx` |
| 5 | Guía de presentación: cómo explicar, mostrar el código, demos y pruebas | `08_Guia_de_Presentacion` |

## Enlaces

- Aplicación desplegada: https://reservacampus-web-gcr3.onrender.com
- Repositorio: https://github.com/Camilo1408/reservacampus
- Swagger: [auth](https://reservacampus-auth-gcr3.onrender.com/docs) ·
  [reservas](https://reservacampus-reservas-gcr3.onrender.com/docs) ·
  [notificaciones](https://reservacampus-notificaciones-gcr3.onrender.com/docs) ·
  [chatbot](https://reservacampus-chatbot-gcr3.onrender.com/docs)
- Integración continua: https://github.com/Camilo1408/reservacampus/actions
- Especificaciones OpenAPI: [`docs/api/`](../api) · Scripts SQL: [`db/`](../../db)

## Regenerar los documentos

Todo se genera desde el código y los resultados reales:

```bash
python docs/fuentes/exportar_api_y_bd.py   # OpenAPI + SQL
python docs/fuentes/diagramas.py           # diagramas (Mermaid -> PNG)
python docs/fuentes/capturas.py            # capturas de pantalla (Playwright)
python docs/fuentes/graficos.py            # gráficos del informe (k6, cobertura, OWASP)
node docs/fuentes/docgen/01_arquitectura.js   # ... y los demás 0X_*.js  (NODE_PATH con el paquete docx)
powershell -ExecutionPolicy Bypass -File docs/fuentes/docgen/a_pdf.ps1   # Word -> PDF
python docs/fuentes/docgen/pdf_alta_resolucion.py  # reemplaza las imágenes del PDF por las originales (sin pixelado)
```
