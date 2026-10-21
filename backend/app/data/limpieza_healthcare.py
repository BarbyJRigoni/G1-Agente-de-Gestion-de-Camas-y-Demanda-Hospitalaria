
from pathlib import Path
import pandas as pd

# Rutas del dataset original y la carpeta de archivos procesados.
CARPETA_DATOS = Path(__file__).resolve().parents[2] / "data"
RUTA_CSV = CARPETA_DATOS / "healthcare_dataset.csv"


def limpiar_healthcare():
    # 1. Cargar el dataset original.
    df = pd.read_csv(RUTA_CSV)
    print("\n===== LIMPIEZA HEALTHCARE =====")
    print("Dimensiones originales:", df.shape)

    # 2. Estandarizar los nombres de las columnas.
    df.columns = (
        df.columns.str.strip().str.lower()
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
        .str.strip("_")
    )

    # Guardar los nombres de las 15 columnas originales.
    columnas_originales = df.columns.tolist()

    # 3. Revisar valores nulos y duplicados.
    print("Valores nulos:", df.isna().sum().sum())
    print("Filas duplicadas:", df.duplicated().sum())

    # 4. Eliminar duplicados exactos, conservando el primer registro.
    df = df.drop_duplicates(subset=columnas_originales).reset_index(drop=True)
    print("Registros sin duplicados:", len(df))

    # 5. Conservar las fechas originales y convertirlas.
    for columna, respaldo in [
        ("date_of_admission", "fecha_ingreso_original"),
        ("discharge_date", "fecha_egreso_original")
    ]:
        df[respaldo] = df[columna]
        df[columna] = pd.to_datetime(
            df[columna], format="%Y-%m-%d", errors="coerce"
        )

    # Calcular la duración como diferencia entre egreso e ingreso.
    df["duracion_internacion"] = (
    df["discharge_date"] - df["date_of_admission"]
        ).dt.days

    # 7. Validar fechas y duraciones.
    print("\n===== VALIDACION =====")
    print("Fechas de ingreso invalidas:", df["date_of_admission"].isna().sum())
    print("Fechas de egreso invalidas:", df["discharge_date"].isna().sum())
    print("Duraciones invalidas:", (df["duracion_internacion"] <= 0).sum())
    print("Duracion minima:", df["duracion_internacion"].min())
    print("Duracion maxima:", df["duracion_internacion"].max())
    print("Duracion promedio:", round(df["duracion_internacion"].mean(), 2))
    print("Dimensiones finales:", df.shape)

    return df


if __name__ == "__main__":
    # 8. Guardar el dataset limpio sin modificar el original.
    df_limpio = limpiar_healthcare()

    carpeta_procesados = CARPETA_DATOS / "procesados"
    carpeta_procesados.mkdir(parents=True, exist_ok=True)

    ruta_salida = carpeta_procesados / "healthcare_limpio.csv"
    df_limpio.to_csv(ruta_salida, index=False, date_format="%Y-%m-%d")

    print("\nDataset procesado guardado en:", ruta_salida)
