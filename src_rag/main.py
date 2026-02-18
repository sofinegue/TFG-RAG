"""
FastAPI endpoints para RAG + Chunking (backend)
Ahora también sirve el frontend React en producción
"""
from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi import Path as PathParam
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from azure.cosmos import CosmosClient
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
from models.doc_model import DocumentsToProcessREQ, Documento, DocStatus
from utils.pricing import load_model_pricing, calculate_cost
from services.docintelligence_service import get_content_from_document
from services.vector_store_service import VectorStoreService
from models.Timestamps import Timestamps
from config import config
from appLangGraph import rag_graph
from services.azure_storage_service import (
    list_json_configs_from_blob,
    download_json_config_from_blob,
    upload_json_config_to_blob,
    upload_blob_file_async,
    delete_json_config_from_blob,
    upload_assistant_config_to_blob
)
import json, os, uuid, asyncio, threading, pytz, time, tempfile

app = FastAPI(title="RAG Backend API")

# 🔧 CORS configuración
# En producción, el frontend se sirve desde el mismo dominio,
# pero durante desarrollo necesitamos permitir localhost:3000
ALLOWED_ORIGINS = [
    "http://localhost:3000",  # React dev server
    "https://pocs-rag-cvs-g4cfdbhug0c4eygw.westeurope-01.azurewebsites.net",
    os.getenv("FRONTEND_URL", "")  # URL personalizada si existe
]

# ============================
# LIMPIAR CACHÉ AL INICIAR
# ============================
_ASSISTANTS_CONFIG_CACHE = None
_CACHE_TIMESTAMP = None
print("🧹 Caché de asistentes limpiado al inicio")

# Filtrar orígenes vacíos
ALLOWED_ORIGINS = [origin for origin in ALLOWED_ORIGINS if origin]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT", "")
COSMOS_KEY = os.getenv("COSMOS_KEY", "")

# CONTENEDOR PERSONAL (POR MODIFICAR)
cosmos_client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
database = cosmos_client.get_database_client("HCR")
container = database.get_container_client("conversation")

MODEL_PRICING, PRICING_DATE = load_model_pricing()


# ============================
# POOL DE THREADS PARA OPERACIONES BLOQUEANTES
# ============================
executor = ThreadPoolExecutor(max_workers=4)


# ============================
# FUNCIONES AUXILIARES COSMOS
# ============================

def get_conversation(conversation_id: str):
    """Obtiene una conversación por ID"""
    try:
        item = container.read_item(item=conversation_id, partition_key=conversation_id)
        print(f"✅ Conversación obtenida: {conversation_id}")
        return item
    except Exception as e:
        print(f"❌ Error al obtener conversación {conversation_id}: {e}")
        return None

def create_new_conversation(user_id: str, assistant_id: str):
    """Crea una nueva conversación y devuelve su ID"""
    try:
        new_id = str(uuid.uuid4())
        new_conversation = {
            "id": new_id,
            "convId": new_id,
            "user_id": user_id,
            "assistant_id": assistant_id,
            "created_at": datetime.now(pytz.timezone("Europe/Madrid")).isoformat(),
            "query_count": 0,
            "messages": [],
            "title": "Nueva conversación"
        }
        container.create_item(body=new_conversation)
        return new_id
    except Exception as e:
        print(f"❌ Error al crear conversación: {e}")
        return None

def update_conversation_title(conversation_id: str, query: str):
    """Actualiza el título de la conversación con la primera pregunta"""
    try:
        item = get_conversation(conversation_id)
        if item:
            title = query[:50] + ("..." if len(query) > 50 else "")
            item["title"] = title
            item["convId"] = conversation_id  # Asegurar que existe
            container.upsert_item(body=item)
    except Exception as e:
        print(f"❌ Error al actualizar título de conversación {conversation_id}: {e}")

def update_conversation(conversation_id: str, current_conv: dict):
    """Actualiza la conversación completa en Cosmos DB"""
    try:
        # Asegúrate de que convId esté presente
        if "convId" not in current_conv:
            current_conv["convId"] = conversation_id
        
        container.upsert_item(body=current_conv)
        print(f"✅ Conversación actualizada: {conversation_id}")
    except Exception as e:
        print(f"❌ Error al actualizar conversación: {e}")
        raise

def get_conversations_by_user(user_id: str):
    """Obtiene todas las conversaciones de un usuario"""
    try:
        query = f"SELECT * FROM c WHERE c.user_id = '{user_id}' ORDER BY c.created_at DESC"
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        return items
    except Exception as e:
        print(f"❌ Error al obtener conversaciones del usuario {user_id}: {e}")
        return []
    
def delete_conversation(conversation_id: str):
    """Elimina una conversación por ID en Cosmos DB"""
    try:
        container.delete_item(item=conversation_id, partition_key=conversation_id)
        print(f"✅ Conversación eliminada: {conversation_id}")
        return True
    except Exception as e:
        print(f"❌ Error al eliminar conversación {conversation_id}: {e}")
        return False


# ============================
# CACHÉ DE CONFIGURACIÓN OPTIMIZADO
# ============================
_ASSISTANTS_CONFIG_CACHE = None
_CACHE_TIMESTAMP = None
CACHE_TTL = 300  # 5 minutos en segundos

