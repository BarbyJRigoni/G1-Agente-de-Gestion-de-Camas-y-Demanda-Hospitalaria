# Bitácora de trabajo – Darío Martínez

**Proyecto:** Agente de Gestión de Camas y Demanda Hospitalaria (Grupo 1)
**Rol:** Backend y API con FastAPI
**Rama:** `dario`

**Tareas asignadas:**
- Configurar la aplicación FastAPI.
- Crear endpoints para consultar datos hospitalarios.
- Desarrollar la lógica de alertas de ocupación.
- Conectar los servicios con el frontend.

**Archivos a cargo:** `main.py`, `core/config.py`, `routers/inventario.py` y `services/alertas.py`.

**Criterio de trabajo:** el backend se construyó sobre los datos limpios y las funciones de Sabrina (`data/procesados/` y `services/analisis.py`), sin modificarlos.

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

## Datasets

El sistema trabaja con los tres datasets limpiados por Sabrina:

- **HDHI** (Hero DMC Heart Institute): **dataset principal**. Es un hospital real, con estacionalidad, y con sus fechas se arman los casos de la demo.
- **LengthOfStay** y **Healthcare**: datasets de comparación. Muestran que el agente se aplica a cualquier hospital cambiando solo el parámetro `dataset`.

Cada consulta trabaja con **un dataset por vez**. Son hospitales distintos, de años distintos y sin pacientes en común, por lo que no se suman en una sola ocupación.

---

## Paso 1 – Configuración central (`core/config.py`)

`config.py` es la configuración central del backend. Reúne en un solo lugar todos los valores que usa el sistema, para que ningún otro archivo los tenga escritos por su cuenta. Los demás módulos los importan desde acá. Si hay que cambiar algo, por ejemplo la capacidad de camas, se modifica una sola vez y el cambio llega a todo el sistema.

Primero define las **rutas** del proyecto. En lugar de escribir direcciones fijas como `C:\Users\...`, las calcula a partir de la ubicación del propio archivo y sube dos carpetas hasta llegar a `backend`. Desde ahí arma la ruta a los datos limpios que preparó Sabrina y la ruta al dashboard. Así el proyecto funciona en la computadora de cualquier integrante del grupo sin tocar nada.

Después define el **título y la versión** de la API, que se muestran en la documentación automática de `/docs`.

La parte principal es el **mapa de datasets**. El proyecto trabaja con tres fuentes de datos, y cada una nombra distinto la misma información. El mapa funciona como un traductor: indica qué columna corresponde a la fecha de ingreso, a la de egreso y a la duración en cada dataset. Así, el mismo código sirve para los tres sin modificar los archivos limpios.

| Dato | HDHI | LengthOfStay | Healthcare |
|---|---|---|---|
| Fecha de ingreso | `fecha_ingreso` | `vdate` | `date_of_admission` |
| Fecha de egreso | `fecha_egreso` | `discharged` | `discharge_date` |
| Duración | `duration_of_stay` | `lengthofstay` | `duracion_internacion` |

Para cada dataset también se guarda un nombre descriptivo y una **fecha de prueba**, que hace de "hoy" simulado porque cada dataset cubre años distintos. Si una consulta no indica dataset, se usa **HDHI** por defecto.

Otro dato importante es la **capacidad de camas**. Los datasets no informan cuántas camas tiene el hospital, así que se estimó a partir de los datos. Primero se reconstruyó cuántas camas estuvieron ocupadas cada noche. Después se tomó el nivel de ocupación que solo se supera el 5 % de los días (percentil 95) y se lo dividió por 0,90. De esta forma, ese nivel de ocupación alta coincide con el 90 % de la capacidad, y la alerta se activa en los picos reales de demanda: no todos los días ni nunca.

| Dataset | Ocupación p95 (camas por noche) | Capacidad |
|---|---:|---:|
| HDHI | 163 | 190 |
| LengthOfStay | 1.144 | 1.280 |
| Healthcare | 508 | 570 |

Por último, fija las **dos reglas de la consigna**: el agente proyecta los próximos **7 días** y emite una **Alerta de Saturación** cuando la ocupación proyectada supera el **90 %** de la capacidad.

