"""Genera los prompts completos del caso de uso EU y los guarda en data/prompts/eu_prompts.txt
Uso:
    python -m src.scripts.generate_eu_prompts
"""
import os
from src.config import config
from src.scripts.prompt_export_utils import PromptExportBuilder, write_prompt_export
OUTPUT_DIR = os.path.join("data", "prompts")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "eu_prompts.txt")
# ── Valores leídos de config.py ────────────────────────────────────────
MAX_ANSWER_CHARS = config.max_answer_chars
RAG_FUSION_K = config.rag_fusion_queries
AZURE_SEARCH_TOP_K = config.azure_search_top_k
# ── Datos de ejemplo ──────────────────────────────────────────────────
EXAMPLE_QUERY = "¿Qué establece el artículo 6 del RGPD sobre la licitud del tratamiento de datos?"
EXAMPLE_CHUNKS = [
    {
        "title": "Artículo 6 – Licitud del tratamiento",
        "content": (
            "1. El tratamiento solo será lícito si se cumple al menos una de las siguientes condiciones: "
            "a) el interesado dio su consentimiento para el tratamiento de sus datos personales para uno "
            "o varios fines específicos; b) el tratamiento es necesario para la ejecución de un contrato "
            "en el que el interesado es parte; c) el tratamiento es necesario para el cumplimiento de una "
            "obligación legal aplicable al responsable del tratamiento; d) el tratamiento es necesario para "
            "proteger intereses vitales del interesado o de otra persona física; e) el tratamiento es necesario "
            "para el cumplimiento de una misión realizada en interés público; f) el tratamiento es necesario "
            "para la satisfacción de intereses legítimos perseguidos por el responsable del tratamiento."
        ),
        "doc_title": "Reglamento (UE) 2016/679 – RGPD",
        "pages": "35-36",
    },
    {
        "title": "Considerando 40 – Bases legales",
        "content": (
            "Para que el tratamiento sea lícito, los datos personales deben ser tratados con el consentimiento "
            "del interesado o sobre alguna otra base legítima establecida por ley, incluida la necesidad de "
            "cumplir la obligación legal aplicable al responsable del tratamiento o la necesidad de ejecutar "
            "un contrato en el que sea parte el interesado."
        ),
        "doc_title": "Reglamento (UE) 2016/679 – RGPD",
        "pages": "8",
    },
    {
        "title": "Artículo 7 – Condiciones para el consentimiento",
        "content": (
            "1. Cuando el tratamiento se base en el consentimiento del interesado, el responsable deberá ser "
            "capaz de demostrar que aquel consintió el tratamiento de sus datos personales. "
            "2. Si el consentimiento del interesado se da en el contexto de una declaración escrita que también "
            "se refiera a otros asuntos, la solicitud de consentimiento se presentará de tal forma que se "
            "distinga claramente de los demás asuntos."
        ),
        "doc_title": "Reglamento (UE) 2016/679 – RGPD",
        "pages": "36-37",
    },
]
def _build_system_message() -> str:
    return (
        "Eres un experto en legislación y documentos institucionales "
        "de la Unión Europea. Respondes con precisión legal."
    )
def _build_generation_prompt(query: str, chunks: list, max_chars: int) -> str:
    """Replica EUPrompts.generation()"""
    context_text = ""
    unique_docs: set = set()
    for i, chunk in enumerate(chunks, 1):
        title = chunk.get("title", "Sin título")
        content = chunk.get("content", "")
        doc_title = chunk.get("doc_title", "Unknown")
        pages = chunk.get("pages", "N/A")
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
[4] IDIOMA: Responde en el idioma de la pregunta (español por defecto).
Máximo {max_chars} caracteres."""
def _build_rag_fusion_prompt(query: str, k: int) -> str:
    """Replica EUPrompts.rag_fusion()"""
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
    """Replica add_context._build_qa_prompt() para el dominio EU"""
    return f"""Eres un experto en generación de preguntas para sistemas de recuperación de información (RAG).
Se te proporciona un fragmento de texto extraído de un documento legal o normativo de la Unión Europea.
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
        "PROMPTS COMPLETOS — CASO DE USO: EU / LEGISLACIÓN UNIÓN EUROPEA\n"
        "Generado automáticamente por src/scripts/generate_eu_prompts.py\n"
        f"Configuración: max_chars={MAX_ANSWER_CHARS}, rag_fusion_k={RAG_FUSION_K}, "
        f"top_k={AZURE_SEARCH_TOP_K}"
    )
    # ── 1. System Message ──────────────────────────────────────────
    builder.add_section("1. SYSTEM MESSAGE", _build_system_message())
    # ── 2. Generation Prompt ───────────────────────────────────────
    builder.add_section(
        "2. PROMPT DE GENERACIÓN PRINCIPAL (EUPrompts.generation)",
        "Se envía como mensaje 'user' al LLM junto con el system message.\n"
        "Los chunks son inyectados dentro del prompt.\n\n"
        f"Query de ejemplo: \"{EXAMPLE_QUERY}\"\n",
        _build_generation_prompt(EXAMPLE_QUERY, EXAMPLE_CHUNKS, MAX_ANSWER_CHARS),
    )
    # ── 3. RAG Fusion Prompt ───────────────────────────────────────
    builder.add_section(
        "3. PROMPT DE RAG FUSION (EUPrompts.rag_fusion)",
        "EU usa RAG Fusion HABILITADO (use_rag_fusion=True).\n"
        f"Se generan {RAG_FUSION_K} queries sintéticas alternativas para ampliar la búsqueda.\n\n",
        _build_rag_fusion_prompt(EXAMPLE_QUERY, RAG_FUSION_K),
    )
    # ── 4. Query Expansion Prompt ──────────────────────────────────
    builder.add_section(
        "4. PROMPT DE EXPANSIÓN DE QUERY (Retriever._expand_query_with_context)",
        "Se usa cuando hay historial conversacional para expandir queries genéricas.\n\n",
    )
    example_history = (
        "USER: ¿Qué dice el RGPD sobre el consentimiento?\n"
        "ASSISTANT: El artículo 7 del RGPD establece las condiciones para el consentimiento..."
    )
    builder.add(
        _build_query_expansion_prompt("¿Y sobre la licitud del tratamiento?", example_history, [])
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
        "1. El tratamiento solo será lícito si se cumple al menos una de las siguientes condiciones: "
        "a) el interesado dio su consentimiento para el tratamiento de sus datos personales para uno "
        "o varios fines específicos; b) el tratamiento es necesario para la ejecución de un contrato."
    )
    builder.add(_build_add_context_prompt(example_content))
    # ── 8. Flujo completo ──────────────────────────────────────────
    builder.add_section("8. FLUJO COMPLETO DEL PIPELINE EU", f"""El pipeline EU sigue estos pasos:
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
   a. Handler EU construye el prompt de generación con los chunks.
   b. Se envía al LLM: [system_message] + [last Q&A opcional] + [user: rag_prompt].
   c. Post-procesado de la respuesta (por defecto sin cambios).
6. GUARDRAILS_OUTPUT (si habilitado)
   - Verificación de longitud, alucinaciones, HTML, disclaimers.
7. DEVOLVER RESPUESTA al usuario.""")
    # ── Escribir fichero ───────────────────────────────────────────
    output = builder.render()
    write_prompt_export(OUTPUT_FILE, output, "EU")
if __name__ == "__main__":
    generate()
