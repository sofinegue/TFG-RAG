"""
add_context.py — Enriquecimiento semántico de chunks con preguntas y respuestas.

Para cada chunk de una colección de Cosmos DB:
  1. Lee su contenido.
  2. Llama a un LLM mini para generar una pregunta y su respuesta correcta.
  3. Persiste el resultado en el campo QuestionsText de Cosmos DB.
  4. Actualiza directamente el campo QuestionsText en el índice de Azure Search
     (merge parcial, sin necesidad de relanzar el indexer).

Uso desde línea de comandos:
    python -m src.rag.prompts.add_context --use-case cvs
    python -m src.rag.prompts.add_context --use-case eu --workers 5 --batch-size 50
    python -m src.rag.prompts.add_context --use-case wiki --overwrite

Argumentos:
    --use-case    Caso de uso: cvs | eu | wiki  (obligatorio)
    --workers     Hilos paralelos de LLM       (default: 4)
    --batch-size  Docs por lote de Azure Search (default: 100)
    --overwrite   Re-genera aunque QuestionsText ya esté relleno
    --dry-run     Muestra qué haría pero no escribe nada
"""

from __future__ import annotations

import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from azure.core.credentials import AzureKeyCredential
from azure.cosmos import CosmosClient
from azure.search.documents import SearchClient
from openai import AzureOpenAI

from src.config import config, safe_create_kwargs

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("add_context")

# ---------------------------------------------------------------------------
# Mapeo use-case → colección Cosmos + índice Azure Search
# ---------------------------------------------------------------------------
USE_CASE_MAP: Dict[str, Dict[str, str]] = {
    "cvs": {
        "cosmos_container": config.cosmosdb_container_cvs,
        "search_index":     config.azure_search_index_cvs,
    },
    "eu": {
        "cosmos_container": config.cosmosdb_container_eu,
        "search_index":     config.azure_search_index_eu,
    },
    "wiki": {
        "cosmos_container": config.cosmosdb_container_wiki,
        "search_index":     config.azure_search_index_wiki,
    },
}

# ---------------------------------------------------------------------------
# Clientes
# ---------------------------------------------------------------------------

def _build_cosmos_container(container_name: str):
    client = CosmosClient(config.cosmos_endpoint, config.cosmos_key)
    db     = client.get_database_client(config.cosmosdb_database)
    return db.get_container_client(container_name)


def _build_search_client(index_name: str) -> SearchClient:
    return SearchClient(
        endpoint=config.azure_search_endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(config.azure_search_key),
    )


def _build_llm_client() -> tuple[AzureOpenAI, str]:
    """
    Devuelve (AzureOpenAI client, deployment_name) para el modelo mini.

    Prioridad de configuración:
      1. Entrada "gpt4o-mini" en MODELS_CONFIG  → usa sus credenciales.
      2. Fallback a azure_openai_url / azure_openai_key / azure_openai_mini_name.
    """
    mini_model_name = "gpt-5-mini"
    try:
        cfg = config.get_model_config(mini_model_name)
        client = AzureOpenAI(
            azure_endpoint=cfg.api_base,
            api_key=cfg.api_key,
            api_version=cfg.api_version,
        )
        return client, cfg.deployment
    except (ValueError, Exception):
        log.warning(
            "Modelo '%s' no encontrado en MODELS_CONFIG. "
            "Usando credenciales directas de AZURE_OPENAI_*.",
            mini_model_name,
        )

    # Fallback directo
    deployment = config.azure_openai_mini_name
    if not deployment:
        raise RuntimeError(
            "No se encontró configuración para el modelo mini. "
            "Añade 'gpt-5-mini' a MODELS_CONFIG o define AZURE_OPENAI_MINI_NAME."
        )
    client = AzureOpenAI(
        azure_endpoint=config.azure_openai_url,
        api_key=config.azure_openai_key,
        api_version=config.azure_openai_api_version,
    )
    return client, deployment


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def _build_qa_prompt(content: str, use_case: str) -> str:
    domain_hint = {
        "cvs":  "un currículum profesional (CV) técnico",
        "eu":   "un documento legal o normativo de la Unión Europea",
        "wiki": "un artículo enciclopédico de Wikipedia",
    }.get(use_case, "un fragmento de texto")

    return f"""Eres un experto en generación de preguntas para sistemas de recuperación de información (RAG).

Se te proporciona un fragmento de texto extraído de {domain_hint}.

FRAGMENTO:
\"\"\"
{content[:1200]}
\"\"\"

Tu tarea:
1. Formula UNA sola pregunta concreta y específica cuya respuesta esté completamente contenida en el fragmento anterior.
2. Escribe la respuesta correcta y completa a esa pregunta, basándote ÚNICAMENTE en el fragmento.

Responde con el siguiente formato exacto (sin texto adicional):
PREGUNTA: <pregunta>
RESPUESTA: <respuesta>"""


