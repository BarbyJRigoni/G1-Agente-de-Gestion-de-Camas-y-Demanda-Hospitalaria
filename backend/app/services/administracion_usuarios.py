"""Administración de cuentas y auditoría, compatible con SQLite y PostgreSQL.

Las escrituras y la revisión de permisos comparten una transacción serializada.
No elimina cuentas ni devuelve contraseñas o sus hashes.
"""
from datetime import datetime, timezone
import hashlib
import json
import re
import secrets
from services import acceso


class ConflictoCuenta(ValueError):
    pass


def _administrador(db, actor):
    fila = db.execute('SELECT rol,activo FROM usuarios WHERE usuario=?', (actor,)).fetchone()
    if not fila or fila[0] != 'administrador' or not fila[1]:
        raise PermissionError('No tenés permisos de administrador.')


def _nombre(valor):
    valor = ' '.join(valor.split())
    if not 2 <= len(valor) <= 120:
        raise ValueError('El nombre completo debe tener entre 2 y 120 caracteres.')
    return valor


def _correo(valor):
    valor = valor.strip().lower()
    if len(valor) > 254 or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', valor):
        raise ValueError('Ingresá un correo electrónico válido.')
    return valor


def _rol(valor):
    if valor not in ('usuario', 'administrador'):
        raise ValueError('El rol debe ser usuario o administrador.')
    return valor


def _auditar(db, actor, accion, usuario, cambios):
    db.execute('INSERT INTO auditoria_usuarios(instante,actor,accion,usuario_afectado,cambios) VALUES (?,?,?,?,?)',
               (datetime.now(timezone.utc).isoformat(timespec='seconds'), actor, accion, usuario,
                json.dumps(cambios, ensure_ascii=False)))


def _cuenta(db, usuario):
    fila = db.execute('SELECT usuario,correo,rol,nombre_completo,activo FROM usuarios WHERE usuario=?',
                      (usuario,)).fetchone()
    if not fila:
        raise LookupError('La cuenta no existe.')
    return dict(zip(('usuario', 'correo', 'rol', 'nombre_completo', 'activo'), fila))


def listar(actor):
    with acceso.conexion() as db:
        _administrador(db, actor)
        filas = db.execute('SELECT usuario,correo,rol,nombre_completo,activo FROM usuarios ORDER BY usuario').fetchall()
    usuarios = [dict(zip(('usuario', 'correo', 'rol', 'nombre_completo', 'activo'), f)) for f in filas]
    for u in usuarios:
        u['activo'] = bool(u['activo'])
    activos = sum(u['activo'] for u in usuarios)
    return {'usuarios': usuarios, 'resumen': {'total': len(usuarios), 'activos': activos,
            'inactivos': len(usuarios) - activos}, 'usuario_actual': actor}


def crear(actor, usuario, nombre_completo, correo, rol, clave):
    usuario = acceso.normalizar_usuario(usuario)
    if not re.fullmatch(r'[a-z0-9._-]{3,40}', usuario):
        raise ValueError('Usuario: de 3 a 40 letras sin tildes, números, puntos o guiones.')
    nombre_completo, correo, rol = _nombre(nombre_completo), _correo(correo), _rol(rol)
    if not 12 <= len(clave) <= 128:
        raise ValueError('La contraseña debe tener entre 12 y 128 caracteres.')
    sal = secrets.token_bytes(32)
    derivada = hashlib.pbkdf2_hmac('sha256', clave.encode(), sal, acceso.ITERACIONES).hex()
    try:
        with acceso.conexion(escritura=True) as db:
            _administrador(db, actor)
            db.execute('INSERT INTO usuarios(usuario,sal,derivada,iteraciones,correo,rol,nombre_completo,activo) VALUES (?,?,?,?,?,?,?,1)',
                       (usuario, sal.hex(), derivada, acceso.ITERACIONES, correo, rol, nombre_completo))
            _auditar(db, actor, 'crear', usuario, {'nombre_completo': nombre_completo,
                     'correo': correo, 'rol': rol, 'activo': True})
    except acceso.ErrorIntegridad:
        raise ConflictoCuenta('El usuario o el correo ya están registrados.') from None
    return {'mensaje': 'Cuenta creada correctamente.'}


def editar(actor, usuario, nombre_completo, correo, rol):
    nombre_completo, correo, rol = _nombre(nombre_completo), _correo(correo), _rol(rol)
    try:
        with acceso.conexion(escritura=True) as db:
            _administrador(db, actor)
            anterior = _cuenta(db, usuario)
            if rol != anterior['rol']:
                if usuario == actor:
                    raise ConflictoCuenta('No podés cambiar tu propio rol desde este panel.')
                if anterior['rol'] == 'administrador' and anterior['activo']:
                    _proteger_ultimo(db)
            nuevos = {'nombre_completo': nombre_completo, 'correo': correo, 'rol': rol}
            cambios = {k: {'antes': anterior[k], 'despues': v}
                       for k, v in nuevos.items() if anterior[k] != v}
            if cambios:
                db.execute('UPDATE usuarios SET nombre_completo=?,correo=?,rol=? WHERE usuario=?',
                           (nombre_completo, correo, rol, usuario))
                if rol != anterior['rol']:
                    db.execute('DELETE FROM sesiones WHERE usuario=?', (usuario,))
                _auditar(db, actor, 'editar', usuario, cambios)
    except acceso.ErrorIntegridad:
        raise ConflictoCuenta('Ese correo ya está registrado.') from None
    return {'mensaje': 'Cuenta actualizada.'}


def _proteger_ultimo(db):
    cantidad = db.execute("SELECT COUNT(*) FROM usuarios WHERE rol='administrador' AND activo=1").fetchone()[0]
    if cantidad <= 1:
        raise ConflictoCuenta('Debe quedar al menos un administrador activo.')


def cambiar_estado(actor, usuario, activo):
    with acceso.conexion(escritura=True) as db:
        _administrador(db, actor)
        anterior = _cuenta(db, usuario)
        if not activo:
            if usuario == actor:
                raise ConflictoCuenta('No podés desactivar tu propia cuenta.')
            if anterior['rol'] == 'administrador' and anterior['activo']:
                _proteger_ultimo(db)
        if bool(anterior['activo']) != activo:
            db.execute('UPDATE usuarios SET activo=? WHERE usuario=?', (int(activo), usuario))
            db.execute('DELETE FROM sesiones WHERE usuario=?', (usuario,))
            _auditar(db, actor, 'reactivar' if activo else 'desactivar', usuario,
                     {'activo': {'antes': bool(anterior['activo']), 'despues': activo}})
    return {'mensaje': 'Cuenta reactivada.' if activo else 'Cuenta desactivada; sesiones revocadas.'}


def auditoria(actor, limite=100):
    with acceso.conexion() as db:
        _administrador(db, actor)
        filas = db.execute('SELECT id,instante,actor,accion,usuario_afectado,cambios FROM auditoria_usuarios ORDER BY id DESC LIMIT ?',
                           (limite,)).fetchall()
    return {'eventos': [{'id': f[0], 'instante': f[1], 'actor': f[2], 'accion': f[3],
                        'usuario_afectado': f[4], 'cambios': json.loads(f[5])} for f in filas]}
