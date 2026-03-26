"""
Registro central de handlers por caso de uso.

Uso:
    from src.rag.handler import get_handler

    handler = get_handler("cvs")
    prompt  = handler.build_generation_prompt(query, context, max_chars)
    index   = handler.index_name
    cfg     = handler.get_retrieval_config()
    llm_cfg = handler.get_llm_config()
"""
from src.config import config
from src.rag.handler.base import BaseUseCaseHandler
from src.rag.handler.cvs_handler import CVsUseCaseHandler
from src.rag.handler.eu_handler import EUUseCaseHandler
from src.rag.handler.wiki_handler import WikiUseCaseHandler

_REGISTRY: dict[str, BaseUseCaseHandler] = {
    "cvs":  CVsUseCaseHandler(config.azure_search_index_cvs),
    "eu":   EUUseCaseHandler(config.azure_search_index_eu),
    "wiki": WikiUseCaseHandler(config.azure_search_index_wiki),
}


def get_handler(use_case: str) -> BaseUseCaseHandler:
    """
    Devuelve el handler registrado para el caso de uso indicado.
    Lanza KeyError si el use_case no está registrado.
    """
    handler = _REGISTRY.get(use_case)
    if handler is None:
        raise KeyError(
            f"Caso de uso '{use_case}' no registrado. "
            f"Opciones disponibles: {list(_REGISTRY.keys())}"
        )
    return handler


def list_use_cases() -> list[str]:
    """Devuelve los IDs de todos los casos de uso registrados."""
    return list(_REGISTRY.keys())


__all__ = ["get_handler", "list_use_cases", "BaseUseCaseHandler",
           "CVsUseCaseHandler", "EUUseCaseHandler", "WikiUseCaseHandler"]
