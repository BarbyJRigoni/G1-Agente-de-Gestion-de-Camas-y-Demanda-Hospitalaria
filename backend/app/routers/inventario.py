"""Endpoints de la API."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.agents.inventario_agent import AgenteCamas
from app.core import config
from app.schemas.camas import CensoHospital, EstanciaResponse, PacienteNuevo, ProyeccionResponse

router = APIRouter()
Escenario = Literal["normal", "limite", "critico"]
Fuente = Literal["HDHI", "LOS", "HC"]


def get_agente(request: Request) -> AgenteCamas:
    agente = getattr(request.app.state, "agente", None)
    if agente is None:
        raise HTTPException(503, "El agente no está inicializado: faltan datasets (ver /salud)")
    return agente


# ------------------------------- Agente -------------------------------
@router.post("/proyeccion-camas", response_model=ProyeccionResponse, tags=["Agente"],
             summary="Proyección semanal de camas a partir del censo actual")
def proyeccion_camas(censo: CensoHospital, agente: AgenteCamas = Depends(get_agente)):
    """
    Recibe el **censo actual** (pacientes en UTI y en Internación General + capacidad) y devuelve,
    por unidad y por día: ingresos y egresos esperados, camas ocupadas y libres, ocupación esperada
    y pesimista (P90), probabilidad de superar el umbral, nivel de riesgo y **Alerta de Saturación**.
    Incluye los KPIs (Tasa de Ocupación Proyectada y ALOS) y recomendaciones.

    Tip: `GET /censo-ejemplo/{escenario}` devuelve un censo real listo para pegar acá.
    """
    return agente.proyectar(censo)


@router.get("/censo-ejemplo/{escenario}", response_model=CensoHospital, tags=["Agente"],
            summary="Censo real reconstruido del dataset HDHI (normal, limite o critico)")
def censo_ejemplo(escenario: Escenario, agente: AgenteCamas = Depends(get_agente)):
    return agente.censo_ejemplo(escenario)


@router.get("/proyeccion-camas/escenario/{escenario}", response_model=ProyeccionResponse, tags=["Agente"],
            summary="Atajo para la demo: arma el censo del escenario y lo proyecta")
def proyeccion_escenario(escenario: Escenario, agente: AgenteCamas = Depends(get_agente)):
    return agente.proyectar(CensoHospital(**agente.censo_ejemplo(escenario)))


@router.get("/escenario/{escenario}/realidad", tags=["Agente"],
            summary="Ocupación que realmente hubo después del censo del escenario (para validar)")
def realidad(escenario: Escenario, agente: AgenteCamas = Depends(get_agente)):
    cen = agente.censo_ejemplo(escenario)
    return {"fecha_censo": cen["fecha_referencia"], **agente.ocupacion_real(cen["fecha_referencia"])}


@router.post("/estimar-estancia", response_model=EstanciaResponse, tags=["Agente"],
             summary="Noches de internación esperadas de un paciente nuevo (modelo de regresión)")
def estimar_estancia(paciente: PacienteNuevo, agente: AgenteCamas = Depends(get_agente)):
    """Los valores de laboratorio son opcionales: si faltan se usa la mediana del dataset."""
    return agente.estimar_estancia(paciente)


# ------------------------------- Modelos -------------------------------
@router.get("/modelo/evaluacion", tags=["Modelos"], summary="Métricas de todos los modelos")
def evaluacion(agente: AgenteCamas = Depends(get_agente)):
    return agente.evaluacion_modelos()


@router.get("/modelo/backtest/{fuente}", tags=["Modelos"],
            summary="Ingresos reales vs. pronosticados en el backtesting")
def backtest(fuente: Fuente, agente: AgenteCamas = Depends(get_agente)):
    m = agente.demanda[fuente]
    return {"fuente": fuente, "metodo_elegido": m.metodo_elegido, **m.evaluacion["serie"]}


# ------------------------------- Datos -------------------------------
@router.get("/datos/calidad", tags=["Datos"], summary="Reporte de limpieza e integración")
def calidad(agente: AgenteCamas = Depends(get_agente)):
    return agente.reporte


@router.get("/estadisticas/alos", tags=["Datos"], summary="ALOS por patología y grupo etario")
def alos(fuente: Fuente = "HDHI",
         agrupar_por: Literal["patologia_grupo", "patologia", "grupo_etario"] = "patologia_grupo",
         min_casos: int = Query(1, ge=1, description="Ocultar estratos con menos casos"),
         agente: AgenteCamas = Depends(get_agente)):
    if fuente == "LOS" and agrupar_por != "patologia":
        raise HTTPException(422, "El dataset LOS no tiene edad: usar agrupar_por=patologia")
    por = {"patologia_grupo": ("patologia", "grupo_etario"), "patologia": ("patologia",),
           "grupo_etario": ("grupo_etario",)}[agrupar_por]
    t = agente.alos(fuente, por)
    t = t[t["casos"] >= min_casos]
    d = agente.por_fuente[fuente]
    return {"fuente": fuente, "alos_global": round(float(d["los_dias"].mean()), 2), "filas": len(t),
            "datos": t.sort_values("alos", ascending=False).to_dict(orient="records")}


@router.get("/estadisticas/ocupacion-historica", tags=["Datos"], summary="Ocupación mensual (HDHI)")
def ocupacion_historica(agente: AgenteCamas = Depends(get_agente)):
    return agente.ocupacion_mensual()
