"""
services/prediccion.py — Modelos de predicción de demanda hospitalaria.

Responsable: Bárbara (Inteligencia artificial e interfaz)

Contiene dos modelos:

1) ModeloDemanda: cuántos pacientes INGRESAN por día en los próximos 7 días.
   Compara cuatro métodos y se queda con el que menos se equivoca en backtesting:
     - media_28d       promedio de los últimos 28 días (baseline)
     - naive_semanal   lo mismo que entró el mismo día de la semana pasada
     - estacional      promedio histórico por (mes, día de semana)
     - regresion       regresión Ridge (numpy): parte del nivel reciente (media de 28
                       días) y aprende cuánto se aparta cada día según el día de la
                       semana y la época del año (términos de Fourier)

2) ModeloEstancia: cuántas noches va a estar internado un paciente (y cuántas en UTI),
   a partir de edad, sexo, tipo de ingreso, antecedentes, diagnósticos y laboratorio.
   Regresión Ridge validada 80/20 contra el ALOS de su patología.

Contrato con la capa de datos (data/loader.py): recibe la tabla integrada con al menos
`fecha_ingreso` (y, para el ModeloEstancia, la tabla limpia de HDHI). No depende de
cómo se hizo la integración.
"""
from datetime import date

import numpy as np
import pandas as pd

from app.core import config

# ======================================================================
# Utilidades
# ======================================================================


def ridge(X: np.ndarray, y: np.ndarray, lam: float = config.RIDGE_LAMBDA) -> np.ndarray:
    """Regresión Ridge con solución cerrada: (X'X + λI)^-1 X'y. No penaliza el intercepto (col 0)."""
    P = lam * np.eye(X.shape[1])
    P[0, 0] = 0
    return np.linalg.solve(X.T @ X + P, X.T @ y)


def metricas(y: np.ndarray, yhat: np.ndarray) -> dict:
    """MAE, RMSE, WAPE, R² y sesgo.
    WAPE = Σ|error| / Σ|real|: error porcentual que no explota con días de 0 ingresos (MAPE sí)."""
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    e = y - yhat
    sst = ((y - y.mean()) ** 2).sum()
    return {"mae": round(float(np.abs(e).mean()), 3),
            "rmse": round(float(np.sqrt((e ** 2).mean())), 3),
            "wape_pct": round(float(100 * np.abs(e).sum() / max(np.abs(y).sum(), 1e-9)), 2),
            "r2": round(float(1 - (e ** 2).sum() / sst), 3) if sst > 0 else 0.0,
            "sesgo": round(float(-e.mean()), 3)}       # >0: el modelo sobreestima


def serie_ingresos(df: pd.DataFrame) -> pd.Series:
    """Ingresos por día (los días sin ingresos valen 0)."""
    s = df["fecha_ingreso"].dt.normalize().value_counts().sort_index()
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D"), fill_value=0).astype(float)


# ======================================================================
# 1) Demanda: ingresos diarios
# ======================================================================
METODOS = ["media_28d", "naive_semanal", "estacional", "regresion"]
MEJORA_MINIMA_PCT = 3.0
NOMBRES = {"media_28d": "Media 28 días", "naive_semanal": "Semana anterior",
           "estacional": "Estacional (mes × día)", "regresion": "Regresión Ridge"}


