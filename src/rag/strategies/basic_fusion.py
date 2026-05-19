"""
BasicFusionStrategy — RAG original con búsqueda híbrida + RAG Fusion
Aplica a los tres casos de uso (cvs, eu, wiki) cuando el idioma es "es"
Usa la configuración GLOBAL del .env (no la específica del handler):
  · top_k               = AZURE_SEARCH_TOP_K
  · max_chunks_used     = MAX_CHUNKS_USED
  · min_relevance_score = MIN_RELEVANCE_SCORE
  · use_rag_fusion      = USE_RAG_FUSION
  · rag_fusion_queries  = RAG_FUSION_QUERIES
Esto garantiza que aunque el use_case sea "cvs" (cuyo handler por defecto
pide cvs_top_k=200 y desactiva fusion), la versión "español" use los
parámetros del RAG original
"""
from __future__ import annotations
from src.config import config
from src.rag.models.retriever import Retriever
from src.rag.strategies.base import BaseStrategy
class BasicFusionStrategy(BaseStrategy):
    """RAG híbrido + RAG Fusion. Sin pipeline propio (usa Generator estándar)."""
    name = "basic_fusion"
    def __init__(self) -> None:
        self._retriever = Retriever()
    def retrieve(self, state: dict) -> dict:
        # Forzamos la config del RAG original aunque el use_case sea cvs
        override = {
            "top_k":               config.azure_search_top_k,
            "min_relevance_score": config.min_relevance_score,
            "max_chunks_used":     config.max_chunks_used,
            "use_rag_fusion":      config.use_rag_fusion,
            "rag_fusion_queries":  config.rag_fusion_queries,
        }
        print(
            f"   🎯 Strategy=basic_fusion (top_k={override['top_k']}, "
            f"max_chunks={override['max_chunks_used']}, fusion={override['use_rag_fusion']})"
        )
        return self._retriever.retrieve(state, retrieval_override=override)
__all__ = ["BasicFusionStrategy"]
