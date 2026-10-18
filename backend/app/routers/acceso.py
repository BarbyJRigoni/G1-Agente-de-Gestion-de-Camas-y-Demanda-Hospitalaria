from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from services import acceso

router = APIRouter(prefix="/auth", tags=["Acceso"])


class Credenciales(BaseModel):
    model_config = ConfigDict(extra="forbid")
    usuario: str = Field(min_length=1, max_length=40)
    clave: str = Field(min_length=1, max_length=128)


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
