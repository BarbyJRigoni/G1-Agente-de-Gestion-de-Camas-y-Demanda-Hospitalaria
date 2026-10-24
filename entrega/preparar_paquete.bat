@echo off
chcp 65001 >nul
REM Uso interno (Grupo 1): arma la carpeta "entrega" para pasarsela a otra persona.
REM Ejecutar desde la raiz del repositorio, con Docker Desktop abierto.
cd /d "%~dp0\.."
echo 1/2 Construyendo la imagen...
docker build -t agente-camas .
if errorlevel 1 ( echo [!] Fallo el build & pause & exit /b 1 )
echo 2/2 Guardando la imagen en entrega\agente-camas.tar (puede pesar varios cientos de MB)...
docker save -o entrega\agente-camas.tar agente-camas
if errorlevel 1 ( echo [!] Fallo el guardado & pause & exit /b 1 )
echo.
echo Listo. Comprimi la carpeta "entrega" (sin este archivo) y pasasela a quien la necesite.
pause
