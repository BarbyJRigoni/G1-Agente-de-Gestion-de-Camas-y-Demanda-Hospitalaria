"""ALOS de HDHI por patologia/comorbilidad y grupo etario.

Ubicacion en el proyecto: backend/app/services/analisis_hdhi.py
Ejecutar desde la raiz: python backend/app/services/analisis_hdhi.py

Usa el CSV limpio a traves de cargar_datos(), del analisis de Sabrina.
Trabaja con duration_of_stay tal como esta registrada en HDHI. No convierte
la estancia a noches. La carga comun selecciona los episodios revisados.
Los indicadores admiten 0 (ausencia), 1 (presencia) y faltantes (desconocidos).
Una internacion puede estar incluida en varias patologias/comorbilidades.
Los resultados cuentan internaciones, no pacientes unicos.
Descripcion original de las variables: https://pmc.ncbi.nlm.nih.gov/articles/PMC8871182/

indice_estancia = ALOS del grupo / ALOS general de este mismo dataset.
Un indice mayor que 1 indica mayor estancia promedio; no es un score clinico.
"""

import json
from math import isfinite

import pandas as pd

# Se usan las ocho columnas cuyos valores se comprobaron en el CSV limpio.
PATOLOGIAS_HDHI = {
    "dm": "Diabetes mellitus",
    "htn": "Hipertension",
    "cad": "Enfermedad coronaria",
    "ckd": "Enfermedad renal cronica",
    "heart_failure": "Insuficiencia cardiaca",
    "aki": "Lesion renal aguda",
    "acs": "Sindrome coronario agudo",
    "anaemia": "Anemia",
}

LIMITES_EDAD = [0, 18, 30, 45, 60, 75, float("inf")]
GRUPOS_EDAD = ["0-17", "18-29", "30-44", "45-59", "60-74", "75 o mas"]

def _cargar_hdhi():
    # Permite importar como services.analisis_hdhi o ejecutar este archivo.
    if __package__:
        from .analisis import cargar_datos
    else:
        from analisis import cargar_datos
    return cargar_datos("hdhi")

def _preparar_datos(df=None, columnas=()):
    """Acepta desconocidos en edad/diagnosticos, exige duracion valida."""
    datos = (_cargar_hdhi() if df is None else df).copy()
    necesarias = ["duration_of_stay", *columnas]
    faltantes = [c for c in necesarias if c not in datos]
    if faltantes:
        raise ValueError(f"Faltan columnas de HDHI: {faltantes}")
    if datos.empty:
        raise ValueError("HDHI no tiene episodios para analizar.")
    for c in necesarias:
        original = datos[c]
        valores = pd.to_numeric(original, errors="coerce")
        if (original.notna() & valores.isna()).any():
            raise ValueError(f"La columna {c} contiene valores no numericos.")
        if not valores.dropna().map(isfinite).all():
            raise ValueError(f"La columna {c} contiene valores no finitos.")
        if c == "duration_of_stay" and (valores.isna().any() or (valores <= 0).any()):
            raise ValueError("La duracion debe ser positiva y conocida.")
        datos[c] = valores
    return datos

def _resumir_estancia(dias, alos_general):
    """Calcula el indice con el promedio sin redondear."""
    alos = float(dias.mean())
    return {
        "cantidad_internaciones": int(len(dias)),
        "alos_promedio": round(alos, 2),
        "mediana_dias": round(float(dias.median()), 2),
        "desviacion_estandar": round(float(dias.std()), 2) if len(dias) > 1 else None,
        "percentil_90_dias": round(float(dias.quantile(0.90)), 2),
        "indice_estancia": round(alos / alos_general, 3),
    }  


