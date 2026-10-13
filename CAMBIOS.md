# Cambios de la rama Barby

Copiar estos archivos respetando las carpetas (reemplazan a los que ya están en la rama).

## Archivos de Bárbara

| Archivo | Qué cambió |
|---|---|
| `backend/app/services/prediccion.py` | Reescrito para la estructura del equipo: modelo de demanda (5 métodos + backtesting) y evaluación del agente |
| `backend/app/agents/inventario_agent.py` | Ingresos desde el modelo, escenario pesimista (P90), probabilidad de saturación, alerta preventiva y lectura del CSV una sola vez |
| `backend/app/routers/prediccion.py` | **Nuevo**: endpoints `/modelo/...` |
| `frontend/index.html` | Reescrito para consumir la API del equipo |
| `docs/modelo_prediccion.md` | **Nuevo**: documentación del modelo, la evaluación y la interfaz |

## Cambios chicos en archivos de Darío (avisarle)

| Archivo | Qué cambió |
|---|---|
| `backend/app/main.py` | +2 líneas: importa y registra `routers/prediccion.py` |
| `backend/app/routers/inventario.py` | +5 campos opcionales en `DiaProyectado` y `ProyeccionRespuesta`, para que `/proyeccion-camas` muestre P90, probabilidad, método y alerta preventiva. No cambia nada de lo que ya devolvía. |

No se tocó nada de Sabrina (limpieza, `analisis.py`, `data/procesados/`).
