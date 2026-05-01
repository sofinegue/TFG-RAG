"""
CvsParallelStrategy — pipeline CVs en paralelo (clasificación por fiabilidad
+ mini-LLM en lotes + ensamblado final con LLM potente).

Aplica EXCLUSIVAMENTE a use_case="cvs" cuando el idioma NO es "es"
(por convenio, los CVs en inglés son los que disparan este flujo masivo).

Composición:
  · retrieve()       → búsqueda directa con CVS_TOP_K, sin RAG Fusion.
  · run_pipeline()   → clasificar + mini-LLM por grupos + format_final_response.
"""
from __future__ import annotations

from typing import Dict

from src.config import config
from src.rag.handler import get_handler
from src.rag.models.retriever import Retriever
from src.rag.strategies.base import BaseStrategy


class CvsParallelStrategy(BaseStrategy):
    """Pipeline CVs masivo (top_k alto + mini-LLM en paralelo)."""

    name = "cvs_parallel"

    def __init__(self) -> None:
        self._retriever = Retriever()

    def retrieve(self, state: Dict) -> Dict:
        # Forzamos siempre cvs_top_k y desactivamos fusion (aunque el use_case
        # ya lo haga, dejamos override explícito para claridad)
        override = {
            "top_k":               config.cvs_top_k,
            "min_relevance_score": 0.0,
            "max_chunks_used":     config.cvs_top_k,
            "use_rag_fusion":      False,
            "rag_fusion_queries":  1,
        }
        print(
            f"   🎯 Strategy=cvs_parallel (top_k={override['top_k']}, "
            f"chunk_size={config.cvs_chunk_size})"
        )
        return self._retriever.retrieve(state, retrieval_override=override)

    def has_custom_pipeline(self) -> bool:
        return True

    def run_pipeline(self, state: Dict) -> Dict:
        """
        Pipeline CVS completo (replica el antiguo nodo `process_cvs`):
          1. classify_chunks_by_reliability → 5 grupos
          2. grupo1: extracción directa / mini-LLM
          3. grupos 2-5: mini-LLM en lotes paralelos
          4. Persistir en historial JSON
          5. Response Format: LLM potente ensambla respuesta final
        """
        query   = state["query"]
        chunks  = state.get("chunks_retrieved", [])
        handler = get_handler("cvs")
        language = state.get("language", "en")

        print(f"   📊 Pipeline CVS: {len(chunks)} chunks → clasificar por fiabilidad")

        try:
            result = handler.process_query(query, chunks, language=language)
            groups = result["groups"]
            state["cvs_groups"] = groups

            for gname, g in groups.items():
                data  = g.get("data", "ninguno")
                count = (
                    len(data) if isinstance(data, list)
                    else (0 if data == "ninguno" else data.count("|") + 1)
                )
                print(f"      {gname} ({g.get('reliability','')}): {count} perfiles")

            print("   🎯 Response Format: ensamblando respuesta final...")
            answer, usage_info = handler.format_final_response(query, groups, language=language)

            state["answer"]       = answer
            state["chunks_used"]  = chunks
            state["metadata"]     = {
                "usage":        usage_info,
                "model":        usage_info.get("model", "unknown"),
                "use_case":     "cvs",
                "rag_mode":     state.get("rag_mode", "gpt"),
                "strategy":     self.name,
                "cvs_pipeline": True,
                "history_id":   result.get("history_id"),
            }
            print(
                f"      ✅ Respuesta CVS generada ({len(answer)} chars, "
                f"{usage_info.get('total_tokens', 0)} tokens)"
            )
        except Exception as e:
            print(f"   ❌ Error en pipeline CVS: {e}")
            import traceback; traceback.print_exc()
            state["error"]    = str(e)
            state["answer"]   = f"<p>❌ Error procesando CVs: {e}</p>"
            state["metadata"] = {"usage": {}, "error": str(e), "strategy": self.name}

        return state


__all__ = ["CvsParallelStrategy"]
