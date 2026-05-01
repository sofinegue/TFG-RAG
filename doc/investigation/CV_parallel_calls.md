Plan & Explanation
Here's what the architecture from the diagram requires and how it maps to the code:
What already exists (but is NOT connected):
•	Config (config.py:104): cvs_top_k, cvs_chunk_size, cvs_group1_use_llm, cvs_reliability_t1-t4, cvs_history_path — all already in place
•	CVS Handler (cvs_handler.py): classify_chunks_by_reliability(), _call_mini_llm_batch(), _process_group_with_mini_llm(), process_query() — fully implemented
•	CVS History (cvs_history.py): JSON persistence with {id, timestamp, query, groups: {grupo1: {reliability, data, reasoning}, ...}} — done
•	CVS Prompts (cvs_prompts.py): mini_llm_batch() prompt — done
What's missing:
1.	Retriever bug: generate_synthetic_queries() checks the global config.use_rag_fusion instead of the handler's retrieval_cfg.use_rag_fusion. For CVs the handler returns use_rag_fusion=False but it's ignored.
2.	LangGraph wiring: cvs_handler.process_query() is never called. The flow goes retrieve → generate (standard GPT), but for CVS it should go retrieve → process_cvs (classify + mini-LLMs + history) → response_format (powerful LLM to assemble final answer).
3.	Response Format prompt: A prompt that takes all 5 group results + the original query and asks a powerful LLM to produce the final user-facing answer.
4.	State field: RAGState needs a cvs_groups field to carry the intermediate group results.
Changes I'll make:
File	Change
retriever.py
Fix retrieve() to pass handler's retrieval_cfg to generate_synthetic_queries so CVS bypasses RAG Fusion
app_langgraph.py
Add process_cvs node + conditional routing after retrieve: if use_case=="cvs" → process_cvs → END, otherwise → generate

cvs_handler.py
Add format_final_response() that calls a powerful LLM with all group results to assemble the user-facing answer
cvs_prompts.py
Add response_format() prompt for the final assembly step

Updated todo list
Step 1: Fix the Retriever to respect per-handler RAG Fusion config
Step 2: Add the response_format prompt to CVsPrompts
Step 3: Add format_final_response() to CVsUseCaseHandler
Step 4: Wire the CVS pipeline into LangGraph
Now the key part — I need to add a process_cvs node to the LangGraph that:
1.	Runs cvs_handler.process_query() (classify → grupo1 direct → grupos 2-5 mini-LLM → history)
2.	Runs cvs_handler.format_final_response() (powerful LLM to assemble the final answer)
3.	Sets the answer in state
And route conditionally: after retrieve, if use_case=="cvs" go to process_cvs, otherwise go to generate.
Edited
app_langgraph.py+19-1
Now add the process_cvs node method itself, right after retrieve_chunks:
Now update the initial_state in the run() method to include the new cvs_groups field:
Now let me verify the final state of all modified files:
Checked app_langgraph.py, cvs_handler.py, cvs_prompts.py, retriever.py, no problems found
Let me also verify the LangGraph edges are correct — especially the process_cvs edge with guardrails_output:
Read app_langgraph.py, lines 70 to 115
Good. The flow is now:
validate → [guardrails_input] → classify → retrieve → 
  ├─ (cvs) → process_cvs → [guardrails_output] → END
  └─ (eu/wiki) → generate → [guardrails_output] → END

Let me also quickly verify the process_cvs and format_final_response chain by reading the final state:
Read app_langgraph.py, lines 185 to 240
Everything looks consistent. Let me also check there's a small indentation issue with the closing parenthesis on the conditional edges:
________________________________________
Resumen de cambios implementados
Arquitectura implementada (3 fases del diagrama):
Fase 1 — Retrieve
•	Se corrigió retriever.py:127 para que generate_synthetic_queries() ahora respete el retrieval_cfg del handler. Para CVs, el handler ya devolvía use_rag_fusion=False y top_k=CVS_TOP_K (50), pero el retriever ignoraba esa config y usaba la global. Ahora:
o	CVs: sin RAG Fusion, búsqueda directa con la query del usuario, recupera CVS_TOP_K chunks
o	EU/Wiki: siguen usando RAG Fusion normalmente
Fase 2 — Generate (clasificar + mini-LLMs)
•	Se añadió el nodo process_cvs en app_langgraph.py:183 que invoca cvs_handler.process_query(). Este método (que ya existía pero no se llamaba nunca) hace:
1.	Clasifica los chunks en 5 grupos de fiabilidad según el score de Azure Search:
	Grupo 1: score >= 0.9 → extracción directa de nombres desde doc_title (sin LLM)
	Grupo 2: 0.7–0.9 → mini-LLM en lotes de CVS_CHUNK_SIZE
	Grupo 3: 0.5–0.7 → mini-LLM
	Grupo 4: 0.3–0.5 → mini-LLM
	Grupo 5: < 0.3 → mini-LLM
