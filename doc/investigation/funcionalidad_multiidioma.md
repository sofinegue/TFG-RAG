# Funcionalidad Multiidioma — Documentación Técnica

## 1. Visión General

La funcionalidad multiidioma permite al usuario seleccionar el idioma en el que desea interactuar con el sistema RAG. Esta selección tiene impacto en tres niveles:

1. **Filtrado de datos (retrieval)**: los chunks recuperados de Azure AI Search se filtran por el campo `sourceLanguage`, de modo que solo se recuperan fragmentos en el idioma seleccionado.
2. **Generación de respuesta**: los prompts enviados al LLM incluyen una instrucción explícita para responder en el idioma elegido.
3. **Persistencia**: en el caso de uso de CVs, el idioma se guarda en cada entrada del historial (`cvs_history.json`).

### Idiomas disponibles por caso de uso

| Caso de uso        | Idiomas disponibles                                  |
|--------------------|------------------------------------------------------|
| **CVs**  | Español (`es`), Inglés (`en`)                        |
| **Wikipedia**      | Español (`es`), Inglés (`en`)                        |
| **Legislación UE** | Español (`es`), Inglés (`en`), Francés (`fr`), Italiano (`it`), Portugués (`pt`) |

Esta configuración refleja los idiomas en los que existen documentos indexados en cada corpus de Azure AI Search.

---

## 2. Arquitectura del Flujo

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                         │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ UseCaseSelector  │  │ 🌐 Language  │  │    ChatPanel     │  │
│  │  (CVs/EU/Wiki)   │  │   Selector   │  │                  │  │
│  └──────────────────┘  └──────┬───────┘  └────────┬─────────┘  │
│                               │                    │            │
│                               │   language="es"    │            │
│                               └────────┬───────────┘            │
│                                        │                        │
│              POST /api/chat  { query, use_case, language, ... } │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BACKEND (FastAPI)                            │
│                                                                 │
│  main.py: recibe `language` como Form param                     │
│           └─→ rag_graph.run(..., language=language)              │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │               LangGraph Pipeline (RAGState)              │   │
│  │                                                          │   │
│  │  RAGState.language = "es" | "en" | "fr" | "it" | "pt"   │   │
│  │                                                          │   │
│  │  validate → guardrails → classify → retrieve → generate  │   │
│  │                                         │                │   │
│  │                              ┌──────────┴──────────┐     │   │
│  │                              │                     │     │   │
│  │                        Retriever            Generator    │   │
│  │                     (filtra por           (responde en   │   │
│  │                    sourceLanguage)       idioma elegido) │   │
│  │                              │                     │     │   │
│  │                     Azure AI Search        Azure OpenAI  │   │
│  │                   filter="sourceLanguage    prompt con   │   │
│  │                     eq 'es'"              "Responde en   │   │
│  │                                            español"      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  CVs History: guarda { ..., "language": "es", ... }             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Cambios por Fichero

### 3.1. Frontend

#### 3.1.1. `frontend/src/App.js`

**Cambios realizados:**

- **Nuevo import**: se añade `useMemo` de React y el componente `LanguageSelector`.
- **Constante `LANGUAGES_BY_USE_CASE`**: define los idiomas disponibles para cada caso de uso:
  ```javascript
  const LANGUAGES_BY_USE_CASE = {
    cvs:  [{ code: 'es', label: 'Español' }, { code: 'en', label: 'English' }],
    wiki: [{ code: 'es', label: 'Español' }, { code: 'en', label: 'English' }],
    eu:   [
      { code: 'es', label: 'Español' },
      { code: 'en', label: 'English' },
      { code: 'fr', label: 'Français' },
      { code: 'it', label: 'Italiano' },
      { code: 'pt', label: 'Português' },
    ],
  };
  ```
- **Estado `language`**: nuevo estado React para almacenar el idioma seleccionado, inicializado a `"es"`.
- **Memo `availableLanguages`**: calcula los idiomas disponibles según el caso de uso activo usando `useMemo`.
- **Effect de reseteo de idioma**: cuando el usuario cambia de caso de uso, si el idioma actual no está disponible en el nuevo caso de uso, se resetea automáticamente al primer idioma disponible (español).
- **Componente `<LanguageSelector>`**: renderizado en la cabecera (`<header>`), a la derecha del `UseCaseSelector`.
- **Prop `language` a `<ChatPanel>`**: se pasa el idioma seleccionado como propiedad al panel de chat.

