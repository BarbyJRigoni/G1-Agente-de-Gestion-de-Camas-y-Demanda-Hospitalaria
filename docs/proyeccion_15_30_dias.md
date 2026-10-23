# Proyección a 15 y 30 días

La consigna pide 7 días, y sigue siendo el valor por defecto. El sistema ahora también permite proyectar a **15 y 30 días**.

## Qué cambió

| Archivo | Cambio |
|---|---|
| `backend/app/core/config.py` | `DIAS_PROYECCION_MAX = 30` y `HORIZONTES_PROYECCION = (7, 15, 30)` |
| `backend/app/agents/inventario_agent.py` | Acepta hasta 30 días (antes, 14) |
| `backend/app/services/prediccion.py` | El modelo de ingresos acepta hasta 30 días; `evaluar_agente()` evalúa cualquier horizonte |
| `backend/app/routers/inventario.py` | `POST /proyeccion-camas` acepta `"dias"` de 1 a 30 (por defecto, 7) |
| `backend/app/routers/prediccion.py` | `/modelo/ocupacion-real` admite hasta 30 días; `/modelo/evaluacion-agente?dias=7\|15\|30` |
| `frontend/index.html` | Selector **Proyección: 7 / 15 / 30 días**; los textos, la tabla, el mapa de camas y el gráfico se adaptan solos |

La simulación de UTI y general sigue a 7 días.

## Cómo se usa

- **Panel:** elegir 15 o 30 días en el selector "Proyección". La primera vez tarda unos segundos, porque calibra el margen de error con 26 fechas anteriores; después queda en memoria.
- **API:** `POST /proyeccion-camas` con `{"dataset": "hdhi", "fecha": "2019-03-01", "dias": 30}`.

## Qué tan confiable es (HDHI, contra la ocupación real)

| Horizonte | Fechas evaluadas | Error a 1 día | Error el último día | Error promedio del agente | Error de "mantener el censo" | Cobertura del escenario pesimista |
|---|---|---|---|---|---|---|
| 7 días | 83 | 4,5 camas | 13,6 camas (7,2 %) | 10,1 | 11,0 | 93,6 % |
| 15 días | 41 | 4,4 camas | 15,5 camas (8,2 %) | 13,5 | 15,2 | 88,4 % |
| 30 días | 40 | 4,4 camas | 15,9 camas (8,4 %) | 15,3 | 18,3 | 88,9 % |

A 15 y 30 días se evaluó una fecha cada dos semanas. En la validación posterior (desde el 29/9/2018), a 30 días el agente se equivoca en promedio 12,7 camas, contra 16,6 de suponer que la ocupación no cambia.

**Cómo leerlo:**
- El error crece en la primera semana y después se estabiliza alrededor de 16 camas (≈8 % de 190).
- Cuanto más lejos se proyecta, **más le gana** el agente a la referencia simple.
- A 30 días el modelo no conoce eventos futuros (brotes, feriados, cambios de capacidad), así que conviene usarlo para **planificar** (personal, cirugías programadas), no para decisiones de un día puntual.
