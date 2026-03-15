# Documentación de Arquitectura — TFG-RAG

---

## Arquitectura general

Es un sistema **RAG (Retrieval-Augmented Generation)** con backend FastAPI, desplegado en Azure.  
El flujo principal es: recibir una pregunta → buscar documentos relevantes → generar una respuesta con un agente de IA.

---

## Archivos principales

### `main.py` — Punto de entrada / API REST
- Levanta la aplicación **FastAPI** con CORS configurado.
- Expone los endpoints HTTP que consume el frontend (React en `localhost:3000`).
- Conecta con **Azure CosmosDB** para guardar y recuperar el historial de conversaciones.
- Usa un `ThreadPoolExecutor` para no bloquear el event loop con operaciones lentas (e.g., lecturas a BD).

---

### `appLangGraph.py` — Orquestador del pipeline RAG

Es el **grafo de estados** (LangGraph). Controla el flujo completo de una consulta:

```
START → validate_user_input → [guardrails_input] → classify_context → [retrieve] → generate → [guardrails_output] → END
```

| Nodo | Qué hace |
|---|---|
| `validate_user_input` | Sanea y valida la query entrante |
| `classify_context` | Decide si la pregunta necesita buscar documentos o puede responderse directamente |
| `retrieve` | Lanza la búsqueda híbrida en Azure Search |
| `generate` | Llama al agente (Azure Assistants) para generar la respuesta |
| `guardrails_input/output` | Filtros opcionales de seguridad (activables en config) |
| `handle_error` | Manejo centralizado de errores |

El estado global (`RAGState`) fluye entre nodos y contiene: la query, historial, chunks recuperados, respuesta, timestamps, etc.

---

### `agent_builder_workflow.py` — Motor de generación con Agentes Azure
- Se conecta a **Azure AI Foundry** (Azure OpenAI Assistants API).
- Gestiona un **agente principal** y **subagentes** que pueden ejecutarse en paralelo (`run_parallel_orchestration`).
- Cada asistente está configurado con un JSON en `/jsonsAsistentes/` (ej. `iberia.json`, `telia.json`).
- Cachea los modelos de los agentes para no hacer peticiones repetidas.
- Soporta **streaming** de respuestas.

---

### `models/retriever.py` — Búsqueda de documentos

Implementa **búsqueda híbrida** en Azure Cognitive Search:
1. **Vector search** — convierte la query en embeddings con Azure OpenAI.
2. **Semantic search** — re-ranking semántico de Azure.
3. **Keyword search** — búsqueda textual clásica.

También hace **query expansion**: extrae nombres propios del historial de conversación (regex) y enriquece la query para recuperar los chunks más relevantes.

---

### `models/generator.py` — Generación de respuestas
- Orquesta la llamada al agente Azure o a GPT directo según el modo (`rag_mode`).
- Post-procesa la respuesta: elimina citas de archivo (`【...】`), formatea CSVs si el asistente devuelve datos tabulares.

---

### `prompts/promptTemplates.py` — Plantillas de prompts
Centraliza todos los prompts del sistema en una clase estática. Soporta multiidioma (español/inglés).  
Incluye prompts para: respuesta directa, clasificación de query, expansión de queries, etc.

---

### `guardrails.py` — Filtros de seguridad
Valida entradas y salidas del pipeline (contenido inapropiado, queries maliciosas, respuestas fuera de scope).  
Son **opcionales** y se activan en `config`.

---

### `services/` — Capa de servicios Azure

| Archivo | Responsabilidad |
|---|---|
| `azure_storage_service.py` | Subida/descarga de archivos en Azure Blob Storage |
| `cosmos_service.py` | CRUD de conversaciones en CosmosDB |
| `docintelligence_service.py` | Extracción de texto de PDFs con Azure Document Intelligence |
| `document_service.py` | Orquesta el procesamiento completo de documentos (chunking, indexación) |
| `openai_service.py` | Wrapper del cliente Azure OpenAI |
| `vector_store_service.py` | Gestión del índice vectorial en Azure Search |

---

### `jsonsAsistentes/` — Configuración de asistentes
Cada JSON define un asistente especializado (ej: `iberia.json`, `telia.json`).  
Contiene su `assistant_id`, instrucciones del sistema, parámetros GPT y si usa búsqueda vectorial.

---

### `config_orig.py` — Configuración global
Variables de entorno, credenciales Azure, parámetros del modelo (temperatura, max tokens, etc.),  
y flags para activar/desactivar guardrails.

---

## Flujo resumido de una consulta

```
Usuario pregunta
     ↓
main.py (FastAPI endpoint)
     ↓
appLangGraph.py (grafo de estados)
     ├── retriever.py → Azure Search (busca chunks relevantes)
     └── generator.py → agent_builder_workflow.py → Azure Assistants API
          ↓
Respuesta enviada al usuario + guardada en CosmosDB
```
