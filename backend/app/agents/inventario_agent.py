"""
Agente de gestion de camas.

Proyecta la ocupacion de camas de los proximos dias a partir del censo
actual (pacientes internados) y de la historia del hospital:

  - ALTAS: de los pacientes que hoy estan internados, cuantos seguiran
    internados cada dia, segun lo que duraron las internaciones pasadas.
  - INGRESOS: cuantos pacientes nuevos llegaran cada dia, segun el modelo de
    demanda de services/prediccion.py (Barbara). El modelo compara cinco metodos
    con backtesting y usa el que menos se equivoca en cada dataset.
  - INCERTIDUMBRE: ademas del valor esperado calcula un escenario pesimista
    (percentil 90) y la probabilidad de superar el umbral. Con eso emite una
    alerta preventiva cuando la probabilidad es del 30 % o mas.

Luego evalua la proyeccion con services/alertas.py (Alerta de Saturacion).
Usa los datos limpios de Sabrina (services/analisis.py) sin modificarlos.
"""
from functools import lru_cache
from math import erf, sqrt

import numpy as np
import pandas as pd

from core import config
from services import alertas
from services.analisis import cargar_datos
from services.prediccion import Z_80, modelo_demanda_hasta, predecir_ingresos

PROB_ALERTA_PREVENTIVA = 0.30   # elegido evaluando precision / recall (ver docs/modelo_prediccion.md)



# ------------------------------------------------------------
# 1. Datos
# ------------------------------------------------------------

# Carga un dataset limpio y deja solo fecha de ingreso, egreso y noches de
# internacion, con los mismos nombres para los tres datasets (mapa de config.py).
# Se usan NOCHES (egreso - ingreso) porque cada dataset cuenta la duracion
# distinto: HDHI incluye el dia de alta y los otros dos no.
def cargar_internaciones(dataset):
    # Se lee el CSV una sola vez por dataset y se devuelve una copia en cada llamada
    return _cargar_internaciones(dataset).copy()


@lru_cache(maxsize=None)
def _cargar_internaciones(dataset):
    if dataset not in config.DATASETS:
        raise ValueError(f"Dataset desconocido: {dataset}. Opciones: {list(config.DATASETS)}")

    columnas = config.DATASETS[dataset]
    df = cargar_datos(dataset)

    internaciones = pd.DataFrame({
        "ingreso": pd.to_datetime(df[columnas["ingreso"]], errors="coerce"),
        "egreso": pd.to_datetime(df[columnas["egreso"]], errors="coerce"),
        "duracion": pd.to_numeric(df[columnas["duracion"]], errors="coerce"),
    })
    internaciones["noches"] = (internaciones["egreso"] - internaciones["ingreso"]).dt.days

    # Se descartan registros sin fechas confirmadas (por ejemplo, las
    # fechas "ambiguas" o "sin coincidencia" que marco la limpieza de HDHI).
    if internaciones.empty or internaciones.isna().any().any():
        raise ValueError(f"{dataset}: faltan internaciones con fechas y duraciones validas.")
    if not np.isfinite(internaciones['duracion']).all() or (internaciones['noches'] < 0).any():
        raise ValueError(f"{dataset}: hay duraciones o fechas invalidas.")
    esperada = internaciones['noches'] + (1 if dataset == 'hdhi' else 0)
    if not np.allclose(internaciones['duracion'], esperada):
        raise ValueError(f"{dataset}: la duracion no coincide con ingreso y egreso.")
    return internaciones.reset_index(drop=True)


# Censo de una fecha: pacientes que ocupan cama esa noche (ingresaron ese dia
# o antes y todavia no se fueron) y cuantas noches llevan, contando esa noche.
def censo_en_fecha(internaciones, fecha):
    fecha = pd.Timestamp(fecha)
    internados = internaciones[
        (internaciones["ingreso"] <= fecha) & (internaciones["egreso"] > fecha)
    ]
    return ((fecha - internados["ingreso"]).dt.days + 1).tolist()


# ------------------------------------------------------------
# 2. Historia: cuanto duran las internaciones y cuantos ingresan
# ------------------------------------------------------------

# Probabilidad de que una internacion dure MAS de t noches, para t = 0, 1, 2...
# Ejemplo: prob_seguir[3] = 0.60 -> el 60 % de las internaciones dura mas de 3 noches.
def calcular_prob_seguir(duraciones, dias_max):
    duraciones = np.asarray(duraciones, dtype=float)
    if len(duraciones) == 0 or not np.isfinite(duraciones).all() or (duraciones < 0).any():
        raise ValueError("No hay duraciones historicas validas para estimar altas.")
    return np.array([(duraciones > t).mean() for t in range(dias_max + 1)])


