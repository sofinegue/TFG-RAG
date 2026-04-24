# Graphiti Knowledge Graph — Documentación Técnica

## 0. Quickstart: `graphiti_quickstart_neo4j.py`

Script independiente de prueba que conecta directamente a Neo4j + Azure OpenAI y ejecuta las operaciones básicas de Graphiti (ingestión, búsqueda híbrida, reranking, node search) **sin depender de Cosmos DB**.

### 0.1 ¿Qué hace el script?

Paso a paso:

1. **Carga de configuración** — Lee las credenciales de Neo4j y Azure OpenAI desde `src/config.py` (que a su vez lee el `.env`). No usa `OPENAI_API_KEY` ni clientes por defecto de OpenAI.

2. **Creación del cliente Azure OpenAI** — Un único `AsyncOpenAI` apuntando al endpoint de compatibilidad v1 de Azure (`<azure_url>/openai/v1/`). Este cliente se reutiliza para LLM, embeddings y reranker.

3. **Inicialización de los 3 clientes de Graphiti**:
   - **`AzureOpenAILLMClient`**: Chat/extracción. Usa el deployment `AZURE_OPENAI_GPT4_1_NAME` (e.g. `gpt-4.1`). Se configura `small_model` al mismo deployment para evitar que Graphiti intente usar `gpt-4.1-nano` (que no existe en Azure).
   - **`AzureOpenAIEmbedderClient`**: Embeddings vectoriales. Usa `AZURE_OPENAI_EMB_NAME` (e.g. `text-embedding-ada-002`).
   - **`OpenAIRerankerClient`**: Cross-encoder para reranking por logprobs. Reutiliza el mismo cliente y config LLM.

4. **Conexión a Neo4j** — `Graphiti(uri, user, password, llm_client=..., embedder=..., cross_encoder=...)`. En la primera ejecución crea ~30 índices automáticamente.

5. **FASE 1: Ingestión de episodios** — 4 episodios de ejemplo (2 de texto, 2 JSON) se procesan secuencialmente. Cada uno pasa por extracción de entidades, resolución de duplicados y extracción de relaciones via LLM.

6. **FASE 2: Búsqueda híbrida** — Combina similitud semántica (embeddings) con BM25 (fulltext) para recuperar relaciones relevantes.

7. **FASE 3: Reranking con center node** — Usa el resultado top de la fase 2 como nodo central para reordenar por distancia en el grafo.

8. **FASE 4: Node search (NODE_HYBRID_SEARCH_RRF)** — Busca nodos (entidades) directamente usando una receta de búsqueda predefinida.

9. **Cierre** — Cierra la conexión a Neo4j.

### 0.2 Configuración necesaria (.env)

```bash
# Neo4j Aura
NEO4J_URI=neo4j+s://XXXXXXXX.databases.neo4j.io
NEO4J_USER=XXXXXXXX
NEO4J_PASSWORD=<password>

# Azure OpenAI
AZURE_OPENAI_URL=https://<resource>.cognitiveservices.azure.com
AZURE_OPENAI_KEY=<api-key>
AZURE_OPENAI_GPT4_1_NAME=gpt-4.1            # Nombre del deployment LLM
AZURE_OPENAI_EMB_NAME=text-embedding-ada-002  # Nombre del deployment de embeddings

# Desactivar telemetría (evita errores SSL detrás de proxy)
GRAPHITI_TELEMETRY_ENABLED=false
```

> **Importante**: `AZURE_OPENAI_EMB_NAME` debe coincidir con el nombre exacto del deployment en Azure Portal (no el nombre del modelo). Verificar en Azure Portal → Azure OpenAI → Deployments.

### 0.3 Ejecución

```bash
python doc/investigation/graphiti_quickstart_neo4j.py
# o bien:
python -m doc.investigation.graphiti_quickstart_neo4j
```

### 0.4 Adaptación desde el quickstart original de Graphiti

El script original (`examples/quickstart.py` de graphiti-core) asume acceso directo a la API de OpenAI. Para nuestro entorno Azure se hicieron los siguientes cambios:

