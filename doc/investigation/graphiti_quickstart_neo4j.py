"""
Copyright 2025, Zep Software, Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

# Limitar coroutines paralelas ANTES de importar graphiti_core.
# Aura Free soporta pocas conexiones concurrentes; el default (20) agota el pool.
os.environ.setdefault('SEMAPHORE_LIMIT', '3')

from openai import AsyncOpenAI
from neo4j import AsyncGraphDatabase

from graphiti_core import Graphiti
from graphiti_core.driver.neo4j_driver import Neo4jDriver
from graphiti_core.embedder.azure_openai import AzureOpenAIEmbedderClient
from graphiti_core.llm_client.azure_openai_client import AzureOpenAILLMClient
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.nodes import EpisodeType
from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF

#################################################
# CONFIGURATION
#################################################
# Usa la configuración centralizada del proyecto
# (src/config.py) para Neo4j y logging.
#################################################

# Añadir la raíz del proyecto al path para importar src.config
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))

from src.config import config  # noqa: E402

# Configure logging con el nivel definido en config
logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

# Neo4j connection parameters desde config centralizado
neo4j_uri = config.neo4j_uri
neo4j_user = config.neo4j_user
neo4j_password = config.neo4j_password

# Azure OpenAI – URL base compatible con la API v1 de OpenAI
azure_base_url = config.azure_openai_url
if not azure_base_url.endswith('/'):
    azure_base_url += '/'
if not azure_base_url.endswith('openai/v1/'):
    azure_base_url += 'openai/v1/'
azure_api_key = config.azure_openai_key

# Silenciar las notificaciones verbosas de Neo4j (índices que ya existen)
logging.getLogger('neo4j.notifications').setLevel(logging.WARNING)

logger.info("Configuración cargada desde src.config")
logger.info(f"  Neo4j URI:       {neo4j_uri}")
logger.info(f"  Neo4j User:      {neo4j_user}")
logger.info(f"  Azure Base URL:  {azure_base_url}")
logger.info(f"  LLM Model:       {config.azure_openai_mini_name}")
logger.info(f"  Emb Deployment:  {config.azure_openai_emb_deployment}")
logger.info(f"  Emb Model Name:  {config.azure_openai_emb_name}")
logger.info(f"  Log Level:       {config.log_level}")

if not neo4j_uri or not neo4j_user or not neo4j_password:
    logger.error("Faltan variables de conexión a Neo4j (NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD)")
    raise ValueError('NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD must be set')


async def main():
    #################################################
    # INITIALIZATION
    #################################################
    # Connect to Neo4j and set up Graphiti indices
    # This is required before using other Graphiti
    # functionality
    #################################################

    logger.info("=== INICIO: Inicializando clientes Azure OpenAI ===")
    t0 = time.perf_counter()

    # Cliente async compartido para LLM y embeddings
    azure_client = AsyncOpenAI(base_url=azure_base_url, api_key=azure_api_key)
    logger.info("  AsyncOpenAI client creado")

    # LLM client (chat / extraction)
    # small_model debe apuntar al mismo deployment para evitar que Graphiti
    # intente usar un modelo por defecto (gpt-4.1-nano) que no existe en Azure.
    llm_config = LLMConfig(
        api_key=azure_api_key,
        base_url=azure_base_url,
        model=config.azure_openai_mini_name,
        small_model=config.azure_openai_mini_name,
    )
    llm_client = AzureOpenAILLMClient(azure_client=azure_client, config=llm_config)
    logger.info(f"  LLM client configurado (model={config.azure_openai_mini_name})")

    # Embedder client
    # La API v1 de Azure necesita el nombre del DEPLOYMENT (e.g. "ada-002"),
    # no el nombre del modelo (e.g. "text-embedding-ada-002").
    emb_config = config.get_embedding_model_config()
    embedder = AzureOpenAIEmbedderClient(
        azure_client=azure_client,
        model=emb_config.deployment,
    )
    logger.info(f"  Embedder configurado (deployment={emb_config.deployment})")

    # Cross-encoder / reranker (reutiliza el mismo cliente Azure)
    reranker = OpenAIRerankerClient(config=llm_config, client=azure_client)
    logger.info("  Reranker configurado (OpenAIRerankerClient via Azure)")

    # Inicializar driver Neo4j con nombre de BD explícito.
    # En Aura la BD NO se llama 'neo4j' sino el ID de la instancia (e.g. '6396cf17').
    logger.info(f"  Conectando a Neo4j (database={config.neo4j_database})...")
    neo4j_driver = Neo4jDriver(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password,
        database=config.neo4j_database,
    )
    # Reemplazar el driver interno con uno que limite el pool de conexiones.
    # Aura Free soporta ~5 conexiones concurrentes; con el default (100) se
    # agotan y aparece "failed to obtain a connection from the pool" timeout.
    neo4j_driver.client = AsyncGraphDatabase.driver(
        uri=neo4j_uri,
        auth=(neo4j_user, neo4j_password),
        max_connection_pool_size=5,
        connection_acquisition_timeout=120,
    )
    logger.info("  Neo4j pool limitado a 5 conexiones (Aura Free)")

    # Inicializar Graphiti con driver custom + Azure clients
    graphiti = Graphiti(
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=reranker,
        graph_driver=neo4j_driver,
    )
    logger.info(f"Graphiti inicializado en {time.perf_counter() - t0:.3f}s")

    try:
        #################################################
        # ADDING EPISODES
        #################################################
        # Episodes are the primary units of information
        # in Graphiti. They can be text or structured JSON
        # and are automatically processed to extract entities
        # and relationships.
        #################################################

        logger.info("=== FASE 1: Preparando episodios para ingestión ===")

        # Episodes list containing both text and JSON episodes
        episodes = [
            {
                'content': 'Kamala Harris is the Attorney General of California. She was previously '
                'the district attorney for San Francisco.',
                'type': EpisodeType.text,
                'description': 'podcast transcript',
            },
            {
                'content': 'As AG, Harris was in office from January 3, 2011 – January 3, 2017',
                'type': EpisodeType.text,
                'description': 'podcast transcript',
            },
            {
                'content': {
                    'name': 'Gavin Newsom',
                    'position': 'Governor',
                    'state': 'California',
                    'previous_role': 'Lieutenant Governor',
                    'previous_location': 'San Francisco',
                },
                'type': EpisodeType.json,
                'description': 'podcast metadata',
            },
            {
                'content': {
                    'name': 'Gavin Newsom',
                    'position': 'Governor',
                    'term_start': 'January 7, 2019',
                    'term_end': 'Present',
                },
                'type': EpisodeType.json,
                'description': 'podcast metadata',
            },
        ]

        logger.info(f"Total de episodios a ingestar: {len(episodes)}")

        # Add episodes to the graph
        for i, episode in enumerate(episodes):
            episode_body = (
                episode['content']
                if isinstance(episode['content'], str)
                else json.dumps(episode['content'])
            )
            logger.info(
                f"  [{i+1}/{len(episodes)}] Ingesting episode 'Freakonomics Radio {i}' "
                f"(type={episode['type'].value}, desc='{episode['description']}', "
                f"body_len={len(episode_body)} chars)"
            )

            t_ep = time.perf_counter()
            await graphiti.add_episode(
                name=f'Freakonomics Radio {i}',
                episode_body=episode_body,
                source=episode['type'],
                source_description=episode['description'],
                reference_time=datetime.now(timezone.utc),
            )
            logger.info(
                f"  [{i+1}/{len(episodes)}] Episodio añadido OK en {time.perf_counter() - t_ep:.3f}s"
            )

        logger.info("=== FASE 1 COMPLETADA: Todos los episodios ingestados ===")

        #################################################
        # BASIC SEARCH
        #################################################
        # The simplest way to retrieve relationships (edges)
        # from Graphiti is using the search method, which
        # performs a hybrid search combining semantic
        # similarity and BM25 text retrieval.
        #################################################

        search_query = 'Who was the California Attorney General?'
        logger.info(f"=== FASE 2: Búsqueda híbrida (semantic + BM25) ===")
        logger.info(f"  Query: '{search_query}'")

        t_search = time.perf_counter()
        results = await graphiti.search(search_query)
        elapsed = time.perf_counter() - t_search

        logger.info(f"  Búsqueda completada en {elapsed:.3f}s — {len(results)} resultados")

        for idx, result in enumerate(results):
            logger.info(f"  Resultado {idx+1}:")
            logger.info(f"    UUID:  {result.uuid}")
            logger.info(f"    Fact:  {result.fact}")
            if hasattr(result, 'valid_at') and result.valid_at:
                logger.info(f"    Valid from: {result.valid_at}")
            if hasattr(result, 'invalid_at') and result.invalid_at:
                logger.info(f"    Valid until: {result.invalid_at}")

        #################################################
        # CENTER NODE SEARCH
        #################################################
        # For more contextually relevant results, you can
        # use a center node to rerank search results based
        # on their graph distance to a specific node
        #################################################

        logger.info("=== FASE 3: Reranking con center node ===")

        if results and len(results) > 0:
            center_node_uuid = results[0].source_node_uuid
            logger.info(f"  Usando center_node_uuid del primer resultado: {center_node_uuid}")

            t_rerank = time.perf_counter()
            reranked_results = await graphiti.search(
                search_query, center_node_uuid=center_node_uuid
            )
            elapsed_rerank = time.perf_counter() - t_rerank

            logger.info(
                f"  Reranking completado en {elapsed_rerank:.3f}s — "
                f"{len(reranked_results)} resultados"
            )

            for idx, result in enumerate(reranked_results):
                logger.info(f"  Resultado reranked {idx+1}:")
                logger.info(f"    UUID:  {result.uuid}")
                logger.info(f"    Fact:  {result.fact}")
                if hasattr(result, 'valid_at') and result.valid_at:
                    logger.info(f"    Valid from: {result.valid_at}")
                if hasattr(result, 'invalid_at') and result.invalid_at:
                    logger.info(f"    Valid until: {result.invalid_at}")
        else:
            logger.warning("  Sin resultados en la búsqueda inicial; no se puede hacer reranking")

        #################################################
        # NODE SEARCH USING SEARCH RECIPES
        #################################################
        # Graphiti provides predefined search recipes
        # optimized for different search scenarios.
        # Here we use NODE_HYBRID_SEARCH_RRF for retrieving
        # nodes directly instead of edges.
        #################################################

        node_query = 'California Governor'
        logger.info("=== FASE 4: Búsqueda de nodos con NODE_HYBRID_SEARCH_RRF ===")
        logger.info(f"  Query: '{node_query}'")

        node_search_config = NODE_HYBRID_SEARCH_RRF.model_copy(deep=True)
        node_search_config.limit = 5
        logger.info(f"  Config: limit={node_search_config.limit}")

        t_node = time.perf_counter()
        node_search_results = await graphiti._search(
            query=node_query,
            config=node_search_config,
        )
        elapsed_node = time.perf_counter() - t_node

        logger.info(
            f"  Búsqueda de nodos completada en {elapsed_node:.3f}s — "
            f"{len(node_search_results.nodes)} nodos encontrados"
        )

        for idx, node in enumerate(node_search_results.nodes):
            node_summary = node.summary[:100] + '...' if len(node.summary) > 100 else node.summary
            logger.info(f"  Nodo {idx+1}:")
            logger.info(f"    UUID:    {node.uuid}")
            logger.info(f"    Name:    {node.name}")
            logger.info(f"    Summary: {node_summary}")
            logger.info(f"    Labels:  {', '.join(node.labels)}")
            logger.info(f"    Created: {node.created_at}")
            if hasattr(node, 'attributes') and node.attributes:
                for key, value in node.attributes.items():
                    logger.info(f"    Attr {key}: {value}")

        logger.info("=== TODAS LAS FASES COMPLETADAS ===")

    except Exception:
        logger.exception("Error durante la ejecución del quickstart")
        raise

    finally:
        #################################################
        # CLEANUP
        #################################################
        # Always close the connection to Neo4j when
        # finished to properly release resources
        #################################################

        logger.info("Cerrando conexión con Neo4j...")
        await graphiti.close()
        logger.info("Conexión cerrada correctamente")


if __name__ == '__main__':
    asyncio.run(main())