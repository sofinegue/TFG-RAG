"""
src.document_ingestion.cvs.doc_chunking_cvs

CV chunking pipeline — Descarga, parseo y subida de CVs estructurados a Cosmos DB.

Estrategia de Chunking
----------------------
Cada CV JSON se divide en **3 chunks semánticos** en lugar de un único bloque:

1. **Experiencia profesional** — Todas las entradas de experiencia laboral,
   enriquecidas con nombre, puesto y dominios de habilidad.
2. **Formación académica** — Estudios formales y otra información complementaria
   (certificaciones, idiomas, etc.).
3. **Skills (competencias)** — Hard skills y soft skills, con contexto del puesto
   y del candidato.

Cada chunk se enriquece con metadatos globales del CV (nombre, puesto, años de
experiencia, dominios) para mejorar el filtrado y la relevancia en búsquedas
vectoriales.

Ubicación de los CVs en Blob Storage
-------------------------------------
Los CVs se almacenan como JSONs en:
    ``<AZURE_CONTAINER_NAME>/data/cvs/<lang>/cv_XXX.json``
donde ``<lang>`` puede ser ``"es"`` o ``"en"``.

Esquema esperado del JSON
-------------------------
::
    {
      "nombre_apellidos": str,
      "puesto": str,
      "experiencia": [str, ...],
      "estudios": [str, ...],
      "hard_skills": [str, ...],   # también acepta "hard skills"
      "soft_skills": [str, ...],   # también acepta "soft skills"
      "otros": [str, ...]
    }
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
import tiktoken
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Optional

from src.services.azure_storage_service import get_specific_file_from_blob_container
from src.services.openai_service import get_embedding
from src.services.cosmos_service import upload_doc_cosmos
from src.config import config
from src.models.Timestamps import Timestamps
from src.models.doc_model import DocEntity
from src.document_ingestion.processchunks import mark_existing_chunks_as_deleted
from src.document_ingestion.cvs.processchunks_cvs import CVProcessor


# ===========================================================================
# Configuración global 
# ===========================================================================

storageaccountname = config.azure_storage_account_name
storageaccountkey = config.azure_storage_key
containername = config.azure_container_name          # investigation-rag-usecases
cosmosendpoint = config.cosmos_endpoint
cosmoskey = config.cosmos_key
dbname = config.cosmosdb_database                    # SNA
containerdbname = config.cosmosdb_container_cvs      # Chunks-CVs

# Tokenizador para contar tokens
encoding = tiktoken.encoding_for_model(config.azure_openai_emb_name)


# ===========================================================================

def get_text_split_cv(
    # blob_name: str,
    docId: str,
    SessionId: str = "",
    doc_entity: Optional[dict] = None,
    CDU: str = "DOCPROCESS",
) -> None:
    """Procesa un CV JSON en 3 chunks semánticos y los sube a Cosmos DB.

    Pipeline
    --------
    1. **Descarga** el JSON del CV desde Blob Storage
       (``data/cvs/<lang>/cv_XXX.json``).
    2. **Parsea** el JSON y crea una instancia de ``CVProcessor``.
    3. **Genera** 3 chunks semánticos (experiencia, formación, skills).
    4. **Enriquece** cada chunk con metadatos globales del CV.
    5. **Genera embedding** con Azure OpenAI.
    6. **Sube** los 3 chunks a Cosmos DB (container ``Chunks-CVs``).

    Parameters
    ----------
    # blob_name : str
    #     Ruta del blob en Azure Storage, e.g. ``"data/cvs/es/cv_001.json"``.
    docId : str
        Identificador único del documento (normalmente igual a blob_name).
    SessionId : str
        ID de sesión para trazabilidad.
    doc_entity : dict | None
        Diccionario con metadatos del documento (compatible con DocEntity).
    CDU : str
        Código de unidad funcional.
    """
    if doc_entity is None:
        doc_entity = {}
    doc_entity = DocEntity(**doc_entity).model_dump(exclude_none=True)

    timestamps_List: List[Timestamps] = []
    timestamps_List.append(Timestamps("01 init"))
    startrun = datetime.now()
    lchunks = 0
    ExceptionReason = ""

    try:
        Call_id = SessionId + docId.split("_")[0] if "_" in docId else SessionId + docId
        display_name = doc_entity.get("doc_nombre", docId)

        # Derivar idioma del path del blob: data/cvs/<lang>/cv_XXX.json
        normalized_id = docId.replace("\\", "/")
        path_parts = [p for p in normalized_id.split("/") if p]
        # path_parts típico: ["data", "cvs", "es", "cv_001.json"]
        source_language = "es"
        for i, part in enumerate(path_parts):
            if part == "cvs" and i + 1 < len(path_parts):
                source_language = path_parts[i + 1]
                break
        # Fallback al doc_entity
        source_language = doc_entity.get("language", source_language)

        print(f"Procesando CV: {docId} (idioma: {source_language})")

        # ──────────────────────────────────────────────────────────────────
        # PASO 1: Descargar el JSON del CV desde Blob Storage
        # ──────────────────────────────────────────────────────────────────
        timestamps_List.append(Timestamps("02 downloadBlob"))

        file_download = asyncio.run(get_specific_file_from_blob_container(
            storageaccountname, storageaccountkey, containername,
            docId, SessionId, Call_id, CDU
        ))

        if not file_download:
            raise FileNotFoundError(f"CV blob no encontrado: {docId}")

        # ──────────────────────────────────────────────────────────────────
        # PASO 2: Parsear el JSON
        # ──────────────────────────────────────────────────────────────────
        timestamps_List.append(Timestamps("03 parseJSON"))

        cv_data = json.loads(file_download.decode("utf-8"))
        cv = CVProcessor.from_dict(cv_data)
        print(f"  CV parseado: {cv.nombre_apellidos} — {cv.puesto}")

        # ──────────────────────────────────────────────────────────────────
        # PASO 3: Marcar chunks previos como borrados
        # ──────────────────────────────────────────────────────────────────
        timestamps_List.append(Timestamps("04 markDeletedChunks"))

        deleted_count = mark_existing_chunks_as_deleted(
            doc_title=display_name,
            cosmos_endpoint=cosmosendpoint,
            cosmos_key=cosmoskey,
            db_name=dbname,
            container_name=containerdbname,
        )
        if deleted_count > 0:
            print(f"  {deleted_count} chunks previos marcados como borrados")

        # ──────────────────────────────────────────────────────────────────
        # PASO 4: Generar los 3 chunks semánticos
        # ──────────────────────────────────────────────────────────────────
        timestamps_List.append(Timestamps("05 generateChunks"))

        chunks = cv.generate_semantic_chunks()
        global_meta = cv.get_global_metadata(source_language)
        lchunks = len(chunks)

        print(f"  Generados {lchunks} chunks semánticos")

        # ──────────────────────────────────────────────────────────────────
        # PASO 5: Embedding + subida a Cosmos DB  (PARALELIZADO)
        # ──────────────────────────────────────────────────────────────────
        timestamps_List.append(Timestamps("06 uploadChunksToCosmos"))

        def _process_single_chunk(chunk_idx: int, chunk_data: dict) -> str:
            """Genera embedding y sube un único chunk a Cosmos DB.
            Se ejecuta dentro de un ThreadPoolExecutor.
            Devuelve un mensaje de estado."""
            chunk_type = chunk_data["type"]       # experience | education | skills
            chunk_content = chunk_data["content"]
            chunk_metadata = {**chunk_data["metadata"]}  # copia para evitar race conditions

            # Merge global metadata
            chunk_metadata.update({
                "cv_id": docId,
                "chunk_index": chunk_idx,
                "language": source_language,
                "skill_domains": global_meta.get("skill_domains", []),
                "years_of_experience": global_meta.get("years_of_experience", 0),
            })

            # Generar embedding
            print(f"    Chunk {chunk_idx}/{lchunks} ({chunk_type}): generando embedding...")
            embedding_vector = get_embedding(
                chunk_content,
                config.azure_openai_emb_name,
                SessionId,
                Call_id,
                CDU,
                doc_entity,
            )

            # Contar tokens
            token_count = len(encoding.encode(chunk_content))

            # Título legible para el chunk
            chunk_title = f"{cv.nombre_apellidos} — {chunk_type.capitalize()}"

            # Construir documento Cosmos
            paragraph_data = {
                "id": _safe_cosmos_id(),
                "chunkId": _generate_chunk_id(display_name, chunk_idx),
                "docTitle": display_name,
                "sourcePath": docId,
                "sourceCollection": "cvs",
                "sourceLanguage": source_language,
                "content": chunk_content,
                "chunk_type": chunk_type,
                "nombre_apellidos": cv.nombre_apellidos,
                "puesto": cv.puesto,
                "QuestionsText": "",
                "docSummary": "",
                "Content_length": token_count,
                "isCreated": datetime.now().isoformat(),
                "Pages": str(chunk_idx),
                "Title": chunk_title,
                "Sections": [chunk_type],
                "nChunk": chunk_idx,
                "isDeleted": False,
                "topLanguage": source_language,
                "Tables": [],
                "Formulas": [],
                "embedding": embedding_vector,
                "metadata": chunk_metadata,
            }

            # Subir a Cosmos DB → Chunks-CVs
            print(f"    Chunk {chunk_idx}/{lchunks} ({chunk_type}): subiendo a Cosmos...")
            upload_doc_cosmos(
                cosmosendpoint, cosmoskey, dbname, containerdbname,
                paragraph_data, SessionId, Call_id, CDU,
            )
            return f"Chunk {chunk_idx} ({chunk_type}) OK"

        # Ejecutar los 3 chunks en paralelo (embedding + upload)
        max_workers = min(lchunks, config.max_workers_docs or 3)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_process_single_chunk, idx, cdata): idx
                for idx, cdata in enumerate(chunks, start=1)
            }
            for future in as_completed(futures):
                try:
                    msg = future.result()
                    print(f"    ✓ {msg}")
                except Exception as chunk_err:
                    idx = futures[future]
                    print(f"    ✗ Chunk {idx} falló: {chunk_err}")

        timestamps_List.append(Timestamps("07 done"))
        elapsed = (datetime.now() - startrun).total_seconds()
        print(f"{docId}: {lchunks} chunks subidos a Cosmos en {elapsed:.2f}s")

    except FileNotFoundError as err:
        success = False
        ExceptionReason = f"Archivo no encontrado: {err}"
        print(f"ERROR [{docId}]: {ExceptionReason}")

    except json.JSONDecodeError as err:
        success = False
        ExceptionReason = f"Error parseando JSON: {err}"
        print(f"ERROR [{docId}]: {ExceptionReason}")

    except Exception as err:
        success = False
        if timestamps_List:
            ExceptionReason = f"Error en {timestamps_List[-1].get_nombre()}: {err}"
        else:
            ExceptionReason = f"Error: {err}"
        print(f"ERROR [{docId}]: {ExceptionReason}")
        import traceback
        traceback.print_exc()

# ===========================================================================
# Helpers internos
# ===========================================================================

def _generate_chunk_id(blob_name: str, chunk_index: int) -> str:
    """Genera un chunkId único en toda la BD: chunk{índice:04d}-{hash8 del documento}."""
    doc_hash = hashlib.sha256(blob_name.encode("utf-8")).hexdigest()[:8]
    return f"chunk{chunk_index:04d}-{doc_hash}"


def _safe_cosmos_id() -> str:
    """Genera un ID seguro para Azure Search / Cosmos DB (solo alfanuméricos, _, -, =)."""
    return re.sub(r'[^a-zA-Z0-9_\-=]', '-', str(uuid.uuid4()))
