"""
src/main.py – Entry point del proyecto TFG-RAG.

Ejecutar el backend RAG:
    python -m src.rag.main

Ejecutar desde aquí (alias):
    python -m src.main
"""
import sys
import os

# Redirige la ejecución al backend RAG
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    print(f"🚀 Iniciando RAG backend en puerto {port}…")
    uvicorn.run("src.rag.main:app", host="0.0.0.0", port=port, reload=False)
