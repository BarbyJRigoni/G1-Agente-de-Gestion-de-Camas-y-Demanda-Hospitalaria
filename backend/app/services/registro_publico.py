"""Registro autónomo de usuarios comunes con límite compartido de solicitudes.

El límite se guarda en la misma base de cuentas (SQLite o PostgreSQL), para
que no se reinicie con cada proceso web. No interviene en las altas del admin.
"""
import time
from services import acceso

VENTANA_IP = 15 * 60
MAXIMO_IP = 5
VENTANA_GLOBAL = 60 * 60
MAXIMO_GLOBAL = 50


class DemasiadosRegistros(ValueError):
    def __init__(self, mensaje, reintentar_en=900):
        super().__init__(mensaje)
        self.reintentar_en = reintentar_en


def registrar(usuario, clave, correo, ip):
    ahora = time.time()
    ip = ip or 'sin-direccion'
    # Cada solicitud reserva su lugar antes del cálculo de PBKDF2.
    # El bloqueo de escritura conserva el límite con solicitudes simultáneas.
    with acceso.conexion(escritura=True) as db:
        db.execute('DELETE FROM intentos_registro WHERE instante<?', (ahora - VENTANA_GLOBAL,))
        total = db.execute('SELECT COUNT(*) FROM intentos_registro').fetchone()[0]
        por_ip = db.execute('SELECT COUNT(*) FROM intentos_registro WHERE ip=? AND instante>?',
                            (ip, ahora - VENTANA_IP)).fetchone()[0]
        if total >= MAXIMO_GLOBAL:
            raise DemasiadosRegistros('Se alcanzó el límite temporal de registros. Volvé a intentar más tarde.', 3600)
        if por_ip >= MAXIMO_IP:
            raise DemasiadosRegistros('Se alcanzó el límite de registros desde tu conexión. Volvé a intentar en 15 minutos.')
        db.execute('INSERT INTO intentos_registro(ip,instante) VALUES (?,?)', (ip, ahora))
    # La cuenta y su evento de auditoría se confirman juntos en crear_usuario.
    acceso.crear_usuario(usuario, clave, correo=correo, registro_publico=True)
    return acceso.normalizar_usuario(usuario)
