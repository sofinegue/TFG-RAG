"""
Prompts específicos para el caso de uso EU / Legislación de la Unión Europea.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from src.config import config

# ---------------------------------------------------------------------------
# Catálogo del corpus EU (lista exhaustiva de documentos, generado offline por
# ``test/scripts/build_eu_catalog.py``). Se carga una sola vez por proceso y
# se inyecta en el prompt para que el LLM pueda responder con precisión a
# preguntas de conteo / listado / identificación / estructura, incluso cuando
# el documento concreto no haya sido recuperado entre los chunks.
# ---------------------------------------------------------------------------
_CATALOG_PATH = Path(__file__).resolve().parents[3] / "data" / "eu" / "catalog.json"
_CATALOG_CACHE: Dict[str, List[Dict]] | None = None


def _load_catalog() -> Dict[str, List[Dict]]:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return _CATALOG_CACHE
    try:
        _CATALOG_CACHE = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        _CATALOG_CACHE = {}
    return _CATALOG_CACHE


def _format_catalog(language: str) -> str:
    """Construye un bloque de texto compacto con el catálogo del corpus.

    Devuelve cadena vacía si no hay catálogo para el idioma solicitado.
    """
    catalog = _load_catalog().get(language) or _load_catalog().get("en") or []
    if not catalog:
        return ""

    # Resúmenes agregados que el LLM puede leer directamente.
    by_type: Dict[str, int] = {}
    by_year: Dict[str, int] = {}
    for e in catalog:
        by_type[e.get("type") or "?"] = by_type.get(e.get("type") or "?", 0) + 1
        ay = e.get("adoption_year") or e.get("act_year") or "?"
        by_year[ay] = by_year.get(ay, 0) + 1

    type_summary = ", ".join(f"{k}={v}" for k, v in sorted(by_type.items()))
    year_summary = ", ".join(f"{k}={v}" for k, v in sorted(by_year.items()))

    lines = [
        f"TOTAL: {len(catalog)} documentos únicos.",
        f"Por tipo: {type_summary}.",
        f"Por año de adopción: {year_summary}.",
        "",
        "Lista exhaustiva (filename | tipo | subtipo | nº páginas | nº artículos | nº acto | año adopción | emisor):",
    ]
    for e in catalog:
        lines.append(
            "  - {fn} | {t} | {st} | pgs={p} | arts={a} | acto={ac} | adop={ay} | {iss}".format(
                fn=e.get("filename", "?"),
                t=e.get("type", "?"),
                st=e.get("subtype") or "-",
                p=e.get("num_pages", 0),
                a=e.get("num_articles", 0),
                ac=e.get("act_number") or "-",
                ay=e.get("adoption_year") or e.get("act_year") or "-",
                iss=e.get("issuer") or "-",
            )
        )
        title = (e.get("long_title") or e.get("title") or "").strip()
        if title:
            lines.append(f"      título: {title}")
    return "\n".join(lines)


class EUPrompts:
    """Prompts centrados en consultas sobre normativa, directivas y reglamentos de la UE."""

    # ------------------------------------------------------------------
    # Prompt principal de generación
    # ------------------------------------------------------------------
    @staticmethod
    def generation(query: str, context: List[Dict], max_chars: int, language: str = "es") -> str:
        context_text = ""
        unique_docs: set = set()

        for i, chunk in enumerate(context, 1):
            title     = chunk.get("title", "Sin título")
            content   = chunk.get("content", "")
            doc_title = chunk.get("doc_title", "Unknown")
            pages     = chunk.get("pages", "N/A")

            content_preview = content[:800] + ("..." if len(content) > 800 else "")
            context_text += (
                f"\n[DOC {i}]: {doc_title}\n"
                f"Sección: {title}\nPáginas: {pages}\nContenido:\n{content_preview}\n---\n"
            )
            unique_docs.add(doc_title)

        num_docs = len(unique_docs)
        catalog_block = _format_catalog(language)
        catalog_section = (
            f"\n**CATÁLOGO COMPLETO DEL CORPUS UE (autoritativo y exhaustivo):**\n"
            f"{catalog_block}\n"
            if catalog_block else ""
        )

        return f"""Eres un experto en legislación y documentos institucionales de la Unión Europea.

Tu tarea es responder con precisión a preguntas sobre normativa, directivas, reglamentos y acuerdos de la UE
basándote en el CATÁLOGO COMPLETO del corpus (metadatos exhaustivos) y en los fragmentos recuperados.
{catalog_section}
**FRAGMENTOS RECUPERADOS – {num_docs} documentos únicos en este lote:**
{context_text}

**PREGUNTA:**
{query}

**INSTRUCCIONES:**

[1] FUENTES:
   - Para preguntas de **conteo / listado / existencia / identificación / estructura básica**
     (cuántos reglamentos, cuántas decisiones, lista todos los X, ¿existe Y?, título de Z,
     páginas/artículos de un documento, documento más largo/corto, año de adopción, emisor),
     USA EL CATÁLOGO COMPLETO. Es exhaustivo: cubre TODOS los documentos del corpus,
     no solo los recuperados.
   - Para **contenido específico** (qué dice el artículo X, qué referencias incluye, etc.),
     usa los FRAGMENTOS RECUPERADOS y cita literalmente.
   - Si la pregunta solicita una lista de filenames, devuélvelos tal y como aparecen en el
     catálogo (p. ej. ``OJ_L_202600197_EN``).

[2] FORMATO DE RESPUESTA (Markdown):
**Respuesta:** [respuesta directa y concisa; si piden un número o un listado, dalo primero]

**Base normativa:**
- [Documento], [Artículo/Sección o "catálogo"] – [extracto / dato relevante]

**Contexto adicional:** [matices, excepciones o información complementaria si existe]

[3] PRECISIÓN:
   - Cuando un documento esté en el catálogo pero no en los fragmentos, sigue contestando
     usando los metadatos del catálogo en vez de decir "no está en los documentos".
   - No inventes referencias normativas ni contenido de artículos.

[4] IDIOMA: Responde en {config.get_lang_name(language)}.

Máximo {max_chars} caracteres."""

    # ------------------------------------------------------------------
    # Prompt de RAG Fusion (adaptado al dominio legal/normativo)
    # ------------------------------------------------------------------
    @staticmethod
    def rag_fusion(query: str, k: int) -> str:
        return f"""Eres un experto en legislación y documentos normativos de la Unión Europea.

Pregunta original: "{query}"

Genera {k} versiones alternativas de esta pregunta para buscar en documentos legales y normativos que:
- Usen terminología jurídica equivalente (ej. "ley" → "reglamento", "directiva", "normativa")
- Incluyan referencias posibles a artículos o secciones relacionadas
- Amplíen a conceptos legales afines o excepciones a la regla
- Consideren distintas formas de redacción formal/técnica

Responde ÚNICAMENTE con las {k} preguntas reformuladas, una por línea, numeradas.

Ejemplo:
1. [reformulación con terminología jurídica alternativa]
2. [reformulación apuntando a artículos o disposiciones]
..."""
