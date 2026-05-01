"""
GraphRagStrategy — retrieval sobre Knowledge Graph en Neo4j vía Graphiti.

Aplica a:
  · use_case = "eu",   language ∈ {en, fr, it, pt}  → database NEO4J_EU_DATABASE
  · use_case = "wiki", language ∈ {en, ...}         → database NEO4J_WIKI_DATABASE

Características:
  · Usa `graphiti.search_(...)` con un `SearchConfig` (combined / edges / nodes)
    según `GRAPH_RAG_MODE`.
  · Devuelve los chunks como una mezcla de:
        - facts (edges)        → contienen relaciones extraídas
        - entities (nodes)     → contienen resúmenes de entidades
        - episodes             → contienen el texto original ingestado
  · Cachea una instancia singleton de Graphiti por database para evitar
    re-inicializar la conexión Neo4j en cada query.

NOTA: la API `search_()` de Graphiti es asíncrona. Como las estrategias se
invocan dentro de un nodo síncrono de LangGraph, envolvemos la llamada en
un loop dedicado (similar al patrón usado en `app_langgraph.generate_answer_async`).
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import os
from typing import Dict, List, Optional

from src.config import config
from src.rag.strategies.base import BaseStrategy


# ─── Estado global (singletons por database) ───────────────────────────
_GRAPHITI_INSTANCES: Dict[str, "Graphiti"] = {}  # noqa: F821 — forward ref
_GRAPHITI_LOCK = None  # se inicializa en primer uso (asyncio.Lock requiere loop)


def _build_azure_base_url() -> str:
    base = config.azure_openai_url or ""
    if not base.endswith("/"):
        base += "/"
    if not base.endswith("openai/v1/"):
        base += "openai/v1/"
    return base


def _resolve_database(use_case: str) -> str:
    if use_case == "eu":
        return config.neo4j_eu_database
    if use_case == "wiki":
        return config.neo4j_wiki_database
    raise ValueError(f"GraphRagStrategy: use_case '{use_case}' no soportado")


async def _get_or_create_graphiti(database: str):
    """Devuelve (y cachea) una instancia de Graphiti para la database indicada."""
    global _GRAPHITI_INSTANCES

    if database in _GRAPHITI_INSTANCES:
        return _GRAPHITI_INSTANCES[database]

    # Imports diferidos: graphiti_core puede no estar disponible al importar
    # el módulo (p. ej. en tests sin Neo4j).
    from openai import AsyncOpenAI
    from neo4j import AsyncGraphDatabase
    from graphiti_core import Graphiti
    from graphiti_core.driver.neo4j_driver import Neo4jDriver
    from graphiti_core.embedder.azure_openai import AzureOpenAIEmbedderClient
    from graphiti_core.llm_client.azure_openai_client import AzureOpenAILLMClient
    from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
    from graphiti_core.llm_client.config import LLMConfig

    # Skip-verify para proxies corporativos
    neo4j_uri = config.neo4j_uri
    if os.environ.get("NEO4J_SKIP_VERIFY", "").lower() in ("1", "true", "yes"):
        neo4j_uri = neo4j_uri.replace("neo4j+s://", "neo4j+ssc://").replace(
            "bolt+s://", "bolt+ssc://"
        )

    azure_base_url = _build_azure_base_url()
    azure_client = AsyncOpenAI(base_url=azure_base_url, api_key=config.azure_openai_key)

    llm_config = LLMConfig(
        api_key=config.azure_openai_key,
        base_url=azure_base_url,
        model=config.azure_openai_gpt4_1_name,
        small_model=config.azure_openai_gpt4_1_name,
    )
    llm_client = AzureOpenAILLMClient(azure_client=azure_client, config=llm_config)

    emb_cfg = config.get_embedding_model_config()
    embedder = AzureOpenAIEmbedderClient(azure_client=azure_client, model=emb_cfg.deployment)
    reranker = OpenAIRerankerClient(config=llm_config, client=azure_client)

    print(f"   🧠 Inicializando Graphiti para database='{database}'...")
    neo4j_driver = Neo4jDriver(
        uri=neo4j_uri,
        user=config.neo4j_user,
        password=config.neo4j_password,
        database=database,
    )
    # Pool de conexiones razonable para retrieval
    old_driver = neo4j_driver.client
    neo4j_driver.client = AsyncGraphDatabase.driver(
        uri=neo4j_uri,
        auth=(config.neo4j_user, config.neo4j_password),
        max_connection_pool_size=20,
        connection_acquisition_timeout=60,
    )
    await old_driver.close()

    graphiti = Graphiti(
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=reranker,
        graph_driver=neo4j_driver,
    )
    _GRAPHITI_INSTANCES[database] = graphiti
    print(f"   ✅ Graphiti listo (database='{database}')")
    return graphiti


def _build_search_config(num_results: int):
    """Devuelve un SearchConfig según GRAPH_RAG_MODE."""
    from graphiti_core.search.search_config_recipes import (
        COMBINED_HYBRID_SEARCH_RRF,
        EDGE_HYBRID_SEARCH_RRF,
        NODE_HYBRID_SEARCH_RRF,
    )

    mode = (config.graph_rag_mode or "combined").lower()
    if mode == "edges":
        cfg = EDGE_HYBRID_SEARCH_RRF.model_copy(deep=True)
    elif mode == "nodes":
        cfg = NODE_HYBRID_SEARCH_RRF.model_copy(deep=True)
    else:
        cfg = COMBINED_HYBRID_SEARCH_RRF.model_copy(deep=True)

    cfg.limit = num_results
    cfg.reranker_min_score = config.graph_rag_min_score
    return cfg


def _results_to_chunks(results, max_chunks: int) -> List[Dict]:
    """
    Convierte un `SearchResults` de Graphiti a la lista de chunks que
    espera el `Generator` estándar (claves: chunk_id, content, title,
    doc_title, pages, score, reranker_score, metadata).
    """
    chunks: List[Dict] = []

    # Episodes (texto original) — los más informativos
    for ep in (results.episodes or []):
        content = getattr(ep, "content", None) or getattr(ep, "name", "") or ""
        chunks.append({
            "chunk_id":       f"episode::{getattr(ep, 'uuid', '')}",
            "id":             getattr(ep, "uuid", ""),
            "content":        content,
            "title":          getattr(ep, "name", "Episode") or "Episode",
            "doc_title":      getattr(ep, "source_description", "") or "",
            "pages":          "N/A",
            "score":          1.0,
            "reranker_score": 1.0,
            "metadata":       {"type": "episode"},
        })

    # Edges (hechos / relaciones) — comprimen información del grafo
    for edge in (results.edges or []):
        fact = getattr(edge, "fact", "") or ""
        if not fact:
            continue
        chunks.append({
            "chunk_id":       f"edge::{getattr(edge, 'uuid', '')}",
            "id":             getattr(edge, "uuid", ""),
            "content":        f"FACT: {fact}",
            "title":          "Knowledge graph fact",
            "doc_title":      getattr(edge, "name", "") or "",
            "pages":          "N/A",
            "score":          0.9,
            "reranker_score": 0.9,
            "metadata":       {"type": "edge"},
        })

    # Nodes (entidades + resúmenes)
    for node in (results.nodes or []):
        summary = getattr(node, "summary", "") or ""
        name    = getattr(node, "name", "") or ""
        if not (summary or name):
            continue
        chunks.append({
            "chunk_id":       f"node::{getattr(node, 'uuid', '')}",
            "id":             getattr(node, "uuid", ""),
            "content":        f"ENTITY {name}: {summary}",
            "title":          name or "Entity",
            "doc_title":      "",
            "pages":          "N/A",
            "score":          0.8,
            "reranker_score": 0.8,
            "metadata":       {"type": "node"},
        })

    return chunks[:max_chunks]


async def _search_async(use_case: str, query: str) -> List[Dict]:
    database = _resolve_database(use_case)
    graphiti = await _get_or_create_graphiti(database)

    num_results = config.graph_rag_top_k
    search_cfg  = _build_search_config(num_results)

    results = await graphiti.search_(query=query, config=search_cfg)
    return _results_to_chunks(results, max_chunks=config.graph_rag_max_chunks)


def _run_async(coro):
    """Ejecuta una coroutine en un loop dedicado (compatible con LangGraph sync)."""
    def runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(runner).result()


class GraphRagStrategy(BaseStrategy):
    """Retrieval sobre Knowledge Graph en Neo4j (Graphiti)."""

    name = "graph_rag"

    def retrieve(self, state: Dict) -> Dict:
        use_case = state.get("use_case", "")
        query    = state.get("query", "")
        language = state.get("language", "")

        print(
            f"   🌐 Strategy=graph_rag [use_case={use_case}, lang={language}, "
            f"mode={config.graph_rag_mode}, top_k={config.graph_rag_top_k}]"
        )

        try:
            chunks = _run_async(_search_async(use_case, query))
        except Exception as e:
            print(f"   ❌ Error en GraphRAG retrieval: {e}")
            import traceback; traceback.print_exc()
            chunks = []

        print(f"   ✅ {len(chunks)} elementos de KG recuperados")
        state["synthetic_queries"] = [query]
        state["chunks_retrieved"]  = chunks
        return state


__all__ = ["GraphRagStrategy"]
