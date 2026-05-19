"""
src.main

Inicia el servidor FastAPI/Uvicorn del backend RAG en puerto 8000
Redirige la ejecución a :mod:`src.rag.main`

Variables de entorno:
    PORT                (default: 8000)
    FRONTEND_URL        (para CORS)

El servidor expone endpoints de RAG para tres casos de uso:
    - CVs (búsqueda de candidatos)
    - EU (legislación europea)
    - Wiki (artículos de Wikipedia)

Uso:
    uvicorn src.rag.main:app --reload --port 8000   # manualmente
"""
import os
import uvicorn

# Redirige la ejecución al backend RAG
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"🚀 Iniciando RAG backend en puerto {port}…")
    uvicorn.run("src.rag.main:app", host="0.0.0.0", port=port, reload=False)
