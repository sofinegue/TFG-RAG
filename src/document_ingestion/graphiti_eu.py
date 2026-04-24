"""
Graphiti EU Ingestion Pipeline
=================================
Lee los chunks de legislación europea (EUR-Lex) desde CosmosDB (Chunks-EU)
y los ingesta como episodios en Neo4j mediante Graphiti, creando un
Knowledge Graph con entidades y relaciones extraídas automáticamente.

Uso:
    python -m src.document_ingestion.graphiti_eu            # todos los chunks
    python -m src.document_ingestion.graphiti_eu --max 5     # solo 5 chunks (pruebas)
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

# Limitar coroutines paralelas ANTES de importar graphiti_core.
# Aura Free soporta ~5 conexiones concurrentes; valores altos agotan el pool.
os.environ.setdefault('SEMAPHORE_LIMIT', '3')

from openai import AsyncOpenAI
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import ConnectionAcquisitionTimeoutError

from graphiti_core import Graphiti
from graphiti_core.driver.neo4j_driver import Neo4jDriver
from graphiti_core.embedder.azure_openai import AzureOpenAIEmbedderClient
from graphiti_core.llm_client.azure_openai_client import AzureOpenAILLMClient
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.nodes import EpisodeType

# Añadir la raíz del proyecto al path para importar src.config
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))

from src.config import config  # noqa: E402
from src.services.cosmos_service import get_querys_cosmos  # noqa: E402

# ─── Logging ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

# Silenciar notificaciones verbosas de Neo4j (índices que ya existen)
logging.getLogger('neo4j.notifications').setLevel(logging.WARNING)

# ─── Neo4j (EU-specific) ──────────────────────────────────────────────
neo4j_uri = config.neo4j_eu_uri
neo4j_user = config.neo4j_eu_user
neo4j_password = config.neo4j_eu_password

# ─── Azure OpenAI ──────────────────────────────────────────────────────
azure_base_url = config.azure_openai_url
if not azure_base_url.endswith('/'):
    azure_base_url += '/'
if not azure_base_url.endswith('openai/v1/'):
    azure_base_url += 'openai/v1/'
azure_api_key = config.azure_openai_key

# Si hay proxy corporativo, cambiar neo4j+s → neo4j+ssc (skip SSL verify)
if os.environ.get('NEO4J_SKIP_VERIFY', '').lower() in ('1', 'true', 'yes'):
    neo4j_uri = neo4j_uri.replace('neo4j+s://', 'neo4j+ssc://').replace('bolt+s://', 'bolt+ssc://')

logger.info("Configuración cargada desde src.config (EU)")
logger.info(f"  Neo4j URI:       {neo4j_uri}")
logger.info(f"  Neo4j User:      {neo4j_user}")
logger.info(f"  Neo4j Database:  {config.neo4j_eu_database}")
logger.info(f"  Azure Base URL:  {azure_base_url}")
logger.info(f"  LLM Model:       {config.azure_openai_gpt4_1_name}")
logger.info(f"  Emb Deployment:  {config.azure_openai_emb_deployment}")
logger.info(f"  Cosmos DB:       {config.cosmosdb_database}")
logger.info(f"  Cosmos EU:       {config.cosmosdb_container_eu}")
logger.info(f"  Log Level:       {config.log_level}")

if not neo4j_uri or not neo4j_user or not neo4j_password:
    raise ValueError('NEO4J_EU_URI, NEO4J_EU_USER, and NEO4J_EU_PASSWORD must be set')


# ─── CosmosDB helpers ─────────────────────────────────────────────────
def fetch_eu_chunks() -> list[dict]:
    """Lee todos los chunks activos de EUR-Lex desde CosmosDB."""
    query = (
        "SELECT c.id, c.chunkId, c.docTitle, c.content, c.sourceLanguage, "
        "c.doc_type, c.Sections, c.nChunk, c.sourcePath "
        "FROM c "
        "WHERE (c.isDeleted != true OR NOT IS_DEFINED(c.isDeleted)) "
        "AND c.sourceLanguage != 'es'"
    )
    logger.info(f"Consultando CosmosDB container '{config.cosmosdb_container_eu}'...")
    chunks = get_querys_cosmos(query, config.cosmosdb_container_eu)
    logger.info(f"  {len(chunks)} chunks recuperados de CosmosDB")
    return chunks


# ─── Neo4j wipe ────────────────────────────────────────────────────────
async def wipe_neo4j(driver):
    """Elimina todos los nodos y relaciones de la base de datos Neo4j."""
    logger.info("Eliminando todos los datos de Neo4j...")
    deleted = 0
    while True:
        async with driver.client.session(database=config.neo4j_eu_database) as session:
            result = await session.run(
                "MATCH (n) WITH n LIMIT 500 DETACH DELETE n RETURN count(n) AS deleted"
            )
            record = await result.single()
            batch = record["deleted"] if record else 0
        deleted += batch
        if batch == 0:
            break
        logger.info(f"  Eliminados {deleted} nodos...")
    logger.info(f"Neo4j limpiado: {deleted} nodos eliminados en total")


# ─── Main ──────────────────────────────────────────────────────────────
async def main(max_chunks: int | None = None):
    logger.info("=" * 60)
    logger.info("  GRAPHITI EU INGESTION PIPELINE")
    logger.info("=" * 60)

    t0 = time.perf_counter()

    # ── 1. Clientes Azure OpenAI ───────────────────────────────────────
    logger.info("=== FASE 0: Inicializando clientes Azure OpenAI ===")

    azure_client = AsyncOpenAI(base_url=azure_base_url, api_key=azure_api_key)

    llm_config = LLMConfig(
        api_key=azure_api_key,
        base_url=azure_base_url,
        model=config.azure_openai_gpt4_1_name,
        small_model=config.azure_openai_gpt4_1_name,
    )
    llm_client = AzureOpenAILLMClient(azure_client=azure_client, config=llm_config)
    logger.info(f"  LLM client configurado (model={config.azure_openai_gpt4_1_name})")

    emb_config = config.get_embedding_model_config()
    embedder = AzureOpenAIEmbedderClient(
        azure_client=azure_client,
        model=emb_config.deployment,
    )
    logger.info(f"  Embedder configurado (deployment={emb_config.deployment})")

    reranker = OpenAIRerankerClient(config=llm_config, client=azure_client)
    logger.info("  Reranker configurado")

    # ── 2. Driver Neo4j ────────────────────────────────────────────────
    logger.info(f"  Conectando a Neo4j (database={config.neo4j_eu_database})...")
    neo4j_driver = Neo4jDriver(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password,
        database=config.neo4j_eu_database,
    )

    # Cerrar el driver original (y su background task) antes de reemplazarlo
    old_driver = neo4j_driver.client
    neo4j_driver.client = AsyncGraphDatabase.driver(
        uri=neo4j_uri,
        auth=(neo4j_user, neo4j_password),
        max_connection_pool_size=5,
        connection_acquisition_timeout=120,
    )
    await old_driver.close()
    logger.info("  Neo4j pool limitado a 5 conexiones (Aura Free)")
    logger.info("  Driver original cerrado (evita orphaned connections)")

    # Esperar a que se creen los índices en el NUEVO driver antes de operar
    logger.info("  Creando índices y constraints en Neo4j...")
    await neo4j_driver.build_indices_and_constraints()
    logger.info("  Índices creados correctamente")

    # ── 3. Wipe Neo4j ─────────────────────────────────────────────────
    await wipe_neo4j(neo4j_driver)

    # ── 4. Inicializar Graphiti ────────────────────────────────────────
    graphiti = Graphiti(
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=reranker,
        graph_driver=neo4j_driver,
    )
    logger.info(f"Graphiti inicializado en {time.perf_counter() - t0:.3f}s")

    try:
        # ── 5. Leer chunks de CosmosDB ─────────────────────────────────
        logger.info("=== FASE 1: Leyendo chunks de EUR-Lex desde CosmosDB ===")
        chunks = fetch_eu_chunks()

        if not chunks:
            logger.warning("No se encontraron chunks en CosmosDB. Abortando.")
            return

        # Ordenar por título y número de chunk para ingestar en orden lógico
        chunks.sort(key=lambda c: (c.get('docTitle', ''), c.get('nChunk', 0)))

        # Aplicar límite de chunks (útil para pruebas rápidas)
        if max_chunks is not None and max_chunks > 0:
            chunks = chunks[:max_chunks]
            logger.info(f"Límite aplicado: usando solo {max_chunks} chunks")

        logger.info(f"Total de chunks a ingestar: {len(chunks)}")
        titles = {c.get('docTitle', 'Unknown') for c in chunks}
        logger.info(f"Documentos únicos: {len(titles)} — {titles}")

        # ── 6. Ingestar chunks como episodios ──────────────────────────
        logger.info("=== FASE 2: Ingestando chunks en Neo4j via Graphiti ===")

        for i, chunk in enumerate(chunks):
            doc_title = chunk.get('docTitle', 'Unknown')
            content = chunk.get('content', '')
            language = chunk.get('sourceLanguage', 'en')
            n_chunk = chunk.get('nChunk', i)
            sections = chunk.get('Sections', [])
            doc_type = chunk.get('doc_type', 'legislation')
            chunk_id = chunk.get('chunkId', chunk.get('id', f'chunk_{i}'))

            # Construir descripción rica para que Graphiti extraiga mejor
            section_str = ' > '.join(sections) if sections else 'General'
            description = (
                f"EUR-Lex document '{doc_title}' ({language}), "
                f"type: {doc_type}, section: {section_str}, chunk {n_chunk}"
            )

            episode_name = f"{doc_title} - chunk {n_chunk} ({chunk_id})"

            logger.info(
                f"  [{i+1}/{len(chunks)}] Ingesting '{episode_name}' "
                f"(lang={language}, type={doc_type}, sections={section_str}, "
                f"content_len={len(content)} chars)"
            )

            t_ep = time.perf_counter()
            # Retry con backoff exponencial para pool timeouts de Aura Free
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    await graphiti.add_episode(
                        name=episode_name,
                        episode_body=content,
                        source=EpisodeType.text,
                        source_description=description,
                        reference_time=datetime.now(timezone.utc),
                    )
                    break  # éxito
                except ConnectionAcquisitionTimeoutError:
                    if attempt == max_retries:
                        logger.error(f"  [{i+1}/{len(chunks)}] Fallido tras {max_retries} intentos")
                        raise
                    wait = 30 * attempt  # 30s, 60s, 90s
                    logger.warning(
                        f"  [{i+1}/{len(chunks)}] Pool timeout (intento {attempt}/{max_retries}), "
                        f"esperando {wait}s antes de reintentar..."
                    )
                    await asyncio.sleep(wait)

            elapsed_ep = time.perf_counter() - t_ep
            logger.info(
                f"  [{i+1}/{len(chunks)}] Episodio añadido OK en {elapsed_ep:.1f}s"
            )

            # Pausa entre chunks para dejar que Aura Free libere conexiones
            if i < len(chunks) - 1:
                await asyncio.sleep(5)

        total_time = time.perf_counter() - t0
        logger.info("=" * 60)
        logger.info(f"  PIPELINE COMPLETADO — {len(chunks)} chunks ingestados")
        logger.info(f"  Tiempo total: {total_time:.1f}s ({total_time/60:.1f} min)")
        logger.info("=" * 60)

    except Exception:
        logger.exception("Error durante la ingestión de chunks EU")
        raise

    finally:
        logger.info("Cerrando conexión con Neo4j...")
        await graphiti.close()
        logger.info("Conexión cerrada correctamente")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Graphiti EU Ingestion Pipeline')
    parser.add_argument(
        '--max', type=int, default=None,
        help='Máximo número de chunks a ingestar (por defecto: todos)',
    )
    args = parser.parse_args()
    asyncio.run(main(max_chunks=args.max))
