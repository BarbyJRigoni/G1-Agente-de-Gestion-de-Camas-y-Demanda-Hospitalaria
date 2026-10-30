"""Habilita registro autónomo web conservando la Administración existente.

Ejecutar en la raíz: python habilitar_registro_web.py
Respalda los archivos fuera del repositorio. No contiene credenciales,
no traslada cuentas y no publica cambios en Render automáticamente.
"""
import ast
from datetime import datetime
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import sys

PARCHES = json.loads('{"backend/app/services/acceso.py": [["import time\\n", "import time\\nimport json\\nfrom datetime import datetime, timezone\\n"], ["def crear_usuario(usuario, clave, reemplazar=False, correo=None):\\n", "def crear_usuario(usuario, clave, reemplazar=False, correo=None, *, registro_publico=False):\\n    if registro_publico and reemplazar:\\n        raise ValueError(\'El registro público no puede reemplazar cuentas.\')\\n"], ["    if not 12 <= len(clave) <= 128:\\n        raise ValueError(\'La contrasena debe tener entre 12 y 128 caracteres.\')\\n", "    minimo, maximo = (5, 14) if registro_publico else (12, 128)\\n    if not minimo <= len(clave) <= maximo:\\n        raise ValueError(f\'La contraseña debe tener entre {minimo} y {maximo} caracteres.\')\\n"], ["            db.execute(\'INSERT INTO usuarios(usuario,sal,derivada,iteraciones,correo) VALUES (?,?,?,?,?)\',\\n                       (usuario, sal.hex(), derivada, ITERACIONES, correo))\\n", "            db.execute(\\"INSERT INTO usuarios(usuario,sal,derivada,iteraciones,correo,rol,activo) VALUES (?,?,?,?,?,\'usuario\',1)\\",\\n                       (usuario, sal.hex(), derivada, ITERACIONES, correo))\\n            if registro_publico:\\n                db.execute(\'INSERT INTO auditoria_usuarios(instante,actor,accion,usuario_afectado,cambios) VALUES (?,?,?,?,?)\',\\n                           (datetime.now(timezone.utc).isoformat(timespec=\'seconds\'), usuario, \'crear\', usuario,\\n                            json.dumps({\'rol\': \'usuario\', \'activo\': True, \'origen\': \'Registro público\'}, ensure_ascii=False)))\\n"]], "backend/app/services/cuentas_db.py": [["    db.execute(\'CREATE INDEX IF NOT EXISTS intentos_tiempo ON intentos(instante)\')\\n", "    db.execute(\'\'\'CREATE TABLE IF NOT EXISTS intentos_registro (\\n        ip TEXT NOT NULL, instante DOUBLE PRECISION NOT NULL)\'\'\')\\n    db.execute(\'CREATE INDEX IF NOT EXISTS intentos_registro_tiempo ON intentos_registro(instante)\')\\n    db.execute(\'CREATE INDEX IF NOT EXISTS intentos_tiempo ON intentos(instante)\')\\n"]], "frontend/js/registro.js": [["// Crear una nueva cuenta: se conserva el endpoint y sus datos de entrada.\\n", "// Interpreta validaciones de FastAPI sin mostrar datos sensibles de la solicitud.\\nfunction mensajeErrorRegistro(datos, estado) {\\n    if (typeof datos.detail === \'string\') return datos.detail;\\n    const nombres = { usuario: \'Nombre de usuario\', correo: \'Correo electrónico\', clave: \'Contraseña\' };\\n    if (Array.isArray(datos.detail)) {\\n        return datos.detail.map(error => {\\n            const campo = nombres[error.loc?.at(-1)] || \'Datos del registro\';\\n            if (error.type === \'string_too_short\') return `${campo}: mínimo ${error.ctx?.min_length} caracteres.`;\\n            if (error.type === \'string_too_long\') return `${campo}: máximo ${error.ctx?.max_length} caracteres.`;\\n            if (error.type === \'missing\') return `${campo}: completá este campo.`;\\n            if (error.type === \'extra_forbidden\') return \'La solicitud contiene un campo no permitido.\';\\n            return `${campo}: revisá el valor ingresado.`;\\n        }).join(\' \');\\n    }\\n    return estado >= 500\\n        ? \'El servidor no pudo completar el registro. Esperá un momento y volvé a intentar.\'\\n        : \'No se pudo crear la cuenta. Revisá los datos.\';\\n}\\n\\n// Crear una nueva cuenta: se conserva el endpoint y sus datos de entrada.\\n"], ["        const datos = await respuesta.json();", "        const datos = await respuesta.json().catch(() => ({}));"], ["            throw new Error(\\n                typeof datos.detail === \'string\'\\n                    ? datos.detail\\n                    : \'No se pudo crear la cuenta. Revisá los datos.\'\\n            );", "            throw new Error(mensajeErrorRegistro(datos, respuesta.status));"], ["        mensajeRegistro.textContent = error.message;", "        mensajeRegistro.textContent = error instanceof TypeError\\n            ? \'No se pudo conectar con el servidor. Revisá la conexión y volvé a intentar.\'\\n            : error.message;"]]}')
MODELO = "class Registro(BaseModel):\n    model_config = ConfigDict(extra='forbid')\n    usuario: str = Field(min_length=3, max_length=14)\n    correo: str = Field(min_length=5, max_length=60)\n    clave: str = Field(min_length=5, max_length=14)\n"
ENDPOINT = "def registrar(datos: Registro, request: Request):\n    # El registro admite visitantes de internet; todos reciben rol de usuario.\n    # Se conserva la verificación de origen, además del control en main.py.\n    origen = request.headers.get('origin')\n    if origen:\n        from urllib.parse import urlsplit\n        try:\n            fuente = urlsplit(origen)\n            servidor = urlsplit(str(request.base_url))\n        except ValueError:\n            raise HTTPException(status_code=403, detail='Origen no permitido.') from None\n        if (fuente.scheme.lower(), fuente.netloc.lower()) != (servidor.scheme.lower(), servidor.netloc.lower()):\n            raise HTTPException(status_code=403, detail='Origen no permitido.')\n    elif request.headers.get('x-requested-with') != 'AgenteCamas':\n        raise HTTPException(status_code=403, detail='Solicitud de origen no permitido.')\n    if request.headers.get('sec-fetch-site') == 'cross-site':\n        raise HTTPException(status_code=403, detail='Origen no permitido.')\n    try:\n        usuario = registro_publico.registrar(\n            usuario=datos.usuario, clave=datos.clave, correo=datos.correo,\n            ip=request.client.host if request.client else 'sin-direccion',\n        )\n    except registro_publico.DemasiadosRegistros as error:\n        raise HTTPException(status_code=429, detail=str(error), headers={'Retry-After': str(error.reintentar_en)}) from None\n    except acceso.ErrorIntegridad:\n        raise HTTPException(status_code=409, detail='El nombre de usuario o el correo ya están registrados.') from None\n    except ValueError as error:\n        raise HTTPException(status_code=400, detail=str(error)) from None\n    return {'mensaje': 'Usuario registrado correctamente. Ya podés iniciar sesión.', 'usuario': usuario}\n"
SERVICIO = '"""Registro autónomo de usuarios comunes con límite compartido de solicitudes.\n\nEl límite se guarda en la misma base de cuentas (SQLite o PostgreSQL), para\nque no se reinicie con cada proceso web. No interviene en las altas del admin.\n"""\nimport time\nfrom services import acceso\n\nVENTANA_IP = 15 * 60\nMAXIMO_IP = 5\nVENTANA_GLOBAL = 60 * 60\nMAXIMO_GLOBAL = 50\n\n\nclass DemasiadosRegistros(ValueError):\n    def __init__(self, mensaje, reintentar_en=900):\n        super().__init__(mensaje)\n        self.reintentar_en = reintentar_en\n\n\ndef registrar(usuario, clave, correo, ip):\n    ahora = time.time()\n    ip = ip or \'sin-direccion\'\n    # Cada solicitud reserva su lugar antes del cálculo de PBKDF2.\n    # El bloqueo de escritura conserva el límite con solicitudes simultáneas.\n    with acceso.conexion(escritura=True) as db:\n        db.execute(\'DELETE FROM intentos_registro WHERE instante<?\', (ahora - VENTANA_GLOBAL,))\n        total = db.execute(\'SELECT COUNT(*) FROM intentos_registro\').fetchone()[0]\n        por_ip = db.execute(\'SELECT COUNT(*) FROM intentos_registro WHERE ip=? AND instante>?\',\n                            (ip, ahora - VENTANA_IP)).fetchone()[0]\n        if total >= MAXIMO_GLOBAL:\n            raise DemasiadosRegistros(\'Se alcanzó el límite temporal de registros. Volvé a intentar más tarde.\', 3600)\n        if por_ip >= MAXIMO_IP:\n            raise DemasiadosRegistros(\'Se alcanzó el límite de registros desde tu conexión. Volvé a intentar en 15 minutos.\')\n        db.execute(\'INSERT INTO intentos_registro(ip,instante) VALUES (?,?)\', (ip, ahora))\n    # La cuenta y su evento de auditoría se confirman juntos en crear_usuario.\n    acceso.crear_usuario(usuario, clave, correo=correo, registro_publico=True)\n    return acceso.normalizar_usuario(usuario)\n'


