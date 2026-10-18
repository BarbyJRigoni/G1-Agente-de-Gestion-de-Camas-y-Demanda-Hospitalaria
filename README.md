# Agente de Gestión de Camas y Demanda Hospitalaria

Proyecto – Agentes Inteligentes  – Desarrollo de Sistemas de I.A 2026.

**Grupo 1 · Salud **

Agente que estima la ocupación y disponibilidad de camas para los próximos **7 días**, utilizando el censo de pacientes y datos históricos de admisiones y estancias.

Emite una **Alerta de Saturación** cuando la ocupación proyectada supera el **90 %** de la capacidad indicada.

La versión funcional se encuentra en la rama **sabrina**. 

## Dataset

Se utilizan tres datasets, analizados por separado:

| Dataset | Registros utilizados | Uso |

| HDHI Admission | 14.331 episodios revisados y consolidados | Admisiones, ocupación y ALOS por patología y grupo etario. |
| Hospital Length of Stay | 100.000 internaciones | Análisis de estancias y comparación de demanda. |
| Healthcare | 54.966 registros limpios | Exploración de internaciones y escenarios con datos sintéticos. |

Los datasets no se fusionan como pacientes únicos ni representan una misma red de cinco hospitales.

Los archivos originales se conservan en `backend/data/`. Los resultados de limpieza y revisión se encuentran en `backend/data/procesados/`.

### Archivos utilizados por el agente

- **HDHI:** `revision_hdhi/episodios/hdhi_episodios_candidatos.csv`.
- **Healthcare:** `healthcare_limpio.csv`.
- **LengthOfStay:** `lengthofstay_limpio.csv`.

Estas rutas parten de `backend/data/procesados/`.

`hdhi_limpio.csv` corresponde a una limpieza anterior y se conserva como antecedente. Los archivos de revisión documentan duplicados, conflictos y registros apartados.

## Estructura

Estructura principal de la versión funcional. Se omiten cachés, instaladores y respaldos locales.

```text
G1_Agente_Gestion_Camas_Demanda_Hospitalaria/
│
├── .venv/                                  → Entorno local de Python
│
├── backend/
│   ├── app/
│   │   ├── main.py                          → Aplicación FastAPI
│   │   ├── crear_usuario.py                 → Creación de cuentas locales
│   │   │
│   │   ├── core/
│   │   │   └── config.py                    → Rutas, capacidades y configuración
│   │   │
│   │   ├── data/
│   │   │   ├── loader.py                    → Carga y exploración de datasets
│   │   │   ├── limpieza_hdhi.py
│   │   │   ├── limpieza_hdhi_revision.py
│   │   │   ├── limpieza_healthcare.py
│   │   │   ├── limpieza_lengthofstay.py
│   │   │   └── preparar_episodios_hdhi.py
│   │   │
│   │   ├── services/
│   │   │   ├── acceso.py                    → Usuarios y sesiones
│   │   │   ├── alertas.py                   → Alertas de ocupación
│   │   │   ├── analisis.py                  → Carga compartida e indicadores
│   │   │   ├── analisis_hdhi.py             → ALOS por patología y edad
│   │   │   ├── modelo_ocupacion.py          → Modelo de ocupación
│   │   │   ├── prediccion.py                → Predicción de ingresos y evaluación
│   │   │   └── sectores.py                  → Simulación de UTI y general
│   │   │
│   │   ├── agents/
│   │   │   └── inventario_agent.py          → Coordinación del agente de camas
│   │   │
│   │   └── routers/
│   │       ├── acceso.py                    → Inicio y cierre de sesión
│   │       ├── inventario.py                → Censos, estadísticas y proyección
│   │       └── prediccion.py                → Consultas del modelo y evaluación
│   │
│   └── data/
│       ├── HDHI Admission data.csv          → Dataset original
│       ├── healthcare_dataset.csv           → Dataset original
│       ├── LengthOfStay.csv                 → Dataset original
│       │
│       └── procesados/
│           ├── hdhi_limpio.csv
│           ├── healthcare_limpio.csv
│           ├── lengthofstay_limpio.csv
│           │
│           └── revision_hdhi/
│               ├── hdhi_casos_a_revisar.csv
│               ├── hdhi_duplicados_retirados_revision.csv
│               ├── hdhi_limpio_revision.csv
│               ├── hdhi_resumen_revision.json
│               │
│               └── episodios/
│                   ├── hdhi_conflictos_por_campo.csv
│                   ├── hdhi_episodios_apartados.csv
│                   ├── hdhi_episodios_candidatos.csv
│                   ├── hdhi_indicadores_candidatos.json
│                   └── resumen_episodios.json
│
├── docs/
│   ├── acceso_y_portada.md
│   ├── analisis_estadistico.md
│   ├── bitacora_dario.md
│   ├── calculo_capacidad_camas.md
│   ├── correccion_agente_verificada.md
│   ├── diseno_panel.md
│   ├── guia_demo.md
│   ├── limpieza_datasets.md
│   ├── mejoras_claridad_agente.md
│   ├── modelo_prediccion.md
│   └── sectores_uti_general.md
│
├── frontend/
│   ├── assets/
│   │   └── hospital-base.svg                → Fondo ilustrativo de la portada
│   │
│   ├── vendor/
│   │   ├── Chart-LICENSE.md
│   │   └── chart.umd.min.js                  → Biblioteca local de gráficos
│   │
│   ├── index.html                          → Panel principal y solapas
│   └── portada.html                        → Portada e inicio de sesión
│
├── .gitignore
├── CAMBIOS.md
├── README.md
└── requirements.txt
```

