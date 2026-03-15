"""
Workflow usando Azure OpenAI Assistants API (Azure AI Foundry)
Reemplaza el Agent Builder de OpenAI por Assistants de Azure
CON SOPORTE PARA AZURE AD (Managed Identity)
"""
import asyncio
import os
import time
import json
from typing import Dict, List, Optional
from pydantic import BaseModel
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from config import config
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.core.rest import HttpRequest
from azure.core.pipeline.policies import BearerTokenCredentialPolicy
from azure.ai.projects.models import ConnectionType
from azure.ai.agents.models import AzureAISearchQueryType, AzureAISearchTool
from typing import Optional, Dict, Any


# # ===== CONFIGURACIÓN POR DEFECTO =====
# AZURE_OPENAI_AGENT_ENDPOINT = os.getenv("AZURE_OPENAI_AGENT_ENDPOINT", "https://open-ai-c4c-pre.openai.azure.com/")
# AZURE_OPENAI_AGENT_API_KEY = os.getenv("AZURE_OPENAI_AGENT_API_KEY", "b86b3a39d06f4e0d8d7b5c484867b197")
# AZURE_OPENAI_AGENT_API_VERSION = os.getenv("AZURE_OPENAI_AGENT_API_VERSION", "2024-05-01-preview")
# AZURE_OPENAI_AGENT_DEPLOYMENT = os.getenv("AZURE_OPENAI_AGENT_DEPLOYMENT", "gpt-5-mini")
# AZURE_OPENAI_AGENT_VECTOR_STORE_ID = os.getenv("AZURE_OPENAI_AGENT_VECTOR_STORE_ID", "vs_iu4OtePpYP4Ob7IEamJz3Zaf")

# print("✅ Configuración Azure OpenAI Assistants:")
# print(f"   Endpoint: {AZURE_OPENAI_AGENT_ENDPOINT}")
# print(f"   Deployment: {AZURE_OPENAI_AGENT_DEPLOYMENT}")
# print(f"   Vector Store: {AZURE_OPENAI_AGENT_VECTOR_STORE_ID}")

# # ===== CLIENTE AZURE OPENAI POR DEFECTO =====
# client = AzureOpenAI(
#     azure_endpoint=AZURE_OPENAI_AGENT_ENDPOINT,
#     api_key=AZURE_OPENAI_AGENT_API_KEY,
#     api_version=AZURE_OPENAI_AGENT_API_VERSION
# )

# ===== SCHEMAS =====
class WorkflowInput(BaseModel):
    input_as_text: str

class CvsDatabaseSchema(BaseModel):
    output_text: str
    sources_array: List[str]

# ===== CACHÉ DE MODELOS DE AGENTS/ASSISTANTS =====
_AGENT_MODEL_CACHE = {}

def get_agent_model(client, agent_id: str, api_type: str) -> str:
    """
    Recupera el modelo de un agent/assistant para guardarlo en caché.
    
    Args:
        client: Cliente de Azure (AIProjectClient o AzureOpenAI)
        agent_id: ID del agent/assistant
        api_type: "azure_ai_projects" o "azure"
    
    Returns:
        str: Nombre del modelo (deployment)
    """
    # Verificar caché
    if agent_id in _AGENT_MODEL_CACHE:
        return _AGENT_MODEL_CACHE[agent_id]
    
    try:
        if api_type == "azure_ai_projects":
            agent = client.agents.get_agent(agent_id)
            model = getattr(agent, 'model', 'gpt')
        else:
            agent = client.beta.assistants.retrieve(agent_id)
            model = getattr(agent, 'model', 'gpt')
        
        # Guardar en caché
        _AGENT_MODEL_CACHE[agent_id] = model
        return model
    
    except Exception as e:
        print(f"         ⚠️ Error recuperando modelo para {agent_id}: {e}")
        return 'unknown_model'

# ===== ORQUESTACIÓN MANUAL CON PARALELIZACIÓN =====

