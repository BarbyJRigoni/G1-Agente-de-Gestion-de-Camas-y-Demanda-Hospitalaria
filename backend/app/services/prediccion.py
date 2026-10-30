"""
services/prediccion.py — Modelo de predicción de demanda hospitalaria y su evaluación.

Responsable: Bárbara (Inteligencia artificial e interfaz)

Qué predice: cuántos pacientes INGRESAN por día en los próximos días. Es el dato
que el agente (agents/inventario_agent.py) necesita para saber cuántas camas se
van a ocupar.

Compiten cinco métodos y se elige el mejor con backtesting:
  - media_28d       promedio de los últimos 28 días (referencia mínima)
  - semana_anterior lo que entró el mismo día de la semana pasada
  - dia_semana_8sem promedio por día de la semana de las últimas 8 semanas
                    (el método con el que se armó la primera versión del agente)
  - estacional      promedio histórico de ese mes y ese día de la semana
  - regresion       regresión Ridge programada con numpy: parte del nivel reciente
                    y aprende cuánto se aparta cada día según el día de la semana
                    y la época del año (términos de Fourier)

Además evalúa al AGENTE completo: proyecta desde fechas pasadas y compara con la
ocupación que realmente hubo (error en camas y precisión / recall de las alertas).

Usa los datos limpios del equipo (services/analisis.py y el mapa de columnas de
core/config.py) sin modificarlos.
"""
from functools import lru_cache
from services.rendimiento import cache_calculo

import numpy as np
import pandas as pd

from core import config
from services.analisis import cargar_datos

# Parámetros del modelo (propios de este módulo)
BACKTEST_SEMANAS = 26        # semanas evaluadas en el backtesting
RIDGE_LAMBDA = 1.0           # regularización de la regresión
MEJORA_MINIMA_PCT = 3.0      # ventaja mínima sobre la media para elegir un método más complejo
Z_80 = 1.2816                # cuantil 90 de la normal: intervalo del 80 % y percentil 90

METODOS = ["media_28d", "semana_anterior", "dia_semana_8sem", "estacional", "regresion"]
NOMBRES = {"media_28d": "Media 28 días", "semana_anterior": "Semana anterior",
           "dia_semana_8sem": "Día de semana (8 semanas)", "estacional": "Estacional (mes × día)",
           "regresion": "Regresión Ridge"}


# ======================================================================
# Utilidades
# ======================================================================
def ridge(X: np.ndarray, y: np.ndarray, lam: float = RIDGE_LAMBDA) -> np.ndarray:
    """Regresión Ridge con solución cerrada: (X'X + λI)^-1 X'y. No penaliza el intercepto."""
    P = lam * np.eye(X.shape[1])
    P[0, 0] = 0
    return np.linalg.solve(X.T @ X + P, X.T @ y)


def metricas(y, yhat) -> dict:
    """MAE, RMSE, WAPE, R² y sesgo.
    WAPE = Σ|error| / Σ|real|. Se usa en lugar del MAPE porque el MAPE explota en días con 0 ingresos."""
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    e = y - yhat
    sst = ((y - y.mean()) ** 2).sum()
    return {"mae": round(float(np.abs(e).mean()), 3),
            "rmse": round(float(np.sqrt((e ** 2).mean())), 3),
            "wape_pct": round(float(100 * np.abs(e).sum() / max(np.abs(y).sum(), 1e-9)), 2),
            "r2": round(float(1 - (e ** 2).sum() / sst), 3) if sst > 0 else 0.0,
            "sesgo": round(float(-e.mean()), 3)}          # > 0: el modelo sobreestima


@lru_cache(maxsize=None)
def serie_ingresos(dataset: str) -> pd.Series:
    """Ingresos por día del dataset (días sin ingresos = 0). Mismo criterio que el agente:
    se descartan los registros sin fechas confirmadas (por ejemplo, las ambiguas de HDHI)."""
    col = config.DATASETS[dataset]
    df = cargar_datos(dataset)
    ingreso = pd.to_datetime(df[col["ingreso"]], errors="coerce")
    egreso = pd.to_datetime(df[col["egreso"]], errors="coerce")
    fechas = ingreso[ingreso.notna() & egreso.notna()].dt.normalize()
    s = fechas.value_counts().sort_index()
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D"), fill_value=0).astype(float)


