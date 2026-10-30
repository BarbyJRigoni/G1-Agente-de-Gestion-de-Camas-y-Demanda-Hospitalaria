"""Diagnóstico de Neon con ensayo de traslado y reversión obligatoria.

Colocar junto a backend, frontend y requirements.txt. No guarda la conexión,
no modifica archivos locales y revierte los cambios del ensayo en PostgreSQL.
"""
from contextlib import contextmanager
from getpass import getpass
import importlib
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote, unquote, urlsplit


def mensaje_seguro(error, url):
    """No muestra DSN, contraseñas ni detalles de filas que puedan contener hashes."""
    principal = getattr(getattr(error, 'diag', None), 'message_primary', None)
    texto = str(principal or error)
    texto = texto.replace(url, '[CONEXIÓN OCULTA]')
    try:
        clave = urlsplit(url).password
    except ValueError:
        clave = None
    if clave:
        for valor in sorted({clave, unquote(clave), quote(unquote(clave), safe='')}, key=len, reverse=True):
            if valor:
                texto = texto.replace(valor, '[CLAVE OCULTA]')
    texto = re.sub(r'(?i)(?:postgres(?:ql)?|https?)://[^\s\'\"<>]+', '[CONEXIÓN OCULTA]', texto)
    texto = re.sub(r'(?i)password\s*=\s*(?:\'[^\']*\'|\"[^\"]*\"|\S+)', 'password=[OCULTA]', texto)
    return ' '.join(texto.split())[:1000]


def main():
    raiz = Path(__file__).resolve().parent
    app = raiz / 'backend' / 'app'
    if not (app / 'migrar_cuentas_neon.py').is_file():
        print('Colocá este archivo en la raíz del proyecto, junto a backend y frontend.')
        return 1
    sys.path.insert(0, str(app))
    url = ''
    base = None
    acceso = None
    conexion_anterior = None
    url_anterior = os.environ.get('DATABASE_URL')
    etapa = 'cargar los módulos instalados'
    try:
        import psycopg
        from services import acceso, cuentas_db
        traslado = importlib.import_module('migrar_cuentas_neon')
        print('Controlador PostgreSQL:', psycopg.__version__)
        url = getpass('Pegá la dirección de Neon (no se mostrará): ').strip()
        if urlsplit(url).scheme not in ('postgres', 'postgresql'):
            print('Dirección no válida. Copiá únicamente la dirección que empieza con postgresql://, sin psql ni comillas.')
            return 1
        os.environ['DATABASE_URL'] = url
        etapa = 'conectar con Neon'
        print('1. Probando conexión...')
        opciones = {'connect_timeout': 15, 'application_name': 'camas_diagnostico'}
        if 'sslmode=' not in url:
            opciones['sslmode'] = 'require'
        base = psycopg.connect(url, **opciones)
        print('   Conexión: OK')
        base.execute("SET LOCAL statement_timeout = '25s'")
        base.execute("SET LOCAL lock_timeout = '10s'")
        etapa = 'preparar las tablas y sus índices'
        print('2. Ensayando preparación de tablas (se revertirá)...')
        db = cuentas_db.ConexionCuentas(base, postgres=True)
        cuentas_db._esquema(db)
        print('   Preparación de tablas: OK')
        etapa = 'leer las cuentas locales y ensayar su traslado'
        print('3. Ensayando traslado, sin confirmar cambios...')
        @contextmanager
        def conexion_de_ensayo(escritura=False):
            if escritura:
                db.execute('SELECT pg_advisory_xact_lock(?)', (cuentas_db.BLOQUEO_CUENTAS,))
            yield db
        conexion_anterior = acceso.conexion
        acceso.conexion = conexion_de_ensayo
        usuarios, eventos = traslado.migrar(acceso.ruta_base())
        print(f'   Ensayo: OK ({usuarios} cuentas y {eventos} eventos)')
        print('DIAGNÓSTICO CORRECTO. El ensayo se revertirá; no trasladó cuentas de forma permanente.')
        return 0
    except KeyboardInterrupt:
        print('\nDiagnóstico cancelado.')
        return 1
    except Exception as error:
        print('FALLO EN:', etapa)
        print('Tipo:', type(error).__name__)
        codigo = getattr(error, 'sqlstate', None)
        if codigo:
            print('Código PostgreSQL:', codigo)
        print('Detalle protegido:', mensaje_seguro(error, url) if url else type(error).__name__)
        print('Se revertirán los cambios del ensayo. No se modificó la base local.')
        return 1
    finally:
        if acceso is not None and conexion_anterior is not None:
            acceso.conexion = conexion_anterior
        if base is not None:
            try:
                base.rollback()
            finally:
                base.close()
        if url_anterior is None:
            os.environ.pop('DATABASE_URL', None)
        else:
            os.environ['DATABASE_URL'] = url_anterior


if __name__ == '__main__':
    sys.exit(main())
