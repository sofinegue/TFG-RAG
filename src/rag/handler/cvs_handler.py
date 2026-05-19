"""
Handler del caso de uso CVs
Flujo (ver diagrama):
  1. Retrieve  — búsqueda directa sin RAG Fusion, CVS_TOP_K chunks
  2. Generate  — los chunks se separan en 5 grupos de fiabilidad según su
                 score de Azure Search; el grupo ≥ 90 % se resuelve
                 extrayendo nombres directamente; el resto se pasa en lotes
                 a un mini-LLM.  n_llamadas = len(chunks_grupo) / CVS_CHUNK_SIZE
  3. Historial — cada consulta se persiste en cvs_history.json con campos
                 data, reasoning y reliability separados por grupo
"""
from __future__ import annotations
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import AzureOpenAI
from src.config import config, safe_create_kwargs
from src.rag.handler.base import BaseUseCaseHandler
from src.rag.handler.cvs_history import CvsHistory
from src.rag.prompts.cvs_prompts import CVsPrompts
# ---------------------------------------------------------------------------
# Etiquetas de los 5 grupos de fiabilidad
# ---------------------------------------------------------------------------
def _build_reliability_labels() -> dict[str, str]:
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
        context: list[dict],
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
    def get_retrieval_config(self) -> dict:
        """
        CVs usa búsqueda directa con alto top_k y sin RAG Fusion,
        para maximizar la cobertura de perfiles a costa de precisión
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
    def _extract_name_from_chunk(chunk: dict) -> str:
        """
        Extrae nombre_apellidos del contenido del chunk
        Busca patrones como 'NOMBRE_APELLIDOS: ...' o 'nombre_apellidos: ...'
        dentro del texto. Si no lo encuentra, intenta extraer un nombre
        propio con regex de capitalización
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
        self, chunks: list[dict]
    ) -> dict[str, list[dict]]:
        """
        Divide chunks en 5 grupos según su score de Azure Search
        Como @search.score no está normalizado (puede ser > 1 en búsqueda
        híbrida), primero se escala min-max al rango [0, 1]
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
        groups: dict[str, list[dict]] = {
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
    # ── Pre-filtro programático por keywords ─────────────────────────
    @staticmethod
    def _extract_keywords_from_query(query: str) -> list[str]:
        """
        Extrae keywords buscables de la consulta del usuario
        Detecta nombres de skills, tecnologías, idiomas, puestos, etc
        y los splitea por AND/OR para búsqueda individual
        """
        raw_keywords: list[str] = []
        # 1. Términos entre comillas
        for m in re.finditer(r'"([^"]+)"', query):
            raw_keywords.append(m.group(1))
        for m in re.finditer(r"'([^']+)'", query):
            raw_keywords.append(m.group(1))
        # 2. Detectar patrones "have X among/in", "know X", "with X", etc.
        patterns = [
            r"(?:have|has|know|knows|with|proficient in|expertise in|experience (?:in|with)|"
            r"familiar with|work with|skilled in|trained in|include|includes|containing|"
            r"claims? to know|competency|competencies in|mention|mentions)\s+(.+?)(?:\s+(?:among|in|on|as|listed|"
            r"their|the|hard|soft|technical|skills|profile|CV|resume|competenc)|\?|$)",
            # "position of X", "role of X", "title of X"
            r"(?:position|role|title|job)\s+(?:of|is|as)\s+(.+?)(?:\?|$|\.|,)",
            # "speak X", "language X"
            r"(?:speak|speaks|language)\s+(.+?)(?:\?|$|\.|,)",
            # "studied X", "degree in X"
            r"(?:studied|degree in|qualification|education.*?in)\s+(.+?)(?:\?|$|\.|,)",
        ]
        for pat in patterns:
            for m in re.finditer(pat, query, re.IGNORECASE):
                kw = m.group(1).strip().rstrip("?.!,")
                kw = re.sub(r"\s+(among|in|on|as|their|the)$", "", kw, flags=re.IGNORECASE)
                if len(kw) > 1:
                    raw_keywords.append(kw)
        # 3. Splitear por AND / OR / "y" / "o" para obtener keywords individuales
        split_keywords: list[str] = []
        for kw in raw_keywords:
            parts = re.split(r"\s+(?:AND|OR|and|or)\s+", kw)
            for part in parts:
                part = part.strip().rstrip("?.!,")
                if len(part) > 1:
                    split_keywords.append(part)
        # 4. Filtrar keywords genéricas que no son buscables
        stop_phrases = {
            "at least", "more than", "less than", "no more", "no less",
            "the position of", "the role of",
        }
        filtered: list[str] = []
        for kw in split_keywords:
            kw_low = kw.lower()
            if any(kw_low.startswith(sp) for sp in stop_phrases):
                # Intentar extraer la parte útil después del stop phrase
                for sp in stop_phrases:
                    if kw_low.startswith(sp):
                        rest = kw[len(sp):].strip()
                        if rest and not rest.replace(" ", "").isdigit():
                            filtered.append(rest)
                        break
            elif re.match(r"^\d+$", kw.strip()):
                continue  # números sueltos no son keywords
            else:
                filtered.append(kw)
        # 5. Dedup preservando orden
        seen = set()
        result = []
        for kw in filtered:
            kw_low = kw.lower()
            if kw_low not in seen:
                seen.add(kw_low)
                result.append(kw)
        return result
    @staticmethod
    def _keyword_scan_chunks(
        chunks: list[dict], keywords: list[str],
    ) -> tuple[list[dict], list[dict]]:
        """
        Divide chunks en dos listas:
          - matched: el contenido contiene AL MENOS UNA keyword (case-insensitive)
          - unmatched: no contiene ninguna
        Para cada chunk matched, añade el campo '_kw_match' con las keywords
        encontradas (para reasoning)
        """
        if not keywords:
            return [], chunks  # sin keywords → todo va al LLM
        matched, unmatched = [], []
        needles = [(kw, kw.lower()) for kw in keywords]
        for chunk in chunks:
            content_lower = chunk.get("content", "").lower()
            found = [kw for kw, kw_low in needles if kw_low in content_lower]
            if found:
                chunk["_kw_match"] = found
                matched.append(chunk)
            else:
                unmatched.append(chunk)
        return matched, unmatched
    # ── Mini-LLM para todos los grupos ────────────────────────────────
    def _call_mini_llm_batch(
        self,
        query: str,
        chunks: list[dict],
        reliability_label: str,
        mini_client: AzureOpenAI,
        mini_deployment: str,
    ) -> tuple[str, str]:
        """
        Llama al mini-LLM con un lote de chunks y devuelve (data, reasoning)
        """
        prompt = self.prompts.mini_llm_batch(query, chunks, reliability_label)
        try:
            response = mini_client.chat.completions.create(
                **safe_create_kwargs(
                    model=mini_deployment,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_completion_tokens=1200,
                )
            )
            tok_in  = response.usage.prompt_tokens     if response.usage else 0
            tok_out = response.usage.completion_tokens if response.usage else 0
            text = response.choices[0].message.content.strip()
            # Parsear data: y reasoning:
            data_match      = re.search(r"data:\s*(.+?)(?:\nreasoning:|$)", text, re.DOTALL)
            reasoning_match = re.search(r"reasoning:\s*(.+)$", text, re.DOTALL)
            data      = data_match.group(1).strip()      if data_match      else text
            reasoning = reasoning_match.group(1).strip() if reasoning_match else ""
            return data, reasoning, tok_in, tok_out
        except Exception as e:
            return "error", str(e), 0, 0
    def _process_group_with_mini_llm(
        self,
        query: str,
        group_chunks: list[dict],
        reliability_label: str,
        mini_client: AzureOpenAI,
        mini_deployment: str,
    ) -> dict:
        """
        Pipeline por grupo:
          1. Pre-filtro programático: busca keywords extraídas de la query
             directamente en el contenido de cada chunk (100% fiable)
          2. Los chunks sin match van al mini-LLM para detección semántica
          3. Fusiona ambos resultados (dedup por nombre)
        """
        # ── Paso 1: Pre-filtro por keywords ──
        keywords = self._extract_keywords_from_query(query)
        kw_matched, kw_unmatched = self._keyword_scan_chunks(group_chunks, keywords)
        # Extraer nombres de los chunks que matchearon por keyword
        kw_names: list[str] = []
        kw_reasons: list[str] = []
        for chunk in kw_matched:
            name = self._extract_name_from_chunk(chunk)
            if name and name not in kw_names:
                kw_names.append(name)
                found_kws = chunk.get("_kw_match", [])
                kw_reasons.append(f"{name}: {', '.join(found_kws)} encontrado en contenido")
        # ── Paso 2: Mini-LLM solo para chunks sin match por keyword ──
        total_tok_in  = 0
        total_tok_out = 0
        total_calls   = 0
        llm_data: list[str] = []
        llm_reasoning: list[str] = []
        if kw_unmatched:
            chunk_size = config.cvs_chunk_size
            batches = [
                kw_unmatched[i: i + chunk_size]
                for i in range(0, len(kw_unmatched), chunk_size)
            ]
            with ThreadPoolExecutor(max_workers=min(len(batches), 8)) as executor:
                futures = {
                    executor.submit(
                        self._call_mini_llm_batch,
                        query, batch, reliability_label, mini_client, mini_deployment,
                    ): idx
                    for idx, batch in enumerate(batches)
                }
                batch_results = [None] * len(batches)
                for future in as_completed(futures):
                    idx = futures[future]
                    batch_results[idx] = future.result()
            for data, reasoning, tok_in, tok_out in batch_results:
                total_tok_in  += tok_in
                total_tok_out += tok_out
                total_calls   += 1
                if data and data.lower() not in ("ninguno", "error"):
                    llm_data.append(data)
                if reasoning and reasoning.lower() != "error" and not reasoning.startswith("BadRequest"):
                    llm_reasoning.append(reasoning)
        # ── Paso 3: Fusionar (dedup) ──
        all_data: list[str] = []
        if kw_names:
            all_data.append(" | ".join(kw_names))
        all_data.extend(llm_data)
        all_reasoning: list[str] = []
        if kw_reasons:
            all_reasoning.append(" | ".join(kw_reasons))
        all_reasoning.extend(llm_reasoning)
        return {
            "reliability":   reliability_label,
            "data":          " | ".join(all_data) if all_data else "ninguno",
            "reasoning":     " | ".join(all_reasoning),
            "mini_tok_in":   total_tok_in,
            "mini_tok_out":  total_tok_out,
            "mini_calls":    total_calls,
            "input_chunks":  len(group_chunks),
            "kw_matches":    len(kw_matched),
            "llm_chunks":    len(kw_unmatched),
        }
    # ── Pipeline CVs completo ──────────────────────────────────────────
    def process_query(
        self,
        query: str,
        chunks: list[dict],
        language: str = "es",
    ) -> dict:
        """
        Pipeline principal para CVs:
          1. Clasifica chunks por fiabilidad
          2. Grupo1: extrae nombres directamente
          3. Grupos 2-5: mini-LLM en paralelo por lotes
          4. Persiste en historial y devuelve los grupos
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
        groups_result: dict[str, dict] = {}
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
        # 6. Agregar uso total del mini-LLM (todos los grupos)
        total_mini_tok_in  = sum(g.get("mini_tok_in",  0) for g in groups_result.values())
        total_mini_tok_out = sum(g.get("mini_tok_out", 0) for g in groups_result.values())
        total_mini_calls   = sum(g.get("mini_calls",   0) for g in groups_result.values())
        return {
            "groups":     groups_result,
            "history_id": history_id,
            "mini_llm_usage": {
                "prompt_tokens":     total_mini_tok_in,
                "completion_tokens": total_mini_tok_out,
                "num_calls":         total_mini_calls,
            },
        }
    # ── Response Format: respuesta final con LLM potente ───────────────
    def format_final_response(
        self,
        query: str,
        groups_result: dict,
        language: str = "es",
    ) -> tuple:
        """
        Paso 3 del diagrama: toma los resultados de todos los grupos
        y los pasa a un LLM potente para generar la respuesta final
        del usuario
        Devuelve (answer: str, usage_info: dict)
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
        # ~15 tokens por perfil * hasta 300 perfiles = ~4500, más headers y resumen
        max_tokens_response = max(config.max_tokens, 8192)
        response = client.chat.completions.create(
            **safe_create_kwargs(
                model=chat_cfg.deployment,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.3,
                max_completion_tokens=max_tokens_response,
            )
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
