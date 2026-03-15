"""
Templates de prompts para los tres casos de uso: cvs, eu, wiki
Sin dependencias externas – Python puro.
"""

from typing import List, Dict
from src.config import config


class PromptTemplates:
    """Prompts centralizados, diferenciados por caso de uso."""

    # ------------------------------------------------------------------
    # RAG Fusion – generación de queries sintéticas (compartido)
    # ------------------------------------------------------------------
    @staticmethod
    def rag_fusion_synthetic_queries(query: str, k: int = 4) -> str:
        lang_map = {"es": "en español", "en": "in English", "pt": "em português"}
        lang = lang_map.get(config.language, "en español")

        return f"""Eres un experto en reformular preguntas para mejorar búsquedas de información.

Pregunta original: "{query}"

Genera {k} versiones alternativas de esta pregunta que:
- Mantengan la intención original
- Usen sinónimos y diferentes estructuras gramaticales
- Exploren diferentes perspectivas del tema
- Sean claras y específicas

Responde ÚNICAMENTE con las {k} preguntas reformuladas, una por línea, numeradas.
Escribe todo {lang}.

Ejemplo:
1. [primera reformulación]
2. [segunda reformulación]
..."""

    # ------------------------------------------------------------------
    # Generación principal – dispatcher por use_case
    # ------------------------------------------------------------------
    @classmethod
    def rag_main_generation(
        cls,
        query: str,
        context: List[Dict],
        max_chars: int = None,
        use_case: str = "cvs",
    ) -> str:
        max_chars = max_chars or config.max_answer_chars
        dispatch = {
            "cvs":  cls._rag_cvs,
            "eu":   cls._rag_eu,
            "wiki": cls._rag_wiki,
        }
        fn = dispatch.get(use_case, cls._rag_generic)
        return fn(query=query, context=context, max_chars=max_chars)

    # ------------------------------------------------------------------
    # CASO DE USO: CVs  (búsqueda de talento)
    # ------------------------------------------------------------------
    @staticmethod
    def _rag_cvs(query: str, context: List[Dict], max_chars: int) -> str:
        context_text = ""
        unique_docs: set = set()

        for i, chunk in enumerate(context, 1):
            title     = chunk.get("title", "Sin título")
            content   = chunk.get("content", "")
            doc_title = chunk.get("doc_title", "Unknown")
            pages     = chunk.get("pages", "N/A")

            content_preview = content[:800] + ("..." if len(content) > 800 else "")
            context_text += (
                f"\n[CV {i}]: {doc_title}\n"
                f"Sección: {title}\nPáginas: {pages}\nContenido:\n{content_preview}\n---\n"
            )
            unique_docs.add(doc_title)

        num_docs = len(unique_docs)

        return f"""Eres un asistente de búsqueda de talento especializado en análisis de CVs técnicos.

Tu misión es encontrar y listar TODOS los candidatos relevantes basándote en los CVs proporcionados y el historial de conversación.

**CONTEXTO – CVs DISPONIBLES ({num_docs} documentos únicos):**
{context_text}

**PREGUNTA DEL USUARIO:**
{query}

**INSTRUCCIONES:**

[1] COBERTURA COMPLETA: Lista TODOS los candidatos que cumplan el criterio. No te limites a "algunos ejemplos".

[2] ESTILO NATURAL: Para cada candidato escribe un párrafo fluido con:
- Nombre completo en negrita
- Qué tiene (skill/certificación/experiencia)
- Contexto relevante del CV (años, proyectos, otras skills)
- Nombre del archivo entre paréntesis al final

[3] HISTORIAL CONVERSACIONAL:
- Pronombres plurales ("tienen", "son", etc.) → habla SOLO de candidatos mencionados antes
- "¿alguien más?" → aporta candidatos DIFERENTES
- "que no sea X" → excluye explícitamente a X

[4] FORMATO:
<p><strong>Encontré [X] candidatos con [criterio]:</strong></p>
<p><strong>1. Nombre Completo</strong><br>[Descripción natural]. (CV: archivo.pdf)</p>
...
<p><strong>Resumen:</strong> [X] candidatos en {num_docs} CVs revisados.</p>

Si no hay candidatos:
<p><strong>No encontré candidatos con [criterio exacto].</strong></p>
<p>Sugerencias: [alternativas concretas]</p>

[5] SINÓNIMOS AUTOMÁTICOS:
- "Spark" → PySpark, Databricks, Spark SQL
- "Azure cert" → AZ-900, DP-600, AI-900, PL-300…
- "Senior" → Sr., Lead, Principal, Consultor Senior
- "ML" → Machine Learning, Deep Learning, AI

RESPONDE EN ESPAÑOL. Máximo {max_chars} caracteres."""

    # ------------------------------------------------------------------
    # CASO DE USO: EU  (legislación y documentos de la UE)
    # ------------------------------------------------------------------
    @staticmethod
    def _rag_eu(query: str, context: List[Dict], max_chars: int) -> str:
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

[2] ESTRUCTURA DE RESPUESTA:
<p><strong>Respuesta:</strong> [respuesta directa y concisa]</p>

<p><strong>Base normativa:</strong></p>
<ul>
  <li>[Documento], [Artículo/Sección] – [extracto relevante]</li>
</ul>

<p><strong>Contexto adicional:</strong> [matices, excepciones o información complementaria si existe]</p>

[3] HONESTIDAD: Si la información no está en los documentos proporcionados, indícalo claramente.
No inventes referencias normativas.

[4] IDIOMA: Responde en el idioma de la pregunta (español por defecto).

Máximo {max_chars} caracteres."""

    # ------------------------------------------------------------------
    # CASO DE USO: Wiki  (artículos enciclopédicos de Wikipedia)
    # ------------------------------------------------------------------
    @staticmethod
    def _rag_wiki(query: str, context: List[Dict], max_chars: int) -> str:
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

[2] ESTRUCTURA:
<p><strong>Respuesta:</strong> [respuesta directa]</p>

<p><strong>Detalle:</strong> [explicación más completa extrayendo lo relevante de los artículos]</p>

<p><strong>Fuentes:</strong></p>
<ul>
  <li>[Título del artículo Wikipedia] – [sección relevante]</li>
</ul>

[3] PRECISIÓN: Usa únicamente información presente en los artículos. Si la pregunta va más allá
de lo disponible en los fragmentos, indícalo.

[4] IDIOMA: Responde en el idioma de la pregunta (español por defecto).

Máximo {max_chars} caracteres."""

    # ------------------------------------------------------------------
    # Fallback genérico
    # ------------------------------------------------------------------
    @staticmethod
    def _rag_generic(query: str, context: List[Dict], max_chars: int) -> str:
        context_text = "\n".join(
            f"[{i}] {c.get('doc_title','?')} – {c.get('content','')[:600]}"
            for i, c in enumerate(context, 1)
        )
        return f"""Eres un asistente experto. Responde la siguiente pregunta basándote en el contexto.

CONTEXTO:
{context_text}

PREGUNTA: {query}

Responde de forma clara y concisa. Máximo {max_chars} caracteres."""

    # ------------------------------------------------------------------
    # Prompt de pregunta directa (sin contexto RAG)
    # ------------------------------------------------------------------
    @staticmethod
    def direct_question_prompt(query: str, max_chars: int = None) -> str:
        max_chars = max_chars or config.max_answer_chars
        return f"""Eres un asistente experto para el proyecto {config.project_name}.

PREGUNTA: {query}

Responde de forma clara y profesional. Máximo {max_chars} caracteres.
Usa formato HTML (<p>, <ul>, <li>, <strong>) para estructurar la respuesta."""