**Prueba:**
```powershell
python -c "from core import config; print(list(config.DATASETS), config.UMBRAL_SATURACION)"
```
Resultado: `['hdhi', 'lengthofstay', 'healthcare'] 0.9`

---

## Paso 2 – Lógica de alertas (`services/alertas.py`)

`alertas.py` contiene la **lógica de alertas de ocupación**. Responde dos cosas que pide la consigna: cuál es la **Tasa de Ocupación Proyectada** de cada día y si corresponde emitir la **Alerta de Saturación**, que se activa cuando la ocupación supera el 90 % de la capacidad del hospital.

Es un archivo independiente: no lee datos ni depende del trabajo de otros integrantes. Solo recibe números (cuántas camas están ocupadas y cuál es la capacidad) y devuelve un resultado. Tampoco tiene la capacidad escrita adentro: la recibe como parámetro. La capacidad de cada dataset está en `config.py`, y el agente se la pasa según el dataset elegido. Por eso la misma lógica sirve para los tres.

Tiene tres funciones que se apoyan una en la otra.

La primera, `calcular_tasa_ocupacion`, calcula el porcentaje de ocupación: divide las camas ocupadas por la capacidad, lo multiplica por 100 y lo redondea a un decimal. Si la capacidad es cero o negativa, avisa con un error, porque no se puede dividir por cero.

La segunda, `evaluar_dia`, analiza un solo día y devuelve la tasa de ocupación, cuántas camas quedan libres y si hay alerta. La comparación contra el 90 % se hace con el valor exacto, sin redondear: un día con 90,04 % de ocupación se muestra como 90,0 %, pero igual dispara la alerta. Además, se usa "mayor que" y no "mayor o igual", porque la consigna dice que la alerta se emite cuando la ocupación **supera** el 90 %. Una ocupación de exactamente 90 % no la dispara, y ese es el caso límite de la demo. Las camas libres nunca dan un número negativo: si el hospital está sobreocupado, quedan cero.

La tercera, `evaluar_proyeccion`, analiza la semana completa. Recibe la lista de días que proyecta el agente, aplica `evaluar_dia` a cada uno y arma un resumen: si hay alerta (basta con que un solo día supere el 90 %), cuál es el día de mayor ocupación, qué días quedan en saturación y el detalle día por día. También genera un mensaje listo para mostrar. Por ejemplo: *"ALERTA DE SATURACION: la ocupación proyectada supera el 90 % en 2 de 7 días. Pico: 94,1 % el 2018-01-10"*.

El umbral del 90 % se toma de `config.py`. Si el grupo decidiera cambiarlo, alcanza con modificarlo allí.

Al final, el archivo incluye una prueba que se ejecuta solo al correrlo directamente. Usa una capacidad de ejemplo de 220 camas y muestra los tres casos de la demostración:

| Caso | Ocupación máxima | Resultado |
|---|---:|---|
| Normal | 63,6 % | Sin alerta |
| Límite | 90,0 % | Sin alerta (no supera el 90 %) |
| Crítico | 95,5 % | **Alerta de Saturación** (5 de 7 días) |

**Prueba:** `python -m services.alertas`

---

## Paso 3 – Agente provisorio (`agents/inventario_agent.py`)

> **Archivo a cargo de Bárbara.** Estaba vacío y el endpoint `/proyeccion-camas` lo necesita, así que se armó esta versión provisoria para probar la API de punta a punta.
> Bárbara puede tomarla como base o reemplazarla por su modelo (`services/prediccion.py`), manteniendo el **contrato** que usa el router:
> - `proyectar_camas(dataset, fecha, dias_internados, capacidad, dias)` → diccionario con `proyeccion`, `alerta_saturacion` y `mensaje`
> - `cargar_internaciones(dataset)` → tabla con `ingreso`, `egreso` y `duracion`
> - `censo_en_fecha(internaciones, fecha)` → lista con las noches que lleva cada internado

El agente estima cuántas camas se liberan y cuántas se ocupan en los próximos 7 días, a partir de los pacientes internados y de la tasa histórica de ingresos. La idea central es:

> **camas ocupadas del día = pacientes actuales que siguen internados + pacientes nuevos que siguen internados**

Primero carga los datos limpios con la función de Sabrina y unifica las columnas con el mapa de `config.py`. Calcula las **noches** de cada internación (egreso menos ingreso), porque HDHI cuenta el día de alta y los otros dos datasets no. Así los tres miden igual.

Con la historia anterior a la fecha del censo, calcula dos cosas. Por un lado, qué proporción de las internaciones pasadas duró más de 1, 2, 3… noches: con eso estima las **altas**. Un paciente que lleva varias noches internado no se comporta igual que uno que recién ingresó, y el cálculo lo tiene en cuenta. Por otro lado, el promedio de ingresos de cada día de la semana en las últimas 8 semanas, que es la **tasa histórica de ingreso**.

Para cada uno de los 7 días suma los pacientes actuales que siguen internados y los ingresos nuevos que todavía no se fueron. Al final aplica la lógica de alertas del paso 2. Solo usa datos anteriores a la fecha del censo, para no "espiar el futuro".

**Validación:** se comparó la proyección con la ocupación real 7 días después.

| Dataset | Error del agente | Error de suponer "no cambia nada" |
|---|---:|---:|
| HDHI | 13,8 % | 16,9 % |
| LengthOfStay | 3,5 % | 4,2 % |
| Healthcare | 3,6 % | 3,3 % (dataset sintético, sin patrón) |

**Casos de la demo (HDHI, capacidad 190 camas):**

| Caso | Fecha del censo | Ocupación hoy | Máximo proyectado | Alerta |
|---|---|---:|---:|---|
| Normal | 2019-01-01 | 65,8 % | 68,3 % | No |
| Límite | 2019-03-05 | 88,9 % | 89,1 % | No |
| Crítico | 2018-01-09 | 100 % | 94,1 % | **Sí** (2 días) |

**Prueba:** `python -m agents.inventario_agent`

---

## Paso 4 – Endpoints (`routers/inventario.py`)

`routers/inventario.py` define los **endpoints de la API**: las direcciones a las que se le puede hacer una consulta al sistema. Cumple dos requisitos de la consigna: al menos cuatro endpoints documentados en `/docs` y validados con Pydantic, y el endpoint `/proyeccion-camas`, que recibe el censo actual del hospital y devuelve la predicción semanal.

El archivo no hace cálculos propios. Recibe la consulta, controla que los datos sean válidos, le pide el resultado al agente y a la lógica de alertas, y lo devuelve en un formato ordenado. Funciona como la ventanilla de atención del sistema.

**Modelos Pydantic.** Son "moldes" que describen qué datos entran y qué datos salen. El modelo de entrada más importante es `CensoActual`, que representa lo que recibe `/proyeccion-camas`. Cada campo tiene su regla:
- el dataset solo puede ser `hdhi`, `lengthofstay` o `healthcare`;
- la capacidad tiene que ser mayor a cero;
- los días a proyectar van de 1 a 14 (por defecto, 7);
- las noches de cada paciente tienen que ser 1 o más;
- la fecha tiene que ser válida.

Si algún dato no cumple, FastAPI rechaza la consulta automáticamente con un error 422 que indica qué campo falló. Los modelos de salida describen qué devuelve cada endpoint: quedan documentados en `/docs` y garantizan que la API responda siempre con el mismo formato, algo importante para el frontend.

**Los cuatro endpoints:**

| Método | Ruta | Qué devuelve |
|---|---|---|
| GET | `/datasets` | Datasets disponibles, capacidad y fecha de prueba |
| GET | `/estadisticas` | Internaciones, período, ALOS, mediana, percentil 90 e ingresos por día |
| GET | `/censo` | Camas ocupadas en una fecha y su tasa de ocupación |
| POST | `/proyeccion-camas` | Proyección de 7 días, tasa de ocupación proyectada y **Alerta de Saturación** |

