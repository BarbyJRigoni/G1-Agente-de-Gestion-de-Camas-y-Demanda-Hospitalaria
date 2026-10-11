from pathlib import Path
import pandas as pd

# Configuracion/ rutas

CARPETA_DATOS = Path(__file__).resolve().parents[2] / "data"
RUTA_CSV = CARPETA_DATOS / "HDHI Admission data.csv"

COLUMNAS_CLINICAS = [
    "hb", "tlc", "platelets", "glucose",
    "urea", "creatinine", "bnp", "ef"
]

FORMATOS_FECHA = ["%m/%d/%Y", "%d/%m/%Y"]


# validacion de fechas

def validar_fechas(df):
    
    """
    Busca parejas de fechas coherentes con la duracion
    registrada, contando el dia de ingreso. No inventa fechas cuando no existe una solucion unica.
    """

    df = df.copy()

    df["fecha_ingreso_original"] = df["d_o_a"]
    df["fecha_egreso_original"] = df["d_o_d"]

    opciones = {}

    for formato_ingreso in FORMATOS_FECHA:
        for formato_egreso in FORMATOS_FECHA:

            ingreso = pd.to_datetime(
                df["d_o_a"],
                format=formato_ingreso,
                errors="coerce"
            )

            egreso = pd.to_datetime(
                df["d_o_d"],
                format=formato_egreso,
                errors="coerce"
            )

            duracion = (egreso - ingreso).dt.days + 1

            valido = (
                duracion == df["duration_of_stay"]
            )

            for indice in df.index[valido]:

                pareja = (
                    ingreso.loc[indice],
                    egreso.loc[indice]
                )

                opciones.setdefault(indice, set()).add(pareja)

    df["fecha_ingreso"] = pd.NaT
    df["fecha_egreso"] = pd.NaT
    df["estado_fechas"] = "sin_coincidencia"

    for indice, parejas in opciones.items():

        if len(parejas) == 1:
            fecha_ingreso, fecha_egreso = next(iter(parejas))

            df.at[indice, "fecha_ingreso"] = fecha_ingreso
            df.at[indice, "fecha_egreso"] = fecha_egreso
            df.at[indice, "estado_fechas"] = "validada"

        else:
            df.at[indice, "estado_fechas"] = "ambigua"

    df["fecha_ingreso"] = pd.to_datetime(
        df["fecha_ingreso"]
    )

    df["fecha_egreso"] = pd.to_datetime(
        df["fecha_egreso"]
    )

    return df

# Limpieza del dataset HDHI

def limpiar_hdhi():

    # Cargar archivo original
    df = pd.read_csv(RUTA_CSV)

    print("\n===== LIMPIEZA HDHI ADMISSION =====")
    print("Dimensiones originales:", df.shape)

    # Trabajar sobre una copia
    df_limpio = df.copy()

    # Estandarizar nombres de columnas
    df_limpio.columns = (
        df_limpio.columns
        .str.strip()
        .str.lower()
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
        .str.strip("_")
    )

    # Convertir valores vacios
    df_limpio[COLUMNAS_CLINICAS] = (
        df_limpio[COLUMNAS_CLINICAS]
        .replace("EMPTY", pd.NA)
    )

    # Convertir columnas clinicas a numeros
    for columna in COLUMNAS_CLINICAS:
        df_limpio[columna] = pd.to_numeric(
            df_limpio[columna],
            errors="coerce"
        )

    # Revisar duplicados sin eliminarlos
    duplicados = df_limpio.duplicated().sum()

    # Validar fechas
    df_limpio = validar_fechas(df_limpio)

    # Corregir valor invalido conocido
    df_limpio["chest_infection"] = pd.to_numeric(
        df_limpio["chest_infection"],
        errors="coerce"
    )

    # Resumen
    print("\nDimensiones despues de la limpieza:")
    print(df_limpio.shape)

    print("\nFilas duplicadas:")
    print(duplicados)

    print("\nValores nulos clinicos:")
    print(df_limpio[COLUMNAS_CLINICAS].isna().sum())

    print("\nEstado de las fechas:")
    print(df_limpio["estado_fechas"].value_counts())

    print("\nValores invalidos en chest_infection:")
    print(df_limpio["chest_infection"].isna().sum())

    print("\nLIMPIEZA HDHI FINALIZADA")

    return df_limpio


# Ejecucion

if __name__ == "__main__":
    df_limpio = limpiar_hdhi()

    carpeta_procesados = CARPETA_DATOS / "procesados"
    carpeta_procesados.mkdir(parents=True, exist_ok=True)

    ruta_salida = carpeta_procesados / "hdhi_limpio.csv"

    df_limpio.to_csv(
        ruta_salida,
        index=False,
        date_format="%Y-%m-%d"
    )

    print("\nDataset limpio guardado en:")
    print(ruta_salida)
    