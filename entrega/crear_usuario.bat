@echo off
chcp 65001 >nul
title Agente de Gestion de Camas - Nuevo usuario
echo Crear un usuario nuevo (el sistema tiene que estar encendido con iniciar.bat).
echo La contrasena debe tener entre 12 y 128 caracteres y no se ve al escribir.
echo.
docker exec -it agente-camas python crear_usuario.py
pause
