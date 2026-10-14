@echo off
cd /d "%~dp0"

if not exist .venv (
    echo [REGEN] Creando entorno virtual Python 3.11...
    py -3.11 -m venv .venv
)

call .venv\Scripts\activate.bat

echo [REGEN] Verificando dependencias...
pip install -r requirements.txt

echo [REGEN] Iniciando espejo inteligente REGEN...
echo [REGEN] Abre en tu navegador: http://127.0.0.1:8080/mirror
set DERMA_WEB=1
set DERMA_TOUCH_MODE=1
python demo_camara.py
pause
