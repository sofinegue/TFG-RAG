"""
Graphiti Wiki Ingestion Pipeline
=================================
Lee los chunks de Wikipedia desde CosmosDB (Chunks-Wiki) y los ingesta
como episodios en Neo4j mediante Graphiti, creando un Knowledge Graph
con entidades y relaciones extraídas automáticamente.

Uso:
    python -m src.document_ingestion.graphiti_wiki            # todos los chunks
    python -m src.document_ingestion.graphiti_wiki --max 5     # solo 5 chunks (pruebas)
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
os.environ.setdefault('SEMAPHORE_LIMIT', '10')

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

# ─── Neo4j (shared instance, Wiki database) ───────────────────────────
neo4j_uri = config.neo4j_uri
neo4j_user = config.neo4j_user
neo4j_password = config.neo4j_password

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

logger.info("Configuración cargada desde src.config")
logger.info(f"  Neo4j URI:       {neo4j_uri}")
logger.info(f"  Neo4j User:      {neo4j_user}")
logger.info(f"  Neo4j Database:  {config.neo4j_wiki_database}")
logger.info(f"  Azure Base URL:  {azure_base_url}")
logger.info(f"  LLM Model:       {config.azure_openai_gpt4_1_name}")
logger.info(f"  Emb Deployment:  {config.azure_openai_emb_deployment}")
logger.info(f"  Cosmos DB:       {config.cosmosdb_database}")
logger.info(f"  Cosmos Wiki:     {config.cosmosdb_container_wiki}")
logger.info(f"  Log Level:       {config.log_level}")

if not neo4j_uri or not neo4j_user or not neo4j_password:
    raise ValueError('NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD must be set')


# ─── CosmosDB helpers ─────────────────────────────────────────────────
def fetch_wiki_chunks() -> list[dict]:
    """Lee todos los chunks activos de Wikipedia desde CosmosDB."""
    query = (
        "SELECT c.id, c.chunkId, c.docTitle, c.content, c.sourceLanguage, "
        "c.categories, c.wiki_url, c.pageid, c.Sections, c.nChunk "
        "FROM c "
        "WHERE (c.isDeleted != true OR NOT IS_DEFINED(c.isDeleted)) "
        "AND c.sourceLanguage = 'en'"
    )
    logger.info(f"Consultando CosmosDB container '{config.cosmosdb_container_wiki}'...")
    chunks = get_querys_cosmos(query, config.cosmosdb_container_wiki)
    logger.info(f"  {len(chunks)} chunks recuperados de CosmosDB")
    return chunks


# ─── Neo4j wipe ────────────────────────────────────────────────────────
async def wipe_neo4j(driver):
    """Elimina todos los nodos y relaciones de la base de datos Neo4j."""
    logger.info("Eliminando todos los datos de Neo4j...")
    deleted = 0
    while True:
        # Abrir y cerrar sesión en cada lote para liberar conexiones al pool
        async with driver.client.session(database=config.neo4j_wiki_database) as session:
            result = await session.run(
                "MATCH (n) WITH n LIMIT 500 DETACH DELETE n RETURN count(n) AS deleted"
            )
            record = await result.single()
            batch = record["deleted"] if record else 0
        # Sesión ya cerrada → conexión devuelta al pool
        deleted += batch
        if batch == 0:
            break
        logger.info(f"  Eliminados {deleted} nodos...")
    logger.info(f"Neo4j limpiado: {deleted} nodos eliminados en total")


# ─── Main ──────────────────────────────────────────────────────────────
async def fetch_existing_episodes(driver) -> set[str]:
    """Devuelve los nombres de episodios ya ingestados en la database."""
    names = set()
    async with driver.client.session(database=config.neo4j_wiki_database) as session:
        result = await session.run("MATCH (e:Episodic) RETURN e.name AS name")
        async for record in result:
            if record["name"]:
                names.add(record["name"])
    logger.info(f"  Episodios existentes en Neo4j: {len(names)}")
    return names


async def main(max_chunks: int | None = None, no_wipe: bool = False):
    logger.info("=" * 60)
    logger.info("  GRAPHITI WIKI INGESTION PIPELINE")
    logger.info(f"  Modo: {'RETRY (sin wipe)' if no_wipe else 'COMPLETO (con wipe)'}")
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
    # IMPORTANTE: Neo4jDriver.__init__ crea un driver interno Y programa
    # build_indices_and_constraints() como tarea en background.
    # Debemos cerrar el driver original ANTES de reemplazarlo para evitar
    # que dos drivers compitan por conexiones (causa #1 de pool exhaustion).
    logger.info(f"  Conectando a Neo4j (database={config.neo4j_wiki_database})...")
    neo4j_driver = Neo4jDriver(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password,
        database=config.neo4j_wiki_database,
    )

    # Cerrar el driver original (y su background task) antes de reemplazarlo
    old_driver = neo4j_driver.client
    neo4j_driver.client = AsyncGraphDatabase.driver(
        uri=neo4j_uri,
        auth=(neo4j_user, neo4j_password),
        max_connection_pool_size=50,
        connection_acquisition_timeout=120,
    )
    await old_driver.close()
    logger.info("  Neo4j pool: 50 conexiones (local)")
    logger.info("  Driver original cerrado (evita orphaned connections)")

    # Esperar a que se creen los índices en el NUEVO driver antes de operar
    logger.info("  Creando índices y constraints en Neo4j...")
    await neo4j_driver.build_indices_and_constraints()
    logger.info("  Índices creados correctamente")

    # ── 3. Wipe Neo4j ─────────────────────────────────────────────────
    if no_wipe:
        logger.info("  --no-wipe activo: conservando datos existentes (modo retry)")
    else:
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
        logger.info("=== FASE 1: Leyendo chunks de Wikipedia desde CosmosDB ===")
        chunks = fetch_wiki_chunks()

        if not chunks:
            logger.warning("No se encontraron chunks en CosmosDB. Abortando.")
            return

        # Ordenar por título y número de chunk para ingestar en orden lógico
        chunks.sort(key=lambda c: (c.get('docTitle', ''), c.get('nChunk', 0)))

        # Aplicar límite de chunks (útil para pruebas rápidas)
        if max_chunks is not None and max_chunks > 0:
            chunks = chunks[:max_chunks]
            logger.info(f"Límite aplicado: usando solo {max_chunks} chunks")

        # Filtrar chunks ya ingestados (modo retry)
        if no_wipe:
            existing = await fetch_existing_episodes(neo4j_driver)
            total_before = len(chunks)
            chunks = [
                c for c in chunks
                if f"{c.get('docTitle', 'Unknown')} - chunk {c.get('nChunk', 0)} ({c.get('chunkId', c.get('id', ''))})" not in existing
            ]
            logger.info(f"  Filtrados: {total_before - len(chunks)} ya ingestados, {len(chunks)} pendientes")

        logger.info(f"Total de chunks a ingestar: {len(chunks)}")
        titles = {c.get('docTitle', 'Unknown') for c in chunks}
        logger.info(f"Artículos únicos: {len(titles)} — {titles}")

        # ── 6. Ingestar chunks como episodios (concurrente) ─────────
        CONCURRENCY = 5  # chunks procesados en paralelo
        logger.info(f"=== FASE 2: Ingestando chunks en Neo4j via Graphiti (concurrencia={CONCURRENCY}) ===")

        sem = asyncio.Semaphore(CONCURRENCY)
        ok_count = 0
        fail_count = 0

        async def ingest_chunk(i: int, chunk: dict):
            nonlocal ok_count, fail_count
            async with sem:
                doc_title = chunk.get('docTitle', 'Unknown')
                content = chunk.get('content', '')
                language = chunk.get('sourceLanguage', 'en')
                n_chunk = chunk.get('nChunk', i)
                sections = chunk.get('Sections', [])
                chunk_id = chunk.get('chunkId', chunk.get('id', f'chunk_{i}'))

                section_str = ' > '.join(sections) if sections else 'General'
                description = (
                    f"Wikipedia article '{doc_title}' ({language}), "
                    f"section: {section_str}, chunk {n_chunk}"
                )
                episode_name = f"{doc_title} - chunk {n_chunk} ({chunk_id})"

                logger.info(
                    f"  [{i+1}/{len(chunks)}] Ingesting '{episode_name}' "
                    f"(lang={language}, content_len={len(content)} chars)"
                )

                t_ep = time.perf_counter()
                max_retries = 5
                for attempt in range(1, max_retries + 1):
                    try:
                        await graphiti.add_episode(
                            name=episode_name,
                            episode_body=content,
                            source=EpisodeType.text,
                            source_description=description,
                            reference_time=datetime.now(timezone.utc),
                        )
                        ok_count += 1
                        break
                    except (ConnectionAcquisitionTimeoutError, Exception) as exc:
                        is_pool = isinstance(exc, ConnectionAcquisitionTimeoutError)
                        label = "Pool timeout" if is_pool else f"{type(exc).__name__}: {exc}"
                        if attempt == max_retries:
                            logger.error(
                                f"  [{i+1}/{len(chunks)}] Fallido tras {max_retries} intentos — {label}"
                            )
                            fail_count += 1
                            return
                        wait = 10 * (2 ** (attempt - 1))  # 10, 20, 40, 80s
                        logger.warning(
                            f"  [{i+1}/{len(chunks)}] {label} (intento {attempt}/{max_retries}), "
                            f"esperando {wait}s..."
                        )
                        await asyncio.sleep(wait)

                elapsed_ep = time.perf_counter() - t_ep
                logger.info(
                    f"  [{i+1}/{len(chunks)}] OK en {elapsed_ep:.1f}s  "
                    f"(progreso: {ok_count}/{len(chunks)})"
                )

        tasks = [ingest_chunk(i, chunk) for i, chunk in enumerate(chunks)]
        await asyncio.gather(*tasks)

        total_time = time.perf_counter() - t0
        logger.info("=" * 60)
        logger.info(f"  PIPELINE COMPLETADO — {ok_count} OK, {fail_count} fallidos de {len(chunks)}")
        logger.info(f"  Tiempo total: {total_time:.1f}s ({total_time/60:.1f} min)")
        logger.info("=" * 60)

    except Exception:
        logger.exception("Error durante la ingestión de chunks wiki")
        raise

    finally:
        logger.info("Cerrando conexión con Neo4j...")
        await graphiti.close()
        logger.info("Conexión cerrada correctamente")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Graphiti Wiki Ingestion Pipeline')
    parser.add_argument(
        '--max', type=int, default=None,
        help='Máximo número de chunks a ingestar (por defecto: todos)',
    )
    parser.add_argument(
        '--no-wipe', action='store_true',
        help='No borrar datos existentes: solo ingesta chunks que faltan (modo retry)',
    )
    args = parser.parse_args()
    asyncio.run(main(max_chunks=args.max, no_wipe=args.no_wipe))