async def run_parallel_orchestration(
    query: str,
    use_client,
    main_agent_id: str,
    subagent_configs: List[Dict],
    api_type: str = "azure_ai_projects",
    main_agent_model: str = "gpt-4o"
):
    """
    Orquestación manual con paralelización real de subagentes
    
    Args:
        query: Query del usuario
        use_client: Cliente de Azure (AIProjectClient o AzureOpenAI)
        main_agent_id: ID del agente principal
        subagent_configs: Lista de configs de subagentes
            [{"agent_id": "...", "name": "...", "model": "...", "description": "..."}, ...]
        api_type: "azure_ai_projects" o "azure"
        main_agent_model: Modelo del agente principal
    
    Returns:
        dict: Respuesta final con metadata completa
    """
    print(f"🎯 Iniciando orquestación paralela con {len(subagent_configs)} subagentes: {[sa['name'] for sa in subagent_configs]}")
    
    # ===== FASE 1: AGENTE PRINCIPAL ANALIZA LA QUERY =====
    print("\n📋 Fase 1: Agente principal analiza query...")
    phase1_start = time.time()
    
    decision_prompt = f"""Analiza esta consulta del usuario y decide qué agentes especializados necesitas llamar.

                            Agentes disponibles:
                            {chr(10).join([f"- {sa['name']}: {sa.get('description', 'No description')}" for sa in subagent_configs])}

                            Consulta del usuario:
                            {query}

                            Responde con un JSON que contenga:
                            1. "subagents": Array con los nombres de los agentes a llamar (ej: ["CVs_Agente_Skills", "CVs_Agente_Experiencia"])
                            2. "reason": Breve explicación de por qué elegiste esos agentes
                            3. "queries": Objeto con las subconsultas específicas para cada agente, usando su nombre como clave

                            Ejemplo de respuesta:
                            {{
                                "subagents": ["CVs_Agente_Skills", "CVs_Agente_Experiencia"],
                                "reason": "La consulta pregunta por perfiles con Python y experiencia en IA",
                                "queries": {{
                                    "CVs_Agente_Skills": "Busca empleados con skills en Python, Machine Learning y Azure",
                                    "CVs_Agente_Experiencia": "Busca empleados con experiencia en proyectos de IA y data science"
                                }}
                            }}

                            IMPORTANTE: Responde SOLO con JSON válido, sin markdown ni texto adicional."""

    try:
        if api_type == "azure_ai_projects":
            decision_run = use_client.agents.create_thread_and_process_run(
                agent_id=main_agent_id,
                thread={"messages": [{"role": "user", "content": decision_prompt}]}
            )
            
            # Obtener respuesta
            if hasattr(use_client, '_config') and hasattr(use_client._config, 'api_version'):
                api_version = use_client._config.api_version
            else:
                api_version = "2024-02-15-preview"
            
            messages_url = f"threads/{decision_run.thread_id}/messages?api-version={api_version}"
            from azure.core.rest import HttpRequest as CoreHttpRequest
            response = use_client.send_request(
                CoreHttpRequest(method="GET", url=messages_url),
                stream=False
            )
            messages = response.json().get("data", [])
            decision_text = messages[0]["content"][0]["text"]["value"]
        else:
            # Azure OpenAI
            thread = use_client.beta.threads.create()
            use_client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=decision_prompt
            )
            run = use_client.beta.threads.runs.create_and_poll(
                thread_id=thread.id,
                assistant_id=main_agent_id
            )
            messages = use_client.beta.threads.messages.list(thread_id=thread.id)
            decision_text = messages.data[0].content[0].text.value
        
        # Parsear decisión
        import re
        decision_text = re.sub(r'```json\n?', '', decision_text)
        decision_text = re.sub(r'```\n?', '', decision_text)
        decision = json.loads(decision_text.strip())
        
        selected_subagents = decision.get("subagents", [])
        reason = decision.get("reason", "No reason provided")
        queries_map = decision.get("queries", {})
        
        print(f"   📌 Subagentes seleccionados: {selected_subagents}")
        print(f"   💡 Razón: {reason}")
        
        phase1_elapsed = time.time() - phase1_start
        print(f"   ⏱️ Fase 1 completada en {phase1_elapsed:.2f}s")
        
    except Exception as e:
        phase1_elapsed = time.time() - phase1_start  # ✅ AÑADIR ESTA LÍNEA
        print(f"   ⚠️ Error parseando decisión: {e}")
        print(f"   🔄 Usando todos los subagentes como fallback")
        selected_subagents = [sa["name"] for sa in subagent_configs]
        queries_map = {sa["name"]: query for sa in subagent_configs}
        reason = "Fallback: usando todos los agentes por error en parsing"
    
    # ===== FASE 2: EJECUTAR SUBAGENTES EN PARALELO =====
    print(f"\n🚀 Fase 2: Ejecutando {len(selected_subagents)} subagentes EN PARALELO...")
    
    if hasattr(use_client, '_config') and hasattr(use_client._config, 'api_version'):
        api_version = use_client._config.api_version
    else:
        api_version = "2024-02-15-preview"
    
    def call_subagent_sync(subagent_config: Dict, context: str):
        """Ejecuta un subagente SÍNCRONO y captura su respuesta + metadata"""
        agent_name = subagent_config["name"]
        agent_id = subagent_config["agent_id"]
        model = subagent_config.get("model", "gpt-4o")
        
        start_time = time.time()
        
        try:
            if api_type == "azure_ai_projects":
                run = use_client.agents.create_thread_and_process_run(
                    agent_id=agent_id,
                    thread={"messages": [{"role": "user", "content": context}]}
                )
                
                # Obtener respuesta
                messages_url = f"threads/{run.thread_id}/messages?api-version={api_version}"
                from azure.core.rest import HttpRequest as CoreHttpRequest
                response = use_client.send_request(
                    CoreHttpRequest(method="GET", url=messages_url),
                    stream=False
                )
                messages = response.json().get("data", [])
                result_text = messages[0]["content"][0]["text"]["value"]
                
                usage = {
                    "prompt_tokens": run.usage.prompt_tokens if run.usage else 0,
                    "completion_tokens": run.usage.completion_tokens if run.usage else 0,
                    "total_tokens": run.usage.total_tokens if run.usage else 0,
                }
                
            else:
                # Azure OpenAI estándar
                thread = use_client.beta.threads.create()
                use_client.beta.threads.messages.create(
                    thread_id=thread.id,
                    role="user",
                    content=context
                )
                run = use_client.beta.threads.runs.create_and_poll(
                    thread_id=thread.id,
                    assistant_id=agent_id
                )
                messages = use_client.beta.threads.messages.list(thread_id=thread.id)
                result_text = messages.data[0].content[0].text.value
                
                usage = {
                    "prompt_tokens": run.usage.prompt_tokens if run.usage else 0,
                    "completion_tokens": run.usage.completion_tokens if run.usage else 0,
                    "total_tokens": run.usage.total_tokens if run.usage else 0,
                }
            
            elapsed = time.time() - start_time
            
            return {
                "agent_name": agent_name,
                "agent_id": agent_id,
                "model": model,
                "result": result_text,
                "usage": usage,
                "elapsed_time": elapsed,
                "status": "success"
            }
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"   ❌ Error en {agent_name}: {e}")
            
            # ✅ MÁS DETALLES DEL ERROR DE AZURE
            if hasattr(e, 'response'):
                print(f"      📋 Status Code: {e.response.status_code}")
                try:
                    error_body = e.response.json()
                    print(f"      📋 Error Body: {error_body}")
                except:
                    print(f"      📋 Response Text: {e.response.text[:500]}")
            
            if hasattr(e, 'error'):
                print(f"      📋 Error Details: {e.error}")
            
            import traceback
            traceback.print_exc()
            return {
                "agent_name": agent_name,
                "agent_id": agent_id,
                "model": model,
                "result": f"Error: {str(e)}",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "elapsed_time": elapsed,
                "status": "error"
            }
    
    # Filtrar configs de subagentes seleccionados
    active_configs = [
        sa for sa in subagent_configs 
        if sa["name"] in selected_subagents
    ]
    
    if not active_configs:
        print("   ⚠️ No hay subagentes activos")
        active_configs = []
    
    # PARALELIZACIÓN: asyncio.to_thread() envuelve CADA llamada síncrona
    subagent_tasks = [
        asyncio.to_thread(
            call_subagent_sync,
            config, 
            queries_map.get(config["name"], query)
        )
        for config in active_configs
    ]
    
    parallel_start = time.time()
    subagent_results = await asyncio.gather(*subagent_tasks, return_exceptions=True)
    parallel_elapsed = time.time() - parallel_start
    
    print(f"   ⚡ Todos los subagentes completados en {parallel_elapsed:.2f}s (en paralelo)")
    
    # ===== FASE 3: AGENTE PRINCIPAL SINTETIZA =====
    print("\n🔄 Fase 3: Sintetizando resultados...")
    phase3_start = time.time()
    
    # Preparar contexto con resultados
    synthesis_context = f"""Consulta original del usuario:
    {query}

    ===== RESULTADOS DE SUBAGENTES =====

    """
    
    for i, result in enumerate(subagent_results):
        if isinstance(result, Exception):
            synthesis_context += f"\n{i+1}. ERROR: {result}\n"
        else:
            synthesis_context += f"""
    {i+1}. {result['agent_name']} (modelo: {result['model']}):
    {result['result']}
    {'='*60}
    """
    
    synthesis_prompt = f"""{synthesis_context}

    Basándote en los resultados de los subagentes especializados:

    1. Combina y cruza la información por el campo "Nombre" (cada subagente devuelve JSONs con empleados)
    2. Devuelve la intersección: empleados que aparecen en TODOS los subagentes llamados
    3. Si la intersección está vacía, explica qué dimensión es más restrictiva
    4. Proporciona una respuesta completa y natural al usuario

    Guidelines:
    - Responde en el mismo idioma que la consulta original
    - Sé claro y directo
    - Si hay candidatos, lista sus nombres y un breve resumen
    - Si no hay intersección completa, menciona coincidencias parciales
    - NO menciones la orquestación ni los subagentes en tu respuesta al usuario"""
    
    try:
        if api_type == "azure_ai_projects":
            final_run = use_client.agents.create_thread_and_process_run(
                agent_id=main_agent_id,
                thread={"messages": [{"role": "user", "content": synthesis_prompt}]}
            )
            
            messages_url = f"threads/{final_run.thread_id}/messages?api-version={api_version}"
            response = use_client.send_request(
                CoreHttpRequest(method="GET", url=messages_url),
                stream=False
            )
            messages = response.json().get("data", [])
            final_text = messages[0]["content"][0]["text"]["value"]
            
            final_usage = {
                "prompt_tokens": final_run.usage.prompt_tokens if final_run.usage else 0,
                "completion_tokens": final_run.usage.completion_tokens if final_run.usage else 0,
                "total_tokens": final_run.usage.total_tokens if final_run.usage else 0,
            }
        else:
            thread = use_client.beta.threads.create()
            use_client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=synthesis_prompt
            )
            run = use_client.beta.threads.runs.create_and_poll(
                thread_id=thread.id,
                assistant_id=main_agent_id
            )
            messages = use_client.beta.threads.messages.list(thread_id=thread.id)
            final_text = messages.data[0].content[0].text.value
            
            final_usage = {
                "prompt_tokens": run.usage.prompt_tokens if run.usage else 0,
                "completion_tokens": run.usage.completion_tokens if run.usage else 0,
                "total_tokens": run.usage.total_tokens if run.usage else 0,
            }
        
        phase3_elapsed = time.time() - phase3_start
        print(f"   ✅ Síntesis completada en {phase3_elapsed:.2f}s")
        
    except Exception as e:
        phase3_elapsed = time.time() - phase3_start
        print(f"   ❌ Error en síntesis: {e} (tiempo: {phase3_elapsed:.2f}s)")
        final_text = f"Error al sintetizar resultados: {e}"
        final_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    
    # ===== CALCULAR TOTALES =====
    total_tokens = final_usage["total_tokens"]
    for result in subagent_results:
        if not isinstance(result, Exception):
            total_tokens += result["usage"]["total_tokens"]
    
    print(f"\n📊 Orquestación completada:")
    print(f"   - Fase 1 (decisión): {phase1_elapsed:.2f}s")
    print(f"   - Fase 2 (paralela): {parallel_elapsed:.2f}s ({len(subagent_results)} subagentes)")
    print(f"   - Fase 3 (síntesis): {phase3_elapsed:.2f}s")
    print(f"   - Tiempo total: {phase1_elapsed + parallel_elapsed + phase3_elapsed:.2f}s")
    print(f"   - Tokens totales: {total_tokens}")
    
    return {
        "output_text": final_text,
        "usage": {
            "prompt_tokens": final_usage["prompt_tokens"],
            "completion_tokens": final_usage["completion_tokens"],
            "total_tokens": total_tokens,
            "model": main_agent_model
        },
        "sub_agents_usage": [
            {
                "tool_type": "parallel_orchestration",
                "agent_name": r["agent_name"],
                "agent_id": r["agent_id"],
                "model": r["model"],
                "prompt_tokens": r["usage"]["prompt_tokens"],
                "completion_tokens": r["usage"]["completion_tokens"],
                "total_tokens": r["usage"]["total_tokens"],
                "elapsed_time": r["elapsed_time"],
                "status": r["status"]
            }
            for r in subagent_results
            if not isinstance(r, Exception)
        ],
        "orchestration_metadata": {
            "parallel_execution_time": parallel_elapsed,
            "subagents_selected": selected_subagents,
            "selection_reason": reason,
            "orchestration_mode": "parallel_manual"
        }
    }