class ModeloDemanda:
    def __init__(self, serie: pd.Series, nombre: str = ""):
        self.nombre = nombre
        self.y = serie.astype(float)
        self.origen = self.y.index.min()
        self.X = self._features(self.y.index)
        self.evaluacion = self._backtest()
        self.metodo_elegido = self._elegir()
        self.rmse = {m: self.evaluacion["metricas"][m]["rmse"] for m in METODOS}

    def _elegir(self) -> str:
        """El de menor WAPE, pero solo si le gana a la media por al menos MEJORA_MINIMA_PCT.
        Si no, la media: con una ventaja tan chica no se justifica un modelo más complejo
        (principio de parsimonia; evita 'aprender' ruido, como pasa con el dataset sintético)."""
        m = self.evaluacion["metricas"]
        mejor = min(METODOS, key=lambda k: m[k]["wape_pct"])
        base = m["media_28d"]["wape_pct"]
        return mejor if 100 * (base - m[mejor]["wape_pct"]) / base >= MEJORA_MINIMA_PCT else "media_28d"

    # ---------- variables explicativas ----------
    def _features(self, fechas: pd.DatetimeIndex) -> pd.DataFrame:
        """Variables de calendario: día de la semana y estacionalidad anual."""
        t = 2 * np.pi * fechas.dayofyear.to_numpy() / 365.25
        X = pd.DataFrame(index=fechas)
        for d in range(1, 7):
            X[f"dia_{d}"] = (fechas.dayofweek == d).astype(float)          # lunes = referencia
        X["sin_anual"], X["cos_anual"] = np.sin(t), np.cos(t)
        X["sin_semestral"], X["cos_semestral"] = np.sin(2 * t), np.cos(2 * t)
        return X

    def _nivel(self, fechas: pd.DatetimeIndex) -> pd.Series:
        """Nivel reciente: media de 28 días que termina 7 días antes de cada fecha.
        Se conoce al momento de pronosticar a 1..7 días, así que no 'mira el futuro'."""
        y = self.y.reindex(fechas.union(self.y.index))
        return y.shift(7).rolling(28, min_periods=14).mean().reindex(fechas)

    def _fit_regresion(self, hasta: pd.Timestamp):
        """Objetivo: desvío respecto del nivel reciente (y - nivel). Así el modelo se adapta
        solo a cambios de nivel (crecimiento, brotes) y aprende el patrón semanal y anual."""
        nivel = self._nivel(self.y.loc[:hasta].index).dropna()
        X = self.X.loc[nivel.index]
        objetivo = (self.y.loc[nivel.index] - nivel).to_numpy()
        mu, sd = X.mean(), X.std().replace(0, 1)
        Z = np.column_stack([np.ones(len(X)), ((X - mu) / sd).to_numpy()])
        return ridge(Z, objetivo), mu, sd

    def _pred(self, metodo: str, hasta: pd.Timestamp, fechas: pd.DatetimeIndex, ajuste=None) -> np.ndarray:
        hist = self.y.loc[:hasta]
        if metodo == "media_28d":
            return np.full(len(fechas), hist.iloc[-28:].mean())
        if metodo == "naive_semanal":
            return np.array([self.y.get(f - pd.Timedelta(days=7), hist.iloc[-7:].mean()) for f in fechas])
        if metodo == "estacional":
            md = hist.groupby([hist.index.month, hist.index.dayofweek]).mean()
            dia = hist.groupby(hist.index.dayofweek).mean()
            return np.array([md.get((f.month, f.dayofweek), dia[f.dayofweek]) for f in fechas])
        coef, mu, sd = ajuste or self._fit_regresion(hasta)
        X = self._features(fechas)
        Z = np.column_stack([np.ones(len(X)), ((X - mu) / sd).to_numpy()])
        nivel = self._nivel(fechas).fillna(hist.iloc[-28:].mean()).to_numpy()
        return np.clip(Z @ coef + nivel, 0, None)

    # ---------- evaluación ----------
    def _backtest(self) -> dict:
        """Backtesting con origen móvil: cada 7 días se entrena con el pasado y se
        pronostican los 7 días siguientes, como pasaría en el uso real."""
        ultimo = self.y.index.max()
        n, paso = config.BACKTEST_ORIGENES, config.BACKTEST_PASO_DIAS
        origenes = [ultimo - pd.Timedelta(days=7 + paso * i) for i in range(n)][::-1]
        origenes = [o for o in origenes if (o - self.origen).days >= 120]
        reales, preds, fechas = [], {m: [] for m in METODOS}, []
        for o in origenes:
            f = pd.date_range(o + pd.Timedelta(days=1), periods=7, freq="D")
            reales.extend(self.y.loc[f]), fechas.extend(f)
            ajuste = self._fit_regresion(o)
            for m in METODOS:
                preds[m].extend(self._pred(m, o, f, ajuste))
        reales = np.array(reales)
        res = {m: metricas(reales, preds[m]) for m in METODOS}
        # Error del TOTAL semanal: es lo que importa para planificar camas (el ruido diario se compensa)
        sem_real = reales.reshape(-1, 7).sum(axis=1)
        for m in METODOS:
            sem_pred = np.array(preds[m]).reshape(-1, 7).sum(axis=1)
            res[m]["wape_semanal_pct"] = round(float(100 * np.abs(sem_real - sem_pred).sum() / sem_real.sum()), 2)
        for m in METODOS:          # cobertura de un intervalo del 80 % construido con el RMSE
            r = res[m]["rmse"] * config.Z_P90
            res[m]["cobertura_80pct"] = round(float(100 * np.mean(np.abs(reales - np.array(preds[m])) <= r)), 1)
        return {"origenes": len(origenes), "dias_evaluados": len(reales),
                "periodo": f"{fechas[0].date()} a {fechas[-1].date()}" if fechas else "",
                "metricas": res,
                "serie": {"fechas": [d.date().isoformat() for d in fechas], "real": reales.tolist(),
                          **{m: np.round(preds[m], 2).tolist() for m in METODOS}}}

    # ---------- uso ----------
    def predecir(self, desde: date, dias: int, metodo: str = "auto") -> tuple[np.ndarray, float]:
        """Ingresos esperados para desde+1 .. desde+dias y el desvío típico del error."""
        metodo = self.metodo_elegido if metodo == "auto" else metodo
        hasta = min(pd.Timestamp(desde), self.y.index.max())
        fechas = pd.date_range(pd.Timestamp(desde) + pd.Timedelta(days=1), periods=dias, freq="D")
        return self._pred(metodo, hasta, fechas), self.rmse[metodo]

    def coeficientes(self) -> dict:
        """Cuántos ingresos suma o resta cada variable respecto del nivel reciente
        (coeficientes sobre variables estandarizadas): para explicar el modelo."""
        coef, *_ = self._fit_regresion(self.y.index.max())
        return dict(zip(["intercepto", *self.X.columns], np.round(coef, 3).tolist()))

    def resumen(self) -> dict:
        m = self.evaluacion["metricas"]
        base = m["media_28d"]["wape_pct"]
        mejor = m[self.metodo_elegido]["wape_pct"]
        return {"serie": self.nombre, "ingresos_promedio_dia": round(float(self.y.mean()), 2),
                "dias_historia": len(self.y), "metodo_elegido": self.metodo_elegido,
                "nombre_metodo": NOMBRES[self.metodo_elegido],
                "mejora_vs_media_pct": round(100 * (base - mejor) / base, 1) if base else 0.0,
                "backtest": {k: v for k, v in self.evaluacion.items() if k != "serie"}}


