"""
Orquestación del RAG usando LangGraph – adaptado para tres casos de uso.
Flujo: validate → [guardrails_input] → classify → [retrieve] → generate → [guardrails_output] → END
"""
import asyncio
import concurrent.futures
from datetime import datetime
from typing import Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.config import config
from src.rag.models.generator import Generator
from src.rag.models.retriever import Retriever
from src.rag.guardrails import guardrails_manager, GuardRailsViolation


class RAGState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────
    query: str
    user_id: str
    use_case: str                     # "cvs" | "eu" | "wiki"
    conversation_history: List[Dict]

    # ── Clasificación ──────────────────────────────────────────────────
    needs_context: bool
    use_retrieval: bool

    # ── Retrieval ──────────────────────────────────────────────────────
    synthetic_queries: List[str]
    chunks_retrieved: List[Dict]

    # ── Generación ─────────────────────────────────────────────────────
    answer: str
    chunks_used: List[Dict]
    metadata: Dict
    timestamps: Dict

    # ── Control ────────────────────────────────────────────────────────
    error: str
    input_validation: Dict
    output_validation: Dict

    # ── Modo RAG ───────────────────────────────────────────────────────
    rag_mode: str           # "gpt" | "assistant"
    assistant_id: Optional[str]
    gpt_config: Dict