# ---------------------------------------------------------------------------
# Lógica principal por chunk
# ---------------------------------------------------------------------------

def _generate_qa(
    chunk: Dict,
    llm_client: AzureOpenAI,
    deployment: str,
    use_case: str,
) -> Optional[str]:
    """
    Llama al LLM mini y devuelve la cadena 'PREGUNTA: …\\nRESPUESTA: …'.
    Devuelve None si el contenido es demasiado corto o la llamada falla.
    """
    content = (chunk.get("content") or "").strip()
    if len(content) < 80:   # chunk demasiado corto para generar QA útil
        return None

    prompt = _build_qa_prompt(content, use_case)
    try:
        response = llm_client.chat.completions.create(
            **safe_create_kwargs(
                model=deployment,
                messages=[{"role": "user", "content": prompt}],
                temperature=config.temperature,
                max_completion_tokens=400,
            )
        )
        qa_text = response.choices[0].message.content.strip()
        # Validación mínima: debe contener las dos etiquetas
        if "PREGUNTA:" in qa_text and "RESPUESTA:" in qa_text:
            return qa_text
        log.warning("Respuesta del LLM sin formato esperado para chunk %s", chunk.get("id"))
        return None
    except Exception as exc:
        log.error("Error LLM en chunk %s: %s", chunk.get("id"), exc)
        return None


def _process_chunk(
    chunk: Dict,
    llm_client: AzureOpenAI,
    deployment: str,
    use_case: str,
    cosmos_container,
    overwrite: bool,
    dry_run: bool,
) -> bool:
    """
    Procesa un chunk individual: genera QA y actualiza Cosmos DB.
    Devuelve True si se procesó (o se habría procesado en dry-run).
    """
    existing_qa = (chunk.get("QuestionsText") or "").strip()
    if existing_qa and not overwrite:
        return False  # ya tiene contenido y no forzamos sobreescritura

    qa_text = _generate_qa(chunk, llm_client, deployment, use_case)
    if not qa_text:
        return False

    if dry_run:
        log.info("[DRY-RUN] chunk=%s → %s", chunk.get("id"), qa_text[:80])
        return True

    # Actualizar Cosmos DB (upsert completo del documento con el campo nuevo)
    chunk["QuestionsText"] = qa_text
    try:
        cosmos_container.upsert_item(chunk)
    except Exception as exc:
        log.error("Error actualizando Cosmos chunk %s: %s", chunk.get("id"), exc)
        return False

    return True


# ---------------------------------------------------------------------------
# Actualización por lotes en Azure Search
# ---------------------------------------------------------------------------

