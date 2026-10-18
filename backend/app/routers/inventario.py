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
from pydantic import BaseModel, ConfigDict, Field, model_validator

from agents import inventario_agent as agente
from core import config
from services import alertas
from services.sectores import EscenarioSectores, proyectar_sectores, parametros_historicos

router = APIRouter()

# Solo se aceptan los datasets definidos en config.py
NombreDataset = Literal["hdhi", "lengthofstay", "healthcare"]


# ============================================================
# Modelos Pydantic
# ============================================================

class CensoActual(BaseModel):
    """Datos que recibe /proyeccion-camas."""
    model_config = ConfigDict(extra="forbid")
    dataset: NombreDataset = Field(config.DATASET_POR_DEFECTO, description="Dataset historico a usar")
    fecha: Optional[date] = Field(None, description="Fecha del censo. Si se omite, se usa la fecha de prueba del dataset")
    capacidad: Optional[int] = Field(None, gt=0, description="Camas del hospital. Si se omite, se usa la de config.py")
    dias_internados: Optional[list[Annotated[int, Field(ge=1)]]] = Field(
        None,
        description="Censo actual: noches que lleva internado cada paciente (1 = ingreso hoy). "
                    "Si se omite, se reconstruye desde el historial",
    )
    sectores: Optional[EscenarioSectores] = Field(None, description="Simulacion UTI/general HDHI: censo y capacidad de cada sector. No reconstruye censos historicos UTI.")

    @model_validator(mode="after")
    def validar_sectores(self):
        if self.sectores is not None:
            if self.dataset != "hdhi":
                raise ValueError("La simulacion por sectores usa solo HDHI, que registra duracion UTI.")
            if self.capacidad is not None or self.dias_internados is not None:
                raise ValueError("Con sectores, envie censo y capacidad dentro de cada sector, sin capacidad ni dias_internados agregados.")
        return self

    dias: int = Field(config.DIAS_PROYECCION, ge=1, le=14, description="Dias a proyectar")


class DiaProyectado(BaseModel):
    fecha: date
    ingresos_previstos: float
    altas_previstas: float
    camas_ocupadas: float
    camas_ocupadas_p90: Optional[float] = Field(None, description="Limite superior nominal 90 %; cobertura futura no garantizada")
    prob_superar_umbral_pct: Optional[float] = None
    camas_libres: int
    tasa_ocupacion_pct: float
    alerta_saturacion: bool


class ProyeccionRespuesta(BaseModel):
    dataset: str
    metodo_ingresos: Optional[str] = Field(None, description="Metodo del modelo de demanda usado")
    metodo_ocupacion: Optional[str] = None
    fecha_corte_modelo: Optional[date] = None
    alerta_ocupacion_censo: bool = False
    calibracion_incertidumbre: Optional[dict] = None
    advertencias: list[str] = Field(default_factory=list)
    prob_max_superar_umbral_pct: Optional[float] = None
    alerta_preventiva: Optional[bool] = Field(None, description="Sin saturacion esperada, pero estimacion de excedencia >= 30 %")
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


