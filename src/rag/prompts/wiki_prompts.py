"""
Prompts específicos para el caso de uso Wiki / Wikipedia.
"""
from typing import Dict, List

LANG_NAMES = {
    "es": "español",
    "en": "English",
    "fr": "français",
    "it": "italiano",
    "pt": "português",
}


class WikiPrompts:
    """Prompts centrados en respuestas enciclopédicas basadas en artículos de Wikipedia."""

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

            content_preview = content[:800] + ("..." if len(content) > 800 else "")
            context_text += (
                f"\n[ARTÍCULO {i}]: {doc_title}\n"
                f"Sección: {title}\nContenido:\n{content_preview}\n---\n"
            )
            unique_docs.add(doc_title)

        num_docs = len(unique_docs)

        return f"""Eres un asistente enciclopédico que responde preguntas de conocimiento general
basándose en artículos de Wikipedia.

**CONTEXTO – ARTÍCULOS ({num_docs} artículos):**
{context_text}

**PREGUNTA:**
{query}

**INSTRUCCIONES:**

[1] RESPUESTA DIRECTA: Empieza con una respuesta concisa a la pregunta.

[2] ESTRUCTURA (Markdown):
**Respuesta:** [respuesta directa]

**Detalle:** [explicación más completa extrayendo lo relevante de los artículos]

**Fuentes:**
- [Título del artículo Wikipedia] – [sección relevante]

[3] PRECISIÓN: Usa únicamente información presente en los artículos. Si la pregunta va más allá
de lo disponible en los fragmentos, indícalo.

[4] IDIOMA: Responde en {LANG_NAMES.get(language, 'español')}.

Máximo {max_chars} caracteres."""

    # ------------------------------------------------------------------
    # Prompt de RAG Fusion (adaptado al dominio enciclopédico)
    # ------------------------------------------------------------------
    @staticmethod
    def rag_fusion(query: str, k: int) -> str:
        return f"""Eres un experto en búsqueda de información enciclopédica y conocimiento general.

Pregunta original: "{query}"

Genera {k} versiones alternativas de esta pregunta para buscar en artículos de Wikipedia que:
- Usen términos alternativos o sinónimos del concepto principal
- Amplíen a conceptos relacionados, causas o consecuencias
- Rephraseén desde distintos ángulos (histórico, científico, geográfico, etc.)
- Varíen el nivel de abstracción (general ↔ específico)

Responde ÚNICAMENTE con las {k} preguntas reformuladas, una por línea, numeradas.

Ejemplo:
1. [reformulación con sinónimos o términos alternativos]
2. [reformulación desde otro ángulo temático]
..."""
