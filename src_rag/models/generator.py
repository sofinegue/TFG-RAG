"""
Módulo de Generación usando Agent Builder de OpenAI O GPT interno
Genera respuestas usando el workflow de Agent Builder con file search integrado
O usando GPT con Azure Search
"""

from pyexpat.errors import messages
from typing import List, Dict, TypedDict
from config import config
from prompts.promptTemplates import PromptTemplates
import os
from typing import AsyncGenerator, Union
import re


# ✅ IMPORTAR EL WORKFLOW DEL AGENT BUILDER
from agent_builder_workflow import WorkflowInput, run_workflow_streaming


class GeneratorState(TypedDict):
    """Estado del generador para LangGraph"""
    query: str
    answer: str
    chunks_used: List[Dict]
    chunks_retrieved: List[Dict]
    metadata: Dict
    user_id: str
    timestamps: Dict[str, float]
    conversation_history: List[Dict]
    rag_mode: str
    gpt_config: Dict  # ✅ AÑADIR

def clean_citations(text: str) -> str:
        """Elimina las citas de archivo que genera Azure OpenAI."""
        # Elimina patrones como 【4:2†archivo.txt】
        text = re.sub(r'【[^】]*】', '', text)
        # Elimina espacios dobles que puedan quedar
        text = re.sub(r'  +', ' ', text)
        # Elimina espacios antes de puntuación
        text = re.sub(r'\s+([.,;:!?])', r'\1', text)
        return text.strip()

def _format_csv_output(text: str) -> str:
    """
    Post-procesa la salida CSV preservando el formato ROW X: del asistente
    
    Args:
        text: Texto original del asistente
        
    Returns:
        Texto formateado con mejor separación visual
    """
    import re
    
    # Si ya tiene el formato correcto con ---ROW, devolver sin cambios
    if "---ROW" in text:
        return text
    
    # Detectar si es una respuesta CSV (tiene múltiples punto y coma)
    if text.count(';') < 5:
        return text  # No es CSV, devolver sin cambios
    
    print("      🔧 Aplicando post-procesamiento CSV...")
    
    # ✅ REMOVER SOLO TEXTO INTRODUCTORIO (antes del primer ROW)
    lines = text.split('\n')
    
    # Buscar la primera línea que contiene "ROW"
    first_row_index = -1
    for i, line in enumerate(lines):
        if re.match(r'^\s*ROW\s+\d+\s*:', line, re.IGNORECASE):
            first_row_index = i
            break
    
    if first_row_index > 0:
        print(f"      📝 Eliminando {first_row_index} líneas de introducción")
        lines = lines[first_row_index:]
    elif first_row_index == -1:
        # No tiene formato ROW X:, buscar primera línea CSV
        print("      ⚠️ No se detectó formato ROW X:, buscando CSV directo...")
        for i, line in enumerate(lines):
            if ';' in line and line.count(';') >= 3:
                first_row_index = i
                break
        
        if first_row_index > 0:
            lines = lines[first_row_index:]
    
    # ✅ AÑADIR SEPARADORES VISUALES SIN MODIFICAR EL CONTENIDO
    formatted = []
    formatted.append("\n📊 **CV en formato CSV - Copia cada fila individualmente:**\n")
    formatted.append("💡 Formato ROW X: seguido del contenido CSV\n")
    formatted.append("=" * 80 + "\n\n")
    
    # Procesar líneas manteniendo el formato original
    current_row_label = None
    row_count = 0
    
    for line in lines:
        stripped = line.strip()
        
        # Detectar etiqueta ROW X:
        row_match = re.match(r'^(ROW\s+\d+)\s*:\s*(.*)$', stripped, re.IGNORECASE)
        
        if row_match:
            row_label = row_match.group(1).upper()
            row_content = row_match.group(2).strip()
            
            # Si había contenido anterior, añadir salto de línea
            if current_row_label and formatted[-1] != '\n':
                formatted.append('\n')
            
            # Añadir separador visual
            formatted.append(f"---{row_label}---\n")
            
            # Si hay contenido en la misma línea, añadirlo
            if row_content:
                if row_content == '[Fila vacía]' or re.match(r'^;+$', row_content):
                    formatted.append("[Fila vacía]\n")
                else:
                    formatted.append(f"{row_content}\n")
            
            current_row_label = row_label
            row_count += 1
        
        elif current_row_label and stripped:
            # Contenido que pertenece a la fila actual
            if stripped == '[Fila vacía]' or re.match(r'^;+$', stripped):
                formatted.append("[Fila vacía]\n")
            else:
                formatted.append(f"{stripped}\n")
        
        elif not stripped:
            # Línea vacía - mantener separación
            if formatted and formatted[-1] != '\n':
                formatted.append('\n')
    
    # Footer
    formatted.append("\n" + "=" * 80 + "\n")
    formatted.append(f"✅ Total: {row_count} filas CSV\n")
    formatted.append(f"💡 Para importar en Excel: Selecciona el contenido → Copia → Pega en Excel → Datos → Texto en columnas → Delimitado → Punto y coma\n")
    
    result = ''.join(formatted)
    print(f"      ✅ Procesadas {row_count} filas CSV")
    
    return result

