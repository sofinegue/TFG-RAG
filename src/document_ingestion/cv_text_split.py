"""
CV chunking pipeline.

This module provides CV document processing by:
1. Downloading CV JSON from Azure Blob Storage
2. Parsing into CVProcessor instances
3. Generating 3 semantic chunks per CV (experience, education, skills)
4. Enriching each chunk with contextual metadata
5. Creating embeddings and uploading to Cosmos DB

Chunking Strategy
-----------------
Instead of one monolithic CV chunk, we create **3 semantic chunks** per CV:
- **experience**: Professional experience with enriched metadata
- **education**: Educational background with enriched metadata  
- **skills**: Hard and soft skills with enriched metadata

This approach:
✓ Improves vector search relevance by topic
✓ Enables targeted filtering (e.g., search only experience chunks)
✓ Preserves cross-references via metadata (name, position, domains)
✓ Scales better than monolithic chunking for vector stores
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Any

from tqdm import tqdm

from doc_ingestion.cv_chunking import CVProcessor, load_json
from models.doc_model import DocEntity
from services.azure_storage_service import get_specific_file_from_blob_container
from services.openai_service import get_embedding
from services.cosmos_service import upload_doc_cosmos
from document_ingestion.processchunks import (
    mark_existing_chunks_as_deleted,
)
from config import config


# ---------------------------------------------------------------------------
# Blob download
# ---------------------------------------------------------------------------

async def _download_cv_blob_async(blob_name: str) -> bytes:
    """Download CV JSON blob from the investigation container."""
    print(f"🔍 Downloading blob: {blob_name} from '{config.azure_container_name}'...")
    return await get_specific_file_from_blob_container(
        account_name=config.azure_storage_account,
        account_key=config.azure_storage_key,
        container_name=config.azure_container_name,
        specific_blob_name=blob_name,
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def get_cv_text_split(
    blob_name: str,
    doc_id: str,
    doc_entity: dict,
    session_id: str,
    *,
    call_id: str = "",
    cdu: str = "DOCPROCESS",
) -> None:
    """Process a CV JSON document into 3 semantic chunks and upload to Cosmos DB.

    Pipeline
    --------
    1. **Download** CV JSON from Blob Storage (``cvs/es/cv_001.json``)
    2. **Parse** into CVProcessor with structured fields
    3. **Generate** 3 semantic chunks (experience, education, skills)
    4. **Enrich** each chunk with extracted metadata
    5. **Embed** each chunk using Azure OpenAI
    6. **Upload** chunks to Cosmos DB (container ``Chunks-CVs``)

    Parameters
    ----------
    blob_name:
        Path of the CV file in Blob Storage, e.g. ``"cvs/es/cv_001.json"``.
    doc_id:
        Unique document identifier used for deduplication in Cosmos DB.
    doc_entity:
        Validated metadata dictionary from DocEntity.model_dump(exclude_none=True).
    session_id:
        Session identifier for log traceability.
    call_id:
        Optional call identifier for logging.
    cdu:
        Functional unit code forwarded to services.

    Raises
    ------
    FileNotFoundError
        If CV blob does not exist in Azure Storage.
    json.JSONDecodeError
        If blob content is not valid JSON.
    """
    start_time = datetime.now()
    language = doc_entity.get("language", "es")

    # Cosmos target for CV chunks
    cosmos_db = config.cosmosdb_database
    cosmos_container = config.cosmosdb_container_cvs   # "Chunks-CVs"

    try:
        print(f"Processing CV: {blob_name}")

        # Step 1: Download CV JSON from Blob Storage
        blob_content = asyncio.run(_download_cv_blob_async(blob_name))

        if not blob_content:
            raise FileNotFoundError(f"CV blob not found: {blob_name}")

        # Step 2: Parse JSON
        cv_data = json.loads(blob_content.decode("utf-8"))
        print(f"  Parsed CV JSON for: {cv_data.get('nombre_apellidos', 'Unknown')}")

        # Step 3: Create CVProcessor
        cv = CVProcessor.from_dict(cv_data)

        # Mark previous chunks as deleted before uploading new ones
        print(f"  Marking previous chunks as deleted...")
        deleted_count = mark_existing_chunks_as_deleted(
            doc_title=doc_id,
            cosmos_endpoint=config.cosmos_endpoint,
            cosmos_key=config.cosmos_key,
            db_name=cosmos_db,
            container_name=cosmos_container,
        )
        if deleted_count > 0:
            print(f"    Marked {deleted_count} previous chunks as deleted")

        # Step 4: Generate 3 semantic chunks
        print(f"  Generating semantic chunks...")
        chunks = cv.generate_semantic_chunks()
        global_metadata = cv.get_global_metadata(language)

        # Step 5: Process each chunk — embed + upload to Cosmos
        chunk_progress = tqdm(
            chunks,
            desc=f"  ⚙️  Chunks ({cv.nombre_apellidos[:20]})",
            unit="chunk",
            ncols=90,
            leave=False,
        )
        for chunk_idx, chunk in enumerate(chunk_progress, start=1):
            chunk_type = chunk["type"]       # experience | education | skills
            chunk_content = chunk["content"]
            chunk_metadata = chunk["metadata"]

            # Merge global metadata
            chunk_metadata.update({
                "cv_id": doc_id,
                "chunk_type": chunk_type,
                "chunk_index": chunk_idx,
                "global_candidate": global_metadata["candidate_name"],
                **{k: v for k, v in global_metadata.items() if k != "candidate_name"},
            })

            # Generate embedding
            chunk_progress.set_postfix_str(f"{chunk_type}: embedding", refresh=True)
            embedding = get_embedding(
                text=chunk_content,
                model=config.embedding_model,          # str "ada-002"
                session_id=session_id,
                call_id=call_id,
                cdu=cdu,
                entity=doc_entity,
            )

            # Build Cosmos document
            chunk_id = f"{doc_id}_{chunk_type[:3]}"
            import re, hashlib
            safe_id = re.sub(r'[^a-zA-Z0-9_\-=]', '-', str(uuid.uuid4()))

            normalized_blob = blob_name.replace("\\", "/")
            path_parts = [p for p in normalized_blob.split("/") if p]
            source_collection = path_parts[0] if path_parts else "cvs"
            source_language = path_parts[1] if len(path_parts) > 1 else language

            paragraph_data = {
                "id": safe_id,
                "chunkId": hashlib.md5(
                    f"{blob_name}|{chunk_type}|{chunk_idx}".encode()
                ).hexdigest(),
                "docTitle": blob_name,
                "sourcePath": normalized_blob,
                "sourceCollection": source_collection,
                "sourceLanguage": source_language,
                "sectionContent": chunk_content,
                "embeddingContent": chunk_content,
                "QuestionsText": "",
                "docSummary": "",
                "Content_length": len(chunk_content.split()),
                "isCreated": datetime.now().isoformat(),
                "Pages": chunk_idx,
                "Title": f"{cv.nombre_apellidos} - {chunk_type.capitalize()}",
                "Sections": embedding,
                "nChunk": chunk_idx,
                "isDeleted": False,
                "topLanguage": chunk_type,
                "Tables": [],
                "Formulas": [],
                "embedding": embedding,
                "metadata": chunk_metadata,
            }

            # Upload to Cosmos DB → Chunks-CVs
            chunk_progress.set_postfix_str(f"{chunk_type}: uploading", refresh=True)
            upload_doc_cosmos(
                config.cosmos_endpoint,
                config.cosmos_key,
                cosmos_db,
                cosmos_container,
                paragraph_data,
                session_id,
                call_id,
                cdu,
            )

        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"✅ CV processed successfully in {elapsed:.2f}s")
        print(f"   Generated {len(chunks)} chunks → {cosmos_container}")

    except FileNotFoundError as e:
        print(f"❌ File error: {e}")
        raise
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        raise
    except Exception as e:
        print(f"❌ Unexpected error processing CV: {e}")
        import traceback
        traceback.print_exc()
        raise


