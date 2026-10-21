# 🏥 Agente de Gestión de Camas y Demanda Hospitalaria

<p align="center">
  <img src="frontend/assets/hospital-base.svg" alt="Ilustración de la entrada del hospital" width="100%">
</p>

Agente inteligente que estima la **ocupación y disponibilidad de camas hospitalarias para los próximos 7 días**, a partir del censo de pacientes internados y de datos históricos de admisiones y estancias. Emite una **Alerta de Saturación** cuando la ocupación proyectada supera el **90 %** de la capacidad, y una **alerta preventiva** cuando la probabilidad de superarlo es significativa.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.142-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/pandas-3.0-150458?logo=pandas&logoColor=white" alt="pandas">
  <img src="https://img.shields.io/badge/scikit--learn-1.9-F7931E?logo=scikitlearn&logoColor=white" alt="scikit-learn">
  <img src="https://img.shields.io/badge/Chart.js-local-FF6384?logo=chartdotjs&logoColor=white" alt="Chart.js">
  <img src="https://img.shields.io/badge/SQLite-acceso-003B57?logo=sqlite&logoColor=white" alt="SQLite">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/estado-prototipo%20acad%C3%A9mico-yellow" alt="Status">
  <img src="https://img.shields.io/badge/versi%C3%B3n-1.0.0-blue" alt="Versión">
  <img src="https://img.shields.io/badge/Grupo%201-Salud-2e7d6b" alt="Grupo 1 Salud">
</p>

---

## 📑 Tabla de Contenidos

