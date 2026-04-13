"""
Genera los prompts completos del caso de uso CVs y los guarda en data/prompts/cvs_prompts.txt

Uso:
    python -m src.scripts.generate_cvs_prompts
"""

import os

from src.config import config

OUTPUT_DIR = os.path.join("data", "prompts")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "cvs_prompts.txt")

# ── Valores leídos de config.py ────────────────────────────────────────
MAX_ANSWER_CHARS = config.max_answer_chars
RAG_FUSION_K = config.rag_fusion_queries
CVS_CHUNK_SIZE = config.cvs_chunk_size
CVS_RELIABILITY_T1 = config.cvs_reliability_t1
CVS_RELIABILITY_T2 = config.cvs_reliability_t2
CVS_RELIABILITY_T3 = config.cvs_reliability_t3
CVS_RELIABILITY_T4 = config.cvs_reliability_t4

# ── Datos de ejemplo para rellenar las plantillas ─────────────────────
EXAMPLE_QUERY = "¿Quién tiene experiencia en Spark y certificaciones de Azure?"
EXAMPLE_CHUNKS = [
    {
        "title": "Experiencia Profesional",
        "content": (
            "NOMBRE_APELLIDOS: María García López\n"
            "Experiencia con Apache Spark, PySpark y Databricks durante 3 años. "
            "Certificaciones: AZ-900, DP-600. Proyectos en el sector bancario con pipelines ETL."
        ),
        "doc_title": "cv_maria_garcia.pdf",
        "pages": "1-2",
    },
    {
        "title": "Skills Técnicas",
        "content": (
            "NOMBRE_APELLIDOS: Carlos Fernández Ruiz\n"
            "Spark SQL, Scala, Azure Data Factory. Certificación AI-900. "
            "2 años como Data Engineer en proyecto de telecomunicaciones."
        ),
        "doc_title": "cv_carlos_fernandez.pdf",
        "pages": "1",
    },
    {
        "title": "Formación y Certificaciones",
        "content": (
            "NOMBRE_APELLIDOS: Ana Martínez Soto\n"
            "Máster en Big Data. PySpark, Hadoop. Sin certificaciones Azure listadas. "
            "1 año en consultoría de datos para retail."
        ),
        "doc_title": "cv_ana_martinez.pdf",
        "pages": "2-3",
    },
]

EXAMPLE_MINI_LLM_CHUNKS = EXAMPLE_CHUNKS[:2]

EXAMPLE_GROUPS = {
    "grupo1": {
        "reliability": f"≥{CVS_RELIABILITY_T1:.0%}",
        "data": ["María García López"],
        "reasoning": "Perfil con Spark y certificaciones AZ-900, DP-600 explícitas en el CV.",
    },
    "grupo2": {
        "reliability": f"{CVS_RELIABILITY_T2:.0%}–{CVS_RELIABILITY_T1:.0%}",
        "data": ["Carlos Fernández Ruiz"],
        "reasoning": "Spark SQL y certificación AI-900, aunque no es exactamente Azure cert clásica.",
    },
    "grupo3": {
        "reliability": f"{CVS_RELIABILITY_T3:.0%}–{CVS_RELIABILITY_T2:.0%}",
        "data": "ninguno",
        "reasoning": "Sin perfiles relevantes en este rango de fiabilidad.",
    },
    "grupo4": {
        "reliability": f"{CVS_RELIABILITY_T4:.0%}–{CVS_RELIABILITY_T3:.0%}",
        "data": "ninguno",
        "reasoning": "Sin perfiles relevantes en este rango de fiabilidad.",
    },
    "grupo5": {
        "reliability": f"<{CVS_RELIABILITY_T4:.0%}",
        "data": ["Ana Martínez Soto"],
        "reasoning": "Tiene PySpark pero no certificaciones Azure; fiabilidad baja.",
    },
}


def _separator(label: str) -> str:
    line = "=" * 80
    return f"\n\n{line}\n  {label}\n{line}\n\n"


def _build_system_message() -> str:
    return (
        "Eres un asistente especializado en análisis de CVs técnicos "
        "de los miembros de la compañía."
    )