#### 3.1.2. `frontend/src/components/LanguageSelector.js` *(nuevo fichero)*

Componente funcional React que renderiza un selector desplegable (`<select>`) con icono de globo 🌐.

```jsx
export default function LanguageSelector({ languages, activeLanguage, onChange }) {
  return (
    <div className="language-selector">
      <span className="language-selector__icon">🌐</span>
      <select
        className="language-selector__select"
        value={activeLanguage}
        onChange={(e) => onChange(e.target.value)}
        aria-label="Selector de idioma"
      >
        {languages.map(lang => (
          <option key={lang.code} value={lang.code}>{lang.label}</option>
        ))}
      </select>
    </div>
  );
}
```

**Props:**
| Prop             | Tipo       | Descripción                                    |
|------------------|------------|------------------------------------------------|
| `languages`      | `Array`    | Lista de `{ code, label }` con idiomas válidos |
| `activeLanguage` | `string`   | Código del idioma actualmente seleccionado     |
| `onChange`        | `function` | Callback invocado al cambiar el idioma         |

#### 3.1.3. `frontend/src/components/ChatPanel.js`

**Cambios realizados:**

- **Nueva prop `language`**: se recibe del componente padre `App`.
- **Envío del idioma en la petición**: en la función `sendMessage()`, se añade `form.append('language', language)` al `FormData` enviado al endpoint `/api/chat`.
- **Dependencia en `useCallback`**: se añade `language` al array de dependencias del hook `useCallback` de `sendMessage`.

#### 3.1.4. `frontend/src/App.css`

**Cambios realizados:**

Se añade un nuevo bloque CSS para el selector de idioma:

```css
.language-selector {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: 8px;
  flex-shrink: 0;
}

.language-selector__icon { font-size: 16px; }

.language-selector__select {
  background: var(--color-surface-2, #1e1e2e);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  color: var(--color-text);
  font-size: 13px;
  padding: 4px 8px;
  cursor: pointer;
}
```

El selector se posiciona a la derecha del `UseCaseSelector` en la cabecera, manteniendo coherencia visual con el tema oscuro de la aplicación.

---

### 3.2. Backend — API (FastAPI)

#### 3.2.1. `src/rag/main.py`

**Cambios realizados:**

- **Nuevo parámetro `language`** en el endpoint `POST /api/chat`:
  ```python
  language: Optional[str] = Form("es"),
  ```
  Se acepta como campo del formulario con valor por defecto `"es"` (español).

- **Propagación al pipeline RAG**:
  ```python
  result = rag_graph.run(
      ...,
      language=language or "es",
      ...
  )
  ```

---

### 3.3. Backend — Pipeline LangGraph

#### 3.3.1. `src/rag/app_langgraph.py`

**Cambios realizados:**

- **Campo `language` en `RAGState`**:
  ```python
  class RAGState(TypedDict):
      ...
      language: str  # "es" | "en" | "fr" | "it" | "pt"
      ...
  ```

- **Propagación al Retriever**: el estado del retriever ahora incluye `language`:
  ```python
  retriever_state = {
      ...,
      "language": state.get("language", "es"),
      ...
  }
  ```

- **Propagación al pipeline CVs**: tanto `process_query` como `format_final_response` reciben el idioma:
  ```python
  result = handler.process_query(query, chunks, language=state.get("language", "es"))
  answer, usage_info = handler.format_final_response(query, groups, language=state.get("language", "es"))
  ```

- **Estado inicial**: el campo `language` se incluye en la creación del estado inicial en `RAGGraph.run()`:
  ```python
  initial_state = RAGState(
      ...,
      language=language,
      ...
  )
  ```

- **Firma de `run()`**: añadido parámetro `language`:
  ```python
  def run(self, ..., language: str = "es", ...) -> Dict:
  ```

---

### 3.4. Backend — Retriever (Filtrado por idioma)

#### 3.4.1. `src/rag/models/retriever.py`

