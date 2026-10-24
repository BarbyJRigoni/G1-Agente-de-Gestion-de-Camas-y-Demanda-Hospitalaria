@echo off
chcp 65001 >nul
title Agente de Gestion de Camas
echo Apagando el sistema...
docker stop agente-camas >nul 2>&1
echo Listo. Los usuarios y datos quedan guardados para la proxima vez.
pause
