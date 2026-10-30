"""Persistencia de cuentas: SQLite local o PostgreSQL mediante DATABASE_URL.

El SQL de cuentas usa ? para sus parámetros. Únicamente este módulo lo adapta
al marcador %s de psycopg; los valores siempre se envían separados del SQL.
No contiene credenciales ni modifica los datasets hospitalarios.
"""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import sqlite3
import threading
from urllib.parse import urlsplit

ErrorIntegridad = sqlite3.IntegrityError
_candado = threading.Lock()
_inicializadas = set()
BLOQUEO_ESQUEMA = 831640701
BLOQUEO_CUENTAS = 831640702


def ruta_base():
    especifica = os.environ.get('CAMAS_AUTH_DB')
    if especifica:
        return Path(especifica).expanduser().resolve()
    proyecto = Path(__file__).resolve().parents[3]
    identificador = hashlib.sha256(str(proyecto).encode()).hexdigest()[:16]
    carpeta = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local' / 'share')))
    return carpeta / 'AgenteCamas' / identificador / 'acceso.sqlite3'


def usa_postgres():
    return bool(os.environ.get('DATABASE_URL', '').strip())


class ConexionCuentas:
    def __init__(self, base, postgres=False):
        self.base = base
        self.postgres = postgres

    def execute(self, sql, parametros=()):
        if self.postgres:
            import psycopg
            try:
                return self.base.execute(sql.replace('?', '%s'), parametros)
            except psycopg.IntegrityError:
                # Mantiene compatibilidad con módulos que capturan sqlite3.IntegrityError.
                raise ErrorIntegridad('Restricción de integridad de cuentas.') from None
        return self.base.execute(sql, parametros)


def _esquema(db):
    if db.postgres:
        db.execute('SELECT pg_advisory_xact_lock(?)', (BLOQUEO_ESQUEMA,))
    tablas = [
        '''CREATE TABLE IF NOT EXISTS usuarios (
            usuario TEXT PRIMARY KEY, sal TEXT NOT NULL, derivada TEXT NOT NULL,
            iteraciones INTEGER NOT NULL, correo TEXT,
            rol TEXT NOT NULL DEFAULT 'usuario', nombre_completo TEXT,
            activo INTEGER NOT NULL DEFAULT 1)''',
        '''CREATE TABLE IF NOT EXISTS sesiones (
            token_hash TEXT PRIMARY KEY,
            usuario TEXT NOT NULL REFERENCES usuarios(usuario) ON DELETE CASCADE,
            vence DOUBLE PRECISION NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS intentos (
            ip TEXT NOT NULL, usuario TEXT NOT NULL, instante DOUBLE PRECISION NOT NULL)''',
    ]
    for sql in tablas:
        db.execute(sql)
    if db.postgres:
        for sql in (
            'ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS correo TEXT',
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS rol TEXT NOT NULL DEFAULT 'usuario'",
            'ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nombre_completo TEXT',
            'ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS activo INTEGER NOT NULL DEFAULT 1',
        ):
            db.execute(sql)
        identificador = 'BIGSERIAL PRIMARY KEY'
    else:
        columnas = {f[1] for f in db.execute('PRAGMA table_info(usuarios)')}
        for nombre, tipo in (
            ('correo', 'TEXT'), ('rol', "TEXT NOT NULL DEFAULT 'usuario'"),
            ('nombre_completo', 'TEXT'), ('activo', 'INTEGER NOT NULL DEFAULT 1'),
        ):
            if nombre not in columnas:
                db.execute(f'ALTER TABLE usuarios ADD COLUMN {nombre} {tipo}')
        identificador = 'INTEGER PRIMARY KEY AUTOINCREMENT'
    db.execute(f'''CREATE TABLE IF NOT EXISTS auditoria_usuarios (
        id {identificador}, instante TEXT NOT NULL, actor TEXT NOT NULL,
        accion TEXT NOT NULL, usuario_afectado TEXT NOT NULL, cambios TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS intentos_registro (
        ip TEXT NOT NULL, instante DOUBLE PRECISION NOT NULL)''')
    db.execute('CREATE INDEX IF NOT EXISTS intentos_registro_tiempo ON intentos_registro(instante)')
    db.execute('CREATE INDEX IF NOT EXISTS intentos_tiempo ON intentos(instante)')
    db.execute('CREATE UNIQUE INDEX IF NOT EXISTS usuarios_correo_unico ON usuarios(correo)')


@contextmanager
def conexion(escritura=False):
    url = os.environ.get('DATABASE_URL', '').strip()
    postgres = bool(url)
    ruta = None
    if postgres:
        if urlsplit(url).scheme not in ('postgres', 'postgresql'):
            raise ValueError('DATABASE_URL debe ser una dirección PostgreSQL.')
        import psycopg
        opciones = {'connect_timeout': 15, 'application_name': 'agente_camas'}
        # Neon conserva además los parámetros SSL originales de su dirección.
        if 'sslmode=' not in url:
            opciones['sslmode'] = 'require'
        base = psycopg.connect(url, **opciones)
        clave = ('postgres', hashlib.sha256(url.encode()).hexdigest())
    else:
        ruta = ruta_base()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        try:
            ruta.parent.chmod(0o700)
        except OSError:
            pass
        if not ruta.exists():
            _inicializadas.discard(('sqlite', str(ruta)))
        base = sqlite3.connect(ruta, timeout=15)
        base.execute('PRAGMA foreign_keys=ON')
        clave = ('sqlite', str(ruta))
    db = ConexionCuentas(base, postgres)
    try:
        # DDL una vez por proceso, con bloqueo entre procesos durante la migración.
        with _candado:
            if clave not in _inicializadas:
                if not postgres:
                    base.execute('BEGIN IMMEDIATE')
                _esquema(db)
                base.commit()
                _inicializadas.add(clave)
        if escritura:
            if postgres:
                db.execute('SELECT pg_advisory_xact_lock(?)', (BLOQUEO_CUENTAS,))
            else:
                base.execute('BEGIN IMMEDIATE')
        yield db
        base.commit()
    except BaseException:
        base.rollback()
        raise
    finally:
        base.close()
        if ruta is not None:
            try:
                ruta.chmod(0o600)
            except OSError:
                pass
