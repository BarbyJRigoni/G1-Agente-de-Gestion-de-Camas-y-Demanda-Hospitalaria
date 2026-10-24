# ============================================================
# Agente de Gestion de Camas y Demanda Hospitalaria - Grupo 1
# Contenedor con la API (FastAPI) y el panel web.
#
# Construir:  docker build -t agente-camas .
# Ejecutar:   docker run -d --name agente-camas -p 8000:8000 -v agente-camas-datos:/datos agente-camas
# Abrir:      http://localhost:8000
# ============================================================
FROM python:3.13-slim

# Sin archivos .pyc, salida de logs inmediata y base de usuarios en /datos
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CAMAS_AUTH_DB=/datos/acceso.sqlite3

WORKDIR /app

# 1. Dependencias (se instalan primero para aprovechar la cache de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Codigo, datos procesados y panel (misma estructura que el repo)
COPY backend/ backend/
COPY frontend/ frontend/

# 3. Arranque: uvicorn desde backend/app, escuchando fuera del contenedor
WORKDIR /app/backend/app
EXPOSE 8000
VOLUME /datos
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