def calcular_alos_hdhi_por_patologia(df=None):
    """Cada indicador desconocido se informa aparte y nunca se interpreta como 0."""
    datos = _preparar_datos(df, PATOLOGIAS_HDHI)
    alos_general = float(datos["duration_of_stay"].mean())
    filas = []
    for columna, nombre in PATOLOGIAS_HDHI.items():
        indicador = datos[columna]
        if not indicador.dropna().isin([0, 1]).all():
            raise ValueError(f"El indicador {columna} debe ser 0, 1 o faltante.")
        dias = datos.loc[indicador.eq(1), "duration_of_stay"]
        resumen = (_resumir_estancia(dias, alos_general) if len(dias) else {
            "cantidad_internaciones": 0, "alos_promedio": None,
            "mediana_dias": None, "desviacion_estandar": None,
            "percentil_90_dias": None, "indice_estancia": None})
        filas.append({
            "columna": columna, "patologia": nombre, **resumen,
            "cantidad_con_dato_conocido": int(indicador.notna().sum()),
            "cantidad_sin_dato": int(indicador.isna().sum()),
            "cantidad_ausencia_confirmada": int(indicador.eq(0).sum()),
        })
    return pd.DataFrame(filas).sort_values(
        "alos_promedio", ascending=False, kind="stable", na_position="last").reset_index(drop=True)

def calcular_alos_hdhi_por_grupo_etario(df=None):
    datos = _preparar_datos(df, ["age"])
    if (datos["age"].dropna() < 0).any():
        raise ValueError("HDHI contiene edades negativas.")
    datos["grupo_etario"] = pd.cut(
        datos["age"], bins=LIMITES_EDAD, labels=GRUPOS_EDAD, right=False)
    general = float(datos["duration_of_stay"].mean())
    filas = [
        {"grupo_etario": str(grupo), **_resumir_estancia(dias, general)}
        for grupo, dias in datos.groupby(
            "grupo_etario", observed=True, sort=True)["duration_of_stay"]]
    return pd.DataFrame(filas, columns=[
        "grupo_etario", "cantidad_internaciones", "alos_promedio",
        "mediana_dias", "desviacion_estandar", "percentil_90_dias", "indice_estancia"])

def obtener_indicadores_hdhi(df=None):
    datos = _preparar_datos(df)
    patologias = calcular_alos_hdhi_por_patologia(datos)
    edades = calcular_alos_hdhi_por_grupo_etario(datos)
    return {
        "dataset": "hdhi",
        "fuente": "episodios_revision" if "id_episodio" in datos else "datos_proporcionados",
        "total_internaciones": int(len(datos)),
        "alos_general_dias": round(float(datos["duration_of_stay"].mean()), 2),
        "columna_duracion": "duration_of_stay",
        "cantidad_sin_grupo_etario": int(pd.to_numeric(
            datos["age"], errors="coerce").isna().sum()),
        "patologias": json.loads(patologias.to_json(orient="records", force_ascii=False)),
        "grupos_etarios": json.loads(edades.to_json(orient="records", force_ascii=False)),
        "aclaraciones": [
            "Se analizan episodios consolidados bajo el supuesto MRD + ingreso + egreso.",
            "Se apartaron grupos con edad o sexo contradictorios y registros sin fechas coherentes.",
            "Los diagnosticos contradictorios quedan desconocidos; no equivalen a ausencia.",
            "Cada patologia informa cantidad de datos conocidos y desconocidos.",
            "Una internacion puede aparecer en varias patologias; no sumar como pacientes unicos.",
            "Indice de estancia = ALOS del grupo / ALOS general de esta misma cohorte.",
            "La seleccion de registros y la reconstruccion de fechas pueden sesgar los resultados.",
        ],
    }

if __name__ == "__main__":
    df_hdhi = _preparar_datos()
    print("\n===== INDICADORES GENERALES HDHI =====")
    print("Internaciones:", len(df_hdhi))
    print("ALOS registrado:", round(float(df_hdhi["duration_of_stay"].mean()), 2), "dias")
    print("\n===== ALOS HDHI POR PATOLOGIA / COMORBILIDAD =====")
    print(calcular_alos_hdhi_por_patologia(df_hdhi).to_string(index=False))
    print("\n===== ALOS HDHI POR GRUPO ETARIO =====")
    print(calcular_alos_hdhi_por_grupo_etario(df_hdhi).to_string(index=False))
    print("\nUna internacion puede aparecer en varias patologias; los grupos no son excluyentes.")
    print("Indice de estancia: ALOS del grupo / ALOS general; valores mayores a 1 indican mayor promedio.")