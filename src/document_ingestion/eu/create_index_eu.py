"""
src.document_ingestion.eu.create_index_eu

Crear índice y indexer de Azure Search **específico para legislación EU**
con búsqueda híbrida (Vector + Semantic + Keyword/BM25).

Campos clave para filtrado y búsqueda semántica — EU
-----------------------------------------------------
- **doc_type** (filterable / facetable):
      legislation | legislation-preparation | inter-agree
      → permite al agente restringir la búsqueda a un tipo de legislación.
- **sourceLanguage** (filterable / facetable):
      en, es, fr, pt, it
      → filtrar por idioma del documento EU.
- **content** (searchable):
      → texto del chunk, contenido principal de búsqueda.
- **Title** (searchable):
      → título de sección dentro del PDF.
- **docTitle** (searchable + filterable):
      → nombre del documento (blob name).

Configuración semántica
-----------------------
- title_field   : Title  (encabezado de sección)
- content_fields: content  (contenido legislativo)
- keywords_fields: docTitle, doc_type
"""
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    HnswParameters,
    VectorSearchAlgorithmMetric,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticSearch,
    SemanticPrioritizedFields,
    SemanticField,
    BM25SimilarityAlgorithm,
    SearchIndexer,
    SearchIndexerDataSourceConnection,
    SearchIndexerDataContainer,
    FieldMapping,
)
from azure.core.credentials import AzureKeyCredential
from src.config import config
from urllib.parse import quote_plus


# ===========================================================================
# Índice
# ===========================================================================

def create_search_index():
    """Crea el índice de Azure Search para EU con búsqueda híbrida."""

    client = SearchIndexClient(
        endpoint=config.azure_search_endpoint,
        credential=AzureKeyCredential(config.azure_search_key),
    )

    fields = [
        # === CAMPOS CLAVE ===
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="chunkId", type=SearchFieldDataType.String, filterable=True),

        # === CONTENIDO PRINCIPAL (keyword + semantic) ===
        SearchableField(
            name="content",
            type=SearchFieldDataType.String,
            # Usar analizador estándar porque tenemos 5 idiomas
            analyzer_name="standard.lucene",
        ),
        SearchableField(
            name="Title",
            type=SearchFieldDataType.String,
            analyzer_name="standard.lucene",
        ),
        SearchableField(
            name="docTitle",
            type=SearchFieldDataType.String,
            filterable=True,
            analyzer_name="standard.lucene",
        ),

        # === CAMPOS ESPECÍFICOS DE EU ===
        SimpleField(
            name="doc_type",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
        ),

        # === CAMPOS OPCIONALES ===
        SearchableField(
            name="QuestionsText",
            type=SearchFieldDataType.String,
            analyzer_name="standard.lucene",
        ),
        SearchableField(
            name="docSummary",
            type=SearchFieldDataType.String,
            analyzer_name="standard.lucene",
        ),

        # === CAMPOS FILTRABLES ===
        SimpleField(name="Pages", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="sourceLanguage", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="sourceCollection", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="sourcePath", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="topLanguage", type=SearchFieldDataType.String, filterable=True),
        SimpleField(
            name="nChunk",
            type=SearchFieldDataType.Int32,
            filterable=True,
            sortable=True,
        ),
        SimpleField(name="isDeleted", type=SearchFieldDataType.Boolean, filterable=True),
        SimpleField(
            name="isCreated",
            type=SearchFieldDataType.DateTimeOffset,
            filterable=True,
            sortable=True,
        ),

        # === VECTOR SEARCH ===
        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            vector_search_dimensions=1536,
            vector_search_profile_name="vector-profile-eu",
        ),

        # === SEMANTIC SEARCH ===
        SearchField(
            name="Sections",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True,
            filterable=False,
        ),
    ]

    # --- Vector Search ---
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="hnsw-algorithm-eu",
                parameters=HnswParameters(
                    metric=VectorSearchAlgorithmMetric.COSINE,
                    m=4,
                    ef_construction=400,
                    ef_search=500,
                ),
            )
        ],
        profiles=[
            VectorSearchProfile(
                name="vector-profile-eu",
                algorithm_configuration_name="hnsw-algorithm-eu",
            )
        ],
    )

    # --- Semantic Search ---
    semantic_config = SemanticConfiguration(
        name="semantic-config-eu",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="Title"),
            content_fields=[
                SemanticField(field_name="content"),
            ],
            keywords_fields=[
                SemanticField(field_name="docTitle"),
                SemanticField(field_name="doc_type"),
                SemanticField(field_name="Sections"),
            ],
        ),
    )
    semantic_search = SemanticSearch(configurations=[semantic_config])

    # --- Crear índice ---
    index = SearchIndex(
        name=config.azure_search_index_eu,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
        similarity=BM25SimilarityAlgorithm(),
    )

    result = client.create_or_update_index(index)
    print(f"✅ Índice EU creado: {result.name}")
    print(f"   - Vector Search: ✓  (HNSW / cosine)")
    print(f"   - Semantic Search: ✓ (title=Title, content=content, kw=docTitle+doc_type)")
    print(f"   - Keyword Search: ✓ (BM25)")
    print(f"   - Filtros: doc_type, sourceLanguage, isDeleted, Pages")
    print(f"   - Analyzer: standard.lucene (multilingual: en/es/fr/pt/it)")


