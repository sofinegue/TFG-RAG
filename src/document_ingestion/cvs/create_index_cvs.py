"""
src.document_ingestion.cvs.create_index_cvs

Crear índice y indexer de Azure Search **específico para CVs**
con búsqueda híbrida (Vector + Semantic + Keyword/BM25).

Campos clave para filtrado y búsqueda semántica
------------------------------------------------
- **chunk_type** (filterable):  experience | education | skills
      → permite al agente restringir la búsqueda a un tipo de sección.
- **nombre_apellidos** (searchable + filterable):
      → búsqueda y filtrado por nombre del candidato.
- **puesto** (searchable + filterable):
      → búsqueda y filtrado por puesto / rol objetivo.
- **sourceLanguage** (filterable):
      → filtrar por idioma del CV (es, en …).
- **sourceCollection** (filterable):
      → siempre "cvs"; útil si se comparte índice en el futuro.

Configuración semántica
-----------------------
- title_field   : Title  (e.g. "Juan Pérez — Experience")
- content_fields: content  (el texto real del chunk)
- keywords_fields: puesto, chunk_type  (mejoran reranking semántico)
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


# ===========================================================================
# Índice
# ===========================================================================

def create_search_index():
    """Crea el índice de Azure Search para CVs con búsqueda híbrida."""

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
            name="content",  # raw text of all the chunk
            type=SearchFieldDataType.String,
            analyzer_name="es.microsoft",
        ),
        SearchableField(
            name="Title",  # "Matthew Flores Wallace — Education"
            type=SearchFieldDataType.String,
            analyzer_name="es.microsoft",
        ),
        SearchableField(
            name="docTitle",  # "en/cv_297.json"
            type=SearchFieldDataType.String,
            filterable=True,
            analyzer_name="es.microsoft",
        ),

        # === CAMPOS ESPECÍFICOS DE CV ===
        SimpleField(
            name="chunk_type",  # "education"
            type=SearchFieldDataType.String,
            filterable=True,       # experience | education | skills
            facetable=True,
        ),
        SearchableField(
            name="nombre_apellidos",  # "Matthew Flores Wallace" 
            type=SearchFieldDataType.String,
            filterable=True,
            analyzer_name="es.microsoft",
        ),
        SearchableField(  # NO ESTÁ SI chunk_type = educacion
            name="puesto",  # "AI Research Scientist"
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
            analyzer_name="es.microsoft",
        ),

        # === CAMPOS OPCIONALES (compatibilidad con pipeline genérico) ===
        SearchableField(
            name="QuestionsText",
            type=SearchFieldDataType.String,
            analyzer_name="es.microsoft",
        ),
        SearchableField(
            name="docSummary",
            type=SearchFieldDataType.String,
            analyzer_name="es.microsoft",
        ),

        # === CAMPOS FILTRABLES ===
        # SimpleField(name="Pages", type=SearchFieldDataType.String, filterable=True),
        SimpleField(
            name="Content_length",
            type=SearchFieldDataType.Int32,
            filterable=True,
            sortable=True,
        ),
        SimpleField(name="sourceLanguage", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="sourceCollection", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="sourcePath", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="topLanguage", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="nChunk", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
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
            vector_search_dimensions=1536,  # text-embedding-ada-002
            vector_search_profile_name="vector-profile-cvs",
        ),
    ]

    # --- Vector Search ---
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="hnsw-algorithm-cvs",
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
                name="vector-profile-cvs",
                algorithm_configuration_name="hnsw-algorithm-cvs",
            )
        ],
    )

    # --- Semantic Search ---
    semantic_config = SemanticConfiguration(
        name="semantic-config-cvs",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="Title"),
            content_fields=[
                SemanticField(field_name="content"),
            ],
            keywords_fields=[
                SemanticField(field_name="puesto"),
                SemanticField(field_name="nombre_apellidos"),
                SemanticField(field_name="chunk_type"),
            ],
        ),
    )
    semantic_search = SemanticSearch(configurations=[semantic_config])

    # --- Crear índice ---
    index = SearchIndex(
        name=config.azure_search_index_cvs,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
        similarity=BM25SimilarityAlgorithm(),
    )

    result = client.create_or_update_index(index)
    print(f"✅ Índice CVs creado: {result.name}")
    print(f"   - Vector Search: ✓  (HNSW / cosine)")
    print(f"   - Semantic Search: ✓ (title=Title, content=content, kw=puesto+nombre)")
    print(f"   - Keyword Search: ✓ (BM25)")
    print(f"   - Filtros: chunk_type, nombre_apellidos, puesto, sourceLanguage, isDeleted")


# ===========================================================================
# Indexer (Cosmos DB → Azure Search)
# ===========================================================================

def create_indexer():
    """Crea el indexer que conecta Cosmos DB (Chunks-CVs) → Azure Search."""

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
        name=f"{config.azure_search_index_cvs}-datasource",
        type="cosmosdb",
        connection_string=cosmos_connection_string,
        container=SearchIndexerDataContainer(name=config.cosmosdb_container_cvs),
    )
    indexer_client.create_or_update_data_source_connection(data_source)
    print(f"✅ Data source CVs creado: {data_source.name}")

    indexer = SearchIndexer(
        name=config.azure_search_indexer_cvs,
        data_source_name=data_source.name,
        target_index_name=config.azure_search_index_cvs,
        field_mappings=[
            FieldMapping(source_field_name="id", target_field_name="id"),
            FieldMapping(source_field_name="chunkId", target_field_name="chunkId"),
            FieldMapping(source_field_name="content", target_field_name="content"),
            FieldMapping(source_field_name="Title", target_field_name="Title"),
            FieldMapping(source_field_name="docTitle", target_field_name="docTitle"),
            FieldMapping(source_field_name="chunk_type", target_field_name="chunk_type"),
            FieldMapping(source_field_name="nombre_apellidos", target_field_name="nombre_apellidos"),
            FieldMapping(source_field_name="puesto", target_field_name="puesto"),
            # Pages comentado en el índice → no mapear
            FieldMapping(source_field_name="Content_length", target_field_name="Content_length"),
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
    print(f"✅ Indexer CVs creado: {result.name}")


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("CREANDO INFRAESTRUCTURA AZURE SEARCH — CVs")
    print("=" * 70 + "\n")

    create_search_index()

    # Descomentar cuando estés listo para crear el indexer
    create_indexer()

    print("\n" + "=" * 70)
    print("COMPLETADO")
    print("=" * 70)