Los **GET** solo consultan información, y los datos se pasan en la dirección (por ejemplo, `/censo?dataset=hdhi&fecha=2018-01-09`). El **POST** recibe el censo en el cuerpo de la consulta y con eso calcula un resultado nuevo. Si una fecha está fuera del período del dataset, la API responde con un error (404 en `/censo` y 400 en `/proyeccion-camas`) que indica el rango válido.

El ALOS de `/estadisticas` y la tasa de ocupación proyectada de `/proyeccion-camas` son los **dos KPI** que pide la consigna.

**Ejemplos para la demo.** En `/docs`, el endpoint `/proyeccion-camas` muestra un menú con cuatro ejemplos listos para ejecutar:
- **Caso normal** (2019-01-01): máximo 68,3 %, sin alerta.
- **Caso límite** (2019-03-05): máximo 89,1 %, sin alerta.
- **Caso crítico** (2018-01-09): máximo 94,1 %, con Alerta de Saturación.
- **Menos camas**: el caso normal con 140 camas en lugar de 190. Muestra cómo la misma situación genera una alerta si el hospital pierde capacidad (pico de 92,7 %).

**Prueba:**
```powershell
python -c "from routers.inventario import router; print([r.path for r in router.routes])"
```
Resultado: `['/datasets', '/estadisticas', '/censo', '/proyeccion-camas']`

---

## Paso 5 – Aplicación (`main.py`)

`main.py` es el **punto de entrada de la API**, el archivo que se ejecuta para poner en marcha el sistema. No tiene lógica de cálculo propia: **arma y conecta** las piezas de los demás archivos.

Primero crea la aplicación con `app = FastAPI(...)`. Ese objeto `app` es la API completa. Por eso el comando de inicio es `uvicorn main:app`: le indica a Uvicorn que en el archivo `main` está el objeto `app` que tiene que ejecutar. El título, la versión y la descripción se toman de `config.py` y aparecen en `/docs`. La descripción usa los valores reales de la configuración (7 días y 90 %): si se cambian, la documentación se actualiza sola.

Después habilita **CORS**. Por seguridad, los navegadores no dejan que una página consulte una API ubicada en otra dirección o en otro puerto. CORS le avisa al navegador que esas consultas están permitidas, y así el dashboard puede pedirle datos a la API. Esto cubre la tarea de *"conectar los servicios con el frontend"*. Para el trabajo práctico se permite cualquier origen; en un sistema real se limitaría a la dirección del frontend.

Con `app.include_router(...)` incorpora los cuatro endpoints de `routers/inventario.py`. Separar los endpoints en su propio archivo deja a `main.py` corto y con una sola responsabilidad: arrancar y conectar.

Agrega además un endpoint propio, **`/salud`**, que comprueba que el servidor funciona. Responde con el estado, la versión, los datasets disponibles y si encontró la carpeta de datos limpios. Con este endpoint, la API queda con **cinco en total: cuatro GET y un POST**.

Por último, define la **página de inicio**. Si `frontend/index.html` tiene contenido, muestra el dashboard del grupo; si todavía está vacío, responde con un mensaje que indica que la documentación está en `/docs`.

**Prueba en `/docs` – Caso crítico:**
`"alerta_saturacion": true` · `ALERTA DE SATURACION: la ocupacion proyectada supera el 90 % en 2 de 7 dias. Pico: 94.1 % el 2018-01-10.`
La respuesta incluye el encabezado `access-control-allow-origin: *`, que confirma que CORS está activo.

---

## Observaciones para el equipo

- **`services/prediccion.py` y `agents/inventario_agent.py`:** están a cargo de Bárbara. El agente de esta rama es provisorio e incluye su propia predicción, para que la API funcione de forma independiente. La integración con el modelo de Bárbara queda pendiente.
- **Duplicados en HDHI:** la limpieza conserva 882 registros que solo difieren en `sno` (el número de orden), porque `duplicated()` compara también esa columna. Inflan la ocupación en torno al 6 %.
- **Fechas ambiguas en HDHI:** las 216 fechas marcadas como "ambiguas" se pueden resolver con la columna `month_year`. Hoy el agente las descarta.
- **Duración:** HDHI cuenta el día de alta y los otros dos datasets no. Por eso el agente trabaja con noches.
