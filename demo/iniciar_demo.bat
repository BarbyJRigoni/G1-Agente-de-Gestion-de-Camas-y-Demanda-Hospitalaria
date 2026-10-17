@echo off
title Agente de Gestion de Camas - Grupo 1
echo ============================================================
echo   Agente de Gestion de Camas y Demanda Hospitalaria (Grupo 1)
echo ============================================================
echo.
echo Iniciando el servidor... El navegador se abre solo en unos segundos.
echo Para cerrar el sistema, cerra esta ventana (o Ctrl + C).
echo.
cd /d "%~dp0..\backend\app"
if exist "..\..\.venv\Scripts\activate.bat" (
    call "..\..\.venv\Scripts\activate.bat"
) else (
    echo [Aviso] No se encontro el entorno .venv: se usa el Python del sistema.
)
start "" cmd /c "timeout /t 12 /nobreak >nul & start http://localhost:8000/ & start http://localhost:8000/docs"
python -m uvicorn main:app
echo.
echo El servidor se detuvo. Si hubo un error, revisa el mensaje de arriba.
pause
