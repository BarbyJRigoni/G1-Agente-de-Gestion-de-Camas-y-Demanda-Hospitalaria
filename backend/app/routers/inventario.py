"""
Endpoints de la API del agente de gestion de camas.

  GET  /datasets           -> datasets disponibles y su capacidad
  GET  /estadisticas       -> indicadores historicos (ALOS, ingresos por dia)
  GET  /censo              -> camas ocupadas en una fecha y su tasa de ocupacion
  POST /proyeccion-camas   -> proyeccion de 7 dias + Alerta de Saturacion (consigna)

Los modelos Pydantic validan los datos que entran y documentan los que salen
(se ven en /docs).
"""
from datetime import date
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from agents import inventario_agent as agente
from core import config
from services import alertas

router = APIRouter()

# Solo se aceptan los datasets definidos en config.py
NombreDataset = Literal["hdhi", "lengthofstay", "healthcare"]


# ============================================================
# Modelos Pydantic
# ============================================================

class CensoActual(BaseModel):
    """Datos que recibe /proyeccion-camas."""
    dataset: NombreDataset = Field(config.DATASET_POR_DEFECTO, description="Dataset historico a usar")
    fecha: Optional[date] = Field(None, description="Fecha del censo. Si se omite, se usa la fecha de prueba del dataset")
    capacidad: Optional[int] = Field(None, gt=0, description="Camas del hospital. Si se omite, se usa la de config.py")
    dias_internados: Optional[list[Annotated[int, Field(ge=1)]]] = Field(
        None,
        description="Censo actual: noches que lleva internado cada paciente (1 = ingreso hoy). "
                    "Si se omite, se reconstruye desde el historial",
    )
    dias: int = Field(config.DIAS_PROYECCION, ge=1, le=14, description="Dias a proyectar")


class DiaProyectado(BaseModel):
    fecha: date
    ingresos_previstos: float
    altas_previstas: float
    camas_ocupadas: float
    camas_ocupadas_p90: Optional[float] = Field(None, description="Escenario pesimista (percentil 90)")
    prob_superar_umbral_pct: Optional[float] = None
    camas_libres: int
    tasa_ocupacion_pct: float
    alerta_saturacion: bool


class ProyeccionRespuesta(BaseModel):
    dataset: str
    metodo_ingresos: Optional[str] = Field(None, description="Metodo del modelo de demanda usado")
    prob_max_superar_umbral_pct: Optional[float] = None
    alerta_preventiva: Optional[bool] = Field(None, description="Sin saturacion esperada, pero prob. >= 30 %")
    fecha_censo: date
    origen_censo: str
    capacidad: int
    camas_ocupadas_hoy: int
    tasa_ocupacion_hoy_pct: float
    alos_historico: float
    alerta_saturacion: bool
    mensaje: str
    tasa_ocupacion_maxima_pct: float
    dia_pico: date
    proyeccion: list[DiaProyectado]


class DatasetInfo(BaseModel):
    clave: str
    nombre: str
    capacidad_total: int
    fecha_demo: date


class Estadisticas(BaseModel):
    dataset: str
    internaciones: int
    desde: date
    hasta: date
    alos_dias: float
    mediana_dias: float
    percentil_90_dias: float
    ingresos_promedio_dia: float


class Censo(BaseModel):
    dataset: str
    fecha: date
    camas_ocupadas: int
    capacidad: int
    camas_libres: int
    tasa_ocupacion_pct: float
    alerta_saturacion: bool


# Ejemplos que aparecen en /docs para la demo (fechas reales de HDHI)
EJEMPLOS_CENSO = {
    "normal": {"summary": "Caso normal (HDHI, 65 % de ocupacion)",
               "value": {"dataset": "hdhi", "fecha": "2019-01-01"}},
    "limite": {"summary": "Caso limite (HDHI, ~89 %)",
               "value": {"dataset": "hdhi", "fecha": "2019-03-05"}},
    "critico": {"summary": "Caso critico (HDHI, 100 % -> alerta)",
                "value": {"dataset": "hdhi", "fecha": "2018-01-09"}},
    "menos_camas": {"summary": "Mismo dia que el normal, pero con 50 camas menos (140)",
                    "value": {"dataset": "hdhi", "fecha": "2019-01-01", "capacidad": 140}},
}