def _build_generation_prompt(query: str, chunks: list, max_chars: int) -> str:
    """Replica CVsPrompts.generation()"""
    context_text = ""
    unique_docs: set = set()

    for i, chunk in enumerate(chunks, 1):
        title = chunk.get("title", "Sin título")
        content = chunk.get("content", "")
        doc_title = chunk.get("doc_title", "Unknown")
        pages = chunk.get("pages", "N/A")

        content_preview = content[:800] + ("..." if len(content) > 800 else "")
        context_text += (
            f"\n[CV {i}]: {doc_title}\n"
            f"Sección: {title}\nPáginas: {pages}\nContenido:\n{content_preview}\n---\n"
        )
        unique_docs.add(doc_title)

    num_docs = len(unique_docs)

    return f"""Eres un asistente especializado en análisis de CVs técnicos de una empresa.

Los CVs que recibes pertenecen a miembros de la compañía (empleados, consultores, profesionales del equipo). NO son candidatos externos a un puesto; son perfiles internos de la organización.

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

RESPONDE EN ESPAÑOL. Máximo {max_chars} caracteres."""


def _build_rag_fusion_prompt(query: str, k: int) -> str:
    """Replica CVsPrompts.rag_fusion()"""
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


def _build_mini_llm_batch_prompt(query: str, chunks: list, reliability_label: str) -> str:
    """Replica CVsPrompts.mini_llm_batch()"""
    context_text = ""
    for i, chunk in enumerate(chunks, 1):
        doc_title = chunk.get("doc_title", "Unknown")
        content = chunk.get("content", "")
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


def _build_response_format_prompt(query: str, groups: dict, max_chars: int) -> str:
    """Replica CVsPrompts.response_format()"""
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

    return f"""Eres un asistente especializado en análisis de CVs técnicos de una empresa.

Los perfiles que recibes pertenecen a miembros de la compañía (empleados, consultores, profesionales del equipo). NO son candidatos externos.

Se ha realizado una búsqueda exhaustiva en el corpus de CVs para la siguiente consulta:

**PREGUNTA DEL USUARIO:**
{query}

**RESULTADOS POR GRUPO DE FIABILIDAD:**
{groups_text}

**INSTRUCCIONES:**

1. Genera una respuesta final clara y estructurada para el usuario.
2. SIEMPRE muestra nombre y apellidos completos de cada persona. NUNCA muestres nombres de ficheros (ej. "cv_134.json", "es/cv 272.json"). Si un resultado contiene un nombre de fichero en lugar de un nombre propio, ignóralo.
2. Las personas del grupo 1 (fiabilidad más alta) son las más fiables; preséntalas primero y con más confianza.
3. Las personas de grupos inferiores tienen menor certeza; preséntalas con matiz ("posiblemente", "podría ser relevante").
4. Si un grupo devolvió "ninguno", no lo menciones salvo que todos devuelvan "ninguno".
5. Agrupa los perfiles en una lista numerada con su nombre en negrita.
6. Al final incluye un breve resumen: cuántas personas se encontraron y la distribución de fiabilidad.
7. Si no hay perfiles en ningún grupo, indícalo claramente y sugiere reformular la consulta.

**FORMATO (Markdown):**
**Encontré [X] perfiles para [criterio]:**

**Alta fiabilidad:**
1. **Nombre** — razón
...

**Fiabilidad media/baja:**
N. **Nombre** — razón (fiabilidad: XX%)
...

**Resumen:** [X] perfiles encontrados ([N] alta fiabilidad, [M] fiabilidad media/baja).

Responde en español. Máximo {max_chars} caracteres."""


def _build_query_expansion_prompt(query: str, history_text: str, unique_names: list) -> str:
    """Replica Retriever._expand_query_with_context()"""
    return f"""Analiza si esta query necesita información del contexto conversacional.

CONVERSACIÓN RECIENTE:
{history_text}

NOMBRES IDENTIFICADOS: {', '.join(unique_names[:10]) if unique_names else 'ninguno'}

QUERY ACTUAL:
{query}

TAREA: Si la query usa términos genéricos y en el historial se mencionaron personas/candidatos
específicos, expande la query incluyendo sus nombres. Si ya es específica, devuélvela sin cambios.
Máximo 15 palabras. Solo nombres, tecnologías y términos clave.

Responde SOLO con la query (expandida o sin cambios):"""


def _build_guardrails_input_prompt() -> str:
    return """[Guardrails de Entrada — Patrones de inyección detectados]

Patrones regex que se comprueban contra cada query de entrada:
- ignore\\s+(previous|above|all)\\s+instructions
- disregard\\s+.*\\s+instructions
- you\\s+are\\s+now\\s+a\\s+different
- pretend\\s+to\\s+be
- act\\s+as\\s+if\\s+you\\s+are
- from\\s+now\\s+on
- <script[^>]*>.*?</script>
- eval\\s*\\(
- exec\\s*\\(

Palabras sospechosas: jailbreak, bypass, override, sudo, admin, password, token, secret, credential

Validaciones:
- Query no vacía y >= 2 caracteres
- Longitud <= 5000 caracteres
- Detección de prompt injection (regex)
- Moderación de contenido (opcional, vía Azure OpenAI Moderations API)
- Sanitización: elimina HTML tags, caracteres de control, normaliza espacios"""


