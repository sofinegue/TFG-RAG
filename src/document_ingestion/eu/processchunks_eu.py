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
  3. Chunks pequeños (<min_tokens) se fusionan; splits con tablas cercanas
     se combinan; chunks grandes (>max_tokens) se subdividen respetando tablas.
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

from langchain_text_splitters import MarkdownHeaderTextSplitter  # usado en pruebas / comentado

from src.config import config
from src.services.openai_service import get_embedding
from src.services.cosmos_service import upload_doc_cosmos
from src.document_ingestion.processchunks import (
    split_markdown_by_sections,
    mark_existing_chunks_as_deleted
)

# Tokenizador (cl100k_base, igual que processchunks.py)
encoding = tiktoken.get_encoding("cl100k_base")

# Configuración Cosmos
cosmosendpoint = config.cosmos_endpoint
cosmoskey = config.cosmos_key
dbname = config.cosmosdb_database
containerdbname = config.cosmosdb_container_eu

# Documentos ya verificados en esta sesión (evita marcar borrados en cada chunk)
_checked_documents_eu: set = set()

# ===========================================================================
# Markdown chunking
# ===========================================================================

def markdown_chunk_eu(
    content: str,
    chunk_size: int = 2000,
    overlap_pct: float = 0.1,
    min_tokens: int = 1000,
    max_tokens: int = 8000,
) -> List[str]:
    """Divide contenido Markdown en chunks respetando encabezados (h1–h6).

    Usa un splitter regex propio (split_markdown_by_sections) que:
      - Produce exactamente 1 encabezado por chunk.
      - Descarta secciones vacías.
      - Subdivide con dividir_por_frases si la sección supera max_tokens.
    """
    return split_markdown_by_sections(content, max_tokens)


# ===========================================================================
# Helpers — detección de encabezados y limpieza
# ===========================================================================

def delete_noise(titles: List[str]) -> List[str]:
    """Limpia ruido de barras invertidas en títulos detectados."""
    cleaned = []
    for title in titles:
        title_cleaned = title.strip()
        cleaned_title = re.sub(r'\\\.', '.', title_cleaned)
        cleaned_title = re.sub(r'\\+', '', cleaned_title)
        cleaned.append(cleaned_title)
    return cleaned


def detect_headers(content: str, level: int) -> List[str]:
    pattern = r"^\s*{}(?!#)(.+)".format("#" * level)
    headers = re.findall(pattern, content, re.MULTILINE)
    return delete_noise(headers)


def detect_title(content: str) -> str:
    matches = re.findall(r"^\s*#\s(?!#)(.+)", content, re.MULTILINE)
    return matches[-1].strip() if matches else ""


def detect_and_remove_headers_footers(
    content: str, total_pages: int, avg: float = 0, min_occurrences: int = 7
) -> str:
    """Detecta y elimina líneas repetidas (cabeceras/pies de página) del Markdown."""
    special_patterns = [r":selected:", r":unselected:", r"\bs[ií]\b", r"\bno(n?)\b", r"procede"]
    special_regex = re.compile("|".join(special_patterns), re.IGNORECASE)
    lines = content.split("\n")
    counter = Counter(lines)
    common_lines = [
        line for line, count in counter.items()
        if count >= min_occurrences
        and count > int(total_pages * avg)
        and not special_regex.search(line.lower())
    ]
    return "\n".join(line for line in lines if line not in common_lines)


def extract_tables(markdown_text: str) -> List[str]:
    """Extrae tablas en formato Markdown del texto."""
    table_pattern = re.compile(r'(\|(?:[^\n]*\|)+\n(?:\|[^\n]*\|)+)', re.MULTILINE)
    return table_pattern.findall(markdown_text)


def get_top_locale(payload: Dict[str, Any], default: str = "und") -> str:
    """Devuelve el locale con mayor confidence del resultado de Doc Intelligence."""
    languages: List[Dict[str, Any]] = payload.get("languages", [])
    if not isinstance(languages, list):
        return default
    top: Optional[Dict[str, Any]] = None
    for item in languages:
        try:
            locale = item["locale"]
            conf = float(item["confidence"])
        except (KeyError, TypeError, ValueError):
            continue
        if top is None or conf > top["confidence"]:
            top = {"locale": locale, "confidence": conf}
    return top["locale"] if top else default


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

        # Verificar y marcar chunks previos solo en el primer chunk de cada documento
        if index == 1 and blob_name not in _checked_documents_eu:
            print(f"  🔍 Verificando chunks previos de '{blob_name}'...")
            mark_existing_chunks_as_deleted(
                doc_title=blob_name,
                cosmos_endpoint=cosmosendpoint,
                cosmos_key=cosmoskey,
                db_name=dbname,
                container_name=containerdbname,
            )
            _checked_documents_eu.add(blob_name)

        raw_id = str(uuid.uuid4())
        safe_id = re.sub(r"[^a-zA-Z0-9_\-=]", "-", raw_id)

        title = title.replace("#", "").strip()
        title = re.sub(r"\\{1,3}", "", title)

        content_clean = re.sub(r"PG\d+", "", content, flags=re.DOTALL).strip()
        embedding_content = content_clean.replace(":selected:", "").replace(":unselected:", "")

        chunkid = _generate_chunk_id(blob_name, index)
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
# Helpers internos
# ===========================================================================

def _generate_chunk_id(blob_name: str, index: int) -> str:
    """Genera un chunkId único en toda la BD: chunk{índice:04d}-{hash8 del documento}."""
    doc_hash = hashlib.sha256(blob_name.encode("utf-8")).hexdigest()[:8]
    return f"chunk{index:04d}-{doc_hash}"


def mark_existing_chunks_as_deleted_eu(doc_title: str) -> int:
    return mark_existing_chunks_as_deleted(
        doc_title=doc_title,
        cosmos_endpoint=cosmosendpoint,
        cosmos_key=cosmoskey,
        db_name=dbname,
        container_name=containerdbname,
    )
