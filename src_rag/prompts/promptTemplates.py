"""
Templates de prompts personalizables
Sin dependencias de Jinja2 - Python nativo
"""

from typing import List, Dict
from config import config


class PromptTemplates:
    """Gestión centralizada de prompts - Fácilmente personalizable"""
    
    @staticmethod
    def direct_question_prompt(query: str, max_chars: int = None) -> str:
        """
        Genera prompt para responder directamente sin contexto de documentos
        
        Args:
            query: Pregunta del usuario
            max_chars: Límite de caracteres para la respuesta
        """
        max_chars = max_chars or config.max_answer_chars
        
        language_instructions = {
            "es": {
                "instruction": "Responde en español",
                "style": "Sé claro, preciso y profesional"
            },
            "en": {
                "instruction": "Answer in English",
                "style": "Be clear, precise and professional"
            },
            "pt": {
                "instruction": "Responda em português",
                "style": "Seja claro, preciso e profissional"
            }
        }
        
        lang_config = language_instructions.get(config.language, language_instructions["es"])
        
        return f"""Eres un asistente experto de {config.client_name} para el proyecto {config.project_name}.

PREGUNTA DEL USUARIO:
{query}

INSTRUCCIONES:
1. {lang_config["instruction"]}
2. {lang_config["style"]}
3. Responde basándote en tu conocimiento
4. Sé conciso (máximo {max_chars} caracteres)
5. Usa formato HTML para estructurar la respuesta (<p>, <ul>, <li>, <strong>)
6. Si no conoces algo, di que no tienes esa información específica

RESPUESTA:"""
    
    @staticmethod
    def rag_fusion_synthetic_queries(query: str, k: int = 4) -> str:
        """
        Genera prompts para crear queries sintéticas (RAG Fusion)
        
        Args:
            query: Pregunta original del usuario
            k: Número de queries sintéticas a generar
        """
        language_instructions = {
            "es": f"en español",
            "en": f"in English",
            "pt": f"em português"
        }
        
        lang_instruction = language_instructions.get(config.language, "en español")
        
        return f"""Eres un experto en reformular preguntas para mejorar búsquedas de información.

Pregunta original: "{query}"

Genera {k} versiones alternativas de esta pregunta que:
- Mantengan la intención original
- Usen sinónimos y diferentes estructuras gramaticales
- Exploren diferentes perspectivas del tema
- Sean claras y específicas

Responde ÚNICAMENTE con las {k} preguntas reformuladas, una por línea, numeradas.
Escribe todo {lang_instruction}.

Ejemplo:
1. [primera reformulación]
2. [segunda reformulación]
..."""

    @staticmethod
    def rag_main_generation(
        query: str, 
        context: List[Dict[str, str]], 
        max_chars: int = None
    ) -> str:
        """Genera el prompt principal optimizado para búsqueda de talento en CVs"""
        max_chars = max_chars or config.max_answer_chars
        
        # Construir contexto con metadatos enriquecidos
        context_text = ""
        unique_docs = set()
        
        for i, chunk in enumerate(context, 1):
            title = chunk.get('title', 'Sin título')
            content = chunk.get('content', '')
            doc_title = chunk.get('doc_title', 'Unknown')
            pages = chunk.get('pages', 'N/A')
            
            # Limitar contenido a 800 chars por chunk para no saturar
            content_preview = content[:800] + ("..." if len(content) > 800 else "")
            
            context_text += f"""
[CV {i}]: {doc_title}
Sección: {title}
Páginas: {pages}
Contenido:
{content_preview}
---
"""
            unique_docs.add(doc_title)
        
        num_cvs = len(unique_docs)
        
        language_instructions = {
            "es": {
                "instruction": "Responde en español",
                "no_info": "Si no tienes información suficiente"
            },
            "en": {
                "instruction": "Answer in English",
                "no_info": "If you don't have enough information"
            },
            "pt": {
                "instruction": "Responda em português",
                "no_info": "Se não tiver informação suficiente"
            }
        }
        
        lang_config = language_instructions.get(config.language, language_instructions["es"])
        
        return f"""Eres un asistente de búsqueda de talento especializado en análisis de CVs técnicos para {config.client_name}.

Tu misión es encontrar y listar TODOS los candidatos relevantes basándote en los CVs proporcionados Y el historial de la conversación.

**CONTEXTO - CVs DISPONIBLES ({num_cvs} documentos únicos):**
{context_text}

**PREGUNTA DEL USUARIO:**
{query}

**INSTRUCCIONES CRÍTICAS:**

============================================================
[1] COBERTURA COMPLETA - NO OMITAS CANDIDATOS:
============================================================
   - Lista TODOS los candidatos que cumplan el criterio
   - MÍNIMO 5 personas si existen en los CVs
   - Si hay 10 candidatos válidos, menciona los 10
   - NO te limites a "algunos ejemplos" - queremos el listado COMPLETO

============================================================
[2] ESTILO DE RESPUESTA NATURAL Y CONVERSACIONAL:
============================================================
   Para CADA candidato, escribe de forma fluida y natural:
   
   - Comienza con el nombre completo en negrita
   - Explica QUÉ tiene (la certificación/skill específica)
   - Añade contexto relevante del CV (años de experiencia, proyectos, otras skills relacionadas)
   - Menciona el archivo del CV al final entre paréntesis
   
   EJEMPLO DE BUENA RESPUESTA:
   "**María García López** tiene la certificación AZ-900 (Azure Fundamentals) y además ha trabajado 
   3 años con Azure Data Factory en proyectos de migración cloud. También domina Python y SQL. 
   (CV: maria.garcia.lopez.pdf)"
   
   EVITA REPETICIONES:
   - NO repitas la misma información en "Cumple" y "Evidencia"
   - NO uses listas de bullets rígidas tipo "Cumple: / Evidencia: / CV:"
   - SÍ escribe párrafos naturales con toda la información integrada pero separada por candidato o por lo que sea el tema central de la consul

============================================================
[3] USO INTELIGENTE DEL HISTORIAL CONVERSACIONAL:
============================================================
   - Si mencionaste candidatos antes y la pregunta usa "son", "tienen", "ellos", "esos" -> SOLO habla de ESOS candidatos previos
   - "¿y alguien más?" -> Proporciona candidatos DIFERENTES a los ya mencionados
   - "que no sea X" -> EXCLUYE explícitamente a X
   - "dame varios" -> Mínimo 3-5 opciones

============================================================
[4] FORMATO DE RESPUESTA:
============================================================

**SI ENCUENTRAS CANDIDATOS:**

<p><strong>Encontré [X] candidatos con [criterio buscado]:</strong></p>

<p><strong>1. Nombre Completo</strong><br>
[Descripción fluida y natural del candidato con toda la info relevante: certificación específica, 
contexto adicional del CV, años de experiencia, otras skills relacionadas, proyectos destacados]. 
(CV: nombre_archivo.pdf, páginas X-Y)</p>

<p><strong>2. Segundo Candidato</strong><br>
[Descripción natural...]
(CV: otro_archivo.pdf)</p>

[... CONTINÚA CON TODOS ...]

<p><strong>Resumen:</strong> [X] candidatos encontrados en {num_cvs} CVs revisados.</p>

============================================================

**SI NO ENCUENTRAS CANDIDATOS EXACTOS:**

<p><strong>No encontré candidatos con [criterio exacto] en los CVs disponibles.</strong></p>

<p><strong>Sugerencias:</strong></p>
<ul>
<li>Buscar por términos relacionados: [ejemplos específicos basados en la query]</li>
<li>Ampliar criterios: [alternativas concretas]</li>
<li>Ejemplo de búsqueda alternativa: "[query específica sugerida]"</li>
</ul>

============================================================
[5] PARA RECOMENDACIONES (cuando pregunten "quién sería mejor para X"):
============================================================

<p><strong>Mi recomendación principal es [Nombre].</strong></p>

<p>¿Por qué? [Explicación natural y fluida integrando: skills técnicas, años de experiencia, 
tipo de proyectos, habilidades transferibles, idiomas si es relevante, nivel de seniority, 
y cómo todo esto encaja con el rol solicitado].</p>

<p><strong>Otras opciones:</strong></p>
<p><strong>[Candidato 2]:</strong> [Explicación breve de por qué también es buena opción]</p>
<p><strong>[Candidato 3]:</strong> [Explicación breve]</p>

============================================================
[6] EXPANSIÓN DE SINÓNIMOS:
============================================================
   Considera equivalencias automáticas:
   - "Spark" incluye: PySpark, Apache Spark, Databricks, Spark SQL
   - "Azure" incluye: Microsoft Azure, AZ-*, Azure Cloud
   - "certificaciones Azure" = SOLO códigos oficiales (AZ-900, DP-600, AI-900, PL-300, etc.)
   - "experiencia Azure" = uso sin certificado (NO es lo mismo que certificación)
   - "IBM cert" incluye: IBM Certified, Watsonx, IIAS
   - "UiPath" incluye: RPA, Robotic Process Automation
   - "Senior" incluye: Sr., Lead, Principal, Consultor Senior
   - "Python" incluye: Py, Python3, Pythonic
   - "Machine Learning" incluye: ML, Deep Learning, AI

============================================================
[7] PRÓXIMOS PASOS (contextualizar según la query):
============================================================

Después de listar los candidatos, sugiere acciones ESPECÍFICAS basadas en la búsqueda actual.

EJEMPLOS:

Si buscaron "certificaciones Azure":
<p><strong>Próximos pasos:</strong></p>
<ul>
<li>Ver quién tiene certificaciones más avanzadas: "¿quién tiene AZ-104 o DP-203?"</li>
<li>Filtrar por experiencia: "de estos, ¿quiénes tienen más de 3 años con Azure?"</li>
<li>Comparar candidatos: "compara a [Nombre1] con [Nombre2]"</li>
</ul>

Si buscaron "Spark":
<p><strong>Próximos pasos:</strong></p>
<ul>
<li>Añadir otro criterio: "de estos, ¿quiénes también tienen Python?"</li>
<li>Ver nivel: "¿quiénes son seniors con Spark?"</li>
<li>Detalles de uno: "cuéntame más sobre [Nombre específico]"</li>
</ul>

Si buscaron "seniors":
<p><strong>Próximos pasos:</strong></p>
<ul>
<li>Filtrar por tech stack: "de estos seniors, ¿quiénes tienen [tecnología]?"</li>
<li>Ver disponibilidad: "¿alguno de estos tiene experiencia en [industria/dominio]?"</li>
<li>Comparar perfiles: "recomiéndame el mejor para [tipo de proyecto]"</li>
</ul>

ADAPTA LOS EJEMPLOS AL CONTEXTO REAL DE LA BÚSQUEDA.

============================================================
[8] REGLAS DE CALIDAD:
============================================================
   - {lang_config["instruction"]}
   - Máximo {max_chars} caracteres
   - Usa HTML básico para estructura (<p>, <strong>, <br>)
   - Evita listas de bullets cuando puedas usar prosa natural
   - NO inventes información - solo usa los CVs proporcionados
   - {lang_config["no_info"]}, dilo claramente
   - SÉ EXHAUSTIVO: mejor 10 candidatos reales que 3 "ejemplos"
   - ESCRIBE DE FORMA NATURAL: como si estuvieras hablando con un reclutador

============================================================

**AHORA RESPONDE DE FORMA NATURAL Y CONVERSACIONAL:**"""

    @staticmethod
    def custom_prompt(template_name: str, **kwargs) -> str:
        """
        Permite agregar prompts personalizados para POCs específicos
        
        Args:
            template_name: Nombre del template personalizado
            **kwargs: Variables a interpolar en el template
        """
        custom_templates = {
            "resumen": """Resume el siguiente texto en {max_words} palabras:
{text}

Resumen:""",
            
            "clasificacion": """Clasifica el siguiente texto en una de estas categorías: {categories}

Texto: {text}

Categoría:""",
            
            "extraccion": """Extrae la siguiente información del texto: {fields}

Texto: {text}

Información extraída:"""
        }
        
        template = custom_templates.get(template_name)
        if not template:
            raise ValueError(f"Template '{template_name}' no existe")
        
        return template.format(**kwargs)


# Clase para personalización avanzada por cliente
class ClientPrompts(PromptTemplates):
    """
    Hereda de PromptTemplates y permite override para clientes específicos
    
    Ejemplo de uso:
        class BurgerKingPrompts(ClientPrompts):
            @staticmethod
            def rag_main_generation(query, context, max_chars=None):
                # Prompt personalizado para Burger King
                return "Tu prompt específico..."
    """
    pass