def _build_guardrails_output_prompt() -> str:
    return """[Guardrails de Salida]

Validaciones aplicadas a la respuesta generada:
- Longitud mínima: 10 caracteres
- Longitud máxima: max_answer_chars * 1.2 (se trunca si excede)
- Verificación de HTML válido (tags abiertos/cerrados)
- Detección de alucinaciones (mini-LLM compara respuesta vs fuentes)

Prompt de detección de alucinaciones:
\"\"\"
Verifica si la siguiente RESPUESTA está basada solo en las FUENTES.

FUENTES:
[Fuente 1]: <contenido chunk 1, max 500 chars>
[Fuente 2]: <contenido chunk 2, max 500 chars>
...

RESPUESTA:
<respuesta generada, max 800 chars>

¿La respuesta inventa información que NO está en las fuentes? Responde solo SÍ o NO.
\"\"\"

Disclaimers automáticos para temas sensibles:
- Médico/salud → "⚠️ Esta información es orientativa. Consulta con un profesional de la salud."
- Legal → "⚠️ Esta información es general. Para asesoría legal, consulta con un abogado."
- Financiero → "⚠️ Esta información no constituye asesoría financiera."
"""


def _build_add_context_prompt(content_example: str) -> str:
    """Replica add_context._build_qa_prompt() para el dominio CVs"""
    return f"""Eres un experto en generación de preguntas para sistemas de recuperación de información (RAG).

Se te proporciona un fragmento de texto extraído de un currículum profesional (CV) técnico.

FRAGMENTO:
\"\"\"
{content_example[:1200]}
\"\"\"

Tu tarea:
1. Formula UNA sola pregunta concreta y específica cuya respuesta esté completamente contenida en el fragmento anterior.
2. Escribe la respuesta correcta y completa a esa pregunta, basándote ÚNICAMENTE en el fragmento.

Responde con el siguiente formato exacto (sin texto adicional):
PREGUNTA: <pregunta>
RESPUESTA: <respuesta>"""


