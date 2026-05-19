"""
src.document_ingestion.wiki.doc_chunking_wiki
Wikipedia chunking pipeline — Descarga artículos JSON desde Blob Storage,
divide el texto en chunks por secciones y sube a Cosmos DB (``Chunks-Wiki``)
Estrategia de Chunking — Wikipedia
-----------------------------------
Los artículos de Wikipedia son textos largos (media ~5-15k tokens) con:
  - Encabezados de sección (``== Título ==``, ``=== Subtítulo ===``)
  - 2 idiomas: es, en
  - Metadatos: categorías, pageid, URL
Pipeline:
  1. **Descarga** el JSON del artículo desde Blob Storage
     (``data/wikipedia/<lang>/json/<Title>.json``)
  2. **Parsea** el JSON y extrae ``contenido`` / ``text``
  3. **Convierte** encabezados Wikipedia (``==``) a Markdown (``#``)
  4. **Divide** por encabezados Markdown, fusionando fragmentos pequeños
     y subdividiendo los demasiado grandes
  5. **Genera embedding** para cada chunk
  6. **Sube** a Cosmos DB (``Chunks-Wiki``)
Ubicación en Blob Storage
-------------------------
::
    <AZURE_CONTAINER_NAME>/data/wikipedia/<lang>/json/<Title>.json
    donde <lang> ∈ {es, en}
"""
from __future__ import annotations
import asyncio
import json
import tiktoken
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional
from src.services.azure_storage_service import get_specific_file_from_blob_container
from src.config import config
from src.models.Timestamps import Timestamps
from src.models.doc_model import DocEntity
from src.document_ingestion.wiki.processchunks_wiki import (
    WikiArticle,
    wiki_text_to_markdown,
    markdown_chunk_wiki,
    detect_sections,
    detect_title,
    upload_chunk_wiki,
    mark_existing_chunks_as_deleted_wiki,
)
# Configuración global
storageaccountname = config.azure_storage_account_name
storageaccountkey = config.azure_storage_key
containername = config.azure_container_name
encoding = tiktoken.encoding_for_model(config.azure_openai_emb_name)
# ===========================================================================
def get_text_split_wiki(
    docId: str,
    SessionId: str = "",
    doc_entity: Optional[dict] = None,
    CDU: str = "DOCPROCESS",
) -> None:
    """Procesa un artículo de Wikipedia (JSON) en chunks y los sube a Cosmos DB
    Parameters
    ----------
    docId : str
        Ruta del blob, e.g. ``"data/wikipedia/es/json/Cervantes.json"``
    SessionId : str
        ID de sesión para trazabilidad
    doc_entity : dict | None
        Metadatos del documento (compatibles con DocEntity)
    CDU : str
        Código de unidad funcional
    """
    if doc_entity is None:
        doc_entity = {}
    doc_entity = DocEntity(**doc_entity).model_dump(exclude_none=True)
    timestamps: list[Timestamps] = [Timestamps("01 init")]
    startrun = datetime.now()
    lchunks = 0
    ExceptionReason = ""
    try:
        Call_id = SessionId + docId.split("/")[-1].split(".")[0] if "/" in docId else SessionId + docId
        display_name = doc_entity.get("doc_nombre", docId)
        # Derivar idioma del path: data/wikipedia/<lang>/json/<file>.json
        normalized = docId.replace("\\", "/")
        parts = [p for p in normalized.split("/") if p]
        source_language = "es"
        for i, p in enumerate(parts):
            if p == "wikipedia" and i + 1 < len(parts):
                source_language = parts[i + 1]
                break
        source_language = doc_entity.get("language", source_language)
        print(f"Procesando Wiki: {docId} (idioma: {source_language})")
        # ── PASO 1: Descargar JSON ────────────────────────────────────
        timestamps.append(Timestamps("02 downloadBlob"))
        file_download = asyncio.run(
            get_specific_file_from_blob_container(
                storageaccountname, storageaccountkey, containername,
                docId, SessionId, Call_id, CDU,
            )
        )
        if not file_download:
            raise FileNotFoundError(f"Wiki blob no encontrado: {docId}")
        # ── PASO 2: Parsear JSON ─────────────────────────────────────
        timestamps.append(Timestamps("03 parseJSON"))
        wiki_data = json.loads(file_download.decode("utf-8"))
        article = WikiArticle.from_dict(wiki_data)
        print(f"  Artículo: {article.title} ({len(article.text)} chars)")
        if not article.text or len(article.text) < 100:
            print(f"  Artículo demasiado corto, se omite: {article.title}")
            return
        # ── PASO 3: Marcar chunks previos como borrados ──────────────
        timestamps.append(Timestamps("04 markDeleted"))
        deleted = mark_existing_chunks_as_deleted_wiki(article.title)
        if deleted > 0:
            print(f"  {deleted} chunks previos marcados como borrados")
        # ── PASO 4: Convertir a Markdown y dividir en chunks ─────────
        timestamps.append(Timestamps("05 chunking"))
        markdown_text = wiki_text_to_markdown(article.text)
        chunk_data = markdown_chunk_wiki(markdown_text, 2000, 0.1, 800, 3000)
        lchunks = len(chunk_data)
        print(f"  Generados {lchunks} chunks")
        # ── PASO 5: Embedding + subida a Cosmos (PARALELIZADO) ───────
        timestamps.append(Timestamps("06 uploadChunks"))
        def _process_chunk(idx: int, chunk_item) -> str:
            chunk, ancestors = chunk_item
            title = detect_title(chunk) or f"{article.title} — Chunk {idx}"
            # Sections = ancestros (h2, h1…) + encabezados propios del chunk (h3…)
            # dict.fromkeys preserva orden y elimina duplicados
            sections = list(dict.fromkeys(ancestors + detect_sections(chunk)))
            upload_chunk_wiki(
                index=idx,
                title=title,
                sections=sections,
                content=chunk,
                article=article,
                blob_name=docId,
                doc_entity=doc_entity,
                SessionId=SessionId,
                Call_id=Call_id,
                CDU=CDU,
            )
            return f"Chunk {idx}/{lchunks} OK"
        max_workers = min(lchunks, config.max_workers_docs or 3)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_process_chunk, i, c): i
                for i, c in enumerate(chunk_data, start=1)
            }
            for future in as_completed(futures):
                try:
                    msg = future.result()
                    print(f"    OK {msg}")
                except Exception as e:
                    print(f"    KO Chunk {futures[future]} falló: {e}")
        timestamps.append(Timestamps("07 done"))
        elapsed = (datetime.now() - startrun).total_seconds()
        print(f"{docId}: {lchunks} chunks subidos a Cosmos en {elapsed:.2f}s")
    except FileNotFoundError as err:
        ExceptionReason = f"Archivo no encontrado: {err}"
        print(f"ERROR [{docId}]: {ExceptionReason}")
    except json.JSONDecodeError as err:
        ExceptionReason = f"Error parseando JSON: {err}"
        print(f"ERROR [{docId}]: {ExceptionReason}")
    except Exception as err:
        if timestamps:
            ExceptionReason = f"Error en {timestamps[-1].get_nombre()}: {err}"
        else:
            ExceptionReason = f"Error: {err}"
        print(f"ERROR [{docId}]: {ExceptionReason}")
        import traceback
        traceback.print_exc()
