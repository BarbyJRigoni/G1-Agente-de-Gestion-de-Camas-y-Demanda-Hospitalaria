"""Copia cuentas y auditoría de SQLite a una PostgreSQL vacía, sin sesiones.

Se ejecuta en la computadora que ya tiene las cuentas. Pide la dirección de
Neon sin mostrarla y no la guarda. Conserva los hashes existentes: no necesita
conocer, pedir ni cambiar las contraseñas de los usuarios.
"""
import argparse
from getpass import getpass
import os
from pathlib import Path
import sqlite3
from services import acceso
from services.cuentas_db import usa_postgres

CAMPOS = ('usuario', 'sal', 'derivada', 'iteraciones', 'correo', 'rol', 'nombre_completo', 'activo')


def migrar(origen):
    if not usa_postgres():
        raise ValueError('Falta configurar la conexión de destino PostgreSQL.')
    if not origen.is_file():
        raise ValueError('No se encontró la base local de cuentas. No se cambió ninguna cuenta.')
    # mode=ro impide crear una base vacía por error o modificar la existente.
    with sqlite3.connect(origen.resolve().as_uri() + '?mode=ro', uri=True) as fuente:
        fuente.row_factory = sqlite3.Row
        fuente.execute('BEGIN')
        usuarios = [dict(f) for f in fuente.execute('SELECT * FROM usuarios')]
        tablas = {f[0] for f in fuente.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        eventos = ([dict(f) for f in fuente.execute('SELECT * FROM auditoria_usuarios ORDER BY id')]
                   if 'auditoria_usuarios' in tablas else [])
    if not usuarios:
        raise ValueError('La base local no tiene usuarios para trasladar.')
    if not any(u.get('rol') == 'administrador' and u.get('activo', 1) for u in usuarios):
        raise ValueError('Primero asigná un administrador activo en tu aplicación local.')
    with acceso.conexion(escritura=True) as db:
        if not db.postgres:
            raise ValueError('El destino debe ser PostgreSQL.')
        cantidades = [db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
                      for t in ('usuarios', 'sesiones', 'intentos', 'auditoria_usuarios')]
        if any(cantidades):
            raise ValueError('El destino ya contiene registros. Se canceló para evitar mezclar o sobrescribir cuentas.')
        for u in usuarios:
            valores = tuple(u.get(c, 'usuario' if c == 'rol' else 1 if c == 'activo' else None) for c in CAMPOS)
            db.execute('''INSERT INTO usuarios(usuario,sal,derivada,iteraciones,correo,rol,nombre_completo,activo)
                          VALUES (?,?,?,?,?,?,?,?)''', valores)
        for e in eventos:
            db.execute('''INSERT INTO auditoria_usuarios(instante,actor,accion,usuario_afectado,cambios)
                          VALUES (?,?,?,?,?)''', tuple(e[c] for c in ('instante', 'actor', 'accion', 'usuario_afectado', 'cambios')))
    return len(usuarios), len(eventos)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origen', type=Path, help='Solo si tus cuentas están en otra ruta SQLite.')
    args = parser.parse_args()
    origen = args.origen or acceso.ruta_base()
    print('Se conservará la base local. Neon debe estar vacía.')
    print('Origen local:', origen)
    url_anterior = os.environ.get('DATABASE_URL')
    try:
        if not url_anterior:
            url = getpass('Pegá la dirección PostgreSQL de Neon (no se mostrará): ').strip()
            if not url:
                print('Operación cancelada.')
                return
            os.environ['DATABASE_URL'] = url
        if input('¿Confirmás copiar cuentas e historial a Neon? Escribí COPIAR: ').strip() != 'COPIAR':
            print('Operación cancelada.')
            return
        usuarios, eventos = migrar(origen)
        print(f'Traslado completado: {usuarios} cuentas y {eventos} eventos.')
        print('Las contraseñas, roles y estados se conservaron. Las sesiones no se trasladaron.')
        print('La base local sigue intacta. Falta probar el acceso en la nube.')
    except (ValueError, sqlite3.Error) as error:
        print('No se completó el traslado:', error)
        raise SystemExit(1) from None
    except Exception:
        # No mostrar excepciones del controlador que puedan incluir datos de conexión.
        print('No se completó el traslado. Revisá la conexión, los permisos y la disponibilidad de Neon.')
        raise SystemExit(1) from None
    finally:
        if url_anterior is None:
            os.environ.pop('DATABASE_URL', None)
        else:
            os.environ['DATABASE_URL'] = url_anterior


if __name__ == '__main__':
    main()
