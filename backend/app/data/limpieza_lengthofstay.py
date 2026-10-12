from pathlib import Path
import pandas as pd

# Rutas de los archivos originales y procesados.
CARPETA_DATOS = Path(__file__).resolve().parents[2] / "data"
RUTA_CSV = CARPETA_DATOS / "LengthOfStay.csv"


def limpiar_lengthofstay():
    # 1. Cargar el dataset original.
    df = pd.read_csv(RUTA_CSV)
    print("\n===== LIMPIEZA LENGTHOFSTAY =====")
    print("Dimensiones originales:", df.shape)

    # 2. Revisar nulos y duplicados antes de procesar.
    print("Valores nulos:", df.isna().sum().sum())
    print("Filas duplicadas:", df.duplicated().sum())

    # Trabajar con una copia para no modificar los datos originales.
    df_limpio = df.copy()

    # 3. Conservar las fechas originales y convertirlas a formato fecha.
    for columna in ["vdate", "discharged"]:
        df_limpio[f"{columna}_original"] = df_limpio[columna]
        df_limpio[columna] = pd.to_datetime(
            df_limpio[columna],
            format="%m/%d/%Y",
            errors="coerce"
        )

    # 4. Comprobar que la duracion registrada coincide con las fechas.
    dias_calculados = (
        df_limpio["discharged"] - df_limpio["vdate"]
    ).dt.days

    print("\n===== VALIDACION =====")
    print("Fechas de ingreso invalidas:", df_limpio["vdate"].isna().sum())
    print("Fechas de egreso invalidas:", df_limpio["discharged"].isna().sum())
    print("Egresos anteriores al ingreso:", (dias_calculados < 0).sum())
    print("Duraciones correctas:", (dias_calculados == df_limpio["lengthofstay"]).sum())
    print("Duraciones inconsistentes:", (dias_calculados != df_limpio["lengthofstay"]).sum())

    return df_limpio


if __name__ == "__main__":
    # 5. Guardar el dataset procesado sin alterar el archivo original.
    df_limpio = limpiar_lengthofstay()

    carpeta_procesados = CARPETA_DATOS / "procesados"
    carpeta_procesados.mkdir(parents=True, exist_ok=True)

    ruta_salida = carpeta_procesados / "lengthofstay_limpio.csv"
    df_limpio.to_csv(ruta_salida, index=False, date_format="%Y-%m-%d")

    print("\nDataset procesado guardado en:", ruta_salida)