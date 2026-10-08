"""Rutas y parámetros de configuración del agente de camas."""
from pathlib import Path

# backend/app/core/config.py -> parents[2] = backend/
BASE_DIR = Path(__file__).resolve().parents[2]
APP_DIR = BASE_DIR / "app"
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR.parent / "frontend"
TEMPLATES_DIR = APP_DIR / "templates"

# Dataset de internaciones (HDHI Admission data)
CSV_PATH = BASE_DIR / "HDHI Admission data.csv"  # misma ruta que usa data/loader.py

# Red hospitalaria
SEDES = 5
HORIZONTE_DIAS = 7          # días a proyectar
UMBRAL_SATURACION = 0.90    # alerta si ocupación proyectada > 90 % de la capacidad

# API
APP_TITLE = "Agente de Gestión de Camas y Demanda Hospitalaria"
APP_VERSION = "0.1.0"
CORS_ORIGINS = ["*"]
