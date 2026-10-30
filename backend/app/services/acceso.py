"""Cuentas y sesiones: SQLite local o PostgreSQL en la nube.

Conserva PBKDF2-SHA256, tokens opacos, vencimiento y roles existentes.
Las credenciales se configuran fuera del repositorio.
"""
import hashlib
import hmac
import re
import secrets
import time
import json
from datetime import datetime, timezone
from services.cuentas_db import conexion, ruta_base, ErrorIntegridad

ITERACIONES = 600_000
DURACION_SESION = 8 * 60 * 60
COOKIE = 'camas_sesion'
_SAL_FICTICIA = b'validacion-usuario-no-existente'


def normalizar_usuario(usuario):
    return usuario.strip().lower()


def crear_usuario(usuario, clave, reemplazar=False, correo=None, *, registro_publico=False):
    if registro_publico and reemplazar:
        raise ValueError('El registro público no puede reemplazar cuentas.')
    usuario = normalizar_usuario(usuario)
    if correo is not None:
        correo = correo.strip().lower()
        if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', correo) or len(correo) > 254:
            raise ValueError('Ingresa un correo electronico valido.')
    if not re.fullmatch(r'[a-z0-9._-]{3,40}', usuario):
        raise ValueError('Usuario: entre 3 y 40 letras sin tildes, numeros, puntos, guiones o guion bajo.')
    minimo, maximo = (5, 14) if registro_publico else (12, 128)
    if not minimo <= len(clave) <= maximo:
        raise ValueError(f'La contraseña debe tener entre {minimo} y {maximo} caracteres.')
    sal = secrets.token_bytes(32)
    derivada = hashlib.pbkdf2_hmac('sha256', clave.encode(), sal, ITERACIONES).hex()
    with conexion(escritura=True) as db:
        existe = db.execute('SELECT 1 FROM usuarios WHERE usuario=?', (usuario,)).fetchone()
        if existe and not reemplazar:
            raise ValueError('Ese usuario ya existe. Use --cambiar-clave para renovar su contrasena.')
        if existe:
            db.execute('DELETE FROM sesiones WHERE usuario=?', (usuario,))
            db.execute('DELETE FROM intentos WHERE usuario=?', (usuario,))
            db.execute('UPDATE usuarios SET sal=?, derivada=?, iteraciones=? WHERE usuario=?',
                       (sal.hex(), derivada, ITERACIONES, usuario))
        else:
            db.execute("INSERT INTO usuarios(usuario,sal,derivada,iteraciones,correo,rol,activo) VALUES (?,?,?,?,?,'usuario',1)",
                       (usuario, sal.hex(), derivada, ITERACIONES, correo))
            if registro_publico:
                db.execute('INSERT INTO auditoria_usuarios(instante,actor,accion,usuario_afectado,cambios) VALUES (?,?,?,?,?)',
                           (datetime.now(timezone.utc).isoformat(timespec='seconds'), usuario, 'crear', usuario,
                            json.dumps({'rol': 'usuario', 'activo': True, 'origen': 'Registro público'}, ensure_ascii=False)))


def hay_usuarios():
    with conexion() as db:
        return db.execute('SELECT 1 FROM usuarios LIMIT 1').fetchone() is not None


def es_administrador(usuario):
    if not usuario:
        return False
    with conexion() as db:
        fila = db.execute('SELECT rol,activo FROM usuarios WHERE usuario=?',
                          (normalizar_usuario(usuario),)).fetchone()
    return bool(fila and fila[0] == 'administrador' and fila[1])


def asignar_administrador_local(usuario):
    usuario = normalizar_usuario(usuario)
    with conexion(escritura=True) as db:
        if not db.execute('SELECT 1 FROM usuarios WHERE usuario=?', (usuario,)).fetchone():
            raise ValueError('El usuario no existe.')
        db.execute("UPDATE usuarios SET rol='administrador' WHERE usuario=?", (usuario,))


class DemasiadosIntentos(ValueError):
    pass


def autenticar(usuario, clave, ip, token_anterior=None):
    usuario = normalizar_usuario(usuario)
    ahora = time.time()
    with conexion(escritura=True) as db:
        db.execute('DELETE FROM intentos WHERE instante<?', (ahora - 300,))
        por_ip = db.execute('SELECT COUNT(*) FROM intentos WHERE ip=?', (ip,)).fetchone()[0]
        por_cuenta = db.execute('SELECT COUNT(*) FROM intentos WHERE ip=? AND usuario=?',
                                (ip, usuario)).fetchone()[0]
        if por_ip >= 20 or por_cuenta >= 5:
            raise DemasiadosIntentos('Demasiados intentos. Espere cinco minutos antes de volver a probar.')
        fila = db.execute('SELECT sal,derivada,iteraciones,activo FROM usuarios WHERE usuario=?',
                          (usuario,)).fetchone()
        sal = bytes.fromhex(fila[0]) if fila else _SAL_FICTICIA
        derivada = hashlib.pbkdf2_hmac('sha256', clave.encode(), sal,
                                     fila[2] if fila else ITERACIONES).hex()
        correcta = hmac.compare_digest(derivada, fila[1] if fila else '0' * 64)
        if not correcta or not fila or not fila[3]:
            db.execute('INSERT INTO intentos(ip,usuario,instante) VALUES (?,?,?)', (ip, usuario, ahora))
            return None
        db.execute('DELETE FROM intentos WHERE ip=? AND usuario=?', (ip, usuario))
        db.execute('DELETE FROM sesiones WHERE vence<=?', (ahora,))
        if token_anterior:
            db.execute('DELETE FROM sesiones WHERE token_hash=?', (_hash_token(token_anterior),))
        token = secrets.token_urlsafe(32)
        db.execute('INSERT INTO sesiones(token_hash,usuario,vence) VALUES (?,?,?)',
                   (_hash_token(token), usuario, ahora + DURACION_SESION))
        return token, usuario


def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def usuario_de_sesion(token):
    if not token or len(token) > 100:
        return None
    with conexion() as db:
        fila = db.execute('''SELECT s.usuario FROM sesiones s JOIN usuarios u ON u.usuario=s.usuario
            WHERE s.token_hash=? AND s.vence>? AND u.activo=1''',
                          (_hash_token(token), time.time())).fetchone()
    return fila[0] if fila else None


def cerrar_sesion(token):
    if token:
        with conexion(escritura=True) as db:
            db.execute('DELETE FROM sesiones WHERE token_hash=?', (_hash_token(token),))