`backend/app/data/` contiene los scripts de procesamiento.
`backend/data/` contiene los archivos de datos.


## Funcionamiento

La interfaz está organizada en cuatro solapas:

1. **Proyección:** ingresos, altas inferidas, ocupación y camas disponibles durante siete días.
2. **Estancias · HDHI:** tiempo medio de estancia por patología/comorbilidad y grupo etario.
3. **Evaluación:** comparación de métodos y errores históricos del modelo agregado.
4. **UTI y general:** simulación con censos, capacidades y alertas independientes por sector.

El endpoint principal es **`POST /proyeccion-camas`**, que recibe el censo y los parámetros del escenario.

La fecha del censo es el punto de partida de la proyección histórica. Por ejemplo, desde el 01/03/2019 se proyecta del 02/03/2019 al 08/03/2019.

Los casos **Normal**, **Límite** y **Crítico** modifican la capacidad supuesta del ejemplo, manteniendo su fecha y demanda.

## Ejecución local

Desde la raíz del proyecto, utilizar la rama funcional:

```powershell
git switch sabrina
```

La primera vez, crear y activar el entorno e instalar las dependencias:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Si el entorno ya está preparado, basta con activarlo:

```powershell
.\.venv\Scripts\Activate.ps1
```

Crear una cuenta local la primera vez:

```powershell
python backend/app/crear_usuario.py
```

La contraseña debe tener entre 12 y 128 caracteres. No aparece en pantalla mientras se escribe. No existen credenciales predeterminadas.

Iniciar el servidor:

```powershell
python -m uvicorn main:app --app-dir backend/app --reload
```

- **Portada:** http://127.0.0.1:8000
- **Estado del servidor:** http://127.0.0.1:8000/salud
- **Documentación de la API:** http://127.0.0.1:8000/docs, después de iniciar sesión.

Mantener la terminal abierta durante el uso. Para detener el servidor, presionar **Ctrl+C**.

## Limitaciones y mejoras

- Es un prototipo académico, no un sistema clínico validado ni una fuente de ocupación en tiempo real.
- Las capacidades de camas son supuestos de simulación.
- Los datasets se analizan por separado.
- La revisión y selección de episodios de HDHI puede introducir sesgos.
- Los diagnósticos desconocidos no se interpretan como ausencia de enfermedad.
- Los valores proyectados pueden contener decimales porque representan cantidades esperadas.
- UTI y general utilizan parámetros ingresados explícitamente. No se dispone de movimientos fechados suficientes para validar la ocupación real por sector.
- La evaluación del modelo agregado no se transfiere a la simulación sectorial.
- Queda por mejorar la selección de fechas válidas y simplificar algunas explicaciones de los gráficos.
- El acceso está pensado para uso local. Publicar el sistema requiere configurar HTTPS y revisar el despliegue.

## Documentación

La documentación de la versión funcional se encuentra en la carpeta `docs/` de la rama `sabrina`.

- `limpieza_datasets.md`: limpieza y preparación de las fuentes.
- `analisis_estadistico.md`: análisis con Pandas.
- `modelo_prediccion.md`: descripción del modelo de ingresos.
- `correccion_agente_verificada.md`: correcciones y verificaciones.
- `acceso_y_portada.md`: portada, cuentas y acceso local.
- `sectores_uti_general.md`: funcionamiento y límites de la simulación sectorial