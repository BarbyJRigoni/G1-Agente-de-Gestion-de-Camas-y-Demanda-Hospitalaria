# Cambios de la rama Barby (corrección de errores)

Responden al documento "Errores_Agente_camas".

| Problema | Arreglo | Archivo |
|---|---|---|
| El método de ingresos se elegía con las últimas 26 semanas del dataset, incluyendo meses posteriores a la fecha del censo | Ahora se elige con las 26 semanas **anteriores** a cada censo. `/modelo/demanda` y `/modelo/backtest` aceptan `?fecha=` para ver esa elección | `services/prediccion.py`, `routers/prediccion.py` |
| El ALOS aparecía con valores distintos (6,47 / 6,44 / 6,38) | La tarjeta dice "ALOS hasta la fecha del censo" y el mensaje explica por qué cambia | `frontend/index.html` |
| El dashboard necesitaba internet (Chart.js por CDN) | Chart.js 4.4.1 va incluido dentro del HTML; la fuente es opcional | `frontend/index.html` |
| Los botones Normal/Límite/Crítico seguían visibles con otros datasets y mandaban fechas de HDHI (errores 400/404) | `.pildoras[hidden] { display: none; }` | `frontend/index.html` |
| Código sin uso: `calcular_tasa_ingresos` y `SEMANAS_HISTORIA` | Eliminado | `agents/inventario_agent.py` |
| Archivos vacíos de la plantilla | Eliminados `backend/app/templates/index.html` y `backend/data/data.csv` | — |
| Caso Normal (01/01/2019): la ocupación real subió a ~84 % y el agente proyectaba 66 % | El botón Normal pasa a 04/06/2018 (proyectó 62 %, fue 65 %) | `frontend/index.html` |

**Para Darío:** en `config.py`, la `fecha_demo` de HDHI conviene que sea `2018-06-04` (en vez de 2019-01-01), para que coincida con el caso Normal. Y en `guia_demo.md`, el caso Normal pasa a ser esa fecha.
