"""Cuentas locales y sesiones opacas. Sin claves predeterminadas ni texto plano.

Usuarios fuera del repositorio; PBKDF2-SHA256; token de sesion aleatorio cuyo
hash se guarda en SQLite. La configuracion de cuentas es una operacion local.
"""
from contextlib import contextmanager
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time

ITERACIONES = 600_000
DURACION_SESION = 8 * 60 * 60
COOKIE = "camas_sesion"
_SAL_FICTICIA = b"validacion-usuario-no-existente"


def ruta_base():
    especifica = os.environ.get("CAMAS_AUTH_DB")
    if especifica:
        return Path(especifica).expanduser().resolve()
    proyecto = Path(__file__).resolve().parents[3]
    identificador = hashlib.sha256(str(proyecto).encode()).hexdigest()[:16]
    carpeta = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share")))
    return carpeta / "AgenteCamas" / identificador / "acceso.sqlite3"

@contextmanager
def conexion():
    ruta = ruta_base()
    ruta.parent.mkdir(parents=True, exist_ok=True)

    try:
        ruta.parent.chmod(0o700)
    except OSError:
        pass

    db = sqlite3.connect(ruta, timeout=10)

    try:
        db.execute("PRAGMA foreign_keys=ON")

        # Crear las tablas si todavía no existen.
        db.executescript("""
          CREATE TABLE IF NOT EXISTS usuarios (
            usuario TEXT PRIMARY KEY,
            sal TEXT NOT NULL,
            derivada TEXT NOT NULL,
            iteraciones INTEGER NOT NULL
          );

          CREATE TABLE IF NOT EXISTS sesiones (
            token_hash TEXT PRIMARY KEY,
            usuario TEXT NOT NULL
                REFERENCES usuarios(usuario) ON DELETE CASCADE,
            vence REAL NOT NULL
          );

          CREATE TABLE IF NOT EXISTS intentos (
            ip TEXT NOT NULL,
            usuario TEXT NOT NULL,
            instante REAL NOT NULL
          );

          CREATE INDEX IF NOT EXISTS intentos_tiempo
          ON intentos(instante);
        """)

        # Serializar la migración para el primer acceso simultáneo.
        db.execute("BEGIN IMMEDIATE")
        # Migración: agregar correo sin eliminar cuentas existentes.
        columnas = {
            fila[1]
            for fila in db.execute("PRAGMA table_info(usuarios)")
        }

        if "correo" not in columnas:
            db.execute(
                "ALTER TABLE usuarios ADD COLUMN correo TEXT"
            )
            # Agregar roles sin eliminar usuarios existentes.
        if "rol" not in columnas:
            db.execute(
                "ALTER TABLE usuarios ADD COLUMN rol TEXT NOT NULL DEFAULT 'usuario'"
            )

        # Ampliación compatible: todas las cuentas existentes siguen habilitadas.
        if "nombre_completo" not in columnas:
            db.execute("ALTER TABLE usuarios ADD COLUMN nombre_completo TEXT")
        if "activo" not in columnas:
            db.execute("ALTER TABLE usuarios ADD COLUMN activo INTEGER NOT NULL DEFAULT 1")
        db.execute("""CREATE TABLE IF NOT EXISTS auditoria_usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instante TEXT NOT NULL, actor TEXT NOT NULL,
            accion TEXT NOT NULL, usuario_afectado TEXT NOT NULL,
            cambios TEXT NOT NULL
        )""")

        # Evitar que dos cuentas tengan el mismo correo.
        db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS usuarios_correo_unico
            ON usuarios(correo)
        """)

        try:
            ruta.chmod(0o600)
        except OSError:
            pass

        db.commit()  # Termina la migración antes de las operaciones de la cuenta.
        yield db
        db.commit()

    finally:
        db.close()

def normalizar_usuario(usuario):
    return usuario.strip().lower()


def crear_usuario(usuario, clave, reemplazar=False, correo=None):
    usuario = normalizar_usuario(usuario)
    if correo is not None:
        correo = correo.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", correo) or len(correo) > 254:
            raise ValueError("Ingresa un correo electronico valido.")
    if not re.fullmatch(r"[a-z0-9._-]{3,40}", usuario):
        raise ValueError("Usuario: entre 3 y 40 letras sin tildes, numeros, puntos, guiones o guion bajo.")
    if not 12 <= len(clave) <= 128:
        raise ValueError("La contrasena debe tener entre 12 y 128 caracteres.")
    sal = secrets.token_bytes(32)
    derivada = hashlib.pbkdf2_hmac("sha256", clave.encode(), sal, ITERACIONES).hex()
    with conexion() as db:
        existe = db.execute("SELECT 1 FROM usuarios WHERE usuario=?", (usuario,)).fetchone()
        if existe and not reemplazar:
            raise ValueError("Ese usuario ya existe. Use --cambiar-clave para renovar su contrasena.")
        if existe:
            db.execute("DELETE FROM sesiones WHERE usuario=?", (usuario,))
            db.execute("DELETE FROM intentos WHERE usuario=?", (usuario,))
            db.execute("UPDATE usuarios SET sal=?, derivada=?, iteraciones=? WHERE usuario=?",
                       (sal.hex(), derivada, ITERACIONES, usuario))
        else:
            db.execute(
                "INSERT INTO usuarios (usuario, sal, derivada, iteraciones, correo) VALUES (?,?,?,?,?)",
                (usuario, sal.hex(), derivada, ITERACIONES, correo)
            )


def hay_usuarios():
    with conexion() as db:
        return db.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone() is not None

def es_administrador(usuario):
    if not usuario:
        return False

    usuario = normalizar_usuario(usuario)

    with conexion() as db:
        fila = db.execute(
            "SELECT rol, activo FROM usuarios WHERE usuario=?",
            (usuario,)
        ).fetchone()

    return bool(fila and fila[0] == "administrador" and fila[1])


def asignar_administrador_local(usuario):
    usuario = normalizar_usuario(usuario)

    with conexion() as db:
        existe = db.execute(
            "SELECT 1 FROM usuarios WHERE usuario=?",
            (usuario,)
        ).fetchone()

        if not existe:
            raise ValueError("El usuario no existe.")

        db.execute(
            "UPDATE usuarios SET rol='administrador' WHERE usuario=?",
            (usuario,)
        )


class DemasiadosIntentos(ValueError):
    pass


def autenticar(usuario, clave, ip, token_anterior=None):
    usuario = normalizar_usuario(usuario)
    ahora = time.time()
    with conexion() as db:
        db.execute("DELETE FROM intentos WHERE instante<?", (ahora - 300,))
        por_ip = db.execute("SELECT count(*) FROM intentos WHERE ip=?", (ip,)).fetchone()[0]
        por_cuenta = db.execute("SELECT count(*) FROM intentos WHERE ip=? AND usuario=?", (ip, usuario)).fetchone()[0]
        if por_ip >= 20 or por_cuenta >= 5:
            raise DemasiadosIntentos("Demasiados intentos. Espere cinco minutos antes de volver a probar.")
        fila = db.execute("SELECT sal,derivada,iteraciones,activo FROM usuarios WHERE usuario=?", (usuario,)).fetchone()
        sal = bytes.fromhex(fila[0]) if fila else _SAL_FICTICIA
        derivada = hashlib.pbkdf2_hmac("sha256", clave.encode(), sal, fila[2] if fila else ITERACIONES).hex()
        correcta = hmac.compare_digest(derivada, fila[1] if fila else "0" * 64)
        if not correcta or not fila or not fila[3]:
            db.execute("INSERT INTO intentos VALUES (?,?,?)", (ip, usuario, ahora))
            return None
        db.execute("DELETE FROM intentos WHERE ip=? AND usuario=?", (ip, usuario))
        db.execute("DELETE FROM sesiones WHERE vence<=?", (ahora,))
        if token_anterior:
            db.execute("DELETE FROM sesiones WHERE token_hash=?", (_hash_token(token_anterior),))
        token = secrets.token_urlsafe(32)
        db.execute("INSERT INTO sesiones VALUES (?,?,?)", (_hash_token(token), usuario, ahora + DURACION_SESION))
        return token, usuario


def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def usuario_de_sesion(token):
    if not token or len(token) > 100:
        return None
    with conexion() as db:
        fila = db.execute("SELECT s.usuario FROM sesiones s JOIN usuarios u ON u.usuario=s.usuario WHERE s.token_hash=? AND s.vence>? AND u.activo=1", (_hash_token(token), time.time())).fetchone()
        return fila[0] if fila else None


def cerrar_sesion(token):
    if token:
        with conexion() as db:
            db.execute("DELETE FROM sesiones WHERE token_hash=?", (_hash_token(token),))
