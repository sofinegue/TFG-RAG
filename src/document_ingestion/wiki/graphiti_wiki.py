"""
src.document_ingestion.wiki.graphiti_wiki

Módulo para construir un grafo de conocimiento (Knowledge Graph) a partir
de los chunks de Wikipedia almacenados en Cosmos DB, usando la librería
Graphiti (temporal knowledge graph framework).

Flujo:
  1. Leer chunks de Cosmos DB filtrando por docTitle e idioma.
  2. Inicializar Graphiti con driver Neo4j y clientes Azure OpenAI.
  3. Crear índices y constraints en Neo4j.
  4. Añadir cada chunk como un episodio (EpisodeType.text).
  5. Opcionalmente construir comunidades sobre los nodos extraídos.

Uso:
  python -m src.document_ingestion.wiki.graphiti_wiki --doc_title "Escritor" --language es
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from typing import List, Dict, Optional

from openai import AsyncAzureOpenAI

from src.config import config
from src.services.cosmos_service import get_querys_cosmos

# Graphiti (instalado desde libs/graphiti_core-0.28.0)
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.llm_client.azure_openai_client import AzureOpenAILLMClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.embedder.azure_openai import AzureOpenAIEmbedderClient
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Silenciar logs verbosos de SDKs de Azure
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# 1. Lectura de chunks desde Cosmos DB
# ---------------------------------------------------------------------------

def get_wiki_chunks_from_cosmos(
    doc_title: str,
    language: str = "es",
) -> List[Dict]:
    """
    Recupera los chunks activos (no eliminados) de un artículo concreto
    desde Cosmos DB → container Chunks-Wiki.

    Returns:
        Lista de dicts con los campos del chunk (content, Sections, nChunk, …).
    """
    query = (
        f"SELECT * FROM c "
        f"WHERE c.docTitle = '{doc_title}' "
        f"AND c.sourceLanguage = '{language}' "
        f"AND c.isDeleted = false "
        f"ORDER BY c.nChunk ASC"
    )
    chunks = get_querys_cosmos(query, config.cosmosdb_container_wiki)
    logger.info(
        "Cosmos: recuperados %d chunks para '%s' (lang=%s)",
        len(chunks), doc_title, language,
    )
    return chunks


# ---------------------------------------------------------------------------
# 2. Inicialización de Graphiti con Azure OpenAI
# ---------------------------------------------------------------------------

def build_azure_openai_async_client() -> AsyncAzureOpenAI:
    """Crea un cliente asíncrono de Azure OpenAI para uso con Graphiti."""
    chat_cfg = config.get_chat_model_config()
    return AsyncAzureOpenAI(
        azure_endpoint=chat_cfg.api_base,
        api_key=chat_cfg.api_key,
        api_version=chat_cfg.api_version,
    )


def build_azure_openai_embedder_client() -> AsyncAzureOpenAI:
    """Crea un cliente asíncrono de Azure OpenAI para embeddings."""
    emb_cfg = config.get_embedding_model_config()
    return AsyncAzureOpenAI(
        azure_endpoint=emb_cfg.api_base,
        api_key=emb_cfg.api_key,
        api_version=emb_cfg.api_version,
    )


async def init_graphiti() -> Graphiti:
    """
    Inicializa la instancia de Graphiti conectada a Neo4j
    con clientes Azure OpenAI para LLM y embeddings.
    """
    # --- Clientes Azure OpenAI ---
    azure_llm_client = build_azure_openai_async_client()
    azure_emb_client = build_azure_openai_embedder_client()

    chat_cfg = config.get_chat_model_config()
    emb_cfg = config.get_embedding_model_config()

    llm_config = LLMConfig(model=chat_cfg.deployment)
    llm_client = AzureOpenAILLMClient(azure_client=azure_llm_client, config=llm_config)

    embedder = AzureOpenAIEmbedderClient(
        azure_client=azure_emb_client,
        model=emb_cfg.deployment,
    )

    # Reranker: usa el mismo cliente LLM de Azure
    reranker = OpenAIRerankerClient(client=azure_llm_client)

    # --- Instancia Graphiti ---
    graphiti = Graphiti(
        uri=config.neo4j_uri,
        user=config.neo4j_user,
        password=config.neo4j_password,
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=reranker,
    )

    logger.info(
        "Graphiti inicializado — Neo4j: %s | LLM: %s | Embedder: %s",
        config.neo4j_uri, chat_cfg.deployment, emb_cfg.deployment,
    )

    return graphiti


# ---------------------------------------------------------------------------
# 3. Ingesta de chunks al grafo
# ---------------------------------------------------------------------------

async def ingest_chunks_to_graph(
    graphiti: Graphiti,
    chunks: List[Dict],
    doc_title: str,
    group_id: str = "wiki_es",
) -> dict:
    """
    Añade cada chunk como un episodio en Graphiti.

    Cada chunk se convierte en un episodio de tipo texto. Los metadatos
    (Sections, categorías, etc.) se incluyen como contexto en el
    source_description para que el LLM los use en la extracción de
    entidades y relaciones.

    Returns:
        Diccionario con estadísticas: total_episodes, nodes_created, edges_created
    """
    stats = {
        "total_episodes": 0,
        "total_nodes": 0,
        "total_edges": 0,
        "errors": 0,
    }

    for i, chunk in enumerate(chunks):
        chunk_content = chunk.get("content", "")
        sections = chunk.get("Sections", [])
        n_chunk = chunk.get("nChunk", i)
        categories = chunk.get("categories", [])

        # Contexto enriquecido para la extracción
        source_desc = (
            f"Artículo Wikipedia '{doc_title}' | "
            f"Secciones: {' > '.join(sections) if sections else 'N/A'} | "
            f"Categorías: {', '.join(categories[:5]) if categories else 'N/A'}"
        )

        episode_name = f"{doc_title} — chunk {n_chunk}"

        try:
            logger.info(
                "Añadiendo episodio %d/%d: %s",
                i + 1, len(chunks), episode_name,
            )

            result = await graphiti.add_episode(
                name=episode_name,
                episode_body=chunk_content,
                source=EpisodeType.text,
                source_description=source_desc,
                reference_time=datetime.now(timezone.utc),
                group_id=group_id,
            )

            n_nodes = len(result.nodes) if result.nodes else 0
            n_edges = len(result.edges) if result.edges else 0

            stats["total_episodes"] += 1
            stats["total_nodes"] += n_nodes
            stats["total_edges"] += n_edges

            logger.info(
                "  → Episodio añadido: %d nodos, %d aristas extraídas",
                n_nodes, n_edges,
            )

        except Exception as e:
            stats["errors"] += 1
            logger.error("Error añadiendo episodio '%s': %s", episode_name, e)
            import traceback
            traceback.print_exc()

    return stats


# ---------------------------------------------------------------------------
# 4. Búsqueda de prueba
# ---------------------------------------------------------------------------

async def test_search(
    graphiti: Graphiti,
    query: str,
    group_id: str = "wiki_es",
    num_results: int = 5,
) -> None:
    """Ejecuta una búsqueda de prueba sobre el grafo y muestra resultados."""
    logger.info("Buscando: '%s'", query)

    results = await graphiti.search(
        query=query,
        group_ids=[group_id],
        num_results=num_results,
    )

    print(f"\n{'='*60}")
    print(f"Resultados de búsqueda para: '{query}'")
    print(f"{'='*60}")

    if not results:
        print("  (sin resultados)")
        return

    for j, edge in enumerate(results, 1):
        print(f"\n--- Resultado {j} ---")
        print(f"  Hecho: {edge.fact}")
        if hasattr(edge, "valid_at") and edge.valid_at:
            print(f"  Válido desde: {edge.valid_at}")
        if hasattr(edge, "invalid_at") and edge.invalid_at:
            print(f"  Inválido desde: {edge.invalid_at}")
        print(f"  UUID: {edge.uuid}")


# ---------------------------------------------------------------------------
# 5. Pipeline completo
# ---------------------------------------------------------------------------

async def run_graphiti_wiki_pipeline(
    doc_title: str,
    language: str = "es",
    group_id: str = "wiki_es",
    test_queries: Optional[List[str]] = None,
) -> dict:
    """
    Pipeline completo: lee chunks de Cosmos → construye grafo → búsqueda de prueba.

    Args:
        doc_title: Título del artículo de Wikipedia.
        language: Idioma del artículo.
        group_id: ID de grupo para particionar el grafo.
        test_queries: Lista de consultas de prueba para ejecutar tras la ingesta.

    Returns:
        Estadísticas de la ingesta.
    """
    # 1. Leer chunks de Cosmos
    chunks = get_wiki_chunks_from_cosmos(doc_title, language)
    if not chunks:
        logger.warning("No se encontraron chunks para '%s' (lang=%s)", doc_title, language)
        return {"error": "No chunks found"}

    # 2. Inicializar Graphiti
    graphiti = await init_graphiti()

    try:
        # 3. Crear índices y constraints
        logger.info("Creando índices y constraints en Neo4j...")
        await graphiti.build_indices_and_constraints()
        logger.info("Índices creados correctamente.")

        # 4. Ingestar chunks al grafo
        stats = await ingest_chunks_to_graph(graphiti, chunks, doc_title, group_id)

        print(f"\n{'='*60}")
        print("RESUMEN DE INGESTA")
        print(f"{'='*60}")
        print(f"  Documento:      {doc_title}")
        print(f"  Idioma:         {language}")
        print(f"  Chunks leídos:  {len(chunks)}")
        print(f"  Episodios:      {stats['total_episodes']}")
        print(f"  Nodos creados:  {stats['total_nodes']}")
        print(f"  Aristas:        {stats['total_edges']}")
        print(f"  Errores:        {stats['errors']}")
        print(f"{'='*60}\n")

        # 5. Búsquedas de prueba
        if test_queries:
            for q in test_queries:
                await test_search(graphiti, q, group_id)

        return stats

    finally:
        await graphiti.close()
        logger.info("Conexión Graphiti cerrada.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Construir Knowledge Graph de artículos Wiki con Graphiti"
    )
    parser.add_argument(
        "--doc_title",
        type=str,
        default="Escritor",
        help="Título del artículo de Wikipedia (default: Escritor)",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="es",
        help="Idioma del artículo (default: es)",
    )
    parser.add_argument(
        "--group_id",
        type=str,
        default="wiki_es",
        help="ID de grupo para el grafo (default: wiki_es)",
    )
    parser.add_argument(
        "--test_query",
        type=str,
        nargs="*",
        default=["¿Qué tipos de escritores existen?", "¿Qué es un dramaturgo?"],
        help="Consultas de prueba para validar el grafo",
    )

    args = parser.parse_args()

    stats = asyncio.run(
        run_graphiti_wiki_pipeline(
            doc_title=args.doc_title,
            language=args.language,
            group_id=args.group_id,
            test_queries=args.test_query,
        )
    )

    # Exit code basado en errores
    if stats.get("error"):
        sys.exit(1)
    if stats.get("errors", 0) > 0 and stats.get("total_episodes", 0) == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
