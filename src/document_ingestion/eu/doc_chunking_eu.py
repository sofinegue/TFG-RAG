"""
src.document_ingestion.eu.doc_chunking_eu

EU chunking pipeline — Descarga PDFs de legislación europea desde Blob Storage,
extrae contenido vía Document Intelligence, divide en chunks Markdown y sube
a Cosmos DB (container ``Chunks-EU``).

Estrategia de Chunking — EU
----------------------------
Los PDFs de EUR-Lex son documentos legislativos con:
  - Estructura de encabezados (títulos, artículos, anexos).
  - Tablas (annexes, sustancias, umbrales, etc.).
  - 5 idiomas: en, es, fr, pt, it.

Pipeline:
  1. **Descarga** el PDF desde Blob Storage (``data/eu/<lang>/<file>.pdf``).
  2. **Extrae** texto Markdown con Azure Document Intelligence (``prebuilt-layout``).
  3. **Limpia** encabezados/pies repetidos que aparecen en cada página.
  4. **Divide** en chunks por encabezados Markdown (MarkdownHeaderTextSplitter),
     fusionando fragmentos pequeños y subdividiendo los demasiado grandes.
  5. **Genera embedding** (Azure OpenAI) para cada chunk.
  6. **Sube** a Cosmos DB (``Chunks-EU``).

Ubicación en Blob Storage
-------------------------
::
    <AZURE_CONTAINER_NAME>/data/eu/<lang>/<section>_<code>.pdf
    donde <lang> ∈ {en, es, fr, pt, it}
"""
from __future__ import annotations

import asyncio
import re
import tiktoken
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Optional

from src.services.azure_storage_service import get_specific_file_from_blob_container
from src.services.docintelligence_service import get_content_from_document
from src.config import config
from src.models.Timestamps import Timestamps
from src.models.doc_model import DocEntity
from src.document_ingestion.eu.processchunks_eu import (
    markdown_chunk_eu,
    detect_headers,
    detect_title,
    upload_chunk_eu,
    mark_existing_chunks_as_deleted_eu,
)

# Configuración global
storageaccountname = config.azure_storage_account_name
storageaccountkey = config.azure_storage_key
containername = config.azure_container_name
encoding = tiktoken.encoding_for_model(config.azure_openai_emb_name)


# ===========================================================================

