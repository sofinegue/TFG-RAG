"""
Prompts específicos para el caso de uso EU / Legislación de la Unión Europea.
"""
from typing import Dict, List

from src.config import config


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

        return f"""Eres un experto en legislación y documentos institucionales de la Unión Europea.

Tu tarea es responder con precisión a preguntas sobre normativa, directivas, reglamentos y acuerdos de la UE
basándote exclusivamente en los fragmentos de documentos proporcionados.

**CONTEXTO – DOCUMENTOS UE ({num_docs} documentos únicos):**
{context_text}

**PREGUNTA:**
{query}

**INSTRUCCIONES:**

[1] PRECISIÓN LEGAL: Cita artículos, párrafos y números de regulación cuando sea posible.

[2] ESTRUCTURA DE RESPUESTA (Markdown):
**Respuesta:** [respuesta directa y concisa]

**Base normativa:**
- [Documento], [Artículo/Sección] – [extracto relevante]

**Contexto adicional:** [matices, excepciones o información complementaria si existe]

[3] HONESTIDAD: Si la información no está en los documentos proporcionados, indícalo claramente.
No inventes referencias normativas.

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
