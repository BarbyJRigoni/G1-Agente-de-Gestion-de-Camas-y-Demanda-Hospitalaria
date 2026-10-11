"""
Configuracion central del backend.

Reune en un solo lugar las rutas, los datasets disponibles, la capacidad
de camas y el umbral de alerta. Los demas modulos importan estos valores
en lugar de escribirlos a mano.
"""
from pathlib import Path

# ============================================================
# Rutas
# ============================================================
BACKEND_DIR = Path(__file__).resolve().parents[2]          # .../backend
CARPETA_PROCESADOS = BACKEND_DIR / "data" / "procesados"   # CSV limpios (Sabrina)
RUTA_FRONTEND = BACKEND_DIR.parent / "frontend" / "index.html"

# ============================================================
# Datos de la API (se muestran en /docs)
# ============================================================
APP_TITULO = "Agente de Gestion de Camas y Demanda Hospitalaria"
APP_VERSION = "1.0.0"

# ============================================================
# Datasets
# ============================================================
# Cada dataset nombra distinto las mismas columnas. Este mapa las traduce
# para que el backend trabaje con los tres sin modificar la limpieza.
#   capacidad_total / capacidad_uti: el dataset no trae la capacidad real.
#   Se estima como el percentil 95 de la ocupacion historica dividido 0,90,
#   asi la alerta del 90 % se activa solo en los picos de demanda.
#   fecha_demo: "hoy" simulado para las pruebas (dentro del rango de datos).
DATASETS = {
    "hdhi": {
        "nombre": "HDHI Admission (Hero DMC Heart Institute)",
        "ingreso": "fecha_ingreso",
        "egreso": "fecha_egreso",
        "duracion": "duration_of_stay",
        "dias_uti": "duration_of_intensive_unit_stay",   # unico dataset con UTI
        "capacidad_total": 220,                          # p95 = 197 camas
        "capacidad_uti": 130,                            # p95 = 115 camas
        "fecha_demo": "2019-03-01",
    },
    "lengthofstay": {
        "nombre": "Hospital Length of Stay (Microsoft)",
        "ingreso": "vdate",
        "egreso": "discharged",
        "duracion": "lengthofstay",
        "dias_uti": None,
        "capacidad_total": 1600,                         # p95 = 1.427 camas
        "capacidad_uti": None,
        "fecha_demo": "2012-12-01",
    },
    "healthcare": {
        "nombre": "Healthcare Dataset (Kaggle, sintetico)",
        "ingreso": "date_of_admission",
        "egreso": "discharge_date",
        "duracion": "duracion_internacion",
        "dias_uti": None,
        "capacidad_total": 600,                          # p95 = 539 camas
        "capacidad_uti": None,
        "fecha_demo": "2024-04-01",
    },
}
DATASET_POR_DEFECTO = "hdhi"

# ============================================================
# Agente y alertas (consigna Grupo 1)
# ============================================================
DIAS_PROYECCION = 7          # proyeccion de los proximos 7 dias
UMBRAL_SATURACION = 0.90     # ocupacion proyectada > 90 % -> "Alerta de Saturacion"