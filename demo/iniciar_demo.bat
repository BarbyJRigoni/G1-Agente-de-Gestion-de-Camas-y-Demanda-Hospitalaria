@echo off
title Agente de Gestion de Camas - Grupo 1
echo ============================================================
echo   Agente de Gestion de Camas y Demanda Hospitalaria (Grupo 1)
echo ============================================================
echo.
echo Iniciando el servidor... El navegador se abre solo en unos segundos.
echo Para cerrar el sistema, cerra esta ventana (o Ctrl + C).
echo.
cd /d "%~dp0.."
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo [Aviso] No se encontro el entorno .venv: se usa el Python del sistema.
)
python -c "import uvicorn" 2>nul || (
    echo Faltan dependencias. Instalando requirements.txt...
    python -m pip install -r requirements.txt
)
start "" cmd /c "timeout /t 10 /nobreak >nul & start http://127.0.0.1:8000/"
python -m uvicorn main:app --app-dir backend/app
echo.
echo El servidor se detuvo. Si hubo un error, revisa el mensaje de arriba.
pause