def _push_to_search(
    chunks: List[Dict],
    search_client: SearchClient,
    batch_size: int,
    dry_run: bool,
) -> None:
    """
    Envía los QuestionsText actualizados a Azure Search como merge parcial.
    Solo necesita los campos 'id' y 'QuestionsText'.
    """
    documents = [
        {"id": c["id"], "QuestionsText": c.get("QuestionsText", "")}
        for c in chunks
        if c.get("QuestionsText")
    ]
    if not documents:
        return

    for i in range(0, len(documents), batch_size):
        batch = documents[i : i + batch_size]
        if dry_run:
            log.info("[DRY-RUN] Azure Search merge: %d documentos", len(batch))
            continue
        try:
            result = search_client.merge_or_upload_documents(batch)
            failed = [r for r in result if not r.succeeded]
            if failed:
                log.warning("%d documentos fallaron en Azure Search", len(failed))
        except Exception as exc:
            log.error("Error en merge Azure Search (lote %d): %s", i // batch_size, exc)


# ---------------------------------------------------------------------------
# Orquestador principal
# ---------------------------------------------------------------------------

def enrich_chunks(
    use_case: str,
    workers: int = config.max_workers_docs,
    batch_size: int = 100,
    overwrite: bool = False,
    dry_run: bool = False,
) -> None:
    if use_case not in USE_CASE_MAP:
        raise ValueError(f"use_case debe ser uno de: {list(USE_CASE_MAP.keys())}")

    mapping          = USE_CASE_MAP[use_case]
    cosmos_container = _build_cosmos_container(mapping["cosmos_container"])
    search_client    = _build_search_client(mapping["search_index"])
    llm_client, deployment = _build_llm_client()

    # --- 1. Leer todos los chunks activos de Cosmos ---
    log.info("📥 Leyendo chunks de Cosmos: db=%s, colección=%s",
             config.cosmosdb_database, mapping["cosmos_container"])
    query = "SELECT * FROM c WHERE (c.isDeleted != true OR NOT IS_DEFINED(c.isDeleted))"
    try:
        chunks: List[Dict] = list(
            cosmos_container.query_items(query, enable_cross_partition_query=True)
        )
    except Exception as exc:
        log.error("No se pudieron leer chunks de Cosmos: %s", exc)
        sys.exit(1)

    total    = len(chunks)
    to_process = [
        c for c in chunks
        if overwrite or not (c.get("QuestionsText") or "").strip()
    ]
    log.info("📊 Total chunks: %d | A procesar: %d (overwrite=%s)", total, len(to_process), overwrite)

    if not to_process:
        log.info("✅ Nada que procesar. Usa --overwrite para regenerar todos.")
        return

    # --- 2. Generar QA en paralelo + actualizar Cosmos ---
    processed = 0
    updated_chunks: List[Dict] = []

    log.info("🤖 Generando preguntas/respuestas con modelo mini [workers=%d]...", workers)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                _process_chunk,
                chunk, llm_client, deployment, use_case,
                cosmos_container, overwrite, dry_run,
            ): chunk
            for chunk in to_process
        }
        for future in as_completed(futures):
            chunk = futures[future]
            try:
                ok = future.result()
            except Exception as exc:
                log.error("Excepción en chunk %s: %s", chunk.get("id"), exc)
                ok = False
            if ok:
                processed += 1
                updated_chunks.append(chunk)
            if processed % 50 == 0 and processed:
                log.info("   ... %d/%d procesados", processed, len(to_process))

    log.info("✅ Chunks actualizados en Cosmos: %d/%d", processed, len(to_process))

    # --- 3. Actualizar Azure Search (merge parcial) ---
    if updated_chunks:
        log.info("🔍 Actualizando Azure Search (índice: %s)...", mapping["search_index"])
        _push_to_search(updated_chunks, search_client, batch_size, dry_run)
        log.info("✅ Azure Search actualizado (%d documentos)", len(updated_chunks))

    log.info("🏁 Proceso completado. use_case=%s | procesados=%d | total=%d",
             use_case, processed, total)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enriquece chunks de Cosmos DB con preguntas y respuestas generadas por LLM."
    )
    parser.add_argument(
        "--use-case", required=True, choices=list(USE_CASE_MAP.keys()),
        help="Colección de Cosmos a procesar: cvs | eu | wiki",
    )
    parser.add_argument(
        "--workers", type=int, default=config.max_workers_docs,
        help=f"Número de hilos paralelos para llamadas al LLM (default: {config.max_workers_docs})",
    )
    parser.add_argument(
        "--batch-size", type=int, default=100,
        help="Tamaño del lote para actualizaciones en Azure Search (default: 100)",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Regenera QA aunque QuestionsText ya esté relleno",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simula la ejecución sin escribir nada en Cosmos ni en Azure Search",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    enrich_chunks(
        use_case=args.use_case,
        workers=args.workers,
        batch_size=args.batch_size,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )
