"""
Handler del caso de uso CVs.

Flujo (ver diagrama):
  1. Retrieve  — búsqueda directa sin RAG Fusion, CVS_TOP_K chunks
  2. Generate  — los chunks se separan en 5 grupos de fiabilidad según su
                 score de Azure Search; el grupo ≥ 90 % se resuelve
                 extrayendo nombres directamente; el resto se pasa en lotes
                 a un mini-LLM.  n_llamadas = len(chunks_grupo) / CVS_CHUNK_SIZE
  3. Historial — cada consulta se persiste en cvs_history.json con campos
                 data, reasoning y reliability separados por grupo.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

from openai import AzureOpenAI

from src.config import config
from src.rag.handler.base import BaseUseCaseHandler
from src.rag.handler.cvs_history import CvsHistory
from src.rag.prompts.cvs_prompts import CVsPrompts


# ---------------------------------------------------------------------------
# Etiquetas de los 5 grupos de fiabilidad
# ---------------------------------------------------------------------------
def _build_reliability_labels() -> Dict[str, str]:
    t1 = config.cvs_reliability_t1
    t2 = config.cvs_reliability_t2
    t3 = config.cvs_reliability_t3
    t4 = config.cvs_reliability_t4
    return {
        "grupo1": f"≥{t1:.0%}",
        "grupo2": f"{t2:.0%}–{t1:.0%}",
        "grupo3": f"{t3:.0%}–{t2:.0%}",
        "grupo4": f"{t4:.0%}–{t3:.0%}",
        "grupo5": f"<{t4:.0%}",
    }


class CVsUseCaseHandler(BaseUseCaseHandler):
    """Handler especializado en búsqueda de perfiles profesionales sobre un corpus de CVs de la compañía."""

    use_case_id = "cvs"

    def __init__(self, index_name: str) -> None:
        self.index_name        = index_name
        self.prompts           = CVsPrompts()
        self.history           = CvsHistory(config.cvs_history_path)
        self.reliability_labels = _build_reliability_labels()

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
            "Eres un asistente especializado en análisis de CVs técnicos "
            "de los miembros de la compañía."
        )

    # ── Retrieval ──────────────────────────────────────────────────────

    def get_retrieval_config(self) -> Dict:
        """
        CVs usa búsqueda directa con alto top_k y sin RAG Fusion,
        para maximizar la cobertura de perfiles a costa de precisión.
        """
        return {
            "top_k":               config.cvs_top_k,
            "min_relevance_score": 0.0,       # sin filtrado mínimo: queremos todos
            "max_chunks_used":     config.cvs_top_k,
            "use_rag_fusion":      False,      # sin expansión de queries
            "rag_fusion_queries":  1,
        }

    # ── Extracción de nombre del contenido del chunk ───────────────────

    @staticmethod
    def _extract_name_from_chunk(chunk: Dict) -> str:
        """
        Extrae nombre_apellidos del contenido del chunk.
        Busca patrones como 'NOMBRE_APELLIDOS: ...' o 'nombre_apellidos: ...'
        dentro del texto. Si no lo encuentra, intenta extraer un nombre
        propio con regex de capitalización.
        """
        content = chunk.get("content", "")

        # Patrón 1: campo explícito NOMBRE_APELLIDOS / nombre_apellidos
        m = re.search(
            r"(?:NOMBRE_APELLIDOS|nombre_apellidos)\s*[:=]\s*[\"']?(.+?)[\"']?\s*(?:[,\n}]|$)",
            content,
            re.IGNORECASE,
        )
        if m:
            return m.group(1).strip().strip("\"'")

        # Patrón 2: campo "nombre" genérico
        m = re.search(
            r"(?:\"nombre\"|nombre)\s*[:=]\s*[\"']?(.+?)[\"']?\s*(?:[,\n}]|$)",
            content,
            re.IGNORECASE,
        )
        if m:
            return m.group(1).strip().strip("\"'")

        return ""

    # ── Clasificación por fiabilidad ───────────────────────────────────

    def classify_chunks_by_reliability(
        self, chunks: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """
        Divide chunks en 5 grupos según su score de Azure Search.

        Como @search.score no está normalizado (puede ser > 1 en búsqueda
        híbrida), primero se escala min-max al rango [0, 1].

        Umbrales leídos del .env (T1 > T2 > T3 > T4):
          grupo1: score >= T1  → alta fiabilidad, nombres directos
          grupo2: T2 <= score < T1
          grupo3: T3 <= score < T2
          grupo4: T4 <= score < T3
          grupo5: score < T4
        """
        t1 = config.cvs_reliability_t1
        t2 = config.cvs_reliability_t2
        t3 = config.cvs_reliability_t3
        t4 = config.cvs_reliability_t4

        # ── Normalización min-max a [0, 1] ──
        raw_scores = [c.get("score", 0.0) for c in chunks]
        min_s = min(raw_scores) if raw_scores else 0.0
        max_s = max(raw_scores) if raw_scores else 0.0
        span  = max_s - min_s

        for chunk in chunks:
            raw = chunk.get("score", 0.0)
            chunk["score_raw"]        = raw
            chunk["score_normalized"] = ((raw - min_s) / span) if span > 0 else 0.0

        groups: Dict[str, List[Dict]] = {
            "grupo1": [], "grupo2": [], "grupo3": [],
            "grupo4": [], "grupo5": [],
        }
        for chunk in chunks:
            score = chunk["score_normalized"]
            if score >= t1:
                groups["grupo1"].append(chunk)
            elif score >= t2:
                groups["grupo2"].append(chunk)
            elif score >= t3:
                groups["grupo3"].append(chunk)
            elif score >= t4:
                groups["grupo4"].append(chunk)
            else:
                groups["grupo5"].append(chunk)

        return groups

    # ── Mini-LLM para todos los grupos ────────────────────────────────

    def _call_mini_llm_batch(
        self,
        query: str,
        chunks: List[Dict],
        reliability_label: str,
        mini_client: AzureOpenAI,
        mini_deployment: str,
    ) -> Tuple[str, str]:
        """
        Llama al mini-LLM con un lote de chunks y devuelve (data, reasoning).
        """
        prompt = self.prompts.mini_llm_batch(query, chunks, reliability_label)
        try:
            response = mini_client.chat.completions.create(
                model=mini_deployment,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=400,
            )
            text = response.choices[0].message.content.strip()
            # Parsear data: y reasoning:
            data_match      = re.search(r"data:\s*(.+?)(?:\nreasoning:|$)", text, re.DOTALL)
            reasoning_match = re.search(r"reasoning:\s*(.+)$", text, re.DOTALL)
            data      = data_match.group(1).strip()      if data_match      else text
            reasoning = reasoning_match.group(1).strip() if reasoning_match else ""
            return data, reasoning
        except Exception as e:
            return "error", str(e)

    def _process_group_with_mini_llm(
        self,
        query: str,
        group_chunks: List[Dict],
        reliability_label: str,
        mini_client: AzureOpenAI,
        mini_deployment: str,
    ) -> Dict:
        """
        Divide group_chunks en lotes de CVS_CHUNK_SIZE y lanza llamadas
        al mini-LLM en paralelo. Devuelve el dict de grupo listo para historial.
        """
        chunk_size = config.cvs_chunk_size
        batches    = [
            group_chunks[i: i + chunk_size]
            for i in range(0, len(group_chunks), chunk_size)
        ]

        all_data:      List[str] = []
        all_reasoning: List[str] = []

        with ThreadPoolExecutor(max_workers=min(len(batches), 8)) as executor:
            futures = {
                executor.submit(
                    self._call_mini_llm_batch,
                    query, batch, reliability_label, mini_client, mini_deployment,
                ): idx
                for idx, batch in enumerate(batches)
            }
            # Recoger resultados en orden de llegada
            batch_results = [""] * len(batches)
            for future in as_completed(futures):
                idx = futures[future]
                data, reasoning = future.result()
                batch_results[idx] = (data, reasoning)

        for data, reasoning in batch_results:
            if data and data.lower() != "ninguno":
                all_data.append(data)
            if reasoning:
                all_reasoning.append(reasoning)

        return {
            "reliability": reliability_label,
            "data":        " | ".join(all_data) if all_data else "ninguno",
            "reasoning":   " | ".join(all_reasoning),
        }

    # ── Pipeline CVs completo ──────────────────────────────────────────

    def process_query(
        self,
        query: str,
        chunks: List[Dict],
        language: str = "es",
    ) -> Dict:
        """
        Pipeline principal para CVs:
          1. Clasifica chunks por fiabilidad.
          2. Grupo1: extrae nombres directamente.
          3. Grupos 2-5: mini-LLM en paralelo por lotes.
          4. Persiste en historial y devuelve los grupos.

        Devuelve:
          {
            "groups": { "grupo1": {...}, "grupo2": {...}, ... },
            "history_id": "uuid"
          }
        """
        # Cliente mini-LLM
        mini_model = config.azure_openai_mini_name or config.chat_model
        try:
            mini_cfg = config.get_model_config(mini_model)
        except ValueError:
            mini_cfg = config.get_chat_model_config()

        mini_client = AzureOpenAI(
            api_key=mini_cfg.api_key,
            api_version=mini_cfg.api_version,
            azure_endpoint=mini_cfg.api_base,
        )
        mini_deployment = mini_cfg.deployment

        # 1. Clasificar
        classified = self.classify_chunks_by_reliability(chunks)

        groups_result: Dict[str, Dict] = {}

        # 2. Grupo 1 — comportamiento configurable vía CVS_GROUP1_USE_LLM
        g1_chunks = classified["grupo1"]
        if not config.cvs_group1_use_llm:
            # Extracción directa: nombre_apellidos del contenido del chunk
            names = []
            for chunk in g1_chunks:
                name = self._extract_name_from_chunk(chunk)
                if name and name not in names:
                    names.append(name)
            groups_result["grupo1"] = {
                "reliability": self.reliability_labels["grupo1"],
                "data":        names if names else [],
                "reasoning":   (
                    f"CVS_GROUP1_USE_LLM=false: nombres extraídos directamente "
                    f"de doc_title ({len(g1_chunks)} chunks, sin llamada LLM)."
                ),
            }
        # si CVS_GROUP1_USE_LLM=true, grupo1 entra en el mismo bucle de mini-LLM

        # 3. Grupos 2-5 (y grupo1 si CVS_GROUP1_USE_LLM=true) → mini-LLM en lotes
        #    Ej: grupo1 con 50 chunks y chunk_size=30 → 2 llamadas (30 + 20)
        #        grupo2 con 25 chunks                → 1 llamada  (25)
        llm_groups = ["grupo2", "grupo3", "grupo4", "grupo5"]
        if config.cvs_group1_use_llm:
            llm_groups = ["grupo1"] + llm_groups

        with ThreadPoolExecutor(max_workers=len(llm_groups)) as executor:
            futures_by_group = {
                gname: executor.submit(
                    self._process_group_with_mini_llm,
                    query,
                    classified[gname],
                    self.reliability_labels[gname],
                    mini_client,
                    mini_deployment,
                )
                for gname in llm_groups
                if classified[gname]  # solo si hay chunks en el grupo
            }
            for gname in llm_groups:
                if gname in futures_by_group:
                    groups_result[gname] = futures_by_group[gname].result()
                else:
                    groups_result[gname] = {
                        "reliability": self.reliability_labels[gname],
                        "data":        "ninguno",
                        "reasoning":   "Sin chunks en este rango de fiabilidad.",
                    }

        # 4. Añadir reliability_score numérico a cada grupo (para historial)
        score_map = {
            "grupo1": config.cvs_reliability_t1,
            "grupo2": config.cvs_reliability_t2,
            "grupo3": config.cvs_reliability_t3,
            "grupo4": config.cvs_reliability_t4,
            "grupo5": config.cvs_reliability_t5,
        }
        for gname, group in groups_result.items():
            group["reliability_score"] = score_map.get(gname, 0.0)

        # 5. Persistir en historial
        history_id = self.history.add_entry(query=query, groups=groups_result, language=language)

        return {"groups": groups_result, "history_id": history_id}

    # ── Response Format: respuesta final con LLM potente ───────────────

    def format_final_response(
        self,
        query: str,
        groups_result: Dict,
        language: str = "es",
    ) -> tuple:
        """
        Paso 3 del diagrama: toma los resultados de todos los grupos
        y los pasa a un LLM potente para generar la respuesta final
        del usuario.

        Devuelve (answer: str, usage_info: dict).
        """
        # Usar el modelo potente (gpt-4.1)
        try:
            chat_cfg = config.get_chat_model_config()
        except ValueError:
            chat_cfg = config.get_model_config(config.chat_model)

        client = AzureOpenAI(
            api_key=chat_cfg.api_key,
            api_version=chat_cfg.api_version,
            azure_endpoint=chat_cfg.api_base,
        )

        prompt = self.prompts.response_format(
            query=query,
            groups=groups_result,
            max_chars=config.max_answer_chars,
            language=language,
        )

        system_message = self.get_system_message()

        # max_tokens alto para CVs: con muchos perfiles, la lista necesita espacio
        # ~15 tokens por perfil * hasta 150 perfiles = ~2250, más headers y resumen
        max_tokens_response = max(config.max_tokens, 4096)

        response = client.chat.completions.create(
            model=chat_cfg.deployment,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.3,
            max_tokens=max_tokens_response,
        )

        answer = response.choices[0].message.content
        usage  = response.usage
        usage_info = {
            "prompt_tokens":     usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens":      usage.total_tokens,
            "model":             chat_cfg.deployment,
        }

        return answer, usage_info
