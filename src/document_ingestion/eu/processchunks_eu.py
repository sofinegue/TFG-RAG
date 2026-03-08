"""
src.document_ingestion.eu.processchunks_eu

Funciones auxiliares para generar y subir chunks de documentos legislativos
europeos (EUR-Lex) a Cosmos DB.

Diseño de chunking — EU
------------------------
Los PDFs de EUR-Lex son documentos legislativos estructurados con:
  - Títulos / artículos / secciones  (encabezados Markdown tras Doc Intelligence)
  - Tablas (anexos, listas de sustancias, etc.)
  - 5 idiomas: en, es, fr, pt, it

Estrategia:
  1. Document Intelligence extrae el PDF como Markdown.
  2. Se usa ``MarkdownHeaderTextSplitter`` (igual que ``processchunks.py``)
     para dividir en chunks respetando encabezados.
  3. Chunks pequeños (<min_tokens) se fusionan; chunks grandes (>max_tokens)
     se subdividen con solapamiento.
  4. Cada chunk recibe metadatos: sección legislativa, idioma, tipo de
     documento (legislation, legislation-preparation, inter-agree).
  5. Se genera embedding y se sube a Cosmos DB → ``Chunks-EU``.

Campos clave del documento Cosmos
----------------------------------
::
    {
      "id", "chunkId", "docTitle", "sourcePath", "sourceCollection": "eu",
      "sourceLanguage", "content", "doc_type", "Content_length",
      "Pages", "Title", "Sections", "nChunk", "isDeleted", "topLanguage",
      "Tables", "embedding"
    }
"""
from __future__ import annotations

import hashlib
import re
import uuid
import tiktoken
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_text_splitters import MarkdownHeaderTextSplitter

from src.config import config
from src.services.openai_service import get_embedding
from src.services.cosmos_service import upload_doc_cosmos

# Tokenizador
encoding = tiktoken.encoding_for_model(config.azure_openai_emb_name)

# Configuración Cosmos
cosmosendpoint = config.cosmos_endpoint
cosmoskey = config.cosmos_key
dbname = config.cosmosdb_database
containerdbname = config.cosmosdb_container_eu


# ===========================================================================
# Markdown chunking (adaptado de processchunks.py — NO se modifica el original)
# ===========================================================================

def markdown_chunk_eu(
    content: str,
    chunk_size: int = 2000,
    overlap_pct: float = 0.1,
    min_tokens: int = 1000,
    max_tokens: int = 3000,
) -> List[str]:
    """Divide contenido Markdown en chunks respetando encabezados.

    Réplica de ``processchunks.markdown_percentage`` adaptada para EU.
    """
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
        ("####", "Header 4"),
        ("#####", "Header 5"),
    ]

    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on, strip_headers=False,
    )
    md_splits = splitter.split_text(content)

    # Fusionar fragmentos pequeños
    combined: List[str] = []
    buf = ""
    for split in md_splits:
        tokens = len(encoding.encode(split.page_content))
        if tokens <= min_tokens:
            buf += split.page_content + " \n "
            if len(encoding.encode(buf)) > min_tokens:
                combined.append(buf)
                buf = ""
        else:
            if buf:
                combined.append(buf)
                buf = ""
            combined.append(split.page_content)
    if buf:
        combined.append(buf)

    # Subdividir chunks demasiado grandes
    final: List[str] = []
    for chunk in combined:
        tcount = len(encoding.encode(chunk))
        if tcount > 4000:
            overlap = int(chunk_size * overlap_pct)
            for i in range(0, len(chunk), chunk_size - overlap):
                part = chunk[i : i + chunk_size]
                final.append(part)
                if len(part) < chunk_size:
                    break
        else:
            final.append(chunk)

    return final


# ===========================================================================
# Helpers — detección de encabezados
# ===========================================================================

