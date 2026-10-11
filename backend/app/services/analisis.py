
from pathlib import Path
import pandas as pd

# Ubicación de los tres datasets que ya fueron limpiados.
CARPETA_PROCESADOS = Path(__file__).resolve().parents[2] / "data" / "procesados"


# Carga el dataset limpio indicado, sin modificar el archivo original.
def cargar_datos(nombre):
    return pd.read_csv(CARPETA_PROCESADOS / f"{nombre}_limpio.csv")


# Muestra el total de internaciones, estancia promedio y datos principales
# de cada dataset. Los archivos se analizan por separado, sin unir pacientes.
def analizar_dataset(nombre, columna_duracion, columnas_conteo):
    df = cargar_datos(nombre)

    print(f"\n===== ANALISIS {nombre.upper()} =====")
    print("Total de internaciones:", len(df))
    print("Duracion promedio:", round(df[columna_duracion].mean(), 2))

    for titulo, columna in columnas_conteo.items():
        print(f"\n{titulo}:\n{df[columna].value_counts()}")

    return df


# Analiza los ingresos, resultados y estancia hospitalaria de HDHI.
def analizar_hdhi():
    return analizar_dataset(
        "hdhi",
        "duration_of_stay",
        {
            "Tipos de admision": "type_of_admission_emergency_opd",
            "Resultados de internacion": "outcome"
        }
    )


# Analiza la estancia, los establecimientos y los reingresos.
def analizar_lengthofstay():
    return analizar_dataset(
        "lengthofstay",
        "lengthofstay",
        {
            "Internaciones por establecimiento": "facid",
            "Distribucion de reingresos": "rcount"
        }
    )


# Analiza las internaciones, admisiones y patologias de Healthcare.
def analizar_healthcare():
    df = analizar_dataset(
        "healthcare",
        "duracion_internacion",
        {
            "Tipos de admision": "admission_type",
            "Condiciones medicas": "medical_condition"
        }
    )

    print("\nCantidad de hospitales:", df["hospital"].nunique())
    print("\nPrimeros 10 hospitales:\n", df["hospital"].value_counts().head(10))
    return df


# Calcula el ALOS: cantidad de internaciones y promedio de dias de estancia
# agrupados por una columna, como patologia o grupo etario.
def calcular_alos(df, columna):
    return (
        df.groupby(columna, observed=True)["duracion_internacion"]
        .agg(cantidad_internaciones="count", alos_promedio="mean")
        .round(2)
    )


# Calcula el ALOS por enfermedad y ordena de mayor a menor promedio.
def calcular_alos_por_patologia():
    df = cargar_datos("healthcare")
    return calcular_alos(df, "medical_condition").sort_values(
        "alos_promedio", ascending=False
    )


# Agrupa pacientes por edades y calcula el ALOS de cada grupo.
def calcular_alos_por_grupo_etario():
    df = cargar_datos("healthcare")

    df["grupo_etario"] = pd.cut(
        df["age"],
        bins=[0, 18, 30, 45, 60, 75, float("inf")],
        labels=["0-17", "18-29", "30-44", "45-59", "60-74", "75 o mas"],
        right=False
    )

    return calcular_alos(df, "grupo_etario")


# Calcula promedio, desviacion estandar, mediana y percentiles de estancia.
def calcular_estadisticas_estancia():
    dias = cargar_datos("healthcare")["duracion_internacion"]

    return {
        "promedio": round(float(dias.mean()), 2),
        "desviacion_estandar": round(float(dias.std()), 2),
        "mediana": round(float(dias.median()), 2),
        "percentil_25": round(float(dias.quantile(0.25)), 2),
        "percentil_75": round(float(dias.quantile(0.75)), 2),
        "percentil_90": round(float(dias.quantile(0.90)), 2)
    }


# Cuenta los movimientos diarios y completa con cero los dias sin registros.
def calcular_movimientos_diarios(columna_fecha):
    df = cargar_datos("healthcare")
    fechas = pd.to_datetime(df[columna_fecha], errors="coerce")

    movimientos = fechas.value_counts().sort_index()

    calendario = pd.date_range(
        movimientos.index.min(), movimientos.index.max(), freq="D"
    )

    movimientos = movimientos.reindex(calendario, fill_value=0)
    movimientos.index.name = "fecha"
    return movimientos


# Cuenta los pacientes que ingresaron cada dia.
def calcular_ingresos_diarios():
    return calcular_movimientos_diarios("date_of_admission")


# Cuenta los pacientes que egresaron cada dia.
def calcular_egresos_diarios():
    return calcular_movimientos_diarios("discharge_date")


# Calcula la diferencia diaria entre ingresos y egresos y su acumulado.
# El balance acumulado NO equivale a la ocupacion real de camas.
def calcular_balance_diario():
    balance = pd.DataFrame({
        "ingresos": calcular_ingresos_diarios(),
        "egresos": calcular_egresos_diarios()
    }).fillna(0).astype(int)

    balance["balance_diario"] = balance["ingresos"] - balance["egresos"]
    balance["balance_acumulado"] = balance["balance_diario"].cumsum()
    return balance


# Reune los principales indicadores historicos para el agente y FastAPI.
# Estos indicadores corresponden a Healthcare, no a los tres datasets unidos.
def obtener_indicadores_generales():
    estadisticas = calcular_estadisticas_estancia()

    return {
        "total_internaciones": len(cargar_datos("healthcare")),
        "alos_promedio": estadisticas["promedio"],
        "desviacion_estandar": estadisticas["desviacion_estandar"],
        "mediana": estadisticas["mediana"],
        "percentil_25": estadisticas["percentil_25"],
        "percentil_75": estadisticas["percentil_75"],
        "percentil_90": estadisticas["percentil_90"],
        "promedio_ingresos_diarios": round(float(calcular_ingresos_diarios().mean()), 2),
        "promedio_egresos_diarios": round(float(calcular_egresos_diarios().mean()), 2)
    }


# Ejecuta los analisis y muestra resultados para comprobar los calculos.
# Este bloque no se ejecuta cuando otro archivo importa las funciones.
if __name__ == "__main__":
    analizar_hdhi()
    analizar_lengthofstay()
    analizar_healthcare()

    print("\n===== ALOS POR PATOLOGIA =====")
    print(calcular_alos_por_patologia())

    print("\n===== ALOS POR GRUPO ETARIO =====")
    print(calcular_alos_por_grupo_etario())

    print("\n===== ESTADISTICAS DE ESTANCIA =====")
    print(calcular_estadisticas_estancia())

    ingresos = calcular_ingresos_diarios()
    egresos = calcular_egresos_diarios()
    balance = calcular_balance_diario()

    # Muestra los primeros diez dias y sus promedios.
    for nombre, datos in [("INGRESOS", ingresos), ("EGRESOS", egresos)]:
        print(f"\n===== {nombre} DIARIOS =====")
        print(datos.head(10))
        print("Promedio diario:", round(datos.mean(), 2))

    print("\n===== BALANCE DIARIO =====")
    print(balance.head(10))

    # Verifica que todos los ingresos y egresos esten contabilizados.
    print("\n===== VALIDACION DEL BALANCE =====")
    print("Total de ingresos:", balance["ingresos"].sum())
    print("Total de egresos:", balance["egresos"].sum())
    print("Balance acumulado final:", balance["balance_acumulado"].iloc[-1])
    print("Cantidad de dias analizados:", len(balance))

    print("\n===== INDICADORES GENERALES =====")
    print(obtener_indicadores_generales())
