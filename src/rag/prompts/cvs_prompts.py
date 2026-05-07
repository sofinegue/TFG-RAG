"""
Prompts específicos para el caso de uso CVs.

Centralizados aquí para que el handler cvs/handler.py los importe y
los tests de prompts puedan validarlos de forma aislada.
"""
from typing import Dict, List

from src.config import config


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

RESPONDE EN {config.get_lang_name(language).upper()}. Máximo {max_chars} caracteres."""

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
            content   = chunk.get("content", "")[:1200]
            context_text += f"\n[CV {i}] {doc_title}:\n{content}\n---"

        # Instrucción de exigencia adaptada al nivel de fiabilidad
        # Los labels tienen formato "≥90%", "70%–90%", "50%–70%", "30%–50%", "<30%"
        # Clasificamos: grupo1-2 = alto, grupo3 = medio, grupo4-5 = bajo
        import re as _re
        nums = [int(x) for x in _re.findall(r"(\d+)%", reliability_label)]
        # El umbral inferior del rango determina la exigencia
        min_pct = min(nums) if nums else 0

        if min_pct >= 60:
            strictness = (
                "3. CRITERIO INCLUSIVO (fiabilidad alta): Estos fragmentos ya fueron seleccionados "
                "como muy relevantes por el buscador. En caso de duda razonable, INCLUYE al perfil. "
                "Es preferible un falso positivo a perder un perfil relevante."
            )
        elif min_pct >= 40:
            strictness = (
                "3. CRITERIO MODERADO (fiabilidad media): Incluye al perfil SOLO si encuentras "
                "evidencia clara del criterio buscado en el contenido del CV (mención explícita "
                "del término o variación morfológica directa)."
            )
        else:
            strictness = (
                "3. CRITERIO ESTRICTO (fiabilidad baja): Estos fragmentos tienen baja relevancia "
                "según el buscador. Incluye al perfil ÚNICAMENTE si el término buscado aparece "
                "de forma LITERAL en el contenido del CV. No interpretes ni inferir competencias "
                "a partir de contexto indirecto."
            )

        return f"""Eres un asistente de análisis de perfiles profesionales. Tu tarea es analizar fragmentos de CVs
de miembros de la compañía y determinar si son relevantes para la consulta del usuario.

Fiabilidad de estos fragmentos: {reliability_label}

CONSULTA DEL USUARIO:
{query}

FRAGMENTOS DE CVs:
{context_text}

INSTRUCCIONES:
1. Analiza CADA fragmento individualmente y decide si la persona es relevante para la consulta.
2. EXHAUSTIVIDAD: Incluye TODOS los perfiles que cumplan el criterio. No omitas ninguno. Si hay 10 perfiles relevantes, lista los 10.
{strictness}
4. BÚSQUEDA EN TODO EL CV: Cuando la consulta pregunte por una skill, tecnología o competencia, búscala en TODAS las secciones del CV:
   - hard_skills (lista explícita de habilidades técnicas)
   - experiencia (descripciones de proyectos y tareas: si alguien menciona "microservices" en su experiencia, SÍ tiene esa competencia)
   - otros (certificaciones, idiomas, etc.)
   - estudios
   No te limites solo a hard_skills. Si una persona menciona "Microservices" en su experiencia profesional, es tan relevante como si apareciera en hard_skills.
5. OPERADORES LÓGICOS — interprétalos estrictamente:
   - Si la consulta contiene "AND" o "y" entre criterios: la persona debe cumplir TODOS los criterios simultáneamente. Si solo cumple uno, NO la incluyas.
   - Si la consulta contiene "OR" o "o" entre criterios: basta con que la persona cumpla AL MENOS UNO de los criterios.
6. CONSULTAS DE CONTEO ("cuántos", "how many", "al menos N"): No filtres. Extrae el dato numérico relevante de cada CV (ej. número de hard skills) e incluye a TODOS los que cumplan la condición numérica.
7. COINCIDENCIA: Busca el término en el contenido del CV. Acepta variaciones morfológicas (ej. "Microservices" también matchea "microservice architecture"). Pero no asumas que una tecnología similar equivale a la buscada (p. ej. "Kafka" ≠ "RabbitMQ", "French" ≠ "Spanish").
8. Extrae el NOMBRE COMPLETO (nombre y apellidos) del campo nombre_apellidos del contenido del CV.
9. NUNCA devuelvas nombres de ficheros (ej. "cv_134.json"). Siempre busca el campo nombre_apellidos dentro del contenido.
10. Si ninguna persona es relevante, indica "ninguno".

FORMATO DE RESPUESTA:
data: <lista de nombres completos relevantes separados por " | ", o "ninguno">
reasoning: <para cada nombre incluido, indica la evidencia exacta encontrada en el CV (ej. "French C2 en idiomas", "Kafka en hard_skills", "10 hard skills listadas")>

