"""
Prompts específicos para el caso de uso CVs / Talento.

Centralizados aquí para que el handler cvs/handler.py los importe y
los tests de prompts puedan validarlos de forma aislada.
"""
from typing import Dict, List

LANG_NAMES = {
    "es": "español",
    "en": "English",
    "fr": "français",
    "it": "italiano",
    "pt": "português",
}


class CVsPrompts:
    """Prompts centrados en búsqueda de perfiles y análisis de CVs técnicos de la compañía."""

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
                f"\n[CV {i}]: {doc_title}\n"
                f"Sección: {title}\nPáginas: {pages}\nContenido:\n{content_preview}\n---\n"
            )
            unique_docs.add(doc_title)

        num_docs = len(unique_docs)

        return f"""Los CVs que recibes pertenecen a miembros de la compañía (empleados, consultores, profesionales del equipo). NO son candidatos externos a un puesto; son perfiles internos de la organización.

Tu misión es encontrar y listar TODOS los perfiles relevantes basándote en los CVs proporcionados y el historial de conversación.

**CONTEXTO – CVs DISPONIBLES ({num_docs} documentos únicos):**
{context_text}

**PREGUNTA DEL USUARIO:**
{query}

**INSTRUCCIONES:**

[1] COBERTURA COMPLETA: Lista TODOS los perfiles que cumplan el criterio. No te limites a "algunos ejemplos".

[2] ESTILO NATURAL: Para cada persona escribe un párrafo fluido con:
- Nombre completo en negrita
- Qué tiene (skill/certificación/experiencia)
- Contexto relevante del CV (años, proyectos, otras skills)
- Nombre del archivo entre paréntesis al final

[3] HISTORIAL CONVERSACIONAL:
- Pronombres plurales ("tienen", "son", etc.) → habla SOLO de personas mencionadas antes
- "¿alguien más?" → aporta perfiles DIFERENTES
- "que no sea X" → excluye explícitamente a X

[4] FORMATO (Markdown):
**Encontré [X] perfiles con [criterio]:**

**1. Nombre Completo**  
[Descripción natural]. (CV: archivo.pdf)

...

**Resumen:** [X] perfiles en {num_docs} CVs revisados.

Si no hay resultados:
**No encontré perfiles con [criterio exacto].**

Sugerencias: [alternativas concretas]

[5] SINÓNIMOS AUTOMÁTICOS:
- "Spark" → PySpark, Databricks, Spark SQL
- "Azure cert" → AZ-900, DP-600, AI-900, PL-300…
- "Senior" → Sr., Lead, Principal, Consultor Senior
- "ML" → Machine Learning, Deep Learning, AI

RESPONDE EN {LANG_NAMES.get(language, 'español').upper()}. Máximo {max_chars} caracteres."""

    # ------------------------------------------------------------------
    # Prompt de RAG Fusion (adaptado al dominio de talento)
    # ------------------------------------------------------------------
    @staticmethod
    def rag_fusion(query: str, k: int) -> str:
        return f"""Eres un experto en análisis de perfiles profesionales técnicos.

Pregunta original: "{query}"

Genera {k} versiones alternativas de esta pregunta para buscar perfiles en CVs de la compañía que:
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

        return f"""Eres un asistente de análisis de perfiles profesionales. Tu tarea es analizar fragmentos de CVs
de miembros de la compañía y determinar si son relevantes para la consulta del usuario.

Fiabilidad de estos fragmentos: {reliability_label}

CONSULTA DEL USUARIO:
{query}

FRAGMENTOS DE CVs:
{context_text}

INSTRUCCIONES:
- Analiza CADA fragmento y decide si la persona es relevante para la consulta.
- Para las personas relevantes, extrae su NOMBRE COMPLETO (nombre y apellidos) del contenido del CV y una breve justificación.
- NUNCA devuelvas nombres de ficheros (ej. "cv_134.json"). Siempre busca el campo nombre_apellidos dentro del contenido.
- Si ninguna es relevante, indica "Ningún perfil relevante en este grupo."

FORMATO DE RESPUESTA:
data: <lista de nombres completos relevantes separados por " | ", o "ninguno">
reasoning: <explicación breve de por qué cada nombre fue incluido o excluido>

Responde SOLO en el formato indicado."""

    # ------------------------------------------------------------------
    # Prompt de "Response Format" – ensamblaje final con LLM potente
    # ------------------------------------------------------------------
    @staticmethod
    def response_format(query: str, groups: dict, max_chars: int, language: str = "es") -> str:
        """
        Recibe los resultados de los 5 grupos de fiabilidad y pide
        al LLM potente que genere la respuesta final para el usuario.
        """
        groups_text = ""
        for gname in ("grupo1", "grupo2", "grupo3", "grupo4", "grupo5"):
            g = groups.get(gname)
            if not g:
                continue
            data = g.get("data", "ninguno")
            if isinstance(data, list):
                data = ", ".join(data) if data else "ninguno"
            reasoning = g.get("reasoning", "")
            reliability = g.get("reliability", gname)
            groups_text += (
                f"\n[{gname.upper()} — fiabilidad {reliability}]\n"
                f"  Perfiles: {data}\n"
                f"  Razonamiento: {reasoning}\n"
            )

        return f"""Los perfiles que recibes pertenecen a miembros de la compañía (empleados, consultores, profesionales del equipo). NO son candidatos externos.

Se ha realizado una búsqueda exhaustiva en el corpus de CVs para la siguiente consulta:

**PREGUNTA DEL USUARIO:**
{query}

**RESULTADOS POR GRUPO DE FIABILIDAD:**
{groups_text}

**INSTRUCCIONES:**

1. SIEMPRE muestra nombre y apellidos completos de cada persona. NUNCA muestres nombres de ficheros (ej. "cv_134.json", "es/cv 272.json"). Si un resultado contiene un nombre de fichero en lugar de un nombre propio, ignóralo.
2. Las personas del grupo 1 (fiabilidad más alta) son las más fiables; preséntalas primero.
3. Las personas de grupos inferiores tienen menor certeza; preséntalas con matiz ("posiblemente", "podría ser relevante").
4. Si un grupo devolvió "ninguno", no lo menciones salvo que todos devuelvan "ninguno".
5. Si no hay perfiles en ningún grupo, indícalo claramente y sugiere reformular la consulta.

**FORMATO OBLIGATORIO (Markdown) — CADA persona en su PROPIA LÍNEA, nunca varias personas en un mismo párrafo:**

**Encontré [X] perfiles para [criterio]:**

**Alta fiabilidad:**
1. **Nombre Completo** — razón breve
2. **Nombre Completo** — razón breve

**Fiabilidad media:**
3. **Nombre Completo** — razón breve (fiabilidad: XX%)
4. **Nombre Completo** — razón breve (fiabilidad: XX%)

**Fiabilidad baja:**
N. **Nombre Completo** — razón breve (fiabilidad: XX%)

**Resumen:** [X] perfiles encontrados ([N] alta, [M] media, [K] baja fiabilidad).

REGLAS DE FORMATO ESTRICTAS:
- CADA perfil debe ocupar EXACTAMENTE una línea: "N. **Nombre** — razón"
- NUNCA agrupes varios nombres en una misma línea o párrafo.
- Usa numeración continua (1, 2, 3...) sin reiniciar entre secciones.
- Mantén las razones breves (máximo 10-15 palabras por perfil).
- NO uses texto en prosa entre los perfiles.

Responde en {LANG_NAMES.get(language, 'español')}."""
