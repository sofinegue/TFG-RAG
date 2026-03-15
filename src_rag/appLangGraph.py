"""
Orquestación del RAG usando LangGraph CON Agent Builder
Sistema híbrido: Azure Search (retrieval opcional) + Agent Builder (generación)
"""

import asyncio
from typing import TypedDict, List, Dict
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from models.generator import Generator
from models.retriever import Retriever
from guardrails import guardrails_manager, GuardRailsViolation
from config import config


class RAGState(TypedDict):
    """Estado global del grafo RAG"""
    # Input
    query: str
    user_id: str
    conversation_history: List[Dict]
    
    # Classification
    needs_context: bool
    use_retrieval: bool
    
    # Retrieval (opcional con Agent Builder)
    synthetic_queries: List[str]
    chunks_retrieved: List[Dict]
    
    # Generation
    answer: str
    chunks_used: list
    metadata: dict
    
    # Timestamps
    timestamps: dict
    
    # Control
    error: str
    
    # GuardRails (opcional)
    input_validation: Dict
    output_validation: Dict

    # RAG MODE
    rag_mode: str
    
    # ASSISTANT ID  # ✅ AGREGAR ESTA LÍNEA
    assistant_id: str  # ✅ AGREGAR ESTA LÍNEA
    
    # GPT CONFIG  # ✅ AÑADIR
    gpt_config: Dict  # ✅ AÑADIR