# ===== CONFIGURACIONES DE ASISTENTES =====
ASSISTANT_CONFIGS = {
    "cvs_database": {
        "name": "CVs Database Assistant",
        "description": "Experto en CVs del equipo EY",
        "endpoint": "https://tevia01s-swcedc-tcrmopenai.openai.azure.com/",
        "api_key": "defd639e766744ea82f0775bc6d98fa9",
        "deployment": "gpt-5",
        "vector_store_id": "vs_7RP0nOpLfunf5hpJLmYvjcdU",
        "prompt": """You are an expert in EY team CVs (RAG system):
Explore EY CV external information using the tools you have (file search or vector search).
Analyze any relevant data, checking your work.
Make sure to output a concise and short answer.
Answer in the same language than the query.
Suggest a follow up question related to the previous question, and to one of the skills, experiences or people mentioned in previous search. Do not suggest anything out of your duties (answering questions about EY team CVs):
DO: suggest new questions about specific skills, experiences, seniority, names, team etc. or organizing the information of people in a different way.
DO NOT: suggest exporting to any file, sending mails or performing other external tool tasks.
Be exhaustive while searching.

IMPORTANT: Never include citations with brackets 【】 or numeric references. Answer naturally without citing sources.""",
        "temperature": 1.0,
        "top_p": 1.0
    },
    "csv_formatter": {
        "name": "CVs CSV Formatter Assistant",
        "description": "Especialista en formatear CVs del equipo EY a formato CSV",
        "endpoint": "https://tevia01s-swcedc-tcrmopenai.openai.azure.com/",
        "api_key": "defd639e766744ea82f0775bc6d98fa9",
        "deployment": "gpt-5",
        "vector_store_id": "vs_7RP0nOpLfunf5hpJLmYvjcdU",
        "prompt": """You are a CSV formatter specialist for EY team data. YOUR TASK: Output each CSV row SEPARATELY with clear visual separation so the user can copy each row one by one. FORMAT EACH ROW LIKE THIS: ROW 1: Column1;Column2;Column3;Column4;Column5;Column6;Column7;Column8 ROW 2: Personal information;;;;PICTURE;Profile Summary;[text]; ROW 3: Name and Surnames;[name];;;;;; For EMPTY ROWS (only semicolons), show: ROW X: [Fila vacía] RULES: 1. Each row must be on its own section with a blank line separation 2. Label each section as ROW 1, ROW 2, ROW 3, etc. 3. Put the CSV line directly after the ROW label 4. Use semicolon (;) separator - 8 columns always 5. NO explanations, just the formatted rows 6. CRITICAL: For rows that are only semicolons (;;;;;;;), write "[Fila vacía]" instead STRUCTURE: ROW 1: Header (Column1;Column2;...) ROW 2: Personal information;;;;PICTURE;Profile Summary;[text]; ROW 3: Name and Surnames;[name];;;;;; ROW 4: Rank;[position];;;;;; ROW 5: Email;[email];;;;;; ROW 6: Mobile phone;[phone];;;;;; ROW 7: [Fila vacía] ROW 8: Education (in reverse chronological order);;;;;;; ROW 9: Degree title;University;Graduation year;Start year;;;; ROW 10-12: Education entries ROW 13: [Fila vacía] ROW 14: Certifications;;;;;;; ROW 15: Certification;Issuer;Certification date;;;;; ROW 16+: Certification entries ROW X: [Fila vacía] ROW Y: Work experience (in reverse chronological order);;;;;;; ROW Z: Client;Industry;Project title;Start - End dates;Project description;Role;Responsibilities;Skills ROW Z+1: Work experience entries Remember: Rows with only semicolons should display as "[Fila vacía]"

IMPORTANT: Never include citations with brackets 【】 or numeric references. Answer naturally without citing sources.""",
        "temperature": 1.0,
        "top_p": 1.0
    }
}

# ===== FUNCIÓN PARA CREAR CLIENTE SEGÚN API TYPE =====
def _create_client_with_auth(assistant_config: dict):
    """
    Crea el cliente apropiado según el api_type
    """
    api_type = assistant_config.get("api_type", "azure")
    endpoint = assistant_config["endpoint"]
    
    if api_type == "azure_ai_projects":
        # ✅ AZURE AI PROJECTS: Usa Azure AD
        
        try:
            credential = DefaultAzureCredential()
            
            # ✅ AIProjectClient NO acepta api_version
            client = AIProjectClient(
                endpoint=endpoint,
                credential=credential
            )
            
            print(f"      ✅ Cliente Azure AI Projects creado con Azure AD")
            return client, "azure_ai_projects"
            
        except Exception as e:
            print(f"      ❌ Error al crear cliente con Azure AD: {e}")
            raise Exception(
                f"Error de autenticación Azure AD:\n\n"
                f"1. Localmente: Ejecuta 'az login'\n"
                f"2. En App Service: Verifica Managed Identity con rol 'Azure AI Developer'\n"
                f"3. Endpoint: {endpoint}\n\n"
                f"Error: {e}"
            )
    
    else:
        # ✅ AZURE OPENAI SERVICE: Usa API Key
        api_key = assistant_config.get("api_key")
        if not api_key:
            raise ValueError("api_key requerido para api_type='azure'")
        
        # client = AzureOpenAI(
        #     azure_endpoint=endpoint,
        #     api_key=api_key,
        #     api_version=AZURE_OPENAI_AGENT_API_VERSION
        # )
        
        return client, "azure"

# ===== FUNCIÓN HELPER PARA DETECTAR TIPO DE CONSULTA =====
def detect_assistant_type(query: str) -> str:
    """
    Detecta qué asistente usar basándose en la query
    
    Returns:
        "csv_formatter" si detecta solicitud de formato CSV
        "cvs_database" para consultas normales de CVs
    """
    csv_keywords = [
        "csv", "formato csv", "exportar csv", "convertir a csv",
        "formato tabla", "semicolon", "semicolons", "separador",
        "formato semicolon", "separado por", "columnas csv"
    ]
    
    query_lower = query.lower()
    
    for keyword in csv_keywords:
        if keyword in query_lower:
            return "csv_formatter"
    
    return "cvs_database"


def _is_reasoning_model(deployment: str) -> bool:
    """Detecta si el modelo es de razonamiento (no soporta temperature/top_p)"""
    if not deployment:
        return False
    deployment_lower = deployment.lower()
    reasoning_models = ['o1', 'o3', 'gpt-5', 'o1-preview', 'o1-mini', 'o3-mini']
    return any(model in deployment_lower for model in reasoning_models)