class EstadoSectorRespuesta(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    camas_ocupadas: float = Field(ge=0)
    capacidad: int = Field(gt=0)
    camas_libres: float = Field(ge=0)
    demanda_sin_cama: float = Field(ge=0)
    tasa_ocupacion_pct: float = Field(ge=0)
    alerta_saturacion: bool


class CensoSectoresRespuesta(BaseModel):
    uti: EstadoSectorRespuesta
    general: EstadoSectorRespuesta


class FlujoUTIRespuesta(EstadoSectorRespuesta):
    ingresos_externos: float = Field(ge=0)
    salidas_sector: float = Field(ge=0)
    altas_hospital: float = Field(ge=0)


class FlujoGeneralRespuesta(EstadoSectorRespuesta):
    ingresos_externos: float = Field(ge=0)
    traslados_recibidos: float = Field(ge=0)
    altas_hospital: float = Field(ge=0)


class DiaSectoresRespuesta(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    fecha: date
    ingresos_hospital: float = Field(ge=0)
    altas_hospital: float = Field(ge=0)
    traslados_uti_a_general: float = Field(ge=0)
    uti: FlujoUTIRespuesta
    general: FlujoGeneralRespuesta


class ProyeccionSectoresRespuesta(BaseModel):
    modo: Literal["simulacion_sectores"]
    dataset: Literal["hdhi"]
    fecha_censo: date
    origen_censo: str
    dias: int
    metodo_ingresos: str
    metodo_sectores: str
    parametros: dict
    referencia_historica: dict
    origen_parametros: Literal["supuestos_usuario", "ejemplo_ficticio"]
    nivel_evidencia: Literal["simulacion_sectorial_no_validada"]
    control_balance: dict
    alerta_saturacion: bool
    alerta_ocupacion_censo: bool
    censo: CensoSectoresRespuesta
    resumen: dict
    proyeccion: list[DiaSectoresRespuesta]
    advertencias: list[str]


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
    "uti_y_general": {"summary": "Simulacion UTI/general: censo, capacidades y parametros ficticios explicitos",
                      "value": {"dataset": "hdhi", "fecha": "2019-03-01", "dias": 7,
                                "sectores": {"uti": {"ocupadas": 7, "capacidad": 20},
                                             "general": {"ocupadas": 90, "capacidad": 170},
                                             "proporcion_ingresos_uti": 0.2, "estancia_media_uti": 2,
                                             "estancia_media_general": 5, "fraccion_salidas_uti_a_general": 0.8,
                                             "origen_parametros": "ejemplo_ficticio"}}},
    "capacidad_base": {"summary": "HDHI: censo historico con capacidad supuesta de 190",
                       "value": {"dataset": "hdhi", "fecha": "2019-01-01", "capacidad": 190}},
    "capacidad_reducida": {"summary": "HDHI: misma fecha, escenario de capacidad reducida (120)",
                           "value": {"dataset": "hdhi", "fecha": "2019-01-01", "capacidad": 120}},
    "lengthofstay": {"summary": "Length of Stay: escenario base",
                     "value": {"dataset": "lengthofstay", "fecha": "2012-12-01"}},
    "healthcare": {"summary": "Healthcare sintetico: escenario base",
                   "value": {"dataset": "healthcare", "fecha": "2024-04-01"}},
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


@router.post("/proyeccion-camas", response_model=ProyeccionRespuesta | ProyeccionSectoresRespuesta, tags=["Agente"],
             summary="Proyeccion semanal de camas y Alerta de Saturacion")
def proyeccion_camas(censo_actual: CensoActual = Body(openapi_examples=EJEMPLOS_CENSO)):
    """
    Recibe el **censo actual** del hospital y devuelve, para cada uno de los proximos dias:
    ingresos y altas previstas, camas ocupadas y libres, **Tasa de Ocupacion Proyectada (%)**
    y si corresponde la **Alerta de Saturacion** (ocupacion > 90 %).
    """
    try:
        if censo_actual.sectores is not None:
            return proyectar_sectores(censo_actual.fecha, censo_actual.sectores, censo_actual.dias)
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



@router.get('/escenarios', tags=['Agente'], summary='Escenarios simulados de capacidad para la demostracion')
def escenarios(dataset: NombreDataset = Query(config.DATASET_POR_DEFECTO)):
    """Conserva las fechas y los ingresos; varia explicitamente la capacidad supuesta.
    Los nombres describen el maximo proyectado, no eventos historicos de saturacion.
    """
    import math
    r = agente.proyectar_camas(dataset)
    pico = max(d['camas_ocupadas'] for d in r['proyeccion'])
    superior = max(d.get('camas_ocupadas_p90', d['camas_ocupadas']) for d in r['proyeccion'])
    if pico <= 0:
        return {'dataset': dataset, 'fecha': r['fecha_censo'], 'casos': [],
                'descripcion': 'Sin demanda proyectada positiva para construir estos escenarios.'}
    capacidades = {'normal': max(math.ceil(pico / .8), math.ceil(superior / .9) + 1),
                   'limite': max(1, math.ceil(pico / .9)),
                   'critico': max(1, math.floor(pico / .95))}
    return {'dataset': dataset, 'fecha': r['fecha_censo'],
            'capacidad_base': config.DATASETS[dataset]['capacidad_total'],
            'descripcion': 'Escenarios simulados: cambia la capacidad supuesta; se conservan fecha y demanda.',
            'casos': [{'tipo': tipo, 'fecha': r['fecha_censo'], 'capacidad': capacidad,
                       'maximo_proyectado_pct': round(100 * pico / capacidad, 1)}
                      for tipo, capacidad in capacidades.items()]}


@router.get("/sectores/parametros", tags=["Datos"], summary="Auditoria historica anterior al censo; no infiere parametros UTI/general")
def referencias_sectores(fecha: Optional[date] = Query(None)):
    try:
        return parametros_historicos(str(fecha or config.DATASETS["hdhi"]["fecha_demo"]))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
