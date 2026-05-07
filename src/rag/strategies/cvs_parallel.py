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
        # cvs_parallel usa top_k alto (300) para cobertura total del corpus;
        # el resto de flujos CVs sigue usando cvs_top_k (40-50).
        parallel_top_k = config.cvs_parallel_top_k
        override = {
            "top_k":               parallel_top_k,
            "min_relevance_score": 0.0,
            "max_chunks_used":     parallel_top_k,
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
                data        = g.get("data", "ninguno")
                n_profiles  = (
                    len(data) if isinstance(data, list)
                    else (0 if data in ("ninguno", "") else data.count("|") + 1)
                )
                n_chunks    = g.get("input_chunks", len(g.get("data", [])) if isinstance(g.get("data"), list) else 0)
                kw_info     = f", {g['kw_matches']} kw" if g.get("kw_matches") else ""
                calls_info  = f", {g['mini_calls']} batch(es)" if g.get("mini_calls") else ""
                print(f"      {gname} ({g.get('reliability','')}): {n_chunks} chunks → {n_profiles} perfiles{kw_info}{calls_info}")

            print("   🎯 Response Format: ensamblando respuesta final...")
            answer, usage_info = handler.format_final_response(query, groups, language=language)

            # Incorporar uso del mini-LLM al metadata
            mini_usage = result.get("mini_llm_usage", {})
            if mini_usage.get("num_calls", 0) > 0:
                usage_info["mini_prompt_tokens"]     = mini_usage["prompt_tokens"]
                usage_info["mini_completion_tokens"] = mini_usage["completion_tokens"]
                usage_info["mini_num_calls"]          = mini_usage["num_calls"]
                # Tokens totales = final + mini
                usage_info["prompt_tokens"]     = usage_info.get("prompt_tokens", 0)     + mini_usage["prompt_tokens"]
                usage_info["completion_tokens"] = usage_info.get("completion_tokens", 0) + mini_usage["completion_tokens"]
                usage_info["total_tokens"]      = usage_info.get("total_tokens", 0)       + mini_usage["prompt_tokens"] + mini_usage["completion_tokens"]

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
