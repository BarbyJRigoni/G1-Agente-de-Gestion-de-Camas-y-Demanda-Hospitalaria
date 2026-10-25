@echo off
chcp 65001 >nul
title Agente de Gestion de Camas - Actualizar
cd /d "%~dp0"
echo Actualizar el sistema a la version de esta carpeta.
echo Los usuarios y datos guardados se conservan.
echo.
docker info >nul 2>&1
if errorlevel 1 (
  echo [!] Docker Desktop no esta abierto. Abrilo y volve a intentar.
  pause
  exit /b 1
)
if not exist agente-camas.tar (
  echo [!] No se encontro agente-camas.tar en esta carpeta.
  pause
  exit /b 1
)
echo 1/3 Apagando la version anterior...
docker rm -f agente-camas >nul 2>&1
echo 2/3 Instalando la version nueva. Puede tardar unos minutos...
docker load -i agente-camas.tar
if errorlevel 1 (
  echo [!] No se pudo instalar la version nueva.
  pause
  exit /b 1
)
echo 3/3 Iniciando...
call iniciar.bat
