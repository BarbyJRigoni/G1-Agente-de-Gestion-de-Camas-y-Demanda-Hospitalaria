"""Pronostico directo de ocupacion HDHI con Ridge por horizonte.

Variables: censo y sus siete retardos, medias 7/14/28 dias, cambio semanal,
dia de semana de destino y calendario anual. Cada ajuste usa objetivos
completamente observados al cierre del censo. No conoce los egresos futuros.
Ventana 365 y lambda 100 elegidas en desarrollo anterior al 29/09/2018.
Validacion posterior: origenes desde 29/09/2018. Los resultados anteriores
son de desarrollo. Las altas se infieren del balance, no son predicciones
individuales de alta. Censos manuales y otros datasets conservan el agente
por estancias hasta disponer de validacion especifica.
"""
from functools import lru_cache
from services.rendimiento import cache_calculo
from math import ceil, erf, sqrt
import numpy as np
import pandas as pd

VENTANA_DIAS = 365
RIDGE_LAMBDA = 100.
INICIO_VALIDACION_HDHI = '2018-09-29'


@lru_cache(maxsize=None)
def serie_ocupacion(dataset):
    from agents.inventario_agent import cargar_internaciones
    from services.prediccion import ocupacion_real
    return ocupacion_real(cargar_internaciones(dataset)).astype(float)


def variables(y, horizonte):
    X = pd.DataFrame(index=y.index)
    for k in range(8):
        X[f'lag{k}'] = y.shift(k)
    for w in (7, 14, 28):
        X[f'mean{w}'] = y.rolling(w).mean()
    X['trend7'] = y - y.shift(7)
    destino = y.index + pd.Timedelta(days=horizonte)
    for d in range(1, 7):
        X[f'dow{d}'] = (destino.dayofweek == d).astype(float)
    fase = 2 * np.pi * destino.dayofyear / 365.25
    X['sin'], X['cos'] = np.sin(fase), np.cos(fase)
    return X


@cache_calculo(maxsize=30)
def _variables_guardadas(dataset, horizonte):
    # Solo retardos/medias hacia atras y calendario, sin egresos ni objetivos futuros.
    return variables(serie_ocupacion(dataset), horizonte)


@cache_calculo(maxsize=512)
def predecir_ocupacion(dataset, fecha_iso, dias):
    fecha = pd.Timestamp(fecha_iso)
    y = serie_ocupacion(dataset).loc[:fecha]
    if len(y) < 148 or y.index.max() != fecha:
        raise ValueError('Se requieren al menos 148 dias de ocupacion hasta el censo.')
    predicciones = []
    for h in range(1, dias + 1):
        X = _variables_guardadas(dataset, h).loc[y.index]
        objetivo = y.shift(-h) - y
        # Excluir cualquier objetivo cuya fecha de observacion sea posterior al censo.
        mascara = ((X.index + pd.Timedelta(days=h) <= fecha)
                   & (X.index >= fecha - pd.Timedelta(days=VENTANA_DIAS))
                   & X.notna().all(axis=1) & objetivo.notna())
        xx = X.loc[mascara].to_numpy()
        tt = objetivo.loc[mascara].to_numpy()
        if len(tt) < 80:
            raise ValueError('No hay historia suficiente para el modelo de ocupacion.')
        mu, sd = xx.mean(axis=0), xx.std(axis=0)
        sd[sd == 0] = 1
        z = (xx - mu) / sd
        centro = tt.mean()
        coef = np.linalg.solve(z.T @ z + RIDGE_LAMBDA * np.eye(z.shape[1]), z.T @ (tt - centro))
        delta = centro + ((X.loc[fecha].to_numpy() - mu) / sd) @ coef
        predicciones.append(max(0., float(y.iloc[-1] + delta)))
    return tuple(predicciones)


def limitar_por_balance(predicciones, resultado):
    # No puede haber mas ocupadas que las previas mas los ingresos previstos.
    # No se limita a la capacidad: una demanda superior debe activar la alerta.
    anterior = float(resultado['camas_ocupadas_hoy'])
    salida = []
    for valor, dia in zip(predicciones, resultado['proyeccion']):
        valor = max(0., min(float(valor), anterior + dia['ingresos_previstos']))
        salida.append(valor)
        anterior = valor
    return tuple(salida)


@cache_calculo(maxsize=512)
def _historico(dataset, fecha_iso, dias):
    from agents.inventario_agent import _proyectar_camas_base
    base = _proyectar_camas_base(dataset, fecha=fecha_iso, dias=dias)
    return tuple(round(v, 1) for v in limitar_por_balance(predecir_ocupacion(dataset, fecha_iso, dias), base))


