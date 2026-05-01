"""
Router de estrategias RAG.

Selecciona la estrategia correcta a partir de (use_case, language):

    ┌────────┬──────────┬──────────────────────┐
    │ use_case│ language │ Estrategia          │
    ├────────┼──────────┼──────────────────────┤
    │ cvs    │ es       │ basic_fusion         │
    │ cvs    │ ≠ es     │ cvs_parallel         │
    │ eu     │ es       │ basic_fusion         │
    │ eu     │ ≠ es     │ graph_rag (EU)       │
    │ wiki   │ es       │ basic_fusion         │
    │ wiki   │ ≠ es     │ graph_rag (Wiki)     │
    └────────┴──────────┴──────────────────────┘
"""
from __future__ import annotations

from src.rag.strategies.base import BaseStrategy
from src.rag.strategies.basic_fusion import BasicFusionStrategy
from src.rag.strategies.cvs_parallel import CvsParallelStrategy
from src.rag.strategies.graph_rag import GraphRagStrategy


# Singletons (se instancian de forma perezosa)
_basic_fusion: BasicFusionStrategy | None = None
_cvs_parallel: CvsParallelStrategy | None = None
_graph_rag:    GraphRagStrategy    | None = None


def _get_basic_fusion() -> BasicFusionStrategy:
    global _basic_fusion
    if _basic_fusion is None:
        _basic_fusion = BasicFusionStrategy()
    return _basic_fusion


def _get_cvs_parallel() -> CvsParallelStrategy:
    global _cvs_parallel
    if _cvs_parallel is None:
        _cvs_parallel = CvsParallelStrategy()
    return _cvs_parallel


def _get_graph_rag() -> GraphRagStrategy:
    global _graph_rag
    if _graph_rag is None:
        _graph_rag = GraphRagStrategy()
    return _graph_rag


def get_strategy(use_case: str, language: str) -> BaseStrategy:
    """Devuelve la estrategia correspondiente a (use_case, language)."""
    use_case = (use_case or "cvs").lower()
    language = (language or "es").lower()

    if language == "es":
        return _get_basic_fusion()

    if use_case == "cvs":
        return _get_cvs_parallel()

    if use_case in ("eu", "wiki"):
        return _get_graph_rag()

    # Fallback seguro
    return _get_basic_fusion()


__all__ = ["BaseStrategy", "get_strategy"]