def load_assistants_config(force_reload: bool = False):
    """
    Carga la configuración de asistentes desde Azure Blob Storage o archivo local.
    Implementa caché en memoria para evitar cargas repetidas.
    
    Args:
        force_reload: Si True, ignora el caché y recarga desde blob storage
    """
    global _ASSISTANTS_CONFIG_CACHE, _CACHE_TIMESTAMP
    
    # ✅ VERIFICAR CACHÉ
    if not force_reload and _ASSISTANTS_CONFIG_CACHE is not None:
        # Verificar si el caché aún es válido (TTL)
        if _CACHE_TIMESTAMP and (time.time() - _CACHE_TIMESTAMP) < CACHE_TTL:
            print("♻️ Usando configuración de asistentes desde caché")
            return _ASSISTANTS_CONFIG_CACHE
        else:
            print("⏰ Caché expirado, recargando...")
    
    try:
        # ✅ CARGAR DESDE AZURE BLOB STORAGE
        from services.azure_storage_service import list_assistant_configs_from_blob, download_assistant_config_from_blob

        print("📦 Cargando asistentes desde Azure Blob Storage...")
        assistant_ids = list_assistant_configs_from_blob()
        
        # ✅ FILTRAR CLAVES DEL SISTEMA (NO SON ASISTENTES REALES)
        system_keys = ["assistants", "validation_summary", "last_updated"]
        real_assistant_ids = [aid for aid in assistant_ids if aid not in system_keys]
        
        if real_assistant_ids:
            print(f"✅ Encontrados {len(real_assistant_ids)} asistentes en blob storage")
            assistants_config = {
                "assistants": {},
                "last_updated": datetime.now().isoformat()
            }
            
            # Estadísticas de carga
            stats = {"loaded": 0, "failed": 0, "invalid": 0}
            
            for assistant_id in real_assistant_ids:
                try:
                    config_data = download_assistant_config_from_blob(assistant_id)
                    
                    # ✅ VERIFICAR SI ESTÁ MARCADO COMO ELIMINADO (SOFT DELETE)
                    if config_data.get("isDeleted", False):
                        print(f"   🗑️ '{assistant_id}' está eliminado (soft delete), omitiendo...")
                        continue  # No agregarlo a la lista de asistentes activos
                    
                    # ✅ VALIDAR CONFIGURACIÓN ANTES DE AGREGAR
                    api_type = config_data.get("api_type", "azure")
                    is_valid = True
                    
                    # ✅ VALIDACIÓN CONDICIONAL DE API KEY
                    if api_type == "azure":
                        # Azure OpenAI Service: REQUIERE api_key
                        api_key = config_data.get("api_key", "").strip()
                        if not api_key:
                            is_valid = False
                            config_data["_validation_error"] = "Falta api_key para tipo 'azure'"
                            print(f"   ❌ '{assistant_id}' inválido: falta api_key")
                            stats["invalid"] += 1
                    else:
                        pass
                    # elif api_type == "azure_ai_projects":
                    #     # Azure AI Projects: NO requiere api_key (usa Azure AD)
                    #     # print(f"   ℹ️ '{assistant_id}' usa Azure AD (no requiere api_key)")
                    #     pass
                    
                    # ✅ VALIDAR CAMPOS REQUERIDOS
                    if not config_data.get("endpoint", "").strip():
                        if is_valid:  # Solo contar si no fue marcado inválido antes
                            stats["invalid"] += 1
                        is_valid = False
                        config_data["_validation_error"] = "Falta endpoint"
                        print(f"   ❌ '{assistant_id}' falta endpoint")
                    else:
                        pass
                    if not config_data.get("deployment", "").strip():
                        if is_valid:  # Solo contar si no fue marcado inválido antes
                            stats["invalid"] += 1
                        is_valid = False
                        config_data["_validation_error"] = config_data.get("_validation_error", "") + " | Falta deployment"
                        print(f"   ❌ '{assistant_id}' falta deployment")
                    else:
                        pass
                    # ✅ MARCAR COMO VÁLIDO O INVÁLIDO
                    if is_valid:
                        config_data["_is_valid"] = True
                        stats["loaded"] += 1
                        print(f"   ✅ '{assistant_id}' cargado correctamente")
                    else:
                        config_data["_is_valid"] = False
                        print(f"   ⚠️ '{assistant_id}' cargado pero inválido")
                    
                    # Agregar al config (válido o inválido, para que el frontend lo vea)
                    assistants_config["assistants"][assistant_id] = config_data
                    
                except Exception as e:
                    print(f"   ⚠️ Error al cargar asistente {assistant_id}: {e}")
                    stats["failed"] += 1
            
            # Agregar resumen de validación
            assistants_config["validation_summary"] = stats
            
            print(f"📊 Resumen de carga:")
            print(f"   ✅ Válidos: {stats['loaded']}")
            print(f"   ⚠️  Inválidos: {stats['invalid']}")
            print(f"   ❌ Errores: {stats['failed']}")
            
            # ✅ GUARDAR EN CACHÉ
            _ASSISTANTS_CONFIG_CACHE = assistants_config
            _CACHE_TIMESTAMP = time.time()
            
            return assistants_config
        else:
            print("⚠️ No se encontraron asistentes válidos en blob storage")
            
    except Exception as e:
        print(f"⚠️ Error al cargar desde blob storage: {e}")
        import traceback
        traceback.print_exc()
    
    # ✅ FALLBACK: Archivo local
    print("📁 Intentando cargar desde archivo local...")
    from pathlib import Path as PathlibPath
    
    config_path = PathlibPath("utils/assistants_config.json")
    
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            print(f"✅ Cargados {len(config.get('assistants', {}))} asistentes desde archivo local")
            
            # ✅ GUARDAR EN CACHÉ
            _ASSISTANTS_CONFIG_CACHE = config
            _CACHE_TIMESTAMP = time.time()
            
            return config
    
    print("⚠️ No se encontró configuración de asistentes")
    empty_config = {
        "assistants": {},
        "last_updated": datetime.now().isoformat(),
        "validation_summary": {
            "loaded": 0,
            "failed": 0,
            "invalid": 0
        }
    }
    
    # ✅ GUARDAR EN CACHÉ (aunque esté vacío)
    _ASSISTANTS_CONFIG_CACHE = empty_config
    _CACHE_TIMESTAMP = time.time()
    
    return empty_config


# ============================
# BACKGROUND CACHE REFRESH
# ============================
def background_cache_refresh():
    """Thread que refresca el caché cada 4 minutos (antes de que expire)"""
    while True:
        try:
            time.sleep(240)  # 4 minutos (antes del TTL de 5 min)
            load_assistants_config(force_reload=True)
        except Exception as e:
            print(f"⚠️ Error refrescando caché en background: {e}")


# ============================
# STARTUP EVENT - PRE-CARGAR CACHÉ
# ============================
@app.on_event("startup")
async def startup_event():
    """Pre-cargar configuración al iniciar el servidor"""
    print("🚀 Inicializando sistema de caché de asistentes...")
    
    # Pre-cargar en el startup de forma asíncrona
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, load_assistants_config, True)
    
    # Iniciar thread de refresco automático en background
    refresh_thread = threading.Thread(target=background_cache_refresh, daemon=True)
    refresh_thread.start()
    
    print("✅ Caché inicializado y refresco automático activado (cada 4 min)")


# ============================
# UPDATE ASSISTANT
# ============================
@app.post("/api/update-assistant")
async def update_assistant(
    user_id: str = Form(...),
    assistant_key: str = Form(...)
):
    """
    Actualiza el asistente activo y sus variables de entorno (versión optimizada con validación)
    """
    try:
        # ✅ Cargar desde caché (instantáneo en el 99.9% de los casos)
        assistants_config = load_assistants_config()
        
        if assistant_key not in assistants_config.get("assistants", {}):
            return JSONResponse(
                status_code=404,
                content={"error": f"Asistente '{assistant_key}' no encontrado"}
            )
        
        assistant_config = assistants_config["assistants"][assistant_key]
        
        # ✅ VALIDAR CONFIGURACIÓN DEL ASISTENTE ANTES DE APLICARLO
        # ✅ VALIDAR CONFIGURACIÓN DEL ASISTENTE ANTES DE APLICARLO
        api_type = assistant_config.get("api_type", "azure")

        if api_type == "azure":
            # Azure OpenAI Service: REQUIERE api_key
            api_key = assistant_config.get("api_key", "").strip()
            if not api_key:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "invalid_assistant_config",
                        "message": (
                            f"El asistente '{assistant_key}' de tipo 'azure' requiere una api_key válida. "
                            f"Por favor, actualiza el archivo {assistant_key}.json en blob storage "
                            f"con una api_key de Azure OpenAI Service válida."
                        ),
                        "assistant_id": assistant_key,
                        "fix_instructions": (
                            "1. Ve a Azure Portal → Tu recurso Azure OpenAI\n"
                            "2. Ve a 'Keys and Endpoint'\n"
                            f"3. Copia la Key 1 o Key 2\n"
                            f"4. Actualiza el campo 'api_key' en {assistant_key}.json\n"
                            "5. Espera 4 minutos para que se refresque el caché o reinicia el servidor"
                        )
                    }
                )

        # elif api_type == "azure_ai_projects":
        #     # Azure AI Projects: NO requiere api_key (usa Azure AD)
        #     print(f"   ℹ️ Asistente '{assistant_key}' usa Azure AD (no requiere api_key)")
        
        # ✅ VALIDAR QUE ENDPOINT NO ESTÉ VACÍO
        endpoint = assistant_config.get("endpoint", "").strip()
        if not endpoint:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_assistant_config",
                    "message": f"El asistente '{assistant_key}' requiere un endpoint válido",
                    "assistant_id": assistant_key
                }
            )
        
        # ✅ VALIDAR QUE DEPLOYMENT NO ESTÉ VACÍO
        deployment = assistant_config.get("deployment", "").strip()
        if not deployment:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_assistant_config",
                    "message": f"El asistente '{assistant_key}' requiere un deployment válido",
                    "assistant_id": assistant_key
                }
            )
        
        # ✅ ACTUALIZAR VARIABLES DE ENTORNO (solo si pasó validación)
        os.environ["AZURE_OPENAI_AGENT_ENDPOINT"] = endpoint
        os.environ["AZURE_OPENAI_AGENT_API_KEY"] = assistant_config.get("api_key", "")
        os.environ["AZURE_OPENAI_AGENT_DEPLOYMENT"] = deployment
        os.environ["AZURE_OPENAI_AGENT_VECTOR_STORE_ID"] = assistant_config.get("vector_store_id", "")
        
        print(f"✅ Asistente cambiado a: {assistant_config['name']}")
        print(f"   Endpoint: {endpoint}")
        print(f"   Deployment: {deployment}")
        
        return {
            "success": True,
            "assistant_name": assistant_config['name'],
            "assistant_key": assistant_key,
            "message": f"Asistente cambiado a: {assistant_config['name']}"
        }
        
    except Exception as e:
        print(f"❌ Error al cambiar asistente: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": str(e)
            }
        )


