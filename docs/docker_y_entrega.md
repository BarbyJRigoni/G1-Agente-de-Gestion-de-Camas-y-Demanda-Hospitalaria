# Docker, paquete de entrega y tiempos de carga

**Responsable:** Darío (API y documentación) · **Rama:** `dario`

Este documento explica tres cosas que se agregaron al proyecto **sin modificar el código de la app** (agente, modelos, datos ni panel):

1. Los tiempos de carga del panel (`backend/app/main.py`).
2. El contenedor Docker (`Dockerfile` y `.dockerignore`).
3. El paquete para que cualquier persona use la app con doble clic (carpeta `entrega/`).

---

## 1. Tiempos de carga

### El problema
La primera proyección y la evaluación del agente se calculaban **recién cuando alguien entraba al panel**:

| Acción | Tiempo (medido en la PC de Darío) |
|---|---|
| Entrar al panel | 13,5 s |
| Abrir la solapa 04 Evaluación | 40 s o más |

### Qué se agregó (solo en `main.py`)

| Mejora | Qué hace |
|---|---|
| **Precálculo al arrancar** | Al levantar el servidor, calcula en segundo plano la fecha de demo de los 3 datasets y la evaluación del agente. |
| **Espera en vez de repetir** | Si alguien entra antes de que termine, la consulta espera ese cálculo en lugar de hacerlo de nuevo en paralelo (antes eso duplicaba el tiempo). |
| **Evaluación guardada en archivo** | La evaluación se guarda en un `.json` en la carpeta temporal del sistema. En los siguientes arranques se lee del archivo en menos de 1 s. Si cambian los datos o el código, se recalcula sola. |

Los cálculos son **exactamente los mismos**: solo cambió **cuándo** se hacen.

### Resultado

| Acción | Antes | Ahora |
|---|---|---|
| Entrar al panel | 13,5 s | 0,2 s |
| Solapa Evaluación | 40 s | instantáneo (desde el segundo arranque) |

En la terminal aparecen estos mensajes:
```
Precalculo del panel listo en ... s
Precalculo completo en ... s
Evaluacion leida del archivo en 0.0 s     (desde el segundo arranque)
```

> **Para la demo:** levantar el servidor y esperar `Precalculo completo` antes de entrar.
> Si se elige una **fecha nueva**, esa proyección se calcula en el momento y tarda unos segundos (por eso suma el indicador de carga de Barby).

---

## 2. Docker

### Conceptos

| Concepto | Qué es |
|---|---|
| **Imagen** | Una "caja" con Linux, Python, las librerías y la app ya instaladas. Se arma con `docker build`. |
| **Contenedor** | La imagen funcionando. Se crea con `docker run`. |
| **Volumen** | Una carpeta que vive fuera del contenedor. Lo que se guarda ahí (los usuarios) no se pierde al reiniciar. |

### Archivos (en la raíz del repo)

**`Dockerfile`**, paso a paso:

| Línea | Qué hace |
|---|---|
| `FROM python:3.13-slim` | Parte de una imagen con Linux y Python 3.13. |
| `ENV ... CAMAS_AUTH_DB=/datos/acceso.sqlite3` | Guarda la base de usuarios en `/datos`. Esta variable ya la leía `services/acceso.py`: no hubo que tocarlo. |
| `COPY requirements.txt` + `RUN pip install` | Instala las librerías. Va antes del código para aprovechar la caché: si solo cambia el código, el siguiente build tarda segundos. |
| `COPY backend/` y `COPY frontend/` | Copia la app con la misma estructura del repo. |
| `WORKDIR /app/backend/app` | Equivale a `cd backend\app`. |
| `VOLUME /datos` | Los usuarios quedan fuera del contenedor. |
| `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]` | Arranca el servidor como siempre, aceptando conexiones desde afuera. |

**`.dockerignore`**: como el `.gitignore`, pero para Docker. Deja afuera `.git`, `.venv`, `docs`, `__pycache__` y los CSV originales (la app solo usa `backend/data/procesados`).