# ======================================================================
# Modelo de demanda
# ======================================================================
class ModeloDemanda:
    def __init__(self, serie: pd.Series, nombre: str = ""):
        self.nombre = nombre
        self.y = serie.astype(float)
        self.origen = self.y.index.min()
        self.X = self._calendario(self.y.index)
        self.evaluacion = self._backtest()
        self.metodo_elegido = self._elegir()
        self.rmse = {m: self.evaluacion["metricas"][m]["rmse"] for m in METODOS}

    # ---------- variables ----------
    @staticmethod
    def _calendario(fechas: pd.DatetimeIndex) -> pd.DataFrame:
        """Día de la semana (lunes = referencia) y estacionalidad anual con términos de Fourier."""
        t = 2 * np.pi * fechas.dayofyear.to_numpy() / 365.25
        X = pd.DataFrame(index=fechas)
        for d in range(1, 7):
            X[f"dia_{d}"] = (fechas.dayofweek == d).astype(float)
        X["sin_anual"], X["cos_anual"] = np.sin(t), np.cos(t)
        X["sin_semestral"], X["cos_semestral"] = np.sin(2 * t), np.cos(2 * t)
        return X

    def _nivel(self, fechas: pd.DatetimeIndex) -> pd.Series:
        """Nivel reciente: media de 28 días que termina 7 días antes de cada fecha.
        Se conoce al momento de pronosticar a 1..7 días: no 'mira el futuro'."""
        y = self.y.reindex(fechas.union(self.y.index))
        return y.shift(7).rolling(28, min_periods=14).mean().reindex(fechas)

    def _ajustar_regresion(self, hasta: pd.Timestamp):
        """Objetivo = desvío respecto del nivel reciente. Así el modelo se adapta solo a
        cambios de nivel (crecimiento, brotes) y aprende el patrón semanal y anual."""
        nivel = self._nivel(self.y.loc[:hasta].index).dropna()
        X = self.X.loc[nivel.index]
        mu, sd = X.mean(), X.std().replace(0, 1)
        Z = np.column_stack([np.ones(len(X)), ((X - mu) / sd).to_numpy()])
        return ridge(Z, (self.y.loc[nivel.index] - nivel).to_numpy()), mu, sd

    # ---------- pronóstico ----------
    def _pronostico(self, metodo: str, hasta: pd.Timestamp, fechas: pd.DatetimeIndex, ajuste=None) -> np.ndarray:
        hist = self.y.loc[:hasta]
        if metodo == "media_28d":
            return np.full(len(fechas), hist.iloc[-28:].mean())
        if metodo == "semana_anterior":
            return np.array([hist.get(f - pd.Timedelta(days=7), hist.iloc[-7:].mean()) for f in fechas])
        if metodo == "dia_semana_8sem":
            ult = hist.iloc[-56:]
            por_dia = ult.groupby(ult.index.dayofweek).mean()
            return np.array([por_dia.get(f.dayofweek, ult.mean()) for f in fechas])
        if metodo == "estacional":
            mes_dia = hist.groupby([hist.index.month, hist.index.dayofweek]).mean()
            dia = hist.groupby(hist.index.dayofweek).mean()
            return np.array([mes_dia.get((f.month, f.dayofweek), dia[f.dayofweek]) for f in fechas])
        coef, mu, sd = ajuste or self._ajustar_regresion(hasta)
        X = self._calendario(fechas)
        Z = np.column_stack([np.ones(len(X)), ((X - mu) / sd).to_numpy()])
        nivel = (self.y.loc[:hasta].reindex(fechas.union(hist.index)).shift(7).rolling(28, min_periods=14).mean().reindex(fechas).fillna(hist.iloc[-28:].mean()).to_numpy())
        return np.clip(Z @ coef + nivel, 0, None)

    def predecir(self, desde, dias: int, metodo: str = "auto"):
        """Seleccion y calibracion conocidas al cierre de la fecha del censo."""
        fecha = pd.Timestamp(desde).normalize()
        if not 1 <= dias <= config.DIAS_PROYECCION_MAX:
            raise ValueError(f"La proyeccion admite entre 1 y {config.DIAS_PROYECCION_MAX} dias.")
        hasta = min(fecha, self.y.index.max())
        historia = self.y.loc[:hasta]
        if len(historia) < 148:
            raise ValueError("Se necesitan al menos 148 dias de historia hasta el censo.")
        if hasta < self.y.index.max():
            return ModeloDemanda(historia, self.nombre).predecir(fecha, dias, metodo)
        metodo = self.metodo_elegido if metodo == "auto" else metodo
        if metodo not in METODOS:
            raise ValueError(f"Metodo desconocido: {metodo}")
        fechas = pd.date_range(fecha + pd.Timedelta(days=1), periods=dias, freq="D")
        return self._pronostico(metodo, hasta, fechas), self.rmse[metodo], metodo

    # ---------- evaluación ----------
    def _backtest(self) -> dict:
        """Backtesting con origen móvil: cada 7 días se entrena SOLO con el pasado y se
        pronostican los 7 días siguientes, igual que en el uso real. Se repite 26 semanas."""
        ultimo = self.y.index.max()
        origenes = [ultimo - pd.Timedelta(days=7 * (i + 1)) for i in range(BACKTEST_SEMANAS)][::-1]
        origenes = [o for o in origenes if (o - self.origen).days >= 120]
        if not origenes:
            raise ValueError("No hay historia suficiente para backtesting.")
        reales, preds, fechas = [], {m: [] for m in METODOS}, []
        for o in origenes:
            f = pd.date_range(o + pd.Timedelta(days=1), periods=7, freq="D")
            reales.extend(self.y.loc[f])
            fechas.extend(f)
            ajuste = self._ajustar_regresion(o)
            for m in METODOS:
                preds[m].extend(self._pronostico(m, o, f, ajuste))
        reales = np.array(reales)
        res = {m: metricas(reales, preds[m]) for m in METODOS}
        semana_real = reales.reshape(-1, 7).sum(axis=1)
        for m in METODOS:
            p = np.array(preds[m])
            # error del TOTAL semanal: lo que importa para planificar camas
            semana_pred = p.reshape(-1, 7).sum(axis=1)
            res[m]["wape_semanal_pct"] = round(float(100 * np.abs(semana_real - semana_pred).sum() / semana_real.sum()), 2)
            # ¿el intervalo del 80 % contiene al valor real ~80 % de las veces?
            res[m]["cobertura_80pct"] = round(float(100 * np.mean(np.abs(reales - p) <= Z_80 * res[m]["rmse"])), 1)
        return {"semanas_evaluadas": len(origenes), "dias_evaluados": len(reales),
                "periodo": f"{fechas[0].date()} a {fechas[-1].date()}" if fechas else "",
                "metricas": res,
                "serie": {"fechas": [d.date().isoformat() for d in fechas], "real": reales.tolist(),
                          **{m: np.round(preds[m], 2).tolist() for m in METODOS}}}

    def _elegir(self) -> str:
        """El de menor WAPE diario, solo si le gana a la media por MEJORA_MINIMA_PCT o más.
        Si no, la media: no se justifica un modelo más complejo (parsimonia) y se evita
        'aprender' ruido, como pasa con el dataset Healthcare, que es aleatorio."""
        m = self.evaluacion["metricas"]
        mejor = min(METODOS, key=lambda k: m[k]["wape_pct"])
        base = m["media_28d"]["wape_pct"]
        return mejor if base > 0 and 100 * (base - m[mejor]["wape_pct"]) / base >= MEJORA_MINIMA_PCT else "media_28d"

    def coeficientes(self) -> dict:
        """Ingresos que suma o resta cada variable respecto del nivel reciente (estandarizadas)."""
        coef, *_ = self._ajustar_regresion(self.y.index.max())
        return dict(zip(["intercepto", *self.X.columns], np.round(coef, 3).tolist()))

    def resumen(self) -> dict:
        m = self.evaluacion["metricas"]
        base, mejor = m["media_28d"]["wape_pct"], m[self.metodo_elegido]["wape_pct"]
        return {"dataset": self.nombre, "ingresos_promedio_dia": round(float(self.y.mean()), 2),
                "dias_historia": len(self.y), "metodo_elegido": self.metodo_elegido,
                "nombre_metodo": NOMBRES[self.metodo_elegido],
                "mejora_vs_media_pct": round(100 * (base - mejor) / base, 1) if base else 0.0,
                "backtest": {k: v for k, v in self.evaluacion.items() if k != "serie"}}


