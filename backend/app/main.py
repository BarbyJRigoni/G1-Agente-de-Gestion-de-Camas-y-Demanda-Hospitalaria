"""
Punto de entrada de la API (FastAPI).

Crea la aplicacion, protege el acceso, registra los endpoints
y sirve la portada, el panel y sus archivos de estilos y JavaScript.

Ejecutar desde la carpeta backend/app:
    uvicorn main:app --reload
Documentacion interactiva:
    http://localhost:8000/docs
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from urllib.parse import urlsplit
import asyncio
import hashlib
import json
import logging
import tempfile
import threading
import time
from services import acceso
from routers.acceso import router as router_acceso

from core import config
from pathlib import Path
from services import prediccion
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

# ============================================================
# Precalculo al arrancar (tiempos de carga)
# ============================================================
# La primera proyeccion y la evaluacion tardan porque entrenan los modelos.
# Se calculan en segundo plano al iniciar el servidor. Si alguien pide esos
# datos mientras tanto, la consulta ESPERA a que termine el precalculo en vez
# de calcular lo mismo en paralelo (eso hacia que todo tardara el doble).
panel_listo = threading.Event()        # proyecciones de la fecha de demo
evaluacion_lista = threading.Event()   # solapa Evaluacion

RUTAS_PANEL = ("/proyeccion-camas", "/escenarios", "/modelo/ocupacion-real")
RUTAS_EVALUACION = ("/modelo/demanda", "/modelo/backtest", "/modelo/evaluacion-agente")
ESPERA_MAXIMA = 180     # segundos; despues la consulta sigue y calcula por su cuenta


# ============================================================
# Evaluacion guardada en un archivo
# ============================================================
# La evaluacion del agente siempre da lo mismo para los mismos datos y el mismo
# codigo. La primera vez se calcula y se guarda en un .json; en los siguientes
# arranques se lee del archivo (menos de 1 s en vez de ~1 min).
# El nombre del archivo lleva una "huella" de los datos y del codigo: si algo
# cambia, la huella cambia y la evaluacion se vuelve a calcular sola.
CARPETA_EVALUACIONES = Path(tempfile.gettempdir()) / "AgenteCamas" / "evaluaciones"
_evaluar_agente_original = prediccion.evaluar_agente
_evaluaciones = {}
_candado_evaluacion = threading.Lock()


def huella_datos_y_codigo():
    """Resume en 16 caracteres los CSV procesados y el codigo del agente."""
    h = hashlib.sha256()
    for ruta in sorted(config.CARPETA_PROCESADOS.rglob("*.csv")):
        info = ruta.stat()
        h.update(f"{ruta.name}|{info.st_size}|{info.st_mtime_ns}".encode())
    carpeta_app = Path(__file__).resolve().parent
    for carpeta in ("agents", "core", "services"):
        for ruta in sorted((carpeta_app / carpeta).glob("*.py")):
            h.update(ruta.read_bytes())
    return h.hexdigest()[:16]


def evaluar_agente_guardada(dataset="hdhi", cada_dias=7, dias=config.DIAS_PROYECCION):
    """Igual que prediccion.evaluar_agente, pero lee y guarda el resultado en disco.
    `dias` es el horizonte evaluado (7 por defecto; 15 y 30 para las proyecciones largas)."""
    clave = (dataset, cada_dias, dias)
    with _candado_evaluacion:
        if clave not in _evaluaciones:
            horizonte = "" if dias == config.DIAS_PROYECCION else f"_h{dias}"
            archivo = CARPETA_EVALUACIONES / f"{dataset}_{cada_dias}d{horizonte}_{huella_datos_y_codigo()}.json"
            try:
                _evaluaciones[clave] = json.loads(archivo.read_text(encoding="utf-8"))
            except (OSError, ValueError):          # no existe o esta danado: se calcula
                _evaluaciones[clave] = _evaluar_agente_original(dataset, cada_dias, dias)
                try:
                    archivo.parent.mkdir(parents=True, exist_ok=True)
                    archivo.write_text(json.dumps(_evaluaciones[clave]), encoding="utf-8")
                except OSError:
                    pass                               # si no se puede guardar, sigue en memoria
        return _evaluaciones[clave]


# El endpoint /modelo/evaluacion-agente usa esta version
prediccion.evaluar_agente = evaluar_agente_guardada


def precalcular():
    from agents.inventario_agent import proyectar_camas
    from services.prediccion import modelo_demanda

    log = logging.getLogger("uvicorn.error")
    inicio = time.perf_counter()
    try:
        # 0. Si la evaluacion ya esta guardada, se lee primero (tarda menos de 1 s)
        if (CARPETA_EVALUACIONES / f"hdhi_7d_{huella_datos_y_codigo()}.json").is_file():
            evaluar_agente_guardada("hdhi")
            evaluacion_lista.set()
            log.info("Evaluacion leida del archivo en %.1f s", time.perf_counter() - inicio)
        # 1. Lo que pide el panel al entrar: la fecha de demo de cada dataset
        for dataset, datos in config.DATASETS.items():
            proyectar_camas(dataset, fecha=datos["fecha_demo"])
            modelo_demanda(dataset)
        panel_listo.set()
        log.info("Precalculo del panel listo en %.1f s", time.perf_counter() - inicio)
        # 2. La solapa Evaluacion (es lo mas lento)
        evaluar_agente_guardada("hdhi")
        log.info("Precalculo completo en %.1f s", time.perf_counter() - inicio)
    except Exception as error:
        log.warning("Precalculo incompleto: %s", error)
    finally:
        panel_listo.set()          # si algo fallo, no se deja esperando a nadie
        evaluacion_lista.set()


@app.on_event("startup")
def iniciar_precalculo():
    threading.Thread(target=precalcular, daemon=True).start()


@app.middleware("http")
async def esperar_precalculo(request: Request, siguiente):
    ruta = request.url.path
    evento = (panel_listo if ruta.startswith(RUTAS_PANEL)
              else evaluacion_lista if ruta.startswith(RUTAS_EVALUACION) else None)
    limite = time.perf_counter() + ESPERA_MAXIMA
    while evento is not None and not evento.is_set() and time.perf_counter() < limite:
        await asyncio.sleep(0.2)
    return await siguiente(request)


# El frontend y la API se sirven desde el mismo origen; no se habilita CORS abierto.
@app.middleware("http")
async def proteger_acceso(request: Request, siguiente):
    request.state.usuario = acceso.usuario_de_sesion(request.cookies.get(acceso.COOKIE))
    ruta = request.url.path
    
    publica = ruta in {
        "/",
        "/ingresar",
        "/auth/sesion",
        "/auth/ingresar",
        "/auth/registrar",
        "/auth/salir",
        "/salud",
        "/portada/hospital",
        "/portada/logo-politecnico",
        "/portada/css/portada.css",
        "/portada/js/acceso.js",
        "/portada/js/registro.js",
        "/favicon.ico",
    } or ruta.startswith("/vendor/")


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

@app.get("/portada/css/portada.css", include_in_schema=False)
def css_portada():
    return FileResponse(
        config.RUTA_FRONTEND.parent / "css" / "portada.css",
        media_type="text/css"
    )


@app.get("/portada/js/acceso.js", include_in_schema=False)
def js_acceso():
    return FileResponse(
        config.RUTA_FRONTEND.parent / "js" / "acceso.js",
        media_type="text/javascript"
    )


@app.get("/portada/js/registro.js", include_in_schema=False)
def js_registro():
    return FileResponse(
        config.RUTA_FRONTEND.parent / "js" / "registro.js",
        media_type="text/javascript"
    )

# Recursos del panel: requieren una sesión, igual que /panel.
@app.get("/panel/css/panel.css", include_in_schema=False)
def css_panel():
    return FileResponse(config.RUTA_FRONTEND.parent / "css" / "panel.css", media_type="text/css")


@app.get("/panel/js/panel.js", include_in_schema=False)
def js_panel():
    return FileResponse(config.RUTA_FRONTEND.parent / "js" / "panel.js", media_type="text/javascript")


@app.get("/panel/js/administracion.js", include_in_schema=False)
def js_administracion():
    return FileResponse(config.RUTA_FRONTEND.parent / "js" / "administracion.js", media_type="text/javascript")


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

@app.get("/portada/logo-politecnico", include_in_schema=False)
def logo_politecnico():
    return FileResponse(
        config.RUTA_FRONTEND.parent / "assets" / "logo-politecnico.jpeg",
        media_type="image/jpeg"
    )

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)