### Cómo usarlo (con Docker Desktop abierto, desde la raíz del repo)

```powershell
docker build -t agente-camas .
docker run -d --name agente-camas -p 8000:8000 -v agente-camas-datos:/datos agente-camas
docker logs -f agente-camas        # ver la terminal; salir con Ctrl + C
```
Abrir `http://localhost:8000`.

### Crear usuarios dentro del contenedor
El registro desde la web **solo funciona desde la misma computadora** (regla de seguridad de `routers/acceso.py`). Con Docker, el pedido llega desde la red interna de Docker y se rechaza con *"El registro solo esta disponible localmente"*. Los usuarios se crean adentro del contenedor:

```powershell
docker exec -it agente-camas python crear_usuario.py
docker exec -it agente-camas python crear_admin.py     # opcional: hacerlo administrador
```

### Si cambia el código
El `Dockerfile` **no se toca**. Hay que reconstruir la imagen y recrear el contenedor (los usuarios se conservan en el volumen):

```powershell
docker build -t agente-camas .
docker rm -f agente-camas
docker run -d --name agente-camas -p 8000:8000 -v agente-camas-datos:/datos agente-camas
```

### Comandos útiles

| Comando | Para qué |
|---|---|
| `docker stop agente-camas` | Apagar |
| `docker start agente-camas` | Encender |
| `docker logs -f agente-camas` | Ver la terminal del servidor |
| `docker rm -f agente-camas` | Borrar el contenedor (no borra usuarios) |
| `docker volume rm agente-camas-datos` | Borrar los usuarios |

---

## 3. Paquete de entrega (para alguien sin conocimientos de código)

La persona **solo necesita Docker Desktop instalado**. No instala Python ni ve el código.

### Contenido de la carpeta `entrega/`

| Archivo | Para quién | Qué hace |
|---|---|---|
| `iniciar.bat` | Usuario | Doble clic: instala la app (la primera vez), pide crear usuario, la enciende y abre el navegador. |
| `detener.bat` | Usuario | Apaga la app. Los usuarios quedan guardados. |
| `crear_usuario.bat` | Usuario | Agrega otro usuario. |
| `LEEME.txt` | Usuario | Instrucciones en lenguaje simple. |
| `preparar_paquete.bat` | **Grupo** | Construye la imagen y la guarda en `entrega/agente-camas.tar`. |
| `agente-camas.tar` | Usuario | La app empaquetada. **No se sube a git** (pesa varios cientos de MB). |

### Qué hace `iniciar.bat`
1. Verifica que Docker Desktop esté abierto.
2. La primera vez, instala la app desde `agente-camas.tar`.
3. Crea el contenedor o lo enciende si ya existía.
4. Si no hay usuarios, pide crear uno y lo hace administrador (usa `crear_usuario.py` y `crear_admin.py` dentro del contenedor).
5. Espera a que termine el precálculo y abre `http://localhost:8000`.

**Probado:** se abre una ventana negra, pide usuario, contraseña y confirmación de administrador, y se abre la app.

### Cómo armar el paquete
1. Con Docker Desktop abierto, doble clic en `entrega\preparar_paquete.bat`.
2. Comprimir la carpeta `entrega` **sin** `preparar_paquete.bat`.
3. Pasarla por Drive o pendrive.

---

## Archivos agregados o modificados

| Archivo | Cambio |
|---|---|
| `backend/app/main.py` | Precálculo, espera y evaluación guardada (solo se agregaron líneas). |
| `Dockerfile` | Nuevo. |
| `.dockerignore` | Nuevo. |
| `entrega/` | Nueva carpeta con los `.bat` y el `LEEME.txt`. |
| `.gitignore` | Se agregó `entrega/*.tar`. |

**No se modificó:** el agente, los modelos (`prediccion.py`, `modelo_ocupacion.py`), los datos, el panel ni el sistema de usuarios.
