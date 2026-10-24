@echo off
chcp 65001 >nul
title Agente de Gestion de Camas
cd /d "%~dp0"
echo ==========================================================
echo    Agente de Gestion de Camas y Demanda Hospitalaria
echo ==========================================================
echo.

REM ---- 1. Docker Desktop tiene que estar abierto ----
docker info >nul 2>&1
if errorlevel 1 (
  echo [!] Docker Desktop no esta abierto.
  echo     Abrilo, espera a que diga "Engine running" y volve a ejecutar este archivo.
  echo.
  pause
  exit /b 1
)

REM ---- 2. Instalar la aplicacion (solo la primera vez) ----
docker image inspect agente-camas >nul 2>&1
if errorlevel 1 (
  echo Instalando la aplicacion. La primera vez tarda unos minutos...
  docker load -i agente-camas.tar
  if errorlevel 1 (
    echo [!] No se encontro o no se pudo leer el archivo agente-camas.tar
    pause
    exit /b 1
  )
)

REM ---- 3. Crear el contenedor (primera vez) o encenderlo ----
docker container inspect agente-camas >nul 2>&1
if errorlevel 1 (
  docker run -d --name agente-camas -p 8000:8000 -v agente-camas-datos:/datos agente-camas >nul
) else (
  docker start agente-camas >nul
)
if errorlevel 1 (
  echo [!] No se pudo iniciar. Puede que otro programa este usando el puerto 8000.
  pause
  exit /b 1
)

REM ---- 4. Primer uso: crear el usuario administrador ----
timeout /t 3 /nobreak >nul
docker exec agente-camas python -c "import sys; from services import acceso; sys.exit(0 if acceso.hay_usuarios() else 1)" >nul 2>&1
if errorlevel 1 (
  echo.
  echo ----------------------------------------------------------
  echo  PRIMER USO: crea tu usuario para entrar al sistema.
  echo  La contrasena debe tener entre 12 y 128 caracteres
  echo  y no se ve mientras la escribis.
  echo ----------------------------------------------------------
  docker exec -it agente-camas python crear_usuario.py
  echo.
  echo  Ahora volve a escribir el mismo usuario para hacerlo administrador
  echo  y confirma escribiendo: si
  docker exec -it agente-camas python crear_admin.py
)

REM ---- 5. Esperar a que terminen los calculos y abrir el navegador ----
echo.
echo Preparando los calculos. Puede tardar hasta un minuto...
for /f "delims=" %%t in ('docker inspect -f "{{.State.StartedAt}}" agente-camas') do set INICIO=%%t
set /a INTENTOS=0
:esperar
docker logs --since %INICIO% agente-camas 2>&1 | findstr /c:"Precalculo del panel listo" >nul
if not errorlevel 1 goto abrir
set /a INTENTOS+=1
if %INTENTOS% geq 150 goto abrir
timeout /t 2 /nobreak >nul
goto esperar

:abrir
start "" http://localhost:8000
echo.
echo ==========================================================
echo  Listo. El sistema se abrio en el navegador:
echo      http://localhost:8000
echo  Para apagarlo, ejecuta detener.bat
echo ==========================================================
echo.
pause