def generate():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    sections = []

    # ── Header ─────────────────────────────────────────────────────
    sections.append(
        "PROMPTS COMPLETOS — CASO DE USO: CVs / TALENTO\n"
        "Generado automáticamente por src/scripts/generate_cvs_prompts.py\n"
        f"Configuración: max_chars={MAX_ANSWER_CHARS}, rag_fusion_k={RAG_FUSION_K}, "
        f"chunk_size={CVS_CHUNK_SIZE}\n"
        f"Umbrales fiabilidad: T1={CVS_RELIABILITY_T1}, T2={CVS_RELIABILITY_T2}, "
        f"T3={CVS_RELIABILITY_T3}, T4={CVS_RELIABILITY_T4}"
    )

    # ── 1. System Message ──────────────────────────────────────────
    sections.append(_separator("1. SYSTEM MESSAGE"))
    sections.append(_build_system_message())

    # ── 2. Generation Prompt ───────────────────────────────────────
    sections.append(_separator("2. PROMPT DE GENERACIÓN PRINCIPAL (CVsPrompts.generation)"))
    sections.append(
        "Se envía como mensaje 'user' al LLM junto con el system message.\n"
        "Los chunks son inyectados dentro del prompt.\n\n"
        f"Query de ejemplo: \"{EXAMPLE_QUERY}\"\n"
    )
    sections.append(_build_generation_prompt(EXAMPLE_QUERY, EXAMPLE_CHUNKS, MAX_ANSWER_CHARS))

    # ── 3. RAG Fusion Prompt ───────────────────────────────────────
    sections.append(_separator("3. PROMPT DE RAG FUSION (CVsPrompts.rag_fusion)"))
    sections.append(
        "NOTA: En CVs, RAG Fusion está DESHABILITADO por defecto (use_rag_fusion=False).\n"
        "Se incluye aquí como referencia del prompt disponible.\n\n"
    )
    sections.append(_build_rag_fusion_prompt(EXAMPLE_QUERY, RAG_FUSION_K))

    # ── 4. Mini-LLM Batch Prompt ──────────────────────────────────
    sections.append(_separator("4. PROMPT MINI-LLM BATCH (CVsPrompts.mini_llm_batch)"))
    sections.append(
        "Se envía a un modelo ligero (gpt4o-mini) para cada lote de chunks.\n"
        f"Tamaño de lote: {CVS_CHUNK_SIZE} chunks.\n"
        "Se ejecuta para los grupos 2-5 (y opcionalmente grupo 1 si CVS_GROUP1_USE_LLM=true).\n\n"
    )
    label = f"{CVS_RELIABILITY_T2:.0%}–{CVS_RELIABILITY_T1:.0%}"
    sections.append(_build_mini_llm_batch_prompt(EXAMPLE_QUERY, EXAMPLE_MINI_LLM_CHUNKS, label))

    # ── 5. Response Format Prompt ──────────────────────────────────
    sections.append(_separator("5. PROMPT RESPONSE FORMAT (CVsPrompts.response_format)"))
    sections.append(
        "Se envía al LLM potente (gpt4.1) con los resultados de los 5 grupos.\n"
        "Es el paso final que ensambla la respuesta para el usuario.\n\n"
    )
    sections.append(_build_response_format_prompt(EXAMPLE_QUERY, EXAMPLE_GROUPS, MAX_ANSWER_CHARS))

    # ── 6. Query Expansion Prompt ──────────────────────────────────
    sections.append(_separator("6. PROMPT DE EXPANSIÓN DE QUERY (Retriever._expand_query_with_context)"))
    sections.append(
        "Se usa cuando hay historial conversacional para expandir queries genéricas.\n\n"
    )
    example_history = (
        "USER: ¿Quién tiene experiencia en Spark?\n"
        "ASSISTANT: Encontré 3 perfiles con experiencia en Spark: María García López, Carlos Fernández Ruiz..."
    )
    sections.append(
        _build_query_expansion_prompt("¿alguien más?", example_history, ["María García López", "Carlos Fernández Ruiz"])
    )

    # ── 7. Guardrails Input ────────────────────────────────────────
    sections.append(_separator("7. GUARDRAILS DE ENTRADA"))
    sections.append(_build_guardrails_input_prompt())

    # ── 8. Guardrails Output ───────────────────────────────────────
    sections.append(_separator("8. GUARDRAILS DE SALIDA"))
    sections.append(_build_guardrails_output_prompt())

    # ── 9. Add Context (QA enrichment) ─────────────────────────────
    sections.append(_separator("9. PROMPT DE ENRIQUECIMIENTO QA (add_context)"))
    sections.append(
        "Se usa durante la ingesta para generar pares pregunta-respuesta por chunk.\n"
        "Modelo: gpt4o-mini. Se almacena en el campo QuestionsText de Cosmos DB.\n\n"
    )
    example_content = (
        "NOMBRE_APELLIDOS: María García López\n"
        "Experiencia con Apache Spark, PySpark y Databricks durante 3 años. "
        "Certificaciones: AZ-900, DP-600. Proyectos en el sector bancario con pipelines ETL."
    )
    sections.append(_build_add_context_prompt(example_content))

    # ── 10. Flujo completo ─────────────────────────────────────────
    sections.append(_separator("10. FLUJO COMPLETO DEL PIPELINE CVs"))
    sections.append("""El pipeline CVs sigue estos pasos:

1. VALIDATE_USER_INPUT
   - Verifica que la query no esté vacía y tenga >= 2 caracteres.

2. GUARDRAILS_INPUT (si habilitado)
   - Detección de prompt injection, keywords sospechosos, moderación.
   - Sanitización de la query.

3. CLASSIFY_CONTEXT
   - Decide si se necesita retrieval (siempre sí en modo GPT).

4. RETRIEVE
   a. Query Expansion: si hay historial, expande la query con contexto.
   b. Búsqueda directa (SIN RAG Fusion): top_k=50 chunks.
   c. Búsqueda híbrida: texto + vector en Azure Search.

5. PROCESS_CVS (pipeline exclusivo de CVs)
   a. Normalizar scores min-max al rango [0, 1].
   b. Clasificar chunks en 5 grupos de fiabilidad:
      - Grupo 1 (≥90%): extracción directa de nombres del campo NOMBRE_APELLIDOS.
      - Grupos 2-5: mini-LLM en lotes paralelos de 5 chunks.
   c. Persistir resultados en cvs_history.json.
   d. Response Format: LLM potente ensambla respuesta final con los 5 grupos.

6. GUARDRAILS_OUTPUT (si habilitado)
   - Verificación de longitud, alucinaciones, HTML, disclaimers.

7. DEVOLVER RESPUESTA al usuario.""")

    # ── Escribir fichero ───────────────────────────────────────────
    output = "\n".join(sections)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"✅ Prompts CVs generados en {OUTPUT_FILE} ({len(output)} caracteres)")


if __name__ == "__main__":
    generate()
