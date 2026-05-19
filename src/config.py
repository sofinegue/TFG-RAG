"""
Configuración centralizada RAG + Chunking
"""
import os
import json
from dataclasses import dataclass
from typing import Optional

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
    project_name: str = os.getenv("PROJECT_NAME")
    language: str = os.getenv("LANGUAGE")
    # === NOMBRES DE IDIOMAS ===
    # Se usa en los prompts para indicar al LLM en qué idioma responder.
    _lang_names_raw: str = os.getenv("LANG_NAMES")
    lang_names: dict[str, str] = None

    # === AGENT BUILDER ===
    agent_builder_openai_api_key: str = os.getenv("AGENT_BUILDER_OPENAI_API_KEY")

    # === AZURE SEARCH ===
    azure_search_endpoint: str = os.getenv("AZURE_SEARCH_ENDPOINT")
    azure_search_key: str = os.getenv("AZURE_SEARCH_KEY")
    azure_search_top_k: int = int(os.getenv("AZURE_SEARCH_TOP_K"))

    azure_search_index_cvs: str = os.getenv("AZURE_SEARCH_INDEX_CVS")
    azure_search_index_eu: str = os.getenv("AZURE_SEARCH_INDEX_EU")
    azure_search_index_wiki: str = os.getenv("AZURE_SEARCH_INDEX_WIKI")
    azure_search_indexer_cvs: str = os.getenv("AZURE_SEARCH_INDEXER_CVS")
    azure_search_indexer_eu: str = os.getenv("AZURE_SEARCH_INDEXER_EU")
    azure_search_indexer_wiki: str = os.getenv("AZURE_SEARCH_INDEXER_WIKI")
    azure_search_index: str = os.getenv("AZURE_SEARCH_INDEX")

    # === MODELOS ===
    chat_model: str = os.getenv("CHAT_MODEL")
    embedding_model: str = os.getenv("EMBEDDING_MODEL")
    tiktoken_model: str = os.getenv("TIKTOKEN_MODEL")
    temperature: float = float(os.getenv("TEMPERATURE"))
    max_tokens: int = int(os.getenv("MAX_TOKENS"))
    _models_config: Optional[list[dict]] = None

    # === AZURE OPENAI (Chunking) ===
    azure_openai_url: str = os.getenv("AZURE_OPENAI_URL")
    azure_openai_key: str = os.getenv("AZURE_OPENAI_KEY")
    azure_openai_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION")
    azure_openai_emb_deployment: str = os.getenv("AZURE_OPENAI_EMB_DEPLOYMENT")
    azure_openai_emb_name: str = os.getenv("AZURE_OPENAI_EMB_NAME")
    azure_openai_mini_name: str = os.getenv("AZURE_OPENAI_MINI_NAME")

    # === AZURE DOCUMENT INTELLIGENCE ===
    doc_intel_url: str = os.getenv("DOC_INTEL_URL")
    doc_intel_key: str = os.getenv("DOC_INTEL_KEY")

    # === AZURE BLOB STORAGE ===
    azure_storage_account_name: str = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
    azure_storage_account: str = os.getenv("AZURE_STORAGE_ACCOUNT")
    azure_storage_key: str = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
    azure_container_name: str = os.getenv("AZURE_CONTAINER_NAME")

    # === AZURE COSMOS DB ===
    cosmos_endpoint: str = os.getenv("COSMOS_ENDPOINT")
    cosmos_key: str = os.getenv("COSMOS_KEY")
    cosmosdb_database: str = os.getenv("AZURE_COSMOSDB_DB_NAME")
    cosmosdb_container_cvs: str = os.getenv("AZURE_COSMOSDB_COLLECTION_CVS")
    cosmosdb_container_eu: str = os.getenv("AZURE_COSMOSDB_COLLECTION_EU")
    cosmosdb_container_wiki: str = os.getenv("AZURE_COSMOSDB_COLLECTION_WIKI")

    # === GUARDRAILS ===
    enable_input_guardrails: bool = os.getenv("ENABLE_INPUT_GUARDRAILS").lower() == "true"
    enable_output_guardrails: bool = os.getenv("ENABLE_OUTPUT_GUARDRAILS").lower() == "true"
    enable_content_moderation: bool = os.getenv("ENABLE_CONTENT_MODERATION").lower() == "true"
    enable_hallucination_check: bool = os.getenv("ENABLE_HALLUCINATION_CHECK").lower() == "true"

    # === RETRIEVAL — RAG ORIGINAL (basic_fusion) ===
    use_rag_fusion: bool = os.getenv("USE_RAG_FUSION").lower() == "true"
    rag_fusion_queries: int = int(os.getenv("RAG_FUSION_QUERIES"))
    max_chunks_used: int = int(os.getenv("MAX_CHUNKS_USED"))
    min_relevance_score: float = float(os.getenv("MIN_RELEVANCE_SCORE"))


    # === RETRIEVAL — GRAPH RAG (Neo4j Graphiti) ===
    graph_rag_top_k: int = int(os.getenv("GRAPH_RAG_TOP_K"))
    graph_rag_max_chunks: int = int(os.getenv("GRAPH_RAG_MAX_CHUNKS"))
    graph_rag_min_score: float = float(os.getenv("GRAPH_RAG_MIN_SCORE"))
    graph_rag_mode: str = os.getenv("GRAPH_RAG_MODE")

    # === CVs – RETRIEVAL MASIVO ===
    cvs_top_k: int = int(os.getenv("AZURE_SEARCH_TOP_K_CVS"))
    cvs_parallel_top_k: int = int(os.getenv("CVS_PARALLEL_TOP_K"))
    cvs_chunk_size: int = int(os.getenv("CVS_CHUNK_SIZE"))
    cvs_history_path: str = os.getenv("CVS_HISTORY_PATH")
    cvs_group1_use_llm: bool = os.getenv("CVS_GROUP1_USE_LLM").lower() == "true"

    # === CVs – FIABILIDAD ===
    # Umbrales de score para clasificar chunks en 5 TRAMOS de fiabilidad.
    # T1 es el umbral más alto (mayor fiabilidad), T4 el más bajo:
    cvs_reliability_t1: float = float(os.getenv("CVS_RELIABILITY_T1"))
    cvs_reliability_t2: float = float(os.getenv("CVS_RELIABILITY_T2"))
    cvs_reliability_t3: float = float(os.getenv("CVS_RELIABILITY_T3"))
    cvs_reliability_t4: float = float(os.getenv("CVS_RELIABILITY_T4"))
    cvs_reliability_t5: float = float(os.getenv("CVS_RELIABILITY_T5"))

    # === CHUNKING ===
    sublotes_flag: bool = bool(int(os.getenv("SUBLOTES_FLAG")))
    max_workers_docs: int = int(os.getenv("MAX_WORKERS_DOCS"))
    hour_diff: int = int(os.getenv("HOUR_DIFF"))

    # === GENERACIÓN ===
    max_answer_chars: int = int(os.getenv("MAX_ANSWER_CHARS"))
    include_sources: bool = os.getenv("INCLUDE_SOURCES").lower() == "true"
    stream_response: bool = os.getenv("STREAM_RESPONSE").lower() == "true"

    # === AZURE OPENAI AGENT BUILDER ===
    azure_openai_agent_endpoint: str = os.getenv("AZURE_OPENAI_AGENT_ENDPOINT")
    azure_openai_agent_api_key: str = os.getenv("AZURE_OPENAI_AGENT_API_KEY")
    azure_openai_agent_api_version: str = os.getenv("AZURE_OPENAI_AGENT_API_VERSION")
    azure_openai_agent_deployment: str = os.getenv("AZURE_OPENAI_AGENT_DEPLOYMENT")
    azure_openai_agent_vector_store_id: str = os.getenv("AZURE_OPENAI_AGENT_VECTOR_STORE_ID")

    # === UI ===
    ui_theme_color: str = os.getenv("UI_THEME_COLOR")
    ui_logo_url: Optional[str] = os.getenv("UI_LOGO_URL")
    ui_welcome_message: str = os.getenv("UI_WELCOME_MESSAGE")

    # === NEO4J (Graphiti Knowledge Graph) ===
    # Conexión compartida (una sola instancia Neo4j)
    neo4j_uri: str = os.getenv("NEO4J_URI").strip()
    neo4j_user: str = os.getenv("NEO4J_USER").strip()
    neo4j_password: str = os.getenv("NEO4J_PASSWORD").strip()
    neo4j_wiki_database: str = os.getenv("NEO4J_WIKI_DATABASE").strip()
    neo4j_eu_database: str = os.getenv("NEO4J_EU_DATABASE").strip()

    # === LOGGING ===
    log_level: str = os.getenv("LOG_LEVEL")
    enable_kibana: bool = os.getenv("KIBANA_ACTIVE").lower() == "true"
    kibana_endpoint_apis: Optional[str] = os.getenv("KIBANA_ENDPOINT_APIS")

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
        self._load_lang_names()
        self._load_models_config()

    def _load_lang_names(self):
        """Carga el mapeo de nombres de idiomas desde LANG_NAMES"""
        try:
            self.lang_names = json.loads(self._lang_names_raw)
        except (json.JSONDecodeError, TypeError):
            self.lang_names = {
                "es": "español", "en": "English",
                "fr": "français", "it": "italiano", "pt": "português",
            }

    def get_lang_name(self, code: str) -> str:
        """
        Devuelve el nombre legible de un idioma dado su código ISO 639-1
        
        Args:
            code (str): Código de idioma (ej. "es", "en", "fr")

        Returns:
            str: Nombre legible del idioma (ej. "español", "English",
        """
        return self.lang_names.get(code, "español")

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
        """
        Obtiene la configuración de un modelo específico

        Args:
            model_name (str): Nombre del modelo

        Returns:
            ModelConfig: Configuración del modelo

        Raises:
            ValueError: Si no se encuentra el modelo o no hay modelos configurados
        """
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
        """
        Obtiene la configuración del modelo de chat actual

        Returns:
            ModelConfig: Configuración del modelo de chat
        """
        return self.get_model_config(self.chat_model)

    def get_embedding_model_config(self) -> ModelConfig:
        """
        Obtiene la configuración del modelo de embeddings actual

        Returns:
            ModelConfig: Configuración del modelo de embeddings
        """
        return self.get_model_config(self.embedding_model)