# ===== FUNCIÓN PARA CREAR/RECUPERAR ASSISTANT =====
def get_or_create_assistant(
    custom_client: Optional[Any] = None,
    deployment: Optional[str] = None,
    vector_store_id: Optional[str] = None,
    instructions: Optional[str] = None,
    temperature: float = 1.0,
    top_p: float = 1.0,
    assistant_key: Optional[str] = None,
    assistant_config: Optional[Dict] = None,
    client_type: str = "azure"
):
    """
    Recupera o crea un asistente/agent según el tipo de cliente
    Soporta:
    - File Search (comportamiento por defecto)
    - Azure AI Search (si search_type == "azure_ai_search")
    """
    # ✅ VALIDACIÓN DE API KEY PARA AZURE AI PROJECTS
    if assistant_config:
        api_type = assistant_config.get("api_type", "azure")
        if api_type == "azure_ai_projects":
            # print(f"Usa Azure AD (no requiere api_key)")
            pass
        else:
            api_key = assistant_config.get("api_key", "").strip()
            if not api_key:
                error_msg = (
                    f"❌ Configuración inválida: El asistente '{assistant_key or 'unknown'}' "
                    f"de tipo 'azure_ai_projects' requiere una api_key válida.\n"
                    f"Por favor, actualiza el archivo {assistant_key}.json en blob storage "
                    f"con una api_key válida."
                )
                raise ValueError(error_msg)
    
    use_client = custom_client
    use_deployment = deployment
    use_vector_store = vector_store_id
    use_instructions = instructions or "You are a helpful assistant..."
    
    # ✅ DETECTAR SI ES AZURE AI PROJECTS
    is_ai_projects = client_type == "azure_ai_projects"
    
    # ✅ DETECTAR TIPO DE BÚSQUEDA
    search_type = assistant_config.get("search_type", "file_search") if assistant_config else "file_search"
    
    cache_key = f"{use_deployment}_{use_vector_store}_{assistant_key or 'default'}_{client_type}_{search_type}"
    
    if not hasattr(get_or_create_assistant, '_cache'):
        get_or_create_assistant._cache = {}
    
    if cache_key in get_or_create_assistant._cache:
        cached = get_or_create_assistant._cache[cache_key]
        print(f"♻️ Agent/Assistant recuperado de caché: {cached.id}")
        return cached
    
    # ✅ BUSCAR assistant_id CON PRIORIDADES
    assistant_id_var = None
    
    # ✅ PRIORIDAD 1: Leer del assistant_config si existe
    if assistant_config and 'assistant_id' in assistant_config:
        assistant_id_var = assistant_config.get('assistant_id', '').strip()
        if assistant_id_var:
            print(f"📋 assistant_id desde config JSON: {assistant_id_var}")
    
    # ✅ PRIORIDAD 2: Buscar en variables de entorno específicas
    if not assistant_id_var and assistant_key:
        env_var_name = f"AZURE_ASSISTANT_ID_{assistant_key.upper()}"
        assistant_id_var = os.getenv(env_var_name)
        if not assistant_id_var:
            env_var_name = f"AZURE_ASSISTANT_ID_{assistant_key}"
            assistant_id_var = os.getenv(env_var_name)
    
    # ✅ PRIORIDAD 3: Variable genérica
    if not assistant_id_var:
        assistant_id_var = os.getenv("AZURE_ASSISTANT_ID")
    
    # ✅ RECUPERAR EXISTENTE Y ACTUALIZAR PROMPT
    if assistant_id_var:
        try:
            print(f"📋 Intentando recuperar: {assistant_id_var}")
            
            if is_ai_projects:
                agent = use_client.agents.get_agent(assistant_id_var)
                print(f"   ✅ Agent recuperado: {agent.name}")
                
                if use_instructions and use_instructions != agent.instructions:
                    print(f"   🔄 Actualizando instrucciones del agent...")
                    update_params = {"agent_id": assistant_id_var, "instructions": use_instructions}
                    if not _is_reasoning_model(use_deployment):
                        update_params.update({"temperature": temperature, "top_p": top_p})
                    agent = use_client.agents.update_agent(**update_params)
                    print(f"   ✅ Agent actualizado con nuevo prompt")
            else:
                agent = use_client.beta.assistants.retrieve(assistant_id_var)
                print(f"   ✅ Assistant recuperado: {agent.name}")
                
                if use_instructions and use_instructions != agent.instructions:
                    print(f"   🔄 Actualizando instrucciones del assistant...")
                    update_params = {"assistant_id": assistant_id_var, "instructions": use_instructions}
                    if not _is_reasoning_model(use_deployment):
                        update_params.update({"temperature": temperature, "top_p": top_p})
                    agent = use_client.beta.assistants.update(**update_params)
                    print(f"   ✅ Assistant actualizado con nuevo prompt")
            
            get_or_create_assistant._cache[cache_key] = agent
            return agent
            
        except Exception as e:
            print(f"   ⚠️ No se pudo recuperar/actualizar: {e}")
    
    # ✅ CREAR NUEVO
    print("🆕 Creando nuevo agent/assistant...")
    try:
        if is_ai_projects:            
            # ========================================
            # 🔍 AZURE AI SEARCH
            # ========================================
            if search_type == "azure_ai_search":
                print("   🔍 Configurando Azure AI Search...")
                from azure.ai.projects.models import ConnectionType
                from azure.ai.agents.models import AzureAISearchQueryType, AzureAISearchTool
                
                # Obtener configuración de Azure AI Search
                azure_search_config = assistant_config.get("azure_search_config", {})
                index_name = azure_search_config.get("index_name", "")
                query_type_str = azure_search_config.get("query_type", "simple").upper()
                top_k = azure_search_config.get("top_k", 10)
                filter_str = azure_search_config.get("filter", "")
                
                # Validar index_name
                if not index_name:
                    raise ValueError("❌ azure_search_config.index_name es requerido para search_type='azure_ai_search'")
                
                # Mapear query_type string a enum
                query_type_map = {
                    "SIMPLE": AzureAISearchQueryType.SIMPLE,
                    "KEYWORD": AzureAISearchQueryType.SIMPLE,  # Alias
                    "SEMANTIC": AzureAISearchQueryType.SEMANTIC,
                    "VECTOR": AzureAISearchQueryType.VECTOR,
                    "VECTOR_SIMPLE_HYBRID": AzureAISearchQueryType.VECTOR_SIMPLE_HYBRID,
                    "VECTOR_SEMANTIC_HYBRID": AzureAISearchQueryType.VECTOR_SEMANTIC_HYBRID,
                    "HYBRID": AzureAISearchQueryType.VECTOR_SIMPLE_HYBRID,  # Alias
                }
                query_type = query_type_map.get(query_type_str, AzureAISearchQueryType.SIMPLE)
                
                # Obtener conexión a Azure AI Search
                try:
                    conn_id = use_client.connections.get_default(ConnectionType.AZURE_AI_SEARCH).id
                    print(f"   📡 Connection ID: {conn_id}")
                except Exception as conn_error:
                    raise ValueError(f"❌ No se encontró conexión a Azure AI Search: {conn_error}")
                
                # Crear la tool de Azure AI Search
                ai_search_tool = AzureAISearchTool(
                    index_connection_id=conn_id,
                    index_name=index_name,
                    query_type=query_type,
                    top_k=top_k,
                    filter=filter_str,
                )
                
                # Crear agent con Azure AI Search
                agent = use_client.agents.create_agent(
                    model=use_deployment,
                    name=f"Dynamic Agent - {assistant_key or 'default'}",
                    instructions=use_instructions,
                    tools=ai_search_tool.definitions,
                    tool_resources=ai_search_tool.resources,
                    temperature=temperature,
                    top_p=top_p
                )
                print(f"   ✅ Agent creado con Azure AI Search: {agent.id}")
            
            # ========================================
            # 📁 FILE SEARCH (comportamiento original)
            # ========================================
            else:
                print("   📁 Configurando File Search...")
                
                if not use_vector_store:
                    raise ValueError("❌ vector_store_id es requerido para search_type='file_search'")
                
                agent = use_client.agents.create_agent(
                    model=use_deployment,
                    name=f"Dynamic Agent - {assistant_key or 'default'}",
                    instructions=use_instructions,
                    tools=[FileSearchTool()],
                    tool_resources=ToolResources(
                        file_search=FileSearchToolResource(
                            vector_store_ids=[use_vector_store]
                        )
                    ),
                    temperature=temperature,
                    top_p=top_p
                )
                print(f"   ✅ Agent creado con File Search: {agent.id}")
        
        else:
            # ========================================
            # 🔷 AZURE OPENAI (solo File Search)
            # ========================================
            from azure.ai.projects.models import FileSearchTool, ToolResources, FileSearchToolResource
            agent = use_client.beta.assistants.create(
                model=use_deployment,
                name=f"Dynamic Assistant - {assistant_key or 'default'}",
                instructions=use_instructions,
                tools=[{"type": "file_search"}],
                tool_resources={
                    "file_search": {
                        "vector_store_ids": [use_vector_store]
                    }
                },
                temperature=temperature,
                top_p=top_p
            )
            print(f"   ✅ Assistant creado con File Search: {agent.id}")
        
        if assistant_key:
            print(f"   💡 Guarda en .env: AZURE_ASSISTANT_ID_{assistant_key.upper()}={agent.id}")
        
        get_or_create_assistant._cache[cache_key] = agent
        return agent
        
    except Exception as e:
        error_msg = f"Error al crear: {e}"
        print(f"      ❌ {error_msg}")
        raise Exception(error_msg)
    