| Aspecto | Original | Adaptado |
|---------|----------|----------|
| **Config** | `os.environ.get('OPENAI_API_KEY')` | `src.config.config` (centralizado) |
| **LLM** | `OpenAIClient()` (requiere `OPENAI_API_KEY`) | `AzureOpenAILLMClient` con `AsyncOpenAI` apuntando a endpoint v1 de Azure |
| **Embeddings** | `OpenAIEmbedder()` (requiere `OPENAI_API_KEY`) | `AzureOpenAIEmbedderClient` con el mismo `AsyncOpenAI` |
| **Reranker** | `OpenAIRerankerClient()` (requiere `OPENAI_API_KEY`) | `OpenAIRerankerClient(config=..., client=azure_client)` |
| **Logging** | `print()` | `logger.info()` con timing por fase |
| **`small_model`** | Default (`gpt-4.1-nano`) | Forzado al mismo deployment que el modelo principal |

---

## 1. Visión General

El módulo `graphiti_wiki` construye un **grafo de conocimiento temporal** (Knowledge Graph) a partir de los chunks de Wikipedia almacenados en Cosmos DB, utilizando la librería [Graphiti](https://github.com/getzep/graphiti) y una base de datos de grafos **Neo4j**.

### Objetivo

Complementar la búsqueda vectorial (Azure AI Search) con una representación estructurada de entidades y relaciones extraídas del texto, permitiendo consultas semánticas sobre el grafo.

### Flujo de alto nivel

```
Cosmos DB (Chunks-Wiki)
        │
        ▼
  Lectura de chunks
  (filtro: docTitle + idioma)
        │
        ▼
  Graphiti + Azure OpenAI
  (extracción de entidades y relaciones)
        │
        ▼
  Neo4j (Knowledge Graph)
  (nodos: entidades, aristas: relaciones)
        │
        ▼
  Búsquedas semánticas sobre el grafo
```

---

## 2. Arquitectura de Componentes

### 2.1 Servicios Externos

| Servicio | Rol | Configuración (.env) |
|----------|-----|----------------------|
| **Cosmos DB** | Almacén de chunks de Wikipedia | `COSMOS_ENDPOINT`, `COSMOS_KEY`, `AZURE_COSMOSDB_DB_NAME`, `AZURE_COSMOSDB_COLLECTION_WIKI` |
| **Neo4j (Aura)** | Base de datos de grafos | `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE` |
| **Azure OpenAI (LLM)** | Extracción de entidades/relaciones | Configurado vía `MODELS_CONFIG` (modelo `gpt-4.1`) |
| **Azure OpenAI (Embeddings)** | Embeddings de nombres de entidades | Configurado vía `MODELS_CONFIG` (modelo `ada-002`) |

### 2.2 Dependencias de Código

```
src/document_ingestion/wiki/graphiti_wiki.py
    ├── src/config.py                          (configuración centralizada)
    ├── src/services/cosmos_service.py          (lectura de chunks)
    ├── graphiti_core (Graphiti)                (framework de Knowledge Graph)
    │   ├── graphiti_core.Graphiti              (clase principal)
    │   ├── graphiti_core.driver.neo4j_driver   (driver Neo4j)
    │   ├── graphiti_core.llm_client            (cliente Azure OpenAI LLM)
    │   ├── graphiti_core.embedder              (cliente Azure OpenAI embeddings)
    │   └── graphiti_core.cross_encoder         (reranker)
    └── neo4j.AsyncGraphDatabase               (driver async de Neo4j)
```

---

## 3. Configuración

### 3.1 Variables de Entorno (.env)

```bash
# Neo4j (Aura Free o local)
NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io   # Aura: neo4j+s://  |  Local: bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<password>
NEO4J_DATABASE=xxxxxxxx                           # Nombre de la DB (ver § 8.1 para cómo obtenerlo)

# Desactivar telemetría PostHog de Graphiti (evita errores SSL detrás de proxies corporativos)
GRAPHITI_TELEMETRY_ENABLED=false
```

> **Nota sobre Neo4j Aura Free**: usa siempre el protocolo `neo4j+s://` (con TLS). El default `bolt://localhost:7687` solo sirve para instancias locales (Docker).
>
> **Nota sobre `NEO4J_DATABASE`**: En Neo4j Aura, la base de datos **no** se llama `neo4j` (que es el valor por defecto del driver). Se llama como el **ID de la instancia** (p.ej. `6396cf17`). Si no se configura correctamente, todas las queries fallan con `DatabaseNotFound`. Ver la sección 8.1 para el proceso de diagnóstico completo.

### 3.2 Configuración en `src/config.py`

```python
# === NEO4J (Graphiti Knowledge Graph) ===
neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password")
neo4j_database: str = os.getenv("NEO4J_DATABASE", "neo4j")
```

---

## 4. Módulo `graphiti_wiki.py` — Detalle

### 4.1 Lectura de Chunks desde Cosmos DB

```python
def get_wiki_chunks_from_cosmos(doc_title: str, language: str = "es") -> List[Dict]
```

- Consulta el contenedor `Chunks-Wiki` filtrando por `docTitle`, `sourceLanguage` e `isDeleted = false`.
- Los chunks se devuelven ordenados por `nChunk` (orden secuencial del artículo).
- El parámetro Python es `doc_title`; el campo de Cosmos DB es `docTitle` (camelCase).

### 4.2 Inicialización de Graphiti

```python
async def init_graphiti() -> Graphiti
```

Crea la instancia de Graphiti con:

1. **Cliente LLM** (`AzureOpenAILLMClient`): usa el deployment configurado como `chat_model` (e.g., `gpt-4.1`).
2. **Cliente de Embeddings** (`AzureOpenAIEmbedderClient`): usa el deployment de `embedding_model` (e.g., `ada-002`).
3. **Reranker** (`OpenAIRerankerClient`): reutiliza el cliente LLM para cross-encoding.
4. **Driver Neo4j** con pool de conexiones limitado y **nombre de DB explícito**:

```python
# Nombre de DB explícito (en Aura NO es 'neo4j', es el ID de la instancia)
neo4j_driver = Neo4jDriver(
    uri=config.neo4j_uri,
    user=config.neo4j_user,
    password=config.neo4j_password,
    database=config.neo4j_database,  # ← CRÍTICO para Aura
)

# Pool reducido para Neo4j Aura Free (≈ 3 conexiones simultáneas)
await neo4j_driver.client.close()
neo4j_driver.client = AsyncGraphDatabase.driver(
    uri=config.neo4j_uri,
    auth=(config.neo4j_user, config.neo4j_password),
    max_connection_pool_size=5,
    connection_acquisition_timeout=60,
)
```

> **¿Por qué pool limitado?** Neo4j Aura Free solo admite ~3 conexiones concurrentes. Graphiti, por defecto, crea un pool de 100 conexiones y lanza múltiples queries en paralelo, lo que agota el pool con error `ConnectionAcquisitionTimeoutError`. Limitar a 5 y reducir el timeout a 60s evita que el proceso se quede colgado.
>
> **¿Por qué `database=config.neo4j_database`?** El `Neo4jDriver` de Graphiti usa por defecto `database='neo4j'`. En Neo4j Aura, la única BD disponible se llama como el ID de la instancia (p.ej. `6396cf17`), por lo que todas las queries fallarían con `DatabaseNotFound` si no se especifica.

Se inyecta el driver custom mediante `graph_driver=neo4j_driver` (en lugar de pasar URI directamente a `Graphiti()`).

### 4.3 Ingesta de Chunks

```python
async def ingest_chunks_to_graph(graphiti, chunks, doc_title, group_id) -> dict
```

Cada chunk se convierte en un **episodio** de tipo texto en Graphiti:

| Campo del episodio | Valor |
|---------------------|-------|
| `name` | `"{doc_title} — chunk {nChunk}"` |
| `episode_body` | Contenido del chunk (`content`) |
| `source` | `EpisodeType.text` |
| `source_description` | Metadatos enriquecidos: título, secciones, categorías |
| `reference_time` | `datetime.now(UTC)` |
| `group_id` | Configurable (default: `wiki_es` o `wiki_en`) |

El `source_description` incluye contexto para que el LLM extraiga mejores entidades y relaciones:
```
Artículo Wikipedia 'Writer' | Secciones: Types > Fiction writers | Categorías: Writers, Literature
```

**Estadísticas** devueltas: `total_episodes`, `total_nodes`, `total_edges`, `errors`.

### 4.4 Búsqueda de Prueba

```python
async def test_search(graphiti, query, group_id, num_results) -> None
```

Ejecuta una búsqueda semántica sobre el grafo y muestra los hechos (facts) encontrados con sus timestamps de validez.

### 4.5 Pipeline Completo

```python
async def run_graphiti_wiki_pipeline(doc_title, language, group_id, test_queries) -> dict
```

Orquesta todo el flujo:

1. Lee chunks de Cosmos DB
2. Inicializa Graphiti
3. Crea índices y constraints en Neo4j
4. Ingesta chunks como episodios
5. (Opcional) Ejecuta búsquedas de prueba
6. Cierra la conexión

---

## 5. Uso (CLI)

### Ingesta de un artículo

```bash
# Artículo en español (default)
python -m src.document_ingestion.wiki.graphiti_wiki --doc_title "Escritor" --language es

# Artículo en inglés
python -m src.document_ingestion.wiki.graphiti_wiki --doc_title "Writer" --language en

# Con group_id personalizado
python -m src.document_ingestion.wiki.graphiti_wiki --doc_title "Writer" --language en --group_id wiki_en

# Con consultas de prueba personalizadas
python -m src.document_ingestion.wiki.graphiti_wiki --doc_title "Writer" --language en --test_query "What types of writers exist?"
```

### Parámetros CLI

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `--doc_title` | `Escritor` | Título del artículo de Wikipedia |
| `--language` | `es` | Idioma del artículo (`es`, `en`) |
| `--group_id` | `wiki_es` | ID de grupo para particionar el grafo |
| `--test_query` | 2 queries por defecto | Consultas de prueba post-ingesta |

---

## 6. Convenciones de Nombres

| Contexto | Nombre | Ejemplo |
|----------|--------|---------|
| **Python** (variables, parámetros, CLI) | `doc_title` (snake_case) | `doc_title="Writer"` |
| **Cosmos DB** (campos del documento) | `docTitle` (camelCase) | `c.docTitle = 'Writer'` |

Esta convención se aplica consistentemente en todo el módulo: los parámetros Python usan snake_case, mientras que las queries a Cosmos DB preservan los nombres de campo originales en camelCase.

---

## 7. Modelo del Grafo en Neo4j

Graphiti crea automáticamente los siguientes tipos de nodos y relaciones:

### Nodos

| Label | Descripción |
|-------|-------------|
| `Entity` | Entidades extraídas del texto (personas, conceptos, lugares...) |
| `Episodic` | Episodios (cada chunk se convierte en uno) |
| `Community` | Comunidades de entidades relacionadas |
| `Saga` | Agrupaciones de episodios relacionados |

### Relaciones

| Tipo | Descripción |
|------|-------------|
| `RELATES_TO` | Relación factual entre dos entidades |
| `MENTIONS` | Un episodio menciona una entidad |
| `HAS_EPISODE` | Vincula sagas con episodios |
| `NEXT_EPISODE` | Orden temporal entre episodios |
| `HAS_MEMBER` | Vincula comunidades con entidades |

### Índices

Graphiti crea ~30 índices automáticamente (RANGE y FULLTEXT) en la primera ejecución. En ejecuciones posteriores, los mensajes `index or constraint already exists` son informativos y se ignoran.

---

## 8. Troubleshooting

### Errores Conocidos y Soluciones

| Error | Causa | Solución |
|-------|-------|----------|
| `DatabaseNotFound: Unable to get a routing table for database 'neo4j'` | Nombre de BD incorrecto (Aura usa el ID de la instancia, no `neo4j`) | Configurar `NEO4J_DATABASE` con el ID real (ver § 8.1) |
| `ConnectionAcquisitionTimeoutError: failed to obtain connection from pool within 300s` | Pool de conexiones agotado (Aura Free ~3 conexiones) | Pool limitado a 5, timeout 60s (ver § 4.2) |
| `SSL: CERTIFICATE_VERIFY_FAILED` en PostHog/urllib3 | Proxy corporativo bloquea telemetría de Graphiti | `GRAPHITI_TELEMETRY_ENABLED=false` en `.env` |
| `index or constraint already exists` | Índices ya creados en ejecución anterior | Ignorar (informativo) |
| `property name_embedding does not exist` | Primer chunk, aún no hay entidades | Ignorar (desaparece tras crear la primera entidad) |
| `property entity_edges does not exist` | Primera ejecución | Ignorar (Graphiti lo crea al necesitarlo) |
| `Cosmos DB Forbidden` | IP no autorizada en firewall | Añadir IP al firewall de Cosmos DB en Azure Portal |

---

### 8.1 Diagnóstico del nombre de base de datos en Neo4j Aura

#### Síntoma

Al ejecutar la ingesta con Graphiti, el proceso se queda colgado durante minutos y finalmente falla con:

```
ERROR - Error executing Neo4j query: failed to obtain a connection from the pool within 300s (timeout)
```

O bien, al probar la conexión directamente:

```
ClientError: {neo4j_code: Neo.ClientError.Database.DatabaseNotFound}
{message: Unable to get a routing table for database 'neo4j' because this database does not exist}
```

#### Causa raíz

El driver `Neo4jDriver` de Graphiti usa `database='neo4j'` por defecto al construirse. En Neo4j **Community Edition** o **Docker**, la BD por defecto se llama efectivamente `neo4j`. Sin embargo, en **Neo4j Aura** (servicio cloud), la BD se llama como el **ID de la instancia** (p.ej. `6396cf17`), y la BD `neo4j` simplemente no existe.

Esto provoca que las queries nunca obtengan un routing table válido, agotando el pool de conexiones con un timeout de 300 segundos.

#### Procedimiento de diagnóstico

1. **Verificar conectividad SSL** — confirma que las credenciales (URI, user, password) son correctas:

```python
from neo4j import GraphDatabase

d = GraphDatabase.driver(
    "neo4j+s://6396cf17.databases.neo4j.io",
    auth=("6396cf17", "<password>"),
)
d.verify_connectivity()  # → OK si las credenciales son correctas
```

2. **Listar las bases de datos disponibles** — conectando a la BD `system` (que siempre existe):

```python
records, _, _ = d.execute_query("SHOW DATABASES", database_="system")
for r in records:
    print(r["name"], r["currentStatus"], "home=" + str(r.get("home", False)))
```

Salida esperada en Aura:
```
6396cf17  online  home=True    ← esta es la BD real
system    online  home=False   ← BD de sistema (solo para gestión)
```

3. **Verificar que la BD correcta funciona**:

```python
records, _, _ = d.execute_query("RETURN 1 AS n", database_="6396cf17")
print(records[0]["n"])  # → 1
```

#### Solución aplicada

Tres cambios coordinados:

1. **`.env`** — añadir la variable `NEO4J_DATABASE` con el nombre real de la BD:
   ```bash
   NEO4J_DATABASE="6396cf17"
   ```

2. **`src/config.py`** — leer la variable:
   ```python
   neo4j_database: str = os.getenv("NEO4J_DATABASE", "neo4j")
   ```

3. **`graphiti_wiki.py`** — pasar `database=` al constructor del driver:
   ```python
   neo4j_driver = Neo4jDriver(
       uri=config.neo4j_uri,
       user=config.neo4j_user,
       password=config.neo4j_password,
       database=config.neo4j_database,  # ← fix
   )
   ```

#### Cómo obtener las credenciales Neo4j Aura

1. Ir a [console.neo4j.io](https://console.neo4j.io)
2. Seleccionar la instancia
3. Los datos necesarios son:
   - **Connection URI** → `NEO4J_URI` (formato `neo4j+s://XXXX.databases.neo4j.io`)
   - **Username** → `NEO4J_USER` (normalmente coincide con el ID de la instancia)
   - **Password** → `NEO4J_PASSWORD` (se genera una sola vez al crear la instancia; si se pierde, hay que regenerarlo)
   - **Database ID** → `NEO4J_DATABASE` (visible como ID de la instancia en el dashboard)

> **Importante**: el password se muestra **una sola vez** al crear la instancia. Si lo pierdes, la única opción es regenerar uno nuevo desde la consola de Aura.

---

### 8.2 Errores SSL de telemetría (PostHog)

#### Síntoma

Durante la ingesta aparecen warnings repetidos:

```
WARNING - Retrying after connection broken by 'SSLError(SSLCertVerificationError(...
    certificate verify failed: unable to get local issuer certificate))': /batch/
ERROR - error uploading: HTTPSConnectionPool(host='us.i.posthog.com', port=443): Max retries exceeded
```

#### Causa

Graphiti incluye telemetría anónima (PostHog) que envía estadísticas de uso a `us.i.posthog.com`. Detrás de un proxy corporativo (como el de EY), la verificación SSL falla porque el proxy intercepta el tráfico HTTPS con su propio certificado.

#### Solución

Desactivar la telemetría con la variable de entorno `GRAPHITI_TELEMETRY_ENABLED`:

```bash
# En .env
GRAPHITI_TELEMETRY_ENABLED=false
```

Además, en `graphiti_wiki.py` se fuerza antes de importar Graphiti:

```python
os.environ.setdefault("GRAPHITI_TELEMETRY_ENABLED", "false")
```

Esto es inocuo: la telemetría solo recoge estadísticas anónimas y desactivarla no afecta al funcionamiento.

---

### Logs a Silenciar (opcionales)

Para una salida más limpia, se pueden subir los niveles de log en el script:

```python
logging.getLogger("neo4j.notifications").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("posthog").setLevel(logging.CRITICAL)
```