class RAGGraph:
    def __init__(self):
        print("🔧 Inicializando RAGGraph multi-caso-de-uso...")
        self.generator = Generator()
        self.retriever = Retriever()
        self.graph = self._build_graph()
        print("✅ RAGGraph listo")

    # ------------------------------------------------------------------
    # Construcción del grafo
    # ------------------------------------------------------------------
    def _build_graph(self) -> StateGraph:
        wf = StateGraph(RAGState)

        wf.add_node("validate_user_input", self.validate_user_input)
        wf.add_node("classify_context",    self.classify_context)
        wf.add_node("retrieve",            self.retrieve_chunks)
        wf.add_node("generate",            self.generate_answer_async)
        wf.add_node("handle_error",        self.handle_error)

        if config.enable_input_guardrails:
            wf.add_node("guardrails_input", self.check_input_guardrails)
        if config.enable_output_guardrails:
            wf.add_node("guardrails_output", self.check_output_guardrails)

        wf.set_entry_point("validate_user_input")

        after_validate = "guardrails_input" if config.enable_input_guardrails else "classify_context"
        wf.add_conditional_edges(
            "validate_user_input",
            self.should_continue_after_validation,
            {"continue": after_validate, "error": "handle_error"},
        )

        if config.enable_input_guardrails:
            wf.add_conditional_edges(
                "guardrails_input",
                self.should_continue_after_input_guardrails,
                {"continue": "classify_context", "error": "handle_error"},
            )

        wf.add_conditional_edges(
            "classify_context",
            self.should_retrieve,
            {"retrieve": "retrieve", "generate": "generate"},
        )

        wf.add_edge("retrieve", "generate")

        if config.enable_output_guardrails:
            wf.add_edge("generate", "guardrails_output")
            wf.add_edge("guardrails_output", END)
        else:
            wf.add_edge("generate", END)

        wf.add_edge("handle_error", END)

        memory = MemorySaver()
        return wf.compile(checkpointer=memory)

    # ------------------------------------------------------------------
    # Nodos
    # ------------------------------------------------------------------
    def validate_user_input(self, state: RAGState) -> RAGState:
        query = state.get("query", "").strip()
        if not query or len(query) < 2:
            state["error"] = "Query vacía o demasiado corta"
        if "timestamps" not in state:
            state["timestamps"] = {}
        return state

    def check_input_guardrails(self, state: RAGState) -> RAGState:
        try:
            is_safe, result = guardrails_manager.validate_input(
                query=state["query"], user_id=state.get("user_id", "anonymous")
            )
            state["input_validation"] = result
            if not is_safe:
                state["error"] = "input_violation"
                state["answer"] = self._violation_message(result)
            elif "sanitized_query" in result:
                state["query"] = result["sanitized_query"]
        except GuardRailsViolation as e:
            state["error"] = "guardrails_violation"
            state["answer"] = f"<p>❌ {e}</p>"
        return state

    def classify_context(self, state: RAGState) -> RAGState:
        rag_mode = state.get("rag_mode", "gpt")
        if rag_mode == "assistant":
            state["needs_context"]  = True
            state["use_retrieval"]  = False
        else:
            state["needs_context"]  = True
            state["use_retrieval"]  = True
        return state

    def retrieve_chunks(self, state: RAGState) -> RAGState:
        try:
            retriever_state = {
                "query":                state["query"],
                "use_case":             state.get("use_case", "cvs"),
                "user_id":              state["user_id"],
                "conversation_history": state.get("conversation_history", []),
                "chunks_retrieved":     [],
                "synthetic_queries":    [],
                "timestamps":           {},
                "rag_mode":             state.get("rag_mode", "gpt"),
            }
            updated = self.retriever.retrieve(retriever_state)
            state["synthetic_queries"] = updated["synthetic_queries"]
            state["chunks_retrieved"]  = updated["chunks_retrieved"]
        except Exception as e:
            print(f"   ❌ Error en retrieval: {e}")
            state["chunks_retrieved"]  = []
            state["synthetic_queries"] = []
        return state

    def generate_answer_async(self, state: RAGState) -> RAGState:
        """Wrapper síncrono que corre la generación async en un thread dedicado."""
        state_copy = dict(state)

        def run_in_new_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self._generate_async(state_copy))
            finally:
                loop.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            result = executor.submit(run_in_new_loop).result()

        for k, v in result.items():
            state[k] = v
        return state

    async def _generate_async(self, state: RAGState) -> RAGState:
        history = state.get("conversation_history", []) if state.get("needs_context", True) else []

        gen_state = {
            "query":                state["query"],
            "user_id":              state.get("user_id", "anonymous"),
            "conversation_history": history,
            "chunks_retrieved":     state.get("chunks_retrieved", []),
            "answer":               "",
            "chunks_used":          [],
            "metadata":             {},
            "timestamps":           {},
            "rag_mode":             state.get("rag_mode", "gpt"),
            "use_case":             state.get("use_case", "cvs"),
            "assistant_id":         state.get("assistant_id"),
            "gpt_config":           state.get("gpt_config", {}),
        }

        updated = await self.generator.generate(gen_state)
        state["answer"]     = updated["answer"]
        state["chunks_used"] = updated.get("chunks_used", [])
        state["metadata"]   = updated.get("metadata", {})
        state["metadata"].update({
            "used_context":     state.get("needs_context", True),
            "used_retrieval":   state.get("use_retrieval", False),
            "chunks_retrieved": len(state.get("chunks_retrieved", [])),
            "use_case":         state.get("use_case", "cvs"),
        })
        return state

    def check_output_guardrails(self, state: RAGState) -> RAGState:
        try:
            _, result = guardrails_manager.validate_output(
                answer=state["answer"],
                query=state["query"],
                chunks_used=state.get("chunks_used", []),
                metadata=state.get("metadata", {}),
            )
            state["output_validation"] = result
            if "enhanced_answer" in result:
                state["answer"] = result["enhanced_answer"]
        except Exception as e:
            print(f"   ⚠️ Output guardrails error: {e}")
        state["timestamps"]["total"] = sum(state.get("timestamps", {}).values())
        return state

    def handle_error(self, state: RAGState) -> RAGState:
        if not state.get("answer"):
            state["answer"] = f"<p>Lo siento, ocurrió un error: {state.get('error', 'desconocido')}</p>"
        state["chunks_used"] = []
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["error"] = state.get("error")
        return state

    # ------------------------------------------------------------------
    # Condicionales
    # ------------------------------------------------------------------
    def should_continue_after_validation(self, state: RAGState) -> str:
        return "error" if state.get("error") else "continue"

    def should_continue_after_input_guardrails(self, state: RAGState) -> str:
        return "error" if state.get("error") in ("input_violation", "guardrails_violation") else "continue"

    def should_retrieve(self, state: RAGState) -> str:
        return "retrieve" if state.get("use_retrieval", True) else "generate"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _violation_message(self, result: Dict) -> str:
        msgs = {
            "prompt_injection": "Detectamos un intento de manipulación. Por favor reformula tu pregunta.",
            "content_moderation": "Tu mensaje contiene contenido inapropiado.",
            "suspicious_keywords": "Tu mensaje contiene términos no permitidos.",
            "excessive_length": "Tu mensaje es demasiado largo.",
        }
        for v in result.get("violations", []):
            if v in msgs:
                return f"<p>❌ {msgs[v]}</p>"
        return "<p>❌ Tu consulta no pudo ser procesada. Por favor reformúlala.</p>"

    # ------------------------------------------------------------------
    # Interfaz pública
    # ------------------------------------------------------------------
    def run(
        self,
        query: str,
        user_id: str = "anonymous",
        conversation_history: List[Dict] = None,
        rag_mode: str = "gpt",
        use_case: str = "cvs",
        assistant_id: str = None,
        gpt_config: Dict = None,
    ) -> Dict:
        start = datetime.now()
        print(f"\n{'='*60}")
        print(f"🚀 RAG [{use_case.upper()}] │ mode={rag_mode} │ user={user_id}")
        print(f"   Query: {query[:60]}{'...' if len(query) > 60 else ''}")
        print(f"{'='*60}")

        initial_state = RAGState(
            query=query,
            user_id=user_id,
            use_case=use_case,
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
            gpt_config=gpt_config or {},
        )

        try:
            final = self.graph.invoke(
                initial_state,
                config={"configurable": {"thread_id": f"{user_id}_{use_case}"}},
            )
            total = (datetime.now() - start).total_seconds()
            final["timestamps"]["total"] = total
            print(f"✅ Completado en {total:.2f}s\n{'='*60}\n")
            return final

        except Exception as e:
            total = (datetime.now() - start).total_seconds()
            print(f"❌ Error crítico: {e}")
            import traceback; traceback.print_exc()
            return {
                "query": query,
                "user_id": user_id,
                "use_case": use_case,
                "answer": f"<p>❌ Error: {e}</p>",
                "chunks_used": [],
                "chunks_retrieved": [],
                "synthetic_queries": [],
                "metadata": {"error": str(e), "usage": {}},
                "timestamps": {"total": total},
                "error": str(e),
            }


# Instancia global (se crea al importar el módulo)
print("📄 Creando instancia global RAGGraph...")
rag_graph = RAGGraph()
print("✅ RAGGraph global listo\n")
