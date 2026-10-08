"""Entrypoint FastAPI. Ejecutar desde backend/:  uvicorn app.main:app --reload"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.core import config

app = FastAPI(title=config.APP_TITLE, version=config.APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cuando existan los routers, registrarlos acá:
# from app.routers import camas
# app.include_router(camas.router)


@app.get("/", include_in_schema=False)
def inicio():
    index = config.FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"mensaje": config.APP_TITLE, "docs": "/docs"}


@app.get("/health")
def health():
    return {
        "estado": "ok",
        "version": config.APP_VERSION,
        "dataset_disponible": config.CSV_PATH.exists(),
        "umbral_saturacion": config.UMBRAL_SATURACION,
        "horizonte_dias": config.HORIZONTE_DIAS,
    }