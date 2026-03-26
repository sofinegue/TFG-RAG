"""
Handler del caso de uso Wiki / Wikipedia.

Hereda de BaseUseCaseHandler e implementa o sobreescribe únicamente
los hooks específicos a respuestas enciclopédicas basadas en Wikipedia.
"""
from typing import Dict, List

from src.rag.handler.base import BaseUseCaseHandler
from src.rag.prompts.wiki_prompts import WikiPrompts


class WikiUseCaseHandler(BaseUseCaseHandler):
    """Handler especializado en respuestas enciclopédicas sobre artículos de Wikipedia."""

    use_case_id = "wiki"

    def __init__(self, index_name: str) -> None:
        self.index_name = index_name
        self.prompts    = WikiPrompts()

    # ── Prompts ────────────────────────────────────────────────────────

    def build_generation_prompt(
        self,
        query: str,
        context: List[Dict],
        max_chars: int,
    ) -> str:
        return self.prompts.generation(query, context, max_chars)

    def build_rag_fusion_prompt(self, query: str, k: int) -> str:
        return self.prompts.rag_fusion(query, k)

    # ── Sistema ────────────────────────────────────────────────────────

    def get_system_message(self) -> str:
        return (
            "Eres un asistente enciclopédico que responde preguntas de "
            "conocimiento general a partir de artículos de Wikipedia."
        )

    # ── Retrieval ──────────────────────────────────────────────────────
    # Sobreescribir get_retrieval_config() aquí si Wiki necesita un top_k
    # diferente o deshabilitar/habilitar RAG Fusion.

    # ── LLM ────────────────────────────────────────────────────────────
    # Sobreescribir get_llm_config() aquí si Wiki usa un modelo diferente.

    # ── Post-proceso ───────────────────────────────────────────────────
    # Sobreescribir post_process_answer() para formatear las fuentes, etc.