# ===== FUNCIÓN PRINCIPAL CON AUTO-DETECCIÓN =====
async def run_workflow_streaming(
    input: WorkflowInput, 
    assistant_config: Optional[Dict] = None,
    assistant_key: Optional[str] = None,
    auto_detect: bool = True
):
    """
    Ejecuta el workflow con streaming habilitado
    
    Args:
        input: WorkflowInput con la query del usuario
        assistant_config: Configuración personalizada del asistente (opcional)
        assistant_key: Clave del asistente a usar (opcional)
        auto_detect: Si True, detecta automáticamente el tipo de asistente
    
    Yields:
        str: Fragmentos de texto de la respuesta
        dict: Metadata al final con usage info
    """
    print(f"\n🌊 Ejecutando workflow Azure Assistants con STREAMING...")
    print(f"   Query: {input.input_as_text[:100]}...")
    
    # ✅ AUTO-DETECCIÓN DE TIPO DE ASISTENTE
    if auto_detect and not assistant_config and not assistant_key:
        detected_type = detect_assistant_type(input.input_as_text)
        
        if detected_type in ASSISTANT_CONFIGS:
            assistant_config = ASSISTANT_CONFIGS[detected_type]
            assistant_key = detected_type
            print(f"   📦 Usando configuración predefinida: {assistant_config['name']}")
    
    # Variable para el tipo de API
    detected_api_type = "azure"
    
    # ✅ DETERMINAR CONFIGURACIÓN
    if assistant_config:
        print(f"   🔧 Usando configuración personalizada del asistente")
    
        # ✅ VALIDACIÓN TEMPRANA DE API TYPE Y KEY
        api_type = assistant_config.get("api_type", "azure")
        api_key = assistant_config.get("api_key")
        
        if api_type == "azure_ai_projects":
            print(f"      ℹ️ Azure AI Projects: Usará autenticación Azure AD")
        
        # Si tiene connected_agents, usar orquestación paralela
        if "connected_agents" in assistant_config and assistant_config["connected_agents"]:
            assistant_config["orchestration_mode"] = "parallel"
            print(f"      🚀 Modo paralelo activado: {len(assistant_config['connected_agents'])} subagentes")
        
        endpoint = assistant_config.get("endpoint")
        deployment = assistant_config.get("deployment")
        vector_store = assistant_config.get("vector_store_id")
        
        # ✅ VALIDAR ENDPOINT
        if not endpoint or not endpoint.strip().startswith("https://"):
            error_msg = (
                f"❌ Endpoint inválido para asistente '{assistant_key}': {endpoint}\n"
                f"El endpoint debe comenzar con 'https://'"
            )
            print(error_msg)
            yield f"data: {error_msg}\n\n"
            return
        
        # ✅ VALIDAR DEPLOYMENT
        if not deployment or not deployment.strip():
            error_msg = (
                f"❌ Deployment inválido para asistente '{assistant_key}': {deployment}\n"
                f"El campo 'deployment' no puede estar vacío"
            )
            print(error_msg)
            yield f"data: {error_msg}\n\n"
            return
        
        # ✅ PROMPT HARDCODEADO PARA CSV FORMATTER
        if assistant_key == "cvs_to_csv":
            instructions = """You are a CSV formatter specialist for EY team data..."""  # (tu prompt completo)
        else:
            instructions = assistant_config.get("prompt", None)
        
        temperature = assistant_config.get("temperature", 1.0)
        top_p = assistant_config.get("top_p", 1.0)
        
        # ✅ CREAR CLIENTE CON MANEJO DE ERRORES MEJORADO
        try:
            custom_client, detected_api_type = _create_client_with_auth(assistant_config)
            print(f"      ✅ Cliente creado correctamente (tipo: {detected_api_type})")
            
        except Exception as client_error:
            error_msg = (
                f"❌ Error al crear cliente: {client_error}\n\n"
                f"Verifica que:\n"
                f"1. El endpoint es correcto\n"
                f"2. Para 'azure': La API key es válida\n"
                f"3. Para 'azure_ai_projects': Has ejecutado 'az login' (local) o tienes Managed Identity configurada (App Service)"
            )
            print(error_msg)
            yield f"data: {error_msg}\n\n"
            return
        
        # ✅ INTENTAR CREAR/RECUPERAR ASSISTANT
        try:
            assistant = get_or_create_assistant(
                custom_client=custom_client,
                deployment=deployment,
                vector_store_id=vector_store,
                instructions=instructions,
                temperature=temperature,
                top_p=top_p,
                assistant_key=assistant_key,
                assistant_config=assistant_config,
                client_type=detected_api_type
            )
            
        except Exception as assist_error:
            error_msg = f"❌ Error al obtener/crear assistant: {assist_error}"
            print(error_msg)
            yield f"data: {error_msg}\n\n"
            return
        
        use_client = custom_client
        use_deployment = deployment
        
    else:
        print(" Ha fallado run_workflow_streaming: No se proporcionó configuración del asistente.")
    
    # ✅ DETECTAR SI ES AZURE AI PROJECTS
    is_ai_projects = detected_api_type == "azure_ai_projects"
    
    # ✅ DETECTAR SI USAR ORQUESTACIÓN MANUAL
    use_manual_orchestration = assistant_config.get("orchestration_mode") == "parallel" if assistant_config else False
    
    if use_manual_orchestration and is_ai_projects:
        # Obtener configs de subagentes desde connected_agents
        connected_agent_keys = assistant_config.get("connected_agents", [])
        
        if not connected_agent_keys:
            print(f"   ⚠️ No hay subagentes configurados, usando modo normal")
            use_manual_orchestration = False
        else:
            # Cargar configs completas de los subagentes
            from main import load_assistants_config
            all_assistants = load_assistants_config().get("assistants", {})
            
            subagent_configs = []
            for key in connected_agent_keys:
                if key in all_assistants:
                    sa = all_assistants[key]
                    subagent_configs.append({
                        "name": sa.get("name", key),
                        "agent_id": sa.get("assistant_id"),
                        "model": sa.get("deployment", "gpt-4o"),
                        "description": sa.get("description", "")
                    })
            
            if not subagent_configs:
                print(f"   ⚠️ No se pudieron cargar configs de subagentes, usando modo normal")
                use_manual_orchestration = False
            else:
                # Ejecutar orquestación manual
                try:
                    result = await run_parallel_orchestration(
                        query=input.input_as_text,
                        use_client=use_client,
                        main_agent_id=assistant.id,
                        subagent_configs=subagent_configs,
                        api_type=detected_api_type,
                        main_agent_model=use_deployment
                    )
                    
                    # Simular streaming del resultado
                    output_text = result["output_text"]
                    lines = output_text.split('\n')
                    for i, line in enumerate(lines):
                        words = line.split(' ')
                        for j, word in enumerate(words):
                            if word:
                                yield word + (" " if j < len(words) - 1 else "")
                                await asyncio.sleep(0.005)
                        if i < len(lines) - 1:
                            yield '\n'
                    
                    # Yield metadata
                    yield {
                        "type": "metadata",
                        "output_text": output_text,
                        "usage": result["usage"],
                        "sub_agents_usage": result["sub_agents_usage"],
                        "orchestration_metadata": result["orchestration_metadata"]
                    }
                    
                    return  # Salir, no usar el flujo normal
                    
                except Exception as orch_error:
                    print(f"   ❌ Error en orquestación manual: {orch_error}")
                    import traceback
                    traceback.print_exc()
                    print(f"   🔄 Fallback a modo normal")
                    use_manual_orchestration = False
    
    # Si no se usa orquestación manual, continuar con el flujo normal
    try:
        import warnings
        warnings.filterwarnings('ignore', category=DeprecationWarning)
        
        if is_ai_projects:
            # ===== AZURE AI PROJECTS =====
            print(f"   🤖 Usando Azure AI Projects API")
            
            try:
                # Crear y ejecutar thread en un solo paso
                thread_run = use_client.agents.create_thread_and_process_run(
                    agent_id=assistant.id,
                    thread={
                        "messages": [
                            {
                                "role": "user",
                                "content": input.input_as_text
                            }
                        ]
                    },
                    polling_interval=1
                )
                
                # ✅ MOSTRAR ERROR SI FALLÓ
                if hasattr(thread_run, 'last_error') and thread_run.last_error:
                    print(f"   ❌ LAST_ERROR CODE: {thread_run.last_error.code}")
                    print(f"   ❌ LAST_ERROR MESSAGE: {thread_run.last_error.message}")

                # Comparar status como string (evita problemas de import en diferentes versiones del SDK)
                status_str = str(thread_run.status).upper()
                
                if "FAILED" in status_str:
                    error_detail = "Unknown error"
                    if hasattr(thread_run, 'last_error') and thread_run.last_error:
                        error_detail = f"{thread_run.last_error.code}: {thread_run.last_error.message}"
                    raise Exception(f"Run failed: {error_detail}")
                elif "CANCELLED" in status_str:
                    raise Exception("Run was cancelled")
                elif "EXPIRED" in status_str:
                    raise Exception("Run expired before completion")
                elif "COMPLETED" not in status_str:
                    raise Exception(f"Run ended with unexpected status: {thread_run.status}")
                
                print(f"   ✅ Run completado exitosamente")
                                
                # ✅ OBTENER MENSAJES DEL THREAD usando send_request - CORREGIDO
                try:
                    # ✅ Usar ruta relativa - el cliente ya tiene el endpoint base configurado
                    if hasattr(use_client, '_config') and hasattr(use_client._config, 'api_version'):
                        api_version = use_client._config.api_version
                    else:
                        api_version = "2024-02-15-preview"

                    messages_url = f"threads/{thread_run.thread_id}/messages?api-version={api_version}"
                    
                    from azure.core.rest import HttpRequest as CoreHttpRequest
                    
                    request = CoreHttpRequest(
                        method="GET",
                        url=messages_url
                    )
                    
                    # send_request maneja automáticamente la autenticación
                    response = use_client.send_request(request, stream=False)
                    
                    if response.status_code != 200:
                        raise Exception(f"HTTP {response.status_code}: {response.text()[:200]}")
                    
                    messages_data = response.json()
                    messages_list = messages_data.get("data", [])
                        
                except Exception as messages_error:
                    print(f"   ❌ Error obteniendo mensajes: {messages_error}")
                    import traceback
                    traceback.print_exc()
                    raise Exception(f"No se pudieron recuperar mensajes: {messages_error}")
                
                # Encontrar respuesta del assistant
                output_text = ""
                
                for msg in messages_list:
                    role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
                    
                    if role == "assistant":
                        content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", [])
                        
                        for content_item in content:
                            if isinstance(content_item, dict):
                                if content_item.get("type") == "text":
                                    text_data = content_item.get("text", {})
                                    output_text = text_data.get("value", "") if isinstance(text_data, dict) else str(text_data)
                                    break
                            else:
                                if getattr(content_item, "type", None) == "text":
                                    text_obj = getattr(content_item, "text", None)
                                    if text_obj:
                                        output_text = getattr(text_obj, "value", str(text_obj))
                                        break
                        
                        if output_text:
                            break
                
                if not output_text:
                    print(f"   🔍 DEBUG: No se encontró respuesta")
                    if messages_list:
                        print(f"   📋 Total mensajes: {len(messages_list)}")
                        print(f"   📋 Primer mensaje: {messages_list[0]}")
                    raise Exception("No se encontró respuesta del assistant en los mensajes")
                
                print(f"   ✅ Respuesta obtenida: {len(output_text)} chars")
                
                # ✅ SIMULAR STREAMING
                lines = output_text.split('\n')
                for i, line in enumerate(lines):
                    words = line.split(' ')
                    for j, word in enumerate(words):
                        if word:
                            yield word + (" " if j < len(words) - 1 else "")
                            await asyncio.sleep(0.005)
                    if i < len(lines) - 1:
                        yield '\n'
                
                # Metadata final con usage del thread_run
                usage_info = {
                    "prompt_tokens": getattr(thread_run.usage, "prompt_tokens", 0) if hasattr(thread_run, "usage") and thread_run.usage else 0,
                    "completion_tokens": getattr(thread_run.usage, "completion_tokens", 0) if hasattr(thread_run, "usage") and thread_run.usage else 0,
                    "total_tokens": getattr(thread_run.usage, "total_tokens", 0) if hasattr(thread_run, "usage") and thread_run.usage else 0,
                    "cached_tokens": 0,
                    "reasoning_tokens": 0,
                    "models_used": [use_deployment],
                    "model": use_deployment
                }
                
                print(f"   ✅ Streaming completado: {len(output_text)} chars")
                print(f"   📊 Usage: {usage_info}")
                
                # ✅ CAPTURAR SUB-AGENTES DESDE RUN STEPS (Azure AI Projects)
                sub_agents_usage = []
                try:
                    print(f"      🔍 Capturando sub-agentes...")
                    
                    # Usar send_request para obtener los steps
                    steps_url = f"threads/{thread_run.thread_id}/runs/{thread_run.id}/steps?api-version={api_version}"
                    
                    from azure.core.rest import HttpRequest as CoreHttpRequest
                    
                    steps_request = CoreHttpRequest(
                        method="GET",
                        url=steps_url
                    )
                    
                    steps_response = use_client.send_request(steps_request, stream=False)
                    
                    if steps_response.status_code == 200:
                        steps_data = steps_response.json()
                        steps_list = steps_data.get("data", [])
                        
                        for i, step in enumerate(steps_list):
                            step_usage = step.get("usage")
                            step_details = step.get("step_details", {})
                            
                            if step_details:
                                tool_calls = step_details.get("tool_calls", [])

                                if tool_calls:
                                    for j, tool_call in enumerate(tool_calls):
                                        tool_type = tool_call.get("type", "unknown")
                                        tool_id = tool_call.get("id", "unknown")
                                        
                                        # Crear sub_agent_info
                                        sub_agent_info = {
                                            "tool_type": tool_type,
                                            "tool_id": tool_id
                                        }
                                        
                                        # Solo agregar modelo si NO es connected_agent
                                        if tool_type != "connected_agent":
                                            sub_agent_info["model"] = use_deployment
                                        
                                        # 🔍 INTENTAR MÚLTIPLES FUENTES PARA USAGE:
                                        # 1. Desde el tool_call
                                        # 2. Desde el step (si solo hay un tool_call)
                                        # 3. Desde connected_agent específico
                                        
                                        usage_found = False
                                        
                                        # Opción 1: Usage en tool_call
                                        if "usage" in tool_call and tool_call["usage"]:
                                            usage = tool_call["usage"]
                                            sub_agent_info["prompt_tokens"] = usage.get("prompt_tokens", 0)
                                            sub_agent_info["completion_tokens"] = usage.get("completion_tokens", 0)
                                            sub_agent_info["total_tokens"] = usage.get("total_tokens", 0)
                                            usage_found = True
                                        
                                        # Opción 2: Usage en step (si solo hay 1 tool_call en este step)
                                        elif step_usage and len(tool_calls) == 1:
                                            sub_agent_info["prompt_tokens"] = step_usage.get("prompt_tokens", 0)
                                            sub_agent_info["completion_tokens"] = step_usage.get("completion_tokens", 0)
                                            sub_agent_info["total_tokens"] = step_usage.get("total_tokens", 0)
                                            usage_found = True
                                        
                                        # Opción 3: Buscar en connected_agent object
                                        elif tool_type == "connected_agent" and "connected_agent" in tool_call:
                                            connected_agent_obj = tool_call.get("connected_agent", {})
                                            if "usage" in connected_agent_obj and connected_agent_obj["usage"]:
                                                usage = connected_agent_obj["usage"]
                                                sub_agent_info["prompt_tokens"] = usage.get("prompt_tokens", 0)
                                                sub_agent_info["completion_tokens"] = usage.get("completion_tokens", 0)
                                                sub_agent_info["total_tokens"] = usage.get("total_tokens", 0)
                                                usage_found = True
                                        
                                        if not usage_found:
                                            sub_agent_info["prompt_tokens"] = 0
                                            sub_agent_info["completion_tokens"] = 0
                                            sub_agent_info["total_tokens"] = 0
                                        
                                        # Agregar agent_name y recuperar modelo para connected_agent
                                        if tool_type == "connected_agent":
                                            connected_agent_obj = tool_call.get("connected_agent", {})
                                            print(f"         🔍 Procesando connected_agent: {connected_agent_obj}")
                                            agent_name = connected_agent_obj.get("name") or connected_agent_obj.get("agent_name")
                                            agent_id = connected_agent_obj.get("assistant_id")
                                            
                                            if agent_name:
                                                sub_agent_info["agent_name"] = agent_name
                                            
                                            # Recuperar modelo del subagente
                                            if agent_id:
                                                print(f"         🔍 Recuperando modelo del agent: {agent_id}")
                                                model = get_agent_model(use_client, agent_id, "azure_ai_projects")
                                                sub_agent_info["model"] = model
                                                print(f"         ✅ Modelo recuperado: {model}")
                                            else:
                                                sub_agent_info["model"] = "unknown_model"
                                            
                                            if agent_name:
                                                sub_agent_info["agent_name"] = agent_name
                                        
                                        sub_agents_usage.append(sub_agent_info)
                    
                    else:
                        print(f"      ⚠️ Error obteniendo steps: HTTP {steps_response.status_code}")
                
                except Exception as steps_error:
                    print(f"      ⚠️ Error capturando sub-agentes: {steps_error}")
                
                # Resumen de sub-agentes
                if sub_agents_usage:
                    total_sub_tokens = sum(sa.get('total_tokens', 0) for sa in sub_agents_usage)
                    print(f"      ✅ {len(sub_agents_usage)} sub-agente(s) capturado(s) ({total_sub_tokens} tokens)")
                
                yield {
                    "type": "metadata",
                    "output_text": output_text,
                    "usage": usage_info,
                    "sub_agents_usage": sub_agents_usage  # ✅ INCLUIR SUB-AGENTES
                }
                
            except Exception as ai_projects_error:
                error_msg = f"Error en Azure AI Projects: {ai_projects_error}"
                print(f"   ❌ {error_msg}")
                import traceback
                traceback.print_exc()
                yield {
                    "type": "error",
                    "message": error_msg
                }
                return
        
        else:
            # ===== AZURE OPENAI (código original) =====
            print(f"   🤖 Usando Azure OpenAI Assistants API")
            
            # Crear thread
            thread = use_client.beta.threads.create()
            
            # Añadir mensaje
            use_client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=input.input_as_text
            )
            
            # ✅ INTENTAR STREAMING NATIVO
            try:
                # Crear stream
                stream = use_client.beta.threads.runs.create(
                    thread_id=thread.id,
                    assistant_id=assistant.id,
                    stream=True,
                    max_completion_tokens=16384
                )
                
                accumulated_text = ""
                usage_info = None
                run_id = None  # ✅ Capturar run_id para obtener steps después
                
                # ✅ PROCESAR EVENTOS DEL STREAM
                for event in stream:
                    event_type = getattr(event, 'event', 'unknown')
                    
                    if event_type == 'thread.message.delta':
                        try:
                            delta = event.data.delta
                            if hasattr(delta, 'content') and delta.content:
                                for content_block in delta.content:
                                    if hasattr(content_block, 'type') and content_block.type == 'text':
                                        if hasattr(content_block, 'text') and hasattr(content_block.text, 'value'):
                                            text_chunk = content_block.text.value
                                            accumulated_text += text_chunk
                                            yield text_chunk
                        except Exception as delta_error:
                            print(f"      ⚠️ Error procesando delta: {delta_error}")
                    
                    elif event_type == 'thread.run.completed':
                        print(f"      ✅ Run completado")
                        try:
                            # ✅ Capturar run_id
                            if hasattr(event.data, 'id'):
                                run_id = event.data.id
                            
                            if hasattr(event.data, 'usage') and event.data.usage:
                                usage_info = {
                                    "prompt_tokens": event.data.usage.prompt_tokens,
                                    "completion_tokens": event.data.usage.completion_tokens,
                                    "total_tokens": event.data.usage.total_tokens,
                                    "cached_tokens": 0,
                                    "reasoning_tokens": 0,
                                    "models_used": [use_deployment],
                                    "model": use_deployment
                                }
                        except Exception as usage_error:
                            print(f"      ⚠️ Error obteniendo usage: {usage_error}")
                    
                    elif event_type in ['thread.run.failed', 'thread.run.cancelled', 'thread.run.expired']:
                        error_msg = f"Run terminó con estado: {event_type}"
                        print(f"      ❌ {error_msg}")
                        yield {
                            "type": "error",
                            "message": error_msg
                        }
                        return
                
                print(f"   ✅ Streaming completado: {len(accumulated_text)} chars")
                
                # ✅ CAPTURAR SUB-AGENTES DESPUÉS DEL STREAMING
                sub_agents_usage = []
                if run_id:
                    try:
                        print(f"      🔍 Obteniendo steps del run para capturar sub-agentes...")
                        print(f"         Thread ID: {thread.id}")
                        print(f"         Run ID: {run_id}")
                        
                        run_steps = use_client.beta.threads.runs.steps.list(
                            thread_id=thread.id,
                            run_id=run_id
                        )
                        
                        print(f"      📊 Total steps encontrados: {len(run_steps.data)}")
                        
                        for i, step in enumerate(run_steps.data):
                            print(f"      📍 Step {i+1}: type={step.type}, status={step.status}")
                            print(f"         step_details type: {type(step.step_details)}")
                            print(f"         step_details attributes: {dir(step.step_details)}")
                            
                            if hasattr(step.step_details, 'tool_calls'):
                                tool_calls = step.step_details.tool_calls
                                print(f"         🔧 Tool calls encontrados: {len(tool_calls) if tool_calls else 0}")
                                
                                if tool_calls:
                                    for j, tool_call in enumerate(tool_calls):
                                        tool_type = getattr(tool_call, 'type', 'unknown')
                                        print(f"         🔹 Tool call {j+1}: type={tool_type}")
                                        print(f"            Attributes: {dir(tool_call)}")
                                        
                                        # ✅ CAPTURAR TODOS LOS TIPOS DE TOOL CALLS
                                        sub_agent_info = {
                                            "tool_type": tool_type,
                                            "tool_id": getattr(tool_call, 'id', 'unknown'),
                                            "model": use_deployment
                                        }
                                        
                                        # Intentar capturar tokens si existen
                                        if hasattr(tool_call, 'usage') and tool_call.usage:
                                            print(f"            ✅ Usage encontrado: {tool_call.usage}")
                                            sub_agent_info["prompt_tokens"] = getattr(tool_call.usage, 'prompt_tokens', 0)
                                            sub_agent_info["completion_tokens"] = getattr(tool_call.usage, 'completion_tokens', 0)
                                            sub_agent_info["total_tokens"] = getattr(tool_call.usage, 'total_tokens', 0)
                                        else:
                                            print(f"            ⚠️ No usage en tool_call")
                                            sub_agent_info["prompt_tokens"] = 0
                                            sub_agent_info["completion_tokens"] = 0
                                            sub_agent_info["total_tokens"] = 0
                                        
                                        # Agregar información específica por tipo
                                        if tool_type == 'file_search':
                                            sub_agent_info["description"] = "Vector Search en documentos"
                                        elif tool_type == 'code_interpreter':
                                            sub_agent_info["description"] = "Code Interpreter"
                                        elif tool_type == 'function':
                                            function_name = getattr(tool_call.function, 'name', 'unknown') if hasattr(tool_call, 'function') else 'unknown'
                                            sub_agent_info["description"] = f"Function: {function_name}"
                                            sub_agent_info["function_name"] = function_name
                                        
                                        sub_agents_usage.append(sub_agent_info)
                                        print(f"      🔗 Tool call detectado: {tool_type} ({sub_agent_info.get('total_tokens', 0)} tokens)")
                                else:
                                    print(f"         ℹ️ tool_calls está vacío")
                            else:
                                print(f"         ℹ️ step_details no tiene atributo 'tool_calls'")
                    
                    except Exception as sub_e:
                        print(f"      ⚠️ Error capturando sub-agentes: {sub_e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"      ⚠️ No se capturó run_id, no se pueden obtener sub-agentes")
                
                # ✅ RESUMEN DE SUB-AGENTES
                if sub_agents_usage:
                    total_sub_tokens = sum(sa.get('total_tokens', 0) for sa in sub_agents_usage)
                    print(f"      📊 Total sub-agentes: {len(sub_agents_usage)} llamadas ({total_sub_tokens} tokens)")
                
                yield {
                    "type": "metadata",
                    "output_text": accumulated_text,
                    "usage": usage_info or {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "cached_tokens": 0,
                        "reasoning_tokens": 0,
                        "models_used": [use_deployment],
                        "model": use_deployment
                    },
                    "sub_agents_usage": sub_agents_usage  # ✅ INCLUIR SUB-AGENTES
                }
                
            except Exception as stream_error:
                # ✅ FALLBACK: STREAMING SIMULADO
                print(f"   ⚠️ Streaming nativo no disponible: {stream_error}")
                print(f"   🔄 Usando streaming simulado...")
                
                run = use_client.beta.threads.runs.create(
                    thread_id=thread.id,
                    assistant_id=assistant.id,
                    max_completion_tokens=16384
                )
                
                max_wait = 120
                elapsed = 0
                while run.status in ['queued', 'in_progress', 'cancelling']:
                    time.sleep(1)
                    elapsed += 1
                    
                    if elapsed % 5 == 0:
                        print(f"   ⏳ Esperando... ({elapsed}s)")
                    
                    if elapsed > max_wait:
                        raise TimeoutError(f"Run excedió {max_wait}s")
                    
                    run = use_client.beta.threads.runs.retrieve(
                        thread_id=thread.id,
                        run_id=run.id
                    )
                
                if run.status != 'completed':
                    raise Exception(f"Run failed with status: {run.status}")
                
                messages = use_client.beta.threads.messages.list(
                    thread_id=thread.id,
                    order='desc',
                    limit=10
                )
                
                assistant_messages = [msg for msg in messages.data if msg.role == "assistant"]
                if not assistant_messages:
                    raise Exception("No response from assistant")
                
                output_text = ""
                for content in assistant_messages[0].content:
                    if content.type == 'text':
                        output_text += content.text.value
                
                # ✅ SIMULAR STREAMING
                # ✅ SIMULAR STREAMING - Preservando saltos de línea
                # Dividir solo por espacios, NO por \n
                lines = output_text.split('\n')
                for i, line in enumerate(lines):
                    words = line.split(' ')
                    for j, word in enumerate(words):
                        if word:  # Evitar palabras vacías
                            yield word + (" " if j < len(words) - 1 else "")
                            await asyncio.sleep(0.005)
                    # Añadir salto de línea después de cada línea (excepto la última)
                    if i < len(lines) - 1:
                        yield '\n'
                
                usage_info = {
                    "prompt_tokens": run.usage.prompt_tokens if hasattr(run, 'usage') and run.usage else 0,
                    "completion_tokens": run.usage.completion_tokens if hasattr(run, 'usage') and run.usage else 0,
                    "total_tokens": run.usage.total_tokens if hasattr(run, 'usage') and run.usage else 0,
                    "cached_tokens": 0,
                    "reasoning_tokens": 0,
                    "models_used": [use_deployment],
                    "model": use_deployment
                }
                
                # ✅ DETECTAR Y CAPTURAR USO DE SUB-AGENTES (TODOS LOS TOOL TYPES)
                sub_agents_usage = []
                try:
                    print(f"      🔍 Obteniendo steps del run para capturar sub-agentes...")
                    print(f"         Thread ID: {thread.id}")
                    print(f"         Run ID: {run.id}")
                    
                    run_steps = use_client.beta.threads.runs.steps.list(
                        thread_id=thread.id,
                        run_id=run.id
                    )
                    
                    print(f"      📊 Total steps encontrados: {len(run_steps.data)}")
                    
                    for i, step in enumerate(run_steps.data):
                        print(f"      📍 Step {i+1}: type={step.type}, status={step.status}")
                        print(f"         step_details type: {type(step.step_details)}")
                        print(f"         step_details attributes: {dir(step.step_details)}")
                        
                        if hasattr(step.step_details, 'tool_calls'):
                            tool_calls = step.step_details.tool_calls
                            print(f"         🔧 Tool calls encontrados: {len(tool_calls) if tool_calls else 0}")
                            
                            if tool_calls:
                                for j, tool_call in enumerate(tool_calls):
                                    tool_type = getattr(tool_call, 'type', 'unknown')
                                    print(f"         🔹 Tool call {j+1}: type={tool_type}")
                                    print(f"            Attributes: {dir(tool_call)}")
                                    
                                    # ✅ CAPTURAR TODOS LOS TIPOS DE TOOL CALLS
                                    sub_agent_info = {
                                        "tool_type": tool_type,
                                        "tool_id": getattr(tool_call, 'id', 'unknown'),
                                        "model": assistant_config.get("deployment", use_deployment) if assistant_config else use_deployment
                                    }
                                    
                                    # Intentar capturar tokens si existen
                                    if hasattr(tool_call, 'usage') and tool_call.usage:
                                        print(f"            ✅ Usage encontrado: {tool_call.usage}")
                                        sub_agent_info["prompt_tokens"] = getattr(tool_call.usage, 'prompt_tokens', 0)
                                        sub_agent_info["completion_tokens"] = getattr(tool_call.usage, 'completion_tokens', 0)
                                        sub_agent_info["total_tokens"] = getattr(tool_call.usage, 'total_tokens', 0)
                                    else:
                                        print(f"            ⚠️ No usage en tool_call")
                                        sub_agent_info["prompt_tokens"] = 0
                                        sub_agent_info["completion_tokens"] = 0
                                        sub_agent_info["total_tokens"] = 0
                                    
                                    # Agregar información específica por tipo
                                    if tool_type == 'file_search':
                                        sub_agent_info["description"] = "Vector Search en documentos"
                                    elif tool_type == 'code_interpreter':
                                        sub_agent_info["description"] = "Code Interpreter"
                                    elif tool_type == 'function':
                                        function_name = getattr(tool_call.function, 'name', 'unknown') if hasattr(tool_call, 'function') else 'unknown'
                                        sub_agent_info["description"] = f"Function: {function_name}"
                                        sub_agent_info["function_name"] = function_name
                                    elif tool_type == 'assistant':
                                        agent_id = tool_call.assistant.id if hasattr(tool_call, 'assistant') else 'unknown'
                                        sub_agent_info["agent_id"] = agent_id
                                        sub_agent_info["description"] = f"Assistant: {agent_id}"
                                        
                                        # Recuperar modelo del subagente
                                        if agent_id != 'unknown':
                                            print(f"         🔍 Recuperando modelo del assistant: {agent_id}")
                                            model = get_agent_model(use_client, agent_id, "azure")
                                            sub_agent_info["model"] = model
                                            print(f"         ✅ Modelo recuperado: {model}")
                                        else:
                                            sub_agent_info["model"] = "unknown_model"
                                    
                                    sub_agents_usage.append(sub_agent_info)
                                    print(f"      🔗 Tool call detectado: {tool_type} ({sub_agent_info.get('total_tokens', 0)} tokens)")
                            else:
                                print(f"         ℹ️ tool_calls está vacío")
                        else:
                            print(f"         ℹ️ step_details no tiene atributo 'tool_calls'")
                
                except Exception as sub_e:
                    print(f"      ⚠️ Error capturando sub-agentes: {sub_e}")
                    import traceback
                    traceback.print_exc()
                
                # ✅ RESUMEN DE SUB-AGENTES
                if sub_agents_usage:
                    total_sub_tokens = sum(sa.get('total_tokens', 0) for sa in sub_agents_usage)
                    print(f"      📊 Total sub-agentes: {len(sub_agents_usage)} llamadas ({total_sub_tokens} tokens)")
                
                yield {
                    "type": "metadata",
                    "output_text": output_text,
                    "usage": usage_info,
                    "sub_agents_usage": sub_agents_usage  # ✅ AGREGAR ARRAY DE SUB-AGENTES
                }
    
    except Exception as e:
        error_str = str(e)
        print(f"   ❌ Error en streaming workflow: {error_str}")
        import traceback
        traceback.print_exc()
        
        # Mensaje de error amigable
        if "401" in error_str or "Unauthorized" in error_str:
            friendly_error = (
                f"❌ Error de autenticación al ejecutar el assistant.\n"
                f"La API key configurada no es válida o ha expirado.\n"
                f"Por favor, actualiza la configuración del asistente '{assistant_key}' en blob storage."
            )
        else:
            friendly_error = f"Error en el workflow: {error_str}"
        
        yield {
            "type": "error",
            "message": f"Error en el workflow: {error_str}"
        }

# ===== FUNCIÓN DE CONVENIENCIA PARA LLAMADA DIRECTA =====
async def run_cvs_database_workflow(input: WorkflowInput):
    """Ejecuta el workflow con el asistente CVs Database"""
    async for chunk in run_workflow_streaming(
        input, 
        assistant_config=ASSISTANT_CONFIGS["cvs_database"],
        assistant_key="cvs_database",
        auto_detect=False
    ):
        yield chunk

async def run_csv_formatter_workflow(input: WorkflowInput):
    """Ejecuta el workflow con el asistente CSV Formatter"""
    async for chunk in run_workflow_streaming(
        input, 
        assistant_config=ASSISTANT_CONFIGS["csv_formatter"],
        assistant_key="csv_formatter",
        auto_detect=False
    ):
        yield chunk