- [📖 Descripción del proyecto](#-descripción-del-proyecto)
- [📂 Estructura del repositorio](#-estructura-del-repositorio)
- [📊 Datasets](#-datasets)
- [🧠 Cómo funciona el agente](#-cómo-funciona-el-agente)
- [🔌 API](#-api)
- [⚙️ Requisitos e instalación](#️-requisitos-e-instalación)
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

> 🎯 **Objetivo:** apoyar la planificación de recursos hospitalarios anticipando situaciones de saturación con un horizonte de 7 días.

La aplicación incluye una **portada con inicio de sesión**, un **panel con cinco solapas** (Proyección, Estancias · HDHI, Evaluación, UTI y general, Administración) y una **API REST** documentada con FastAPI.

---

## 📂 Estructura del repositorio

```text
.
├── backend/
│   ├── app/
│   │   ├── main.py                 # Aplicación FastAPI (sirve API + frontend)
│   │   ├── crear_usuario.py        # Alta de cuentas locales
│   │   ├── crear_admin.py          # Asignación del rol administrador
│   │   ├── core/config.py          # Rutas, datasets, capacidades y umbral
│   │   ├── data/                   # Scripts de carga y limpieza
│   │   ├── services/               # Análisis, predicción, alertas, sectores, acceso
│   │   ├── agents/                 # Coordinación del agente de camas
│   │   └── routers/                # Endpoints: inventario, predicción, acceso
│   └── data/
│       ├── *.csv                   # Datasets originales (sin modificar)
│       └── procesados/             # Datasets limpios y revisión de HDHI
├── docs/                           # Documentación técnica del proyecto
├── frontend/
│   ├── assets/                     # Imagen de portada y logo
│   ├── css/  js/                   # Estilos y scripts de la portada
│   ├── vendor/                     # Chart.js local
│   ├── index.html                  # Panel principal
│   └── portada.html                # Portada e inicio de sesión
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
              Ocupación proyectada D+1 … D+7  (+ P90)
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

| Método | Ruta | Función |
|---|---|---|
| `GET` | `/salud` | Estado del servidor |
| `GET` | `/datasets` | Fuentes disponibles |
| `GET` | `/estadisticas` | Indicadores históricos (ALOS, mediana, P90, ingresos/día) |
| `GET` | `/censo` | Ocupación en una fecha |
| `POST` | `/proyeccion-camas` | **Proyección a 7 días y alertas** |
| `GET` | `/escenarios` | Escenarios Normal / Límite / Crítico |
| `GET` | `/modelo/demanda` | Método de ingresos elegido y métricas |
| `GET` | `/modelo/backtest` | Ingresos reales vs. pronosticados |
| `GET` | `/modelo/evaluacion-agente` | Desempeño del agente contra la ocupación real |
| `POST` | `/auth/ingresar` · `/auth/registrar` · `/auth/salir` | Acceso de usuarios |
| `GET` | `/auth/admin/usuarios` | Listado de usuarios (solo administradores) |

La documentación interactiva está en **`/docs`** (requiere sesión iniciada).

---

## ⚙️ Requisitos e instalación

**Requisitos**

- Windows con PowerShell (probado con Python 3.11)
- fastapi · uvicorn · pydantic · pandas · numpy · scikit-learn · scipy

**Instalación**

```powershell
git clone https://github.com/BarbyJRigoni/G1-Agente-de-Gestion-de-Camas-y-Demanda-Hospitalaria.git
cd G1-Agente-de-Gestion-de-Camas-y-Demanda-Hospitalaria
git switch sabrina                       # rama con la versión funcional

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

**Crear una cuenta** (no existen credenciales predeterminadas; contraseña de 12 a 128 caracteres):

```powershell
python backend/app/crear_usuario.py
python backend/app/crear_admin.py        # opcional: rol administrador
```

---

## 🚀 Uso

```powershell
python -m uvicorn main:app --app-dir backend/app --reload
```

| Recurso | URL |
|---|---|
| 🏠 Portada e inicio de sesión | http://127.0.0.1:8000 |
| ❤️ Estado del servidor | http://127.0.0.1:8000/salud |
| 📘 Documentación de la API | http://127.0.0.1:8000/docs |

FastAPI sirve la interfaz y la API desde el mismo origen: no hace falta levantar un servidor aparte para el frontend. Para detenerlo, **Ctrl + C**.

> 💡 Si PowerShell bloquea `Activate.ps1`, usar directamente `.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend/app --reload`.

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

---

## 🧪 Notas metodológicas y limitaciones

- 🏗️ **Capacidad simulada:** los datasets no informan camas habilitadas reales; las capacidades 190 / 1.280 / 570 son supuestos del escenario.
- 🔀 **Fuentes separadas:** los tres datasets no se suman ni representan una misma red hospitalaria.
- 📉 **Sesgo conocido:** el agente subestima la ocupación en unas 3 a 5 camas (crecimiento del hospital y curva de estancia basada en internaciones terminadas).
- ⏳ **Validación temporal:** la evaluación usa solo información anterior a cada censo; alterar internaciones posteriores no cambia la predicción.
- 🏥 **UTI y general:** simulación con parámetros ingresados explícitamente; no se dispone de movimientos fechados para validarla.
- 🔢 Los valores proyectados pueden tener decimales porque representan **cantidades esperadas**.
- 🔒 **Acceso local:** contraseñas con derivación criptográfica y sal en SQLite; publicar el sistema requiere HTTPS y un despliegue específico.
- ⚠️ **Prototipo académico:** no es un sistema clínico validado ni determina altas o derivaciones.

---

## 📚 Documentación y referencias

**Documentación del proyecto** (`docs/`)

- `limpieza_datasets.md` — limpieza y preparación de las fuentes
- `analisis_estadistico.md` — análisis con Pandas
- `calculo_capacidad_camas.md` — supuestos de capacidad
- `modelo_prediccion.md` — modelo de ingresos y evaluación
- `correccion_agente_verificada.md` — correcciones y verificaciones
- `sectores_uti_general.md` — simulación UTI y general
- `acceso_y_portada.md` — portada, cuentas y acceso
- `guia_demo.md` — guion de la demostración

**Fuentes de datos**

- [HDHI Admission Data – Hero DMC Heart Institute (Kaggle)](https://www.kaggle.com/datasets/ashishsahani/hospital-admissions-data)
- [Hospital Length of Stay – Microsoft (GitHub)](https://github.com/microsoft/r-server-hospital-length-of-stay)
- [Healthcare Dataset – prasad22 (Kaggle)](https://www.kaggle.com/datasets/prasad22/healthcare-dataset)
- [FastAPI](https://fastapi.tiangolo.com/) · [pandas](https://pandas.pydata.org/) · [scikit-learn](https://scikit-learn.org/) · [Chart.js](https://www.chartjs.org/)

---

## ✍️ Autoría

**Grupo 1 · Salud**

| Integrante | Rol |
|---|---|
| **Sabrina Villegas** | Datos: limpieza y análisis |
| **Bárbara Rigoni** | IA y predicción, agente e interfaz |
| **Darío Martínez** | Backend y API (FastAPI) |

Estudiantes de la Tecnicatura Superior en Ciencias de Datos e Inteligencia Artificial — Centro Politécnico Superior Malvinas Argentinas.

Proyecto desarrollado para la materia **Desarrollo de Sistemas de Inteligencia Artificial** — 2026.
