"""Corrige únicamente las barras de Excel que quedan huérfanas al filtrar.

Colocar junto a backend y frontend. No cambia cuentas, permisos, modelos,
gráficos ni consultas a la API. Hace un respaldo fuera del proyecto.
"""
from datetime import datetime
import json
from pathlib import Path
import shutil
import sys

CAMBIOS = json.loads('[["(function () {\\n  // Tablas del panel: id -> nombre de la hoja y del archivo\\n", "(function () {\\n  // Cada barra pertenece a una tabla concreta; se retira si esa tabla desaparece.\\n  const barrasExcelPorTabla = new Map();\\n  // Tablas del panel: id -> nombre de la hoja y del archivo\\n"], ["  function agregarBoton(tabla, cfg) {\\n    if (tabla.dataset.conExcel) return;\\n    tabla.dataset.conExcel = \\"1\\";\\n", "  function agregarBoton(tabla, cfg) {\\n    if (barrasExcelPorTabla.has(tabla)) return;\\n"], ["    barra.append(estado, boton);\\n    (tabla.closest(\\".scroll\\") || tabla).before(barra);\\n", "    barra.append(estado, boton);\\n    barrasExcelPorTabla.set(tabla, barra);\\n    (tabla.closest(\\".scroll\\") || tabla).before(barra);\\n"], ["  function revisarTablas() {\\n    Object.entries(TABLAS).forEach", "  function revisarTablas() {\\n    for (const [tabla, barra] of barrasExcelPorTabla) {\\n      if (!tabla.isConnected || !barra.isConnected) {\\n        barra.remove();\\n        barrasExcelPorTabla.delete(tabla);\\n      }\\n    }\\n    Object.entries(TABLAS).forEach"]]')


def main():
    raiz = Path(__file__).resolve().parent
    archivo = raiz / 'frontend' / 'js' / 'panel.js'
    if not archivo.is_file():
        print('Colocá este instalador en la raíz del proyecto, junto a backend y frontend.')
        return 1
    datos = archivo.read_bytes()
    codificacion = 'utf-16' if datos.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
    original = datos.decode(codificacion).replace('\r\n', '\n').replace('\r', '\n')
    if 'const barrasExcelPorTabla = new Map();' in original:
        print('Esta corrección ya está instalada. No se modificó ningún archivo.')
        return 0
    nuevo = original
    for anterior, correccion in CAMBIOS:
        if nuevo.count(anterior) != 1:
            print('panel.js tiene cambios distintos a la versión revisada. No se modificó ningún archivo.')
            return 1
        nuevo = nuevo.replace(anterior, correccion, 1)
    respaldo = raiz.parent / 'Respaldos_Agente_Camas' / ('excel_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    copia = respaldo / 'frontend' / 'js' / 'panel.js'
    copia.parent.mkdir(parents=True)
    shutil.copy2(archivo, copia)
    temporal = archivo.with_name('panel.js.excel-temporal')
    try:
        temporal.write_text(nuevo, encoding='utf-8', newline='\n')
        temporal.replace(archivo)
    except BaseException:
        temporal.unlink(missing_ok=True)
        shutil.copy2(copia, archivo)
        raise
    print('Corrección instalada: una barra de exportación por tabla.')
    print('Se retiran las barras de tablas reemplazadas al filtrar o actualizar.')
    print('Único archivo modificado: frontend/js/panel.js')
    print('Respaldo:', respaldo)
    print('Probá el panel local con Ctrl+F5 y cambiá varias veces los filtros de Administración.')
    print('La versión en Render seguirá igual hasta subir este cambio a sabrina y desplegarlo.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, UnicodeError) as error:
        print('No se pudo completar la corrección:', error)
        sys.exit(1)
