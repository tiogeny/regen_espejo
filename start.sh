#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

if [ ! -d ".venv" ]; then
    echo "⚡ Creando entorno virtual Python..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "📦 Verificando dependencias..."
pip install -r requirements.txt

echo "🪞 Iniciando REGEN Smart Mirror..."
echo "👉 Abre en tu navegador: http://127.0.0.1:8080/mirror"
DERMA_WEB=1 DERMA_TOUCH_MODE=1 python demo_camara.py