# Instancia global
config = RAGConfig()
# Compatibilidad con modelos de razonamiento (o-series, gpt-5-*)
# Estos modelos solo admiten los valores por defecto de temperature/top_p/etc.
# Cualquier otro valor provoca BadRequestError 400.
_REASONING_PREFIXES = ("o1", "o2", "o3", "o4", "gpt-5")

def is_reasoning_model(model_name: str) -> bool:
    """
    True si el nombre de modelo corresponde a un modelo de razonamiento

    Args:
        model_name (str): Nombre del modelo

    Returns:
        bool: True si el modelo es de razonamiento, False en caso contrario
    """
    if not model_name:
        return False
    n = model_name.lower().strip()
    return any(
        n == p or n.startswith(p + "-") or n.startswith(p + ".")
        for p in _REASONING_PREFIXES
    )
def safe_create_kwargs(**kwargs) -> dict:
    """
    Elimina parámetros no soportados por modelos de razonamiento. Para usarla:
    response = client.chat.completions.create(**safe_create_kwargs(model=..., temperature=0.3, ...))

    Args:
        **kwargs: Parámetros a pasar a la función de creación de completions

    Returns:
        dict: Diccionario de parámetros filtrados
    """
    # Resolver el deployment al nombre de modelo si está disponible
    model = kwargs.get("model", "")
    if is_reasoning_model(model):
        for param in ("temperature", "top_p", "frequency_penalty", "presence_penalty"):
            kwargs.pop(param, None)
    return kwargs