# Ingresos esperados por dia de la semana (0 = lunes ... 6 = domingo),
# promediando las ultimas semanas anteriores a la fecha del censo.


# ------------------------------------------------------------
# 3. Proyeccion
# ------------------------------------------------------------

def _proyectar_camas_base(dataset, fecha=None, dias_internados=None,
                    capacidad=None, dias=config.DIAS_PROYECCION):
    """
    dataset          : "hdhi", "lengthofstay" o "healthcare".
    fecha            : fecha del censo ("hoy"). Por defecto, la fecha_demo del dataset.
    dias_internados  : censo actual -> lista con las noches que lleva internado cada
                       paciente (1 = ingreso hoy). Si no se envia, se reconstruye.
    capacidad        : camas del hospital. Por defecto, la de config.py.
    dias             : cantidad de dias a proyectar (7 segun la consigna).
    """
    datos = config.DATASETS.get(dataset, {})
    fecha = pd.Timestamp(fecha or datos.get("fecha_demo"))
    capacidad = datos.get("capacidad_total") if capacidad is None else capacidad
    if not isinstance(dias, (int, np.integer)) or not 1 <= dias <= 14:
        raise ValueError("La proyeccion admite entre 1 y 14 dias.")
    if capacidad is None or not np.isfinite(capacidad) or capacidad <= 0:
        raise ValueError("La capacidad debe ser mayor a cero.")

    internaciones = cargar_internaciones(dataset)
    if not internaciones["ingreso"].min() <= fecha <= internaciones["ingreso"].max():
        raise ValueError(
            f"La fecha {fecha.date()} esta fuera del rango del dataset "
            f"({internaciones['ingreso'].min().date()} a {internaciones['ingreso'].max().date()})."
        )

    # Censo: si no lo envian, se reconstruye con los internados en esa fecha
    origen_censo = "recibido" if dias_internados is not None else "reconstruido del historial"
    if dias_internados is None:
        dias_internados = censo_en_fecha(internaciones, fecha)

    # Historia anterior a la fecha del censo (no se usan datos del "futuro")
    pasado = internaciones[internaciones["egreso"] < fecha]
    if any(not isinstance(d, (int, np.integer)) or d < 1 for d in dias_internados):
        raise ValueError("Cada estancia del censo debe ser una cantidad entera de noches mayor a cero.")
    max_historia = int(pasado['noches'].max()) if not pasado.empty else 0
    sin_soporte = sum(d > max_historia for d in dias_internados)
    if origen_censo == 'recibido' and sin_soporte:
        raise ValueError("El censo manual incluye estancias mayores al soporte historico; no se pueden estimar sus altas.")
    dias_max = max_historia + dias + 1
    prob_seguir = calcular_prob_seguir(pasado["noches"], dias_max)
    # Ingresos esperados de cada dia: modelo de demanda (services/prediccion.py)
    ingresos_modelo, rmse_ingresos, metodo_ingresos = predecir_ingresos(dataset, fecha, dias)
    # Sobredispersion: cuanto mas varian los ingresos reales que una Poisson pura
    phi = max(1.0, rmse_ingresos ** 2 / max(modelo_demanda_hasta(dataset, fecha.date().isoformat()).y.mean(), 1.0))
    umbral_camas = config.UMBRAL_SATURACION * capacidad

    proyeccion = []
    ocupadas_ayer = len(dias_internados)
    ingresos_por_dia = []

    for j in range(1, dias + 1):
        dia = fecha + pd.Timedelta(days=j)

        # a) Pacientes actuales que siguen internados el dia j.
        #    Un paciente que lleva d noches sigue si su internacion dura mas de d+j-1
        #    noches, sabiendo que ya dura mas de d-1: prob_seguir[d+j-1] / prob_seguir[d-1].
        p_siguen = np.array([
            prob_seguir[d + j - 1] / prob_seguir[d - 1]
            if d <= max_historia and prob_seguir[d - 1] > 0 else 1.0
            for d in dias_internados
        ])
        siguen_actuales = p_siguen.sum()

        # b) Ingresos nuevos esperados ese dia (modelo de demanda)
        ingresos_hoy = float(ingresos_modelo[j - 1])
        ingresos_por_dia.append(ingresos_hoy)

        # c) Pacientes nuevos (ingresados del dia 1 al j) que siguen internados el dia j
        siguen_nuevos = sum(
            ingresos_por_dia[k - 1] * prob_seguir[j - k]
            for k in range(1, j + 1)
        )

        ocupadas = siguen_actuales + siguen_nuevos
        altas = ocupadas_ayer + ingresos_hoy - ocupadas

        # d) Incertidumbre: cada internado sigue o no (Bernoulli) y los ingresos varian
        #    como una Poisson sobredispersa. Con la aproximacion normal se obtienen el
        #    percentil 90 y la probabilidad de superar el umbral.
        desvio = sqrt(float((p_siguen * (1 - p_siguen)).sum()) + phi * siguen_nuevos)
        if desvio > 0:
            prob = 1 - 0.5 * (1 + erf((umbral_camas - ocupadas) / (desvio * sqrt(2))))
        else:
            prob = float(ocupadas > umbral_camas)

        proyeccion.append({
            "fecha": dia.date().isoformat(),
            "ingresos_previstos": round(ingresos_hoy, 1),
            "altas_previstas": round(altas, 1),
            "camas_ocupadas": round(ocupadas, 1),
            "camas_ocupadas_p90": round(ocupadas + Z_80 * desvio, 1),
            "prob_superar_umbral_pct": round(100 * prob, 1),
        })
        ocupadas_ayer = ocupadas

    # Evaluacion con la logica de alertas (paso 2)
    evaluacion = alertas.evaluar_proyeccion(proyeccion, capacidad)
    for dia, evaluado in zip(proyeccion, evaluacion["dias"]):
        dia.update({
            "camas_libres": evaluado["camas_libres"],
            "tasa_ocupacion_pct": evaluado["tasa_ocupacion_pct"],
            "alerta_saturacion": evaluado["alerta_saturacion"],
        })

    prob_max = max(d["prob_superar_umbral_pct"] for d in proyeccion)
    alerta_preventiva = not evaluacion["alerta_saturacion"] and prob_max >= 100 * PROB_ALERTA_PREVENTIVA
    mensaje = evaluacion["mensaje"]
    if alerta_preventiva:
        mensaje += (f" ALERTA PREVENTIVA: hay {prob_max:.0f} % de probabilidad de superar el "
                    f"{config.UMBRAL_SATURACION:.0%} en al menos un dia proyectado. "
                    "Es la mayor probabilidad diaria, no la conjunta semanal.")

    return {
        "dataset": dataset,
        "advertencias": ([f"{sin_soporte} pacientes del censo reconstruido superan el soporte de estancias; "
                           "en el modelo por estancias se conservan sin estimar altas."] if sin_soporte else []),
        "metodo_ingresos": metodo_ingresos,
        "prob_max_superar_umbral_pct": prob_max,
        "alerta_preventiva": alerta_preventiva,
        "fecha_censo": fecha.date().isoformat(),
        "origen_censo": origen_censo,
        "capacidad": capacidad,
        "camas_ocupadas_hoy": len(dias_internados),
        "tasa_ocupacion_hoy_pct": alertas.calcular_tasa_ocupacion(len(dias_internados), capacidad),
        "alos_historico": round(float(pasado["duracion"].mean()), 2),
        "alerta_saturacion": evaluacion["alerta_saturacion"],
        "mensaje": mensaje,
        "tasa_ocupacion_maxima_pct": evaluacion["tasa_ocupacion_maxima_pct"],
        "dia_pico": evaluacion["dia_pico"],
        "proyeccion": proyeccion,
    }