# ======================================================================
# 2) Estancia por paciente (HDHI)
# ======================================================================
VARS_PACIENTE = ["edad", "sexo_m", "rural", "urgencia", "SMOKING", "ALCOHOL", "DM", "HTN", "CAD",
                 "PRIOR CMP", "CKD", "RAISED CARDIAC ENZYMES"]
LAB_ESTANCIA = ["HB", "TLC", "PLATELETS", "GLUCOSE", "UREA", "CREATININE", "EF"]


class ModeloEstancia:
    """Predice noches totales y noches en UTI de un paciente al ingreso."""

    def __init__(self, hdhi: pd.DataFrame, patologias: list[str], semilla: int = 42):
        self.patologias = patologias
        X = self._matriz(hdhi)
        self.mu, self.sd = X.mean(), X.std().replace(0, 1)
        Z = self._z(X)
        test = np.random.default_rng(semilla).random(len(hdhi)) < 0.2
        self.coef, self.evaluacion = {}, {}
        alos_pat = hdhi[~test].groupby("patologia")
        for objetivo in ("los_dias", "dias_uti"):
            y = hdhi[objetivo].to_numpy(float)
            c = ridge(Z[~test], y[~test], lam=5.0)
            base = hdhi.loc[test, "patologia"].map(alos_pat[objetivo].mean()).to_numpy()
            self.evaluacion[objetivo] = {"regresion": metricas(y[test], np.clip(Z[test] @ c, 0, None)),
                                         "baseline_alos_patologia": metricas(y[test], base)}
            self.coef[objetivo] = ridge(Z, y, lam=5.0)         # modelo final con todo
        self.evaluacion["registros_train"], self.evaluacion["registros_test"] = int((~test).sum()), int(test.sum())

    def _matriz(self, d: pd.DataFrame) -> pd.DataFrame:
        X = pd.DataFrame(index=d.index)
        X["edad"] = d["edad"]
        X["sexo_m"] = (d["sexo"] == "M").astype(float)
        X["rural"] = (d.get("RURAL", "U") == "R").astype(float) if "RURAL" in d else 0.0
        X["urgencia"] = (d["tipo_ingreso"] == "Urgencia").astype(float)
        for c in VARS_PACIENTE[4:] + LAB_ESTANCIA:
            X[c] = d[c].astype(float) if c in d else np.nan
        for p in self.patologias:
            X[f"pat_{p}"] = (d["patologia"] == p).astype(float)
        return X

    def _z(self, X: pd.DataFrame) -> np.ndarray:
        Z = ((X.fillna(self.mu) - self.mu) / self.sd).to_numpy()
        return np.column_stack([np.ones(len(X)), Z])

    def predecir(self, paciente: dict) -> dict:
        X = self._matriz(pd.DataFrame([paciente]))
        z = self._z(X)[0]
        out = {}
        for objetivo, nombre in (("los_dias", "noches_totales"), ("dias_uti", "noches_uti")):
            aportes = z * self.coef[objetivo]
            out[nombre] = round(max(0.0, float(aportes.sum())), 1)
            if objetivo == "los_dias":
                top = sorted(zip(X.columns, aportes[1:]), key=lambda t: abs(t[1]), reverse=True)[:5]
                out["factores_principales"] = [{"variable": n.replace("pat_", "Diagnóstico: "),
                                                "aporte_noches": round(float(a), 2)} for n, a in top if abs(a) >= 0.05]
        rmse = self.evaluacion["los_dias"]["regresion"]["rmse"]
        out["rango_80pct"] = [round(max(0.0, out["noches_totales"] - config.Z_P90 * rmse), 1),
                              round(out["noches_totales"] + config.Z_P90 * rmse, 1)]
        return out
