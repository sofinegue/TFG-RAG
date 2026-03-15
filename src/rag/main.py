"""
Backend RAG – tres casos de uso: CVs, EU (legislación), Wiki (Wikipedia).

Ejecutar con:
    python -m src.rag.main
    uvicorn src.rag.main:app --reload --port 8000
"""
import json
import os
import time
import uuid
import asyncio
import threading
import pytz

from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List

import uvicorn
from azure.cosmos import CosmosClient
from fastapi import FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.config import config
from src.rag.app_langgraph import rag_graph
from src.rag.utils.pricing import load_model_pricing, calculate_cost

app = FastAPI(title="RAG Backend – Multi Use-Case")

# ──────────────────────────────────────────────────────────────────────
# CORS
# ──────────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    os.getenv("FRONTEND_URL", ""),
]
ALLOWED_ORIGINS = [o for o in ALLOWED_ORIGINS if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────────────────────
# Cosmos DB (conversaciones)
# ──────────────────────────────────────────────────────────────────────
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT", "")
COSMOS_KEY      = os.getenv("COSMOS_KEY", "")
COSMOS_DB       = os.getenv("COSMOS_CONVERSATIONS_DB", "RAG_DB")
COSMOS_COLL     = os.getenv("COSMOS_CONVERSATIONS_CONTAINER", "Conversations")

cosmos_client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
_db        = cosmos_client.get_database_client(COSMOS_DB)
_container = _db.get_container_client(COSMOS_COLL)

MODEL_PRICING, PRICING_DATE = load_model_pricing()
executor = ThreadPoolExecutor(max_workers=4)

# ──────────────────────────────────────────────────────────────────────
# USE CASES CONFIG
# ──────────────────────────────────────────────────────────────────────
USE_CASES = {
    "cvs": {
        "id":          "cvs",
        "label":       "CVs / Talento",
        "description": "Búsqueda en currículums del equipo EY",
        "icon":        "👤",
        "index":       config.azure_search_index_cvs,
    },
    "eu": {
        "id":          "eu",
        "label":       "Legislación UE",
        "description": "Consultas sobre legislación y documentos de la Unión Europea",
        "icon":        "🇪🇺",
        "index":       config.azure_search_index_eu,
    },
    "wiki": {
        "id":          "wiki",
        "label":       "Wikipedia",
        "description": "Preguntas de conocimiento general basadas en artículos de Wikipedia",
        "icon":        "📖",
        "index":       config.azure_search_index_wiki,
    },
}

# ──────────────────────────────────────────────────────────────────────
# Helpers de conversación (Cosmos DB)
# ──────────────────────────────────────────────────────────────────────
def get_conversation(conv_id: str):
    try:
        return _container.read_item(item=conv_id, partition_key=conv_id)
    except Exception:
        return None


def create_new_conversation(user_id: str, use_case: str = "cvs"):
    new_id = str(uuid.uuid4())
    doc = {
        "id":          new_id,
        "convId":      new_id,
        "user_id":     user_id,
        "use_case":    use_case,
        "created_at":  datetime.now(pytz.timezone("Europe/Madrid")).isoformat(),
        "query_count": 0,
        "messages":    [],
        "title":       "Nueva conversación",
    }
    try:
        _container.create_item(body=doc)
    except Exception as e:
        print(f"⚠️ No se pudo crear la conversación en Cosmos: {e}")
    return new_id


def update_conversation(conv_id: str, conv: dict):
    try:
        if "convId" not in conv:
            conv["convId"] = conv_id
        _container.upsert_item(body=conv)
    except Exception as e:
        print(f"⚠️ No se pudo actualizar conversación {conv_id}: {e}")


def update_title(conv_id: str, query: str):
    try:
        item = get_conversation(conv_id)
        if item:
            item["title"]  = query[:50] + ("..." if len(query) > 50 else "")
            item["convId"] = conv_id
            _container.upsert_item(body=item)
    except Exception as e:
        print(f"⚠️ No se pudo actualizar título {conv_id}: {e}")


def delete_conversation(conv_id: str) -> bool:
    try:
        _container.delete_item(item=conv_id, partition_key=conv_id)
        return True
    except Exception:
        return False


def get_conversations_by_user(user_id: str) -> list:
    try:
        query = (
            f"SELECT * FROM c WHERE c.user_id = '{user_id}' "
            "ORDER BY c.created_at DESC"
        )
        return list(_container.query_items(query=query, enable_cross_partition_query=True))
    except Exception:
        return []

# ──────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ──────────────────────────────────────────────────────────────────────

@app.get("/api/use-cases")
async def list_use_cases():
    """Devuelve los casos de uso disponibles para el frontend."""
    return {"use_cases": list(USE_CASES.values())}


@app.post("/api/chat")
async def chat(
    query:           str  = Form(...),
    user_id:         Optional[str]  = Form(None),
    conversation_id: Optional[str]  = Form(None),
    use_case:        Optional[str]  = Form("cvs"),
    rag_mode:        Optional[str]  = Form("gpt"),
    show_timestamps: Optional[bool] = Form(False),
    assistant_id:    Optional[str]  = Form(None),
):
    # Validar use_case
    if use_case not in USE_CASES:
        return JSONResponse(
            status_code=400,
            content={"error": f"use_case '{use_case}' no válido. Opciones: {list(USE_CASES.keys())}"},
        )

    user_id = user_id or "anonymous"

    # Obtener o crear conversación
    if conversation_id:
        current_conv = get_conversation(conversation_id)
        if current_conv is None:
            conversation_id = create_new_conversation(user_id, use_case)
            current_conv    = get_conversation(conversation_id)
    else:
        conversation_id = create_new_conversation(user_id, use_case)
        current_conv    = get_conversation(conversation_id)

    if current_conv is None:
        # Conversación en memoria si Cosmos no está disponible
        current_conv = {
            "id": conversation_id, "convId": conversation_id,
            "user_id": user_id, "use_case": use_case,
            "query_count": 0, "messages": [], "title": query[:50],
        }

    if current_conv.get("query_count", 0) == 0:
        update_title(conversation_id, query)

    conversation_history = [
        {"role": m["role"], "content": m["content"]}
        for m in current_conv["messages"]
    ]

    current_conv["messages"].append({"role": "user", "content": query})
    current_conv["query_count"] = current_conv.get("query_count", 0) + 1

    # Ejecutar RAG
    try:
        result = rag_graph.run(
            query=query,
            user_id=user_id,
            conversation_history=conversation_history,
            rag_mode=rag_mode,
            use_case=use_case,
            assistant_id=assistant_id,
        )
    except Exception as e:
        current_conv["messages"].pop()
        return JSONResponse(status_code=500, content={"error": str(e)})

    # Guardrails: bloquear si fue una violación
    if result.get("error") in ("input_violation", "guardrails_violation"):
        current_conv["messages"].pop()
        return JSONResponse(
            status_code=400,
            content={"error": result.get("answer", "Consulta rechazada por políticas de uso.")},
        )

    answer   = result.get("answer", "")
    metadata = result.get("metadata", {}) if isinstance(result.get("metadata"), dict) else {}
    usage    = metadata.get("usage", {}) if isinstance(metadata.get("usage"), dict) else {}

    # Registrar respuesta en el historial
    current_conv["messages"].append({"role": "assistant", "content": answer})
    update_conversation(conversation_id, current_conv)

    # Calcular costo
    cost_info = {}
    model_name = usage.get("model", "")
    if model_name:
        cost_info = calculate_cost(
            model_name=model_name,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            cached_tokens=usage.get("cached_tokens", 0),
            pricing_dict=MODEL_PRICING,
        )

    response_payload = {
        "answer":          answer,
        "conversation_id": conversation_id,
        "use_case":        use_case,
        "chunks_used":     result.get("chunks_used", []),
        "metadata": {
            "use_case":          use_case,
            "rag_mode":          rag_mode,
            "model":             model_name,
            "usage":             usage,
            "cost":              cost_info,
            "chunks_count":      len(result.get("chunks_used", [])),
        },
    }

    if show_timestamps:
        response_payload["timestamps"] = result.get("timestamps", {})

    return response_payload


@app.post("/api/conversations/create")
async def create_conversation(
    user_id:  str = Form(...),
    use_case: str = Form("cvs"),
):
    conv_id = create_new_conversation(user_id, use_case)
    return {"conversation_id": conv_id}


@app.get("/api/conversations")
async def get_conversations(user_id: str):
    convs = get_conversations_by_user(user_id)
    return {"conversations": convs}


@app.get("/api/conversations/{conv_id}")
async def get_single_conversation(conv_id: str):
    conv = get_conversation(conv_id)
    if not conv:
        return JSONResponse(status_code=404, content={"error": "Conversación no encontrada"})
    return conv


@app.delete("/api/delete-conversation")
async def delete_conv(conversation_id: str = Form(...)):
    ok = delete_conversation(conversation_id)
    return {"success": ok}


@app.get("/health")
async def health():
    return {"status": "ok", "use_cases": list(USE_CASES.keys()), "timestamp": datetime.now().isoformat()}


@app.get("/api/version")
async def version():
    return {"version": "1.0.0", "project": config.project_name}


# ──────────────────────────────────────────────────────────────────────
# Servir frontend React (producción)
# ──────────────────────────────────────────────────────────────────────
FRONTEND_BUILD = Path(__file__).parent.parent.parent / "frontend" / "build"

if FRONTEND_BUILD.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(FRONTEND_BUILD / "static")),
        name="static",
    )

    @app.get("/")
    async def serve_index():
        return FileResponse(str(FRONTEND_BUILD / "index.html"))

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Dejar pasar las rutas /api/
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"error": "Not found"})
        return FileResponse(str(FRONTEND_BUILD / "index.html"))


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"🚀 Iniciando servidor en puerto {port}")
    uvicorn.run("src.rag.main:app", host="0.0.0.0", port=port, reload=False)
