from pathlib import Path
import pandas as pd

ruta_csv = Path(__file__).resolve().parents[2] / "HDHI Admission data.csv"

df = pd.read_csv(ruta_csv)

print("DIMENSIONES DEL DATASET:")
print(df.shape)

print("\nCOLUMNAS:")
print(df.columns.tolist())

print("\nPRIMERAS 5 FILAS:")
print(df.head())

print("\nVALORES NULOS:")
print(df.isnull().sum())

print("\nFILAS DUPLICADAS:")
print(df.duplicated().sum())




print("\nTIPOS DE DATOS:")
print(df.dtypes.to_string())

print("\nTIPOS DE INGRESO:")
print(df["TYPE OF ADMISSION-EMERGENCY/OPD"].value_counts(dropna=False))

print("\nRESULTADOS DE INTERNACION:")
print(df["OUTCOME"].value_counts(dropna=False))

print("\nESTADISTICAS DE DURACION DE INTERNACION:")
print(df["DURATION OF STAY"].describe())


print("\nVALORES DE LAS COLUMNAS CLINICAS:")

columnas_clinicas = [
    "HB", "TLC", "PLATELETS", "GLUCOSE",
    "UREA", "CREATININE", "BNP", "EF"
]

for columna in columnas_clinicas:
    valores = pd.to_numeric(df[columna], errors="coerce")
    invalidos = valores.isna() & df[columna].notna()

    print(f"\n{columna}")
    print("Valores no numericos:", invalidos.sum())
    print("Ejemplos:", df.loc[invalidos, columna].unique()[:10])

print("\nFECHAS ORIGINALES:")
print(df[["D.O.A", "D.O.D"]].head(10).to_string(index=False))

print("\nVALORES DE CHEST INFECTION:")
print(df["CHEST INFECTION"].value_counts(dropna=False))