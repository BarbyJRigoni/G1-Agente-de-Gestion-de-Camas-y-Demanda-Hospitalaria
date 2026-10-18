# Portada y acceso local

## Instalacion y uso
Desde la raiz del proyecto, con .venv activo, ejecutar el actualizador integrado. Este verifica el agente con una cuenta de prueba y una base temporal, que se eliminan al terminar. No crea claves por defecto ni modifica las cuentas del usuario.
Una vez instalado:

    python backend/app/crear_usuario.py

Ingresar el usuario y escribir dos veces una contrasena de 12 a 128 caracteres. No se muestra mientras se escribe. Luego iniciar:

    python -m uvicorn main:app --app-dir backend/app --reload

Abrir http://127.0.0.1:8000. La portada muestra el formulario; al entrar se accede a /panel. El panel permite cerrar sesion. No abrir frontend/index.html como archivo: el acceso requiere el servidor.
Para crear otra cuenta, volver a ejecutar crear_usuario.py. Para recuperar una cuenta local:

    python backend/app/crear_usuario.py --usuario sabrina --cambiar-clave

La renovacion invalida las sesiones anteriores de esa cuenta. Esta herramienta supone acceso local autorizado al proyecto; no hay registro publico de cuentas.

## Elegir la foto
Colocar una imagen propia o autorizada del hospital elegido en frontend/assets/hospital.jpg. Tambien se admiten hospital.jpeg, hospital.png y hospital.webp; se usa la primera extension disponible en ese orden. Mantener una sola foto para evitar confusiones. Recargar con Ctrl+F5; no hace falta cambiar Python ni HTML.
Sin foto se usa hospital-base.svg, una ilustracion generica que no representa un hospital de Rio Grande. No se atribuye vinculacion institucional al hospital de la foto. El fondo tiene una capa oscura para permitir leer el texto y el formulario.
El actualizador no modifica ni elimina la foto personalizada.

## Proteccion del acceso
Las contrasenas se guardan como derivadas PBKDF2-HMAC-SHA256 con sal aleatoria de 32 bytes y 600000 iteraciones. No hay contrasenas en codigo, CSV o Git.
La base SQLite de cuentas y sesiones se guarda fuera del repositorio, bajo LOCALAPPDATA/AgenteCamas en Windows, separada por ubicacion del proyecto. CAMAS_AUTH_DB permite una ruta alternativa para pruebas. Copiar o mover el proyecto cambia su identificador local y puede requerir configurar la cuenta nuevamente.
Las sesiones usan un token aleatorio; SQLite guarda su hash, no el token. Vencen a las ocho horas y se revocan en el servidor al cerrar sesion o cambiar la clave. La cookie es HttpOnly y SameSite=Strict; agrega Secure cuando se usa HTTPS.
Se limita el numero de intentos fallidos por IP y usuario. Los errores no revelan si existe la cuenta. El panel, los datos, proyecciones, estadisticas y documentacion de API requieren sesion. Solo son publicos portada, estado de acceso, login/logout, foto, biblioteca de graficos y /salud (estado tecnico sin datos de pacientes).
La API y el frontend usan el mismo origen. No se habilita CORS abierto. Las escrituras rechazan origen externo; los clientes sin Origin deben enviar X-Requested-With: AgenteCamas. El navegador del panel lo agrega automaticamente. Swagger usa el Origin del mismo servidor y la cookie de sesion.
Las respuestas no se cachean. El panel oculta sus resultados al perder la sesion y vuelve al acceso. No se guardan claves ni tokens de sesion en localStorage.

## Alcance
Es un acceso local para la demostracion academica. No incluye roles clinicos, autenticacion multifactor, auditoria clinica ni la infraestructura requerida para datos reales. Si se publica fuera de localhost hacen falta HTTPS y una revision de despliegue. La autenticacion no cambia las predicciones ni valida el modelo sectorial.

## Referencias de implementacion
- https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