def detect_headers(content: str, level: int) -> List[str]:
    pattern = r"^\s*{}(?!#)(.+)".format("#" * level)
    headers = re.findall(pattern, content, re.MULTILINE)
    return [h.strip().replace("\\.", ".") for h in headers]


def detect_title(content: str) -> str:
    matches = re.findall(r"^\s*#\s(?!#)(.+)", content, re.MULTILINE)
    return matches[-1].strip() if matches else ""


def detect_doc_type(blob_name: str) -> str:
    """Extrae el tipo de documento EU del nombre del blob.
    
    Ejemplo: ``data/eu/en/legislation_2001.pdf`` → ``legislation``
    """
    fname = blob_name.replace("\\", "/").split("/")[-1]
    parts = fname.replace(".pdf", "").split("_")
    if len(parts) >= 1:
        return parts[0]  # legislation | legislation-preparation | inter-agree
    return "unknown"


# ===========================================================================
# Upload
# ===========================================================================

def upload_chunk_eu(
    index: int,
    page_range: str,
    title: str,
    sections: List[str],
    content: str,
    blob_name: str,
    top_language: str,
    tables: List[str],
    doc_entity: dict,
    SessionId: str,
    Call_id: str,
    CDU: str,
) -> None:
    """Genera embedding y sube un chunk EU a Cosmos DB (Chunks-EU)."""
    try:
        normalized = (blob_name or "").replace("\\", "/")
        path_parts = [p for p in normalized.split("/") if p]
        source_collection = "eu"
        source_language = path_parts[2] if len(path_parts) > 2 else doc_entity.get("language", "")

        raw_id = str(uuid.uuid4())
        safe_id = re.sub(r"[^a-zA-Z0-9_\-=]", "-", raw_id)

        content_clean = re.sub(r"PG\d+", "", content, flags=re.DOTALL).strip()
        embedding_content = content_clean.replace(":selected:", "").replace(":unselected:", "")

        chunkid = _generate_chunk_id(blob_name, content_clean, title, page_range)
        token_count = len(encoding.encode(content_clean))
        doc_type = detect_doc_type(blob_name)

        paragraph_data = {
            "id": safe_id,
            "chunkId": chunkid,
            "docTitle": blob_name,
            "sourcePath": normalized,
            "sourceCollection": source_collection,
            "sourceLanguage": source_language,
            "content": content_clean,
            "doc_type": doc_type,
            "QuestionsText": "",
            "docSummary": "",
            "Content_length": token_count,
            "isCreated": datetime.now().isoformat(),
            "Pages": page_range,
            "Title": title,
            "Sections": sections,
            "nChunk": index,
            "isDeleted": False,
            "topLanguage": top_language,
            "Tables": tables,
            "Formulas": [],
            "embedding": get_embedding(
                embedding_content,
                config.azure_openai_emb_name,
                SessionId,
                Call_id,
                CDU,
                doc_entity,
            ),
        }

        upload_doc_cosmos(
            cosmosendpoint, cosmoskey, dbname, containerdbname,
            paragraph_data, SessionId, Call_id, CDU,
        )
    except Exception as err:
        print(f"ERROR subiendo chunk EU a Cosmos: {err}")


# ===========================================================================
# mark_existing_chunks_as_deleted  (reutiliza la de processchunks.py)
# ===========================================================================

def mark_existing_chunks_as_deleted_eu(doc_title: str) -> int:
    """Marca como borrados todos los chunks previos del documento EU."""
    from src.document_ingestion.processchunks import mark_existing_chunks_as_deleted
    return mark_existing_chunks_as_deleted(
        doc_title=doc_title,
        cosmos_endpoint=cosmosendpoint,
        cosmos_key=cosmoskey,
        db_name=dbname,
        container_name=containerdbname,
    )


# ===========================================================================
# Helpers internos
# ===========================================================================

def _generate_chunk_id(doctitle: str, content: str, title: str, page: str) -> str:
    raw = (doctitle + content + (title or "") + (page or "")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
