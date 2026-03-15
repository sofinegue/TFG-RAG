#!/bin/bash

echo "🚀 Iniciando RAG Full Stack (React + FastAPI)..."

# ============================
# 1. INSTALAR DEPENDENCIAS PYTHON
# ============================
echo "📦 Actualizando pip..."
python -m pip install --upgrade pip

echo "📚 Instalando dependencias Python..."
pip install -r requirements.txt

# ============================
# 2. VERIFICAR QUE EXISTA EL BUILD DE REACT
# ============================
if [ -d "react-app/build" ]; then
    echo "✅ Build de React encontrado"
    ls -lh react-app/build/ | head -10
else
    echo "❌ ERROR: No se encontró react-app/build/"
    echo "Por favor, ejecuta 'npm run build' localmente antes de desplegar"
    exit 1
fi

# =============================
# 3. INICIAR FASTAPI
# ============================
PORT="${PORT:-8000}"
echo "🎯 Iniciando FastAPI en puerto $PORT..."

# Ejecutar FastAPI con uvicorn
uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1

echo "✅ Aplicación iniciada exitosamente"