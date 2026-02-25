"""
Configuración centralizada RAG + Chunking
"""
import os
import json
from dataclasses import dataclass
from typing import Optional, Dict, List
from dotenv import load_dotenv

load_dotenv()

@dataclass
class ModelConfig:
    """Configuración de un modelo individual"""
    name: str
    api_base: str
    api_key: str
    api_version: str
    deployment: str
    api_type: str = "azure"

@dataclass
class RAGConfig:
    """Configuración completa del sistema RAG + Chunking"""
    
    # === IDENTIDAD DEL CLIENTE ===
    client_name: str = os.getenv("CLIENT_NAME", "Demo Client")
    project_name: str = os.getenv("PROJECT_NAME", "RAG Assistant")
    language: str = os.getenv("LANGUAGE", "es")

    # === AGENT BUILDER ===
    agent_builder_openai_api_key: str = os.getenv("AGENT_BUILDER_OPENAI_API_KEY")

    # === AZURE SEARCH ===
    azure_search_endpoint: str = os.getenv("AZURE_SEARCH_ENDPOINT")
    azure_search_key: str = os.getenv("AZURE_SEARCH_KEY")
    azure_search_index: str = os.getenv("AZURE_SEARCH_INDEX")
    azure_search_indexer: str = os.getenv("AZURE_SEARCH_INDEXER")
    azure_search_top_k: int = int(os.getenv("AZURE_SEARCH_TOP_K", "10"))
    
    # === MODELOS ===
    chat_model: str = os.getenv("CHAT_MODEL", "gpt4.1")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "ada-002")
    temperature: float = float(os.getenv("TEMPERATURE", "0.3"))
    max_tokens: int = int(os.getenv("MAX_TOKENS", "1500"))
    
    # === AZURE OPENAI (Chunking) ===
    azure_openai_url: str = os.getenv("AZURE_OPENAI_URL")
    azure_openai_key: str = os.getenv("AZURE_OPENAI_KEY")
    azure_openai_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    azure_openai_emb_deployment: str = os.getenv("AZURE_OPENAI_EMB_DEPLOYMENT")
    azure_openai_emb_name: str = os.getenv("AZURE_OPENAI_EMB_NAME", "text-embedding-ada-002")
    azure_openai_gpt4_1_name: str = os.getenv("AZURE_OPENAI_GPT4_1_NAME")
    azure_openai_mini_gpt4o_name: str = os.getenv("AZURE_OPENAI_Mini_GPT4o_NAME")
    
    # === DOCUMENT INTELLIGENCE ===
    doc_intel_url: str = os.getenv("DOC_INTEL_URL")
    doc_intel_key: str = os.getenv("DOC_INTEL_KEY")
    
    # === AZURE STORAGE ===
    azure_storage_account: str = os.getenv("AZURE_STORAGEACCOUNT")
    azure_storage_key: str = os.getenv("AZURE_STORAGEACCOUNT_KEY")
    azure_container_name: str = os.getenv("AZURE_STORAGE_NAME_INVESTIGATION", "plug-rag-docs")
    azure_container_configs: str = os.getenv("AZURE_CONTAINER_NAME_CONFIGS", "config-jsons")
    azure_storage_account_assistants: str = os.getenv("AZURE_STORAGE_ACCOUNT_Assistants")
    azure_storage_key_assistants: str = os.getenv("AZURE_STORAGE_KEY_Assistants")
    azure_container_name_assistants: str = os.getenv("AZURE_CONTAINER_NAME_Assistants")
    # azure_container_name_deleted_assistants: Optional[str] = os.getenv("AZURE_CONTAINER_NAME_Deleted_Assistants")  # Esta variable no existe en el .env
    # === COSMOS DB ===
    cosmos_endpoint: str = os.getenv("COSMOS_ENDPOINT")
    cosmos_key: str = os.getenv("COSMOS_KEY")
    cosmosdb_database: str = os.getenv("AZURE_COSMOSDB_DB_NAME", "RAG_DB")
    cosmosdb_container: str = os.getenv("AZURE_COSMOSDB_COLLECTION_NAME", "Chunks")
    cosmosdb_process_db: str = os.getenv("AZURE_COSMOSDB_PROCESSDOCUMENTS_DB_NAME")
    cosmosdb_process_container: str = os.getenv("AZURE_COSMOSDB_COLLECTION_PROCESSDOCUMENTS_NAME")
    
    # === GUARDRAILS ===
    enable_input_guardrails: bool = os.getenv("ENABLE_INPUT_GUARDRAILS", "true").lower() == "true"
    enable_output_guardrails: bool = os.getenv("ENABLE_OUTPUT_GUARDRAILS", "true").lower() == "true"
    enable_content_moderation: bool = os.getenv("ENABLE_CONTENT_MODERATION", "false").lower() == "true"
    enable_hallucination_check: bool = os.getenv("ENABLE_HALLUCINATION_CHECK", "true").lower() == "true"

    # === RETRIEVAL ===
    use_rag_fusion: bool = os.getenv("USE_RAG_FUSION", "true").lower() == "true"
    rag_fusion_queries: int = int(os.getenv("RAG_FUSION_QUERIES", "5"))
    max_chunks_used: int = int(os.getenv("MAX_CHUNKS_USED", "20"))
    min_relevance_score: float = float(os.getenv("MIN_RELEVANCE_SCORE", "0.7"))
    
    # === CHUNKING ===
    sublotes_flag: bool = bool(int(os.getenv("SUBLOTES_FLAG", "0")))
    max_workers_docs: int = int(os.getenv("MAX_WORKERS_DOCS", "3"))
    hour_diff: int = int(os.getenv("HOUR_DIFF", "0"))
    
    # === GENERACIÓN ===
    max_answer_chars: int = int(os.getenv("MAX_ANSWER_CHARS", "1200"))
    include_sources: bool = os.getenv("INCLUDE_SOURCES", "true").lower() == "true"
    stream_response: bool = os.getenv("STREAM_RESPONSE", "false").lower() == "true"
    
    # === AZURE OPENAI AGENT BUILDER ===
    azure_openai_agent_endpoint: str = os.getenv("AZURE_OPENAI_AGENT_ENDPOINT")
    azure_openai_agent_api_key: str = os.getenv("AZURE_OPENAI_AGENT_API_KEY")
    azure_openai_agent_api_version: str = os.getenv("AZURE_OPENAI_AGENT_API_VERSION", "2024-02-15-preview")
    azure_openai_agent_deployment: str = os.getenv("AZURE_OPENAI_AGENT_DEPLOYMENT")

    # Vector Store ID (tu file search)
    azure_openai_agent_vector_store_id: str = os.getenv("AZURE_OPENAI_AGENT_VECTOR_STORE_ID", "vs_7RP0nOpLfunf5hpJLmYvjcdU")
    
    # === UI ===
    ui_theme_color: str = os.getenv("UI_THEME_COLOR", "#1f77b4")
    ui_logo_url: Optional[str] = os.getenv("UI_LOGO_URL")
    ui_welcome_message: str = os.getenv(
        "UI_WELCOME_MESSAGE", 
        "¡Hola! Soy tu asistente RAG. ¿En qué puedo ayudarte?"
    )
    
    # === LOGGING ===
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    enable_kibana: bool = os.getenv("KIBANA_ACTIVE", "false").lower() == "true"
    kibana_endpoint_apis: Optional[str] = os.getenv("KIBANA_ENDPOINT_APIS")
    
    # === MODELOS CONFIG ===
    _models_config: Optional[List[Dict]] = None
    
    def __post_init__(self):
        """Validación de configuración obligatoria"""
        required = {
            "AZURE_SEARCH_ENDPOINT": self.azure_search_endpoint,
            "AZURE_SEARCH_KEY": self.azure_search_key,
            "COSMOS_ENDPOINT": self.cosmos_endpoint,
            "COSMOS_KEY": self.cosmos_key,
        }
        
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(f"Variables requeridas faltantes: {', '.join(missing)}")
        
        self._load_models_config()
    
    def _load_models_config(self):
        """Carga la configuración de modelos desde MODELS_CONFIG"""
        models_config_str = os.getenv("MODELS_CONFIG")
        if models_config_str:
            try:
                self._models_config = json.loads(models_config_str)
            except json.JSONDecodeError as e:
                raise ValueError(f"Error parseando MODELS_CONFIG: {e}")
        else:
            self._models_config = []
    
    def get_model_config(self, model_name: str) -> ModelConfig:
        """Obtiene la configuración de un modelo específico"""
        if not self._models_config:
            raise ValueError("No hay modelos configurados en MODELS_CONFIG")
        
        for model in self._models_config:
            if model.get("name") == model_name:
                return ModelConfig(
                    name=model["name"],
                    api_base=model["api_base"],
                    api_key=model["api_key"],
                    api_version=model["api_version"],
                    deployment=model["deployment"],
                    api_type=model.get("api_type", "azure")
                )
        
        raise ValueError(f"Modelo '{model_name}' no encontrado en MODELS_CONFIG")
    
    def get_chat_model_config(self) -> ModelConfig:
        """Obtiene la configuración del modelo de chat actual"""
        return self.get_model_config(self.chat_model)
    
    def get_embedding_model_config(self) -> ModelConfig:
        """Obtiene la configuración del modelo de embeddings actual"""
        return self.get_model_config(self.embedding_model)

    @property
    def azure_storage_account_assistants(self) -> str:
        return self.azure_storage_account_assistants

    @property
    def azure_storage_key_assistants(self) -> str:
        return self.azure_storage_key_assistants

    @property
    def azure_container_assistants(self) -> str:
        return self.azure_container_name_assistants

    @property
    def azure_container_deleted_assistants(self) -> Optional[str]:
        return self.azure_container_name_deleted_assistants

# Instancia global
config = RAGConfig()

# Crear alias Config para compatibilidad con código de chunking
Config = config