El sistema está construido con FastAPI como API REST, LangGraph como motor de orquestación del pipeline RAG, y Azure como infraestructura de todos los servicios de IA y datos. El frontend es una aplicación React que se comunica con la API.
La arquitectura soporta tres casos de uso independientes con sus propios índices de búsqueda:
	cvs: búsqueda de talento en currículums de empleados
	eu: consultas sobre normativa de la Unión Europea
	wiki: consultas sobre artículos de Wikipedia
Cada caso de uso tiene su propio índice en Azure AI Search (index-cvs, index-eu, index-wiki), su propia colección en CosmosDB, y sus propios prompts de generación especializados.
Configuración centralizada (config.py)
Toda la configuración del sistema está en la clase de datos RAGConfig, que lee variables de entorno mediante python-dotenv. Esto incluye las credenciales y endpoints de todos los servicios Azure, los parámetros de los modelos (temperatura, max_tokens, modelo de chat y de embedding), los nombres de los índices por caso de uso, y los flags de activación de guardrails. La separación de configuración en una clase de datos única facilita el despliegue en distintos entornos sin tocar el código.
El punto de entrada: main.py
La API FastAPI expone los endpoints HTTP que consume el frontend React. CORS está configurado para permitir peticiones desde localhost:3000. Las operaciones de base de datos (lectura/escritura en CosmosDB) se ejecutan en un ThreadPoolExecutor para no bloquear el event loop de asyncio, ya que el cliente de CosmosDB es síncrono pero la API es asíncrona.
El orquestador: LangGraph (app_langgraph.py)
El núcleo del pipeline es un grafo de estados construido con LangGraph. LangGraph es una extensión de LangChain diseñada para definir flujos de trabajo de IA como grafos dirigidos, donde cada nodo es una función que transforma un estado global compartido.
El estado global se define en el TypedDict llamado RAGState, que contiene todos los datos que fluyen a través del grafo: la query del usuario, el user_id, el use_case, el historial de conversación (conversation_history), los chunks recuperados (chunks_retrieved), las queries sintéticas generadas (synthetic_queries), la respuesta final (answer), metadatos de la ejecución, marcas de tiempo (timestamps) y el modo de RAG activo (rag_mode: "gpt" o "assistant").
El grafo se construye así:
START
  └→ validate_user_input
       └→ [guardrails_input]     ← opcional, activable en config
            └→ classify_context
                 ├→ retrieve      ← solo en modo GPT
                 │    └→ generate
                 └→ generate      ← directo en modo assistant
                      └→ [guardrails_output]  ← opcional
                           └→ END

         [handle_error]  ← accesible desde cualquier punto de fallo
Las transiciones entre nodos son aristas condicionales: should_continue_after_validation decide si pasar a guardrails o ir directamente a clasificación según si hubo error; should_retrieve decide si recuperar chunks o generar directamente según el rag_mode. Esta separación entre decisión y ejecución es la fortaleza de LangGraph: el flujo de control es explícito, auditable y modificable sin tocar la lógica de cada nodo.
LangGraph guarda el estado entre ejecuciones mediante un MemorySaver (checkpointer en memoria), usando como clave de hilo {user_id}_{use_case}.
La recuperación: búsqueda híbrida + RAG Fusion (retriever.py)
El Retriever implementa una estrategia de recuperación en varios niveles para maximizar la relevancia de los chunks obtenidos:
1. Expansión de la query con historial conversacional. Antes de buscar, el sistema analiza los últimos cuatro mensajes del historial usando una expresión regular para extraer nombres propios (personas mencionadas en la conversación). Si la query actual usa términos genéricos como "¿y él?" o "¿tiene certificaciones?", se envía un prompt a GPT para reescribirla incluyendo los nombres concretos identificados. Esto resuelve la correferencia conversacional sin necesitar de una arquitectura de memoria compleja.
2. Generación de queries sintéticas (RAG Fusion). Si el parámetro use_rag_fusion está activo (por defecto sí), el retriever envía la query expandida a GPT con un prompt que pide generar N reformulaciones alternativas. Por ejemplo, para la query "candidatos con experiencia en cloud", podría generar variantes como "perfiles Azure o AWS", "ingenieros con proyectos en nube", etc. El número de queries sintéticas está configurable (rag_fusion_queries, por defecto 5).
3. Búsqueda híbrida en paralelo. Para cada query (original + sintéticas), se lanza una búsqueda en Azure AI Search usando ThreadPoolExecutor. Cada búsqueda es híbrida: envía la query como texto (búsqueda léxica BM25) y simultáneamente como vector (embedding generado con text-embedding-ada-002), combinando lo mejor de la búsqueda por palabras clave con la búsqueda semántica. El índice está configurado en Azure AI Search para fusionar ambas modalidades internamente.
4. Fusión con Reciprocal Rank Fusion (RRF). Todos los resultados de todas las búsquedas se fusionan con el algoritmo RRF. Para cada chunk, su puntuación RRF es la suma de 1/(60+"rango" ) en cada lista de resultados donde aparece. Los chunks que aparecen en múltiples resultados (por distintas reformulaciones de la query) acumulan más puntuación, lo que prioriza los más consistentemente relevantes. Finalmente se filtran los que no superan el umbral de relevancia (min_relevance_score) y se trunca al número máximo de chunks configurado (max_chunks_used).


5. Caso especial modo assistant. En modo "assistant", el paso de retrieval se salta completamente: el agente de Azure AI Assistants tiene su propio mecanismo file_search integrado para acceder a los documentos.



