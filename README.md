# 🏥 Agente de Gestión de Camas y Demanda Hospitalaria

<p align="center">
  <img src="frontend/assets/hospital-base.svg" alt="Ilustración de la entrada del hospital" width="100%">
</p>

Agente inteligente que estima la **ocupación y disponibilidad de camas hospitalarias para los próximos 7 días** (con extensiones a 15 y 30 días), a partir del censo de pacientes internados y de datos históricos de admisiones y estancias. Emite una **Alerta de Saturación** cuando la ocupación proyectada supera el **90 %** de la capacidad, y una **alerta preventiva** cuando la probabilidad de superarlo es significativa.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.142-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/pandas-3.0-150458?logo=pandas&logoColor=white" alt="pandas">
  <img src="https://img.shields.io/badge/scikit--learn-1.9-F7931E?logo=scikitlearn&logoColor=white" alt="scikit-learn">
  <img src="https://img.shields.io/badge/Chart.js-local-FF6384?logo=chartdotjs&logoColor=white" alt="Chart.js">
  <img src="https://img.shields.io/badge/SQLite%20%7C%20PostgreSQL-cuentas-4169E1?logo=postgresql&logoColor=white" alt="SQLite / PostgreSQL">
  <img src="https://img.shields.io/badge/Docker-listo-2496ED?logo=docker&logoColor=white" alt="Docker">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/estado-prototipo%20acad%C3%A9mico-yellow" alt="Status">
  <img src="https://img.shields.io/badge/Grupo%201-Salud-2e7d6b" alt="Grupo 1 Salud">
</p>

---

## 📑 Tabla de Contenidos