def leer(ruta):
    datos = ruta.read_bytes()
    if datos.startswith((b'\xff\xfe\x00\x00', b'\x00\x00\xfe\xff')):
        codificacion = 'utf-32'
    elif datos.startswith((b'\xff\xfe', b'\xfe\xff')):
        codificacion = 'utf-16'
    else:
        codificacion = 'utf-8-sig'
    return datos.decode(codificacion).replace('\r\n', '\n').replace('\r', '\n')


def cambiar_router(texto):
    if 'registro_publico.registrar(' in texto:
        if 'from services import acceso, registro_publico' not in texto:
            raise ValueError('routers/acceso.py tiene un registro distinto al revisado.')
        return texto
    if texto.count('from services import acceso') != 1:
        raise ValueError('No se reconoció la importación de acceso en routers/acceso.py.')
    arbol = ast.parse(texto)
    objetivos = {n.name: n for n in arbol.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))}
    if 'Registro' not in objetivos or 'registrar' not in objetivos:
        raise ValueError('No se encontró el modelo o el endpoint de registro.')
    funcion = objetivos['registrar']
    if not any(isinstance(d, ast.Call) and d.args and isinstance(d.args[0], ast.Constant)
               and d.args[0].value == '/registrar' for d in funcion.decorator_list):
        raise ValueError('El endpoint de registro tiene otra estructura.')
    constantes = {n.value for n in ast.walk(funcion) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    if not {'127.0.0.1', '::1'}.issubset(constantes):
        raise ValueError('El registro ya tiene modificaciones distintas a la versión revisada.')
    campos = {n.target.id for n in objetivos['Registro'].body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)}
    if campos != {'usuario', 'correo', 'clave'}:
        raise ValueError('El modelo Registro tiene otros campos. No se sobrescribieron.')
    lineas = texto.splitlines(keepends=True)
    for nodo, nuevo in sorted([(objetivos['Registro'], MODELO), (funcion, ENDPOINT)], key=lambda x: x[0].lineno, reverse=True):
        lineas[nodo.lineno - 1:nodo.end_lineno] = [nuevo.rstrip() + '\n']
    return ''.join(lineas).replace('from services import acceso', 'from services import acceso, registro_publico', 1)


