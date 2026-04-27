"""
Handler del caso de uso EU / Legislación de la Unión Europea.

Hereda de BaseUseCaseHandler e implementa o sobreescribe únicamente
los hooks específicos a consultas sobre normativa y documentos de la UE.
"""
from typing import Dict, List

from src.rag.handler.base import BaseUseCaseHandler
from src.rag.prompts.eu_prompts import EUPrompts


class EUUseCaseHandler(BaseUseCaseHandler):
    """Handler especializado en consultas sobre legislación y documentos de la UE."""

    use_case_id = "eu"

    def __init__(self, index_name: str) -> None:
        self.index_name = index_name
        self.prompts    = EUPrompts()

    # ── Prompts ────────────────────────────────────────────────────────

    def build_generation_prompt(
        self,
        query: str,
        context: List[Dict],
        max_chars: int,
        language: str = "es",
    ) -> str:
        return self.prompts.generation(query, context, max_chars, language=language)

    def build_rag_fusion_prompt(self, query: str, k: int) -> str:
        return self.prompts.rag_fusion(query, k)

    # ── Sistema ────────────────────────────────────────────────────────

    def get_system_message(self) -> str:
        return (
            "Eres un experto en legislación y documentos institucionales "
            "de la Unión Europea. Respondes con precisión legal."
        )

    # ── Retrieval ──────────────────────────────────────────────────────
    # Sobreescribir get_retrieval_config() aquí si EU necesita ajustar
    # el número de chunks, el score mínimo de relevancia, etc.

    # ── LLM ────────────────────────────────────────────────────────────
    # Sobreescribir get_llm_config() aquí si EU requiere más tokens
    # de respuesta o temperatura más baja para mayor precisión legal.

    # ── Post-proceso ───────────────────────────────────────────────────
    # Sobreescribir post_process_answer() para formatear citas legales,
    # añadir disclaimers, etc.
