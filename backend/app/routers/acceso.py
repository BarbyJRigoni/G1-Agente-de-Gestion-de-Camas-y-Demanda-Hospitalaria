from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from services import acceso, registro_publico

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
    model_config = ConfigDict(extra='forbid')
    usuario: str = Field(min_length=3, max_length=14)
    correo: str = Field(min_length=5, max_length=60)
    clave: str = Field(min_length=5, max_length=14)

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
    # El registro admite visitantes de internet; todos reciben rol de usuario.
    # Se conserva la verificación de origen, además del control en main.py.
    origen = request.headers.get('origin')
    if origen:
        from urllib.parse import urlsplit
        try:
            fuente = urlsplit(origen)
            servidor = urlsplit(str(request.base_url))
        except ValueError:
            raise HTTPException(status_code=403, detail='Origen no permitido.') from None
        if (fuente.scheme.lower(), fuente.netloc.lower()) != (servidor.scheme.lower(), servidor.netloc.lower()):
            raise HTTPException(status_code=403, detail='Origen no permitido.')
    elif request.headers.get('x-requested-with') != 'AgenteCamas':
        raise HTTPException(status_code=403, detail='Solicitud de origen no permitido.')
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(status_code=403, detail='Origen no permitido.')
    try:
        usuario = registro_publico.registrar(
            usuario=datos.usuario, clave=datos.clave, correo=datos.correo,
            ip=request.client.host if request.client else 'sin-direccion',
        )
    except registro_publico.DemasiadosRegistros as error:
        raise HTTPException(status_code=429, detail=str(error), headers={'Retry-After': str(error.reintentar_en)}) from None
    except acceso.ErrorIntegridad:
        raise HTTPException(status_code=409, detail='El nombre de usuario o el correo ya están registrados.') from None
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None
    return {'mensaje': 'Usuario registrado correctamente. Ya podés iniciar sesión.', 'usuario': usuario}
    

# Las operaciones administrativas tienen su propio módulo.
from routers.administracion_usuarios import router as router_administracion
router.include_router(router_administracion)