class CamposPortada(HTMLParser):
    def __init__(self):
        super().__init__()
        self.campos = {}

    def handle_starttag(self, tag, atributos):
        datos = dict(atributos)
        if tag == 'input' and datos.get('id'):
            self.campos[datos['id']] = datos


def main():
    raiz = Path(__file__).resolve().parent
    requeridos = [*PARCHES, 'backend/app/routers/acceso.py', 'frontend/portada.html']
    for relativo in requeridos:
        if not (raiz / relativo).is_file():
            raise ValueError(f'Falta {relativo}. Colocá este archivo junto a backend y frontend.')
    campos = CamposPortada()
    campos.feed(leer(raiz / 'frontend/portada.html'))
    for campo in ('nuevaClave', 'confirmarClave'):
        atributos = campos.campos.get(campo, {})
        if atributos.get('minlength') != '5' or atributos.get('maxlength') != '14':
            raise ValueError('El formulario tiene otra longitud de contraseña. No se modificó ningún archivo.')
    if campos.campos.get('nuevoUsuario', {}).get('maxlength') != '14' or campos.campos.get('nuevoCorreo', {}).get('maxlength') != '60':
        raise ValueError('Los límites de usuario o correo difieren del formulario revisado.')
    cambios = {}
    for relativo, parches in PARCHES.items():
        texto = leer(raiz / relativo)
        for anterior, nuevo in parches:
            if texto.count(nuevo) == 1:
                continue
            if texto.count(anterior) == 1:
                texto = texto.replace(anterior, nuevo, 1)
            else:
                raise ValueError(f'{relativo} tiene ediciones distintas a la versión revisada. No se modificó ningún archivo.')
        cambios[relativo] = texto
    relativo = 'backend/app/routers/acceso.py'
    cambios[relativo] = cambiar_router(leer(raiz / relativo))
    relativo = 'backend/app/services/registro_publico.py'
    if (raiz / relativo).exists() and leer(raiz / relativo) != SERVICIO:
        raise ValueError('Ya existe otro servicio de registro público. No se sobrescribió.')
    cambios[relativo] = SERVICIO
    for relativo, texto in cambios.items():
        if relativo.endswith('.py'):
            ast.parse(texto, filename=relativo)
    pendientes = {r: t for r, t in cambios.items() if not (raiz / r).exists() or leer(raiz / r) != t}
    if not pendientes:
        print('El registro web ya está instalado. No se modificó ningún archivo.')
        return 0
    respaldo = raiz.parent / 'Respaldos_Agente_Camas' / ('registro_web_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    respaldo.mkdir(parents=True)
    existentes, nuevos = [], []
    for relativo in pendientes:
        archivo = raiz / relativo
        if archivo.exists():
            copia = respaldo / relativo
            copia.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(archivo, copia)
            existentes.append(relativo)
        else:
            nuevos.append(relativo)
    (respaldo / 'archivos.json').write_text(json.dumps({'raiz': str(raiz), 'existentes': existentes, 'nuevos': nuevos}, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        for relativo, texto in pendientes.items():
            archivo = raiz / relativo
            archivo.parent.mkdir(parents=True, exist_ok=True)
            temporal = archivo.with_name(archivo.name + '.registro-temporal')
            temporal.write_text(texto, encoding='utf-8', newline='\n')
            temporal.replace(archivo)
    except BaseException:
        for relativo in existentes:
            shutil.copy2(respaldo / relativo, raiz / relativo)
        for relativo in nuevos:
            (raiz / relativo).unlink(missing_ok=True)
        raise
    print('Registro web instalado. Las cuentas nuevas reciben rol de usuario común.')
    print('Se conservan Administración, sus altas y roles, y las contraseñas existentes.')
    print('Formulario y API pública: usuario de 3 a 14, correo hasta 60 y contraseña de 5 a 14 caracteres.')
    print('Límite: 5 solicitudes por IP cada 15 minutos y 50 solicitudes totales por hora.')
    print('Las altas públicas se registran en la auditoría, sin contraseñas ni hashes.')
    print('Se conservaron el diseño de la portada, los gráficos, los modelos y los CSV.')
    print('Respaldo:', respaldo)
    print('Archivos cambiados:')
    for relativo in pendientes:
        print(' -', relativo)
    print('Reiniciá Uvicorn y probá el registro local con una cuenta de prueba.')
    print('Todavía falta subir el código a sabrina y desplegarlo en Render para habilitarlo en internet.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, SyntaxError) as error:
        print('No se completó la preparación:', error)
        sys.exit(1)
