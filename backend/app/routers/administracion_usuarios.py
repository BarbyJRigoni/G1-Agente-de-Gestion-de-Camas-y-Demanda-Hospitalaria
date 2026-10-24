"""Endpoints exclusivos para administrar cuentas y consultar su auditoría."""
from typing import Literal
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from services import acceso
from services import administracion_usuarios as gestion

router = APIRouter(prefix='/admin', tags=['Administración de usuarios'])


class EdicionUsuario(BaseModel):
    model_config = ConfigDict(extra='forbid')
    nombre_completo: str = Field(min_length=2, max_length=120)
    correo: str = Field(min_length=5, max_length=254)
    rol: Literal['usuario', 'administrador']


class NuevoUsuario(EdicionUsuario):
    usuario: str = Field(min_length=3, max_length=40)
    clave: str = Field(min_length=12, max_length=128, repr=False)


class EstadoUsuario(BaseModel):
    model_config = ConfigDict(extra='forbid')
    activo: StrictBool


def _actor(request):
    actor = request.state.usuario
    if not actor:
        raise HTTPException(401, 'Iniciá sesión.')
    if not acceso.es_administrador(actor):
        raise HTTPException(403, 'No tenés permisos de administrador.')
    return actor


def _ejecutar(funcion, *args):
    try:
        return funcion(*args)
    except PermissionError as error:
        raise HTTPException(403, str(error)) from None
    except LookupError as error:
        raise HTTPException(404, str(error)) from None
    except gestion.ConflictoCuenta as error:
        raise HTTPException(409, str(error)) from None
    except ValueError as error:
        raise HTTPException(400, str(error)) from None


@router.get('/usuarios')
def listar_usuarios(request: Request):
    return _ejecutar(gestion.listar, _actor(request))


@router.post('/usuarios', status_code=201)
def crear_usuario(datos: NuevoUsuario, request: Request):
    return _ejecutar(gestion.crear, _actor(request), datos.usuario,
                     datos.nombre_completo, datos.correo, datos.rol, datos.clave)


@router.patch('/usuarios/{usuario}')
def editar_usuario(usuario: str, datos: EdicionUsuario, request: Request):
    return _ejecutar(gestion.editar, _actor(request), usuario,
                     datos.nombre_completo, datos.correo, datos.rol)


@router.patch('/usuarios/{usuario}/estado')
def estado_usuario(usuario: str, datos: EstadoUsuario, request: Request):
    return _ejecutar(gestion.cambiar_estado, _actor(request), usuario, datos.activo)


@router.get('/auditoria')
def auditoria(request: Request, limite: int = Query(100, ge=1, le=500)):
    return _ejecutar(gestion.auditoria, _actor(request), limite)
