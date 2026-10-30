"""Prepara el acceso de Agente Camas para Neon sin cambiar modelos ni panel.

Ejecutar desde la raíz del proyecto: python preparar_nube_neon.py
No solicita credenciales, no se conecta a Neon y no publica nada.
"""
import argparse
import ast
import base64
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zlib


CONTENIDO = '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'
HUELLAS = '{"backend/app/migrar_cuentas_neon.py": "6279c7e0cf40aee26bef182301abfd6dec1dab66160d9c9f49c674b1a57cf90d", "backend/app/services/acceso.py": "c77affafb9f720ec11e54bb2c3bf96322c7533ed0f83a99141146676c9c15bc4", "backend/app/services/administracion_usuarios.py": "35e8342cd29bdbdbbe7f1270abb0298c167cf62bc070147fcd1d5057d5745be6", "backend/app/services/cuentas_db.py": "463509cee0c25ba9181ab7eb4cd5f2dcb135d8584450498f43b15bdf8b9cdcc8"}'


def leer(ruta):
    # PowerShell puede generar archivos UTF-16 con BOM (por ejemplo requirements.txt).
    # El respaldo conserva los bytes originales; las versiones nuevas se escriben UTF-8.
    contenido = ruta.read_bytes()
    if contenido.startswith((b'\xff\xfe\x00\x00', b'\x00\x00\xfe\xff')):
        codificacion = 'utf-32'
    elif contenido.startswith((b'\xff\xfe', b'\xfe\xff')):
        codificacion = 'utf-16'
    else:
        codificacion = 'utf-8-sig'
    try:
        texto = contenido.decode(codificacion)
    except UnicodeError:
        raise ValueError(
            f'No se pudo leer {ruta.name}. En VS Code guardalo con codificación UTF-8 y repetí. '
            'No se modificó ningún archivo.'
        ) from None
    return texto.replace('\r\n', '\n').replace('\r', '\n')


