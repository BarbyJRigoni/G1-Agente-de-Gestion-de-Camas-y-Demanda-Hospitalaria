"""Conecta la tabla de episodios revisados al backend con respaldo automatico.
Guardar en la carpeta principal del proyecto y ejecutar:
python integrar_revision_hdhi.py

Modifica SOLO cargar_datos() de services/analisis.py y cuatro funciones
de services/analisis_hdhi.py. Conserva los CSV y los otros datasets.
No corrige todavia la validacion temporal del modelo de prediccion.
"""
from pathlib import Path
import ast
import datetime
import shutil
import subprocess
import sys
import textwrap

CARGAR = '''
def cargar_datos(nombre):
    # HDHI_EPISODIOS_REVISION_V1: fuente comun para censo, ingresos y ALOS.
    if nombre == "hdhi":
        ruta = (CARPETA_PROCESADOS / "revision_hdhi" / "episodios"
                / "hdhi_episodios_candidatos.csv")
        if not ruta.is_file():
            raise ValueError(
                "Falta la tabla de episodios de HDHI. Ejecute "
                "python backend/app/data/preparar_episodios_hdhi.py")
        df = pd.read_csv(ruta, low_memory=False)
        necesarias = ["id_episodio", "mrd_no", "fecha_ingreso",
                      "fecha_egreso", "duration_of_stay"]
        if any(c not in df for c in necesarias):
            raise ValueError("La tabla de episodios de HDHI esta incompleta.")
        if df.empty or df["id_episodio"].isna().any():
            raise ValueError("HDHI no contiene episodios identificados.")
        if df["id_episodio"].duplicated().any() or df.duplicated(
                ["mrd_no", "fecha_ingreso", "fecha_egreso"]).any():
            raise ValueError("HDHI contiene episodios repetidos.")
        ingreso = pd.to_datetime(df["fecha_ingreso"], format="%Y-%m-%d", errors="coerce")
        egreso = pd.to_datetime(df["fecha_egreso"], format="%Y-%m-%d", errors="coerce")
        duracion = pd.to_numeric(df["duration_of_stay"], errors="coerce")
        if (ingreso.isna().any() or egreso.isna().any()
                or duracion.isna().any() or (duracion <= 0).any()
                or (egreso < ingreso).any()
                or ((egreso - ingreso).dt.days + 1 != duracion).any()):
            raise ValueError("HDHI contiene fechas o duraciones incoherentes.")
        return df
    return pd.read_csv(CARPETA_PROCESADOS / f"{nombre}_limpio.csv")
'''

PREPARAR = '''
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
'''

PATOLOGIA = '''
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
'''

EDADES = '''
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
'''

INDICADORES = '''
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
'''


def reemplazar_funciones(texto, cambios, archivo):
    arbol = ast.parse(texto, filename=archivo)
    funciones = {n.name: n for n in arbol.body if isinstance(n, ast.FunctionDef)}
    faltan = set(cambios) - set(funciones)
    if faltan:
        raise ValueError(f"{archivo}: faltan funciones esperadas: {sorted(faltan)}")
    lineas = texto.splitlines(keepends=True)
    for nombre in sorted(cambios, key=lambda n: funciones[n].lineno, reverse=True):
        nodo = funciones[nombre]
        if nodo.decorator_list:
            raise ValueError(f"{archivo}: {nombre} tiene decoradores inesperados.")
        lineas[nodo.lineno - 1:nodo.end_lineno] = [
            textwrap.dedent(cambios[nombre]).strip() + "\n"]
    resultado = "".join(lineas)
    compile(resultado, archivo, "exec")
    return resultado


def preparar_cambios(raiz):
    servicios = raiz / "backend" / "app" / "services"
    cambios = {}
    for archivo, funciones in [
        ("analisis.py", {"cargar_datos": CARGAR}),
        ("analisis_hdhi.py", {
            "_preparar_datos": PREPARAR,
            "calcular_alos_hdhi_por_patologia": PATOLOGIA,
            "calcular_alos_hdhi_por_grupo_etario": EDADES,
            "obtener_indicadores_hdhi": INDICADORES,
        }),
    ]:
        ruta = servicios / archivo
        texto = ruta.read_text(encoding="utf-8-sig")
        nuevo = reemplazar_funciones(texto, funciones, str(ruta))
        if archivo == "analisis_hdhi.py":
            nuevo = nuevo.replace(
                "la estancia a noches ni excluye registros por el estado de sus fechas.",
                "la estancia a noches. La carga comun selecciona los episodios revisados.")
            nuevo = nuevo.replace(
                "Los ocho indicadores analizados admiten 0 (ausencia) y 1 (presencia).",
                "Los indicadores admiten 0 (ausencia), 1 (presencia) y faltantes (desconocidos).")
        cambios[ruta] = nuevo
    return cambios


def main():
    raiz = Path.cwd()
    if not (raiz / "backend" / "app" / "services").is_dir():
        raise ValueError("Ejecute este script desde la carpeta principal del proyecto.")
    rama = subprocess.run(
        ["git", "branch", "--show-current"], cwd=raiz,
        capture_output=True, text=True, check=True).stdout.strip()
    if rama != "prueba-sabrina":
        raise ValueError(f"Rama actual: {rama}. Este cambio esta preparado para prueba-sabrina.")
    csv = raiz / "backend/data/procesados/revision_hdhi/episodios/hdhi_episodios_candidatos.csv"
    if not csv.is_file():
        raise ValueError("Primero ejecute preparar_episodios_hdhi.py.")
    cambios = preparar_cambios(raiz)
    # Validar la carga y el JSON antes de escribir ningun modulo.
    import pandas as pd
    import json
    from math import isfinite
    analisis = raiz / "backend/app/services/analisis.py"
    hdhi = raiz / "backend/app/services/analisis_hdhi.py"
    ns = {"__file__": str(analisis), "__name__": "validacion_analisis"}
    exec(compile(cambios[analisis], str(analisis), "exec"), ns)
    datos = ns["cargar_datos"]("hdhi")
    hs = {"__file__": str(hdhi), "__name__": "validacion_hdhi"}
    exec(compile(cambios[hdhi], str(hdhi), "exec"), hs)
    indicadores = hs["obtener_indicadores_hdhi"](datos)
    json.dumps(indicadores, allow_nan=False)
    if sum(x["cantidad_internaciones"] for x in indicadores["grupos_etarios"]) + indicadores[
            "cantidad_sin_grupo_etario"] != len(datos):
        raise ValueError("No coincide el total de episodios por edad.")
    respaldo = raiz / ("respaldo_integracion_hdhi_" +
                       datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    respaldo.mkdir()
    for ruta in cambios:
        destino = respaldo / ruta.relative_to(raiz)
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ruta, destino)
    try:
        for ruta, contenido in cambios.items():
            ruta.write_text(contenido, encoding="utf-8")
    except Exception:
        for ruta in cambios:
            shutil.copy2(respaldo / ruta.relative_to(raiz), ruta)
        raise
    print("Carga compartida de HDHI actualizada.")
    print("Episodios:", len(datos))
    print("ALOS:", indicadores["alos_general_dias"])
    print("Diagnosticos desconocidos:",
          {x["columna"]: x["cantidad_sin_dato"] for x in indicadores["patologias"]})
    print("Respaldo:", respaldo)
    print("Se conservaron CSV originales, capacidad y otros datasets.")
    print("Detenga el servidor con Ctrl+C e inicielo de nuevo para vaciar las caches.")
    print("Pendiente: corregir validacion temporal del modelo y repetir pruebas de la API.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"No se completo la integracion: {error}", file=sys.stderr)
        sys.exit(1)