# ============================
# FUNCIONES AUXILIARES VARIABLES
# ============================

def set_environment_variables(env_vars: dict):
    for key, value in env_vars.items():
        if value:
            os.environ[key] = str(value)

def parse_json_variables(json_data: dict) -> bool:
    try:
        if "azsearch" in json_data:
            set_environment_variables({
                "AZURE_SEARCH_ENDPOINT": json_data["azsearch"].get("endpoint", ""),
                "AZURE_SEARCH_API_KEY": json_data["azsearch"].get("api_key", ""),
                "AZURE_SEARCH_INDEX_NAME": json_data["azsearch"].get("index_name", "")
            })

        if "cosmosdb" in json_data:
            set_environment_variables({
                "COSMOSDB_ENDPOINT": json_data["cosmosdb"].get("endpoint", ""),
                "COSMOSDB_KEY": json_data["cosmosdb"].get("key", ""),
                "COSMOSDB_DATABASE": json_data["cosmosdb"].get("database", ""),
                "COSMOSDB_CONTAINER": json_data["cosmosdb"].get("container", "")
            })

        if "openai" in json_data:
            set_environment_variables({
                "AGENT_BUILDER_OPENAI_API_KEY": json_data["openai"].get("api_key", ""),
                "OPENAI_MODEL": json_data["openai"].get("model", ""),
                "OPENAI_TEMPERATURE": str(json_data["openai"].get("temperature", ""))
            })

        return True

    except Exception as e:
        print(f"❌ Error al procesar el JSON: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================
# MODO GPT INTERNO: ENABLE/DISABLE
# ============================
@app.get("/api/gptmode")
async def get_gptmode():
    """
    Devuelve si el GPT está habilitado desde .env
    """
    try:
        gpt_active = os.getenv("GPT_INTERNAL_ACTIVE", "false").lower() == "true"
        return {
            "gpt_mode_active": gpt_active
        }
    except Exception as e:
        print(f"❌ Error al obtener la variable de entorno: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

# ============================
# GPT CONFIG MANAGEMENT
# ============================

@app.get("/api/gpt-configs")
async def list_gpt_configs():
    """Lista todas las configuraciones GPT del blob storage"""
    try:
        from services.azure_storage_service import list_json_configs_from_blob
        
        configs = list_json_configs_from_blob(
            account_name=config.azure_storage_assistants_account,
            account_key=config.azure_storage_assistants_key,
            container_name=config.azure_container_assistants,
            prefix="gpt-configs/"
        )
        
        return {"configs": configs}
    except Exception as e:
        print(f"❌ Error listando GPT configs: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/gpt-configs/{config_id}")
async def get_gpt_config(config_id: str):
    """Obtiene una configuración GPT específica"""
    try:
        from services.azure_storage_service import download_json_config_from_blob
        
        blob_name = f"gpt-configs/{config_id}.json"
        config_data = download_json_config_from_blob(
            account_name=config.azure_storage_assistants_account,
            account_key=config.azure_storage_assistants_key,
            container_name=config.azure_container_assistants,
            blob_name=blob_name
        )
        
        return config_data
    except Exception as e:
        print(f"❌ Error obteniendo GPT config: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/gpt-configs")
async def save_gpt_config(request: Request):
    """Guarda o actualiza una configuración GPT"""
    try:
        from services.azure_storage_service import upload_json_config_to_blob
        from datetime import datetime
        
        config_data = await request.json()
        
        # Generar ID si no existe
        if not config_data.get("id"):
            config_data["id"] = f"gpt_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Timestamps
        now = datetime.now().isoformat()
        if not config_data.get("created_at"):
            config_data["created_at"] = now
        config_data["updated_at"] = now
        
        blob_name = f"gpt-configs/{config_data['id']}"
        
        upload_json_config_to_blob(
            account_name=config.azure_storage_assistants_account,
            account_key=config.azure_storage_assistants_key,
            container_name=config.azure_container_assistants,
            json_content=config_data,
            blob_name=blob_name
        )
        
        return {"success": True, "config": config_data}
    except Exception as e:
        print(f"❌ Error guardando GPT config: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.delete("/api/gpt-configs/{config_id}")
async def delete_gpt_config(config_id: str):
    """Elimina una configuración GPT"""
    try:
        from services.azure_storage_service import delete_json_config_from_blob
        
        blob_name = f"gpt-configs/{config_id}.json"
        delete_json_config_from_blob(
            account_name=config.azure_storage_assistants_account,
            account_key=config.azure_storage_assistants_key,
            container_name=config.azure_container_assistants,
            blob_name=blob_name
        )
        
        return {"success": True}
    except Exception as e:
        print(f"❌ Error eliminando GPT config: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/available-models")
async def get_available_models():
    """Devuelve los modelos disponibles con sus parámetros soportados"""
    try:
        models_config_str = os.getenv("MODELS_CONFIG", "[]")
        models = json.loads(models_config_str)
        
        # Definir qué parámetros soporta cada tipo de modelo
        model_capabilities = {
            "gpt-4": {"temperature": True, "top_p": True, "max_tokens": True, "frequency_penalty": True, "presence_penalty": True},
            "gpt-4o": {"temperature": True, "top_p": True, "max_tokens": True, "frequency_penalty": True, "presence_penalty": True},
            "gpt-4o-mini": {"temperature": True, "top_p": True, "max_tokens": True, "frequency_penalty": True, "presence_penalty": True},
            "gpt-3.5-turbo": {"temperature": True, "top_p": True, "max_tokens": True, "frequency_penalty": True, "presence_penalty": True},
            "o1": {"max_completion_tokens": True, "reasoning_effort": True},  # o1 no soporta temperature
            "o1-mini": {"max_completion_tokens": True, "reasoning_effort": True},
            "o1-preview": {"max_completion_tokens": True, "reasoning_effort": True},
        }
        
        enriched_models = []
        for model in models:
            model_name = model.get("name", "")
            # Buscar capabilities por nombre parcial
            capabilities = {"temperature": True, "top_p": True, "max_tokens": True}  # Default
            for key, caps in model_capabilities.items():
                if key in model_name.lower():
                    capabilities = caps
                    break
            
            enriched_models.append({
                **model,
                "capabilities": capabilities
            })
        
        return {"models": enriched_models}
    except Exception as e:
        print(f"❌ Error obteniendo modelos: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/azure-search-indexes")
async def get_azure_search_indexes():
    """Lista los índices disponibles en Azure Search"""
    try:
        from azure.search.documents.indexes import SearchIndexClient
        from azure.core.credentials import AzureKeyCredential
        
        index_client = SearchIndexClient(
            endpoint=config.azure_search_endpoint,
            credential=AzureKeyCredential(config.azure_search_key)
        )
        
        indexes = []
        for index in index_client.list_indexes():
            indexes.append({
                "name": index.name,
                "fields_count": len(index.fields) if index.fields else 0
            })
        
        return {"indexes": indexes}
    except Exception as e:
        print(f"❌ Error listando índices: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# ============================
# CHAT RAG
# ============================
@app.post("/api/chat")
async def chat(
    query: str = Form(...),
    user_id: Optional[str] = Form(None),
    conversation_id: Optional[str] = Form(None),
    rag_mode: Optional[str] = Form("assistant"),
    show_timestamps: Optional[bool] = Form(False),
    assistant_id: Optional[str] = Form(None),
    gpt_config_id: Optional[str] = Form(None)  # ✅ AÑADIR

):
    try:
        print(f"=== INICIO REQUEST ===")
        print(f"query: {query}")
        print(f"user_id: {user_id}")
        print(f"rag_mode: {rag_mode}")
        print(f"assistant_id: {assistant_id}")
        gpt_config = None
        if rag_mode in ["normal", "gpt"] and gpt_config_id:
            try:
                from services.azure_storage_service import download_json_config_from_blob
                blob_name = f"gpt-configs/{gpt_config_id}.json"
                gpt_config = download_json_config_from_blob(
                    account_name=config.azure_storage_assistants_account,
                    account_key=config.azure_storage_assistants_key,
                    container_name=config.azure_container_assistants,
                    blob_name=blob_name
                )
                print(f"✅ GPT Config cargada: {gpt_config.get('name')}")
            except Exception as e:
                print(f"⚠️ No se pudo cargar GPT config: {e}")
        # Obtener o crear conversación
        if conversation_id:
            current_conv = get_conversation(conversation_id)
            if current_conv is None:
                print(f"Conversación {conversation_id} no encontrada, creando nueva...")
                conversation_id = create_new_conversation(user_id, assistant_id)
                current_conv = get_conversation(conversation_id)
        else:
            print("No hay conversation_id, creando nueva conversación...")
            conversation_id = create_new_conversation(user_id, assistant_id)
            current_conv = get_conversation(conversation_id)

        if current_conv is None:
            raise ValueError(f"No se pudo obtener/crear la conversación. conversation_id: {conversation_id}")

        if current_conv.get("query_count", 0) == 0:
            update_conversation_title(conversation_id, query)

        # Historial para el RAG
        conversation_history = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in current_conv["messages"]
        ]

        # Agregar mensaje del usuario
        current_conv["messages"].append({
            "role": "user",
            "content": query
        })

        print(f"Ejecutando RAG con historial de {len(conversation_history)} mensajes")

        # ✅ EJECUTAR RAG CON assistant_id
        try:
            result = rag_graph.run(
                query=query,
                user_id=user_id,
                conversation_history=conversation_history,
                rag_mode=rag_mode,
                assistant_id=assistant_id,
                gpt_config=gpt_config  # ✅ AÑADIR ESTA LÍNEA
            )
            print(f"RAG ejecutado. Resultado keys: {result.keys()}")
        except Exception as e:
            print(f"ERROR en RAG: {e}")
            current_conv["messages"].pop()
            raise

        if "answer" in result:
            answer_preview = result["answer"][:100] + "..." if len(result["answer"]) > 100 else result["answer"]
            print(f"   Answer preview: {answer_preview}")
        if "metadata" in result:
            print(f"   Metadata type: {type(result['metadata'])}")
            if isinstance(result["metadata"], dict):
                print(f"   Metadata keys: {result['metadata'].keys()}")

        # Verificar estructura del resultado
        if not isinstance(result, dict):
            print(f"ERROR: result no es un diccionario, es {type(result)}")
            current_conv["messages"].pop()
            raise ValueError("Resultado del RAG tiene formato incorrecto")

        if "answer" not in result:
            print(f"ERROR: 'answer' no está en result. Keys: {result.keys()}")
            current_conv["messages"].pop()
            raise ValueError("El resultado del RAG no contiene 'answer'")

        if result.get("error") in ["input_violation", "guardrails_violation"]:
            current_conv["messages"].pop()
            return JSONResponse(status_code=400, content={
                "error": "Tu consulta no pudo ser procesada. Por favor, reformula tu pregunta."
            })

        # ✅ Asegurar que metadata es un diccionario
        metadata = result.get("metadata", {})
        if not isinstance(metadata, dict):
            print(f"⚠️ ADVERTENCIA: metadata no es dict, es {type(metadata)}")
            metadata = {}
        
        # ✅ Asegurar que usage es un diccionario
        usage_info = metadata.get("usage", {})
        if not isinstance(usage_info, dict):
            print(f"⚠️ ADVERTENCIA: usage no es dict, es {type(usage_info)}")
            usage_info = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }

        assistant_message = {
            "role": "assistant",
            "content": result["answer"],
            "metadata": {
                "mode": metadata.get("mode", "unknown"),
                "total_time": result.get("timestamps", {}).get("total", 0),
                "model": metadata.get("model", config.chat_model),
                "context_messages": metadata.get("context_messages", 0),
                "usage": usage_info
            }
        }

        if show_timestamps:
            assistant_message["metadata"]["timestamps"] = result["timestamps"]

        current_conv["messages"].append(assistant_message)
        current_conv["query_count"] += 1
        # Guardar conversación actualizada
        try:
            update_conversation(conversation_id, current_conv)
            print(f"Conversación actualizada exitosamente")
        except Exception as e:
            print(f"ERROR al actualizar conversación: {e}")
            raise

        return {
            "conversation_id": conversation_id,
            "messages": current_conv["messages"],
            "answer": result["answer"],
            "metadata": result["metadata"],
            "timestamps": result["timestamps"]
        }

    except Exception as e:
        print(f"Error en chat: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})


# ============================
# CREAR CONVERSACIÓN VACÍA
# ============================
@app.post("/api/conversations/create")
async def create_conversation_endpoint(
    user_id: str = Form(...),
    assistant_id: Optional[str] = Form(None)
):
    """
    Crea una nueva conversación vacía sin necesidad de query
    """
    try:
        print(f"📝 Creando nueva conversación para user_id: {user_id}")
        
        if not user_id or user_id.strip() == '':
            return JSONResponse(
                status_code=400,
                content={"error": "user_id es requerido"}
            )
        
        conversation_id = create_new_conversation(user_id, assistant_id or "default")
        
        if conversation_id:
            # Obtener la conversación recién creada
            conversation = get_conversation(conversation_id)
            
            return {
                "conversation_id": conversation_id,
                "conversation": conversation,
                "message": "✅ Conversación creada exitosamente"
            }
        else:
            return JSONResponse(
                status_code=500,
                content={"error": "No se pudo crear la conversación"}
            )
    except Exception as e:
        print(f"❌ Error creando conversación: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# ============================
# DELETE CONVERSATION
# ============================
@app.post("/api/delete-conversation")
async def delete_conversation_api(conversation_id: str = Form(...)):
    try:
        success = delete_conversation(conversation_id)  # Lógica interna
        if success:
            return {"message": "✅ Conversación eliminada"}
        else:
            return JSONResponse(status_code=500, content={"error": "❌ Error al eliminar conversación"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ============================
# UPLOAD DOCUMENTS REACT
# ============================
@app.post("/api/upload-documents")
async def upload_documents(
    files: List[UploadFile] = File(...),
    id_llamada: str = Form(...),
    equipo: str = Form(...),
    id_caso: str = Form(...),
    usuario: Optional[str] = Form("anonymous"),
    get_formula: Optional[bool] = Form(False)
):
    try:
        documentos = []

        for file in files:
            file_bytes = await file.read()
            original_filename = file.filename
            normalized_filename = original_filename.lower().replace(' ', '_')

            blob_ref = await upload_blob_file_async(
                account_name=config.azure_storage_account,
                account_key=config.azure_storage_key,
                container_name=config.azure_container_name,
                input_file=file_bytes,
                destination_blob=normalized_filename,
                content_type=file.content_type or "application/octet-stream"
            )

            documentos.append(
                Documento(
                    id=str(uuid.uuid4()),
                    status=DocStatus.PENDING,
                    doc_id=blob_ref.blob_name,
                    doc_nombre=normalized_filename
                )
            )

        # Construir objeto de procesamiento
        req = DocumentsToProcessREQ(
            id_llamada=id_llamada,
            id_caso=id_caso,
            usuario=usuario,
            equipo=equipo,
            get_formula=get_formula,
            documentos=documentos
        )

        timestamps_list = [Timestamps("01 init")]
        startrun = datetime.now()
        session_id = f"Upload_{id_llamada}"

        def process_in_background():
            try:
                asyncio.run(
                    get_content_from_document(
                        req, timestamps_list, session_id, startrun, "UPLOAD-DOCS"
                    )
                )
            except Exception as bg_error:
                print(f"Error en procesamiento background: {bg_error}")
                import traceback
                traceback.print_exc()

        thread = threading.Thread(target=process_in_background, daemon=True)
        thread.start()

        return {
            "message": "✅ Documentos subidos y procesamiento iniciado",
            "documentos": len(documentos),
            "id_llamada": id_llamada,
            "estado": "En procesamiento"
        }

    except Exception as e:
        print(f"Error en upload-documents: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})
    

# ============================
# LOGIN
# ============================
@app.post("/api/login")
async def login(username: str = Form(...), password: str = Form(...)):
    """
    Verifica credenciales contra variables de entorno directamente
    """
    from services.azure_storage_service import get_users_from_table
    try:
        users_raw = get_users_from_table()
        valid_user = next((r for r in users_raw if r.get("username") == username), None)
        
        if valid_user and valid_user.get("password") == password:
            g = valid_user.get("group")
            group = (g[0] if isinstance(g, (list, tuple)) and g else g)
            print(group)
            return {
                "authenticated": True,
                "user": username.strip(),
                "group": group
            }
        else:
            return {
                "authenticated": False,
                "error": "User or password incorrect"
            }

    except Exception as e:
        print(f"Error en login: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})



@app.get("/api/groups/list")
async def list_groups():
    """
    Lista todos los grupos disponibles desde la tabla de usuarios
    """
    try:
        from services.azure_storage_service import get_users_from_table
        
        users = get_users_from_table()
        
        # Extraer grupos únicos de todos los usuarios
        groups = set()
        for user in users:
            user_group = user.get("group")
            if user_group:
                if isinstance(user_group, list):
                    groups.update(user_group)
                else:
                    groups.add(user_group)
        
        return {
            "groups": sorted(list(groups)),
            "count": len(groups)
        }
        
    except Exception as e:
        print(f"❌ Error al listar grupos: {e}")
        # Fallback a grupos conocidos
        return {
            "groups": ["POCs", "Admins", "Users"],
            "error": str(e)
        }

@app.get("/api/deployments/list")
async def list_deployments():
    """
    Lista los deployments disponibles en Azure AI Foundry
    """
    try:
        from azure.identity import DefaultAzureCredential
        from azure.ai.projects import AIProjectClient
        
        # Obtener endpoint del primer asistente válido o de variables de entorno
        endpoint = os.getenv("AZURE_OPENAI_AGENT_ENDPOINT", "")
        
        if not endpoint:
            # Intentar obtener de la config de asistentes
            config = load_assistants_config(force_reload=False)
            for assistant_id, assistant_config in config.get("assistants", {}).items():
                if assistant_config.get("endpoint"):
                    endpoint = assistant_config["endpoint"]
                    break
        
        if not endpoint:
            return {"deployments": [], "error": "No endpoint configured"}
        
        credential = DefaultAzureCredential()
        client = AIProjectClient(endpoint=endpoint, credential=credential)
        
        # Listar modelos/deployments disponibles
        deployments = []
        
        try:
            # Intentar listar deployments (depende de la API disponible)
            models = client.inference.get_model_info()
            if models:
                deployments.append({
                    "name": models.model_name,
                    "model": models.model_type
                })
        except Exception as e:
            print(f"⚠️ Error listando modelos: {e}")
        
        # Fallback: deployments comunes conocidos
        if not deployments:
            deployments = [
                {"name": "gpt-4", "model": "gpt-4"},
                {"name": "gpt-4o", "model": "gpt-4o"},
                {"name": "gpt-4o-mini", "model": "gpt-4o-mini"},
                {"name": "gpt-4.1", "model": "gpt-4.1"},
                {"name": "gpt-5", "model": "gpt-5"},
                {"name": "gpt-5-mini", "model": "gpt-5-mini"},
            ]
        
        return {"deployments": deployments}
        
    except Exception as e:
        print(f"❌ Error al listar deployments: {e}")
        return {
            "deployments": [
                {"name": "gpt-4", "model": "gpt-4"},
                {"name": "gpt-4o", "model": "gpt-4o"},
                {"name": "gpt-5", "model": "gpt-5"},
            ],
            "error": str(e)
        }


# ============================
# CONFIG ASISTENTES
# ============================
@app.get("/api/assistants/config")
def get_assistants_config():
    """
    Devuelve la configuración de asistentes desde el caché.
    """
    try:
        # ✅ USAR EL CACHÉ CENTRALIZADO
        config = load_assistants_config(force_reload=False)
        return config
    except Exception as e:
        print(f"❌ Error al obtener configuración de asistentes: {e}")
        return {
            "assistants": {},
            "last_updated": datetime.now().isoformat(),
            "error": str(e)
        }

class AssistantsConfig(BaseModel):
    assistants: dict

@app.post("/api/assistants/config")
def save_assistants_config(config: AssistantsConfig):
    """
    Actualiza la configuración de asistentes:
    - Elimina los asistentes que ya no están en la nueva configuración (del blob).
    - Guarda los asistentes restantes.
    - Actualiza el backup local.
    """
    config_data = config.dict()
    config_data["last_updated"] = datetime.now().isoformat()

    config_path = Path("utils/assistants_config.json")

    try:
        # Recuperamos la lista de asistentes previa desde el CACHÉ (que refleja el Blob Storage)
        previous_assistants = {}
        cached_config = load_assistants_config(force_reload=False)
        if cached_config and "assistants" in cached_config:
            previous_assistants = cached_config["assistants"]
        else:
            # Fallback: recargar desde Blob Storage
            cached_config = load_assistants_config(force_reload=True)
            if cached_config and "assistants" in cached_config:
                previous_assistants = cached_config["assistants"]

        deleted_assistants = set(previous_assistants.keys()) - set(config_data["assistants"].keys())

        # ✅ SOFT DELETE: Marcar como eliminado en lugar de borrar físicamente
        for assistant_id in deleted_assistants:
            try:
                # Obtener la config actual del asistente eliminado
                deleted_config = previous_assistants.get(assistant_id, {})
                deleted_config["connected_to"] = ""
                deleted_config["isDeleted"] = True
                deleted_config["deleted_at"] = datetime.now().isoformat()
                deleted_config["_is_valid"] = False
                
                # Subir el JSON actualizado con isDeleted: true
                upload_assistant_config_to_blob(deleted_config, assistant_id)
                print(f"🗑️ Asistente '{assistant_id}' marcado como eliminado (soft delete)")
            except Exception as e:
                print(f"❌ Error al marcar asistente '{assistant_id}' como eliminado: {e}")

        # Guardar blobs
        # Guardar blobs (mergeando con config existente para no perder campos sensibles)
        for assistant_id, assistant_config in config_data["assistants"].items():
            try:
                # Obtener config existente para preservar campos sensibles
                existing_config = previous_assistants.get(assistant_id, {})
                
                # Campos que NO deben sobrescribirse si vienen vacíos del frontend
                sensitive_fields = ["api_key", "assistant_id", "vector_store_id"]
                
                for field in sensitive_fields:
                    # Si el frontend no envió el campo o lo envió vacío, mantener el valor existente
                    if not assistant_config.get(field) and existing_config.get(field):
                        assistant_config[field] = existing_config[field]
                
                upload_assistant_config_to_blob(assistant_config, assistant_id)
                print(f"✅ Asistente '{assistant_id}' guardado en blob storage")
            except Exception as e:
                print(f"⚠️ Error al guardar asistente '{assistant_id}' en blob: {e}")

    except Exception as e:
        print(f"⚠️ Error general al guardar en blob storage: {e}")

    # Backup local 'utils/assistants_config.json'
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)

    # ✅ INVALIDAR CACHÉ para que se recargue en la próxima petición
    global _ASSISTANTS_CONFIG_CACHE, _CACHE_TIMESTAMP
    _ASSISTANTS_CONFIG_CACHE = None
    _CACHE_TIMESTAMP = None
    print("🔄 Caché de asistentes invalidado tras guardar configuración")

    return {"status": "ok", "message": "Configuración guardada correctamente"}
    
@app.delete("/api/assistants/{assistant_id}")
async def delete_assistant(assistant_id: str):
    """
    Elimina (soft delete) un asistente específico
    """
    try:
        # Obtener config actual del asistente
        cached_config = load_assistants_config(force_reload=False)
        
        if assistant_id not in cached_config.get("assistants", {}):
            return JSONResponse(
                status_code=404,
                content={"error": f"Asistente '{assistant_id}' no encontrado"}
            )
        
        # Obtener la config del asistente a eliminar
        deleted_config = cached_config["assistants"][assistant_id].copy()
        deleted_config["connected_to"] = ""
        deleted_config["isDeleted"] = True
        deleted_config["deleted_at"] = datetime.now().isoformat()
        deleted_config["_is_valid"] = False
        
        # Subir SOLO el JSON del asistente eliminado
        upload_assistant_config_to_blob(deleted_config, assistant_id)
        print(f"🗑️ Asistente '{assistant_id}' marcado como eliminado (soft delete)")
        
        # Invalidar caché
        global _ASSISTANTS_CONFIG_CACHE, _CACHE_TIMESTAMP
        _ASSISTANTS_CONFIG_CACHE = None
        _CACHE_TIMESTAMP = None
        
        return {
            "status": "ok",
            "message": f"Asistente '{assistant_id}' eliminado correctamente"
        }
        
    except Exception as e:
        print(f"❌ Error al eliminar asistente: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# ============================
# AZS CONFIG
# ============================
class AzureSearchConfig(BaseModel):
    endpoint: str
    api_key: str
    index_name: str

@app.post("/api/config/azsearch")
def save_azure_search_config(config: AzureSearchConfig):
    """
    Guarda la configuración de Azure Search y actualiza variables de entorno.
    """
    try:
        os.environ["AZURE_SEARCH_ENDPOINT"] = config.endpoint
        os.environ["AZURE_SEARCH_API_KEY"] = config.api_key
        os.environ["AZURE_SEARCH_INDEX_NAME"] = config.index_name

        return {"status": "ok", "message": "Configuración guardada correctamente"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    

# ============================
# COSMOSDB CONFIG
# ============================
class CosmosDBConfig(BaseModel):
    endpoint: str
    key: str
    database: str
    container: str

@app.post("/api/config/cosmosdb")
def save_cosmosdb_config(config: CosmosDBConfig):
    """
    Guarda la configuración de CosmosDB y actualiza variables de entorno.
    """
    try:
        os.environ["COSMOS_ENDPOINT"] = config.endpoint
        os.environ["COSMOS_KEY"] = config.key
        os.environ["COSMOS_DATABASE_NAME"] = config.database
        os.environ["COSMOS_CONTAINER_NAME"] = config.container

        return {"status": "ok", "message": "Configuración guardada correctamente"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============================
# OPENAI CONFIG
# ============================
class OpenAIConfig(BaseModel):
    api_key: str
    model: str
    temperature: float

@app.post("/api/config/openai")
def save_openai_config(config: OpenAIConfig):
    """
    Guarda la configuración de OpenAI y actualiza variables de entorno.
    """
    try:
        os.environ["AGENT_BUILDER_OPENAI_API_KEY"] = config.api_key
        os.environ["OPENAI_MODEL"] = config.model
        os.environ["OPENAI_TEMPERATURE"] = str(config.temperature)

        return {"status": "ok", "message": "Configuración guardada correctamente"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============================
# VECTOR STORES - LISTAR
# ============================
@app.get("/api/vector-stores/list")
async def list_vector_stores():
    """
    Lista todos los Vector Stores disponibles en Azure AI Projects
    """
    try:
        # Usar las variables de entorno configuradas
        project_endpoint = os.getenv(
            "AZURE_AI_PROJECT_ENDPOINT",
            "https://agentes-poc.services.ai.azure.com/api/projects/firstProject"
        )
        
        service = VectorStoreService(project_endpoint=project_endpoint)
        vector_stores = service.list_vector_stores(limit=50)
        
        return {
            "vector_stores": vector_stores,
            "count": len(vector_stores)
        }
        
    except Exception as e:
        print(f"❌ Error al listar vector stores: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# ============================
# VECTOR STORES - SUBIR ARCHIVOS
# ============================
@app.post("/api/vector-stores/upload")
async def upload_files_to_vector_store(
    vector_store_id: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """
    Sube múltiples archivos a un Vector Store específico
    """
    try:
        
        
        print(f"📤 Recibiendo {len(files)} archivos para Vector Store: {vector_store_id}")
        
        # Inicializar servicio
        project_endpoint = os.getenv(
            "AZURE_AI_PROJECT_ENDPOINT",
            "https://agentes-poc.services.ai.azure.com/api/projects/firstProject"
        )
        
        service = VectorStoreService(project_endpoint=project_endpoint)
        
        # Guardar archivos temporalmente
        temp_files = []
        try:
            for file in files:
                # Crear archivo temporal
                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
                    content = await file.read()
                    tmp_file.write(content)
                    tmp_file.flush()
                    temp_files.append(tmp_file.name)
                    print(f"   📄 {file.filename} guardado temporalmente")
            
            # Subir archivos usando el servicio con multithreading
            results = service.upload_multiple_files(
                vector_store_id=vector_store_id,
                file_paths=temp_files,
                show_progress=False,  # No mostrar barra en backend
                max_workers=5
            )
            
            # Contar éxitos y fallos
            successful = sum(1 for r in results if r.get("success"))
            failed = len(results) - successful
            
            return {
                "message": f"✅ Proceso completado",
                "successful": successful,
                "failed": failed,
                "total": len(files),
                "details": results
            }
            
        finally:
            # Limpiar archivos temporales
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    print(f"⚠️ Error al eliminar archivo temporal: {e}")
        
    except Exception as e:
        print(f"❌ Error al subir archivos: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# ============================
# AI SEARCH - LISTAR ÍNDICES
# ============================
@app.get("/api/search-indexes/list")
async def list_search_indexes():
    """
    Lista todos los índices de Azure AI Search disponibles
    """
    try:
        from azure.search.documents.indexes import SearchIndexClient
        from azure.core.credentials import AzureKeyCredential
        
        # Obtener configuración de AI Search
        search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "")
        search_key = os.getenv("AZURE_SEARCH_API_KEY", "")
        
        if not search_endpoint or not search_key:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Azure AI Search no está configurado. Configura AZURE_SEARCH_ENDPOINT y AZURE_SEARCH_API_KEY"
                }
            )
        
        # Crear cliente
        credential = AzureKeyCredential(search_key)
        index_client = SearchIndexClient(
            endpoint=search_endpoint,
            credential=credential
        )
        
        # Listar índices
        indexes = []
        for index in index_client.list_indexes():
            # Obtener estadísticas del índice
            try:
                stats = index_client.get_index_statistics(index.name)
                document_count = stats.document_count
            except:
                document_count = 0
            
            indexes.append({
                "name": index.name,
                "document_count": document_count,
                "fields_count": len(index.fields) if hasattr(index, 'fields') else 0
            })
        
        print(f"✅ Encontrados {len(indexes)} índices de AI Search")
        
        return {
            "indexes": indexes,
            "count": len(indexes)
        }
        
    except Exception as e:
        print(f"❌ Error al listar índices de AI Search: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# ============================
# VECTOR STORES - INFO DE UN VECTOR STORE
# ============================
@app.get("/api/vector-stores/{vector_store_id}/info")
async def get_vector_store_info(vector_store_id: str):
    """
    Obtiene información detallada de un Vector Store específico
    """
    try:
        
        
        project_endpoint = os.getenv(
            "AZURE_AI_PROJECT_ENDPOINT",
            "https://agentes-poc.services.ai.azure.com/api/projects/firstProject"
        )
        
        service = VectorStoreService(project_endpoint=project_endpoint)
        info = service.get_vector_store_info(vector_store_id)
        
        return info
        
    except Exception as e:
        print(f"❌ Error al obtener info del vector store: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# ============================
# VECTOR STORES - LISTAR ARCHIVOS
# ============================
@app.get("/api/vector-stores/{vector_store_id}/files")
async def list_vector_store_files(vector_store_id: str):
    """
    Lista todos los archivos en un Vector Store específico
    """
    try:
        
        
        project_endpoint = os.getenv(
            "AZURE_AI_PROJECT_ENDPOINT",
            "https://agentes-poc.services.ai.azure.com/api/projects/firstProject"
        )
        
        service = VectorStoreService(project_endpoint=project_endpoint)
        files = service.list_vector_store_files(vector_store_id, limit=100)
        
        return {
            "vector_store_id": vector_store_id,
            "files": files,
            "count": len(files)
        }
        
    except Exception as e:
        print(f"❌ Error al listar archivos del vector store: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# ============================
# VECTOR STORES - CREAR NUEVO
# ============================
@app.post("/api/vector-stores/create")
async def create_vector_store(name: str = Form(...)):
    """
    Crea un nuevo Vector Store
    """
    try:
        
        
        project_endpoint = os.getenv(
            "AZURE_AI_PROJECT_ENDPOINT",
            "https://agentes-poc.services.ai.azure.com/api/projects/firstProject"
        )
        
        service = VectorStoreService(project_endpoint=project_endpoint)
        vector_store_id = service.create_vector_store(name)
        
        return {
            "message": f"✅ Vector Store '{name}' creado exitosamente",
            "vector_store_id": vector_store_id,
            "name": name
        }
        
    except Exception as e:
        print(f"❌ Error al crear vector store: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# ============================
# VECTOR STORES - ELIMINAR ARCHIVO
# ============================
@app.delete("/api/vector-stores/{vector_store_id}/files/{file_id}")
async def delete_file_from_vector_store(vector_store_id: str, file_id: str):
    """
    Elimina un archivo específico de un Vector Store
    """
    try:
        
        project_endpoint = os.getenv(
            "AZURE_AI_PROJECT_ENDPOINT",
            "https://agentes-poc.services.ai.azure.com/api/projects/firstProject"
        )
        
        service = VectorStoreService(project_endpoint=project_endpoint)
        success = service.delete_file_from_vector_store(vector_store_id, file_id)
        
        if success:
            return {
                "message": f"✅ Archivo eliminado exitosamente",
                "vector_store_id": vector_store_id,
                "file_id": file_id
            }
        else:
            return JSONResponse(
                status_code=500,
                content={"error": "No se pudo eliminar el archivo"}
            )
        
    except Exception as e:
        print(f"❌ Error al eliminar archivo: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# ============================
# IMPORT JSON CONFIG
# ============================
@app.post("/api/config/import_json")
async def import_json_config(file: UploadFile):
    try:
        content = await file.read()
        json_data = json.loads(content)
        success = parse_json_variables(json_data)
        if success:
            return {"status": "ok", "message": "Configuración importada y aplicada"}
        else:
            return {"status": "error", "message": "Error al aplicar configuración"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/config/list_json_blobs")
def list_json_blobs():
    try:
        return list_json_configs_from_blob(
            account_name=config.azure_storage_account,
            account_key=config.azure_storage_key,
            container_name=config.azure_container_configs
        )
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/config/import_json_from_blob")
def import_json_from_blob(blob_name: str):
    try:
        blob_content = download_json_config_from_blob(
            account_name=config.azure_storage_account,
            account_key=config.azure_storage_key,
            container_name=config.azure_container_configs,
            blob_name=blob_name
        )
        success = parse_json_variables(blob_content)
        if success:
            return {"status": "ok", "message": f"Configuración '{blob_name}' importada y aplicada"}
        else:
            return {"status": "error", "message": "Error al aplicar configuración"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
      

# ============================
# HEALTH CHECK
# ============================
@app.get("/health")
async def health():
    """Health check del servicio"""
    return {
        "status": "ok",
        "client": config.client_name,
        "project": config.project_name,
        "chat_model": config.chat_model,
        "embedding_model": config.embedding_model
    }

@app.get("/api/version")
async def version():
    """Versión del servicio"""
    return {"version": "1.0.0"}


# ============================
# ASISTENTES DISPONIBLES DE BACKUP
# ============================
@app.get("/api/assistants")
async def get_assistants():
    """
    Devuelve la lista de asistentes disponibles para el modo RAG
    """
    try:
        assistants = {
            "CVs Database Assistant": {
                "name": "CVs Database Assistant",
                "description": "Experto en CVs del equipo EY",
                "endpoint": "https://tevia01s-swcedc-tcrmopenai.openai.azure.com/",
                "api_key": "defd639e766744ea82f0775bc6d98fa9",
                "deployment": "gpt-5",
                "vector_store_id": "vs_7RP0nOpLfunf5hpJLmYvjcdU",
                "prompt": "You are an expert in EY team CVs (RAG system):\nExplore EY CV external information using the tools you have (file search or vector search).\nAnalyze any relevant data, checking your work.\nMake sure to output a concise and short answer.\nAnswer in the same language than the query.\nSuggest a follow up question related to the previous question, and to one of the skills, experiences or people mentioned in previous search. Do not suggest anything out of your duties (answering questions about EY team CVs):\nDO: suggest new questions about specific skills, experiences, seniority, names, team etc. or organizing the information of people in a different way.\nDO NOT: suggest exporting to any file, sending mails or performing other external tool tasks.\nBe exhaustive while searching.\n\nIMPORTANT: Never include citations with brackets 【】 or numeric references. Answer naturally without citing sources.",
                "temperature": 1.0,
                "top_p": 1.0
            },
            "Telia Baltics Expert": {
                "name": "Telia Baltics Expert",
                "description": "Asistente experto en ofertas y servicios Telia en Lituania, Estonia y Finlandia (B2C y B2B)",
                "endpoint": "https://tevia01s-swcedc-tcrmopenai.openai.azure.com/",
                "api_key": "defd639e766744ea82f0775bc6d98fa9",
                "deployment": "gpt-5",
                "vector_store_id": "vs_mwZWqxuAC8svGH1x4oFHB7xS",
                "prompt": "Rol y objetivo\nEres un asistente experto en ofertas y servicios Telia en Lituania, Estonia y Finlandia (B2C y B2B). Respondes en inglés claro y accionable. Prioriza precisión, estructura y utilidad práctica (tablas, listas, cálculos, checklists).\n\nBase de conocimiento (KB)\nDispones de una KB con campos: id, title, text, sources, category (B2C/B2B). Usa solo esta KB para hechos. NUNCA incluyas citas en formato de corchetes 【】 ni referencias con símbolos especiales. Si hay caracteres extraños (Â, EÅ¾ys…), normaliza a \"Ežys\", \"iPhone 17\", etc.\n\nEstilo y formato por defecto\nEncabezado breve con la respuesta directa. Luego una tabla o bullets con detalles. Cierra con \"Próximos pasos\" (acciones concretas) cuando sea relevante. Si el usuario lo pide, ofrece devolver JSON o CSV además del texto.\n\nCapacidades clave\nComparativas: planes móviles (jóvenes/familia/empresa), Telia TV vs Telia Play, fibra vs Telia1, dispositivos (S25, iPhone 16/17, Pixel 10 Pro), Ežys superplans, MultiSIM, SAFE, IoT, DaaS, My Telia for Business.\n\nCálculos de roaming UE (prepago Ežys): Límite de datos UE ≈ cuota en € ÷ 1,573 €/GB. Expón el número con 2 decimales y advierte FUP.\n\nProcedimientos: alta/renovación/cancelación (autoservicio/SMS), activación eSIM, APN, instalación SAFE, Telia TV/Play, portabilidades empresa.\n\nB2B: matrices de planes por velocidad/GB UE/compartición, catálogo de seguridad (DDoS, WAF, MDM), IoT kits, DaaS, gestión en My Telia.\n\nLimitaciones: si falta el dato en KB, dilo, no inventes. Sugiere qué campo/nota faltaría.\n\nPolítica de preguntas aclaratorias\nSi puedes responder razonablemente con lo que hay, no preguntes. Solo pide 1–2 aclaraciones cuando cambien materialmente el resultado (p.ej., país LT/EE/FI, prepago vs contrato, presupuesto, nº dispositivos). Ofrece un supuesto razonable si el usuario no responde.\n\nIMPORTANTE: Nunca uses citas con formato 【】 ni referencias numéricas. Responde de forma natural y directa sin citar fuentes explícitamente.",
                "temperature": 1.0,
                "top_p": 1.0
            },
            "UGEN Documents Assistant": {
                "name": "UGEN Documents Assistant",
                "description": "Experto en documentos del equipo TGSS UGEN",
                "endpoint": "https://open-ai-c4c-pre.openai.azure.com/",
                "api_key": "b86b3a39d06f4e0d8d7b5c484867b197",
                "deployment": "gpt-5-mini",
                "vector_store_id": "vs_iu4OtePpYP4Ob7IEamJz3Zaf",
                "prompt": "You are an expert in TGSS UGEN team (RAG system):\nExplore UGEN documentos external information using the tools you have (file search or vector search).\nAnalyze any relevant data, checking your work.\nMake sure to output a concise and short answer.\nAnswer in the same language than the query.\nSuggest a follow up question related to the previous question, and to one of the skills, experiences or people mentioned in previous search. Do not suggest anything out of your duties (answering questions about UGEN documents):\nDO: suggest new questions about topics mentioned in retrieved documents.\nDO NOT: suggest exporting to any file, sending mails or performing other external tool tasks.\nBe exhaustive while searching.\n\nIMPORTANT: Never include citations with brackets 【】 or numeric references. Answer naturally without citing sources.",
                "temperature": 1.0,
                "top_p": 1.0
            }
        }
        return assistants
    except Exception as e:
        print(f"Error obteniendo asistentes: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# ============================  
# HISTORIAL DE CONVERSACIONES
# ============================
@app.get("/api/conversations")
async def get_conversations(request: Request):
    """
    Devuelve el historial de conversaciones desde Cosmos DB
    """
    try:
        user_id = request.query_params.get("user_id")
        if not user_id:
            return JSONResponse(status_code=400, content={"error": "Falta user_id"})
        
        conversations = get_conversations_by_user(user_id)
        return conversations
    except Exception as e:
        print(f"❌ Error obteniendo historial:", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


# ============================
# RECUPERACIÓN DE CONVERSACIÓN
# ============================
@app.get("/api/conversations/{conversation_id}")
async def get_conversation_by_id(conversation_id: str):
    """
    Devuelve una conversación por ID desde Cosmos DB
    """
    try:
        conversation = get_conversation(conversation_id)
        if conversation:
            return {"conversation": conversation}
        else:
            return JSONResponse(status_code=404, content={"error": "Conversación no encontrada"})
    except Exception as e:
        print(f"❌ Error obteniendo conversación:", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


# ============================    
# ESTADÍSTICAS DE CONVERSACIÓN
# ============================
@app.get("/api/stats/{conversation_id}")
async def get_conversation_stats(conversation_id: str = PathParam(...)):
    """
    Devuelve estadísticas de una conversación
    """
    try:
        conversation = get_conversation(conversation_id)
        if not conversation:
            return JSONResponse(status_code=404, content={"error": "Conversación no encontrada"})

        total_input = total_output = total_cached = total_reasoning = total_time = total_cost = 0
        models_used = set()
        query_count = 0

        for msg in conversation.get("messages", []):
           if msg.get("role") == "assistant":
                query_count += 1
                metadata = msg.get("metadata", {})
                usage = metadata.get("usage", {})

                model = metadata.get("model", "unknown")
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
                cached_tokens = usage.get("cached_tokens", 0)
                reasoning_tokens = usage.get("reasoning_tokens", 0)
                message_time = metadata.get("total_time", 0)

                # ✅ CALCULAR COSTE: PRINCIPAL + SUB-AGENTES POR SEPARADO                     
                sub_agents_usage = usage.get("sub_agents_usage", [])
                
                # Coste del agente principal
                principal_cost_data = calculate_cost(model, input_tokens, output_tokens, cached_tokens, reasoning_tokens, pricing_dict = MODEL_PRICING)
                message_cost = principal_cost_data["total_cost"]
                models_used.add(principal_cost_data["model"])
                
                # Costes de cada sub-agente
                for sub_agent in sub_agents_usage:
                    sub_model = sub_agent.get("model", "gpt-4o") # "gpt-4o" como fallback
                    sub_input = sub_agent.get("prompt_tokens", 0)
                    input_tokens += sub_input 
                    sub_output = sub_agent.get("completion_tokens", 0)
                    output_tokens += sub_output
                    sub_cached = sub_agent.get("cached_tokens", 0)
                    sub_reasoning = sub_agent.get("reasoning_tokens", 0)
                    
                    sub_cost_data = calculate_cost(sub_model, sub_input, sub_output, sub_cached, sub_reasoning, pricing_dict = MODEL_PRICING)
                    message_cost += sub_cost_data["total_cost"]
                    models_used.add(sub_cost_data["model"])
                
                # Acumular totales
                last_input = input_tokens
                last_output = output_tokens
                total_input += input_tokens
                total_output += output_tokens
                total_cached += cached_tokens
                total_reasoning += reasoning_tokens
                total_time += message_time
                total_cost += message_cost

                avg_input = total_input / query_count if query_count else 0
                avg_output = total_output / query_count if query_count else 0
                avg_total = (total_input + total_output) / query_count if query_count else 0
                avg_cost = total_cost / query_count if query_count else 0
                avg_time = total_time / query_count if query_count else 0

                last_msg = conversation["messages"][-1] if conversation["messages"] else {}
                
                # Extraer modelos del último mensaje
                last_msg_models = set()
                if last_msg.get("role") == "assistant":
                    last_metadata = last_msg.get("metadata", {})
                    last_usage = last_metadata.get("usage", {})
                    
                    main_model = last_usage.get("model", last_metadata.get("model"))
                    if main_model:
                        last_msg_models.add(main_model)
                    
                    for sub_agent in last_usage.get("sub_agents_usage", []):
                        sub_model = sub_agent.get("model")
                        if sub_model:
                            last_msg_models.add(sub_model)

        return {
            "pricing_date": PRICING_DATE,
            "last_query": last_msg,
            "last_query_input": last_input,
            "last_query_output": last_output,
            "last_query_models": sorted(last_msg_models),
            "averages": {
                "avg_input": avg_input,
                "avg_output": avg_output,
                "avg_total": avg_total,
                "avg_cost": avg_cost,
                "avg_time": avg_time
            },
            "totals": {
                "queries": query_count,
                "messages": len(conversation["messages"]),
                "total_input": total_input,
                "total_output": total_output,
                "total_cached": total_cached,
                "total_reasoning": total_reasoning,
                "total_time": total_time,
                "total_cost": total_cost,
                "models_used": sorted(models_used)
            }
        }

    except Exception as e:
        print(f"Error en estadísticas: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# ============================
# SERVIR FRONTEND REACT
# ============================

# Verificar si existe el build de React
react_build_path = Path("react-app/build")

if react_build_path.exists() and react_build_path.is_dir():
    print("✅ Frontend React build encontrado, sirviendo archivos estáticos...")
    
    # Servir archivos estáticos (CSS, JS, imágenes)
    app.mount(
        "/static", 
        StaticFiles(directory="react-app/build/static"), 
        name="static"
    )
    
    # Servir otros archivos del build (manifest.json, robots.txt, etc.)
    @app.get("/manifest.json")
    async def serve_manifest():
        return FileResponse("react-app/build/manifest.json")
    
    @app.get("/favicon.ico")
    async def serve_favicon():
        favicon_path = Path("react-app/build/favicon.ico")
        if favicon_path.exists():
            return FileResponse(favicon_path)
        return JSONResponse(status_code=404, content={"error": "Favicon not found"})
    
    @app.get("/robots.txt")
    async def serve_robots():
        robots_path = Path("react-app/build/robots.txt")
        if robots_path.exists():
            return FileResponse(robots_path)
        return JSONResponse(status_code=404, content={"error": "Robots.txt not found"})
    
    # 🔧 CATCH-ALL ROUTE para React Router (SPA)
    # IMPORTANTE: Debe ir AL FINAL, después de todos los endpoints /api/*
    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        """
        Sirve la aplicación React para todas las rutas que no sean /api/*
        Esto permite que React Router funcione correctamente
        """
        # Si la ruta empieza con 'api/', ya fue manejada por los endpoints anteriores
        if full_path.startswith("api/"):
            return JSONResponse(
                status_code=404, 
                content={"error": "API endpoint not found"}
            )
        
        # Si el archivo específico existe, servirlo
        file_path = react_build_path / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        
        # Para cualquier otra ruta, servir index.html (SPA fallback)
        return FileResponse("react-app/build/index.html")

else:
    print("⚠️ No se encontró el build de React. El frontend no estará disponible.")
    print("   Ejecuta 'cd react-app && npm run build' para crear el build.")
    
    @app.get("/")
    async def root_no_frontend():
        return {
            "message": "Backend funcionando correctamente",
            "warning": "Frontend no disponible (falta build de React)",
            "instructions": "Ejecuta: cd react-app && npm run build"
        }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Iniciando servidor en puerto {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)