- [📖 Descripción del proyecto](#-descripción-del-proyecto)
- [📂 Estructura del repositorio](#-estructura-del-repositorio)
- [📊 Datasets](#-datasets)
- [🖥️ El panel](#️-el-panel)
- [🧠 Cómo funciona el agente](#-cómo-funciona-el-agente)
- [🔌 API](#-api)
-  Acceso a la nube https://g1-agente-de-gestion-de-camas-y-demanda.onrender.com/panel 
- [🚀 Uso](#-uso)
- [📈 Resultados](#-resultados)
- [🧪 Notas metodológicas y limitaciones](#-notas-metodológicas-y-limitaciones)
- [📚 Documentación y referencias](#-documentación-y-referencias)
- [✍️ Autoría](#️-autoría)

---

## 📖 Descripción del proyecto

La gestión de camas es uno de los cuellos de botella de cualquier hospital: cuando la ocupación se acerca al límite aumentan las derivaciones, las demoras en guardia y la presión sobre el personal. Anticipar esos picos con algunos días de margen permite reorganizar altas, reforzar sectores o coordinar derivaciones.

Este proyecto construye un **agente de planificación** que, dada una **fecha de censo** y una **capacidad simulada**:

1. Reconstruye los pacientes internados en esa fecha.
2. Pronostica los **ingresos** diarios de la semana siguiente.
3. Estima las **altas** a partir de la curva histórica de estancia.
4. Proyecta la **ocupación y las camas libres** día por día, con un escenario pesimista (**P90**).
5. Emite **alertas** de saturación y preventivas.

> 🎯 **Objetivo:** apoyar la planificación de recursos hospitalarios anticipando situaciones de saturación con un horizonte de 7 días (el que pide la consigna), con extensiones a 15 y 30 días para planificación de mediano plazo.

La aplicación incluye una **portada con registro e inicio de sesión**, un **panel con menú lateral** (Proyección, Estancias · HDHI, UTI y general, Evaluación y Administración), **exportación a Excel**, una **API REST** documentada con FastAPI y un **contenedor Docker** para ejecutarla sin instalar Python.

---

## 📂 Estructura del repositorio

```text
.
├── backend/
│   ├── app/
│   │   ├── main.py                     # Aplicación FastAPI (API + panel), precálculo al arrancar
│   │   ├── crear_usuario.py            # Alta de cuentas por consola
│   │   ├── crear_admin.py              # Asignación del rol administrador
│   │   ├── migrar_cuentas_neon.py      # Copia de cuentas de SQLite a PostgreSQL (Neon)
│   │   ├── core/config.py              # Rutas, datasets, capacidades, umbral y horizontes
│   │   ├── data/                       # Scripts de carga y limpieza
│   │   ├── agents/                     # Coordinación del agente de camas
│   │   ├── routers/                    # inventario · prediccion · acceso · administracion_usuarios
│   │   └── services/                   # análisis, predicción, alertas, sectores, cuentas, caché
│   └── data/
│       ├── *.csv                       # Datasets originales (sin modificar)
│       └── procesados/                 # Datasets limpios y revisión de HDHI
├── frontend/
│   ├── portada.html                    # Portada, registro e inicio de sesión
│   ├── index.html                      # Panel principal
│   ├── css/  js/                       # Estilos y lógica (panel.js, administracion.js, ...)
│   ├── assets/                         # Imagen de portada y logo
│   └── vendor/                         # Chart.js y SheetJS locales (funciona sin internet)
├── demo/                               # Panel sin servidor y arranque con doble clic
├── docs/                               # Documentación técnica y manual de instalación
├── Dockerfile · .dockerignore
├── requirements.txt
└── README.md
```

---

## 📊 Datasets

Se utilizan **tres fuentes independientes**. Se analizan por separado: no se fusionan como pacientes únicos ni representan un mismo hospital.

| Dataset | Registros utilizados | Uso principal | Capacidad simulada |
|---|---|---|---|
| 🫀 **HDHI Admission** (Hero DMC Heart Institute) | 14.331 episodios revisados | Admisiones, ocupación y ALOS por patología y edad | 190 camas |
| 🏨 **Hospital Length of Stay** (Microsoft) | 100.000 internaciones | Estancias y comparación de demanda | 1.280 camas |
| 🧾 **Healthcare** (sintético, Kaggle) | 54.966 registros limpios | Exploración de internaciones y escenarios | 570 camas |

### Limpieza

| Dataset | Original | Final | Principales tareas |
|---|---|---|---|
| HDHI | 15.757 | 14.331 episodios | Columnas a `snake_case`, `EMPTY` → nulo, validación de fechas vs. duración, consolidación de episodios |
| LengthOfStay | 100.000 | 100.000 | Verificación de fechas, nulos y duplicados (sin hallazgos) |
| Healthcare | 55.500 | 54.966 | 534 duplicados exactos eliminados, cálculo de `duracion_internacion` |

Los archivos que consume el agente están en `backend/data/procesados/`:

```text
healthcare_limpio.csv
lengthofstay_limpio.csv
revision_hdhi/episodios/hdhi_episodios_candidatos.csv
```

---

## 🖥️ El panel

| Sección | Qué muestra |
|---|---|
| **01 Proyección** | Ocupación, camas libres, ingresos y altas para 7, 15 o 30 días; mapa de camas por día, calendario con resumen de demanda, escenarios Normal / Límite / Crítico y alertas |
| **02 Estancias · HDHI** | Tiempo medio de estancia (ALOS) con barras por patología y dona por grupo etario |
| **03 UTI y general** | Simulación por sectores con censos, capacidades, estancias y traslados propios |
| **04 Evaluación** | Comparación de métodos de ingresos, backtesting y error del agente por horizonte |
| **⚙ Administración** | Solo administradores: alta, edición, roles, activación/desactivación de cuentas, filtros e historial de cambios |

Todas las tablas se pueden **exportar a Excel**. El menú lateral se pliega y el panel se adapta a celulares.

---

## 🧠 Cómo funciona el agente

```text
 Fecha de censo + capacidad
            │
            ▼
 ┌─────────────────────────┐    ┌──────────────────────────┐
 │ Censo: internados hoy   │    │ Pronóstico de ingresos   │
 │ (reconstruido)          │    │ (método elegido por WAPE)│
 └────────────┬────────────┘    └────────────┬─────────────┘
              │       ┌──────────────────┐   │
              └──────►│ Altas esperadas  │◄──┘
                      │ (curva de estancia)
                      └────────┬─────────┘
                               ▼
         Ocupación proyectada D+1 … D+7 / 15 / 30  (+ P90)
                               │
                               ▼
        🔴 Saturación (> 90 %)   🟠 Preventiva (prob. ≥ 30 %)
```

- **Ingresos:** se comparan cinco métodos (media 28 días, semana anterior, día de la semana, estacional y regresión Ridge) y se elige el de menor WAPE, solo si mejora a la media en ≥ 3 % (parsimonia).
- **Altas:** se estiman de forma agregada con la distribución histórica de duración de estancia.
- **Alertas:**
  - **Saturación:** ocupación esperada **> 90 %** de la capacidad.
  - **Preventiva:** sin saturación esperada, pero la probabilidad diaria de superar el umbral es **≥ 30 %**.
- **UTI y general:** simulación por sectores con censos, capacidades, estancias y traslados ingresados por el usuario.

---

## 🔌 API

**Datos y agente**

| Método | Ruta | Función |
|---|---|---|
| `GET` | `/salud` | Estado del servidor |
| `GET` | `/datasets` | Fuentes disponibles |
| `GET` | `/estadisticas` | Indicadores históricos (ALOS, mediana, P90, ingresos/día) |
| `GET` | `/censo` | Ocupación en una fecha |
| `POST` | `/proyeccion-camas` | **Proyección y alertas** (`dias` de 1 a 30; por defecto 7) |
| `GET` | `/escenarios` | Escenarios Normal / Límite / Crítico |
| `GET` | `/sectores/parametros` | Auditoría histórica para la simulación UTI y general |

**Modelo de predicción**

| Método | Ruta | Función |
|---|---|---|
| `GET` | `/modelo/demanda` | Método de ingresos elegido y métricas |
| `GET` | `/modelo/backtest` | Ingresos reales vs. pronosticados |
| `GET` | `/modelo/evaluacion-agente` | Error del agente contra la ocupación real (`dias=7\|15\|30`) |
| `GET` | `/modelo/ocupacion-real` | Camas realmente ocupadas después de una fecha |

**Acceso y administración**

| Método | Ruta | Función |
|---|---|---|
| `GET` | `/auth/sesion` | Sesión actual |
| `POST` | `/auth/ingresar` · `/auth/salir` | Inicio y cierre de sesión |
| `POST` | `/auth/registrar` | Registro web de usuarios comunes |
| `GET` · `POST` | `/auth/admin/usuarios` | Listar y crear cuentas |
| `PATCH` | `/auth/admin/usuarios/{usuario}` | Editar nombre, correo y rol |
| `PATCH` | `/auth/admin/usuarios/{usuario}/estado` | Activar o desactivar una cuenta |
| `GET` | `/auth/admin/auditoria` | Historial de cambios |

Ejemplo:

```json
POST /proyeccion-camas
{ "dataset": "hdhi", "fecha": "2019-03-01", "dias": 7 }
```

La documentación interactiva está en **`/docs`** (requiere sesión iniciada).

---

**Acceso desde la nube**
La aplicación está publicada en Render y se puede utilizar desde un navegador, sin instalar Python, Docker ni ejecutar el servidor en la computadora de quien ingresa.

Enlace de acceso: [Acceder al agente](https://g1-agente-de-gestion-de-camas-y-demanda.onrender.com/panel)

**Cómo ingresar**
1. Abrir el enlace con conexión a internet.
2. Crear una cuenta desde el registro público o iniciar sesión con una cuenta habilitada en la versión publicada.
3. Acceder al panel y utilizar las consultas y simulaciones disponibles según el rol.
4. Cerrar la sesión al terminar, especialmente si se utiliza una computadora compartida.
El registro público crea cuentas de usuario común. Las operaciones de Administración requieren el rol correspondiente y se controlan en el servidor. No se necesitan credenciales administrativas para utilizar las funciones de consulta autorizadas.

**Servicios utilizados**
Servicio	Función en la publicación
GitHub	Conserva el código y los cambios del equipo.
Render	Ejecuta la aplicación, incluyendo la interfaz, la API y los cálculos.
Docker	Define el entorno y el arranque de la aplicación publicada.
Neon PostgreSQL	Guarda cuentas, sesiones e historial de auditoría en una base compartida.

La conexión con Neon se configura en Render mediante la variable de entorno DATABASE_URL. Su valor contiene credenciales y no debe incluirse en el repositorio ni en la documentación pública.

Las cuentas creadas en la página pública se consultan desde la misma base compartida, independientemente del dispositivo. Una cuenta de una instalación local sólo está disponible en la nube si fue migrada o creada también en esa base. Git comparte el código; no sincroniza automáticamente las cuentas de SQLite de cada computadora.

Los datos históricos hospitalarios continúan en los archivos del proyecto. Publicar la aplicación no la conecta con un hospital en tiempo real ni modifica el alcance académico del agente.

**API y demostración desde la nube**
La interfaz y la API se utilizan bajo el mismo dominio público. La documentación interactiva se consulta en la ruta /docs de la versión publicada, con la sesión y los permisos que exija la configuración de acceso.

Para la demostración se puede abrir el panel desde este enlace público y utilizar los escenarios Normal, Límite y Crítico. No hace falta iniciar el servidor local ni mantener abierta la computadora de desarrollo para que Render ejecute la aplicación.

**Tiempos de carga y actualizaciones**
La instancia gratuita puede demorar al volver a arrancar después de un período sin uso. Además, una consulta nueva puede necesitar cálculos; las consultas equivalentes ya disponibles en caché pueden responder más rápido. El tiempo de arranque y el de cálculo son distintos, y no se garantiza una respuesta instantánea en todos los casos.

Guardar cambios en la computadora no actualiza por sí solo la página pública. Los cambios deben subirse a GitHub e incorporarse a un despliegue de la rama configurada en Render. Antes de presentar una actualización, se comprueba que el despliegue haya terminado y se revisa la aplicación publicada.

---

## ⚙️ Requisitos e instalación

Hay tres formas de usar el sistema:

| Opción | Para quién | Necesita |
|---|---|---|
| 🅰️ **Entorno local** | Desarrollo | Python 3.11 o superior |
| 🐳 **Docker** | Probar sin instalar Python | Docker Desktop |
| 🧪 **Demo sin servidor** (`demo/panel_sin_servidor.html`) | Respaldo para la exposición | Solo un navegador |

### 🅰️ Entorno local (Windows · PowerShell)

```powershell
git clone https://github.com/BarbyJRigoni/G1-Agente-de-Gestion-de-Camas-y-Demanda-Hospitalaria.git
cd G1-Agente-de-Gestion-de-Camas-y-Demanda-Hospitalaria

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

python backend/app/crear_usuario.py      # primera cuenta (clave de 12 a 128 caracteres)
python backend/app/crear_admin.py        # opcional: rol administrador

python -m uvicorn main:app --app-dir backend/app --reload
```

> 💡 Si PowerShell bloquea `Activate.ps1`, usar `.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend/app --reload`.

### 🐳 Docker

```powershell
docker build -t agente-camas .
docker run -d --name agente-camas -p 8000:8000 -v agente-camas-datos:/datos agente-camas
docker exec -it agente-camas python crear_usuario.py
docker exec -it agente-camas python crear_admin.py      # opcional
```

Las cuentas se guardan en el volumen `agente-camas-datos` y se conservan al recrear el contenedor.

### 🗄️ Cuentas en PostgreSQL (opcional)

Por defecto las cuentas se guardan en SQLite local. Si se define la variable de entorno `DATABASE_URL` con una dirección PostgreSQL (por ejemplo, Neon), el sistema la usa en su lugar. Para pasar las cuentas existentes:

```powershell
python backend/app/migrar_cuentas_neon.py
```

El script pide la dirección sin mostrarla y no la guarda.

Más detalle en [`docs/Manual_de_instalacion.md`](docs/Manual_de_instalacion.md) y [`docs/docker_y_entrega.md`](docs/docker_y_entrega.md).

---

## 🚀 Uso

| Recurso | URL |
|---|---|
| 🏠 Portada, registro e inicio de sesión | http://127.0.0.1:8000 |
| ❤️ Estado del servidor | http://127.0.0.1:8000/salud |
| 📘 Documentación de la API | http://127.0.0.1:8000/docs |

Los cálculos se hacen **a pedido** y se reutilizan: la primera proyección de cada fuente tarda unos segundos y después responde al instante; la evaluación del agente tarda alrededor de un minuto la primera vez y luego se lee de un archivo en menos de 1 s, aun después de reiniciar.

FastAPI sirve la interfaz y la API desde el mismo origen: no hace falta levantar un servidor aparte para el frontend. Para detenerlo, **Ctrl + C**.

---

## 📈 Resultados

### Escenarios de demostración (HDHI, censo 01/03/2019)

| Escenario | Ocupación máxima proyectada | Resultado |
|---|---|---|
| 🟢 Normal | 68,3 % | Sin alerta |
| 🟡 Límite | 89,1 % | Sin alerta |
| 🔴 Crítico | 94,1 % | **Alerta de Saturación** |
| 🔴 Capacidad reducida a 140 camas | 92,7 % | **Alerta de Saturación** |

### Pronóstico de ingresos (backtest)

| Dataset | Método elegido | MAE (ingresos/día) | WAPE diario | WAPE semanal | Cobertura IC 80 % |
|---|---|---|---|---|---|
| HDHI | Día de la semana (8 sem.) | 5,02 | 20,2 % | 10,1 % | 77,5 % |
| LengthOfStay | Media 28 días | 14,75 | 5,4 % | 2,1 % | 83,0 % |
| Healthcare | Media 28 días | 4,76 | 16,0 % | 8,5 % | 77,5 % |

> ℹ️ En HDHI el patrón semanal explica casi toda la variación (los lunes ingresan más pacientes y los domingos menos). En LengthOfStay y Healthcare gana la media: el sistema **no inventa patrones donde no los hay**.

### Evaluación del agente (ocupación, HDHI)

| Horizonte | D+1 | D+2 | D+3 | D+4 | D+5 | D+6 | D+7 |
|---|---|---|---|---|---|---|---|
| Error medio (camas) | 6,3 | 10,5 | 13,2 | 15,5 | 15,4 | 16,9 | 18,3 |
| % de la capacidad | 3,3 | 5,6 | 6,9 | 8,2 | 8,1 | 8,9 | 9,6 |

El error crece con la anticipación, como es esperable. Tras la corrección del agente, el límite superior P90 cubrió el **93,6 %** de las ocupaciones observadas en 497 predicciones comparables.

### Proyección a 7, 15 y 30 días (HDHI)

| Horizonte | Fechas evaluadas | Error promedio del agente | Error de "mantener el censo" | Cobertura del P90 |
|---|---|---|---|---|
| 7 días | 83 | 10,1 camas | 11,0 camas | 93,6 % |
| 15 días | 41 | 13,5 camas | 15,2 camas | 88,4 % |
| 30 días | 40 | 15,3 camas | 18,3 camas | 88,9 % |

> ℹ️ El error se estabiliza en torno a 16 camas (≈ 8 % de 190) y, cuanto más lejos se proyecta, **más le gana el agente a la referencia simple**. A 15 y 30 días sirve para planificar (personal, cirugías programadas), no para decisiones de un día puntual.

---

## 🧪 Notas metodológicas y limitaciones

- 🏗️ **Capacidad simulada:** los datasets no informan camas habilitadas reales; las capacidades 190 / 1.280 / 570 son supuestos del escenario.
- 🔀 **Fuentes separadas:** los tres datasets no se suman ni representan una misma red hospitalaria.
- 📉 **Sesgo conocido:** el agente subestima la ocupación en unas 3 a 5 camas (crecimiento del hospital y curva de estancia basada en internaciones terminadas).
- ⏳ **Validación temporal:** la evaluación usa solo información anterior a cada censo; alterar internaciones posteriores no cambia la predicción.
- 🏥 **UTI y general:** simulación con parámetros ingresados explícitamente; no se dispone de movimientos fechados para validarla.
- 🔢 Los valores proyectados pueden tener decimales porque representan **cantidades esperadas**.
- 🔒 **Cuentas:** contraseñas con derivación criptográfica (PBKDF2) y sal, en SQLite o PostgreSQL. Los cambios de cuentas quedan registrados en un historial de auditoría.
- 🚦 **Registro web:** asigna siempre el rol usuario y tiene límites contra abusos (5 registros cada 15 minutos por conexión y 50 por hora en total).
- ⚡ **Rendimiento:** los cálculos repetidos se guardan en una caché en memoria y la evaluación del agente en un archivo, sin cambiar los resultados.
- 🌐 **Despliegue:** publicar el sistema en internet requiere HTTPS y una configuración específica.
- 📆 **UTI y general** sigue proyectando a 7 días.
- ⚠️ **Prototipo académico:** no es un sistema clínico validado ni determina altas o derivaciones.

---

## 📚 Documentación y referencias

**Documentación del proyecto** (`docs/`)

- `Manual_de_instalacion.md` — instalación paso a paso
- `docker_y_entrega.md` — Docker y tiempos de carga
- `proyeccion_15_30_dias.md` — extensión del horizonte y su confiabilidad
- `limpieza_datasets.md` — limpieza y preparación de las fuentes
- `analisis_estadistico.md` — análisis con Pandas
- `calculo_capacidad_camas.md` — supuestos de capacidad
- `modelo_prediccion.md` — modelo de ingresos y evaluación
- `correccion_agente_verificada.md` — correcciones y verificaciones
- `sectores_uti_general.md` — simulación UTI y general
- `acceso_y_portada.md` — portada, cuentas y acceso
- `diseno_panel.md` — diseño del panel
- `guia_demo.md` — guion de la demostración

**Fuentes de datos**

- [HDHI Admission Data – Hero DMC Heart Institute (Kaggle)](https://www.kaggle.com/datasets/ashishsahani/hospital-admissions-data)
- [Hospital Length of Stay – Microsoft (GitHub)](https://github.com/microsoft/r-server-hospital-length-of-stay)
- [Healthcare Dataset – prasad22 (Kaggle)](https://www.kaggle.com/datasets/prasad22/healthcare-dataset)
- [FastAPI](https://fastapi.tiangolo.com/) · [pandas](https://pandas.pydata.org/) · [scikit-learn](https://scikit-learn.org/) · [Chart.js](https://www.chartjs.org/) · [SheetJS](https://sheetjs.com/) · [Docker](https://www.docker.com/) · [Neon](https://neon.tech/)

---

## ✍️ Autoría

**Grupo 1 · Salud**

| Integrante | Rol |
|---|---|
| **Sabrina Villegas** | Datos: limpieza, análisis, frontend y la nube en render con neo |
| **Bárbara Rigoni** | IA y predicción, agente e interfaz |
| **Darío Martínez** | Backend y API (FastAPI), Docker y documentación |

Estudiantes de la Tecnicatura Superior en Ciencias de Datos e Inteligencia Artificial — Centro Politécnico Superior Malvinas Argentinas.

Proyecto desarrollado para la materia **Desarrollo de Sistemas de Inteligencia Artificial** — 2026.