class Generator:
    """
    Generador usando Agent Builder O GPT interno
    """
    
    def __init__(self):
        print("   📦 Inicializando Generator con modos híbridos...")
        self.config = config
        self.prompts = PromptTemplates()
        
        self.assistant_configs = self._load_all_assistant_configs()

        print("   ✓ Agent Builder workflow disponible")
        print("   ✓ GPT interno disponible")
    
    async def generate_answer_with_context(
        self, 
        query: str, 
        conversation_history: List[Dict] = None,
        chunks: List[Dict] = None,
        rag_mode: str = "assistant",
        last_query: str = None,
        last_response: str = None,
        assistant_id: str = None,
        gpt_config: Dict = None  # ✅ AÑADIR
    ) -> tuple[str, dict]:
        """
        Genera respuesta usando Agent Builder O GPT interno
        
        Returns:
            tuple[str, dict]: (respuesta, usage_info)
        """
        
        # ✅ MODO ASSISTANT
        if rag_mode == "assistant":
            print(f"      🤖 Generando con Azure Assistants...")
            
            # ✅ DEBUG: VER QUÉ LLEGA
            print(f"      🔍 DEBUG generate_answer_with_context:")
            print(f"         assistant_id recibido: '{assistant_id}'")
            print(f"         assistant_id is None: {assistant_id is None}")
            print(f"         Asistentes en self.assistant_configs: {list(self.assistant_configs.keys())}")
            print(f"         '{'propuestasEY'}' in configs: {'propuestasEY' in self.assistant_configs}")
            
            try:
                # Construir query con contexto
                query_with_context = query
                if last_query and last_response:
                    context_prefix = f"Consulta anterior: {last_query}\nRespuesta anterior: {last_response}\n\nConsulta actual: "
                    query_with_context = context_prefix + query
                    print(f"      📝 Usando contexto conversacional")
                
                # ✅ OBTENER CONFIGURACIÓN DEL ASISTENTE ESPECÍFICO
                assistant_config = None
                assistant_key = assistant_id  # Usar el ID del asistente
                
                print(f"      🔍 DEBUG antes de buscar config:")
                print(f"         assistant_id: '{assistant_id}'")
                print(f"         assistant_key: '{assistant_key}'")
                
                # ✅ INTENTAR OBTENER DESDE EL CACHÉ DE SELF (ya cargado en __init__)
                if assistant_id and assistant_id in self.assistant_configs:
                    assistant_config = self.assistant_configs[assistant_id]
                    print(f"      📦 Configuración obtenida del caché para asistente: {assistant_id}")
                    print(f"      🔍 api_type en config: {assistant_config.get('api_type')}")
                # ✅ FALLBACK: Intentar cargar desde blob si no está en caché
                elif assistant_id:
                    try:
                        from services.azure_storage_service import download_assistant_config_from_blob
                        assistant_config = download_assistant_config_from_blob(assistant_id)
                        print(f"      📦 Configuración cargada desde blob para asistente: {assistant_id}")
                    except Exception as e:
                        print(f"      ⚠️ No se pudo cargar config del asistente {assistant_id} desde blob: {e}")
                        assistant_config = None
                
                # ✅ ÚLTIMO FALLBACK: Usar variables de entorno genéricas
                if not assistant_config:
                    print(f"      ℹ️ Usando configuración por defecto de variables de entorno")
                    assistant_config = {
                        "endpoint": os.getenv("AZURE_OPENAI_AGENT_ENDPOINT"),
                        "api_key": os.getenv("AZURE_OPENAI_AGENT_API_KEY"),
                        "deployment": os.getenv("AZURE_OPENAI_AGENT_DEPLOYMENT"),
                        "vector_store_id": os.getenv("AZURE_OPENAI_AGENT_VECTOR_STORE_ID"),
                        "api_type": "azure",  # Por defecto
                        "prompt": None,
                        "temperature": 1.0,
                        "top_p": 1.0
                    }
                    assistant_key = None
                
                print(f"      📋 Configuración del asistente:")
                print(f"         Endpoint: {assistant_config.get('endpoint')}")
                print(f"         Deployment: {assistant_config.get('deployment')}")
                print(f"         Vector Store: {assistant_config.get('vector_store_id')}")
                print(f"         API Type: {assistant_config.get('api_type', 'azure')}")
                print(f"         Assistant Key: {assistant_key}")
                
                workflow_input = WorkflowInput(input_as_text=query_with_context)
                
                print(f"      🚀 Ejecutando workflow del Assistant...")
                
                # ✅ ACUMULAR RESULTADO DEL STREAMING
                answer = ""
                usage_info = {}
                sub_agents_usage = []  # ✅ CAPTURAR SUB-AGENTES
                
                # ✅ PASAR EL assistant_key CORRECTO
                async for chunk in run_workflow_streaming(
                    input=workflow_input,
                    assistant_config=assistant_config,
                    assistant_key=assistant_key,
                    auto_detect=False
                ):
                    if isinstance(chunk, dict):
                        # Metadata final
                        if chunk.get("type") == "metadata":
                            usage_info = chunk.get("usage", {})
                            sub_agents_usage = chunk.get("sub_agents_usage", [])  # ✅ CAPTURAR SUB-AGENTES
                    else:
                        # Texto
                        answer += chunk
                
                # Si no hay answer, devolver error
                if not answer:
                    answer = "<p>⚠️ No se recibió respuesta del Assistant</p>"
                answer = clean_citations(answer)
                # Construir usage_info si está vacío
                if not usage_info:
                    usage_info = {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "cached_tokens": 0,
                        "reasoning_tokens": 0,
                        "models_used": [],
                        "model": assistant_config.get('deployment', 'unknown')
                    }
                
                # ✅ AGREGAR SUB-AGENTES AL USAGE_INFO
                if sub_agents_usage:
                    usage_info["sub_agents_usage"] = sub_agents_usage
                    total_sub_tokens = sum(sa.get("total_tokens", 0) for sa in sub_agents_usage)
                    print(f"      🔗 Sub-agentes: {len(sub_agents_usage)} llamadas ({total_sub_tokens} tokens)")
                
                print(f"      ✅ Respuesta Assistant ({len(answer)} chars)")
                print(f"      🎫 Tokens: {usage_info.get('total_tokens', 0)}")
                
                return answer, usage_info
                
            except Exception as e:
                error_msg = f"❌ Error Assistant: {str(e)} \n"
                print(f"      ❌ Error: {str(e)}")
                import traceback
                traceback.print_exc()
                
                return error_msg, {
                    "prompt_tokens": 0, 
                    "completion_tokens": 0, 
                    "total_tokens": 0,
                    "cached_tokens": 0,
                    "reasoning_tokens": 0,
                    "models_used": [],
                    "error": str(e)
                }
        
        # ✅ MODO GPT INTERNO
        else:
            print(f"      🔧 Generando con RAG interno (GPT + Azure Search)...")
            
            try:
                from openai import AzureOpenAI
                
                # ✅ USAR CONFIGURACIÓN PERSONALIZADA O DEFAULTS
                if not isinstance(gpt_config, dict):
                    print(f"      ⚠️ gpt_config no es dict, es {type(gpt_config)}, usando dict vacío")
                    gpt_config = {}
                
                # Obtener modelo de la config o usar default
                model_name = gpt_config.get("model", config.chat_model)
                
                try:
                    chat_config = config.get_model_config(model_name)
                except ValueError:
                    print(f"      ⚠️ Modelo '{model_name}' no encontrado, usando default")
                    chat_config = config.get_chat_model_config()
                
                openai_client = AzureOpenAI(
                    api_key=chat_config.api_key,
                    api_version=chat_config.api_version,
                    azure_endpoint=chat_config.api_base
                )
                
                # ✅ PARÁMETROS PERSONALIZADOS
                temperature = gpt_config.get("temperature", config.temperature)
                max_tokens = gpt_config.get("max_tokens", config.max_tokens)
                top_p = gpt_config.get("top_p", 0.95)
                max_chunks = gpt_config.get("max_chunks_used", config.max_chunks_used)
                custom_prompt = gpt_config.get("prompt", "")
                verbosity = gpt_config.get("verbosity", "normal")
                frequency_penalty = gpt_config.get("frequency_penalty", 0)
                presence_penalty = gpt_config.get("presence_penalty", 0)
                
                print(f"      📋 Configuración GPT:")
                print(f"         Modelo: {chat_config.deployment}")
                print(f"         Temperature: {temperature}")
                print(f"         Max Tokens: {max_tokens}")
                print(f"         Max Chunks: {max_chunks}")
                print(f"         Verbosity: {verbosity}")
                
                # ✅ AJUSTAR INSTRUCCIONES SEGÚN VERBOSITY
                verbosity_instructions = {
                    "concise": "\n\nIMPORTANTE: Responde de forma breve y directa. Máximo 2-3 oraciones.",
                    "normal": "",
                    "detailed": "\n\nIMPORTANTE: Proporciona una respuesta completa y detallada con todos los detalles relevantes."
                }
                
                # Construir system message
                system_message = custom_prompt if custom_prompt else "Eres un asistente experto que responde preguntas basándose en el contexto proporcionado."
                system_message += verbosity_instructions.get(verbosity, "")
                
                # Pasar chunks directamente a rag_main_generation (no convertir a string)
                # Generar prompt
                prompt = self.prompts.rag_main_generation(
                    query=query,
                    context=chunks[:max_chunks] if chunks else [], 
                    max_chars=config.max_answer_chars
                )
                
                # Construir mensajes
                messages = [{"role": "system", "content": system_message}]
                
                if last_query and last_response:
                    messages.append({"role": "user", "content": last_query[:500]})
                    messages.append({"role": "assistant", "content": last_response[:500]})
                    print(f"      📝 Contexto conversacional añadido")
                
                messages.append({"role": "user", "content": prompt})
                
                print(f"      📤 Llamando a GPT...")
                
                # ✅ LLAMADA CON PARÁMETROS PERSONALIZADOS
                response = openai_client.chat.completions.create(
                    model=chat_config.deployment,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    frequency_penalty=frequency_penalty,
                    presence_penalty=presence_penalty
                )
                
                answer = response.choices[0].message.content
                usage = response.usage
                
                cached_tokens = 0
                if hasattr(usage, 'prompt_tokens_details') and usage.prompt_tokens_details:
                    cached_tokens = getattr(usage.prompt_tokens_details, 'cached_tokens', 0)
                
                usage_info = {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cached_tokens": cached_tokens,
                    "reasoning_tokens": 0,
                    "models_used": [chat_config.deployment],
                    "model": chat_config.deployment
                }
                
                print(f"      ✅ Respuesta GPT generada ({len(answer)} chars)")
                print(f"      🎫 Tokens: {usage_info['total_tokens']}")
                
                return answer, usage_info
                
            except Exception as e:
                error_msg = f"<p>❌ Error GPT interno: {str(e)}</p>"
                print(f"      ❌ Error: {str(e)}")
                import traceback
                traceback.print_exc()
                
                return error_msg, {
                    "prompt_tokens": 0, 
                    "completion_tokens": 0, 
                    "total_tokens": 0,
                    "cached_tokens": 0,
                    "reasoning_tokens": 0,
                    "models_used": [],
                    "model": chat_config.deployment if 'chat_config' in locals() else "unknown",
                    "error": str(e)
                }
    
    def _load_all_assistant_configs(self) -> Dict:
        """
        Obtiene las configuraciones de asistentes desde el caché centralizado de main.py
        """
        try:
            # Importar la función de caché centralizada
            from main import load_assistants_config
            
            # Obtener config desde caché (no fuerza recarga)
            cached_config = load_assistants_config(force_reload=False)
            
            if cached_config and "assistants" in cached_config:
                print(f"      ✅ Configs obtenidas desde caché centralizado: {len(cached_config['assistants'])} asistentes")
                return cached_config["assistants"]
            else:
                print("      ⚠️ Caché centralizado vacío, retornando dict vacío")
                return {}
                
        except ImportError as e:
            print(f"      ⚠️ No se pudo importar caché centralizado: {e}")
            # Fallback: retornar vacío (el sistema usará variables de entorno)
            return {}
        except Exception as e:
            print(f"      ⚠️ Error al obtener configs del caché: {e}")
            return {}
    
    def _fix_list_formatting(self, text: str) -> str:
        """
        Arregla el formato de listas que vienen del Assistant sin saltos de línea
        
        Transforma:
            "Item: - A - B - C"
        En:
            "Item:\n- A\n- B\n- C"
        """
        import re
        
        # Detectar listas con guiones pegados
        # Patrón: " - " seguido de texto (pero no al inicio de línea)
        text = re.sub(r'([^\n]) - ', r'\1\n- ', text)
        
        # Detectar listas numeradas pegadas
        # Patrón: " 1. " o " 2. " (pero no al inicio de línea)
        text = re.sub(r'([^\n]) (\d+)\. ', r'\1\n\2. ', text)
        
        # Limpiar múltiples saltos de línea consecutivos
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text
    
    async def stream_generate(
        self, 
        query: str, 
        conversation_history: List[Dict] = None,
        chunks: List[Dict] = None,
        rag_mode: str = "assistant",
        assistant_key: str = None,  # ✅ AÑADIDO
        last_query: str = None,
        last_response: str = None
    ) -> AsyncGenerator[Union[str, Dict], None]:
        """
        Genera respuesta en streaming
        
        Yields:
            str o dict: Fragmentos de texto o metadata final
        """
        try:
            print(f"      🌊 Iniciando streaming...")
            print(f"      🎯 Modo RAG: {rag_mode}")
            
            # ✅ MODO ASSISTANT
            if rag_mode == "assistant":
                try:
                    # ✅ CONSTRUIR CONTEXTO SI EXISTE
                    query_with_context = query
                    if last_query and last_response:
                        context_prefix = f"Consulta anterior: {last_query}\nRespuesta anterior: {last_response}\n\nConsulta actual: "
                        query_with_context = context_prefix + query
                        print(f"      📝 Usando contexto conversacional")
                        print(f"      📄 Contexto añadido: {context_prefix.strip()}")
                    
                    # ✅ OBTENER CONFIGURACIÓN DEL ASISTENTE DE LAS VARIABLES DE ENTORNO
                    assistant_config = {
                        "endpoint": os.getenv("AZURE_OPENAI_AGENT_ENDPOINT"),
                        "api_key": os.getenv("AZURE_OPENAI_AGENT_API_KEY"),
                        "deployment": os.getenv("AZURE_OPENAI_AGENT_DEPLOYMENT"),
                        "vector_store_id": os.getenv("AZURE_OPENAI_AGENT_VECTOR_STORE_ID"),
                        "prompt": None,  # Usar el prompt por defecto del asistente
                        "temperature": 1.0,
                        "top_p": 1.0
                    }
                    
                    print(f"      📋 Configuración del asistente:")
                    print(f"         Endpoint: {assistant_config['endpoint']}")
                    print(f"         Deployment: {assistant_config['deployment']}")
                    print(f"         Vector Store: {assistant_config['vector_store_id']}")
                    
                    # ✅ EJECUTAR WORKFLOW DE AGENT BUILDER
                    print(f"      ⚙️ Llamando a run_workflow_streaming...")
                    
                    workflow_input = WorkflowInput(input_as_text=query_with_context)
                    
                    # ✅ STREAMING DEL WORKFLOW CON LIMPIEZA DE CITAS
                    citation_buffer = ""

                    async for chunk in run_workflow_streaming(
                        input=workflow_input,
                        assistant_config=assistant_config,
                        assistant_key=assistant_key,
                        auto_detect=False
                    ):
                        if isinstance(chunk, dict):
                            # Antes de metadata, vaciar buffer si queda algo
                            if citation_buffer:
                                cleaned = clean_citations(citation_buffer)
                                if cleaned:
                                    yield cleaned
                                citation_buffer = ""
                            
                            # Metadata final
                            if chunk.get("type") == "metadata":
                                print(f"      ✅ Workflow completado")
                                yield chunk
                            elif chunk.get("type") == "error":
                                print(f"      ❌ Error en workflow: {chunk.get('message')}")
                                yield chunk
                        else:
                            # Fragmento de texto - acumular para manejar citas partidas
                            citation_buffer += chunk
                            
                            # Si hay corchete abierto sin cerrar, esperar más chunks
                            if '【' in citation_buffer and '】' not in citation_buffer.split('【')[-1]:
                                continue
                            
                            # Limpiar y enviar
                            cleaned = clean_citations(citation_buffer)
                            citation_buffer = ""
                            if cleaned:
                                yield cleaned
                    
                    return  # ✅ IMPORTANTE: salir después del assistant mode
                
                except Exception as e:
                    error_msg = f"Error en modo assistant: {str(e)}"
                    print(f"      ❌ {error_msg}")
                    import traceback
                    traceback.print_exc()
                    yield {"type": "error", "message": error_msg}
                    return
            
            # ✅ MODO GPT NORMAL (fallback) - CAMBIO: if en vez de elif
            if rag_mode in ["normal", "advanced"]:
                print(f"      🧠 Modo: GPT interno ({rag_mode})")
                
                # Construir contexto
                if chunks:
                    context = "\n\n".join([
                        f"Documento: {chunk.get('title', 'Sin título')}\n{chunk.get('content', '')}"
                        for chunk in chunks[:5]
                    ])
                else:
                    context = "No hay contexto adicional disponible."
                
                # Obtener prompt
                if rag_mode == "advanced":
                    prompt = self.prompts.rag_advanced_generation(
                        query=query,
                        context=context,
                        max_chars=config.max_answer_chars
                    )
                else:
                    prompt = self.prompts.rag_main_generation(
                        query=query,
                        context=context,
                        max_chars=config.max_answer_chars
                    )
                
                # Cliente OpenAI
                from openai import AzureOpenAI
                chat_config = config.get_chat_model_config()
                
                openai_client = AzureOpenAI(
                    api_key=chat_config.api_key,
                    api_version=chat_config.api_version,
                    azure_endpoint=chat_config.api_base
                )
                
                # Construir mensajes con historial
                messages = []
                
                # Agregar historial (últimos 5 mensajes)
                if last_query and last_response:
                    messages.append({"role": "user", "content": last_query[:500]})
                    messages.append({"role": "assistant", "content": last_response[:500]})
                    print(f"      📝 Contexto conversacional añadido")

                # Agregar prompt actual
                messages.append({"role": "user", "content": prompt})
                
                # ✅ STREAMING NATIVO DE GPT
                stream = openai_client.chat.completions.create(
                    model=chat_config.deployment,
                    messages=messages,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                    stream=True
                )
                
                accumulated_text = ""
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        text = chunk.choices[0].delta.content
                        accumulated_text += text
                        yield text
                
                # Metadata final
                yield {
                    "type": "metadata",
                    "output_text": accumulated_text,
                    "usage": {
                        "prompt_tokens": 0,  # No disponible en streaming
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "cached_tokens": 0,
                        "reasoning_tokens": 0,
                        "models_used": [chat_config.deployment],
                        "model": chat_config.deployment
                    }
                }
                return
            
            # Modo no soportado
            else:
                error_msg = f"Modo RAG '{rag_mode}' no soportado"
                print(f"      ❌ {error_msg}")
                yield {"type": "error", "message": error_msg}
                            
        except Exception as e:
            error_msg = f"❌ Error en streaming: {str(e)}"
            print(f"      {error_msg}")
            import traceback
            traceback.print_exc()
            yield {"type": "error", "message": error_msg}
    
    async def generate(self, state: GeneratorState) -> GeneratorState:
        """
        Función principal para LangGraph
        Ejecuta Assistant O GPT según el modo
        
        Args:
            state: Estado actual del grafo
            
        Returns:
            Estado actualizado con respuesta generada
        """
        query = state["query"]
        conversation_history = state.get("conversation_history", [])
        chunks = state.get("chunks_retrieved", [])
        rag_mode = state.get("rag_mode", "assistant")
        
        # ✅ OBTENER Y LIMPIAR ASSISTANT_ID DEL STATE
        assistant_id_raw = state.get("assistant_id")
        
        # ✅ VALIDAR: Convertir string "None" a None real
        if assistant_id_raw == "None" or assistant_id_raw == "" or assistant_id_raw is None:
            assistant_id = None
        else:
            assistant_id = assistant_id_raw
        
        # ✅ OBTENER GPT_CONFIG DEL STATE
        gpt_config = state.get("gpt_config", {})
        
        # ✅ Validar que gpt_config sea un diccionario
        if not isinstance(gpt_config, dict):
            print(f"   ⚠️ gpt_config no es dict, es {type(gpt_config)}, usando dict vacío")
            gpt_config = {}

        if gpt_config:
            print(f"   📋 GPT Config: {gpt_config.get('name', 'sin nombre')}")
        # ✅ DEBUG
        print(f"   🔍 DEBUG assistant_id:")
        print(f"      Raw: '{assistant_id_raw}' (type: {type(assistant_id_raw)})")
        print(f"      Limpio: '{assistant_id}' (type: {type(assistant_id)})")
        
        print(f"   🎯 Query: {query[:50]}...")
        print(f"   🔧 Modo: {rag_mode.upper()}")
        if assistant_id:
            print(f"   🤖 Assistant ID: {assistant_id}")
        
        # ✅ EXTRAER ÚLTIMA CONSULTA Y RESPUESTA
        last_query = None
        last_response = None
        if conversation_history and len(conversation_history) >= 2:
            # Buscar el último par usuario-asistente
            for i in range(len(conversation_history) - 1, 0, -1):
                if conversation_history[i]["role"] == "assistant" and conversation_history[i-1]["role"] == "user":
                    last_query = conversation_history[i-1]["content"]
                    last_response = conversation_history[i]["content"]
                    break
        
        # ✅ AWAIT con contexto incluido + ASSISTANT_ID LIMPIO + GPT_CONFIG
        answer, usage_info = await self.generate_answer_with_context(
            query, 
            conversation_history,
            chunks,
            rag_mode=rag_mode,
            last_query=last_query,
            last_response=last_response,
            assistant_id=assistant_id,
            gpt_config=gpt_config  # ✅ AÑADIR
        )
        
        # ✅ Determinar chunks usados (solo relevante en modo GPT)
        chunks_used = chunks[:config.max_chunks_used] if chunks and rag_mode == "gpt" else []
        
        # ✅ MODIFICADO: Metadata condicional según modo
        if rag_mode == "assistant":
            mode_name = "assistant_rag"
            deployment = usage_info.get("model") or os.getenv("AZURE_OPENAI_AGENT_DEPLOYMENT", "gpt-5-mini")
        else:
            mode_name = "gpt_internal_rag"
            deployment = config.chat_model
        
        # ✅ Incluir usage_info en metadata
        state["answer"] = answer
        state["chunks_used"] = chunks_used
        state["metadata"] = {
            "model": usage_info.get("model", deployment),
            "deployment": deployment,
            "mode": mode_name,
            "num_chunks_used": len(chunks_used),
            "num_chunks_available": len(chunks) if chunks else 0,
            "sources_from_assistant": len(usage_info.get("models_used", [])) if rag_mode == "assistant" else 0,
            "client": config.client_name,
            "context_messages": len(conversation_history) if conversation_history else 0,
            "usage": usage_info,
            "sub_agents_usage": usage_info.get("sub_agents_usage", [])  # ✅ EXTRAER SUB-AGENTES DEL USAGE_INFO
        }
        
        print(f"   ✅ Estado actualizado")
        print(f"   📊 Metadata: {state['metadata']['mode']}")
        
        return state