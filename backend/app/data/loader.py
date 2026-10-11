
from pathlib import Path
import pandas as pd

# Carpeta que contiene los tres datasets originales.
CARPETA_DATOS = Path(__file__).resolve().parents[2] / "data"

# Cargamos los datasets para revisar su estado antes de limpiarlos.
datasets = {
    "HDHI Admission": pd.read_csv(CARPETA_DATOS / "HDHI Admission data.csv"),
    "LengthOfStay": pd.read_csv(CARPETA_DATOS / "LengthOfStay.csv"),
    "Healthcare": pd.read_csv(CARPETA_DATOS / "healthcare_dataset.csv")
}


# Explora la estructura y calidad de cada dataset.
def explorar_dataset(nombre, df):
    print(f"\n===== {nombre.upper()} =====")
    print("Dimensiones:", df.shape)
    print("Columnas:", df.columns.tolist())
    print("\nPrimeras 5 filas:\n", df.head().to_string(index=False))
    print("\nValores nulos:\n", df.isnull().sum().to_string())
    print("\nFilas duplicadas:", df.duplicated().sum())
    print("\nTipos de datos:\n", df.dtypes.to_string())


# Ejecuta la exploracion general de los tres archivos.
for nombre, df in datasets.items():
    explorar_dataset(nombre, df)


# Revisa aspectos particulares del dataset HDHI.
df_hdhi = datasets["HDHI Admission"]

print("\n===== REVISION ESPECIFICA HDHI =====")

# Analiza los tipos de ingreso y resultados de internacion.
for columna in ["TYPE OF ADMISSION-EMERGENCY/OPD", "OUTCOME",
                "CHEST INFECTION"]:
    print(f"\n{columna}:\n", df_hdhi[columna].value_counts(dropna=False))

# Revisa la distribucion de la duracion de internacion.
print("\nDuracion de internacion:")
print(df_hdhi["DURATION OF STAY"].describe())

# Detecta valores no numericos en columnas clinicas.
columnas_clinicas = [
    "HB", "TLC", "PLATELETS", "GLUCOSE",
    "UREA", "CREATININE", "BNP", "EF"
]

for columna in columnas_clinicas:
    valores = pd.to_numeric(df_hdhi[columna], errors="coerce")
    invalidos = valores.isna() & df_hdhi[columna].notna()

    print(f"\n{columna} - No numericos:", invalidos.sum())

    if invalidos.any():
        print("Ejemplos:", df_hdhi.loc[invalidos, columna].unique()[:10])

# Muestra ejemplos de fechas para revisar su formato original.
print("\nFechas originales:")
print(df_hdhi[["D.O.A", "D.O.D"]].head(10).to_string(index=False))

print("\nEXPLORACION FINALIZADA")
