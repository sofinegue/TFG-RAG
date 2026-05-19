"""
Generador de respuestas RAG para los tres casos de uso
Soporta dos modos:
  - 'gpt'       : Azure OpenAI + Azure Search (chunks en contexto)
  - 'assistant' : Azure AI Assistant / Agent Builder (file_search integrado)
                  Requiere que agent_builder_workflow esté disponible
"""
import os
import re
from typing import TypedDict, Optional, AsyncGenerator
from openai import AzureOpenAI
from src.config import config, safe_create_kwargs
from src.rag.handler import get_handler
# Importación opcional del Agent Builder workflow
try:
    from agent_builder_workflow import WorkflowInput, run_workflow_streaming
    _AGENT_BUILDER_AVAILABLE = True
except ImportError:
    _AGENT_BUILDER_AVAILABLE = False
def clean_citations(text: str) -> str:
    """Elimina citas de archivo generadas por Azure OpenAI (【…】)."""
    text = re.sub(r"【[^】]*】", "", text)
    text = re.sub(r"  +", " ", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    return text.strip()
class GeneratorState(TypedDict):
    query: str
    answer: str
    chunks_used: list[dict]
    chunks_retrieved: list[dict]
    metadata: dict
    user_id: str
    timestamps: dict[str, float]
    conversation_history: list[dict]
    rag_mode: str
    use_case: str
    language: str
    assistant_id: Optional[str]
    gpt_config: dict
class Generator:
    """Genera respuestas usando GPT+AzureSearch o Azure AI Assistants"""
    def __init__(self):
        self.config = config
        self.assistant_configs: dict = {}
        if _AGENT_BUILDER_AVAILABLE:
            self.assistant_configs = self._load_all_assistant_configs()
        print(f"   OK Generator inicializado (agent_builder={'disponible' if _AGENT_BUILDER_AVAILABLE else 'no disponible'})")
    # ------------------------------------------------------------------
    # Helpers de asistentes
    # ------------------------------------------------------------------
    def _load_all_assistant_configs(self) -> dict:
        """Carga configuraciones de asistentes desde blob storage (opcional)"""
        try:
            from src.services.azure_storage_service import (
                list_assistant_configs_from_blob,
                download_assistant_config_from_blob,
            )
            assistant_ids = list_assistant_configs_from_blob()
            system_keys = {"assistants", "validation_summary", "last_updated"}
            configs: dict = {}
            for aid in assistant_ids:
                if aid in system_keys:
                    continue
                try:
                    cfg = download_assistant_config_from_blob(aid)
                    if cfg:
                        configs[aid] = cfg
                except Exception:
                    pass
            print(f"   📦 {len(configs)} asistentes cargados desde blob storage")
            return configs
        except Exception as e:
            print(f"   ⚠️ No se pudieron cargar asistentes: {e}")
            return {}
    # ------------------------------------------------------------------
    # Generación principal (async)
    # ------------------------------------------------------------------
    async def generate_answer_with_context(
        self,
        query: str,
        conversation_history: list[dict] = None,
        chunks: list[dict] = None,
        rag_mode: str = "gpt",
        last_query: str = None,
        last_response: str = None,
        assistant_id: str = None,
        gpt_config: dict = None,
        use_case: str = "cvs",
        language: str = "es",
    ):
        """
        Genera respuesta y devuelve (answer: str, usage_info: dict)
        """
        gpt_config = gpt_config or {}
        # ── MODO ASSISTANT ──────────────────────────────────────────
        if rag_mode == "assistant":
            if not _AGENT_BUILDER_AVAILABLE:
                print("      ⚠️ Agent Builder no disponible, usando modo GPT como fallback")
                rag_mode = "gpt"
            else:
                return await self._generate_assistant(
                    query=query,
                    last_query=last_query,
                    last_response=last_response,
                    assistant_id=assistant_id,
                )
        # ── MODO GPT + AZURE SEARCH ──────────────────────────────────
        return await self._generate_gpt(
            query=query,
            chunks=chunks or [],
            conversation_history=conversation_history or [],
            last_query=last_query,
            last_response=last_response,
            gpt_config=gpt_config,
            use_case=use_case,            language=language,        )
    # ------------------------------------------------------------------
    # GPT interno
    # ------------------------------------------------------------------
    async def _generate_gpt(
        self,
        query: str,
        chunks: list[dict],
        conversation_history: list[dict],
        last_query: str,
        last_response: str,
        gpt_config: dict,
        use_case: str,
        language: str = "es",
    ):
        print(f"      🔧 Generando con GPT [{use_case}]...")
        handler  = get_handler(use_case)
        llm_cfg  = handler.get_llm_config()
        # gpt_config (enviado por el cliente) tiene prioridad sobre los defaults del handler
        model_name        = gpt_config.get("model")        or llm_cfg.get("model",             config.chat_model)
        temperature       = gpt_config.get("temperature",       llm_cfg.get("temperature",       config.temperature))
        max_tokens        = gpt_config.get("max_tokens",        llm_cfg.get("max_tokens",        config.max_tokens))
        top_p             = gpt_config.get("top_p",             llm_cfg.get("top_p",             0.95))
        frequency_penalty = gpt_config.get("frequency_penalty", llm_cfg.get("frequency_penalty", 0.0))
        presence_penalty  = gpt_config.get("presence_penalty",  llm_cfg.get("presence_penalty",  0.0))
        max_chunks        = gpt_config.get("max_chunks_used",   config.max_chunks_used)
        try:
            chat_cfg = config.get_model_config(model_name)
        except ValueError:
            chat_cfg = config.get_chat_model_config()
        client = AzureOpenAI(
            api_key=chat_cfg.api_key,
            api_version=chat_cfg.api_version,
            azure_endpoint=chat_cfg.api_base,
        )
        # system_message: custom_prompt del cliente > system message del handler
        system_message = gpt_config.get("prompt") or handler.get_system_message()
        rag_prompt = handler.build_generation_prompt(
            query=query,
            context=chunks[:max_chunks],
            max_chars=config.max_answer_chars,
            language=language,
        )
        messages = [{"role": "system", "content": system_message}]
        if last_query and last_response:
            messages.append({"role": "user",      "content": last_query[:500]})
            messages.append({"role": "assistant", "content": last_response[:500]})
        messages.append({"role": "user", "content": rag_prompt})
        response = client.chat.completions.create(
            **safe_create_kwargs(
                model=chat_cfg.deployment,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
            )
        )
        raw_answer = response.choices[0].message.content
        answer     = handler.post_process_answer(raw_answer)
        usage      = response.usage
        usage_info = {
            "prompt_tokens":     usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens":      usage.total_tokens,
            "cached_tokens":     getattr(usage, "cached_tokens", 0),
            "model":             chat_cfg.deployment,
        }
        print(f"      ✅ Respuesta generada ({len(answer)} chars, {usage.total_tokens} tokens)")
        return answer, usage_info
    # ------------------------------------------------------------------
    # Azure AI Assistant / Agent Builder
    # ------------------------------------------------------------------
    async def _generate_assistant(
        self,
        query: str,
        last_query: str,
        last_response: str,
        assistant_id: str,
    ):
        print(f"      🤖 Generando con Assistant [id={assistant_id}]...")
        query_with_context = query
        if last_query and last_response:
            query_with_context = (
                f"Consulta anterior: {last_query}\n"
                f"Respuesta anterior: {last_response}\n\n"
                f"Consulta actual: {query}"
            )
        assistant_config = self.assistant_configs.get(assistant_id) if assistant_id else None
        if not assistant_config and assistant_id:
            try:
                from src.services.azure_storage_service import download_assistant_config_from_blob
                assistant_config = download_assistant_config_from_blob(assistant_id)
            except Exception:
                pass
        if not assistant_config:
            assistant_config = {
                "endpoint":        os.getenv("AZURE_OPENAI_AGENT_ENDPOINT"),
                "api_key":         os.getenv("AZURE_OPENAI_AGENT_API_KEY"),
                "deployment":      os.getenv("AZURE_OPENAI_AGENT_DEPLOYMENT"),
                "vector_store_id": os.getenv("AZURE_OPENAI_AGENT_VECTOR_STORE_ID"),
                "api_type":        "azure",
            }
        workflow_input = WorkflowInput(input_as_text=query_with_context)
        answer = ""
        usage_info = {}
        async for chunk in run_workflow_streaming(
            input=workflow_input,
            assistant_config=assistant_config,
            assistant_key=assistant_id,
            auto_detect=False,
        ):
            if isinstance(chunk, dict) and chunk.get("type") == "metadata":
                usage_info = chunk.get("usage", {})
            else:
                answer += chunk
        answer = clean_citations(answer) or "<p>⚠️ Sin respuesta del Assistant</p>"
        print(f"      ✅ Respuesta Assistant ({len(answer)} chars)")
        return answer, usage_info or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    # ------------------------------------------------------------------
    # Interfaz para LangGraph
    # ------------------------------------------------------------------
    async def generate(self, state: GeneratorState) -> GeneratorState:
        """Nodo async para LangGraph"""
        rag_mode = state.get("rag_mode", "gpt")
        use_case = state.get("use_case", "cvs")
        # Recuperar último par Q&A del historial para contexto conversacional
        history = state.get("conversation_history", [])
        last_query = last_response = None
        for i in range(len(history) - 1, 0, -1):
            if history[i]["role"] == "assistant" and history[i - 1]["role"] == "user":
                last_query    = history[i - 1]["content"]
                last_response = history[i]["content"]
                break
        try:
            answer, usage_info = await self.generate_answer_with_context(
                query=state["query"],
                conversation_history=history,
                chunks=state.get("chunks_retrieved", []),
                rag_mode=rag_mode,
                last_query=last_query,
                last_response=last_response,
                assistant_id=state.get("assistant_id"),
                gpt_config=state.get("gpt_config", {}),
                use_case=use_case,
                language=state.get("language", "es"),
            )
            state["answer"]     = answer
            state["chunks_used"] = state.get("chunks_retrieved", [])
            state["metadata"]   = {
                "usage":   usage_info,
                "model":   usage_info.get("model", "unknown"),
                "use_case": use_case,
                "rag_mode": rag_mode,
            }
        except Exception as e:
            print(f"   ❌ Error en generate: {e}")
            import traceback; traceback.print_exc()
            state["error"]  = str(e)
            state["answer"] = f"<p>❌ Error generando respuesta: {e}</p>"
            state["metadata"] = {"usage": {}, "error": str(e)}
        return state
