<h1 align="center">🛠️ Manual de instalación</h1>

<p align="center">
  <img src="frontend/assets/hospital-base.svg" alt="Ilustración de la entrada del hospital" width="100%">
</p>

<p align="center">
  <b>Agente de Gestión de Camas y Demanda Hospitalaria</b><br>
  Grupo 1 · Salud
</p>

<p align="center">
  <img src="https://img.shields.io/badge/versi%C3%B3n-1.0.0-blue" alt="Versión 1.0.0">
  <img src="https://img.shields.io/badge/actualizado-18%2F10%2F2026-lightgrey" alt="18/10/2026">
  <img src="https://img.shields.io/badge/Windows-PowerShell-0078D6?logo=windows&logoColor=white" alt="Windows PowerShell">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white" alt="Python 3.11">
</p>

Este manual explica cómo instalar y poner en marcha el sistema **en una PC local con Windows y PowerShell**. Incluye la creación de cuentas, las comprobaciones de funcionamiento y cómo resolver los errores de arranque más comunes.

---

## 📑 Contenido

1. [📋 Requisitos previos](#1--requisitos-previos)
2. [📁 Comprobar la carpeta del proyecto](#2--comprobar-la-carpeta-del-proyecto)
3. [🐍 Crear el entorno e instalar dependencias](#3--crear-el-entorno-e-instalar-dependencias)
4. [👤 Configurar cuentas locales](#4--configurar-cuentas-locales)
5. [🚀 Iniciar la aplicación](#5--iniciar-la-aplicación)
6. [✅ Comprobar el funcionamiento](#6--comprobar-el-funcionamiento)
7. [🔁 Iniciar de nuevo y detener](#7--iniciar-de-nuevo-y-detener)
8. [🩺 Resolver problemas de instalación](#8--resolver-problemas-de-instalación)
9. [💾 Conservación de datos y alcance local](#9--conservación-de-datos-y-alcance-local)

> [!TIP]
> **¿Apurado?** Ver el [⚡ resumen rápido](#-resumen-rápido) al final.

---

## 1 · 📋 Requisitos previos

| Necesario | Detalle |
|---|---|
| 🪟 **Windows** | Con terminal **PowerShell** |
| 🐍 **Python** | Comando `python` accesible. En el equipo de referencia se usó **Python 3.11** |
| 🌐 **Navegador** | Cualquiera actualizado |
| 🔌 **Conexión a internet** | Para descargar las dependencias |
| 🌿 **Git** | Solo si el proyecto se descarga desde el repositorio |
| 📝 **VS Code** | Opcional |

- El archivo `requirements.txt` fija las versiones de las dependencias. Su instalación en un entorno nuevo **debe completarse sin errores** antes de continuar.
- Hace falta una **copia completa del proyecto y de sus datos procesados**.

---

## 2 · 📁 Comprobar la carpeta del proyecto

```powershell
cd "C:\Users\LENOVO\Documents\G1-Agente-de-Gestion-de-Camas-y-Demanda-Hospitalaria"
python --version
```

> [!NOTE]
> Esta ruta es la del equipo de referencia. **Adaptarla** si el proyecto está guardado en otra ubicación. Si se recibió un **ZIP**, extraerlo antes de ejecutar los comandos.

En esa carpeta deben estar:

- [ ] `requirements.txt`
- [ ] `backend/`
- [ ] `frontend/`

Y dentro de `backend/data/procesados/`:

- [ ] `healthcare_limpio.csv`
- [ ] `lengthofstay_limpio.csv`
- [ ] `revision_hdhi/episodios/hdhi_episodios_candidatos.csv`

| Carpeta | Contiene |
|---|---|
| `backend/app/data/` | Scripts de limpieza |
| `backend/data/` | Archivos de datos |

> [!WARNING]
> Si faltan archivos procesados, **pedir la copia completa al equipo** y consultar `docs/limpieza_datasets.md` antes de regenerarlos.

Si ya se tiene la versión funcional en la PC, no hace falta cambiar de rama ni reemplazar trabajo.

---

## 3 · 🐍 Crear el entorno e instalar dependencias

Desde la raíz del proyecto, ejecutar **una sola vez**:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

✔️ La terminal debe mostrar el prefijo **`(.venv)`**.

> [!TIP]
> Si ya existe un entorno funcional, basta con **activarlo**.

> [!CAUTION]
> No reinstalar mientras otra terminal esté modificando ese mismo entorno.

---

## 4 · 👤 Configurar cuentas locales

### Crear la primera cuenta

Desde la raíz y con el entorno activo:

```powershell
python backend/app/crear_usuario.py
```

- Ingresar un **nombre de usuario**.
- Escribir **dos veces** una contraseña de **12 a 128 caracteres**.
- 🔒 La contraseña **no se ve** mientras se escribe.

> [!IMPORTANT]
> **No existen credenciales predeterminadas.** También se puede crear una cuenta desde **Registrarse** en la portada, con el servidor iniciado.

### Asignar el rol administrador *(opcional)*

```powershell
python backend/app/crear_admin.py
```

Indicar la cuenta y confirmar con **`si`** cuando el programa lo pida. Esa cuenta podrá consultar usuarios, correos y roles desde la solapa **Administración**.

---

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
> Usar **solo uno** de los dos comandos, según la carpeta en la que esté la terminal. En esta versión, ejecutar `app.main:app` desde `backend` provoca errores de importación con `services`, `routers` y `core`.

💡 La opción `--reload` es para desarrollo local: reinicia el servidor cada vez que cambia el código.

---

## 6 · ✅ Comprobar el funcionamiento

| # | Acción | Resultado esperado |
|:-:|---|---|
| 1 | Abrir http://127.0.0.1:8000/salud | ❤️ El servidor responde |
| 2 | Abrir http://127.0.0.1:8000 e iniciar sesión | 🏠 Se accede al panel |
| 3 | Ir a **Proyección** | 📊 Carga HDHI con una fecha de demostración. Esperar la primera proyección |
| 4 | Probar **Normal**, **Límite** y **Crítico** | 🔄 Cambia la capacidad y se actualizan los resultados |
| 5 | Abrir las otras solapas y http://127.0.0.1:8000/docs | 📘 Documentación técnica de la API (requiere sesión) |

> [!NOTE]
> **No hace falta** iniciar un servidor aparte para el frontend: FastAPI sirve la interfaz y la API desde el mismo origen.

---

## 7 · 🔁 Iniciar de nuevo y detener

**▶️ En usos posteriores**, abrir PowerShell en la raíz y ejecutar:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --app-dir backend/app --reload
```

**⏹️ Para detener:**

| Acción | Cómo |
|---|---|
| Detener el servidor | <kbd>Ctrl</kbd> + <kbd>C</kbd> en la terminal |
| Salir del entorno virtual | `deactivate` (después de detener el servidor) |

---

## 8 · 🩺 Resolver problemas de instalación

<details>
<summary><b>🚫 PowerShell bloquea <code>Activate.ps1</code></b></summary>

<br>

Se puede usar el Python del entorno directamente, **sin activarlo ni cambiar políticas**:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend/app --reload
```

</details>

<details>
<summary><b>❌ <code>No module named services</code></b></summary>

<br>

Detener con <kbd>Ctrl</kbd> + <kbd>C</kbd> y usar el comando de la [sección 5](#5--iniciar-la-aplicación) desde la raíz, o entrar a `backend/app` y ejecutar `main:app`.

> El problema es la **ruta de importación**, no una biblioteca que falte instalar con pip.

</details>

<details>
<summary><b>📦 <code>No module named uvicorn</code> u otra dependencia</b></summary>

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

Luego abrir http://127.0.0.1:8001 y usar ese mismo puerto para `/salud` y `/docs`.

</details>

<details>
<summary><b>🔑 Olvido de contraseña</b></summary>

<br>

Desde la raíz, con el entorno activo:

```powershell
python backend/app/crear_usuario.py --usuario NOMBRE --cambiar-clave
```

Reemplazar `NOMBRE` por la cuenta existente. El cambio **cierra todas las sesiones** de esa cuenta.

</details>

<details>
<summary><b>📉 Faltan datos</b></summary>

<br>

Reponer los archivos procesados (ver [sección 2](#2--comprobar-la-carpeta-del-proyecto)) y reiniciar el servidor.

</details>

---

## 9 · 💾 Conservación de datos y alcance local

| Tema | Detalle |
|---|---|
| 🗄️ **Base de cuentas** | `acceso.sqlite3` en `%LOCALAPPDATA%\AgenteCamas`, dentro de una subcarpeta según la ruta del proyecto |
| ⚙️ **Otra ubicación** | Definir la variable de entorno `CAMAS_AUTH_DB` |
| 📦 **Mover el proyecto** | Puede hacer que use **otra base de cuentas** |
| 🛟 **Respaldo** | Detener el servidor y copiar la base, junto con los datos y el código |

> [!IMPORTANT]
> Este manual cubre el **uso local en `127.0.0.1`**. Publicar el sistema en red requiere un procedimiento de despliegue específico.

---

## ⚡ Resumen rápido

```powershell
# 1. Ir a la carpeta del proyecto
cd "RUTA\G1-Agente-de-Gestion-de-Camas-y-Demanda-Hospitalaria"

# 2. Entorno y dependencias (solo la primera vez)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# 3. Crear cuenta (solo la primera vez)
python backend/app/crear_usuario.py

# 4. Iniciar
python -m uvicorn main:app --app-dir backend/app --reload

# 5. Abrir http://127.0.0.1:8000   ·   Detener con Ctrl + C
```

---

<p align="center">
  <sub>Grupo 1 · Desarrollo de Sistemas de Inteligencia Artificial · Centro Politécnico Superior Malvinas Argentinas · 2026</sub>
</p>