class RAGGraph:
    """
    Grafo RAG modular con Agent Builder
    
    Flujo:
    START → validate → [guardrails] → classify → [retrieve] → generate_async → END
    
    NOTA: El nodo 'generate' ahora es async porque usa Agent Builder
    """
    
    def __init__(self):
        print("🔧 Inicializando RAGGraph con Agent Builder...")
        self.generator = Generator()
        self.retriever = Retriever()
        self.graph = self._build_graph()
        print("✅ Grafo construido")
    
    def _build_graph(self) -> StateGraph:
        """
        Construye el grafo de estados con Agent Builder
        
        Flujo simplificado (sin guardrails opcionales):
        START → validate_input → classify_context → [retrieve] → generate → END
        """
        workflow = StateGraph(RAGState)
        
        # === NODOS ===
        workflow.add_node("validate_user_input", self.validate_user_input)
        workflow.add_node("classify_context", self.classify_context)
        workflow.add_node("retrieve", self.retrieve_chunks)
        workflow.add_node("generate", self.generate_answer_async)  # ✅ Wrapper async
        workflow.add_node("handle_error", self.handle_error)
        
        # === GUARDRAILS OPCIONALES ===
        if config.enable_input_guardrails:
            workflow.add_node("guardrails_input", self.check_input_guardrails)
        
        if config.enable_output_guardrails:
            workflow.add_node("guardrails_output", self.check_output_guardrails)
        
        # === ENTRY POINT ===
        workflow.set_entry_point("validate_user_input")
        
        # === EDGES CONDICIONALES ===
        workflow.add_conditional_edges(
            "validate_user_input",
            self.should_continue_after_validation,
            {
                "continue": "guardrails_input" if config.enable_input_guardrails else "classify_context",
                "error": "handle_error"
            }
        )
        
        if config.enable_input_guardrails:
            workflow.add_conditional_edges(
                "guardrails_input",
                self.should_continue_after_input_guardrails,
                {
                    "continue": "classify_context",
                    "error": "handle_error"
                }
            )
        
        workflow.add_conditional_edges(
            "classify_context",
            self.should_retrieve,
            {
                "retrieve": "retrieve",
                "generate": "generate"
            }
        )
        
        # === EDGES NORMALES ===
        workflow.add_edge("retrieve", "generate")
        
        if config.enable_output_guardrails:
            workflow.add_edge("generate", "guardrails_output")
            workflow.add_edge("guardrails_output", END)
        else:
            workflow.add_edge("generate", END)
        
        workflow.add_edge("handle_error", END)
        
        # === COMPILAR ===
        memory = MemorySaver()
        return workflow.compile(checkpointer=memory)
    
    # ========== NODOS DEL GRAFO ==========
    
    def validate_user_input(self, state: RAGState) -> RAGState:
        """Valida el input básico del usuario"""
        print(f"🔍 Validando input básico...")
        start_time = datetime.now()
        
        query = state.get("query", "").strip()
        
        if not query:
            state["error"] = "Query vacía"
            return state
        
        if len(query) < 2:
            state["error"] = "Query demasiado corta"
            return state
        
        if "timestamps" not in state:
            state["timestamps"] = {}
        
        state["timestamps"]["validation"] = (datetime.now() - start_time).total_seconds()
        
        print(f"   ✅ Input válido: {query[:50]}...")
        
        return state
    
    def check_input_guardrails(self, state: RAGState) -> RAGState:
        """Valida seguridad del input (opcional)"""
        if not config.enable_input_guardrails:
            print("   ⏭️  Input GuardRails desactivados")
            return state
        
        print(f"🛡️  Aplicando Input GuardRails...")
        start_time = datetime.now()
        
        try:
            is_safe, validation_result = guardrails_manager.validate_input(
                query=state["query"],
                user_id=state.get("user_id", "anonymous")
            )
            
            state["input_validation"] = validation_result
            
            if not is_safe:
                state["error"] = "input_violation"
                state["answer"] = self._get_violation_message(validation_result)
                print(f"      ❌ Input bloqueado: {validation_result.get('violations')}")
            else:
                if "sanitized_query" in validation_result:
                    state["query"] = validation_result["sanitized_query"]
                print(f"      ✅ Input aprobado")
            
            state["timestamps"]["input_guardrails"] = (datetime.now() - start_time).total_seconds()
            
        except GuardRailsViolation as e:
            state["error"] = "guardrails_violation"
            state["answer"] = f"<p>❌ Tu consulta no cumple con nuestras políticas de uso: {str(e)}</p>"
            print(f"      ❌ Violación detectada: {e}")
        
        return state
    
    def classify_context(self, state: RAGState) -> RAGState:
        """
        Clasifica si necesita retrieval de Azure Search
        
        - Assistant: NO usa Azure Search (tiene file_search integrado)
        - GPT interno: SÍ usa Azure Search
        """
        print("🔎 Clasificando necesidad de retrieval...")
        start_time = datetime.now()
        
        query = state["query"]
        rag_mode = state.get("rag_mode", "assistant")
        
        print(f"   🔍 Modo RAG detectado: {rag_mode}")
        
        # ✅ LÓGICA CONDICIONAL POR MODO
        if rag_mode == "assistant":
            # Assistant: NO retrieval de Azure Search
            state["needs_context"] = True
            state["use_retrieval"] = False
            mode_desc = "Assistant (file_search integrado)"
        
        else:
            # GPT interno: SÍ retrieval de Azure Search (siempre)
            state["needs_context"] = True
            state["use_retrieval"] = True
            mode_desc = "GPT + Azure Search"
        
        state["timestamps"]["classification"] = (datetime.now() - start_time).total_seconds()
        
        print(f"   🎯 Modo: {mode_desc}")
        print(f"   📊 Estado después de clasificación:")
        print(f"      needs_context: {state['needs_context']}")
        print(f"      use_retrieval: {state['use_retrieval']}")
        
        return state
    
    def retrieve_chunks(self, state: RAGState) -> RAGState:
        """
        Nodo de retrieval con Azure Search (opcional)
        
        Este retrieval es complementario al file_search del Agent Builder
        """
        print("📚 Recuperando chunks de Azure Search...")
        start_time = datetime.now()
        
        try:
            retriever_state = {
                "query": state["query"],
                "user_id": state["user_id"],
                "conversation_history": state.get("conversation_history", []),
                "chunks_retrieved": [],
                "synthetic_queries": [],
                "timestamps": {},
                "rag_mode": state.get("rag_mode", "agent")  # ✅ PASAR rag_mode
            }
            
            updated_retriever_state = self.retriever.retrieve(retriever_state)

            
            state["synthetic_queries"] = updated_retriever_state["synthetic_queries"]
            state["chunks_retrieved"] = updated_retriever_state["chunks_retrieved"]
            state["timestamps"]["retrieval"] = (datetime.now() - start_time).total_seconds()
            
            print(f"   ✅ {len(state['chunks_retrieved'])} chunks de Azure Search recuperados")
            
            return state
            
        except Exception as e:
            print(f"   ❌ Error en retrieval: {e}")
            state["chunks_retrieved"] = []
            state["synthetic_queries"] = []
            state["timestamps"]["retrieval"] = (datetime.now() - start_time).total_seconds()
            return state
    
    def generate_answer_async(self, state: RAGState) -> RAGState:
        """
        Wrapper SÍNCRONO que ejecuta código async de forma segura
        """
        print(f"   🎬 ENTRANDO A generate_answer_async")
        
        rag_mode = state.get("rag_mode", "assistant")
        mode_display = "Assistant" if rag_mode == "assistant" else "RAG Interno"
        
        print(f"🤖 Preparando generación con {mode_display}...")
        
        import concurrent.futures
        
        # ✅ Copiar state para evitar problemas de threading
        state_copy = dict(state)  # Convertir TypedDict a dict normal
        
        def run_async_in_thread():
            """Ejecuta código async en un nuevo event loop"""
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                # ✅ Definir función async DENTRO del loop
                async def run():
                    return await self._generate_async(state_copy)
                
                # Ejecutar la función async
                result = new_loop.run_until_complete(run())
                return result
            finally:
                new_loop.close()
        
        # Ejecutar en thread separado
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_async_in_thread)
            result = future.result()
        
        # ✅ Actualizar state original con resultado
        for key, value in result.items():
            state[key] = value
        
        return state
    
    async def _generate_async(self, state: RAGState) -> RAGState:
        """
        Genera respuesta usando Assistant O GPT según el modo
        
        Esta es la función que realmente llama al generador
        """
        rag_mode = state.get("rag_mode", "assistant")
        
        print(f"🧠 Ejecutando generador en modo: {rag_mode.upper()}")
        start_time = datetime.now()
        
        try:
            history_to_use = (
                state["conversation_history"] 
                if state.get("needs_context", True) 
                else []
            )
            
            # ✅ DEBUG: Ver qué hay en el state antes de crear gen_state
            print(f"   🔍 DEBUG _generate_async:")
            print(f"      assistant_id en state: '{state.get('assistant_id')}'")
            
            gen_state = {
                "query": state["query"],
                "user_id": state["user_id"],
                "conversation_history": history_to_use,
                "chunks_retrieved": state.get("chunks_retrieved", []),
                "answer": "",
                "chunks_used": [],
                "metadata": {},
                "timestamps": {},
                "rag_mode": rag_mode,
                "assistant_id": state.get("assistant_id"),
                "gpt_config": state.get("gpt_config", {})  # ✅ AÑADIR
            }
            
            # ✅ DEBUG: Confirmar que se agregó
            print(f"      assistant_id en gen_state: '{gen_state.get('assistant_id')}'")
            
            # ✅ AWAIT el generador async CON rag_mode Y assistant_id
            updated_state = await self.generator.generate(gen_state)
            
            # ✅ Actualizar estado
            state["answer"] = updated_state["answer"]
            state["chunks_used"] = updated_state.get("chunks_used", [])
            state["metadata"] = updated_state["metadata"]
            state["timestamps"]["generation"] = (datetime.now() - start_time).total_seconds()
            
            # ✅ Metadata adicional
            state["metadata"]["used_context"] = state.get("needs_context", True)
            state["metadata"]["used_retrieval"] = state.get("use_retrieval", False)
            state["metadata"]["chunks_retrieved"] = len(state.get("chunks_retrieved", []))
            
            print(f"   ✅ Respuesta generada: {len(state['answer'])} chars")
            print(f"   📊 Modelo: {state['metadata'].get('model', 'unknown')}")
            
            return state
            
        except Exception as e:
            print(f"   ❌ Error en generación: {str(e)}")
            import traceback
            traceback.print_exc()
            state["error"] = f"Error en generación: {str(e)}"
            return state
    
    def check_output_guardrails(self, state: RAGState) -> RAGState:
        """Valida calidad/seguridad del output (opcional)"""
        if not config.enable_output_guardrails:
            print("   ⏭️  Output GuardRails desactivados")
            return state
        
        print(f"🛡️  Aplicando Output GuardRails...")
        start_time = datetime.now()
        
        try:
            is_compliant, validation_result = guardrails_manager.validate_output(
                answer=state["answer"],
                query=state["query"],
                chunks_used=state.get("chunks_used", []),
                metadata=state.get("metadata", {})
            )
            
            state["output_validation"] = validation_result
            
            # Usar respuesta mejorada (con disclaimers, etc.)
            if "enhanced_answer" in validation_result:
                state["answer"] = validation_result["enhanced_answer"]
            
            if not is_compliant:
                print(f"      ⚠️  Issues detectados: {validation_result.get('issues')}")
            else:
                print(f"      ✅ Output aprobado")
            
            state["timestamps"]["output_guardrails"] = (datetime.now() - start_time).total_seconds()
            
        except Exception as e:
            print(f"      ⚠️  Error en output guardrails: {e}")
        
        # ✅ Calcular tiempo total
        state["timestamps"]["total"] = sum(state["timestamps"].values())
        
        return state
    
    def handle_error(self, state: RAGState) -> RAGState:
        """Maneja errores del grafo"""
        error_msg = state.get("error", "Error desconocido")
        print(f"⚠️  Manejando error: {error_msg}")
        
        if not state.get("answer"):
            state["answer"] = f"<p>Lo siento, ocurrió un error: {error_msg}</p>"
        
        state["chunks_used"] = []
        
        if "metadata" not in state:
            state["metadata"] = {}
        
        state["metadata"]["error"] = error_msg
        
        return state
    
    # ========== CONDICIONALES ==========
    
    def should_continue_after_validation(self, state: RAGState) -> str:
        """Decide si continuar después de validación básica"""
        return "error" if state.get("error") else "continue"
    
    def should_continue_after_input_guardrails(self, state: RAGState) -> str:
        """Decide si continuar después de guardrails de input"""
        if state.get("error") in ["input_violation", "guardrails_violation"]:
            return "error"
        return "continue"
    
    def should_retrieve(self, state: RAGState) -> str:
        """
        Decide si hacer retrieval de Azure Search o ir directo a Assistant
        
        Con Assistant, vamos directo a 'generate'
        """
        use_retrieval = state.get("use_retrieval", False)
        decision = "retrieve" if use_retrieval else "generate"
        
        print(f"   🔀 Decisión de flujo:")
        print(f"      use_retrieval: {use_retrieval}")
        print(f"      → Ir a: {decision}")
        
        return decision
    
    # ========== HELPERS ==========
    
    def _get_violation_message(self, validation_result: Dict) -> str:
        """Genera mensaje amigable de violación de guardrails"""
        violations = validation_result.get("violations", [])
        
        messages = {
            "prompt_injection": "Detectamos un intento de manipulación. Por favor, reformula tu pregunta de manera natural.",
            "content_moderation": "Tu mensaje contiene contenido inapropiado. Por favor, reformula tu pregunta.",
            "suspicious_keywords": "Tu mensaje contiene términos que no podemos procesar. Por favor, reformula.",
            "excessive_length": "Tu mensaje es demasiado largo. Por favor, acorta tu pregunta."
        }
        
        for violation in violations:
            if violation in messages:
                return f"<p>❌ {messages[violation]}</p>"
        
        return "<p>❌ Tu consulta no cumple con nuestras políticas de uso. Por favor, reformula.</p>"
    
    # ========== INTERFAZ PÚBLICA ==========
    
    def run(
        self,
        query: str,
        user_id: str = "anonymous",
        conversation_history: List[Dict] = None,
        rag_mode: str = "assistant",
        assistant_id: str = None,
        gpt_config: Dict = None  # ✅ AÑADIR
    ) -> Dict:
        """
        Ejecuta el pipeline RAG completo con Agent Builder
        
        Args:
            query: Pregunta del usuario
            user_id: Identificador del usuario
            conversation_history: Historial de la conversación
            rag_mode: Modo de RAG ("assistant" o "gpt")
            assistant_id: ID del asistente a usar (para modo assistant)
            
        Returns:
            dict con answer, chunks_used, metadata, timestamps, etc.
        """
        # ✅ MENSAJE CONDICIONAL SEGÚN MODO
        mode_display = "Assistant" if rag_mode == "assistant" else "RAG Interno"
        
        # ✅ LOG DE DEBUG - VER VALOR REAL
        print(f"   🔧 rag_mode recibido: '{rag_mode}'")
        if assistant_id:
            print(f"   🤖 assistant_id recibido: '{assistant_id}'")

        print(f"\n{'='*60}")
        print(f"🚀 Ejecutando RAG con {mode_display}")
        print(f"   Query: {query[:50]}{'...' if len(query) > 50 else ''}")
        print(f"   User: {user_id}")
        print(f"{'='*60}")
        
        # ✅ INICIAR TIMER GLOBAL
        start_time_total = datetime.now()
        
        initial_state = RAGState(
            query=query,
            user_id=user_id,
            answer="",
            chunks_used=[],
            chunks_retrieved=[],
            synthetic_queries=[],
            metadata={},
            timestamps={},
            error="",
            conversation_history=conversation_history or [],
            needs_context=False,
            use_retrieval=False,
            input_validation={},
            output_validation={},
            rag_mode=rag_mode,
            assistant_id=assistant_id,
            gpt_config=gpt_config or {}  # ✅ AÑADIR
        )
        
        try:
            final_state = self.graph.invoke(
                initial_state,
                config={"configurable": {"thread_id": user_id}}
            )
            
            # ✅ CALCULAR TIEMPO TOTAL
            total_time = (datetime.now() - start_time_total).total_seconds()
            final_state["timestamps"]["total"] = total_time
            
            print("✅ Grafo completado exitosamente")
            print(f"   Tiempo total: {total_time:.2f}s")
            print(f"{'='*60}\n")
            
            # ✅ Añadir info de guardrails al metadata (si está habilitado)
            if config.enable_input_guardrails and "input_validation" in final_state:
                final_state["metadata"]["input_validation"] = {
                    "risk_level": final_state["input_validation"].get("risk_level", "low"),
                    "violations": final_state["input_validation"].get("violations", [])
                }
            
            if config.enable_output_guardrails and "output_validation" in final_state:
                final_state["metadata"]["output_validation"] = {
                    "issues": final_state["output_validation"].get("issues", []),
                    "risk_level": final_state["output_validation"].get("risk_level", "low")
                }
            
            return final_state
            
        except Exception as e:
            print(f"❌ Error crítico en el grafo: {str(e)}")
            import traceback
            traceback.print_exc()
            print(f"{'='*60}\n")
            
            # ✅ CALCULAR TIEMPO TOTAL INCLUSO EN ERROR
            total_time = (datetime.now() - start_time_total).total_seconds()
            
            return {
                "query": query,
                "user_id": user_id,
                "answer": f"<p>❌ Error crítico: {str(e)}</p>",
                "chunks_used": [],
                "chunks_retrieved": [],
                "synthetic_queries": [],
                "metadata": {
                    "error": str(e),
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                },
                "timestamps": {"total": total_time},
                "error": str(e),
                "conversation_history": conversation_history or [],
                "needs_context": False,
                "use_retrieval": False,
                "input_validation": {},
                "output_validation": {},
                "rag_mode": rag_mode,
                "assistant_id": assistant_id,
                "gpt_config": gpt_config or {}  # ✅ AÑADIR
            }
    
    def stream(
        self, 
        query: str, 
        user_id: str = "anonymous",
        conversation_history: List[Dict] = None
    ):
        """
        Ejecuta el grafo en modo streaming (para debugging)
        
        Yields:
            Estados intermedios del grafo
        """
        print(f"\n{'='*60}")
        print(f"🌊 Ejecutando RAG en modo streaming")
        print(f"{'='*60}")
        
        initial_state = RAGState(
            query=query,
            user_id=user_id,
            answer="",
            chunks_used=[],
            chunks_retrieved=[],
            synthetic_queries=[],
            metadata={},
            timestamps={},
            error="",
            conversation_history=conversation_history or [],
            needs_context=False,
            use_retrieval=False,
            input_validation={},
            output_validation={}
        )
        
        for state in self.graph.stream(
            initial_state,
            config={"configurable": {"thread_id": user_id}}
        ):
            yield state
    
    def visualize(self, output_path: str = "rag_graph.png"):
        """
        Genera visualización del grafo (requiere graphviz)
        
        Args:
            output_path: Ruta donde guardar la imagen
        """
        try:
            from IPython.display import Image, display
            
            graph_image = self.graph.get_graph().draw_mermaid_png()
            
            with open(output_path, "wb") as f:
                f.write(graph_image)
            
            print(f"✅ Grafo guardado en: {output_path}")
            
            try:
                display(Image(graph_image))
            except:
                print("   (Para ver la imagen, abre el archivo generado)")
                
        except ImportError:
            print("⚠️  Para visualizar el grafo, instala: pip install graphviz")
        except Exception as e:
            print(f"❌ Error al visualizar: {e}")


# ========== INSTANCIA GLOBAL ==========

print("📄 Creando instancia global de RAGGraph con Agent Builder...")
rag_graph = RAGGraph()
print("✅ RAGGraph listo para usar\n")