Responde SOLO en el formato indicado."""

    # ------------------------------------------------------------------
    # Prompt de "Response Format" – ensamblaje final con LLM potente
    # ------------------------------------------------------------------
    @staticmethod
    def response_format(query: str, groups: dict, max_chars: int, language: str = "es") -> str:
        """
        Recibe los resultados de los 5 grupos de fiabilidad y pide
        al LLM potente que genere la respuesta final para el usuario.

        Importante: el usuario final NUNCA debe ver el concepto de
        "fiabilidad". El primer grupo se presenta como "principales
        resultados" y el resto en una sola sección de "otros perfiles
        que coinciden", manteniendo el orden interno por fiabilidad.
        Toda la respuesta debe ser una lista numerada continua.
        """
        # Construir secciones internas (solo el LLM las ve, no el usuario).
        groups_text = ""
        for gname in ("grupo1", "grupo2", "grupo3", "grupo4", "grupo5"):
            g = groups.get(gname)
            if not g:
                continue
            data = g.get("data", "ninguno")
            if isinstance(data, list):
                data = ", ".join(data) if data else "ninguno"
            reasoning = g.get("reasoning", "")
            section = "PRINCIPAL" if gname == "grupo1" else "SECUNDARIO"
            groups_text += (
                f"\n[{gname.upper()} — sección interna: {section}]\n"
                f"  Perfiles: {data}\n"
                f"  Razonamiento: {reasoning}\n"
            )

        lang_name = config.get_lang_name(language)
        is_es = language.lower().startswith("es")
        h_main      = "Principales resultados" if is_es else "Main results"
        h_others    = "Otros perfiles que coinciden" if is_es else "Other matching profiles"
        intro_tmpl  = ("Encontré {n} perfiles para «{q}»:" if is_es
                       else 'Found {n} profiles for "{q}":')
        none_msg    = ("No encontré perfiles que coincidan con la consulta. "
                       "Prueba a reformularla o a ampliar los criterios."
                       if is_es else
                       "No matching profiles were found. Try rephrasing the "
                       "query or broadening the criteria.")

        return f"""Se ha realizado una búsqueda exhaustiva en el corpus de CVs (perfiles internos de la compañía) para la siguiente consulta.

**PREGUNTA DEL USUARIO:**
{query}

**RESULTADOS POR GRUPO (uso interno – NO expongas estos nombres ni el concepto de fiabilidad al usuario):**
{groups_text}

**INSTRUCCIONES DE CONTENIDO:**

1. SIEMPRE muestra el nombre y apellidos completos. NUNCA muestres nombres de ficheros (p. ej. "cv_134.json"). Si un resultado contiene un nombre de fichero en lugar de un nombre propio, ignóralo.
2. EXHAUSTIVIDAD: Incluye TODOS los perfiles que aparecen en los resultados de los grupos. Tu trabajo es ensamblar la lista completa, NO resumirla ni acortarla. Si hay 50 nombres, lista los 50.
3. OPERADORES LÓGICOS — aplícalos como filtro final:
   - Si la consulta usa "AND" / "y" entre criterios: incluye SOLO perfiles cuyo razonamiento demuestre que cumplen TODOS los criterios.
   - Si la consulta usa "OR" / "o" entre criterios: incluye perfiles que cumplan AL MENOS UNO de los criterios.
4. Los perfiles del GRUPO1 son los principales resultados; preséntalos primero.
5. Los perfiles de GRUPO2 a GRUPO5 son "otros perfiles que coinciden"; mantén su orden relativo (grupo2 antes que grupo3, etc.) pero NO los separes en sub-secciones ni los etiquetes con grupos.
6. PROHIBIDO mencionar al usuario las palabras "fiabilidad", "reliability", "alta", "media", "baja", porcentajes de confianza, ni los nombres internos de los grupos.
7. Si el GRUPO1 está vacío y hay perfiles en otros grupos, presenta esos otros directamente bajo "{h_main}" (no inventes una distinción entre principales y secundarios cuando no la hay).
8. Si no hay perfiles en ningún grupo, responde EXACTAMENTE con: "{none_msg}"
9. La justificación de cada perfil debe ser una frase BREVE (máx. 12 palabras) y NO debe incluir porcentajes ni términos de fiabilidad.
10. NUNCA repitas el mismo nombre dos veces en toda la respuesta. Si una persona aparece en varios grupos, inclúyela UNA sola vez en la sección de mayor prioridad (GRUPO1 > GRUPO2 > … > GRUPO5).
11. La justificación debe ser CONCRETA y verificable a partir del CV (p. ej. "French C2 listado", "Goethe-Zertifikat B2", "Microservices en hard skills"). NUNCA escribas justificaciones tautológicas tipo "Habla francés o alemán" o "Cumple el criterio".
12. NO inventes perfiles que no aparezcan en los resultados de los grupos. Solo lista los que están en los datos proporcionados.

**FORMATO OBLIGATORIO (Markdown):**

La respuesta debe ser ENTERAMENTE una lista numerada continua. NO escribas párrafos en prosa. Sigue EXACTAMENTE esta plantilla, respetando los saltos de línea en blanco entre líneas:

**{intro_tmpl.format(n="[X]", q=query)}**

**{h_main}:**

1. **Nombre Completo** — razón breve

2. **Nombre Completo** — razón breve

**{h_others}:**

3. **Nombre Completo** — razón breve

4. **Nombre Completo** — razón breve

REGLAS DE FORMATO ESTRICTAS:
- CADA perfil ocupa EXACTAMENTE una línea con el formato `N. **Nombre Completo** — razón`.
- Inserta una línea en blanco DESPUÉS de cada perfil (cada uno es un párrafo de una sola línea).
- NUNCA juntes varios perfiles en la misma línea ni en el mismo párrafo.
- Numeración continua a lo largo de toda la respuesta (1, 2, 3, …); no la reinicies en "{h_others}".
- Si una sección no tiene perfiles, OMÍTELA por completo (no escribas el encabezado vacío).
- NO añadas un "Resumen" final ni metadatos de búsqueda.
- NO uses HTML; solo Markdown.

Responde en {lang_name}."""

