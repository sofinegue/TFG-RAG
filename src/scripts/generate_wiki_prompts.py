"""Genera los prompts completos del caso de uso Wikipedia y los guarda en data/prompts/wiki_prompts.txt
Uso:
    python -m src.scripts.generate_wiki_prompts
"""
import os
from src.config import config
from src.scripts.prompt_export_utils import PromptExportBuilder, write_prompt_export
OUTPUT_DIR = os.path.join("data", "prompts")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "wiki_prompts.txt")
# ── Valores leídos de config.py ────────────────────────────────────────
MAX_ANSWER_CHARS = config.max_answer_chars
RAG_FUSION_K = config.rag_fusion_queries
AZURE_SEARCH_TOP_K = config.azure_search_top_k
# ── Datos de ejemplo ──────────────────────────────────────────────────
EXAMPLE_QUERY = "¿Cuándo se fundó la ciudad de Madrid y cuál es su origen histórico?"
EXAMPLE_CHUNKS = [
    {
        "title": "Historia – Orígenes",
        "content": (
            "Madrid fue fundada como una fortaleza militar por el emir Muhammad I de Córdoba "
            "en torno al año 860 d.C., con el nombre de Mayrit. La fortaleza se construyó en "
            "un promontorio junto al río Manzanares con fines defensivos. La primera mención "
            "documental de la ciudad data del siglo X. Tras la conquista cristiana de Toledo en "
            "1085 por Alfonso VI, Madrid pasó a manos castellanas sin resistencia significativa."
        ),
        "doc_title": "Madrid",
    },
    {
        "title": "Historia – Capitalidad",
        "content": (
            "En 1561, el rey Felipe II trasladó la corte a Madrid, convirtiéndola en la capital "
            "de facto del Imperio español. La elección se debió a su posición central en la "
            "Península Ibérica y la ausencia de un obispado poderoso que pudiera competir con "
            "el poder real. Desde entonces, salvo breves periodos, Madrid ha sido la capital de España."
        ),
        "doc_title": "Madrid",
    },
    {
        "title": "Etimología",
        "content": (
            "El nombre original de Madrid fue Mayrit (مجريط), de origen árabe. La etimología más "
            "aceptada lo deriva de 'mağrā' (cauce) + el sufijo romance '-it', haciendo referencia "
            "a la abundancia de arroyos subterráneos y cauces de agua en la zona. Otra teoría lo "
            "relaciona con 'matrĭcem' (matriz), en alusión al arroyo madre."
        ),
        "doc_title": "Madrid",
    },
]
def _build_system_message() -> str:
    return (
        "Eres un asistente enciclopédico que responde preguntas de "
        "conocimiento general a partir de artículos de Wikipedia."
    )
def _build_generation_prompt(query: str, chunks: list, max_chars: int) -> str:
    """Replica WikiPrompts.generation()"""
    context_text = ""
    unique_docs: set = set()
    for i, chunk in enumerate(chunks, 1):
        title = chunk.get("title", "Sin título")
        content = chunk.get("content", "")
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
[4] IDIOMA: Responde en el idioma de la pregunta (español por defecto).
Máximo {max_chars} caracteres."""
def _build_rag_fusion_prompt(query: str, k: int) -> str:
    """Replica WikiPrompts.rag_fusion()"""
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
    """Replica add_context._build_qa_prompt() para el dominio Wiki"""
    return f"""Eres un experto en generación de preguntas para sistemas de recuperación de información (RAG).
