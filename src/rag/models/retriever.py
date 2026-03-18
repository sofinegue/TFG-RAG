"""
Retriever con búsqueda híbrida (texto + vector) y RAG Fusion.
Adaptado para los tres casos de uso: cvs, eu, wiki.
Cada caso usa su propio índice de Azure Search.
"""

import re
from typing import List, Dict, TypedDict
from concurrent.futures import ThreadPoolExecutor

from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.models import VectorizedQuery
from openai import AzureOpenAI

from src.config import config
from src.rag.prompts.prompt_templates import PromptTemplates


# Mapeo de caso de uso → nombre del índice de Azure Search
USE_CASE_INDEX_MAP = {
    "cvs":  config.azure_search_index_cvs,
    "eu":   config.azure_search_index_eu,
    "wiki": config.azure_search_index_wiki,
}


class ChunkData(TypedDict):
    chunk_id: str
    title: str
    content: str
    doc_title: str
    pages: str
    score: float
    reranker_score: float
    metadata: Dict


class RetrieverState(TypedDict):
    query: str
    use_case: str
    synthetic_queries: List[str]
    chunks_retrieved: List[ChunkData]
    user_id: str
    conversation_history: List[Dict]
    timestamps: Dict[str, float]
    rag_mode: str


class Retriever:
    """Retriever con búsqueda híbrida + Query Expansion + RAG Fusion."""

    def __init__(self):
        self.config = config
        self.prompts = PromptTemplates()

        # Clientes de OpenAI (compartidos para todos los índices)
        embedding_cfg = config.get_embedding_model_config()
        self.embedding_client = AzureOpenAI(
            api_key=embedding_cfg.api_key,
            api_version=embedding_cfg.api_version,
            azure_endpoint=embedding_cfg.api_base,
        )
        self.embedding_deployment = embedding_cfg.deployment

        chat_cfg = config.get_chat_model_config()
        self.chat_client = AzureOpenAI(
            api_key=chat_cfg.api_key,
            api_version=chat_cfg.api_version,
            azure_endpoint=chat_cfg.api_base,
        )
        self.chat_deployment = chat_cfg.deployment

    # ------------------------------------------------------------------
    # Creación de SearchClient por caso de uso (lazy, por query)
    # ------------------------------------------------------------------
    def _get_search_client(self, use_case: str) -> SearchClient:
        index_name = USE_CASE_INDEX_MAP.get(use_case, config.azure_search_index_cvs)
        return SearchClient(
            endpoint=config.azure_search_endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(config.azure_search_key),
        )

    # ------------------------------------------------------------------
    # Query expansion con historial conversacional
    # ------------------------------------------------------------------
    def _expand_query_with_context(self, query: str, history: List[Dict]) -> str:
        if not history or len(history) < 2:
            return query

        recent = history[-4:]
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content'][:400]}" for m in recent
        )

        name_pattern = r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3}\b"
        found_names = re.findall(name_pattern, history_text)
        full_names = [n for n in found_names if len(n.split()) >= 2]
        unique_names = list(dict.fromkeys(full_names))

        expansion_prompt = f"""Analiza si esta query necesita información del contexto conversacional.

CONVERSACIÓN RECIENTE:
{history_text}

NOMBRES IDENTIFICADOS: {', '.join(unique_names[:10]) if unique_names else 'ninguno'}

QUERY ACTUAL:
{query}

TAREA: Si la query usa términos genéricos y en el historial se mencionaron personas/candidatos
específicos, expande la query incluyendo sus nombres. Si ya es específica, devuélvela sin cambios.
Máximo 15 palabras. Solo nombres, tecnologías y términos clave.

Responde SOLO con la query (expandida o sin cambios):"""

        try:
            response = self.chat_client.chat.completions.create(
                model=self.chat_deployment,
                messages=[{"role": "user", "content": expansion_prompt}],
                temperature=0.1,
                max_tokens=70,
            )
            expanded = response.choices[0].message.content.strip().strip('"').strip("'")
            if len(expanded.split()) > 20 or not expanded or "\n" in expanded:
                return query
            return expanded
        except Exception as e:
            print(f"      ⚠️ Error en expansión de query: {e}")
            return query

    # ------------------------------------------------------------------
    # Queries sintéticas (RAG Fusion)
    # ------------------------------------------------------------------
    def generate_synthetic_queries(self, query: str) -> List[str]:
        if not config.use_rag_fusion:
            return [query]

        k = config.rag_fusion_queries - 1
        prompt = self.prompts.rag_fusion_synthetic_queries(query, k)

        try:
            response = self.chat_client.chat.completions.create(
                model=self.chat_deployment,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500,
            )
            text = response.choices[0].message.content
            queries = re.sub(r"\d+\.\s*", "", text).strip().split("\n")
            queries = [q.strip() for q in queries if q.strip()]
            queries.insert(0, query)
            return queries[: config.rag_fusion_queries]
        except Exception as e:
            print(f"Error generando queries sintéticas: {e}")
            return [query]

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------
    def get_embedding(self, text: str) -> List[float]:
        response = self.embedding_client.embeddings.create(
            model=self.embedding_deployment, input=text
        )
        return response.data[0].embedding

    # ------------------------------------------------------------------
    # Búsqueda híbrida en un índice concreto
    # ------------------------------------------------------------------
    def hybrid_search(self, query: str, use_case: str, top_k: int = 10) -> List[Dict]:
        try:
            search_client = self._get_search_client(use_case)
            query_embedding = self.get_embedding(query)

            results = search_client.search(
                search_text=query,
                vector_queries=[
                    VectorizedQuery(
                        vector=query_embedding,
                        k_nearest_neighbors=top_k,
                        fields="embedding",
                    )
                ],
                top=top_k,
                select=["id", "chunkId", "content", "Title", "docTitle"],
            )

            chunks = []
            for result in results:
                chunks.append(
                    {
                        "chunk_id": result.get("chunkId") or result.get("id"),
                        "id":       result.get("id"),
                        "content":  result.get("content") or result.get("sectionContent", ""),
                        "title":    result.get("Title", ""),
                        "doc_title":result.get("docTitle", ""),
                        "pages":    result.get("Pages", "N/A"),
                        "score":    result.get("@search.score", 0),
                        "reranker_score": 1.0,
                    }
                )
            return chunks
        except Exception as e:
            print(f"Error en búsqueda híbrida ({use_case}): {e}")
            return []

    # ------------------------------------------------------------------
    # RAG Fusion – fusión con RRF
    # ------------------------------------------------------------------
    def rag_fusion_retrieve(self, queries: List[str], use_case: str) -> List[ChunkData]:
        all_chunks = []

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.hybrid_search, q, use_case) for q in queries]
            for future in futures:
                all_chunks.extend(future.result())

        # RRF scoring
        chunk_scores: Dict[str, Dict] = {}
        for rank, chunk in enumerate(all_chunks, 1):
            cid = chunk.get("chunk_id") or chunk.get("id") or str(rank)
            rrf_score = 1 / (60 + rank)
            if cid in chunk_scores:
                chunk_scores[cid]["rrf_score"] += rrf_score
            else:
                chunk["rrf_score"] = rrf_score
                chunk_scores[cid] = chunk

        ranked = sorted(
            chunk_scores.values(), key=lambda x: x.get("rrf_score", 0), reverse=True
        )
        filtered = [c for c in ranked if c.get("reranker_score", 0) >= config.min_relevance_score]
        return filtered[: config.max_chunks_used]

    # ------------------------------------------------------------------
    # Interfaz pública para LangGraph
    # ------------------------------------------------------------------
    def retrieve(self, state: RetrieverState) -> RetrieverState:
        rag_mode = state.get("rag_mode", "gpt")
        use_case = state.get("use_case", "cvs")

        # En modo assistant el file_search del agente ya recupera contexto
        if rag_mode == "assistant":
            print("   🤖 Modo assistant: omitiendo retrieval de Azure Search")
            state["synthetic_queries"] = []
            state["chunks_retrieved"]  = []
            return state

        query   = state["query"]
        history = state.get("conversation_history", [])

        print(f"   🔍 Retrieval [{use_case}] – query: {query[:60]}")
        expanded = self._expand_query_with_context(query, history)
        synthetic_queries = self.generate_synthetic_queries(expanded)
        print(f"   📝 {len(synthetic_queries)} queries sintéticas")

        chunks = self.rag_fusion_retrieve(synthetic_queries, use_case)
        print(f"   ✅ {len(chunks)} chunks recuperados")

        state["synthetic_queries"] = synthetic_queries
        state["chunks_retrieved"]  = chunks
        return state
