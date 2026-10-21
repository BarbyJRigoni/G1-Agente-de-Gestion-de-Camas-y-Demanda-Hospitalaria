"""Revision reproducible de HDHI. No reemplaza hdhi_limpio.csv.
Copiar en backend/app/data/ y ejecutar desde la raiz del proyecto:
python backend/app/data/limpieza_hdhi_revision.py

Elimina solo repeticiones identicas excepto SNO, conservando una copia
y exportando las adicionales. No fusiona episodios con datos distintos.
Valida fechas con duracion inclusiva y month_year. Conserva valores
originales y marca inconsistencias de UCI e indicadores binarios.
"""
from pathlib import Path
import argparse
import json
import pandas as pd

CLINICAS = ["hb", "tlc", "platelets", "glucose", "urea", "creatinine", "bnp", "ef"]
BINARIAS = [
    "smoking", "alcohol", "dm", "htn", "cad", "prior_cmp", "ckd",
    "raised_cardiac_enzymes", "severe_anaemia", "anaemia", "stable_angina",
    "acs", "stemi", "atypical_chest_pain", "heart_failure", "hfref", "hfnef",
    "valvular", "chb", "sss", "aki", "cva_infract", "cva_bleed", "af", "vt",
    "psvt", "congenital", "uti", "neuro_cardiogenic_syncope", "orthostatic",
    "infective_endocarditis", "dvt", "cardiogenic_shock", "shock",
    "pulmonary_embolism", "chest_infection",
]
FORMATOS = ["%m/%d/%Y", "%d/%m/%Y"]


def validar_fechas(df):
    df = df.copy()
    df["fecha_ingreso_original"] = df["d_o_a"]
    df["fecha_egreso_original"] = df["d_o_d"]
    # Mapeo explicito: no depende del idioma configurado en Windows.
    meses = dict(zip(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug",
         "sep", "oct", "nov", "dec"], range(1, 13)))
    partes = df["month_year"].astype("string").str.strip().str.lower().str.extract(
        r"^([a-z]{3})-(\d{2}|\d{4})$")
    mes = partes[0].map(meses)
    anio = pd.to_numeric(partes[1], errors="coerce")
    anio = anio.where(anio >= 100, anio + 2000)
    opciones = {}
    for fi in FORMATOS:
        ingreso = pd.to_datetime(df["d_o_a"], format=fi, errors="coerce")
        for fe in FORMATOS:
            egreso = pd.to_datetime(df["d_o_d"], format=fe, errors="coerce")
            valido = (
                ingreso.notna() & egreso.notna() & (egreso >= ingreso)
                & ((egreso - ingreso).dt.days + 1 == df["duration_of_stay"])
                & (ingreso.dt.month == mes) & (ingreso.dt.year == anio)
            )
            for i in df.index[valido]:
                opciones.setdefault(i, set()).add((ingreso.loc[i], egreso.loc[i]))
    df["fecha_ingreso"] = pd.NaT
    df["fecha_egreso"] = pd.NaT
    df["estado_fechas"] = "sin_coincidencia"
    for i, parejas in opciones.items():
        if len(parejas) == 1:
            df.at[i, "fecha_ingreso"], df.at[i, "fecha_egreso"] = next(iter(parejas))
            df.at[i, "estado_fechas"] = "validada"
        else:
            df.at[i, "estado_fechas"] = "ambigua"
    return df


