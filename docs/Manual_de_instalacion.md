<h1 align="center">🛠️ Manual de instalación</h1>

<p align="center">
  <img src="../frontend/assets/hospital-base.svg" alt="Ilustración de la entrada del hospital" width="100%">
</p>

<p align="center">
  <b>Agente de Gestión de Camas y Demanda Hospitalaria</b><br>
  Grupo 1 · Salud
</p>

<p align="center">
  <img src="https://img.shields.io/badge/actualizado-01%2F11%2F2026-lightgrey" alt="01/11/2026">
  <img src="https://img.shields.io/badge/Windows-PowerShell-0078D6?logo=windows&logoColor=white" alt="Windows PowerShell">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Docker-opcional-2496ED?logo=docker&logoColor=white" alt="Docker">
</p>

Este manual explica cómo instalar y poner en marcha el sistema en una PC con Windows. Cubre las tres formas de usarlo, la creación de cuentas, las comprobaciones de funcionamiento y cómo resolver los errores más comunes.

## 🧭 ¿Qué forma de instalación elijo?

| Opción | Para quién | Necesita | Sección |
|---|---|---|---|
| 🅰️ **Entorno local** | Desarrollo y exposición | Python 3.11 o superior | [3 a 6](#3--crear-el-entorno-e-instalar-dependencias) |
| 🐳 **Docker** | Probar sin instalar Python o publicar en la nube | Docker Desktop | [7](#7--instalación-con-docker) |
| 🧪 **Demo sin servidor** | Respaldo si falla la PC en la exposición | Solo un navegador | [9](#8--demo-sin-servidor) |

> [!TIP]
> **¿Apurado?** Ver el [⚡ resumen rápido](#-resumen-rápido) al final.

## 📑 Contenido
1. [📋 Requisitos previos](#1--requisitos-previos)
2. [📥 Descargar el proyecto](#2--descargar-el-proyecto)
3. [🐍 Crear el entorno e instalar dependencias](#3--crear-el-entorno-e-instalar-dependencias)
4. [👤 Configurar cuentas](#4--configurar-cuentas)
5. [🚀 Iniciar la aplicación](#5--iniciar-la-aplicación)
6. [✅ Comprobar el funcionamiento](#6--comprobar-el-funcionamiento)
7. [🐳 Instalación con Docker](#7--instalación-con-docker)
8. [🧪 Demo sin servidor](#8--demo-sin-servidor)
9. [🗄️ Cuentas en PostgreSQL (Neon)](#9-️-cuentas-en-postgresql-neon)
10. [🔁 Iniciar de nuevo y detener](#10--iniciar-de-nuevo-y-detener)
11. [🩺 Resolver problemas](#11--resolver-problemas)
12. [💾 Conservación de datos y alcance](#12--conservación-de-datos-y-alcance)

## 1 · 📋 Requisitos previos

| Necesario | Detalle |
|---|---|
| 🪟 **Windows 10 u 11** | Con terminal **PowerShell** |
| 🐍 **Python 3.11 o superior** | Comando `python` accesible (solo para la instalación local) |
| 🐳 **Docker Desktop** | Solo para la opción Docker |
| 🌐 **Navegador** | Cualquiera actualizado |
| 🔌 **Conexión a internet** | Para descargar el proyecto y las dependencias |
| 🌿 **Git** | Para descargar desde el repositorio (también se puede bajar como ZIP) |
| 📝 **VS Code** | Opcional |

## 2 · 📥 Descargar el proyecto
La versión integrada se descarga desde la rama **`main`**:

```powershell
git clone https://github.com/BarbyJRigoni/G1-Agente-de-Gestion-de-Camas-y-Demanda-Hospitalaria.git
cd G1-Agente-de-Gestion-de-Camas-y-Demanda-Hospitalaria
```

> [!NOTE]
> **Sin Git:** en GitHub, botón **Code → Download ZIP**, extraer el ZIP y abrir PowerShell dentro de la carpeta.

Comprobar que estén:
- [ ] `requirements.txt` y `Dockerfile`
- [ ] `backend/` y `frontend/`
- [ ] `demo/`

Y dentro de `backend/data/procesados/`:
- [ ] `healthcare_limpio.csv`
- [ ] `lengthofstay_limpio.csv`
- [ ] `revision_hdhi/episodios/hdhi_episodios_candidatos.csv`

> [!WARNING]
> Si faltan archivos procesados, **pedir la copia completa al equipo** y consultar `docs/limpieza_datasets.md` antes de regenerarlos.

## 3 · 🐍 Crear el entorno e instalar dependencias

Desde la raíz del proyecto, ejecutar **una sola vez**:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

✔️ La terminal debe mostrar el prefijo **`(.venv)`**.

`requirements.txt` fija las versiones de FastAPI, Uvicorn, Pydantic, pandas, NumPy, scikit-learn, SciPy y psycopg (este último solo se usa si las cuentas van a PostgreSQL).

> [!CAUTION]
> No reinstalar mientras otra terminal esté modificando ese mismo entorno.

## 4 · 👤 Configurar cuentas

> [!IMPORTANT]
> **No existen credenciales predeterminadas.** Hay tres formas de crear cuentas:

| Forma | Quién | Usuario | Contraseña | Rol |
|---|---|---|---|---|
| 💻 **Consola** (`crear_usuario.py`) | Quien instala | 3 a 40 caracteres | 12 a 128 caracteres | Usuario |
| 🌐 **Registrarse** en la portada | Cualquier visitante | 3 a 14 caracteres | 5 a 14 caracteres | Usuario |
| ⚙️ **Administración** en el panel | Un administrador | 3 a 40 caracteres | 12 a 128 caracteres | Usuario o administrador |

El usuario admite letras minúsculas, números, punto, guion y guion bajo.

### Crear la primera cuenta por consola

Desde la raíz y con el entorno activo:

```powershell
python backend/app/crear_usuario.py
```

Escribir el usuario y **dos veces** la contraseña. 🔒 La contraseña **no se ve** mientras se escribe.

### Convertirla en administrador

```powershell
python backend/app/crear_admin.py
```

Indicar la cuenta y confirmar con **`si`**. Un administrador puede crear, editar, activar y desactivar cuentas, cambiar roles y ver el historial de cambios desde **⚙ Administración**.

> [!TIP]
> Conviene crear al menos **un administrador por consola**. Después, el resto de las cuentas se pueden manejar desde el panel.

### Registro desde la portada

El formulario **Registrarse** pide usuario, correo (hasta 60 caracteres) y contraseña. Siempre asigna el rol **usuario** y tiene límites contra abusos: **5 registros cada 15 minutos** por conexión y **50 por hora** en total.

## 5 · 🚀 Iniciar la aplicación

Desde la raíz del proyecto y con `(.venv)` activo:

```powershell
python -m uvicorn main:app --app-dir backend/app --reload
```

⏳ Esperar el mensaje **`Application startup complete`** y **dejar la terminal abierta**.

<details>
<summary>📂 ¿La terminal ya está dentro de <code>backend/app</code>?</summary>

<br>

Usar en cambio:

```powershell
python -m uvicorn main:app --reload
```

</details>

> [!WARNING]
> Usar **solo uno** de los dos comandos, según la carpeta en la que esté la terminal. Ejecutar `app.main:app` desde `backend` provoca errores de importación con `services`, `routers` y `core`.

💡 La opción `--reload` es para desarrollo: reinicia el servidor cada vez que cambia el código. Para la exposición se puede omitir.

### Tiempos de la primera vez

Los cálculos se hacen **a pedido** y se guardan para reutilizarlos:

| Acción | Primera vez | Siguientes |
|---|---|---|
| Primera proyección de cada fuente | Unos segundos | Inmediato (queda en memoria) |
| Proyección a 15 o 30 días | Unos segundos más (calibra el margen de error) | Inmediato |
| Solapa **04 Evaluación** | Alrededor de 1 minuto | Menos de 1 s, aun después de reiniciar (se guarda en un archivo) |

> [!TIP]
> **Antes de la exposición:** abrir una vez cada fuente, los horizontes de 15 y 30 días y la solapa Evaluación. Así, durante la demo todo responde al instante.

## 6 · ✅ Comprobar el funcionamiento

| # | Acción | Resultado esperado |
|:-:|---|---|
| 1 | Abrir http://127.0.0.1:8000/salud | ❤️ El servidor responde |
| 2 | Abrir http://127.0.0.1:8000 e iniciar sesión | 🏠 Se accede al panel |
| 3 | **01 Proyección** | 📊 Carga HDHI con una fecha de demostración |
| 4 | Probar **Normal**, **Límite** y **Crítico** | 🔄 Cambia la capacidad y aparecen las alertas |
| 5 | Cambiar **Proyección** a 15 y 30 días | 📈 La tabla, el mapa de camas y el gráfico se adaptan |
| 6 | **Exportar a Excel** | 📥 Se descarga la tabla visible |
| 7 | Abrir **02 Estancias**, **03 UTI y general** y **04 Evaluación** | 🗂️ Cada sección carga sus gráficos |
| 8 | Con una cuenta administradora, **⚙ Administración** | 👥 Lista de usuarios e historial |
| 9 | Abrir http://127.0.0.1:8000/docs | 📘 Documentación de la API (requiere sesión) |

> [!NOTE]
> **No hace falta** un servidor aparte para el frontend: FastAPI sirve la interfaz y la API desde el mismo origen. Chart.js y SheetJS están incluidos en el proyecto, así que el panel funciona sin internet.

## 7 · 🐳 Instalación con Docker

Esta opción arma la imagen a partir del código, así que primero hay que **descargar el proyecto** como se explica en la [sección 2](#2--descargar-el-proyecto):

```powershell
git clone https://github.com/BarbyJRigoni/G1-Agente-de-Gestion-de-Camas-y-Demanda-Hospitalaria.git
cd G1-Agente-de-Gestion-de-Camas-y-Demanda-Hospitalaria
```

No hace falta Python ni el `.venv` (secciones 3 a 5). Con **Docker Desktop abierto** (*Engine running*), desde esa carpeta:

```powershell
docker build -t agente-camas .
docker run -d --name agente-camas -p 8000:8000 -v agente-camas-datos:/datos agente-camas
```

Crear las cuentas **dentro del contenedor**:

```powershell
docker exec -it agente-camas python crear_usuario.py
docker exec -it agente-camas python crear_admin.py
```

Abrir http://localhost:8000.

| Concepto | Qué es |
|---|---|
| **Imagen** (`agente-camas`) | La app ya instalada con Linux, Python 3.13 y sus librerías |
| **Contenedor** | La imagen funcionando |
| **Volumen** (`agente-camas-datos`) | Carpeta fuera del contenedor donde quedan las cuentas. No se pierde al reiniciar ni al actualizar |

### 📄 El `Dockerfile`
`docker build` lee el archivo **`Dockerfile`**, en la raíz del proyecto. Es la receta para armar la imagen. No hace falta modificarlo para instalar ni para actualizar.

| Instrucción | Qué hace |
|---|---|
| `FROM python:3.13-slim` | Parte de un Linux mínimo con Python 3.13 |
| `ENV ... CAMAS_AUTH_DB=/datos/acceso.sqlite3` | Guarda la base de cuentas en `/datos` y evita archivos `.pyc` |
| `COPY requirements.txt .` + `RUN pip install ...` | Instala las librerías. Va antes del código para que, si solo cambia el código, la reconstrucción tarde segundos |
| `COPY backend/` y `COPY frontend/` | Copia la app con la misma estructura del repo |
| `WORKDIR /app/backend/app` | Equivale a `cd backend\app` |
| `EXPOSE 8000` | La app escucha en el puerto 8000 |
| `VOLUME /datos` | Deja las cuentas fuera de la imagen para que no se pierdan |
| `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]` | Arranca el servidor aceptando conexiones desde fuera del contenedor |

El archivo **`.dockerignore`** deja afuera de la imagen lo que no hace falta: `.git`, `.venv`, `docs`, cachés y los CSV originales (la app usa solo `backend/data/procesados`).

**Comandos útiles**

| Comando | Para qué |
|---|---|
| `docker stop agente-camas` | Apagar |
| `docker start agente-camas` | Encender |
| `docker logs -f agente-camas` | Ver la terminal del servidor (salir con <kbd>Ctrl</kbd> + <kbd>C</kbd>) |
| `docker rm -f agente-camas` | Borrar el contenedor (las cuentas se conservan) |
| `docker volume rm agente-camas-datos` | ⚠️ Borrar las cuentas |

### Si cambia el código

Reconstruir la imagen y recrear el contenedor. Las cuentas se conservan:

```powershell
docker build -t agente-camas .
docker rm -f agente-camas
docker run -d --name agente-camas -p 8000:8000 -v agente-camas-datos:/datos agente-camas
```

## 8 · 🧪 Demo sin servidor

La carpeta `demo/` tiene dos opciones de respaldo para la exposición:

| Archivo | Qué hace |
|---|---|
| 🌐 `panel_sin_servidor.html` | Doble clic y se abre en el navegador. **No necesita Python, internet ni sesión.** Muestra resultados reales grabados de la API para los tres datasets y los escenarios Normal, Límite y Crítico |
| ▶️ `iniciar_demo.bat` | Levanta el sistema completo con el `.venv` del proyecto y abre el navegador. Si faltan librerías, las instala. Se cierra cerrando la ventana negra |

> [!WARNING]
> `panel_sin_servidor.html` solo muestra los casos grabados. Si se cambia la fecha o la capacidad a mano, avisa que ese caso no está disponible. Si cambia el modelo o los datos, conviene regenerarlo.

## 9 · 🗄️ Cuentas en PostgreSQL (Neon)

*Opcional.* Por defecto las cuentas se guardan en **SQLite**, en la propia computadora. Para compartir las mismas cuentas entre varias instalaciones o publicar el sistema, se puede usar una base **PostgreSQL** gratuita, por ejemplo en [Neon](https://neon.tech/).

### Usar PostgreSQL
Definir la variable `DATABASE_URL` antes de iniciar el servidor, en la misma terminal:

```powershell
$env:DATABASE_URL = "postgresql://usuario:clave@servidor/base?sslmode=require"
python -m uvicorn main:app --app-dir backend/app --reload
```

Si `DATABASE_URL` no está definida, el sistema vuelve a usar SQLite.

> [!CAUTION]
> La dirección de la base incluye la contraseña. **No escribirla en el código ni subirla a GitHub.**

### Pasar las cuentas existentes de SQLite a Neon

```powershell
python backend/app/migrar_cuentas_neon.py
```

- Pide la dirección de Neon **sin mostrarla** y no la guarda.
- Pide confirmar escribiendo **`COPIAR`**.
- Copia cuentas, roles, estados e historial. Las contraseñas se conservan sin conocerlas.
- La base de Neon **debe estar vacía**. La base local queda intacta.

## 10 · 🔁 Iniciar de nuevo y detener

| Forma | Encender | Apagar |
|---|---|---|
| 🅰️ Local | `.\.venv\Scripts\Activate.ps1` y luego `python -m uvicorn main:app --app-dir backend/app --reload` | <kbd>Ctrl</kbd> + <kbd>C</kbd> y luego `deactivate` |
| 🐳 Docker | `docker start agente-camas` | `docker stop agente-camas` |

> Cerrar el navegador **no** apaga el servidor.

## 11 · 🩺 Resolver problemas

<details>
<summary><b>🚫 PowerShell bloquea <code>Activate.ps1</code></b></summary>

<br>

Usar el Python del entorno directamente, **sin activarlo ni cambiar políticas**:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend/app --reload
```

</details>

<details>
<summary><b>❌ <code>No module named services</code></b></summary>

<br>

Detener con <kbd>Ctrl</kbd> + <kbd>C</kbd> y usar el comando de la [sección 5](#5--iniciar-la-aplicación) desde la raíz, o entrar a `backend/app` y ejecutar `main:app`.

> El problema es la **ruta de importación**, no una biblioteca que falte instalar.

</details>

<details>
<summary><b>📦 <code>No module named uvicorn</code>, <code>psycopg</code> u otra dependencia</b></summary>

<br>

Comprobar que se está usando el **entorno correcto** y repetir la instalación desde `requirements.txt`.

> Si pip falla por versiones o descargas, **guardar el error completo** y no cambiar versiones al azar.

</details>

<details>
<summary><b>🔌 Puerto 8000 ocupado</b></summary>

<br>

Detener el servidor anterior o iniciar otro en un puerto distinto:

```powershell
python -m uvicorn main:app --app-dir backend/app --reload --port 8001
```

Abrir http://127.0.0.1:8001 y usar ese puerto para `/salud` y `/docs`. Con Docker, cerrar el programa que use el puerto 8000 o reiniciar la PC.

</details>

<details>
<summary><b>🐳 "Docker Desktop no está abierto"</b></summary>

<br>

Abrir Docker Desktop, esperar *Engine running* y volver a ejecutar el comando.

</details>

<details>
<summary><b>⏳ La solapa Evaluación o el horizonte de 30 días tardan</b></summary>

<br>

Es normal la primera vez (ver [Tiempos de la primera vez](#tiempos-de-la-primera-vez)). Esperar el resultado. Si falla, guardar el mensaje completo.

</details>

<details>
<summary><b>🔑 Olvido de contraseña</b></summary>

<br>

Un administrador puede gestionarlo desde **⚙ Administración**. Por consola, desde la raíz con el entorno activo:

```powershell
python backend/app/crear_usuario.py --usuario NOMBRE --cambiar-clave
```

Reemplazar `NOMBRE` por la cuenta. El cambio **cierra todas las sesiones** de esa cuenta.

</details>

<details>
<summary><b>🚦 "Se alcanzó el límite de registros"</b></summary>

<br>

El registro desde la portada permite 5 registros cada 15 minutos por conexión. Esperar o crear la cuenta por consola o desde Administración.

</details>

<details>
<summary><b>🗄️ No conecta con PostgreSQL</b></summary>

<br>

Revisar que `DATABASE_URL` empiece con `postgresql://` y que la base de Neon esté activa. Para volver a SQLite, cerrar la terminal (la variable se borra) y abrir una nueva.

</details>

## 12 · 💾 Conservación de datos y alcance

| Tema | Detalle |
|---|---|
| 🗄️ **Cuentas (local)** | `acceso.sqlite3` en `%LOCALAPPDATA%\AgenteCamas`, en una subcarpeta según la ruta del proyecto. `CAMAS_AUTH_DB` permite otra ubicación |
| 🐳 **Cuentas (Docker)** | Volumen `agente-camas-datos` |
| ☁️ **Cuentas (PostgreSQL)** | La base indicada en `DATABASE_URL` |
| 📊 **Evaluación guardada** | Carpeta temporal del sistema (`AgenteCamas\evaluaciones`). Se recalcula sola si cambian los datos o el código |
| 📦 **Mover el proyecto** | Con SQLite local, puede hacer que use **otra base de cuentas** |
| 🛟 **Respaldo** | Detener el servidor y copiar la base de cuentas, junto con los datos y el código |

> [!IMPORTANT]
> Este manual cubre el uso en una PC (`127.0.0.1` / `localhost`). Publicar el sistema en internet requiere HTTPS y una configuración de despliegue específica.

## ⚡ Resumen rápido

**Local**

```powershell
git clone https://github.com/BarbyJRigoni/G1-Agente-de-Gestion-de-Camas-y-Demanda-Hospitalaria.git
cd G1-Agente-de-Gestion-de-Camas-y-Demanda-Hospitalaria
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python backend/app/crear_usuario.py
python backend/app/crear_admin.py
python -m uvicorn main:app --app-dir backend/app --reload
# Abrir http://127.0.0.1:8000   ·   Detener con Ctrl + C
```

**Docker**

```powershell
docker build -t agente-camas .
docker run -d --name agente-camas -p 8000:8000 -v agente-camas-datos:/datos agente-camas
docker exec -it agente-camas python crear_usuario.py
docker exec -it agente-camas python crear_admin.py
# Abrir http://localhost:8000
```

<p align="center">
  <sub>Grupo 1 · Desarrollo de Sistemas de Inteligencia Artificial · Centro Politécnico Superior Malvinas Argentinas · 2026</sub>
</p>