**Cambios realizados:**

- **Campo `language` en `RetrieverState`**:
  ```python
  class RetrieverState(TypedDict):
      ...
      language: str
      ...
  ```

- **Filtro OData en `hybrid_search()`**: se añade un filtro `sourceLanguage eq '{language}'` a las consultas de Azure AI Search:
  ```python
  def hybrid_search(self, query, use_case, top_k=10, language=None):
      filter_expr = None
      if language:
          filter_expr = f"sourceLanguage eq '{language}'"

      results = search_client.search(
          search_text=query,
          vector_queries=[...],
          filter=filter_expr,
          top=top_k,
          select=handler.search_select_fields,
      )
  ```
  Esto utiliza el campo `sourceLanguage` que ya existe como campo filtrable en los tres índices de Azure AI Search (CVs, EU, Wiki), definido en los scripts de creación de índices (`create_index_cvs.py`, `create_index_eu.py`, `create_index_wiki.py`).

- **Propagación en `rag_fusion_retrieve()`**: el parámetro `language` se propaga a cada llamada de `hybrid_search()`:
  ```python
  def rag_fusion_retrieve(self, queries, use_case, retrieval_cfg=None, language=None):
      ...
      futures = [executor.submit(self.hybrid_search, q, use_case, top_k, language) for q in queries]
  ```

- **Lectura del idioma en `retrieve()`**: el nodo de retrieval extrae el idioma del estado:
  ```python
  language = state.get("language", "es")
  chunks = self.rag_fusion_retrieve(synthetic_queries, use_case, retrieval_cfg, language=language)
  ```

---

### 3.5. Backend — Generador

#### 3.5.1. `src/rag/models/generator.py`

**Cambios realizados:**

- **Campo `language` en `GeneratorState`**: nuevo campo para transportar el idioma.
- **Propagación completa**: `generate()` → `generate_answer_with_context()` → `_generate_gpt()`, todas reciben `language`.
- **Uso en el prompt**: el idioma se pasa a `handler.build_generation_prompt(..., language=language)`, para que el prompt incluya la instrucción de responder en el idioma seleccionado.

---

### 3.6. Backend — Handlers

#### 3.6.1. `src/rag/handler/base.py`

**Cambios realizados:**

- **Eliminación de `LANG_NAMES` local**: el diccionario que antes se definía aquí se ha centralizado en `config.py` (ver sección 3.9).
- **Parámetro `language` en `build_generation_prompt()`**: el método abstracto ahora acepta el idioma:
  ```python
  @abstractmethod
  def build_generation_prompt(self, query, context, max_chars, language="es") -> str:
  ```

#### 3.6.2. `src/rag/handler/cvs_handler.py`

**Cambios realizados:**

- `build_generation_prompt()`: acepta y propaga `language` a los prompts.
- `process_query()`: acepta `language` y lo pasa al historial.
- `format_final_response()`: acepta `language` y lo pasa al prompt de respuesta final.

#### 3.6.3. `src/rag/handler/document_handler.py` *(nuevo — sustituye a `eu_handler.py` y `wiki_handler.py`)*

Handler unificado para los casos de uso documentales (EU y Wikipedia). En lugar de tener dos handlers separados con código prácticamente idéntico, se usa una única clase `DocumentHandler` parametrizada con un atributo `use_case` que determina qué clase de prompts se carga:

```python
class DocumentHandler(BaseUseCaseHandler):
    def __init__(self, use_case: str, index_name: str) -> None:
        self.use_case_id = use_case
        self.use_case    = use_case      # "eu" | "wiki"
        self.index_name  = index_name
        self.prompts     = _PROMPTS_MAP[use_case]()  # EUPrompts() o WikiPrompts()
```

**Mapeo interno:**

| `use_case` | Clase de prompts | System message |
|------------|-----------------|----------------|
| `"eu"` | `EUPrompts` | Experto en legislación UE, precisión legal |
| `"wiki"` | `WikiPrompts` | Asistente enciclopédico, conocimiento general |

**Registro en `__init__.py`:**
```python
_REGISTRY = {
    "cvs":  CVsUseCaseHandler(config.azure_search_index_cvs),
    "eu":   DocumentHandler("eu",   config.azure_search_index_eu),
    "wiki": DocumentHandler("wiki", config.azure_search_index_wiki),
}
```