def proyectar_camas(dataset, fecha=None, dias_internados=None, capacidad=None,
                    dias=config.DIAS_PROYECCION):
    from services.modelo_ocupacion import aplicar_modelo
    resultado = _proyectar_camas_base(dataset, fecha, dias_internados, capacidad, dias)
    resultado = aplicar_modelo(resultado, dias_internados)
    resultado['fecha_corte_modelo'] = resultado['fecha_censo']
    resultado['alerta_ocupacion_censo'] = resultado['camas_ocupadas_hoy'] / resultado['capacidad'] > config.UMBRAL_SATURACION
    return resultado



# Prueba rapida: los tres casos de la demo con fechas reales de HDHI.
if __name__ == "__main__":
    casos = {
        "Normal": "2019-01-01",
        "Limite": "2019-03-05",
        "Critico": "2018-01-09",
    }

    for nombre, fecha in casos.items():
        r = proyectar_camas("hdhi", fecha=fecha)
        print(f"\n=== Caso {nombre} | censo {r['fecha_censo']} | "
              f"{r['camas_ocupadas_hoy']} de {r['capacidad']} camas ocupadas "
              f"({r['tasa_ocupacion_hoy_pct']} %) ===")
        print(pd.DataFrame(r["proyeccion"]).to_string(index=False))
        print(r["mensaje"])
# MODELO_OCUPACION_HDHI_V2
