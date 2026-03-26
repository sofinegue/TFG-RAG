"""
Prompts específicos para el caso de uso CVs / Talento.

Centralizados aquí para que el handler cvs/handler.py los importe y
los tests de prompts puedan validarlos de forma aislada.
"""
from typing import Dict, List


class CVsPrompts:
    """Prompts centrados en búsqueda de candidatos y análisis de CVs técnicos."""

    # ------------------------------------------------------------------
    # Prompt principal de generación
    # ------------------------------------------------------------------
    @staticmethod
    def generation(query: str, context: List[Dict], max_chars: int) -> str:
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

[4] FORMATO (Markdown):
**Encontré [X] candidatos con [criterio]:**

**1. Nombre Completo**  
[Descripción natural]. (CV: archivo.pdf)

...

**Resumen:** [X] candidatos en {num_docs} CVs revisados.

Si no hay candidatos:
**No encontré candidatos con [criterio exacto].**

Sugerencias: [alternativas concretas]

[5] SINÓNIMOS AUTOMÁTICOS:
- "Spark" → PySpark, Databricks, Spark SQL
- "Azure cert" → AZ-900, DP-600, AI-900, PL-300…
- "Senior" → Sr., Lead, Principal, Consultor Senior
- "ML" → Machine Learning, Deep Learning, AI

RESPONDE EN ESPAÑOL. Máximo {max_chars} caracteres."""

    # ------------------------------------------------------------------
    # Prompt de RAG Fusion (adaptado al dominio de talento)
    # ------------------------------------------------------------------
    @staticmethod
    def rag_fusion(query: str, k: int) -> str:
        return f"""Eres un experto en búsqueda de talento y recursos humanos técnicos.

Pregunta original: "{query}"

Genera {k} versiones alternativas de esta pregunta para buscar candidatos en CVs que:
- Incluyan sinónimos de tecnologías (ej. "ML" → "Machine Learning", "aprendizaje automático")
- Amplíen a certificaciones o roles relacionados (ej. "Python" → "Django, FastAPI, Pandas")
- Consideren distintos niveles de experiencia (junior, senior, lead, principal)
- Usen variantes bilingües de términos técnicos (inglés/español)

Responde ÚNICAMENTE con las {k} preguntas reformuladas, una por línea, numeradas.

Ejemplo:
1. [reformulación con sinónimos tecnológicos]
2. [reformulación con roles y certificaciones]
..."""

    # ------------------------------------------------------------------
    # Prompt mini-LLM para clasificación de chunks por fiabilidad
    # ------------------------------------------------------------------
    @staticmethod
    def mini_llm_batch(query: str, chunks: list, reliability_label: str) -> str:
        context_text = ""
        for i, chunk in enumerate(chunks, 1):
            doc_title = chunk.get("doc_title", "Unknown")
            content   = chunk.get("content", "")[:600]
            context_text += f"\n[CV {i}] {doc_title}:\n{content}\n---"

        return f"""Eres un asistente de búsqueda de talento. Tu tarea es analizar fragmentos de CVs
y determinar si los candidatos son relevantes para la consulta del usuario.

Fiabilidad de estos fragmentos: {reliability_label}

CONSULTA DEL USUARIO:
{query}

FRAGMENTOS DE CVs:
{context_text}

INSTRUCCIONES:
- Analiza CADA fragmento y decide si el candidato es relevante para la consulta.
- Para los candidatos relevantes, extrae su nombre completo y una breve justificación.
- Si ninguno es relevante, indica "Ningún candidato relevante en este grupo."

FORMATO DE RESPUESTA:
data: <lista de nombres completos relevantes separados por " | ", o "ninguno">
reasoning: <explicación breve de por qué cada nombre fue incluido o excluido>

Responde SOLO en el formato indicado."""