def revisar(ruta, carpeta):
    df = pd.read_csv(ruta)
    originales = len(df)
    df.columns = (df.columns.str.strip().str.lower()
                  .str.replace(r"[^a-z0-9]+", "_", regex=True).str.strip("_"))
    if df.columns.duplicated().any():
        raise ValueError("Hay nombres de columnas repetidos despues de normalizar.")
    requeridas = set(CLINICAS + BINARIAS + [
        "sno", "mrd_no", "d_o_a", "d_o_d", "age", "month_year",
        "duration_of_stay", "duration_of_intensive_unit_stay"])
    faltantes = requeridas - set(df.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas: {sorted(faltantes)}")

    # Comparar datos fuente antes de convertir: no confundir dos valores
    # distintos que despues se conviertan al mismo NaN.
    repetida = df.duplicated(subset=[c for c in df.columns if c != "sno"])
    duplicados = df.loc[repetida].copy()
    df = df.loc[~repetida].copy()

    for c in CLINICAS + BINARIAS + [
        "age", "duration_of_stay", "duration_of_intensive_unit_stay"]:
        fuente = df[c].copy()
        numerica = pd.to_numeric(fuente, errors="coerce")
        invalida = numerica.isna() & fuente.notna()
        if c in BINARIAS:
            invalida |= numerica.notna() & ~numerica.isin([0, 1])
        if invalida.any():
            df[c + "_original"] = fuente
        if c in BINARIAS:
            numerica = numerica.where(numerica.isin([0, 1]))
        df[c] = numerica

    df = validar_fechas(df)
    df["uci_inconsistente"] = (
        df["duration_of_intensive_unit_stay"].isna()
        | (df["duration_of_intensive_unit_stay"] < 0)
        | (df["duration_of_intensive_unit_stay"] > df["duration_of_stay"])
    )
    # Estos limites son controles tecnicos, no validacion clinica.
    df["edad_invalida"] = df.age.isna() | (df.age < 0) | (df.age > 120)
    df["duracion_invalida"] = (
        df.duration_of_stay.isna() | (df.duration_of_stay < 1)
        | (df.duration_of_stay % 1 != 0)
    )
    valida = df.estado_fechas.eq("validada")
    clave = ["mrd_no", "fecha_ingreso", "fecha_egreso"]
    df["episodio_repetido_revisar"] = False
    df.loc[valida, "episodio_repetido_revisar"] = (
        df.loc[valida].duplicated(clave, keep=False))
    # No equivale a aprobado: quedan episodios repetidos pendientes.
    df["apto_temporal"] = valida & ~df.duracion_invalida

    resumen = {
        "filas_originales": originales,
        "repeticiones_identicas_excluyendo_sno_retiradas": len(duplicados),
        "filas_revision": len(df),
        "estado_fechas": {k: int(v) for k, v in df.estado_fechas.value_counts().items()},
        "uci_inconsistente": int(df.uci_inconsistente.sum()),
        "filas_en_episodios_repetidos_a_revisar": int(df.episodio_repetido_revisar.sum()),
        "edad_invalida": int(df.edad_invalida.sum()),
        "duracion_invalida": int(df.duracion_invalida.sum()),
        "alos_registrado_revision": round(float(df.duration_of_stay.mean()), 6),
        "nulos_clinicos": {k: int(v) for k, v in df[CLINICAS].isna().sum().items()},
        "nulos_binarios": {k: int(v) for k, v in df[BINARIAS].isna().sum().items() if v},
        "criterios": [
            "Duracion HDHI = egreso - ingreso + 1 dia.",
            "Fechas contrastadas con mes y anio de ingreso.",
            "Se conserva una copia de registros identicos excepto SNO.",
            "Episodios repetidos con diferencias se marcan, no se fusionan.",
            "UCI inconsistente se marca sin cambiar su valor.",
            "apto_temporal no resuelve la identidad de episodios repetidos.",
            "No se reemplaza hdhi_limpio.csv ni se modifica el agente.",
        ],
    }
    carpeta.mkdir(parents=True, exist_ok=True)
    df.to_csv(carpeta / "hdhi_limpio_revision.csv", index=False, date_format="%Y-%m-%d")
    duplicados.to_csv(carpeta / "hdhi_duplicados_retirados_revision.csv", index=False)
    df.loc[~df.apto_temporal | df.uci_inconsistente | df.edad_invalida
           | df.episodio_repetido_revisar].to_csv(
               carpeta / "hdhi_casos_a_revisar.csv", index=False, date_format="%Y-%m-%d")
    (carpeta / "hdhi_resumen_revision.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(f"Archivos de revision guardados en: {carpeta.resolve()}")
    return df, resumen


if __name__ == "__main__":
    base = Path(__file__).resolve().parents[2] / "data"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", type=Path, default=base / "HDHI Admission data.csv")
    parser.add_argument("--salida", type=Path, default=base / "procesados" / "revision_hdhi")
    args = parser.parse_args()
    revisar(args.entrada, args.salida)
