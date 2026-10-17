"""
services/prediccion.py — Modelo de predicción de demanda hospitalaria y su evaluación.

Responsable: Bárbara (Inteligencia artificial e interfaz)

Qué predice: cuántos pacientes INGRESAN por día en los próximos días. Es el dato
que el agente (agents/inventario_agent.py) necesita para saber cuántas camas se
van a ocupar.

Compiten cinco métodos y se elige el mejor con backtesting. La elección se hace
SOLO con datos anteriores a la fecha del censo: para un censo del 1/1/2019 se
comparan los métodos en las 26 semanas previas a esa fecha, nunca con meses
posteriores (que en esa simulación todavía no pasaron).
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

import numpy as np
import pandas as pd

from core import config
from services.analisis import cargar_datos

# Parámetros del modelo (propios de este módulo)
BACKTEST_SEMANAS = 26        # semanas evaluadas para elegir el método
MIN_SEMANAS_ELECCION = 8     # con menos historia que esto se usa la media (no hay con qué comparar)
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
        # Pronósticos de prueba de TODA la historia, semana por semana. Después, para cada
        # fecha de censo se miran solo las semanas que ya habían terminado en esa fecha.
        self._semanas = self._pronosticos_semanales()
        self.evaluacion = self._evaluar(self.y.index.max() + pd.Timedelta(days=1))
        self.metodo_elegido = self.evaluacion["metodo_elegido"]   # con toda la historia (informe final)

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
            return np.array([self.y.get(f - pd.Timedelta(days=7), hist.iloc[-7:].mean()) for f in fechas])
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
        nivel = self._nivel(fechas).fillna(hist.iloc[-28:].mean()).to_numpy()
        return np.clip(Z @ coef + nivel, 0, None)

    def predecir(self, desde, dias: int, metodo: str = "auto"):
        """Ingresos esperados para desde+1 .. desde+dias, error típico (RMSE) y método usado.
        Todo sale de datos hasta `desde`: el pronóstico, la elección del método y el RMSE."""
        ev = self._evaluar(pd.Timestamp(desde))
        metodo = ev["metodo_elegido"] if metodo == "auto" else metodo
        rmse = ev["metricas"][metodo]["rmse"] if ev["metricas"] else float(np.sqrt(max(self.y.mean(), 1)))
        hasta = min(pd.Timestamp(desde), self.y.index.max())
        fechas = pd.date_range(pd.Timestamp(desde) + pd.Timedelta(days=1), periods=dias, freq="D")
        return self._pronostico(metodo, hasta, fechas), rmse, metodo

    # ---------- evaluación ----------
    def _pronosticos_semanales(self) -> list[dict]:
        """Backtesting con origen móvil sobre toda la serie: cada 7 días se entrena SOLO
        con el pasado y se pronostican los 7 días siguientes, igual que en el uso real."""
        semanas = []
        o = self.origen + pd.Timedelta(days=120)          # primero, 4 meses de historia mínima
        while o + pd.Timedelta(days=7) <= self.y.index.max():
            f = pd.date_range(o + pd.Timedelta(days=1), periods=7, freq="D")
            ajuste = self._ajustar_regresion(o)
            semanas.append({"origen": o, "fechas": f, "real": self.y.loc[f].to_numpy(),
                            "pred": {m: self._pronostico(m, o, f, ajuste) for m in METODOS}})
            o += pd.Timedelta(days=7)
        return semanas

    @lru_cache(maxsize=512)
    def _evaluar(self, fecha: pd.Timestamp) -> dict:
        """Compara los métodos en las últimas 26 semanas que YA habían terminado en `fecha`
        y elige uno. Es lo que vería alguien parado ese día en el hospital."""
        previas = [s for s in self._semanas if s["fechas"][-1] < fecha][-BACKTEST_SEMANAS:]
        if len(previas) < MIN_SEMANAS_ELECCION:
            return {"semanas_evaluadas": len(previas), "periodo": "", "metricas": {},
                    "metodo_elegido": "media_28d", "serie": {}}
        reales = np.concatenate([s["real"] for s in previas])
        preds = {m: np.concatenate([s["pred"][m] for s in previas]) for m in METODOS}
        res = {m: metricas(reales, preds[m]) for m in METODOS}
        semana_real = reales.reshape(-1, 7).sum(axis=1)
        for m in METODOS:
            # error del TOTAL semanal: lo que importa para planificar camas
            semana_pred = preds[m].reshape(-1, 7).sum(axis=1)
            res[m]["wape_semanal_pct"] = round(float(100 * np.abs(semana_real - semana_pred).sum() / semana_real.sum()), 2)
            # ¿el intervalo del 80 % contiene al valor real ~80 % de las veces?
            res[m]["cobertura_80pct"] = round(float(100 * np.mean(np.abs(reales - preds[m]) <= Z_80 * res[m]["rmse"])), 1)
        fechas = [d for s in previas for d in s["fechas"]]
        return {"semanas_evaluadas": len(previas), "dias_evaluados": len(reales),
                "periodo": f"{fechas[0].date()} a {fechas[-1].date()}",
                "metricas": res, "metodo_elegido": self._elegir(res),
                "serie": {"fechas": [d.date().isoformat() for d in fechas], "real": reales.tolist(),
                          **{m: np.round(preds[m], 2).tolist() for m in METODOS}}}

    @staticmethod
    def _elegir(m: dict) -> str:
        """El de menor WAPE diario, solo si le gana a la media por MEJORA_MINIMA_PCT o más.
        Si no, la media: no se justifica un modelo más complejo (parsimonia) y se evita
        'aprender' ruido, como pasa con el dataset Healthcare, que es aleatorio."""
        mejor = min(METODOS, key=lambda k: m[k]["wape_pct"])
        base = m["media_28d"]["wape_pct"]
        return mejor if 100 * (base - m[mejor]["wape_pct"]) / base >= MEJORA_MINIMA_PCT else "media_28d"

    def coeficientes(self) -> dict:
        """Ingresos que suma o resta cada variable respecto del nivel reciente (estandarizadas)."""
        coef, *_ = self._ajustar_regresion(self.y.index.max())
        return dict(zip(["intercepto", *self.X.columns], np.round(coef, 3).tolist()))

    def resumen(self, fecha=None) -> dict:
        """Evaluación con las 26 semanas anteriores a `fecha` (por defecto, el final del dataset)."""
        fecha = pd.Timestamp(fecha) if fecha else self.y.index.max() + pd.Timedelta(days=1)
        ev = self._evaluar(fecha)
        m, elegido = ev["metricas"], ev["metodo_elegido"]
        mejora = round(100 * (m["media_28d"]["wape_pct"] - m[elegido]["wape_pct"]) / m["media_28d"]["wape_pct"], 1) if m else 0.0
        return {"dataset": self.nombre, "evaluado_hasta": (fecha - pd.Timedelta(days=1)).date().isoformat(),
                "ingresos_promedio_dia": round(float(self.y.mean()), 2),
                "dias_historia": len(self.y), "metodo_elegido": elegido, "nombre_metodo": NOMBRES[elegido],
                "mejora_vs_media_pct": mejora,
                "backtest": {k: v for k, v in ev.items() if k not in ("serie", "metodo_elegido")}}


@lru_cache(maxsize=None)
def modelo_demanda(dataset: str) -> ModeloDemanda:
    """Entrena y evalúa el modelo de un dataset una sola vez (queda en memoria)."""
    return ModeloDemanda(serie_ingresos(dataset), dataset)


def predecir_ingresos(dataset: str, fecha, dias: int, metodo: str = "auto"):
    """Lo que usa el agente: (ingresos esperados por día, RMSE, método usado)."""
    return modelo_demanda(dataset).predecir(fecha, dias, metodo)


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
def evaluar_agente(dataset: str = "hdhi", cada_dias: int = 7) -> dict:
    """Proyecta desde muchas fechas pasadas y compara con lo que realmente pasó."""
    from agents import inventario_agent as agente          # import acá para evitar import circular

    internaciones = agente.cargar_internaciones(dataset)
    real = ocupacion_real(internaciones)
    capacidad = config.DATASETS[dataset]["capacidad_total"]
    umbral = config.UMBRAL_SATURACION
    fechas = real.index[90:-8:cada_dias]           # se saltea el arranque (hospital "vacío")
    errores, casos = [], []
    for f in fechas:
        r = agente.proyectar_camas(dataset, fecha=f.date())
        pred = np.array([d["camas_ocupadas"] for d in r["proyeccion"]])
        obs = real.loc[f + pd.Timedelta(days=1): f + pd.Timedelta(days=len(pred))].to_numpy()
        errores.append(pred - obs)
        casos.append((pred.max() / capacidad,
                      max(d["camas_ocupadas_p90"] for d in r["proyeccion"]) / capacidad,
                      r["prob_max_superar_umbral_pct"] / 100,
                      bool((obs / capacidad > umbral).any())))
    e, c = np.array(errores), np.array(casos)
    saturo = c[:, 3] > 0

    def regla(alerta):
        aciertos = int((alerta & saturo).sum())
        return {"alertas": int(alerta.sum()), "aciertos": aciertos,
                "precision": round(aciertos / max(int(alerta.sum()), 1), 2),
                "recall": round(aciertos / max(int(saturo.sum()), 1), 2)}

    return {
        "dataset": dataset, "fechas_evaluadas": len(fechas), "capacidad": capacidad,
        "semanas_que_realmente_superaron_el_umbral": int(saturo.sum()),
        "error_por_dia": {"mae_camas": np.abs(e).mean(axis=0).round(1).tolist(),
                          "mae_pct_capacidad": (100 * np.abs(e).mean(axis=0) / capacidad).round(1).tolist(),
                          "sesgo_camas": e.mean(axis=0).round(1).tolist()},
        "reglas_de_alerta": {
            "ocupacion_esperada_mayor_90": regla(c[:, 0] > umbral),
            "p90_mayor_90": regla(c[:, 1] > umbral),
            "probabilidad_mayor_30": regla(c[:, 2] >= 0.30),
        },
    }
