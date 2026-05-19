"""
DocumentHandler — handler unificado para casos de uso documentales (EU y Wikipedia)
Ambos casos de uso siguen el mismo flujo RAG estándar (retrieve → generate),
sin pipeline especializado. La diferencia entre ellos reside en los prompts
y el system message, que se seleccionan según el atributo `use_case`
  use_case = "eu"   → EUPrompts   + system message legal
  use_case = "wiki" → WikiPrompts + system message enciclopédico
"""
from src.rag.handler.base import BaseUseCaseHandler
from src.rag.prompts.eu_prompts import EUPrompts
from src.rag.prompts.wiki_prompts import WikiPrompts
# Mapeo de use_case → clase de prompts
_PROMPTS_MAP = {
    "eu":   EUPrompts,
    "wiki": WikiPrompts,
}
# System messages por caso de uso
_SYSTEM_MESSAGES = {
    "eu": (
        "Eres un experto en legislación y documentos institucionales "
        "de la Unión Europea. Respondes con precisión legal."
    ),
    "wiki": (
        "Eres un asistente enciclopédico que responde preguntas de "
        "conocimiento general a partir de artículos de Wikipedia."
    ),
}
class DocumentHandler(BaseUseCaseHandler):
    """
    Handler genérico para casos de uso documentales
    Se instancia una vez por cada caso de uso (eu, wiki) con su propio
    index_name. Los prompts y system message se adaptan al dominio
    mediante el atributo `use_case`
    """
    def __init__(self, use_case: str, index_name: str) -> None:
        self.use_case_id = use_case
        self.use_case    = use_case
        self.index_name  = index_name
        prompts_cls = _PROMPTS_MAP.get(use_case)
        if prompts_cls is None:
            raise KeyError(
                f"No hay prompts configurados para use_case='{use_case}'. "
                f"Opciones: {list(_PROMPTS_MAP.keys())}"
            )
        self.prompts = prompts_cls()
    # ── Prompts ────────────────────────────────────────────────────────
    def build_generation_prompt(
        self,
        query: str,
        context: list[dict],
        max_chars: int,
        language: str = "es",
    ) -> str:
        return self.prompts.generation(query, context, max_chars, language=language)
    def build_rag_fusion_prompt(self, query: str, k: int) -> str:
        return self.prompts.rag_fusion(query, k)
    # ── Sistema ────────────────────────────────────────────────────────
    def get_system_message(self) -> str:
        return _SYSTEM_MESSAGES.get(
            self.use_case,
            "Eres un asistente experto que responde preguntas "
            "basándose en el contexto proporcionado.",
        )
