"""Simulacion academica UTI/general: flujos separados, sin fechas UTI inventadas.

Se supone UTI -> general -> egreso, sin reingreso a UTI ni bloqueo de traslados.
Los tiempos de cada sector siguen una distribucion geometrica (sin memoria).
Los parametros por sector deben ingresarse explicitamente; no se deducen del uso UTI registrado.
Son supuestos de escenario, no trayectorias observadas ni un modelo validado por sector.
"""
from datetime import date, timedelta
from functools import lru_cache
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from core import config
from services.analisis import cargar_datos
from services.prediccion import predecir_ingresos, serie_ingresos


class CensoSector(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ocupadas: int = Field(ge=0, strict=True)
    capacidad: int = Field(gt=0, strict=True)

    @model_validator(mode="after")
    def censo_dentro_de_capacidad(self):
        if self.ocupadas > self.capacidad:
            raise ValueError("El censo de camas ocupadas no puede superar las camas habilitadas del sector. Registre capacidad adicional si corresponde; la demanda futura sin cama se informa por separado.")
        return self


class EscenarioSectores(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    uti: CensoSector
    general: CensoSector
    proporcion_ingresos_uti: float = Field(ge=0, le=1)
    estancia_media_uti: float = Field(ge=1, le=365)
    estancia_media_general: float = Field(ge=1, le=365)
    fraccion_salidas_uti_a_general: float = Field(ge=0, le=1)
    origen_parametros: Literal["supuestos_usuario", "ejemplo_ficticio"] = "supuestos_usuario"


@lru_cache(maxsize=64)
def parametros_historicos(fecha_iso):
    """Auditoria descriptiva; nunca completa los parametros operativos UTI/general."""
    fecha = pd.Timestamp(fecha_iso)
    serie = serie_ingresos("hdhi")
    if not serie.index.min() <= fecha <= serie.index.max():
        raise ValueError("La fecha esta fuera del rango de HDHI.")
    if len(serie.loc[:fecha]) < 148:
        raise ValueError("Se necesitan al menos 148 dias de historia hasta el censo.")
    df = cargar_datos("hdhi")
    egreso = pd.to_datetime(df["fecha_egreso"], errors="coerce")
    anteriores = egreso < fecha
    uti = pd.to_numeric(df["duration_of_intensive_unit_stay"], errors="coerce")
    conocidos = anteriores & uti.notna() & np.isfinite(uti) & (uti >= 0)
    return {
        "fecha_corte": fecha.date().isoformat(),
        "ultimo_egreso_utilizado": egreso[anteriores].max().date().isoformat() if anteriores.any() else None,
        "episodios_anteriores": int(anteriores.sum()),
        "episodios_con_valor_uti": int(conocidos.sum()),
        "episodios_sin_valor_uti_utilizable": int((anteriores & ~conocidos).sum()),
        "parametros_inferidos": False,
        "unidad_uti_confirmada": False,
        "recorrido_uti_general_observado": False,
        "origen": "Auditoria de disponibilidad HDHI anterior al censo. No se infieren tasas de ingreso UTI, medias operativas ni traslados.",
    }


def _estado(ocupadas, capacidad):
    if not np.isfinite(ocupadas) or ocupadas < 0 or capacidad <= 0:
        raise ValueError("Ocupacion no finita, negativa o capacidad no positiva.")
    return {"camas_ocupadas": round(float(ocupadas), 4), "capacidad": capacidad,
            "camas_libres": round(max(capacidad - ocupadas, 0), 4),
            "demanda_sin_cama": round(max(ocupadas - capacidad, 0), 4),
            "tasa_ocupacion_pct": round(100 * ocupadas / capacidad, 2),
            "alerta_saturacion": bool(ocupadas / capacidad > config.UMBRAL_SATURACION)}


def proyectar_sectores(fecha, sectores, dias=7):
    fecha = date.fromisoformat(str(fecha or config.DATASETS["hdhi"]["fecha_demo"]))
    if not 1 <= dias <= 14:
        raise ValueError("La proyeccion admite entre 1 y 14 dias.")
    ref = parametros_historicos(fecha.isoformat())
    valores = sectores.model_dump()
    claves = ("proporcion_ingresos_uti", "estancia_media_uti", "estancia_media_general", "fraccion_salidas_uti_a_general")
    parametros = {k: valores[k] for k in claves}
    ingresos, _, metodo = predecir_ingresos("hdhi", pd.Timestamp(fecha), dias)
    uti, general = float(sectores.uti.ocupadas), float(sectores.general.ocupadas)
    censo = {"uti": _estado(uti, sectores.uti.capacidad), "general": _estado(general, sectores.general.capacidad)}
    resultados = []
    error_max_balance = 0.0
    for i, ingreso in enumerate(ingresos):
        ingreso = float(ingreso)
        if not np.isfinite(ingreso) or ingreso < 0:
            raise ValueError("El modelo de ingresos devolvio un valor no valido.")
        # Primero salen pacientes presentes al inicio del dia; despues entran los nuevos.
        salida_uti = uti / parametros["estancia_media_uti"]
        traslado = salida_uti * parametros["fraccion_salidas_uti_a_general"]
        alta_uti = salida_uti - traslado
        alta_general = general / parametros["estancia_media_general"]
        ingreso_uti = ingreso * parametros["proporcion_ingresos_uti"]
        ingreso_general = ingreso - ingreso_uti
        anterior = uti + general
        uti = uti - salida_uti + ingreso_uti
        general = general - alta_general + traslado + ingreso_general
        error_balance = abs(anterior + ingreso - alta_uti - alta_general - uti - general)
        if not np.isfinite(uti + general) or min(uti, general) < 0 or error_balance > 1e-7 * max(1, anterior + ingreso):
            raise ValueError("El balance de pacientes no es valido; se cancela la simulacion.")
        error_max_balance = max(error_max_balance, error_balance)
        resultados.append({
            "fecha": (fecha + timedelta(days=i+1)).isoformat(),
            "ingresos_hospital": round(ingreso, 4),
            "altas_hospital": round(alta_uti + alta_general, 4),
            "traslados_uti_a_general": round(traslado, 4),
            "uti": {**_estado(uti, sectores.uti.capacidad), "ingresos_externos": round(ingreso_uti, 4),
                    "salidas_sector": round(salida_uti, 4), "altas_hospital": round(alta_uti, 4)},
            "general": {**_estado(general, sectores.general.capacidad), "ingresos_externos": round(ingreso_general, 4),
                        "traslados_recibidos": round(traslado, 4), "altas_hospital": round(alta_general, 4)},
        })
    resumen = {}
    for sector in ("uti", "general"):
        pico = max(resultados, key=lambda d: d[sector]["camas_ocupadas"])
        resumen[sector] = {"alerta_censo": censo[sector]["alerta_saturacion"],
                           "alerta_proyeccion": any(d[sector]["alerta_saturacion"] for d in resultados),
                           "ocupacion_maxima_pct": pico[sector]["tasa_ocupacion_pct"], "dia_pico": pico["fecha"]}
    return {"modo": "simulacion_sectores", "dataset": "hdhi", "fecha_censo": fecha.isoformat(),
            "origen_censo": "ingresado por el usuario; no reconstruido por sector", "dias": dias,
            "metodo_ingresos": metodo, "metodo_sectores": "Flujos diarios con tiempos geometricos sin memoria",
            "parametros": parametros, "referencia_historica": ref,
            "origen_parametros": sectores.origen_parametros,
            "nivel_evidencia": "simulacion_sectorial_no_validada",
            "control_balance": {"estado": "verificado", "error_absoluto_maximo": error_max_balance},
            "alerta_saturacion": any(r["alerta_proyeccion"] for r in resumen.values()),
            "alerta_ocupacion_censo": any(r["alerta_censo"] for r in resumen.values()),
            "censo": censo, "resumen": resumen, "proyeccion": resultados,
            "advertencias": [
                "Simulacion academica por sector sin validacion temporal de ocupacion UTI/general.",
                "No existen fechas de entrada/salida UTI: no se reconstruye un censo UTI historico.",
                "El reparto de ingresos, estancias y traslados son parametros explicitos del escenario, no valores inferidos del dataset.",
                "Se supone recorrido UTI a general sin reingresos, espera, bloqueos ni traslados general a UTI.",
                "La duracion UTI registrada no se convierte automaticamente a noches ni se resta del total hospitalario.",
                "Tiempos sin memoria: las altas no dependen de la edad, diagnostico ni dias ya transcurridos.",
                "Los traslados liberan UTI y ocupan general; no son altas del hospital ni nuevos ingresos externos.",
                "Si la demanda supera la capacidad se muestra exceso teorico, no ubicacion fisica de pacientes.",
                "No se ofrece P90 ni probabilidad de saturacion por sector: no hay calibracion con movimientos reales.",
            ]}
