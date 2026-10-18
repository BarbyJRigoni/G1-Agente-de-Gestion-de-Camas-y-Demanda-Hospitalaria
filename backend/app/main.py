"""
Punto de entrada de la API (FastAPI).

Crea la aplicacion, habilita CORS para el frontend, registra los endpoints
de routers/inventario.py y sirve el dashboard en la raiz.

Ejecutar desde la carpeta backend/app:
    uvicorn main:app --reload
Documentacion interactiva:
    http://localhost:8000/docs
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from urllib.parse import urlsplit
from services import acceso
from routers.acceso import router as router_acceso

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

# El frontend y la API se sirven desde el mismo origen; no se habilita CORS abierto.
@app.middleware("http")
async def proteger_acceso(request: Request, siguiente):
    request.state.usuario = acceso.usuario_de_sesion(request.cookies.get(acceso.COOKIE))
    ruta = request.url.path
    publica = ruta in {"/", "/ingresar", "/auth/sesion", "/auth/ingresar", "/auth/salir", "/salud", "/portada/hospital", "/favicon.ico"} or ruta.startswith("/vendor/")
    if not publica and not request.state.usuario:
        respuesta = (RedirectResponse("/ingresar", status_code=303) if ruta in {"/panel", "/docs", "/redoc", "/docs/oauth2-redirect"}
                     else JSONResponse(status_code=401, content={"detail":"Inicia sesion para acceder al agente."}))
    elif request.method not in {"GET", "HEAD", "OPTIONS"}:
        origen = request.headers.get("origin")
        base = urlsplit(str(request.base_url))
        esperado = f"{base.scheme}://{base.netloc}".lower()
        valido = origen.rstrip("/").lower() == esperado if origen else request.headers.get("x-requested-with") == "AgenteCamas"
        if not valido or request.headers.get("sec-fetch-site") == "cross-site":
            respuesta = JSONResponse(status_code=403, content={"detail":"Solicitud de origen no permitido."})
        else:
            respuesta = await siguiente(request)
    else:
        respuesta = await siguiente(request)
    respuesta.headers["Cache-Control"] = "no-store"
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Referrer-Policy"] = "same-origin"
    return respuesta

app.include_router(router_acceso)

# Endpoints del agente (paso 4)
app.include_router(router_camas)
app.include_router(router_prediccion)
app.mount("/vendor", StaticFiles(directory=config.RUTA_FRONTEND.parent / "vendor", check_dir=False), name="vendor")


@app.get("/salud", tags=["Sistema"], summary="Estado de la API")
def salud():
    """Permite comprobar rapidamente que el servidor esta funcionando."""
    archivos = {}
    for nombre in config.DATASETS:
        ruta = (config.CARPETA_PROCESADOS / 'revision_hdhi' / 'episodios' / 'hdhi_episodios_candidatos.csv'
                if nombre == 'hdhi' else config.CARPETA_PROCESADOS / f'{nombre}_limpio.csv')
        archivos[nombre] = ruta.is_file() and ruta.stat().st_size > 0
    return {"estado": "ok" if all(archivos.values()) else "datos_incompletos",
            "version": config.APP_VERSION, "datasets": list(config.DATASETS),
            "datos_disponibles": all(archivos.values()), "archivos_disponibles": archivos}


@app.exception_handler(FileNotFoundError)
def archivo_faltante(request, error):
    return JSONResponse(status_code=503, content={
        "detail": "Falta un archivo de datos necesario. Revise /salud y los CSV procesados."})



@app.get("/", include_in_schema=False)
def inicio(request: Request):
    if request.state.usuario:
        return RedirectResponse("/panel", status_code=303)
    return FileResponse(config.RUTA_FRONTEND.parent / "portada.html")


@app.get("/ingresar", include_in_schema=False)
def portada(request: Request):
    if request.state.usuario:
        return RedirectResponse("/panel", status_code=303)
    return FileResponse(config.RUTA_FRONTEND.parent / "portada.html")


@app.get("/panel", include_in_schema=False)
def panel():
    return FileResponse(config.RUTA_FRONTEND)


@app.get("/portada/hospital", include_in_schema=False)
def imagen_hospital():
    carpeta = config.RUTA_FRONTEND.parent / "assets"
    for extension in ("jpg", "jpeg", "png", "webp"):
        ruta = carpeta / f"hospital.{extension}"
        if ruta.is_file():
            return FileResponse(ruta)
    return FileResponse(carpeta / "hospital-base.svg", media_type="image/svg+xml")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)
