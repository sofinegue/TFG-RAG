# TFG-RAG


## ./src/generate_data

The `generate_data` folder contains scripts for creating documents for the RAG (Retrieval-Augmented Generation) system. This folder includes:

- **Data creation scripts**: Tools for generating synthetic or processing raw data
- **Data validation utilities**: Scripts to verify data quality and integrity

This folder serves as the foundation for preparing training and operational datasets used throughout the TFG-RAG project.

To generate valid synthetic data, run:

    python -m src.generate_data.runner


## ./src/document_ingestion

The `document_ingestion` folder contains scripts for processing, chunking, and indexing all documents. It is organized into subfolders by document type (`cvs/`, `wiki/`, `eu/`), each following the same two-step pipeline:

### Paso 1 — Generar chunks y subirlos a Cosmos DB

Ejecutar el `runner_*.py` correspondiente. Este script lee los documentos desde Azure Blob Storage, los trocea en chunks y los sube a Cosmos DB.

    python -m src.document_ingestion.cvs.runner_cvs
    python -m src.document_ingestion.wiki.runner_wiki
    python -m src.document_ingestion.eu.runner_eu

### Paso 2 — Crear el índice y el indexer en Azure AI Search

Una vez los chunks están en Cosmos DB, ejecutar el `create_index_*.py` correspondiente. Este script crea el índice y el indexer en Azure AI Search, habilitando búsqueda vectorial y semántica sobre los chunks.

    python -m src.document_ingestion.cvs.create_index_cvs
    python -m src.document_ingestion.wiki.create_index_wiki
    python -m src.document_ingestion.eu.create_index_eu

> **Importante:** Siempre hay que ejecutar primero el `runner_*.py` antes que el `create_index_*.py`, ya que el indexer toma los datos de Cosmos DB.




# Documentation

## services

The `services` folder contains Azure service integrations for storage, database, AI processing, and embeddings.

### azure_storage_service.py
Azure Blob Storage and Table Storage operations for managing files and configurations.

**Functions:**
- `upload_json_config_to_blob(account_name, account_key, container_name, json_content, blob_name)` — Upload JSON configuration to blob storage with automatic .json extension handling
- `list_json_configs_from_blob(account_name, account_key, container_name, prefix)` — list all JSON blobs under a given prefix
- `download_json_config_from_blob(account_name, account_key, container_name, blob_name)` — Download and parse JSON configuration from blob
- `delete_json_config_from_blob(account_name, account_key, container_name, blob_name)` — Move blob to deleted container and remove
- `upload_blob_file_async(account_name, account_key, container_name, input_file, destination_blob, content_type)` — Async upload of binary files, returns BlobRef object
- `save_assistant_id_to_blob(assistant_key, assistant_id)` — Patch assistant_id into existing JSON configuration blob
- `get_specific_file_from_blob_container(account_name, account_key, container_name, specific_blob_name, ...)` — Async download with retry logic (3 attempts with exponential backoff)
- `generate_shared_access_signature_blob_files(blob_file_name, account_name, account_key, container_name)` — Generate 1-hour SAS URL for blob access
- `upload_assistant_config_to_blob(assistant_config, assistant_id)` — Wrapper for uploading assistant configurations
- `download_assistant_config_from_blob(assistant_id)` — Wrapper for downloading assistant configurations
- `list_assistant_configs_from_blob()` — list and validate all assistant configurations (checks for required fields: api_key, endpoint, deployment)
- `get_users_from_table(account_name, account_key, table_name, query_filter, select_fields)` — Query Azure Table Storage with filters and field selection

### cosmos_service.py
Cosmos DB operations for document storage and retrieval.

**Functions:**
- `cosmos_container_connection(key, endpoint, database_id, container_id)` — Establish connection to Cosmos DB container, returns container client
- `upload_doc_cosmos(endpoint, cosmos_key, dbname, container_db, data, session_id, call_id, cdu)` — Upsert document to Cosmos DB with optional Kibana logging
- `get_querys_cosmos(query, container_name, session_id, call_id, cdu)` — Execute SQL query with cross-partition support, returns list of results

### docintelligence_service.py
Azure Document Intelligence integration for extracting content from documents.

