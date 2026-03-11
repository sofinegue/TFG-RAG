"""
src.document_ingestion.wiki.processchunks_wiki

Funciones auxiliares para generar y subir chunks de artículos de Wikipedia
a Cosmos DB.

Diseño de chunking — Wikipedia
-------------------------------
Los artículos de Wikipedia se almacenan como JSON con:
  - ``titulo`` / ``title``:  título del artículo
  - ``idioma`` / ``language``:  "es" o "en"
  - ``pageid``:  ID de página Wikipedia
  - ``categorias`` / ``categories``:  lista de categorías
  - ``url``:  URL canónica del artículo
  - ``contenido`` / ``text``:  texto plano completo del artículo

Estrategia:
  1. El texto usa **encabezados con ``==``** (estilo Wikipedia).
     Se normalizan a Markdown (``#`` / ``##`` / ``###``).
  2. Se usa ``MarkdownHeaderTextSplitter`` para dividir respetando
     la estructura de secciones.
  3. Chunks pequeños se fusionan; chunks grandes se subdividen.
  4. Cada chunk recibe metadatos: categorías, URL, pageid, idioma.
  5. Se genera embedding y se sube a Cosmos DB → ``Chunks-Wiki``.

Campos clave del documento Cosmos
----------------------------------
::
    {
      "id", "chunkId", "docTitle", "sourcePath", "sourceCollection": "wikipedia",
      "sourceLanguage", "content", "categories", "wiki_url", "pageid",
      "Content_length", "Pages", "Title", "Sections", "nChunk", "isDeleted",
      "topLanguage", "embedding"
    }
"""
from __future__ import annotations

import hashlib
import re
import uuid
import tiktoken
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_text_splitters import MarkdownHeaderTextSplitter

from src.config import config
from src.services.openai_service import get_embedding
from src.services.cosmos_service import upload_doc_cosmos
from src.document_ingestion.processchunks import mark_existing_chunks_as_deleted

# Tokenizador
encoding = tiktoken.encoding_for_model(config.azure_openai_emb_name)

# Configuración Cosmos
cosmosendpoint = config.cosmos_endpoint
cosmoskey = config.cosmos_key
dbname = config.cosmosdb_database
containerdbname = config.cosmosdb_container_wiki


# ===========================================================================
# WikiArticle — parser de JSONs de Wikipedia
# ===========================================================================

class WikiArticle:
    """Parser de artículos de Wikipedia desde JSON.

    Acepta tanto el formato del generador (``titulo``, ``idioma``,
    ``categorias``, ``contenido``) como el esquema canónico
    (``title``, ``language``, ``categories``, ``text``).
    """

    def __init__(self) -> None:
        self.title: str = ""
        self.language: str = ""
        self.pageid: int = 0
        self.categories: List[str] = []
        self.url: str = ""
        self.text: str = ""

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WikiArticle":
        inst = cls()
        inst.title = d.get("title") or d.get("titulo", "")
        inst.language = d.get("language") or d.get("idioma", "")
        inst.pageid = d.get("pageid", 0)
        inst.categories = d.get("categories") or d.get("categorias", [])
        inst.url = d.get("url", "")
        inst.text = d.get("text") or d.get("contenido", "")
        return inst


# ===========================================================================
# Wikipedia text → Markdown conversion
# ===========================================================================

def wiki_text_to_markdown(text: str) -> str:
    """Convierte encabezados de estilo Wikipedia (``== … ==``) a Markdown.

    Ejemplos::
        == Sección ==        → # Sección
        === Subsección ===   → ## Subsección
        ==== Sub-sub ====    → ### Sub-sub
    """
    def _replace_heading(m: re.Match) -> str:
        equals = m.group(1)
        title = m.group(2).strip()
        level = min(len(equals), 5)  # máx 5 niveles
        return "#" * level + " " + title

    return re.sub(r"^(={2,})\s*(.+?)\s*\1\s*$", _replace_heading, text, flags=re.MULTILINE)


# ===========================================================================
# Markdown chunking (adaptado para Wiki)
# ===========================================================================

def markdown_chunk_wiki(
    content: str,
    chunk_size: int = 2000,
    overlap_pct: float = 0.1,
    min_tokens: int = 800,
    max_tokens: int = 3000,
) -> List[str]:
    """Divide contenido Markdown de Wikipedia en chunks."""
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
# Helpers — detección de secciones
# ===========================================================================

def detect_sections(content: str) -> List[str]:
    """Extrae encabezados Markdown del chunk."""
    headers = []
    for level in range(1, 6):
        pattern = r"^\s*{}(?!#)(.+)".format("#" * level)
        matches = re.findall(pattern, content, re.MULTILINE)
        headers.extend(h.strip() for h in matches)
    return headers


def detect_title(content: str) -> str:
    matches = re.findall(r"^\s*#\s(?!#)(.+)", content, re.MULTILINE)
    return matches[-1].strip() if matches else ""


# ===========================================================================
# Upload
# ===========================================================================

def upload_chunk_wiki(
    index: int,
    title: str,
    sections: List[str],
    content: str,
    article: WikiArticle,
    blob_name: str,
    doc_entity: dict,
    SessionId: str,
    Call_id: str,
    CDU: str,
) -> None:
    """Genera embedding y sube un chunk Wiki a Cosmos DB (Chunks-Wiki)."""
    try:
        raw_id = str(uuid.uuid4())
        safe_id = re.sub(r"[^a-zA-Z0-9_\-=]", "-", raw_id)

        token_count = len(encoding.encode(content))
        chunkid = _generate_chunk_id(blob_name, content, title, str(index))

        paragraph_data = {
            "id": safe_id,
            "chunkId": chunkid,
            "docTitle": article.title,
            "sourcePath": blob_name,
            "sourceCollection": "wikipedia",
            "sourceLanguage": article.language,
            "content": content,
            "categories": article.categories,
            "wiki_url": article.url,
            "pageid": article.pageid,
            "QuestionsText": "",
            "docSummary": "",
            "Content_length": token_count,
            "isCreated": datetime.now().isoformat(),
            "Pages": str(index),
            "Title": title or f"{article.title} — Chunk {index}",
            "Sections": sections,
            "nChunk": index,
            "isDeleted": False,
            "topLanguage": article.language,
            "Tables": [],
            "Formulas": [],
            "embedding": get_embedding(
                content,
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
        print(f"ERROR subiendo chunk Wiki a Cosmos: {err}")


# ===========================================================================
# mark_existing_chunks_as_deleted
# ===========================================================================

def mark_existing_chunks_as_deleted_wiki(doc_title: str) -> int:
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