def nombres(texto):
    arbol = ast.parse(texto)
    return {n.name for n in arbol.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def preparar(raiz):
    requeridos = ('backend/app/main.py', 'backend/app/services/acceso.py',
                  'backend/app/services/administracion_usuarios.py', 'requirements.txt', 'Dockerfile')
    for relativo in requeridos:
        if not (raiz / relativo).is_file():
            raise ValueError(f'Falta {relativo}. Colocá este instalador en la raíz de tu proyecto.')
    if not (raiz / '.git').exists():
        raise ValueError('No se encontró Git. Usá tu proyecto original, en la rama sabrina.')
    resultado = subprocess.run(['git', 'branch', '--show-current'], cwd=raiz,
                              capture_output=True, text=True, check=True)
    if resultado.stdout.strip() != 'sabrina':
        raise ValueError('El proyecto no está en la rama sabrina. Cambiá de rama antes de ejecutar.')
    merge = subprocess.run(['git', 'rev-parse', '--git-path', 'MERGE_HEAD'], cwd=raiz,
                          capture_output=True, text=True, check=True).stdout.strip()
    if (raiz / merge).exists():
        raise ValueError('Hay un merge pendiente. Completalo antes de preparar la nube.')
    payload = json.loads(zlib.decompress(base64.b64decode(CONTENIDO)))
    huellas = json.loads(HUELLAS)
    for nombre, texto in payload.items():
        if hashlib.sha256(texto.encode()).hexdigest() != huellas[nombre]:
            raise ValueError('El instalador está dañado. No se modificó ningún archivo.')
        ast.parse(texto)
    acceso_original = leer(raiz / 'backend/app/services/acceso.py')
    admin_original = leer(raiz / 'backend/app/services/administracion_usuarios.py')
    if 'services.cuentas_db' not in acceso_original:
        esperados = {'ruta_base', 'conexion', 'normalizar_usuario', 'crear_usuario', 'hay_usuarios',
                     'es_administrador', 'asignar_administrador_local', 'DemasiadosIntentos',
                     'autenticar', '_hash_token', 'usuario_de_sesion', 'cerrar_sesion'}
        if nombres(acceso_original) != esperados:
            raise ValueError('acceso.py tiene una estructura distinta a la revisada. No se modificó nada.')
        esperados_admin = {'ConflictoCuenta', '_administrador', '_nombre', '_correo', '_rol', '_auditar',
                          '_cuenta', 'listar', 'crear', 'editar', '_proteger_ultimo', 'cambiar_estado', 'auditoria'}
        if nombres(admin_original) != esperados_admin:
            raise ValueError('administracion_usuarios.py tiene funciones distintas a las revisadas. No se modificó nada.')
    cambios = dict(payload)
    main = leer(raiz / 'backend/app/main.py')
    anterior = 'request.state.usuario = acceso.usuario_de_sesion(request.cookies.get(acceso.COOKIE))'
    nuevo = 'request.state.usuario = await asyncio.to_thread(acceso.usuario_de_sesion, request.cookies.get(acceso.COOKIE))'
    if main.count(anterior) == 1 and 'import asyncio' in main:
        main = main.replace(anterior, nuevo)
    elif main.count(nuevo) != 1:
        raise ValueError('main.py difiere de la versión revisada. No se modificó ningún archivo.')
    ast.parse(main)
    cambios['backend/app/main.py'] = main
    requerimientos = leer(raiz / 'requirements.txt')
    lineas = [l.strip() for l in requerimientos.splitlines() if l.strip() and not l.lstrip().startswith('#')]
    psycopg_actual = [l for l in lineas if l.lower().startswith(('psycopg==', 'psycopg[', 'psycopg>', 'psycopg<', 'psycopg~'))]
    dependencia = 'psycopg[binary]==3.3.6'
    if psycopg_actual and psycopg_actual != [dependencia]:
        raise ValueError('requirements.txt ya define otra versión de psycopg. Revisala antes de instalar.')
    if not psycopg_actual:
        requerimientos = requerimientos.rstrip() + '\n' + dependencia + '\n'
    cambios['requirements.txt'] = requerimientos
    # Los secretos y las bases locales nunca se incorporan a Git ni a la imagen.
    exclusiones = ['.env', '.env.*', '**/.env', '**/.env.*', '**/*.sqlite*', '**/*.db',
                   '**/*.db-wal', '**/*.db-shm', '**/*.db-journal']
    for nombre in ('.gitignore', '.dockerignore'):
        texto = leer(raiz / nombre) if (raiz / nombre).exists() else ''
        faltantes = [l for l in exclusiones if l not in texto.splitlines()]
        if faltantes:
            texto = texto.rstrip() + '\n\n# Credenciales y cuentas locales\n' + '\n'.join(faltantes) + '\n'
        cambios[nombre] = texto
    # No se escribe si alguna ruta nueva contiene otro trabajo.
    for relativo in payload:
        destino = raiz / relativo
        if relativo.endswith(('cuentas_db.py', 'migrar_cuentas_neon.py')) and destino.exists():
            if leer(destino) != payload[relativo]:
                raise ValueError(f'{relativo} ya existe con otro contenido. No se sobrescribió.')
    pendientes = {k: v for k, v in cambios.items()
                  if not (raiz / k).exists() or leer(raiz / k) != v}
    if not pendientes:
        print('La preparación de Neon ya estaba instalada. No se modificó ningún archivo.')
        return
    respaldo = raiz.parent / 'Respaldos_Agente_Camas' / ('neon_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    respaldo.mkdir(parents=True)
    existentes = []
    nuevos = []
    for relativo in pendientes:
        origen = raiz / relativo
        if origen.exists():
            copia = respaldo / relativo
            copia.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origen, copia)
            existentes.append(relativo)
        else:
            nuevos.append(relativo)
    manifiesto = {'raiz': str(raiz), 'existentes': existentes, 'nuevos': nuevos}
    (respaldo / 'restauracion.json').write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        for relativo, contenido in pendientes.items():
            destino = raiz / relativo
            destino.parent.mkdir(parents=True, exist_ok=True)
            temporal = destino.with_name(destino.name + '.neon-temporal')
            temporal.write_text(contenido, encoding='utf-8', newline='\n')
            temporal.replace(destino)
    except BaseException:
        restaurar(raiz, respaldo)
        raise
    print('Preparación de Neon instalada. Todavía no está publicada ni conectada.')
    print('Respaldo fuera del repositorio:', respaldo)
    print('Archivos cambiados:')
    for nombre in pendientes:
        print(' -', nombre)
    print('Se conservaron modelos, CSV, gráficos, cuentas locales y permisos de las rutas.')
    print('Siguiente paso: python -m pip install -r requirements.txt')
    print('Después probaremos el programa local y trasladaremos las cuentas a Neon.')
    print('No pulses Deploy en Render todavía. No se guardaron credenciales.')


def restaurar(raiz, respaldo):
    datos = json.loads((respaldo / 'restauracion.json').read_text(encoding='utf-8'))
    if Path(datos['raiz']).resolve() != raiz:
        raise ValueError('Ese respaldo corresponde a otro proyecto.')
    for relativo in datos['existentes'] + datos['nuevos']:
        destino = (raiz / relativo).resolve()
        if not destino.is_relative_to(raiz):
            raise ValueError('Ruta de respaldo inválida.')
    for relativo in datos['existentes']:
        shutil.copy2(respaldo / relativo, raiz / relativo)
    for relativo in datos['nuevos']:
        (raiz / relativo).unlink(missing_ok=True)
    print('Se restauraron los archivos previos a la preparación de Neon.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restaurar', type=Path)
    args = parser.parse_args()
    raiz = Path(__file__).resolve().parent
    try:
        if args.restaurar:
            restaurar(raiz, args.restaurar.resolve())
        else:
            preparar(raiz)
    except (ValueError, OSError, subprocess.CalledProcessError, SyntaxError) as error:
        print('No se completó la preparación:', error)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
