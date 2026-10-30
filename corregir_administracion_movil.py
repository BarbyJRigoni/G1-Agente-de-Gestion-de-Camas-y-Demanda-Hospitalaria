"""Corrige el ancho de Administracion en celulares.

Ejecutar en la raiz: python corregir_administracion_movil.py
Modifica solo frontend/css/panel.css y guarda un respaldo externo.
"""
from datetime import datetime
from pathlib import Path
import re
import shutil
import tempfile

AJUSTE = '/* INICIO AJUSTE ADMINISTRACION MOVIL */\n/* La columna puede reducirse; las tablas anchas se desplazan dentro de su cuadro. */\n#vista-administracion {\n  grid-template-columns:minmax(0,1fr);\n  min-width:0;\n  max-width:100%;\n}\n#vista-administracion > *,\n#adminPanelUsuarios,\n#adminPanelHistorial {\n  min-width:0;\n  max-width:100%;\n}\n#vista-administracion .scroll {\n  min-width:0;\n  max-width:100%;\n  overflow-x:auto;\n}\n@media(max-width:900px) {\n  #contenidoAplicacion > header {\n    width:100%;\n    min-width:0;\n  }\n  #contenidoAplicacion > header > * {\n    min-width:0;\n    max-width:100%;\n  }\n  #contenidoAplicacion > header .sesion-usuario {\n    flex-wrap:wrap;\n    justify-content:flex-end;\n  }\n  #nombreSesion {\n    overflow-wrap:anywhere;\n  }\n  #vista-administracion .admin-identidad {\n    flex:1 1 240px;\n    min-width:0;\n    max-width:100%;\n  }\n  #vista-administracion .admin-identidad > div {\n    min-width:0;\n  }\n  #vista-administracion .admin-presentacion h2,\n  #vista-administracion .admin-presentacion p {\n    overflow-wrap:anywhere;\n  }\n  #vista-administracion .admin-herramientas > label,\n  #vista-administracion .admin-herramientas > button,\n  #vista-administracion .admin-navegacion > button {\n    min-width:0;\n    max-width:100%;\n  }\n  #vista-administracion .admin-navegacion > button {\n    white-space:normal;\n  }\n}\n/* FIN AJUSTE ADMINISTRACION MOVIL */\n'
INICIO = '/* INICIO AJUSTE ADMINISTRACION MOVIL */'
FIN = '/* FIN AJUSTE ADMINISTRACION MOVIL */'


def leer(ruta):
    contenido = ruta.read_bytes()
    if contenido.startswith((b'\xff\xfe\x00\x00', b'\x00\x00\xfe\xff')):
        return contenido.decode('utf-32').replace('\r\n','\n')
    if contenido.startswith((b'\xff\xfe',b'\xfe\xff')):
        return contenido.decode('utf-16').replace('\r\n','\n')
    return contenido.decode('utf-8-sig').replace('\r\n','\n')


def main():
    raiz = Path(__file__).resolve().parent
    css = raiz / 'frontend/css/panel.css'
    html = raiz / 'frontend/index.html'
    if not css.is_file() or not html.is_file():
        raise ValueError('Coloca este instalador en la raiz del proyecto, junto a backend y frontend.')
    original = leer(css)
    pagina = leer(html)
    for selector in ('.tab-panel', '.admin-tabla', '.scroll', '#contenidoAplicacion'):
        if selector not in original:
            raise ValueError('El CSS no coincide con la estructura revisada. No se modifico ningun archivo.')
    if '\\#contenidoAplicacion' in original:
        raise ValueError('El CSS contiene escapes de Markdown. Adjunta el archivo panel.css original para revisarlo; no se modifico nada.')
    for identificador in ('contenidoAplicacion','vista-administracion','adminPanelUsuarios','adminPanelHistorial','listaUsuarios'):
        if not re.search(r'\bid\s*=\s*[\"\x27]'+identificador+r'[\"\x27]', pagina):
            raise ValueError('El HTML tiene otra estructura. No se modifico ningun archivo.')
    if original.count(INICIO) != original.count(FIN) or original.count(INICIO) > 1:
        raise ValueError('Hay un bloque anterior incompleto o repetido. No se modifico ningun archivo.')
    if INICIO in original:
        comienzo = original.index(INICIO)
        final = original.index(FIN, comienzo) + len(FIN)
        nuevo = original[:comienzo] + AJUSTE.rstrip() + original[final:]
    else:
        nuevo = original.rstrip() + '\n\n' + AJUSTE
    if nuevo == original:
        print('El ajuste movil ya esta instalado. No se duplicaron estilos.')
        return
    respaldo = raiz.parent / 'Respaldos_Agente_Camas' / ('admin_movil_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f')) / 'frontend/css/panel.css'
    respaldo.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(css, respaldo)
    with tempfile.NamedTemporaryFile(dir=css.parent, delete=False) as temporal:
        temporal.write(nuevo.encode('utf-8'))
        ruta_temporal = Path(temporal.name)
    try:
        ruta_temporal.replace(css)
    finally:
        ruta_temporal.unlink(missing_ok=True)
    print('Ajuste instalado en frontend/css/panel.css.')
    print('Administracion se ajusta al ancho disponible; las tablas se desplazan dentro de su cuadro.')
    print('Se conservan columnas, acciones, permisos, graficos y colores.')
    print('HTML, JavaScript y backend no se modificaron.')
    print('Respaldo: '+str(respaldo))
    print('Proba en el celular. Para verlo en Render, primero guarda, sube y despliega este cambio.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('No se completo la correccion: '+str(error))
        raise SystemExit(1)
