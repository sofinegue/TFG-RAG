"""
BaseUseCaseHandler — Template Method Pattern.

Define el esqueleto completo de la pipeline RAG. Las subclases concretas
sobreescriben únicamente los ganchos (hooks) necesarios para sus casos de uso.

  OBLIGATORIO sobreescribir
  ─────────────────────────
  · build_generation_prompt()   → prompt principal enviado al LLM
  · use_case_id                 → atributo de clase: "cvs" | "eu" | "wiki"
  · index_name                  → atributo de instancia (inicializar en __init__)

  OPCIONAL sobreescribir (implementación por defecto disponible)
  ──────────────────────────────────────────────────────────────
  PROMPTS
  · build_rag_fusion_prompt()   → prompt para generar queries sintéticas
  · get_system_message()        → system prompt del LLM

  RETRIEVAL
  · get_retrieval_config()      → top_k, min_score, rag_fusion, etc.
  · search_select_fields        → columnas solicitadas a Azure Search
  · parse_search_result()       → mapeo de documento Azure Search → chunk interno

  GENERACIÓN LLM
  · get_llm_config()            → modelo, temperatura, max_tokens, etc.
  · post_process_answer()       → post-procesado de la respuesta antes de devolverla
"""
from abc import ABC, abstractmethod
from typing import Dict, List


class BaseUseCaseHandler(ABC):
    """
    Implementa el Template Method Pattern para los casos de uso del RAG.
    Cada subclase representa un dominio (CVs, EU, Wiki) y sobreescribe
    únicamente los hooks relevantes a su lógica.
    """

    use_case_id: str   # atributo de clase — "cvs" | "eu" | "wiki"
    index_name:  str   # atributo de instancia — nombre del índice Azure Search

    # ══════════════════════════════════════════════════════════════════
    # MÉTODO ABSTRACTO (obligatorio)
    # ══════════════════════════════════════════════════════════════════

    @abstractmethod
    def build_generation_prompt(
        self,
        query: str,
        context: List[Dict],
        max_chars: int,
        language: str = "es",
    ) -> str:
        """
        Construye el prompt principal que recibirá el LLM junto con los
        chunks recuperados de Azure Search.
        """
        ...

    # ══════════════════════════════════════════════════════════════════
    # HOOKS DE PROMPT (opcionales)
    # ══════════════════════════════════════════════════════════════════

    def build_rag_fusion_prompt(self, query: str, k: int) -> str:
        """
        Prompt para generar k queries sintéticas (RAG Fusion).
        Sobreescribir para adaptar el dominio, idioma o estilo.
        """
        from src.config import config
        lang_map = {"es": "en español", "en": "in English", "pt": "em português"}
        lang = lang_map.get(config.language, "en español")

        return f"""Eres un experto en reformular preguntas para mejorar búsquedas de información.

Pregunta original: "{query}"

Genera {k} versiones alternativas de esta pregunta que:
- Mantengan la intención original
- Usen sinónimos y diferentes estructuras gramaticales
- Exploren diferentes perspectivas del tema
- Sean claras y específicas

Responde ÚNICAMENTE con las {k} preguntas reformuladas, una por línea, numeradas.
Escribe todo {lang}.

Ejemplo:
1. [primera reformulación]
2. [segunda reformulación]
..."""

    def get_system_message(self) -> str:
        """
        System prompt del LLM al generar la respuesta.
        Sobreescribir para personalizar el rol o las restricciones del asistente.
        """
        return (
            "Eres un asistente experto que responde preguntas "
            "basándose en el contexto proporcionado."
        )

    def post_process_answer(self, answer: str) -> str:
        """
        Post-procesado de la respuesta del LLM antes de devolverla al usuario.
        Por defecto no modifica nada. Sobreescribir para limpiar, formatear, etc.
        """
        return answer

    # ══════════════════════════════════════════════════════════════════
    # HOOKS DE RETRIEVAL (opcionales)
    # ══════════════════════════════════════════════════════════════════

    def get_retrieval_config(self) -> Dict:
        """
        Parámetros de retrieval para este caso de uso.
        Sobreescribir para ajustar top_k, min_score, use_rag_fusion, etc.
        """
        from src.config import config
        return {
            "top_k":               config.azure_search_top_k,
            "min_relevance_score": config.min_relevance_score,
            "max_chunks_used":     config.max_chunks_used,
            "use_rag_fusion":      config.use_rag_fusion,
            "rag_fusion_queries":  config.rag_fusion_queries,
        }

    @property
    def search_select_fields(self) -> List[str]:
        """
        Columnas que se solicitan a Azure Search en cada query.
        Sobreescribir si el esquema del índice contiene campos distintos.
        """
        return ["id", "chunkId", "content", "Title", "docTitle"]

    def parse_search_result(self, result) -> Dict:
        """
        Transforma un documento de Azure Search al formato interno de chunk.
        Sobreescribir si el esquema del índice difiere de las keys por defecto.
        """
        return {
            "chunk_id":       result.get("chunkId") or result.get("id"),
            "id":             result.get("id"),
            "content":        result.get("content") or result.get("sectionContent", ""),
            "title":          result.get("Title", ""),
            "doc_title":      result.get("docTitle", ""),
            "pages":          result.get("Pages", "N/A"),
            "score":          result.get("@search.score", 0),
            "reranker_score": 1.0,
        }

    # ══════════════════════════════════════════════════════════════════
    # HOOKS DE GENERACIÓN LLM (opcionales)
    # ══════════════════════════════════════════════════════════════════

    def get_llm_config(self) -> Dict:
        """
        Configuración del LLM para este caso de uso.
        Sobreescribir para usar un modelo, temperatura o token budget distinto.
        Los valores de gpt_config enviados por el cliente tienen siempre
        prioridad sobre estos defaults.
        """
        from src.config import config
        return {
            "model":             config.chat_model,
            "temperature":       config.temperature,
            "max_tokens":        config.max_tokens,
            "top_p":             0.95,
            "frequency_penalty": 0.0,
            "presence_penalty":  0.0,
        }