Los ficheros `eu_handler.py` y `wiki_handler.py` quedan como código legado (no se importan desde ningún punto activo).

---

### 3.7. Backend — Prompts

Los ficheros de prompts `eu_prompts.py` y `wiki_prompts.py` se mantienen separados, ya que cada dominio requiere instrucciones específicas (precisión legal vs. estilo enciclopédico). Lo que cambia es que ya no definen `LANG_NAMES` localmente, sino que lo obtienen de `config`.

#### 3.7.1. `src/rag/prompts/cvs_prompts.py`

**Cambios realizados:**

- **Eliminación de `LANG_NAMES` local** → se importa `config` y se usa `config.get_lang_name(language)`.
- **`generation()`**: la instrucción de idioma pasa de texto fijo a:
  ```
  RESPONDE EN {config.get_lang_name(language).upper()}. Máximo {max_chars} caracteres.
  ```
- **`response_format()`**: la instrucción pasa a:
  ```
  Responde en {config.get_lang_name(language)}.
  ```

#### 3.7.2. `src/rag/prompts/eu_prompts.py`

**Cambios realizados:**

- **Eliminación de `LANG_NAMES` local** → se importa `config` y se usa `config.get_lang_name(language)`.
- **`generation()`**: la instrucción `[4] IDIOMA` pasa a:
  ```
  [4] IDIOMA: Responde en {config.get_lang_name(language)}.
  ```

#### 3.7.3. `src/rag/prompts/wiki_prompts.py`

**Cambios realizados:**

- **Eliminación de `LANG_NAMES` local** → se importa `config` y se usa `config.get_lang_name(language)`.
- **`generation()`**: misma lógica que EU:
  ```
  [4] IDIOMA: Responde en {config.get_lang_name(language)}.
  ```

---

### 3.8. Backend — Historial de CVs

#### 3.8.1. `src/rag/handler/cvs_history.py`

**Cambios realizados:**

- **Parámetro `language` en `add_entry()`**:
  ```python
  def add_entry(self, query, groups, language="es") -> str:
  ```

- **Persistencia del idioma**: cada entrada del historial ahora incluye el campo `"language"`:
  ```python
  entry = {
      "id":        entry_id,
      "timestamp": datetime.now(tz=timezone.utc).isoformat(),
      "question":  query,
      "language":  language,   # ← NUEVO
      "results":   results,
  }
  ```

**Ejemplo de entrada en `cvs_history.json` con el nuevo campo:**
```json
{
  "id": "a1b2c3d4-...",
  "timestamp": "2026-04-15T10:30:00+00:00",
  "question": "Find profiles with Python experience",
  "language": "en",
  "results": [
    {
      "reliability": 0.9,
      "data": ["John Smith", "Jane Doe"],
      "reasoning": "Both have 5+ years Python experience"
    }
  ]
}
```

---

## 4. Campo `sourceLanguage` en los índices de Azure AI Search

Los tres índices de Azure AI Search ya contienen el campo `sourceLanguage` como campo filtrable (`filterable=True`, `facetable=True`), definido en los scripts de creación de índices:

- `src/document_ingestion/cvs/create_index_cvs.py` → `SimpleField(name="sourceLanguage", type=SearchFieldDataType.String, filterable=True, facetable=True)`
- `src/document_ingestion/eu/create_index_eu.py` → ídem
- `src/document_ingestion/wiki/create_index_wiki.py` → ídem

Este campo se rellena durante la ingesta de documentos y contiene el código ISO 639-1 del idioma del documento fuente (por ejemplo, `"es"`, `"en"`, `"fr"`).

El filtrado se realiza mediante una expresión OData estándar de Azure AI Search:
```
sourceLanguage eq 'es'
```

Esta expresión se aplica tanto a la búsqueda textual (BM25) como a la búsqueda vectorial (k-NN), garantizando que solo se recuperen chunks del idioma seleccionado.

---

## 5. Compatibilidad hacia atrás

Todos los parámetros `language` tienen un valor por defecto de `"es"` (español), lo que garantiza que:

- Si el frontend no envía el campo `language`, el sistema se comporta exactamente igual que antes de la implementación.
- Si se llama al backend desde otro cliente (por ejemplo, una API REST directa) sin especificar idioma, se utiliza español por defecto.
- Las entradas antiguas del historial de CVs que no tienen el campo `language` siguen siendo válidas y legibles.

---

## 6. Centralización de `LANG_NAMES` en `config.py`

### 6.1. Motivación

Originalmente, el diccionario `LANG_NAMES` (mapeo de código ISO 639-1 a nombre legible del idioma) estaba duplicado en 4 ficheros distintos:
- `src/rag/handler/base.py`
- `src/rag/prompts/cvs_prompts.py`
- `src/rag/prompts/eu_prompts.py`
- `src/rag/prompts/wiki_prompts.py`

Esto violaba el principio DRY (Don't Repeat Yourself) y dificultaba añadir nuevos idiomas, ya que requería modificar todos los ficheros.

### 6.2. Solución

El diccionario se ha centralizado en `src/config.py` como atributo de `RAGConfig`, configurable mediante la variable de entorno `LANG_NAMES`:

```python
# En .env (opcional — si no se define, se usan los valores por defecto):
LANG_NAMES={"es": "español", "en": "English", "fr": "français", "it": "italiano", "pt": "português"}
```

```python
# En config.py:
class RAGConfig:
    _lang_names_raw: str = os.getenv(
        "LANG_NAMES",
        '{"es": "español", "en": "English", "fr": "français", "it": "italiano", "pt": "português"}',
    )
    lang_names: Dict[str, str] = None  # se inicializa en __post_init__

    def _load_lang_names(self):
        try:
            self.lang_names = json.loads(self._lang_names_raw)
        except (json.JSONDecodeError, TypeError):
            self.lang_names = {
                "es": "español", "en": "English",
                "fr": "français", "it": "italiano", "pt": "português",
            }

    def get_lang_name(self, code: str) -> str:
        return self.lang_names.get(code, "español")
```

### 6.3. Uso en los ficheros de prompts

Todos los ficheros de prompts ahora importan `config` y usan `config.get_lang_name(language)`:

```python
# Antes (en cada fichero de prompts):
LANG_NAMES = {"es": "español", "en": "English", ...}
# ... en el prompt:
f"Responde en {LANG_NAMES.get(language, 'español')}"

# Después:
from src.config import config
# ... en el prompt:
f"Responde en {config.get_lang_name(language)}"
```

### 6.4. Ficheros modificados

| Fichero | Cambio |
|---------|--------|
| `src/config.py` | Añadido `_lang_names_raw`, `lang_names`, `_load_lang_names()`, `get_lang_name()` |
| `src/rag/handler/base.py` | Eliminado `LANG_NAMES` local (no se usaba en este fichero) |
| `src/rag/prompts/cvs_prompts.py` | Eliminado `LANG_NAMES` → importa `config`, usa `config.get_lang_name()` |
| `src/rag/prompts/eu_prompts.py` | Eliminado `LANG_NAMES` → importa `config`, usa `config.get_lang_name()` |
| `src/rag/prompts/wiki_prompts.py` | Eliminado `LANG_NAMES` → importa `config`, usa `config.get_lang_name()` |

---

## 7. Unificación de handlers documentales (`DocumentHandler`)

### 7.1. Motivación

Los handlers `EUUseCaseHandler` (en `eu_handler.py`) y `WikiUseCaseHandler` (en `wiki_handler.py`) eran clases casi idénticas: ambas heredaban de `BaseUseCaseHandler`, definían los mismos métodos (`build_generation_prompt`, `build_rag_fusion_prompt`, `get_system_message`) y simplemente delegaban a su clase de prompts correspondiente. La única diferencia era qué clase de prompts instanciaban y el system message.

### 7.2. Solución: `DocumentHandler`

Se creó una única clase `DocumentHandler` en `src/rag/handler/document_handler.py` con un atributo `use_case` que determina qué prompts usa:

```python
_PROMPTS_MAP = {
    "eu":   EUPrompts,
    "wiki": WikiPrompts,
}

class DocumentHandler(BaseUseCaseHandler):
    def __init__(self, use_case: str, index_name: str) -> None:
        self.use_case_id = use_case
        self.use_case    = use_case      # "eu" | "wiki"
        self.index_name  = index_name
        self.prompts     = _PROMPTS_MAP[use_case]()
```

**Decisión de diseño**: los prompts `EUPrompts` y `WikiPrompts` se mantienen en ficheros separados (`eu_prompts.py` y `wiki_prompts.py`) porque los dominios son suficientemente distintos (precisión legal vs. estilo enciclopédico) como para justificar prompts independientes. Lo que se unifica es el handler, no los prompts.

### 7.3. Flujo RAG unificado para documentos

Tanto EU como Wiki siguen exactamente el mismo flujo RAG estándar (sin pipeline especializado como CVs):

```
retrieve → generate → [guardrails_output] → END
```

El pipeline CVs, en cambio, usa su propio nodo `process_cvs` con clasificación por fiabilidad y mini-LLM.

### 7.4. Registro de handlers

```python
# src/rag/handler/__init__.py
_REGISTRY = {
    "cvs":  CVsUseCaseHandler(config.azure_search_index_cvs),
    "eu":   DocumentHandler("eu",   config.azure_search_index_eu),
    "wiki": DocumentHandler("wiki", config.azure_search_index_wiki),
}
```

### 7.5. Ficheros afectados

| Fichero | Tipo de cambio | Descripción |
|---------|---------------|-------------|
| `src/rag/handler/document_handler.py` | **Nuevo** | Handler unificado con atributo `use_case` |
| `src/rag/handler/__init__.py` | Modificado | Registro usa `DocumentHandler` en lugar de `EUUseCaseHandler`/`WikiUseCaseHandler` |
| `src/rag/handler/eu_handler.py` | **Legado** | Ya no se importa; permanece como referencia |
| `src/rag/handler/wiki_handler.py` | **Legado** | Ya no se importa; permanece como referencia |

---

## 8. Resumen de ficheros modificados

| Fichero | Tipo de cambio | Descripción |
|---------|---------------|-------------|
| `frontend/src/App.js` | Modificado | Estado `language`, `LANGUAGES_BY_USE_CASE`, renderizado del `LanguageSelector` |
| `frontend/src/components/LanguageSelector.js` | **Nuevo** | Componente selector de idioma con dropdown |
| `frontend/src/components/ChatPanel.js` | Modificado | Envía `language` en FormData al backend |
| `frontend/src/App.css` | Modificado | Estilos para `.language-selector` |
| `src/config.py` | Modificado | `lang_names` centralizado (desde .env), `get_lang_name()` |
| `src/rag/main.py` | Modificado | Parámetro `language` en `/api/chat`, propagación a `rag_graph.run()` |
| `src/rag/app_langgraph.py` | Modificado | Campo `language` en `RAGState`, propagación completa |
| `src/rag/models/retriever.py` | Modificado | Filtro OData `sourceLanguage eq '...'` en Azure Search |
| `src/rag/models/generator.py` | Modificado | `language` en `GeneratorState`, propagación a prompts |
| `src/rag/handler/base.py` | Modificado | Eliminado `LANG_NAMES` local, `language` en `build_generation_prompt()` |
| `src/rag/handler/document_handler.py` | **Nuevo** | Handler unificado para EU y Wiki con atributo `use_case` |
| `src/rag/handler/__init__.py` | Modificado | Registro usa `DocumentHandler` |
| `src/rag/handler/cvs_handler.py` | Modificado | `language` en `build_generation_prompt()`, `process_query()`, `format_final_response()` |
| `src/rag/prompts/cvs_prompts.py` | Modificado | Usa `config.get_lang_name()` en lugar de `LANG_NAMES` local |
| `src/rag/prompts/eu_prompts.py` | Modificado | Usa `config.get_lang_name()` en lugar de `LANG_NAMES` local |
| `src/rag/prompts/wiki_prompts.py` | Modificado | Usa `config.get_lang_name()` en lugar de `LANG_NAMES` local |
| `src/rag/handler/cvs_history.py` | Modificado | Campo `"language"` en cada entrada del historial JSON |