# ===========================================================================
# Indexer (Cosmos DB → Azure Search)
# ===========================================================================

def create_indexer():
    """Crea el indexer que conecta Cosmos DB (Chunks-EU) → Azure Search."""

    indexer_client = SearchIndexerClient(
        endpoint=config.azure_search_endpoint,
        credential=AzureKeyCredential(config.azure_search_key),
    )

    cosmos_connection_string = (
        f"AccountEndpoint={config.cosmos_endpoint};"
        f"AccountKey={config.cosmos_key};"
        f"Database={config.cosmosdb_database}"
    )

    data_source = SearchIndexerDataSourceConnection(
        name=f"{config.azure_search_index_eu}-datasource",
        type="cosmosdb",
        connection_string=cosmos_connection_string,
        container=SearchIndexerDataContainer(name=config.cosmosdb_container_eu),
    )
    indexer_client.create_or_update_data_source_connection(data_source)
    print(f"✅ Data source EU creado: {data_source.name}")

    indexer = SearchIndexer(
        name=config.azure_search_indexer_eu,
        data_source_name=data_source.name,
        target_index_name=config.azure_search_index_eu,
        field_mappings=[
            FieldMapping(source_field_name="id", target_field_name="id"),
            FieldMapping(source_field_name="chunkId", target_field_name="chunkId"),
            FieldMapping(source_field_name="content", target_field_name="content"),
            FieldMapping(source_field_name="Title", target_field_name="Title"),
            FieldMapping(source_field_name="docTitle", target_field_name="docTitle"),
            FieldMapping(source_field_name="doc_type", target_field_name="doc_type"),
            FieldMapping(source_field_name="Pages", target_field_name="Pages"),
            FieldMapping(source_field_name="sourceLanguage", target_field_name="sourceLanguage"),
            FieldMapping(source_field_name="sourceCollection", target_field_name="sourceCollection"),
            FieldMapping(source_field_name="sourcePath", target_field_name="sourcePath"),
            FieldMapping(source_field_name="topLanguage", target_field_name="topLanguage"),
            FieldMapping(source_field_name="nChunk", target_field_name="nChunk"),
            FieldMapping(source_field_name="isDeleted", target_field_name="isDeleted"),
            FieldMapping(source_field_name="isCreated", target_field_name="isCreated"),
            FieldMapping(source_field_name="embedding", target_field_name="embedding"),
            FieldMapping(source_field_name="QuestionsText", target_field_name="QuestionsText"),
            FieldMapping(source_field_name="docSummary", target_field_name="docSummary"),
        ],
    )

    result = indexer_client.create_or_update_indexer(indexer)
    print(f"✅ Indexer EU creado: {result.name}")


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("CREANDO INFRAESTRUCTURA AZURE SEARCH — EU")
    print("=" * 70 + "\n")

    create_search_index()

    # Descomentar cuando estés listo para crear el indexer
    create_indexer()

    print("\n" + "=" * 70)
    print("COMPLETADO")
    print("=" * 70)
