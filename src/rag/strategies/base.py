"""
BaseStrategy — interfaz común a todas las estrategias de retrieval/processing.

Cada estrategia encapsula DÓNDE y CÓMO se obtienen los chunks de contexto y,
opcionalmente, un post-pipeline propio (p. ej. clasificación por fiabilidad
+ mini-LLM en lotes para CVs) que sustituye al `Generator` estándar.

Casos cubiertos:
  · BasicFusionStrategy : RAG original con búsqueda híbrida + RAG Fusion
                          (3 casos de uso, idioma español)
  · CvsParallelStrategy : pipeline CVs por fiabilidad y mini-LLM en paralelo
                          (cvs, idioma != español)
  · GraphRagStrategy    : búsqueda sobre Knowledge Graph en Neo4j (Graphiti)
                          (eu/wiki, idioma != español)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List


class BaseStrategy(ABC):
    """Estrategia de retrieval (+ post-processing opcional)."""

    name: str = "base"

    @abstractmethod
    def retrieve(self, state: Dict) -> Dict:
        """
        Recupera contexto a partir de `state["query"]` y devuelve:
          {
            "synthetic_queries": [...],
            "chunks_retrieved":  [chunk_dict, ...],
          }
        """
        ...

    def has_custom_pipeline(self) -> bool:
        """
        True si la estrategia trae su propia generación de respuesta
        (sustituye al nodo `generate` estándar). Por defecto False.
        """
        return False

    def run_pipeline(self, state: Dict) -> Dict:
        """
        Pipeline de respuesta propio (solo si has_custom_pipeline()==True).
        Debe rellenar state["answer"], state["chunks_used"] y state["metadata"].
        """
        return state


__all__ = ["BaseStrategy"]
