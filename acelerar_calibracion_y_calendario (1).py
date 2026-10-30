"""Acelera la calibracion historica y actualiza el calendario sin cerrarlo.

Ejecutar desde la raiz: python acelerar_calibracion_y_calendario.py
No solicita claves ni se conecta a Render o Neon.
"""
import ast
import base64
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zlib

PAQUETE = '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'


def leer(ruta):
    contenido = ruta.read_bytes()
    if contenido.startswith((b'\xff\xfe\x00\x00', b'\x00\x00\xfe\xff')):
        texto = contenido.decode('utf-32')
    elif contenido.startswith((b'\xff\xfe', b'\xfe\xff')):
        texto = contenido.decode('utf-16')
    else:
        texto = contenido.decode('utf-8-sig')
    return texto.replace('\r\n', '\n')


def escribir(ruta, contenido):
    with tempfile.NamedTemporaryFile(dir=ruta.parent, delete=False) as archivo:
        temporal = Path(archivo.name)
        archivo.write(contenido)
    try:
        temporal.replace(ruta)
    finally:
        temporal.unlink(missing_ok=True)


def main():
    datos = json.loads(zlib.decompress(base64.b64decode(PAQUETE)))
    raiz = Path(__file__).resolve().parent
    pendientes = []
    for relativo, cambios in datos['parches'].items():
        ruta = raiz / relativo
        if not ruta.is_file():
            raise ValueError(f'Falta {relativo}. Coloca el instalador en la raiz y aplica primero la optimizacion anterior.')
        actual = leer(ruta)
        marcador = '// CALIBRACION_Y_CALENDARIO_V2' if relativo.endswith('.js') else '# CALIBRACION_Y_CALENDARIO_V2'
        if marcador in actual:
            if not all(nuevo in actual for _, nuevo in cambios):
                raise ValueError(f'La correccion de {relativo} tiene cambios posteriores; adjuntalo para revisarlo.')
            continue
        esperado = datos['huellas'].get(relativo)
        if esperado and hashlib.sha256(actual.encode()).hexdigest() != esperado:
            raise ValueError(f'Version distinta en {relativo}. No se modifico ningun archivo. Adjuntalo para adaptar la correccion.')
        if relativo.endswith('/modelo_ocupacion.py'):
            # Python 3.12 agrega type_params=[]; Python 3.11 no lo incluye.
            # Se normaliza solo ese campo vacio y se conservan los demas controles.
            nodos = {n.name:ast.dump(n).replace(', type_params=[]', '') for n in ast.parse(actual).body if isinstance(n,ast.FunctionDef)}
            for nombre, esperado_ast in datos['funciones_modelo'].items():
                if nodos.get(nombre) != esperado_ast.replace(', type_params=[]', ''):
                    raise ValueError(f'El modelo de ocupacion tiene cambios en {nombre}. No se modifico ningun archivo.')
        nuevo = actual
        for antes, despues in cambios:
            if nuevo.count(antes) != 1:
                raise ValueError(f'No coincide un bloque de {relativo}. No se modifico ningun archivo.')
            nuevo = nuevo.replace(antes, despues, 1)
        nuevo = nuevo.rstrip() + '\n\n' + marcador + '\n'
        if relativo.endswith('.py'):
            ast.parse(nuevo, filename=relativo)
        pendientes.append((relativo,ruta,nuevo))
    if not pendientes:
        print('La correccion ya esta instalada. No se modificaron archivos.')
        return
    respaldo = raiz.parent / 'Respaldos_Agente_Camas' / ('calibracion_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    originales = {}
    for relativo,ruta,_ in pendientes:
        originales[relativo] = ruta.read_bytes()
        destino = respaldo / relativo
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ruta,destino)
    escritos = []
    try:
        for relativo,ruta,nuevo in pendientes:
            escritos.append((relativo,ruta))
            escribir(ruta,nuevo.encode('utf-8'))
    except BaseException:
        for relativo,ruta in reversed(escritos):
            escribir(ruta,originales[relativo])
        raise
    print('Correccion instalada: reutilizacion de ajustes historicos y variables de ocupacion.')
    print('Se conservan los 26 origenes, metodos, horizontes, formulas y cortes temporales.')
    print('Matrices numericas limitadas a un hilo BLAS para evitar sobrecarga en estos calculos.')
    print('Calendario: permanece abierto, indica el calculo y se actualiza automaticamente.')
    print('Las consultas anteriores se cancelan en el navegador al elegir otra fecha; esto no detiene un calculo ya iniciado en el servidor.')
    print('Si la consulta supera 3 minutos, se muestra un error en vez de esperar indefinidamente.')
    print('No se modificaron cuentas, permisos, Administracion, datasets ni exportacion Excel.')
    print('Archivos cambiados:')
    for relativo,_,_ in pendientes:
        print(' - '+relativo)
    print('Respaldo: '+str(respaldo))
    print('Reinicia Uvicorn y proba. La mejora real en Render se medira despues de subir y desplegar.')
    print('Logs de Render: Calculo iniciado / terminado, con tiempo en segundos.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('No se completo la instalacion: '+str(error))
        raise SystemExit(1)
