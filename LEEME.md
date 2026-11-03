# Administración de usuarios

## Qué aparece

- Administración de usuarios en la barra superior, solo para administradores.
- Total, activos e inactivos. Activo significa habilitado, no conectado.
- Búsqueda por nombre completo, usuario o correo sin distinguir tildes.
- Filtros por rol y estado.
- Crear usuario; editar nombre, correo y rol; desactivar y reactivar.
- Historial de cambios administrativos con fecha y responsable.

Las cuentas anteriores conservan contraseña y rol, se consideran activas y muestran nombre pendiente de completar. El administrador puede completar ese dato. Las cuentas creadas desde el registro público siguen siendo usuarios comunes; nunca pueden elegir un rol administrativo desde ese formulario.

## Reglas

No se eliminan cuentas. Desactivar revoca todas sus sesiones e impide ingresar. Reactivar no devuelve los tokens anteriores. Un cambio de rol revoca sus sesiones. No se permite desactivar la propia cuenta ni cambiar el propio rol desde el panel. Debe quedar al menos un administrador activo. Cada acción administrativa se comprueba dentro de una transacción y queda auditada; los intentos rechazados no crean cambios parciales. Las contraseñas y sus hashes no se muestran en la lista ni en la auditoría.

El historial empieza con esta función y registra cambios hechos desde el panel/API administrativa. No reconstruye acciones históricas ni es un registro completo de todos los accesos. Los asistentes locales de creación y cambio de clave conservan su funcionamiento y no forman parte de ese historial administrativo.

## Archivos

- backend/app/services/acceso.py: migración compatible, cuentas inactivas y sesiones.
- backend/app/services/administracion_usuarios.py: operaciones, validación y auditoría.
- backend/app/routers/acceso.py: mantiene acceso/registro y reúne el nuevo router.
- backend/app/routers/administracion_usuarios.py: endpoints exclusivos de administración.
- frontend/index.html: nueva sección y formulario.
- frontend/css/panel.css: estilos administrativos añadidos al final.
- frontend/js/administracion.js: tarjetas, filtros, formularios y consultas.

Modelos, agente, CSV, proyecciones y demás solapas no se modifican. Exportación a Excel queda para el trabajo de Bárbara.

## Pruebas realizadas

Migración de una base de la versión anterior conservando credenciales y sesión, creación y edición, duplicados, acceso denegado a usuarios comunes, desactivación y revocación, reactivación, validación de roles y estados, protección de la propia cuenta, rollback y auditoría sin contraseñas. Pruebas de DOM con API simulada para tarjetas, filtros, búsquedas, formularios y mensajes; prueba de respaldo SQLite y rechazo del instalador si detecta código cambiado.

Falta comprobar visualmente la pantalla en tu Windows antes de hacer commit. No se subió nada a GitHub automáticamente.