2.	Procesa cada grupo en paralelo con ThreadPoolExecutor
3.	Persiste en el historial data/cvs_history.json con estructura:
{"id": "uuid", "timestamp": "ISO-8601", "query": "...", "groups": {
  "grupo1": {"reliability": "≥90%", "data": ["Nombre1", ...], "reasoning": "..."},
  "grupo2": {"reliability": "70%–90%", "data": "nombre | nombre", "reasoning": "..."},
  ...
}}

Fase 3 — Response Format
•	Se añadió format_final_response() en cvs_handler.py que toma los resultados de todos los grupos y los pasa a un LLM potente (gpt-4.1) para ensamblar la respuesta final
•	Se creó el prompt response_format() en cvs_prompts.py que instruye al LLM a presentar candidatos de alta fiabilidad primero, usar matices para fiabilidad baja, y dar un resumen con distribución
Routing en LangGraph:
•	Se añadió cvs_groups como nuevo campo del estado RAGState en app_langgraph.py:35
•	Tras retrieve, un routing condicional (should_use_cvs_pipeline) decide:
o	use_case == "cvs" → process_cvs → guardrails_output → END
o	Otros → generate (flujo estándar) → guardrails_output → END
Variables de entorno (ya existentes en config.py):
Variable	Default	Uso
CVS_TOP_K	50	Chunks a recuperar sin RAG Fusion
CVS_CHUNK_SIZE	5	Lote de chunks por llamada mini-LLM
CVS_GROUP1_USE_LLM	false	Si true, grupo1 también pasa por mini-LLM
CVS_RELIABILITY_T1	0.9	Umbral grupo1 (alta fiabilidad)
CVS_RELIABILITY_T2	0.7	Umbral grupo2
CVS_RELIABILITY_T3	0.5	Umbral grupo3
CVS_RELIABILITY_T4	0.3	Umbral grupo4
CVS_HISTORY_PATH	data/cvs_history.json	Ruta al historial

Replacing 1 lines with 1 lines in [](file:///c%3A/Users/WG918GS/OneDrive%20-%20EY/Desktop/TFG/TFG-RAG/src/config.py)


```

```
Hecho. La ruta por defecto ahora es `data/historial/cvs_history.json`. La carpeta se crea automáticamente (el `CvsHistory.__init__` ya hace `mkdir(parents=True, exist_ok=True)`).

---

Sobre dónde se envían los chunks:

### Mini-LLM (gpt-4o-mini)
En cvs_handler.py — método `_call_mini_llm_batch()`:
- Recibe un lote de chunks y llama a `self.prompts.mini_llm_batch(query, chunks, reliability_label)` para construir el prompt.
- Luego hace `mini_client.chat.completions.create(model=mini_deployment, ...)`.

El **batching** ocurre en `_process_group_with_mini_llm()` (cvs_handler.py), que divide los chunks del grupo en lotes de `cvs_chunk_size` (ahora 12) y lanza cada lote en paralelo con `ThreadPoolExecutor`.

El prompt que recibe cada lote se construye en cvs_prompts.py — método `mini_llm_batch()`: itera los chunks y mete `content[:600]` de cada uno.

### LLM final / potente (gpt-4.1)
En cvs_handler.py — método `format_final_response()`:
- Recibe los **resultados agregados** de los 5 grupos (nombres + reasoning), **no los chunks directamente**.
- Llama a `self.prompts.response_format(query, groups, max_chars)` y lo envía al modelo potente con `client.chat.completions.create()`.

El prompt de response_format se construye en cvs_prompts.py — método `response_format()`: monta el texto de cada grupo con perfiles y razonamiento.

**Resumen del flujo de datos:**
```
chunks (50) → classify_by_reliability → 5 grupos
  ├─ grupo1: extracción directa de nombres (sin LLM)
  ├─ grupos 2-5: chunks → lotes de 12 → mini-LLM (content[:600])
  └─ resultados de todos los grupos → response_format → LLM potente (sin chunks, solo nombres+reasoning)
```