@cache_calculo(maxsize=256)
def residuos_anteriores(dataset, fecha_iso, dias):
    fecha = pd.Timestamp(fecha_iso)
    real = serie_ocupacion(dataset)
    inicio = real.index.min() + pd.Timedelta(days=147)
    ultimo = fecha - pd.Timedelta(days=dias)
    origenes = [ultimo - pd.Timedelta(weeks=i) for i in range(26)][::-1]
    origenes = [o for o in origenes if o >= inicio]
    if len(origenes) < 12:
        return (), ()
    filas = []
    for origen in origenes:
        fechas = pd.date_range(origen + pd.Timedelta(days=1), periods=dias)
        if fechas.max() > fecha:
            raise AssertionError('La calibracion utilizo resultados futuros.')
        obs = real.reindex(fechas)
        if obs.isna().any():
            raise ValueError('Faltan ocupaciones historicas para calibrar.')
        filas.append(tuple(obs.to_numpy() - np.asarray(_historico(dataset, origen.date().isoformat(), dias))))
    return tuple(filas), tuple(o.date().isoformat() for o in origenes)


def aplicar_modelo(resultado, dias_internados=None):
    from core import config
    from services import alertas
    if resultado['dataset'] != 'hdhi' or dias_internados is not None:
        resultado['metodo_ocupacion'] = 'Estancias historicas (censo manual u otro dataset)'
        resultado['calibracion_incertidumbre'] = {'metodo': 'aproximacion_original', 'origenes': 0}
        return resultado
    dias = len(resultado['proyeccion'])
    fecha = resultado['fecha_censo']
    valores = limitar_por_balance(predecir_ocupacion('hdhi', fecha, dias), resultado)
    filas, origenes = residuos_anteriores('hdhi', fecha, dias)
    errores = np.asarray(filas, dtype=float) if filas else None
    n = len(filas)
    if n:
        rango = min(n, ceil((n + 1) * .90)) - 1
        margen = np.maximum(0., np.sort(errores, axis=0)[rango])
    umbral = config.UMBRAL_SATURACION * resultado['capacidad']
    anterior = float(resultado['camas_ocupadas_hoy'])
    for h, (valor, dia) in enumerate(zip(valores, resultado['proyeccion'])):
        antiguo = dia['camas_ocupadas']
        dia['camas_ocupadas_agente_anterior'] = antiguo
        dia['camas_ocupadas_p90_agente_anterior'] = dia['camas_ocupadas_p90']
        valor = round(float(valor), 1)
        dia['camas_ocupadas'] = valor
        dia['altas_previstas'] = round(max(0., anterior + dia['ingresos_previstos'] - valor), 1)
        if n:
            dia['camas_ocupadas_p90'] = round(float(valor + margen[h]), 1)
            excedencias = int((errores[:, h] > umbral - valor).sum())
            dia['prob_superar_umbral_pct'] = round(100 * (excedencias + 1) / (n + 1), 1)
        else:
            amplitud = max(0., dia['camas_ocupadas_p90'] - antiguo)
            dia['camas_ocupadas_p90'] = round(valor + amplitud, 1)
            desvio = amplitud / 1.2816
            prob = .5 * (1 - erf((umbral - valor) / (desvio * sqrt(2)))) if desvio else float(valor > umbral)
            dia['prob_superar_umbral_pct'] = round(100 * prob, 1)
        anterior = valor
    evaluacion = alertas.evaluar_proyeccion(resultado['proyeccion'], resultado['capacidad'])
    for dia, evaluado in zip(resultado['proyeccion'], evaluacion['dias']):
        for campo in ('camas_libres', 'tasa_ocupacion_pct', 'alerta_saturacion'):
            dia[campo] = evaluado[campo]
    prob_max = max(d['prob_superar_umbral_pct'] for d in resultado['proyeccion'])
    preventiva = not evaluacion['alerta_saturacion'] and prob_max >= 30
    mensaje = evaluacion['mensaje']
    if preventiva:
        mensaje += f' ALERTA PREVENTIVA: estimacion diaria maxima de excedencia {prob_max:.1f} %; no es la conjunta semanal.'
    resultado.update(metodo_ocupacion='Ridge de ocupacion por horizonte',
                     prob_max_superar_umbral_pct=prob_max, alerta_preventiva=preventiva,
                     alerta_saturacion=evaluacion['alerta_saturacion'], mensaje=mensaje,
                     tasa_ocupacion_maxima_pct=evaluacion['tasa_ocupacion_maxima_pct'], dia_pico=evaluacion['dia_pico'])
    resultado['calibracion_incertidumbre'] = {
        'metodo': 'residuos_modelo_ocupacion' if n else 'aproximacion_provisional',
        'origenes': n, 'ultimo_resultado_utilizado': fecha if n else None,
        'nota': 'Limite superior empirico nominal 90 %; no garantiza cobertura futura. '
                'Excedencia suavizada: (casos + 1) / (muestra + 1). Altas inferidas por balance.'}
    return resultado

# CALIBRACION_Y_CALENDARIO_V2