# ============================================================
# Endpoints
# ============================================================

@router.get("/datasets", response_model=list[DatasetInfo], tags=["Datos"],
            summary="Datasets disponibles")
def listar_datasets():
    """Devuelve los tres datasets, su capacidad de camas y la fecha de prueba."""
    return [
        {"clave": clave, "nombre": d["nombre"],
         "capacidad_total": d["capacidad_total"], "fecha_demo": d["fecha_demo"]}
        for clave, d in config.DATASETS.items()
    ]


@router.get("/estadisticas", response_model=Estadisticas, tags=["Datos"],
            summary="Indicadores historicos de internacion")
def estadisticas(dataset: NombreDataset = Query(config.DATASET_POR_DEFECTO)):
    """ALOS (tiempo medio de estancia), mediana, percentil 90 e ingresos promedio por dia."""
    datos = agente.cargar_internaciones(dataset)
    ingresos_por_dia = datos["ingreso"].value_counts()
    dias_totales = (datos["ingreso"].max() - datos["ingreso"].min()).days + 1

    return {
        "dataset": dataset,
        "internaciones": len(datos),
        "desde": datos["ingreso"].min().date(),
        "hasta": datos["ingreso"].max().date(),
        "alos_dias": round(float(datos["duracion"].mean()), 2),
        "mediana_dias": float(datos["duracion"].median()),
        "percentil_90_dias": float(datos["duracion"].quantile(0.90)),
        "ingresos_promedio_dia": round(ingresos_por_dia.sum() / dias_totales, 1),
    }


@router.get("/censo", response_model=Censo, tags=["Datos"],
            summary="Camas ocupadas en una fecha")
def censo(dataset: NombreDataset = Query(config.DATASET_POR_DEFECTO),
          fecha: Optional[date] = Query(None, description="Si se omite, se usa la fecha de prueba")):
    """Reconstruye el censo de una fecha historica y calcula su tasa de ocupacion."""
    fecha = fecha or date.fromisoformat(config.DATASETS[dataset]["fecha_demo"])
    datos = agente.cargar_internaciones(dataset)

    if not datos["ingreso"].min().date() <= fecha <= datos["ingreso"].max().date():
        raise HTTPException(
            status_code=404,
            detail=f"Sin datos para {fecha}. Rango: {datos['ingreso'].min().date()} "
                   f"a {datos['ingreso'].max().date()}.",
        )

    ocupadas = len(agente.censo_en_fecha(datos, fecha))
    evaluado = alertas.evaluar_dia(fecha, ocupadas, config.DATASETS[dataset]["capacidad_total"])
    return {"dataset": dataset, **evaluado}


@router.post("/proyeccion-camas", response_model=ProyeccionRespuesta, tags=["Agente"],
             summary="Proyeccion semanal de camas y Alerta de Saturacion")
def proyeccion_camas(censo_actual: CensoActual = Body(openapi_examples=EJEMPLOS_CENSO)):
    """
    Recibe el **censo actual** del hospital y devuelve, para cada uno de los proximos dias:
    ingresos y altas previstas, camas ocupadas y libres, **Tasa de Ocupacion Proyectada (%)**
    y si corresponde la **Alerta de Saturacion** (ocupacion > 90 %).
    """
    try:
        return agente.proyectar_camas(
            dataset=censo_actual.dataset,
            fecha=censo_actual.fecha,
            dias_internados=censo_actual.dias_internados,
            capacidad=censo_actual.capacidad,
            dias=censo_actual.dias,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

from services.analisis_hdhi import obtener_indicadores_hdhi

@router.get(
    "/estadisticas/hdhi",
    tags=["Datos"],
    summary="ALOS de HDHI por patologia y edad",
)
def estadisticas_hdhi():
    return obtener_indicadores_hdhi()

