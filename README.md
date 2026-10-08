# Agente de Gestión de Camas y Demanda Hospitalaria

Trabajo Práctico Final – Agentes Inteligentes 3.0 – Desarrollo de Sistemas de I.A. 2026 (Grupo 1, Salud)

Agente que prevé la ocupación de camas de una red hospitalaria de 5 sedes para los próximos 7 días a partir del censo actual, y emite una **Alerta de Saturación** cuando la proyección supera el 90 % de la capacidad.


## Dataset



## Estructura

```
proyecto/
|
├── backend/
|   ├── app/
│   |   ├── main.py                    → FastAPI entrypoint
│   │   |
│   │   ├── core/
│   │   |   └── config.py               → rutas y configuración
│   │   │
│   │   ├── data/
│   │   └── loader.py                   → carga CSV (pandas)
│   │ 
│   │   ├── services/
│   │   │   ├── prediccion.py            → IA (ventas futuras)
│   │   │   ├── alertas.py               → vencimientos
│   │   │   └── analisis.py              → stock crítico
│   │   │
│   │   ├── agents/
│   │      └── inventario_agent.py       → orquestador IA
│   │   ├── routers/
│   │      └── inventario.py            → endpoints API
│       │ 
│   │   └── templates/
│   │       └── index.html             → frontend renderizado
│   │
|   |── data/
│       └── data.csv                   → historial de ventas
│
└── frontend/
   └── index.html                      → UI principal (dashboard)


## Limitaciones y mejoras


