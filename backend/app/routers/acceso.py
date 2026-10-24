from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from services import acceso

router = APIRouter(prefix="/auth", tags=["Acceso"])

def requerir_administrador(request: Request):
    usuario = request.state.usuario

    if not usuario:
        raise HTTPException(
            status_code=401,
            detail="Debes iniciar sesion."
        )

    if not acceso.es_administrador(usuario):
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos de administrador."
        )

    return usuario

class Credenciales(BaseModel):
    model_config = ConfigDict(extra="forbid")
    usuario: str = Field(min_length=1, max_length=40)
    clave: str = Field(min_length=1, max_length=128)

class Registro(BaseModel):
    model_config = ConfigDict(extra="forbid")
    usuario: str = Field(min_length=3, max_length=40)
    correo: str = Field(min_length=5, max_length=254)
    clave: str = Field(min_length=12, max_length=128)

@router.get("/sesion")
def sesion(request: Request):
    return {"autenticado": bool(request.state.usuario), "usuario": request.state.usuario,
            "acceso_configurado": acceso.hay_usuarios()}


@router.post("/ingresar")
def ingresar(datos: Credenciales, request: Request, response: Response):
    try:
        resultado = acceso.autenticar(datos.usuario, datos.clave, request.client.host if request.client else "local",
                                     request.cookies.get(acceso.COOKIE))
    except acceso.DemasiadosIntentos as error:
        raise HTTPException(status_code=429, detail=str(error), headers={"Retry-After": "300"})
    if resultado is None:
        raise HTTPException(status_code=401, detail="Usuario o contrasena incorrectos.")
    token, usuario = resultado
    response.set_cookie(acceso.COOKIE, token, max_age=acceso.DURACION_SESION, httponly=True,
                        secure=request.url.scheme == "https", samesite="strict", path="/")
    return {"autenticado": True, "usuario": usuario}


@router.post("/salir")
def salir(request: Request, response: Response):
    acceso.cerrar_sesion(request.cookies.get(acceso.COOKIE))
    response.delete_cookie(acceso.COOKIE, path="/", httponly=True, samesite="strict", secure=request.url.scheme == "https")
    return {"autenticado": False}

@router.post("/registrar", status_code=201)
def registrar(datos: Registro, request: Request):
    # Solo permite el registro desde el servidor local.
    cliente = request.client.host if request.client else ""
    if cliente not in ("127.0.0.1", "::1"):
        raise HTTPException(
            status_code=403,
            detail="El registro solo esta disponible localmente."
        )

    # Evita que un sitio externo solicite registros desde el navegador.
    origen = request.headers.get("origin")
    if origen:
        from urllib.parse import urlsplit

        origen_url = urlsplit(origen)
        servidor_url = urlsplit(str(request.base_url))

        if (
            origen_url.scheme != servidor_url.scheme
            or origen_url.netloc != servidor_url.netloc
        ):
            raise HTTPException(
                status_code=403,
                detail="Origen no permitido."
            )

    try:
        acceso.crear_usuario(
            usuario=datos.usuario,
            clave=datos.clave,
            reemplazar=False,
            correo=datos.correo
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    return {
        "mensaje": "Usuario registrado correctamente. Ya podes iniciar sesion.",
        "usuario": acceso.normalizar_usuario(datos.usuario)
    }
    

# Las operaciones administrativas tienen su propio módulo.
from routers.administracion_usuarios import router as router_administracion
router.include_router(router_administracion)
