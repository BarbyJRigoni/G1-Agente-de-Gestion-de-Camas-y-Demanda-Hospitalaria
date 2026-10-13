# Modelo de predicción de demanda, evaluación e interfaz

**Responsable:** Bárbara Rigoni, Inteligencia artificial e interfaz
**Archivos:** `services/prediccion.py`, `agents/inventario_agent.py`, `routers/prediccion.py` y `frontend/index.html`

Todo se construyó sobre los datos limpios de Sabrina (`data/procesados/`, `services/analisis.py`) y el backend de Darío (`core/config.py`, `routers/inventario.py`, `services/alertas.py`), sin modificar la limpieza.

---

## 1. Qué hace el modelo y por qué hace falta

Para proyectar camas, el agente necesita dos cosas:

- **Cuántas camas se liberan:** sale de los pacientes internados hoy y de cuánto duraron las internaciones pasadas. Esa parte ya la resolvía el agente.
- **Cuántas se ocupan:** depende de **cuántos pacientes van a ingresar** cada día. Eso es lo que predice este modelo.

## 2. Los cinco métodos que compiten

| Método | Cómo pronostica |
|---|---|
| Media 28 días | El promedio de las últimas 4 semanas. Es la referencia mínima a superar. |
| Semana anterior | Lo que entró el mismo día de la semana pasada. |
| Día de semana (8 semanas) | El promedio de cada día de la semana en las últimas 8 semanas. Es el método de la primera versión del agente. |
| Estacional | El promedio histórico de ese mes y ese día de la semana. |
| Regresión Ridge | Parte del nivel reciente y aprende cuánto se aparta cada día según el día de la semana y la época del año. |

La regresión está programada con numpy (solución cerrada de Ridge), sin librerías externas. Predice el **desvío respecto del nivel reciente** y no el valor absoluto, así se adapta sola si el hospital crece o hay un brote. La época del año se representa con términos de Fourier (seno y coseno del día del año), la forma estándar de modelar un ciclo anual con pocas variables.

## 3. Cómo se evaluó

**Backtesting con origen móvil.** En una serie de tiempo no se puede separar un 20 % al azar, porque el modelo "vería el futuro". Por eso se toma una fecha, se entrena **solo con lo anterior**, se pronostican los 7 días siguientes y se compara con lo que pasó. Se repitió 26 semanas seguidas, igual que se usaría en la realidad.

**Métricas:**

- **MAE**: error promedio, en pacientes por día.
- **WAPE**: error total sobre ingresos totales, en %. Se prefiere al MAPE porque el MAPE explota en días con 0 ingresos.
- **WAPE semanal**: error del total de la semana, que es lo que importa para planificar camas.
- **Cobertura del intervalo del 80 %**: si la incertidumbre está bien estimada, el valor real debe caer dentro ~80 % de las veces.

**Regla de elección:** gana el de menor WAPE diario, **pero solo si le gana a la media por 3 % o más**. Si no, se usa la media, que es más simple (principio de parsimonia).

### Resultados

| Dataset | Método | MAE | WAPE diario | WAPE semanal | Cobertura IC 80 % |
|---|---|---|---|---|---|
| **HDHI** (21,2 ingresos/día) | Media 28 días | 5,73 | 23,1 % | 9,7 % | 79,1 % |
| | Semana anterior | 6,53 | 26,3 % | 10,8 % | 79,1 % |
| | **Día de semana (8 sem.) ✓** | **5,02** | **20,2 %** | 10,1 % | 77,5 % |
| | Estacional | 5,53 | 22,3 % | 12,6 % | 79,1 % |
| | Regresión Ridge | 5,19 | 20,9 % | 11,3 % | 78,6 % |
| **LengthOfStay** (272/día) | **Media 28 días ✓** | 14,75 | 5,4 % | 2,1 % | 83,0 % |
| **Healthcare** (30/día) | **Media 28 días ✓** | 4,76 | 16,0 % | 8,5 % | 77,5 % |

### Qué muestran

1. **En HDHI gana el método de día de la semana**, con un 12 % menos de error que la media. Es el método de la primera versión del agente, así que la evaluación **confirma con datos** que esa decisión era buena. La regresión queda segunda, muy cerca: el patrón semanal (los lunes entran más y los domingos menos) explica casi todo, y la estacionalidad no suma tanto con solo dos años de historia.
2. **En LengthOfStay y Healthcare gana la media**: no tienen patrón semanal ni estacional. En Healthcare la regresión "gana" por 1,7 %, pero en datos aleatorios eso es ruido, y la regla de parsimonia lo descarta. Esto prueba que el sistema **no inventa patrones donde no los hay**.
3. **El error diario es alto en todos los métodos** (~20 % en HDHI) porque los ingresos tienen mucho azar: con ~21 pacientes por día, la variación aleatoria ya es de ±5. Ese límite no se puede bajar con ningún modelo sin información externa.
4. **Los intervalos están bien calibrados**: cubren entre 77 % y 83 %, cerca del 80 % esperado. Por eso el agente puede usar esa incertidumbre para el escenario pesimista.

## 4. Cómo se integró al agente (`agents/inventario_agent.py`)

Se mantuvo la lógica de proyección del agente y se agregaron tres cosas:

1. **Ingresos del modelo.** Los ingresos esperados de cada día salen de `predecir_ingresos()`, que usa el método elegido para ese dataset y **solo datos hasta la fecha del censo**.
2. **Incertidumbre.** Cada paciente internado sigue o no al día siguiente (variación de Bernoulli), y los ingresos varían más que una Poisson pura (sobredispersión medida en el backtesting). Con eso el agente calcula, para cada día:
   - el **escenario pesimista (P90)**: la ocupación que solo se supera 1 de cada 10 veces;
   - la **probabilidad de superar el 90 %**.
3. **Alerta preventiva.** Si la ocupación esperada no llega al 90 % pero la probabilidad de superarlo es del 30 % o más, el mensaje lo avisa. La **Alerta de Saturación** de la consigna (esperada > 90 %) no cambia.

Además, el CSV se lee una sola vez por dataset y queda en memoria, en lugar de leerse en cada pedido.

## 5. Evaluación del agente completo

Se reconstruyó el censo real de **91 fechas** de HDHI (una por semana), se proyectó desde cada una y se comparó con la ocupación que hubo.

**Error en camas** (capacidad de 190):

| Día | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| Error medio (camas) | 6,3 | 10,5 | 13,2 | 15,5 | 15,4 | 16,9 | 18,3 |
| % de la capacidad | 3,3 | 5,6 | 6,9 | 8,2 | 8,1 | 8,9 | 9,6 |

El error crece con la anticipación, como es esperable. También hay un **sesgo de unas 3 a 5 camas hacia abajo**: el agente subestima un poco. Dos causas probables son que el hospital creció en el período (el promedio de 8 semanas va "atrasado") y que la curva de estancia usa solo internaciones ya terminadas, que tienden a ser las más cortas.

**¿Qué regla de alerta conviene?**

| Regla | Alertas | Aciertos | Precisión | Recall |
|---|---|---|---|---|
| Ocupación esperada > 90 % (consigna) | 1 | 1 | 100 % | 12 % |
| Escenario pesimista (P90) > 90 % | 8 | 3 | 38 % | 38 % |
| Probabilidad ≥ 30 % (preventiva) | 3 | 2 | 67 % | 25 % |

En el período hubo **8 semanas que superaron el 90 %**. La regla de la consigna nunca se equivoca cuando avisa, pero **anticipa solo 1 de esas 8**. La alerta preventiva suma una más con buena precisión, y la regla del P90 anticipa 3 a cambio de más falsas alarmas.

Con solo 8 eventos, estas diferencias son orientativas. La conclusión sí es clara: **esperar a que el valor esperado supere el 90 % es tarde**, y usar la incertidumbre mejora la anticipación.

## 6. Endpoints nuevos (`routers/prediccion.py`)

| Método | Ruta | Qué devuelve |
|---|---|---|
| GET | `/modelo/demanda?dataset=hdhi` | Método elegido, métricas de los cinco y coeficientes de la regresión |
| GET | `/modelo/backtest?dataset=hdhi` | Ingresos reales vs. pronosticados día por día |
| GET | `/modelo/evaluacion-agente?dataset=hdhi` | Error por día de anticipación y precisión / recall de las alertas |
| GET | `/modelo/ocupacion-real?dataset=hdhi&desde=2019-03-05` | Ocupación que realmente hubo después de una fecha |

Además, `POST /proyeccion-camas` ahora devuelve también `metodo_ingresos`, `alerta_preventiva`, `prob_max_superar_umbral_pct` y, por día, `camas_ocupadas_p90` y `prob_superar_umbral_pct`.

## 7. Interfaz (`frontend/index.html`)

Se abre en `http://localhost:8000/`. Es HTML, CSS y JavaScript sin frameworks, con Chart.js para los gráficos, y consume la API en vivo.

- **Controles:** dataset, fecha del censo, cantidad de camas y los tres casos de la demo (Normal 01/01/2019, Límite 05/03/2019, Crítico 09/01/2018).
- **Mensaje del agente y KPIs:** ocupación de hoy, tasa de ocupación proyectada máxima, probabilidad de superar el 90 %, ALOS y día pico.
- **Mapa de camas:** una celda por cama. Moviendo el control de días se ve cómo se llena: oscuro es lo esperado, celeste lo que se ocuparía en el escenario pesimista, rojo los pacientes sin cama.
- **Proyección vs. realidad:** como el censo es una fecha pasada, se muestra la ocupación real de esos días para verificar si el agente acertó.
- **Detalle por día:** ingresos, altas, ocupación esperada y pesimista, probabilidad y valor real.
- **"¿Qué tan bien predice?":** la tabla de los cinco métodos en los tres datasets, el gráfico de backtesting, el error por día de anticipación y la tabla de reglas de alerta.

## 8. Limitaciones y mejoras

- Mejorar la predicción de ingresos requiere información externa: clima, feriados y datos epidemiológicos.
- Corregir el sesgo del agente: incorporar a la curva de estancia los pacientes que siguen internados (estimador de Kaplan-Meier) y una tendencia en el modelo de ingresos.
- Con más semanas de saturación se podría ajustar mejor el umbral de la alerta preventiva.