**Functions:**
- `get_content_from_document(file_download, SessionId, Call_id, retries, boolformulas)` — Async extraction using prebuilt-layout model with optional formula and language detection features. Includes automatic retry logic (up to 3 attempts with 5s delay). Returns analyzed document result in markdown format.

### openai_service.py
Azure OpenAI service for embeddings and chat completions.

**Functions:**
- `num_tokens_from_string(string)` — Count tokens in a string using tiktoken (gpt-4 encoding)
- `get_embedding(text, model, session_id, call_id, cdu, entity)` — Generate embedding vector using Azure OpenAI embedding model from MODELS_CONFIG
- `get_response_from_gpt(prompt, temperature, model, max_tokens, cdu, session_id, call_id, try_retry, entity, logit_bias)` — Generate chat completion using Azure OpenAI chat model from MODELS_CONFIG with configurable temperature and token limits

## models

The `models` folder contains Pydantic data models for validation and type safety.

### doc_model.py
Document processing models and status definitions.

**Classes:**
- **`DocStatus`** — Document status constants
  - `PENDING = 1` — Document awaiting processing
  - `PROCESSING = 2` — Document currently being processed
  - `PROCESSED = 3` — Document processing completed

- **`BlobRef(BaseModel)`** — Azure Blob reference metadata
  - `blob_name: str` — Full blob path in storage
  - `filename: str` — Original filename
  - `size: int` — File size in bytes
  - `content_type: Optional[str]` — MIME type

- **`Documento(BaseModel)`** — Basic document record
  - `id: str` — Unique document identifier
  - `status: int` — Current processing status (default: PENDING)
  - `doc_id: str` — Document ID
  - `doc_nombre: str` — Document name

- **`DocEntity(BaseModel)`** — Extended document entity with metadata for chunking pipeline
  - `id: Optional[str]` — Unique entity identifier
  - `doc_id: str` — Document ID
  - `doc_nombre: str` — Document name
  - `id_caso: str` — Case/collection identifier
  - `usuario: Optional[str]` — User who uploaded the document
  - `equipo: Optional[str]` — Team identifier
  - `source_collection: Optional[str]` — Source collection name (e.g., "eu", "cvs", "wikipedia")
  - `language: Optional[str]` — Document language (ISO 639-1 code)

- **`DocumentsToProcessREQ(BaseModel)`** — Batch document processing request
  - `id_llamada: str` — Call identifier
  - `id_caso: str` — Case identifier
  - `usuario: Optional[str]` — User identifier
  - `equipo: str` — Team identifier
  - `get_formula: bool` — Enable formula extraction (default: False)
  - `documentos: list[Documento]` — list of documents to process

## document_ingestion

The `document_ingestion` folder contains the complete pipeline for downloading, chunking, and indexing documents into the RAG system.

### doc_chunking.py
Main document processing pipeline entry point.

**Functions:**
- `get_text_split(blob_name, docId, get_formulas, SessionId, doc_entity, CDU)` — Complete document processing pipeline:
  1. Validates doc_entity using DocEntity Pydantic model
  2. Downloads document from Azure Blob Storage
  3. Extracts content using Azure Document Intelligence
  4. Labels content by page numbers
  5. Extracts tables and formulas
  6. Cleans content (removes headers/footers, false checkboxes)
  7. Splits content into chunks using markdown_percentage
  8. Uploads chunks to Cosmos DB with embeddings

### processchunks.py
Advanced text chunking algorithms and content processing utilities.

**Core Chunking Functions:**
- `markdown_percentage(content, chunk_size, chunk_overlap_percentage, min_tokens, max_tokens)` — Main text splitter using LangChain's MarkdownHeaderTextSplitter. Respects markdown headers, combines small splits, and handles table boundaries intelligently.
- `dividir_si_excede_max_tokens(split, max_tokens, chunk_size, chunk_overlap_percentage)` — Split chunks that exceed maximum token limit, with special handling for markdown tables
- `dividir_chunk_con_tablas(chunk, max_tokens, distancia_tokens)` — Table-aware chunk splitter that preserves table integrity
- `dividir_con_solapamiento(texto, longitud, solapamiento)` — Sliding window text splitter with configurable overlap (skips tables)
- `combinar_splits_tablas(sub_splits, max_tokens, distancia_maxima)` — Merge adjacent table-containing splits when within token limits