@cache_calculo(maxsize=3)
def modelo_demanda(dataset: str) -> ModeloDemanda:
    """Entrena y evalúa el modelo de un dataset una sola vez (queda en memoria)."""
    return ModeloDemanda(serie_ingresos(dataset), dataset)


def predecir_ingresos(dataset: str, fecha, dias: int, metodo: str = "auto"):
    fecha = pd.Timestamp(fecha).normalize()
    modelo = modelo_demanda_hasta(dataset, fecha.date().isoformat())
    return modelo.predecir(fecha, dias, metodo)


# ======================================================================
# Evaluación del agente completo
# ======================================================================
def ocupacion_real(internaciones: pd.DataFrame) -> pd.Series:
    """Camas ocupadas cada noche (mismo criterio que agente.censo_en_fecha):
    ingreso <= noche < egreso. Se calcula con eventos +1 / -1 y suma acumulada."""
    idx = pd.date_range(internaciones["ingreso"].min(), internaciones["ingreso"].max(), freq="D")
    entra = internaciones["ingreso"].value_counts().reindex(idx, fill_value=0)
    sale = internaciones["egreso"].value_counts().reindex(idx, fill_value=0)
    return (entra - sale).cumsum()


@lru_cache(maxsize=None)
def evaluar_agente(dataset: str = 'hdhi', cada_dias: int = 7, dias: int = config.DIAS_PROYECCION) -> dict:
    """Proyecta desde fechas pasadas a `dias` dias y compara con lo que realmente paso."""
    from agents import inventario_agent as agente
    from services.modelo_ocupacion import INICIO_VALIDACION_HDHI
    internaciones = agente.cargar_internaciones(dataset)
    real = ocupacion_real(internaciones)
    capacidad = config.DATASETS[dataset]['capacidad_total']
    umbral = config.UMBRAL_SATURACION
    fechas = real.index[147:-(dias + 1):cada_dias]   # cada fecha necesita `dias` dias reales despues
    if not len(fechas):
        raise ValueError('No hay historia suficiente para evaluar el agente.')
    errores, anteriores, referencias, casos = [], [], [], []
    cubre, cubre_ant = [], []
    for f in fechas:
        r = agente.proyectar_camas(dataset, fecha=f.date(), dias=dias)
        pred = np.array([d['camas_ocupadas'] for d in r['proyeccion']])
        viejo = np.array([d.get('camas_ocupadas_agente_anterior', d['camas_ocupadas']) for d in r['proyeccion']])
        obs = real.reindex(pd.date_range(f + pd.Timedelta(days=1), periods=len(pred))).to_numpy()
        errores.append(pred - obs)
        anteriores.append(viejo - obs)
        referencias.append(r['camas_ocupadas_hoy'] - obs)
        casos.append((pred.max() / capacidad,
                      max(d['camas_ocupadas_p90'] for d in r['proyeccion']) / capacidad,
                      r['prob_max_superar_umbral_pct'] / 100,
                      bool((obs / capacidad > umbral).any())))
        if r.get('calibracion_incertidumbre', {}).get('metodo') == 'residuos_modelo_ocupacion':
            cubre.append(obs <= np.array([d['camas_ocupadas_p90'] for d in r['proyeccion']]))
            cubre_ant.append(obs <= np.array([d['camas_ocupadas_p90_agente_anterior'] for d in r['proyeccion']]))
    e, anterior, ref, c = np.array(errores), np.array(anteriores), np.array(referencias), np.array(casos)
    saturo = c[:, 3] > 0
    def regla(aviso):
        aciertos = int((aviso & saturo).sum())
        return {'alertas': int(aviso.sum()), 'aciertos': aciertos,
                'precision': round(aciertos / int(aviso.sum()), 2) if aviso.any() else None,
                'recall': round(aciertos / int(saturo.sum()), 2) if saturo.any() else None}
    resultado = {
        'dataset': dataset, 'dias_proyectados': dias, 'fechas_evaluadas': len(fechas), 'capacidad': capacidad,
        'semanas_que_realmente_superaron_el_umbral': int(saturo.sum()),
        'error_por_dia': {'mae_camas': np.abs(e).mean(axis=0).round(1).tolist(),
                         'mae_pct_capacidad': (100 * np.abs(e).mean(axis=0) / capacidad).round(1).tolist(),
                         'sesgo_camas': e.mean(axis=0).round(1).tolist()},
        'reglas_de_alerta': {'ocupacion_esperada_mayor_90': regla(c[:, 0] > umbral),
                            'p90_mayor_90': regla(c[:, 1] > umbral),
                            'probabilidad_mayor_30': regla(c[:, 2] >= .30)},
        'comparacion_referencia': {
            'nombre': 'Mantener la ocupacion del censo',
            'mae_camas_por_dia': np.abs(ref).mean(axis=0).round(2).tolist(),
            'mae_agente_anterior_por_dia': np.abs(anterior).mean(axis=0).round(2).tolist(),
            'mae_global_referencia': round(float(np.abs(ref).mean()), 3),
            'mae_global_agente_anterior': round(float(np.abs(anterior).mean()), 3),
            'mae_global_agente': round(float(np.abs(e).mean()), 3),
            'nota': 'Mismas fechas. El total incluye el periodo de desarrollo.'},
        'cobertura_limite_superior': {
            'objetivo_nominal_pct': 90, 'fechas_con_calibracion': len(cubre),
            'pronosticos_comparables': int(np.asarray(cubre).size),
            'empirico_pct': round(float(100 * np.mean(cubre)), 1) if cubre else None,
            'aproximacion_original_pct': round(float(100 * np.mean(cubre_ant)), 1) if cubre_ant else None,
            'nota': 'Calibracion anterior a cada censo. Cobertura futura no garantizada.'}}
    if dataset == 'hdhi':
        mascara = np.array([f >= pd.Timestamp(INICIO_VALIDACION_HDHI) for f in fechas])
        if mascara.any():
            resultado['validacion_posterior'] = {
                'primer_censo': fechas[mascara][0].date().isoformat(),
                'ultimo_censo': fechas[mascara][-1].date().isoformat(),
                'fechas': int(mascara.sum()),
                'mae_agente': round(float(np.abs(e[mascara]).mean()), 3),
                'mae_agente_anterior': round(float(np.abs(anterior[mascara]).mean()), 3),
                'mae_referencia': round(float(np.abs(ref[mascara]).mean()), 3),
                'nota': 'Parametros elegidos con el periodo anterior; cada ajuste usa solo el pasado.'}
    return resultado


# CORRECCION_TEMPORAL_HDHI_V1
@cache_calculo(maxsize=128)
def modelo_demanda_hasta(dataset: str, fecha_iso: str) -> ModeloDemanda:
    """Backtesting y modelo calculados solo con ingresos hasta el censo."""
    serie = serie_ingresos(dataset).loc[:pd.Timestamp(fecha_iso)]
    if len(serie) < 148:
        raise ValueError("Se necesitan al menos 148 dias de historia hasta el censo.")
    return ModeloDemanda(serie, dataset)
