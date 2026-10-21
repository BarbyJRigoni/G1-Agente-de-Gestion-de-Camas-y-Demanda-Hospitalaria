"""
Endpoints del modelo de demanda y de la evaluacion del agente.

Responsable: Barbara (Inteligencia artificial e interfaz)

  GET /modelo/demanda            -> metodo elegido y metricas del backtesting
  GET /modelo/backtest           -> ingresos reales vs. pronosticados (para graficar)
  GET /modelo/evaluacion-agente  -> error del agente y precision / recall de las alertas
  GET /modelo/ocupacion-real     -> camas que realmente se ocuparon despues de una fecha
"""
from datetime import date
from typing import Literal, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from agents import inventario_agent as agente
from core import config
from services import prediccion

router = APIRouter(prefix="/modelo", tags=["Modelo de prediccion"])
NombreDataset = Literal["hdhi", "lengthofstay", "healthcare"]


@router.get("/demanda", summary="Modelo de demanda: metodo elegido y metricas")
def demanda(dataset: NombreDataset = Query(config.DATASET_POR_DEFECTO),
            fecha: Optional[date] = Query(None, description="Corte temporal; sin fecha, evaluacion del historial completo")):
    """Compara cinco metodos de prediccion de ingresos con 26 semanas de backtesting
    (MAE, RMSE, WAPE diario y semanal, R², sesgo y cobertura del intervalo del 80 %)
    y devuelve el elegido. Incluye los coeficientes de la regresion."""
    m = modelo_para_consulta(dataset, fecha)
    return {**m.resumen(), **alcance(m, fecha), "coeficientes_regresion": m.coeficientes()}


@router.get("/backtest", summary="Ingresos reales vs. pronosticados")
def backtest(dataset: NombreDataset = Query(config.DATASET_POR_DEFECTO),
             fecha: Optional[date] = Query(None, description="Corte temporal; sin fecha, historial completo")):
    m = modelo_para_consulta(dataset, fecha)
    return {"dataset": dataset, "metodo_elegido": m.metodo_elegido, **alcance(m, fecha), **m.evaluacion["serie"]}


@router.get("/evaluacion-agente", summary="Que tan bien proyecta el agente (contra la realidad)")
def evaluacion_agente(dataset: NombreDataset = Query(config.DATASET_POR_DEFECTO)):
    """Reconstruye el censo de fechas pasadas, proyecta 7 dias y compara con la ocupacion
    que realmente hubo. Devuelve el error por dia de horizonte y la precision / recall
    de distintas reglas de alerta."""
    return prediccion.evaluar_agente(dataset)


@router.get("/ocupacion-real", summary="Camas que realmente se ocuparon despues de una fecha")
def ocupacion_real(dataset: NombreDataset = Query(config.DATASET_POR_DEFECTO),
                   desde: Optional[date] = Query(None, description="Por defecto, la fecha de prueba"),
                   dias: int = Query(config.DIAS_PROYECCION, ge=1, le=14)):
    desde = pd.Timestamp(desde or config.DATASETS[dataset]["fecha_demo"])
    real = prediccion.ocupacion_real(agente.cargar_internaciones(dataset))
    tramo = real.loc[desde + pd.Timedelta(days=1): desde + pd.Timedelta(days=dias)]
    if tramo.empty:
        raise HTTPException(404, f"No hay datos reales despues de {desde.date()} en {dataset}")
    capacidad = config.DATASETS[dataset]["capacidad_total"]
    return {"dataset": dataset, "fechas": [d.date().isoformat() for d in tramo.index],
            "camas_ocupadas": tramo.astype(int).tolist(),
            "tasa_ocupacion_pct": (100 * tramo / capacidad).round(1).tolist()}


def modelo_para_consulta(dataset, fecha):
    if fecha is None:
        return prediccion.modelo_demanda(dataset)
    serie = prediccion.serie_ingresos(dataset)
    if not serie.index.min().date() <= fecha <= serie.index.max().date():
        raise HTTPException(400, 'Fecha de corte fuera del rango de ingresos del dataset.')
    try:
        return prediccion.modelo_demanda_hasta(dataset, fecha.isoformat())
    except ValueError as error:
        raise HTTPException(400, str(error))


def alcance(modelo, fecha):
    return {'alcance_evaluacion': 'hasta_el_censo' if fecha else 'historial_completo',
            'fecha_corte': modelo.y.index.max().date().isoformat(),
            'nota_seleccion': 'La proyeccion selecciona el metodo con historia hasta su censo; '
                              'la comparacion general puede incluir fechas posteriores a una demo.'}