La generación: dos modos de operación (generator.py)
El Generator soporta dos modos configurables en tiempo de ejecución:
Modo GPT (rag_mode = "gpt"). Los chunks recuperados se serializan y se inyectan en el prompt del sistema junto con la query y el historial reciente. La llamada va directamente a la API de Azure OpenAI (AzureOpenAI client). Los parámetros del modelo (temperatura, max_tokens, modelo concreto) son configurables por caso de uso mediante gpt_config. Esta es la modalidad estándar RAG.
Modo Assistant (rag_mode = "assistant"). El sistema delega en Azure AI Assistants API (parte de Azure AI Foundry). Cada asistente es un agente pre-configurado con su propio system prompt, acceso a herramientas y, opcionalmente, un índice vectorial propio. En el código del proyecto legacy (agent_builder_workflow.py) se gestionan múltiples asistentes que pueden ejecutarse en paralelo, con streaming de respuestas y caché de configuraciones.
INVESTIGAR CUÁL DE LOS DOS ES MEJOR PARA CADA CASOS DE USO
La post-procesión es común a ambos modos: se eliminan las citas de archivo con formato 【...】 que genera Azure OpenAI automáticamente, se normalizan los espacios y se aplica cualquier formateo especial (como tablas CSV si el asistente devuelve datos tabulares).
Los prompts (prompt_templates.py)
Todos los prompts están centralizados en la clase estática PromptTemplates. Hay prompts para:
	Generación principal: diferenciados por caso de uso (_rag_cvs, _rag_eu, _rag_wiki). El prompt para CVs, por ejemplo, instruye al modelo a listar todos los candidatos relevantes con formato de párrafo natural, mientras que el de Wikipedia tiene instrucciones distintas de explicación enciclopédica.
	RAG Fusion: solicita al LLM generar k reformulaciones alternativas de la query en el idioma configurado.
	Expansión conversacional: decide si la query necesita contexto del historial y la reescribe.
	Clasificación de contexto: determina si la pregunta necesita recuperar documentos.
El sistema es multiidioma: el idioma del prompt se selecciona según la variable LANGUAGE de configuración.
Los guardrails (guardrails.py)
Los guardrails son filtros de seguridad opcionales que se activan con los flags enable_input_guardrails y enable_output_guardrails en la configuración.
Guardrails de entrada validan la query entrante en varias capas:
	Longitud: rechaza queries superiores a 5.000 caracteres
	Inyección de prompt: detecta patrones de ataque con expresiones regulares (frases como "ignore previous instructions", eval(, <script>, etc.)
	Palabras clave sospechosas: detecta términos como jailbreak, sudo, password
	Moderación de contenido: si enable_content_moderation está activo, envía la query a la API de moderación de Azure OpenAI
	Sanitización: limpia la query antes de procesarla
Guardrails de salida validan la respuesta generada antes de enviarla al usuario, con una comprobación opcional de alucinaciones si enable_hallucination_check está activo.
Si cualquier validación falla, se lanza una GuardRailsViolation que el nodo handle_error del grafo convierte en un mensaje de error amigable para el usuario.
La capa de servicios (services)
Cada servicio Azure tiene su propio módulo de abstracción:
	cosmos_service.py: CRUD sobre las colecciones de CosmosDB; guarda y recupera el historial de conversaciones.
	azure_storage_service.py: sube y descarga ficheros de Azure Blob Storage; también lista y descarga configuraciones de asistentes.
	docintelligence_service.py: envía PDFs a Azure Document Intelligence y devuelve el texto estructurado para el pipeline de ingesta.
	openai_service.py: wrapper del cliente AzureOpenAI con gestión de credenciales.
	vector_store_service.py: gestiona el ciclo de vida del índice vectorial en Azure AI Search (creación, actualización, eliminación de documentos).
	document_service.py: orquesta el flujo completo de procesamiento de un documento (extracción → chunking → indexación).
Flujo completo de una consulta (resumen técnico)
Usuario: "¿Qué candidatos tienen certificación en AWS?"
    │
    ▼
main.py  →  FastAPI endpoint  →  rag_graph.run(query, user_id, use_case="cvs", rag_mode="gpt")
    │
    ▼
LangGraph (RAGState)
    │
    ├─ validate_user_input:    query válida, inicializa timestamps
    ├─ guardrails_input:       no contiene inyección ni contenido inapropiado
    ├─ classify_context:       modo GPT → use_retrieval = True
    │
    ├─ retrieve:
    │    ├─ expand_query:         "candidatos con certificación en AWS" (sin cambios)
    │    ├─ generate_synthetic:   ["perfiles cloud AWS", "ingenieros certificados Amazon", ...]
    │    ├─ hybrid_search × 5:    búsqueda paralela en Azure AI Search (index-cvs)
    │    └─ rag_fusion RRF:       fusión y reranking → 15 chunks más relevantes
    │
    ├─ generate:
    │    ├─ prompt_cvs:           contexto con los 15 chunks + pregunta
    │    ├─ Azure OpenAI GPT-4.1: genera respuesta con candidatos listados
    │    └─ clean_citations:      elimina referencias 【...】
    │
    ├─ guardrails_output:      respuesta válida, sin alucinaciones detectadas
    └─ END → respuesta + metadata devueltos al frontend

CosmosDB:  historial actualizado con la pregunta y la respuesta
