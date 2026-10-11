# Bitácora de trabajo – Darío Martínez

**Rol:** Backend y API con FastAPI · **Rama:** `dario`
**Archivos:** `core/config.py`, `services/alertas.py`, `agents/inventario_agent.py`, `routers/inventario.py`, `main.py`

**Criterio:** el backend se construyó sobre los datos limpios y las funciones de Sabrina (`data/procesados/`, `services/analisis.py`), sin modificarlos.

---

## Cómo ejecutar

```powershell
# Desde la raíz del repositorio
python -m venv .venv
.venv\Scripts\activate
pip install pandas numpy fastapi uvicorn

cd backend\app
uvicorn main:app --reload
```
Documentación interactiva: http://localhost:8000/docs

---

## Paso 1 – Configuración (`core/config.py`)

**Objetivo:** reunir en un solo archivo las rutas, los datasets, la capacidad de camas y el umbral de alerta.

**Explicación:**
- **Rutas:** se calculan desde la ubicación del archivo (`Path(__file__).parents[2]`), así funcionan en la PC de cualquier integrante.
- **Mapa de columnas (`DATASETS`):** cada dataset nombra distinto los mismos datos. El mapa permite usar los tres con el mismo código.

| Concepto | HDHI | LengthOfStay | Healthcare |
|---|---|---|---|
| Fecha de ingreso | `fecha_ingreso` | `vdate` | `date_of_admission` |
| Fecha de egreso | `fecha_egreso` | `discharged` | `discharge_date` |
| Duración | `duration_of_stay` | `lengthofstay` | `duracion_internacion` |

- **Capacidad:** los datasets no la informan. Se calculó como `percentil 95 de la ocupación por noche ÷ 0,90`, para que la alerta se active solo en los picos de demanda.

| Dataset | Ocupación p95 | Capacidad |
|---|---:|---:|
| HDHI | 163 camas | 190 |
| LengthOfStay | 1.144 camas | 1.280 |
| Healthcare | 508 camas | 570 |

- **Reglas de la consigna:** `DIAS_PROYECCION = 7` y `UMBRAL_SATURACION = 0.90`.

---

## Paso 2 – Alertas (`services/alertas.py`)

**Objetivo:** calcular la **Tasa de Ocupación Proyectada (%)** y emitir la **Alerta de Saturación** cuando se supera el 90 %.

**Explicación:**
- `calcular_tasa_ocupacion()`: `camas ocupadas / capacidad × 100`.
- `evaluar_dia()`: tasa, camas libres y alerta de un día. Compara el valor **sin redondear** (90,04 % dispara la alerta aunque se muestre 90,0 %) y usa `>` porque la consigna dice "supera".
- `evaluar_proyeccion()`: evalúa todos los días y devuelve el resumen (alerta, día pico, días en saturación y mensaje).
- No depende de otros módulos: recibe números y devuelve resultados.

**Prueba:** `python -m services.alertas` → casos normal, límite (90,0 %, sin alerta) y crítico (con alerta).

---

## Paso 3 – Agente (`agents/inventario_agent.py`)

**Objetivo:** estimar cuántas camas se liberan y se ocupan en los próximos 7 días, a partir de los pacientes internados y de la tasa histórica de ingresos.

**Idea central:**
> camas ocupadas del día = pacientes actuales que siguen internados + pacientes nuevos que siguen internados

**Explicación:**
- `cargar_internaciones()`: usa `cargar_datos()` de Sabrina y unifica las columnas. Calcula las **noches** (`egreso − ingreso`), porque HDHI cuenta el día de alta y los otros dos datasets no.
- `censo_en_fecha()`: pacientes que ocupan cama esa noche y cuántas noches llevan.
- `calcular_prob_seguir()`: proporción histórica de internaciones que duran más de 1, 2, 3… noches. Con esto se estiman las **altas**.
- `calcular_tasa_ingresos()`: promedio de ingresos por día de la semana en las últimas 8 semanas (**tasa histórica de ingreso**).
- `proyectar_camas()`: para cada día suma los pacientes actuales que siguen internados, según cuántas noches lleva cada uno, más los ingresos nuevos que todavía no se fueron. Al final aplica las alertas del paso 2.
- Solo usa historia **anterior** a la fecha del censo, para no usar datos del futuro.

**Validación (backtesting):** se comparó la proyección con la ocupación real 7 días después.

| Dataset | Error del agente | Error de suponer "no cambia nada" |
|---|---:|---:|
| HDHI | 13,8 % | 16,9 % |
| LengthOfStay | 3,5 % | 4,2 % |
| Healthcare | 3,6 % | 3,3 % (dataset sintético, sin patrón) |

**Casos de la demo (HDHI):**

| Caso | Fecha | Ocupación hoy | Máximo proyectado | Alerta |
|---|---|---:|---:|---|
| Normal | 2019-01-01 | 65,8 % | 68,3 % | No |
| Límite | 2019-03-05 | 88,9 % | 89,1 % | No |
| Crítico | 2018-01-09 | 100 % | 94,1 % | **Sí** (2 días) |

---

## Paso 4 – Endpoints (`routers/inventario.py`)

**Objetivo:** exponer el agente como API, con validación Pydantic.

| Método | Ruta | Devuelve |
|---|---|---|
| GET | `/datasets` | Datasets, capacidad y fecha de prueba |
| GET | `/estadisticas` | ALOS, mediana, percentil 90, ingresos por día |
| GET | `/censo` | Camas ocupadas en una fecha y tasa de ocupación |
| POST | `/proyeccion-camas` | Proyección de 7 días y **Alerta de Saturación** |

**Explicación:**
- **`CensoActual` (Pydantic)** valida la entrada: dataset permitido, capacidad > 0, días entre 1 y 14, noches ≥ 1 y fecha válida. Si algo falla, FastAPI responde **422** indicando el campo.
- **Modelos de salida** (`ProyeccionRespuesta`, `Censo`, etc.): documentan y garantizan el formato de cada respuesta.
- **Errores:** fecha fuera de rango → **400** (`/proyeccion-camas`) o **404** (`/censo`), con el rango válido.
- **Ejemplos en `/docs`:** normal, límite, crítico y "50 camas menos" (mismo día que el normal, con 140 camas: alerta con pico de 92,7 %).

---

## Paso 5 – Aplicación (`main.py`)

**Objetivo:** punto de entrada que ejecuta Uvicorn (`uvicorn main:app --reload`).

**Explicación:**
- Crea `app = FastAPI(...)` con título, versión y descripción tomados de `config.py`.
- **CORS** habilitado para que el frontend pueda consumir la API.
- `include_router()` incorpora los endpoints del paso 4.
- `/salud` comprueba que el servidor funciona y encuentra los datos.
- `/` muestra `frontend/index.html` si tiene contenido.

**Prueba en `/docs` – Caso crítico:**
`"alerta_saturacion": true` · `ALERTA DE SATURACION: la ocupacion proyectada supera el 90 % en 2 de 7 dias. Pico: 94.1 % el 2018-01-10.`

---

## Observaciones para el equipo

- **Duplicados en HDHI:** la limpieza conserva 882 registros que solo difieren en `sno`, porque `duplicated()` no los detecta. Inflan la ocupación en torno al 6 %.
- **Fechas ambiguas en HDHI:** las 216 marcadas como ambiguas se pueden resolver con la columna `month_year`. Hoy el agente las descarta.
- **Duración:** HDHI cuenta el día de alta y los otros dos datasets no. Por eso el agente trabaja con noches.