**Database Operations:**
- `upload_chunks(index, page_number, title, array, content, blob_name, topl, tables, formulas, doc_entity, SessionId, Call_id, CDU)` — Build chunk dictionary with metadata (including sourcePath, sourceCollection, sourceLanguage), generate embedding, and upload to Cosmos DB
- `mark_existing_chunks_as_deleted(doc_title, cosmos_endpoint, cosmos_key, db_name, container_name)` — Mark all existing chunks for a document as deleted before reprocessing (returns count of marked chunks)

**Content Cleaning:**
- `clean_false_checkbox(result, text, confidence)` — Remove low-confidence checkbox detections from Document Intelligence output
- `detect_and_remove_headers_footers(content, total_pages, avg, min_occurrences)` — Identify and remove repeated headers/footers across pages
- `detect_and_remove_duplicate_tables(markdown_text, total_pages, min_occurrences_percentage)` — Remove tables that appear repeatedly across document
- `eliminar_figuras_repetidas(texto)` — Remove repeated figure references from text

**Header Detection:**
- `detect_headers(content, level)` — Find all markdown headers of specified level (1-5)
- `detect_title(content)` — Extract last h1 header (#)
- `detect_subtitle(content)` — Extract last h2 header (##)
- `detect_threeheader(content)` — Extract last h3 header (###)
- `detect_fourheader(content)` — Extract last h4 header (####)
- `detect_fiveheader(content)` — Extract last h5 header (#####)

**Table Utilities:**
- `convert_table_to_markdown(table)` — Convert Azure Document Intelligence table object to markdown format
- `es_tabla_markdown(contenido)` — Detect if content contains markdown table syntax
- `extract_tables(markdown_text)` — Extract all markdown tables from text
- `compare_tables(table1, table2)` — Compare two tables for similarity
- `extract_pg_number(table)` — Extract page number from table content

**Metadata & Utilities:**
- `generate_chunkid(doctitle, content, title, page)` — Generate SHA256-based unique chunk identifier
- `get_top_locale(payload, default)` — Extract most common language from Document Intelligence result
- `get_most_common_locale(result)` — Get most frequent language from analysis result
- `get_first_60_percent(content)` — Extract first 60% of content
- `delete_noise(titles)` — Remove common noise patterns from title lists
- `normalize_text(text)` — Normalize text for comparison (lowercase, remove punctuation)

**Checkbox & Lote Detection:**
- `contains_checkbox(content)` — Check if content contains checkbox markers
- `contains_selected_checkbox(content)` — Check if content contains selected checkbox markers
- `contains_lote(content, sublotes_flag)` — Detect single lot reference
- `contains_lote_plural(content, sublotes_flag)` — Detect multiple lot references
- `extract_lotes(content, sublotes_flag)` — Extract all lot numbers from content
- `get_last_detected_lote(content)` — Get the last lot number mentioned

**Datapoint Extraction:**
- `load_datapoints(filename)` — Load datapoint definitions from JSON file
- `extract_datapoints(content, datapoints_list)` — Extract predefined datapoints from content
- `sort_key(value)` — Sort key function for lot numbers

### create_index.py
Azure AI Search index and indexer creation for hybrid search (vector + semantic + keyword).

**Functions:**
- `create_search_index()` — Create Azure AI Search index with:
  - HNSW vector search configuration (1536 dimensions)
  - Semantic search configuration with prioritized fields
  - BM25 keyword search
  - Fields: id, chunkId, sectionContent, Title, docTitle, QuestionsText, docSummary, Pages, topLanguage, nChunk, isDeleted, isCreated, embedding
  - Spanish language analyzer for text fields
  
- `create_indexer()` — Create Azure Search indexer with:
  - Cosmos DB datasource connection
  - Field mappings for automatic indexing
  - Scheduled or on-demand execution

### run_utils.py
Shared utilities for document ingestion runners (reusable across EU, CVs, and Wikipedia).

**Constants:**
- `EXTENSIONS_DOCS` — Frozenset of document extensions: {".pdf", ".txt"}
- `EXTENSIONS_JSON` — Frozenset of JSON extension: {".json"}
- `EXTENSIONS_ALL` — Frozenset of all supported extensions: {".pdf", ".txt", ".json"}

**Functions:**
- `collect_local_files(local_folder, allowed_exts, recursive)` — Scan directory and return sorted list of files filtered by extension
- `add_common_args(parser)` — Add standard CLI arguments to argparse parser: --language, --limit, --dry-run, --session-id
- `generate_session_id(prefix, language)` — Generate timestamped session ID (format: PREFIX_LANG_YYYYMMDD_HHMMSS)
- `print_run_summary(local_folder, language, files, session_id, blob_prefix)` — Print formatted console summary before processing

### run_eu.py
CLI runner for chunking EU regulatory documents by language.

**Functions:**
- `build_args()` — Parse CLI arguments including --get-formulas flag for formula extraction
- `main()` — Process all documents in data/eu/<language>/:
  - Validates folder exists
  - Collects files (.pdf, .txt)
  - Applies --limit if specified
  - Creates DocEntity for each file
  - Calls get_text_split for processing
  - Supports --dry-run mode

**Usage:**
```bash
python -m document_ingestion.run_eu --language es
python -m document_ingestion.run_eu --language fr --limit 10 --get-formulas
```

### run_cvs.py
CLI runner for chunking CV JSON documents by language.

**Functions:**
- `build_args()` — Parse CLI arguments (standard flags only)
- `main()` — Process all CV files in data/cvs/<language>/:
  - Validates folder exists
  - Collects JSON files only
  - Creates DocEntity with source_collection="cvs"
  - Calls get_cv_text_split (currently mocked)
  - Supports --dry-run mode

**Usage:**
```bash
python -m document_ingestion.run_cvs --language es
python -m document_ingestion.run_cvs --language en --limit 5 --dry-run
```

### run_wikipedia.py
CLI runner for chunking Wikipedia articles by language and format.

**Functions:**
- `build_args()` — Parse CLI arguments including --format (json, txt, or all)
- `collect_wikipedia_files(language_folder, fmt)` — Collect files from both json/ and txt/ subdirectories based on format selection
- `main()` — Process all Wikipedia articles in data/wikipedia/<language>/:
  - Validates folder exists
  - Collects files from json/ and/or txt/ subfolders
  - Preserves subfolder structure in blob path
  - Creates DocEntity with source_collection="wikipedia"
  - Calls get_wikipedia_text_split (currently mocked)
  - Supports --dry-run mode

**Usage:**
```bash
python -m document_ingestion.run_wikipedia --language en
python -m document_ingestion.run_wikipedia --language en --format json --limit 20
```

### cv_text_split.py
> **Superseded** by `cvs/doc_chunking_cvs.py`. Kept for reference.

Original CV-specific chunking pipeline.

---

### cvs/ (package)
Self-contained CV chunking sub-package. Downloads structured CV JSONs from Azure Blob Storage, splits each into 3 semantic chunks, generates embeddings, and uploads to Cosmos DB.

#### cvs/doc_chunking_cvs.py
Main CV chunking pipeline entry point.

**Functions:**
- `get_text_split_cv(docId, SessionId, doc_entity, CDU)` — Complete CV processing pipeline:
  1. Download CV JSON from Azure Blob Storage (`data/cvs/<lang>/cv_XXX.json`)
  2. Parse JSON into `CVProcessor` instance
  3. Mark existing chunks as deleted in Cosmos DB (prevents duplicates)
  4. Generate 3 semantic chunks via `CVProcessor.generate_semantic_chunks()`
  5. Merge chunk-specific metadata with global CV metadata
  6. Generate embedding vector for each chunk (Azure OpenAI `text-embedding-ada-002`)
  7. Upload all 3 chunks to Cosmos DB container `Chunks-CVs`

**Cosmos Document Schema (per chunk):**
```
id, chunkId, docTitle, sourcePath, sourceCollection("cvs"),
sourceLanguage, sectionContent, QuestionsText, docSummary,
Content_length, isCreated, Pages, Title, Sections, nChunk,
isDeleted, topLanguage, Tables, Formulas, embedding[], metadata{}
```

**Helper Functions:**
- `_generate_chunk_id(blob_name, chunk_type, chunk_index)` — Deterministic MD5-based chunk ID
- `_safe_cosmos_id()` — UUID sanitized for Azure Search (alphanumeric + `_`, `-`, `=`)

#### cvs/processchunks_cvs.py
CV-specific semantic chunking and metadata generation.

**Chunking Strategy**: Each CV is split into **3 semantic chunks**:
1. **Experience** (`experience`) — `sectionContent` = puesto + experiencia + otros
2. **Education** (`education`) — `sectionContent` = estudios + hard_skills + otros
3. **Skills** (`skills`) — `sectionContent` = hard_skills + soft_skills + otros

Each chunk includes the candidate's `nombre_apellidos` for cross-referencing.

**Classes:**
- **`CVProcessor`** — Structured CV data processor
  - `nombre_apellidos: str` — Full name
  - `puesto: str` — Job position
  - `experiencia: list[str]` — Professional experience entries
  - `estudios: list[str]` — Education entries
  - `hard_skills: list[str]` — Technical skills (accepts `"hard_skills"` or `"hard skills"`)
  - `soft_skills: list[str]` — Soft/transversal skills
  - `otros: list[str]` — Additional information (languages, certifications, etc.)

**Methods:**
- `from_dict(cls, d)` — Class method to construct CVProcessor from raw dictionary
- `generate_semantic_chunks()` — Generate all 3 chunks (experience, education, skills)
- `generate_experience_chunk()` — Experience chunk with `years_of_experience` metadata
- `generate_education_chunk()` — Education chunk with estudios + hard_skills
- `generate_skills_chunk()` — Skills chunk with hard + soft skills
- `get_global_metadata(language)` — Global CV metadata (name, position, years of experience)
- `calculate_years_of_experience()` — Parse date ranges in experience entries to estimate total years

### runner.py
CLI runner for batch processing all CV JSONs from Azure Blob Storage into Cosmos DB.

**Functions:**
- `run_cv_chunking(language)` — Process all CVs for a given language:
  - lists all JSON blobs under `data/cvs/<language>/`
  - Creates `DocEntity` per CV with `cv_id = <lang>/cv_XXX.json`
  - Calls `get_text_split_cv` for each CV
  - Prints summary with OK/error counts
- `main(language)` — Entry point: processes given language or auto-discovers all languages
- `_list_cv(language)` — list all JSON blobs under `data/cvs/<language>/`
- `_discover_languages()` — Auto-discover available languages by scanning blob prefixes
- `_generate_session_id(language)` — Generate timestamped session ID (`CVS_ES_YYYYMMDD_HHMMSS`)

**Usage:**
```bash
python -m src.document_ingestion.runner                  # all languages (auto-discover)
python -m src.document_ingestion.runner --language es     # Spanish only
python -m src.document_ingestion.runner --language en     # English only
```

### wikipedia_text_split.py
Wikipedia article chunking pipeline (mocked - implementation planned).

**Functions:**
- `get_wikipedia_text_split(blob_name, doc_id, doc_entity, session_id, call_id, cdu)` — Process Wikipedia article into chunks. **Implementation roadmap:**
  1. Download article from Blob Storage (JSON or TXT)
  2. Extract and clean content (remove infoboxes, citations)
  3. Restructure as Markdown with proper headers
  4. Split using markdown_percentage
  5. Generate embeddings and upload chunks to Cosmos DB

## doc_ingestion

The `doc_ingestion` folder contains specialized tools for CV and local file content extraction.

### cv_chunking.py
> **Note:** The `CVProcessor` class has been moved to `document_ingestion/cvs/processchunks_cvs.py` as the canonical implementation. This file is kept for reference and local testing.

Original CV semantic chunking prototype with local file loading.

**Utility Functions:**
- `load_json(path)` — Load JSON file with UTF-8 encoding

### content_extraction.py
Local file content extraction without Azure Document Intelligence (uses PyMuPDF).

**Functions:**
- `extract_pdf_content(file_pdf)` — Extract text content from PDF using PyMuPDF/fitz, returns dict with content, pages, tables, paragraphs
- `extract_txt_or_json_content(path)` — Read text or JSON files directly, returns standardized content dict
- `extract_content(path)` — Route extraction based on file extension (.pdf → fitz, .txt/.json → text reader)
- `show_content(content)` — Debug print extracted content dictionary