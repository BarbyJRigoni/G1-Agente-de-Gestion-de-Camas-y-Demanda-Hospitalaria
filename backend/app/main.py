"""
Punto de entrada de la API (FastAPI).

Crea la aplicacion, habilita CORS para el frontend, registra los endpoints
de routers/inventario.py y sirve el dashboard en la raiz.

Ejecutar desde la carpeta backend/app:
    uvicorn main:app --reload
Documentacion interactiva:
    http://localhost:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from core import config
from routers.inventario import router as router_camas
from routers.prediccion import router as router_prediccion   # modelo de demanda (Barbara)

app = FastAPI(
    title=config.APP_TITULO,
    version=config.APP_VERSION,
    description=(
        "Agente que proyecta la ocupacion de camas de los proximos "
        f"{config.DIAS_PROYECCION} dias a partir del censo actual y emite una "
        f"**Alerta de Saturacion** cuando supera el {config.UMBRAL_SATURACION:.0%} de la capacidad.\n\n"
        "Grupo 1 — Desarrollo de Sistemas de I.A. — Instituto Terciario Malvinas Argentinas."
    ),
)

# CORS: permite que el frontend (otra pagina u otro puerto) consuma la API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoints del agente (paso 4)
app.include_router(router_camas)
app.include_router(router_prediccion)


@app.get("/salud", tags=["Sistema"], summary="Estado de la API")
def salud():
    """Permite comprobar rapidamente que el servidor esta funcionando."""
    return {
        "estado": "ok",
        "version": config.APP_VERSION,
        "datasets": list(config.DATASETS),
        "datos_disponibles": config.CARPETA_PROCESADOS.exists(),
    }


@app.get("/", include_in_schema=False)
def inicio():
    """Muestra el dashboard si existe; si no, indica donde esta la documentacion."""
    if config.RUTA_FRONTEND.exists() and config.RUTA_FRONTEND.stat().st_size > 0:
        return FileResponse(config.RUTA_FRONTEND)
    return {"mensaje": "API funcionando. Documentacion en /docs"}