Se te proporciona un fragmento de texto extraído de un artículo enciclopédico de Wikipedia.
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
    builder = PromptExportBuilder()
    # ── Header ─────────────────────────────────────────────────────
    builder.add(
        "PROMPTS COMPLETOS — CASO DE USO: WIKIPEDIA / ENCICLOPÉDICO\n"
        "Generado automáticamente por src/scripts/generate_wiki_prompts.py\n"
        f"Configuración: max_chars={MAX_ANSWER_CHARS}, rag_fusion_k={RAG_FUSION_K}, "
        f"top_k={AZURE_SEARCH_TOP_K}"
    )
    # ── 1. System Message ──────────────────────────────────────────
    builder.add_section("1. SYSTEM MESSAGE", _build_system_message())
    # ── 2. Generation Prompt ───────────────────────────────────────
    builder.add_section(
        "2. PROMPT DE GENERACIÓN PRINCIPAL (WikiPrompts.generation)",
        "Se envía como mensaje 'user' al LLM junto con el system message.\n"
        "Los chunks son inyectados dentro del prompt.\n\n"
        f"Query de ejemplo: \"{EXAMPLE_QUERY}\"\n",
        _build_generation_prompt(EXAMPLE_QUERY, EXAMPLE_CHUNKS, MAX_ANSWER_CHARS),
    )
    # ── 3. RAG Fusion Prompt ───────────────────────────────────────
    builder.add_section(
        "3. PROMPT DE RAG FUSION (WikiPrompts.rag_fusion)",
        "Wikipedia usa RAG Fusion HABILITADO (use_rag_fusion=True).\n"
        f"Se generan {RAG_FUSION_K} queries sintéticas alternativas para ampliar la búsqueda.\n\n",
        _build_rag_fusion_prompt(EXAMPLE_QUERY, RAG_FUSION_K),
    )
    # ── 4. Query Expansion Prompt ──────────────────────────────────
    builder.add_section(
        "4. PROMPT DE EXPANSIÓN DE QUERY (Retriever._expand_query_with_context)",
        "Se usa cuando hay historial conversacional para expandir queries genéricas.\n\n",
    )
    example_history = (
        "USER: ¿Cuándo se fundó Madrid?\n"
        "ASSISTANT: Madrid fue fundada en torno al año 860 d.C. por el emir Muhammad I de Córdoba..."
    )
    builder.add(
        _build_query_expansion_prompt("¿Y quién la convirtió en capital?", example_history, [])
    )
    # ── 5. Guardrails Input ────────────────────────────────────────
    builder.add_section("5. GUARDRAILS DE ENTRADA", _build_guardrails_input_prompt())
    # ── 6. Guardrails Output ───────────────────────────────────────
    builder.add_section("6. GUARDRAILS DE SALIDA", _build_guardrails_output_prompt())
    # ── 7. Add Context (QA enrichment) ─────────────────────────────
    builder.add_section(
        "7. PROMPT DE ENRIQUECIMIENTO QA (add_context)",
        "Se usa durante la ingesta para generar pares pregunta-respuesta por chunk.\n"
        "Modelo: gpt4o-mini. Se almacena en el campo QuestionsText de Cosmos DB.\n\n",
    )
    example_content = (
        "Madrid fue fundada como una fortaleza militar por el emir Muhammad I de Córdoba "
        "en torno al año 860 d.C., con el nombre de Mayrit. La fortaleza se construyó en "
        "un promontorio junto al río Manzanares con fines defensivos."
    )
    builder.add(_build_add_context_prompt(example_content))
    # ── 8. Flujo completo ──────────────────────────────────────────
    builder.add_section("8. FLUJO COMPLETO DEL PIPELINE WIKIPEDIA", f"""El pipeline Wikipedia sigue estos pasos:
1. VALIDATE_USER_INPUT
   - Verifica que la query no esté vacía y tenga >= 2 caracteres.
2. GUARDRAILS_INPUT (si habilitado)
   - Detección de prompt injection, keywords sospechosos, moderación.
   - Sanitización de la query.
3. CLASSIFY_CONTEXT
   - Decide si se necesita retrieval (siempre sí en modo GPT).
4. RETRIEVE
   a. Query Expansion: si hay historial, expande la query con contexto.
   b. RAG Fusion: genera {RAG_FUSION_K} queries sintéticas alternativas.
   c. Búsqueda híbrida (texto + vector) en Azure Search por cada query.
   d. RRF (Reciprocal Rank Fusion): fusiona y rankea resultados.
   e. Filtrado por min_relevance_score y max_chunks_used.
   → Resultado: {AZURE_SEARCH_TOP_K} chunks máximo.
5. GENERATE
   a. Handler Wiki construye el prompt de generación con los chunks.
   b. Se envía al LLM: [system_message] + [last Q&A opcional] + [user: rag_prompt].
   c. Post-procesado de la respuesta (por defecto sin cambios).
6. GUARDRAILS_OUTPUT (si habilitado)
   - Verificación de longitud, alucinaciones, HTML, disclaimers.
7. DEVOLVER RESPUESTA al usuario.""")
    # ── Escribir fichero ───────────────────────────────────────────
    output = builder.render()
    write_prompt_export(OUTPUT_FILE, output, "Wiki")
if __name__ == "__main__":
    generate()
