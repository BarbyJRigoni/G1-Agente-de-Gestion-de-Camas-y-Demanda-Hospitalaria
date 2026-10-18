"""Prepara una tabla candidata de episodios sin reemplazar el CSV del agente.
Ubicacion: backend/app/data/preparar_episodios_hdhi.py
Ejecutar desde la raiz: python backend/app/data/preparar_episodios_hdhi.py

Supuesto documentado: MRD + ingreso + egreso identifican un episodio.
Los grupos con contradicciones de edad/sexo se separan para revision.
En los demas, cada campo se conserva SOLO si todos sus valores coinciden,
incluidos los faltantes. Una diferencia se convierte a faltante y se registra.
No usa OR, maximos ni promedios para inventar condiciones clinicas.
"""
from pathlib import Path
import argparse
import json
import pandas as pd


def preparar(entrada, salida):
    df = pd.read_csv(entrada, low_memory=False)
    requeridas = ["sno", "mrd_no", "fecha_ingreso", "fecha_egreso",
                  "duration_of_stay", "age", "gender", "estado_fechas"]
    faltantes = set(requeridas) - set(df.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas: {sorted(faltantes)}")
    ingreso = pd.to_datetime(df.fecha_ingreso, format="%Y-%m-%d", errors="coerce")
    egreso = pd.to_datetime(df.fecha_egreso, format="%Y-%m-%d", errors="coerce")
    duracion = pd.to_numeric(df.duration_of_stay, errors="coerce")
    valida = (df.estado_fechas.eq("validada") & ingreso.notna() & egreso.notna()
              & (egreso >= ingreso) & (duracion == (egreso - ingreso).dt.days + 1)
              & df.mrd_no.notna())
    candidatos = df.loc[valida].copy()
    candidatos["fecha_ingreso"] = ingreso.loc[valida].dt.strftime("%Y-%m-%d")
    candidatos["fecha_egreso"] = egreso.loc[valida].dt.strftime("%Y-%m-%d")
    excluidos = df.loc[~valida].copy()
    excluidos["motivo_exclusion"] = "sin_fecha_duracion_o_identificador_coherentes"
    claves = ["mrd_no", "fecha_ingreso", "fecha_egreso"]
    auxiliares = {"sno", "uci_inconsistente", "edad_invalida", "duracion_invalida",
                  "episodio_repetido_revisar", "apto_temporal"}
    comparar = [c for c in df.columns
                if c not in claves and c not in auxiliares]
    grupos = candidatos.groupby(claves, sort=True, dropna=False)
    conteos = grupos[comparar].nunique(dropna=False)
    faltantes_identidad = candidatos[["age", "gender"]].isna().any(axis=1)
    candidatos["_identidad_ausente"] = faltantes_identidad
    identidad_invalida = ((conteos.age != 1) | (conteos.gender != 1)
                         | grupos["_identidad_ausente"].any())
    identidad = int(identidad_invalida.sum())
    claves_invalidas = identidad_invalida[identidad_invalida].index
    indice_filas = pd.MultiIndex.from_frame(candidatos[claves])
    rechazar = indice_filas.isin(claves_invalidas)
    rechazado = candidatos.loc[rechazar].drop(columns="_identidad_ausente").copy()
    rechazado["motivo_exclusion"] = "edad_o_sexo_contradictorios_o_ausentes"
    excluidos = pd.concat([excluidos, rechazado], ignore_index=True)
    candidatos = candidatos.loc[~rechazar].drop(columns="_identidad_ausente")
    grupos = candidatos.groupby(claves, sort=True, dropna=False)
    conteos = grupos[comparar].nunique(dropna=False)
    # first() solo se usa donde todos los valores son iguales.
    # Si NaN y un valor difieren, nunique(dropna=False) lo marca como conflicto.
    consenso = grupos[comparar].first().mask(conteos > 1)
    consenso["id_episodio"] = [
        f"HDHI-{mrd}-{fi}-{fe}" for mrd, fi, fe in consenso.index]
    consenso["sno_fuentes"] = grupos.sno.agg(lambda x: "|".join(x.astype(str)))
    consenso["cantidad_registros_fuente"] = grupos.size()
    diferencias = conteos.gt(1)
    consenso["columnas_en_conflicto"] = [
        "|".join(diferencias.columns[fila]) for fila in diferencias.to_numpy()]
    episodios = consenso.reset_index()
    if episodios.empty:
        raise ValueError("No quedaron episodios candidatos.")
    conflictos = []
    for clave, fila in diferencias[diferencias.any(axis=1)].iterrows():
        grupo = grupos.get_group(clave)
        for columna in diferencias.columns[fila]:
            valores = [
                None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)
                for v in grupo[columna].drop_duplicates()]
            conflictos.append({
                "id_episodio": consenso.loc[clave, "id_episodio"],
                "sno_fuentes": consenso.loc[clave, "sno_fuentes"],
                "columna": columna,
                "valores": json.dumps(valores, ensure_ascii=False)})
    reporte = {
        "filas_revision": len(df),
        "filas_con_fechas_duracion_e_id_coherentes": int(valida.sum()),
        "grupos_apartados_por_identidad": identidad,
        "filas_apartadas_por_identidad": len(rechazado),
        "episodios_candidatos": len(episodios),
        "episodios_con_campos_en_conflicto": int(
            episodios.columnas_en_conflicto.ne("").sum()),
        "alos_registrado_cohorte_candidata": round(
            float(episodios.duration_of_stay.mean()), 6),
        "supuesto": "MRD + ingreso + egreso identifican un episodio; requiere documentacion.",
        "criterio": "Campos contradictorios quedan ausentes; no se fusionan diagnosticos con OR.",
        "limitaciones": [
            "No prueba la identidad real de pacientes ni resuelve internaciones superpuestas.",
            "Las fechas fueron reconstruidas retrospectivamente con duracion y mes de ingreso.",
            "Los faltantes de diagnostico no equivalen a ausencia de enfermedad.",
            "La exclusion por identidad puede sesgar las estadisticas.",
            "Salida candidata: no cambia cargar_datos(), el modelo ni la API.",
        ],
    }
    salida.mkdir(parents=True, exist_ok=True)
    episodios.to_csv(salida / "hdhi_episodios_candidatos.csv", index=False)
    excluidos.to_csv(salida / "hdhi_episodios_apartados.csv", index=False)
    pd.DataFrame(conflictos, columns=["id_episodio", "sno_fuentes", "columna", "valores"]).to_csv(
        salida / "hdhi_conflictos_por_campo.csv", index=False)
    indicadores = indicadores_hdhi(episodios)
    (salida / "hdhi_indicadores_candidatos.json").write_text(
        json.dumps(indicadores, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8")
    (salida / "resumen_episodios.json").write_text(
        json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(reporte, ensure_ascii=False, indent=2))
    print("\nALOS por patologia (los desconocidos no se cuentan como ausencia):")
    print(pd.DataFrame(indicadores["patologias"]).to_string(index=False))
    print("\nALOS por grupo etario:")
    print(pd.DataFrame(indicadores["grupos_etarios"]).to_string(index=False))
    print(f"Salida: {salida.resolve()}")
    return episodios, reporte


PATOLOGIAS = {
    "dm": "Diabetes mellitus", "htn": "Hipertension",
    "cad": "Enfermedad coronaria", "ckd": "Enfermedad renal cronica",
    "heart_failure": "Insuficiencia cardiaca", "aki": "Lesion renal aguda",
    "acs": "Sindrome coronario agudo", "anaemia": "Anemia",
}


def indicadores_hdhi(df):
    """Resume episodios candidatos sin imputar diagnosticos contradictorios."""
    duracion = pd.to_numeric(df.duration_of_stay, errors="coerce")
    if duracion.isna().any() or (duracion <= 0).any():
        raise ValueError("La duracion de los episodios debe ser positiva y conocida.")
    general = float(duracion.mean())

    def resumen(dias):
        return {
            "cantidad_internaciones": int(len(dias)),
            "alos_promedio": round(float(dias.mean()), 2) if len(dias) else None,
            "mediana_dias": round(float(dias.median()), 2) if len(dias) else None,
            "desviacion_estandar": round(float(dias.std()), 2) if len(dias) > 1 else None,
            "percentil_90_dias": round(float(dias.quantile(.9)), 2) if len(dias) else None,
            "indice_estancia": round(float(dias.mean()) / general, 3) if len(dias) else None,
        }

    patologias = []
    for c, nombre in PATOLOGIAS.items():
        indicador = pd.to_numeric(df[c], errors="coerce")
        conocida = indicador.isin([0, 1])
        patologias.append({
            "columna": c, "patologia": nombre,
            **resumen(duracion[indicador.eq(1)]),
            "cantidad_con_dato_conocido": int(conocida.sum()),
            "cantidad_sin_dato": int((~conocida).sum()),
            "cantidad_ausencia_confirmada": int(indicador.eq(0).sum()),
        })
    edad = pd.to_numeric(df.age, errors="coerce")
    grupos = pd.cut(edad, bins=[0, 18, 30, 45, 60, 75, float("inf")],
                    labels=["0-17", "18-29", "30-44", "45-59", "60-74", "75 o mas"],
                    right=False)
    edades = [
        {"grupo_etario": str(grupo), **resumen(dias)}
        for grupo, dias in duracion.groupby(grupos, observed=True, sort=True)]
    return {
        "dataset": "hdhi", "estado": "cohorte_candidata_sin_integrar",
        "total_internaciones": len(df), "alos_general_dias": round(general, 2),
        "columna_duracion": "duration_of_stay",
        "patologias": patologias, "grupos_etarios": edades,
        "cantidad_sin_grupo_etario": int(grupos.isna().sum()),
        "aclaraciones": [
            "Una fila representa un episodio candidato segun MRD, ingreso y egreso.",
            "Campos contradictorios quedan como faltantes, nunca se convierten a cero.",
            "Cada patologia informa presentes, ausencias confirmadas y desconocidos.",
            "Los grupos de patologias se superponen y no se suman como pacientes unicos.",
            "Indice de estancia = ALOS del grupo / ALOS general de esta cohorte.",
            "Este archivo no reemplaza la respuesta actual de la API.",
        ],
    }


if __name__ == "__main__":
    base = Path(__file__).resolve().parents[2] / "data" / "procesados" / "revision_hdhi"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", type=Path, default=base / "hdhi_limpio_revision.csv")
    parser.add_argument("--salida", type=Path, default=base / "episodios")
    args = parser.parse_args()
    preparar(args.entrada, args.salida)