def get_text_split_eu(
    docId: str,
    SessionId: str = "",
    doc_entity: Optional[dict] = None,
    CDU: str = "DOCPROCESS",
) -> None:
    """Procesa un PDF de legislación EU en chunks y los sube a Cosmos DB.

    Parameters
    ----------
    docId : str
        Ruta del blob, e.g. ``"data/eu/en/legislation_2001.pdf"``.
    SessionId : str
        ID de sesión para trazabilidad.
    doc_entity : dict | None
        Metadatos del documento (compatibles con DocEntity).
    CDU : str
        Código de unidad funcional.
    """
    if doc_entity is None:
        doc_entity = {}
    doc_entity = DocEntity(**doc_entity).model_dump(exclude_none=True)

    timestamps: List[Timestamps] = [Timestamps("01 init")]
    startrun = datetime.now()
    lchunks = 0
    ExceptionReason = ""

    try:
        Call_id = SessionId + docId.split("_")[0] if "_" in docId else SessionId + docId
        display_name = doc_entity.get("doc_nombre", docId)

        # Derivar idioma del path: data/eu/<lang>/file.pdf
        normalized = docId.replace("\\", "/")
        parts = [p for p in normalized.split("/") if p]
        source_language = "en"
        for i, p in enumerate(parts):
            if p == "eu" and i + 1 < len(parts):
                source_language = parts[i + 1]
                break
        source_language = doc_entity.get("language", source_language)

        print(f"Procesando EU PDF: {docId} (idioma: {source_language})")

        # ── PASO 1: Descargar PDF ──────────────────────────────────────
        timestamps.append(Timestamps("02 downloadBlob"))
        file_download = asyncio.run(
            get_specific_file_from_blob_container(
                storageaccountname, storageaccountkey, containername,
                docId, SessionId, Call_id, CDU,
            )
        )
        if not file_download:
            raise FileNotFoundError(f"EU blob no encontrado: {docId}")

        # ── PASO 2: Document Intelligence → Markdown ──────────────────
        timestamps.append(Timestamps("03 docIntelligence"))
        result = asyncio.run(
            get_content_from_document(
                file_download=file_download,
                SessionId=SessionId,
                boolformulas=False,
            )
        )
        full_content: str = result.content
        print(f"  Contenido extraído: {len(full_content)} caracteres")

        # ── PASO 3: Marcar chunks previos como borrados ───────────────
        timestamps.append(Timestamps("04 markDeleted"))
        deleted = mark_existing_chunks_as_deleted_eu(display_name)
        if deleted > 0:
            print(f"  {deleted} chunks previos marcados como borrados")

        # ── PASO 4: Insertar marcas de página y limpiar ───────────────
        timestamps.append(Timestamps("05 cleanContent"))

        # Insertar marcas de página PG<n> si Document Intelligence las provee
        page_contents = {}
        last_page_number = 0
        if docId.lower().endswith(".pdf"):
            for paragraph in getattr(result, "paragraphs", []) or []:
                for region in getattr(paragraph, "bounding_regions", []) or []:
                    pn = region.page_number
                    content = paragraph.content
                    if pn > last_page_number:
                        last_page_number = pn
                    page_contents.setdefault(pn, []).append(content)

        # Añadir etiquetas PG
        last_pos = 0
        for pn in sorted(page_contents.keys()):
            paras = page_contents[pn]
            if not paras:
                continue
            last_content = paras[-1]
            pos = full_content.find(last_content, last_pos)
            if pos != -1:
                pos += len(last_content)
                page_label = f" PG{pn} "
                full_content = full_content[:pos] + f"\n{page_label}" + full_content[pos:]
                last_pos = pos

        # Limpiar ruido (figuras, fórmulas, comentarios)
        full_content = re.sub(r"!\[\]\(figures/\d+\)\n?", "", full_content)
        full_content = re.sub(r"<!--.*?-->", "", full_content, flags=re.DOTALL)
        full_content = re.sub(r'PageHeader="[^"]*"', "", full_content)
        full_content = re.sub(r'PageFooter="[^"]*"', "", full_content)

        # ── PASO 5: Chunking ─────────────────────────────────────────
        timestamps.append(Timestamps("06 chunking"))
        chunks = markdown_chunk_eu(full_content, 2000, 0.1, 1000, 3000)
        lchunks = len(chunks)
        print(f"  Generados {lchunks} chunks")

        # ── PASO 6: Embedding + subida a Cosmos (PARALELIZADO) ────────
        timestamps.append(Timestamps("07 uploadChunks"))

        # Detectar idioma más común
        top_lang = source_language

        def _process_chunk(idx: int, chunk: str) -> str:
            pages = re.findall(r"PG(\d+)", chunk)
            if pages:
                page_range = f"{pages[0]}-{pages[-1]}" if pages[0] != pages[-1] else pages[0]
            else:
                page_range = str(idx)

            title = detect_title(chunk)
            sections = (
                detect_headers(chunk, 1)
                + detect_headers(chunk, 2)
                + detect_headers(chunk, 3)
            )

            # Extraer tablas simples del chunk
            tables = re.findall(r"(\|(?:[^\n]*\|)+\n(?:\|[^\n]*\|)+)", chunk, re.MULTILINE)

            upload_chunk_eu(
                index=idx,
                page_range=page_range,
                title=title,
                sections=sections,
                content=chunk,
                blob_name=display_name,
                top_language=top_lang,
                tables=tables,
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
                for i, c in enumerate(chunks, start=1)
            }
            for future in as_completed(futures):
                try:
                    msg = future.result()
                    print(f"    ✓ {msg}")
                except Exception as e:
                    print(f"    ✗ Chunk {futures[future]} falló: {e}")

        timestamps.append(Timestamps("08 done"))
        elapsed = (datetime.now() - startrun).total_seconds()
        print(f"{docId}: {lchunks} chunks subidos a Cosmos en {elapsed:.2f}s")

    except FileNotFoundError as err:
        ExceptionReason = f"Archivo no encontrado: {err}"
        print(f"ERROR [{docId}]: {ExceptionReason}")

    except Exception as err:
        if timestamps:
            ExceptionReason = f"Error en {timestamps[-1].get_nombre()}: {err}"
        else:
            ExceptionReason = f"Error: {err}"
        print(f"ERROR [{docId}]: {ExceptionReason}")
        import traceback
        traceback.print_exc()
