"""ALOS de HDHI por patologia/comorbilidad y grupo etario.

Ubicacion en el proyecto: backend/app/services/analisis_hdhi.py
Ejecutar desde la raiz: python backend/app/services/analisis_hdhi.py

Usa el CSV limpio a traves de cargar_datos(), del analisis de Sabrina.
Trabaja con duration_of_stay tal como esta registrada en HDHI. No convierte
la estancia a noches ni excluye registros por el estado de sus fechas.
Los ocho indicadores analizados admiten 0 (ausencia) y 1 (presencia).
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
    """Valida una copia de los datos sin escribir ni modificar el CSV."""
    datos = (_cargar_hdhi() if df is None else df).copy()
    necesarias = ["duration_of_stay", *columnas]
    faltantes = [columna for columna in necesarias if columna not in datos]
    if faltantes:
        raise ValueError(f"Faltan columnas de HDHI: {faltantes}")
    if datos.empty:
        raise ValueError("HDHI no tiene internaciones para analizar.")

    for columna in necesarias:
        valores = pd.to_numeric(datos[columna], errors="coerce")
        if valores.isna().any() or not valores.map(isfinite).all():
            raise ValueError(f"La columna {columna} tiene valores nulos o no numericos.")
        datos[columna] = valores

    if (datos["duration_of_stay"] <= 0).any():
        raise ValueError("La duracion registrada de HDHI debe ser mayor que cero.")
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
    """Resume cada indicador presente, conservando los grupos que se superponen."""
    datos = _preparar_datos(df, PATOLOGIAS_HDHI)
    alos_general = float(datos["duration_of_stay"].mean())
    filas = []

    for columna, nombre in PATOLOGIAS_HDHI.items():
        if not datos[columna].isin([0, 1]).all():
            raise ValueError(f"El indicador {columna} debe contener solo 0 y 1.")
        dias = datos.loc[datos[columna] == 1, "duration_of_stay"]
        if not dias.empty:
            filas.append({
                "columna": columna,
                "patologia": nombre,
                **_resumir_estancia(dias, alos_general),
            })
            

    columnas = ["columna", "patologia", "cantidad_internaciones", "alos_promedio",
                "mediana_dias", "desviacion_estandar", "percentil_90_dias", "indice_estancia"]
    tabla = pd.DataFrame(filas, columns=columnas)
    return tabla.sort_values("alos_promedio", ascending=False, kind="stable").reset_index(drop=True)

def calcular_alos_hdhi_por_grupo_etario(df=None):
    """Agrupa por edad: 18 pertenece a 18-29 y 75 pertenece a 75 o mas."""
    datos = _preparar_datos(df, ["age"])
    if (datos["age"] < 0).any():
        raise ValueError("HDHI contiene edades negativas.")

    datos["grupo_etario"] = pd.cut(
        datos["age"], bins=LIMITES_EDAD, labels=GRUPOS_EDAD, right=False
    )
    alos_general = float(datos["duration_of_stay"].mean())
    filas = [
        {"grupo_etario": str(grupo), **_resumir_estancia(dias, alos_general)}
        for grupo, dias in datos.groupby("grupo_etario", observed=True, sort=True)["duration_of_stay"]
    ]
    return pd.DataFrame(filas)

def obtener_indicadores_hdhi(df=None):
    """Devuelve indicadores y tablas como un diccionario apto para FastAPI."""
    datos = _preparar_datos(df)
    patologias = calcular_alos_hdhi_por_patologia(datos)
    edades = calcular_alos_hdhi_por_grupo_etario(datos)
    return {
        "dataset": "hdhi",
        "total_internaciones": int(len(datos)),
        "alos_general_dias": round(float(datos["duration_of_stay"].mean()), 2),
        "columna_duracion": "duration_of_stay",
        "patologias": json.loads(patologias.to_json(orient="records", force_ascii=False)),
        "grupos_etarios": json.loads(edades.to_json(orient="records", force_ascii=False)),
        "aclaraciones": [
            "Se analiza la duracion registrada en todas las internaciones del CSV limpio.",
            "Una internacion puede tener varios indicadores de patologia/comorbilidad presentes.",
            "Las cantidades por patologia no deben sumarse como pacientes unicos.",
            "El indice compara el ALOS de cada grupo con el ALOS general del mismo dataset.",
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