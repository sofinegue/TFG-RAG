"""
Crear índice y indexer de Azure Search con búsqueda híbrida
(Vector Search + Semantic Search + Keyword Search)
"""
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.search.documents.indexes.models import *
from azure.core.credentials import AzureKeyCredential
from config import config
from urllib.parse import quote_plus


def create_search_index():
    """Crea el índice de Azure Search con búsqueda híbrida"""
    
    client = SearchIndexClient(
        endpoint=config.azure_search_endpoint,
        credential=AzureKeyCredential(config.azure_search_key)
    )
    
    # Definir campos del índice
    fields = [
        # === CAMPOS CLAVE ===
        SimpleField(
            name="id", 
            type=SearchFieldDataType.String, 
            key=True
        ),
        SimpleField(
            name="chunkId", 
            type=SearchFieldDataType.String, 
            filterable=True
        ),
        
        # === CAMPOS SEARCHABLE (para keyword + semantic) ===
        SearchableField(
            name="sectionContent", 
            type=SearchFieldDataType.String,
            analyzer_name="es.microsoft"  # Analizador en español
        ),
        SearchableField(
            name="Title", 
            type=SearchFieldDataType.String,
            analyzer_name="es.microsoft"
        ),
        SearchableField(
            name="docTitle", 
            type=SearchFieldDataType.String,
            filterable=True,
            analyzer_name="es.microsoft"
        ),
        
        # === CAMPOS OPCIONALES ===
        SearchableField(
            name="QuestionsText",
            type=SearchFieldDataType.String,
            analyzer_name="es.microsoft"
        ),
        SearchableField(
            name="docSummary",
            type=SearchFieldDataType.String,
            analyzer_name="es.microsoft"
        ),
        
        # === CAMPOS FILTRABLE ===
        SimpleField(
            name="Pages", 
            type=SearchFieldDataType.String, 
            filterable=True
        ),
        SimpleField(
            name="topLanguage", 
            type=SearchFieldDataType.String, 
            filterable=True
        ),
        SimpleField(
            name="nChunk",
            type=SearchFieldDataType.Int32,
            filterable=True,
            sortable=True
        ),
        SimpleField(
            name="isDeleted",
            type=SearchFieldDataType.Boolean,
            filterable=True
        ),
        SimpleField(
            name="isCreated",
            type=SearchFieldDataType.DateTimeOffset,
            filterable=True,
            sortable=True
        ),
        
        # === VECTOR SEARCH ===
        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            vector_search_dimensions=1536,  # ada-002
            vector_search_profile_name="vector-profile"
        ),
    ]
    
    # === CONFIGURACIÓN DE VECTOR SEARCH ===
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="hnsw-algorithm",
                parameters=HnswParameters(
                    metric=VectorSearchAlgorithmMetric.COSINE,
                    m=4,
                    ef_construction=400,
                    ef_search=500
                )
            )
        ],
        profiles=[
            VectorSearchProfile(
                name="vector-profile",
                algorithm_configuration_name="hnsw-algorithm"
            )
        ]
    )
    
    # === CONFIGURACIÓN SEMÁNTICA ===
    semantic_config = SemanticConfiguration(
        name="semantic-config",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="Title"),
            content_fields=[
                SemanticField(field_name="sectionContent"),
                SemanticField(field_name="QuestionsText"),
                SemanticField(field_name="docSummary")
            ],
            keywords_fields=[
                SemanticField(field_name="docTitle")
            ]
        )
    )
    
    semantic_search = SemanticSearch(
        configurations=[semantic_config]
    )
    
    # === CREAR ÍNDICE ===
    index = SearchIndex(
        name=config.azure_search_index,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
        similarity=BM25SimilarityAlgorithm()  # Algoritmo de ranking BM25
    )
    
    result = client.create_or_update_index(index)
    print(f"✅ Índice creado: {result.name}")
    print(f"   - Vector Search: ✓")
    print(f"   - Semantic Search: ✓")
    print(f"   - Keyword Search: ✓ (BM25)")


def create_indexer():
    """Crea el indexer que conecta Cosmos DB → Azure Search"""
    
    indexer_client = SearchIndexerClient(
        endpoint=config.azure_search_endpoint,
        credential=AzureKeyCredential(config.azure_search_key)
    )
    
    # URL-encode la Cosmos Key
    encoded_cosmos_key = quote_plus(config.cosmos_key)
    
    # Crear data source (Cosmos DB)
    cosmos_connection_string = (
        f"AccountEndpoint={config.cosmos_endpoint};"
        f"AccountKey={encoded_cosmos_key};"
        f"Database={config.cosmosdb_database}"
    )
    
    data_source = SearchIndexerDataSourceConnection(
        name=f"{config.azure_search_index}-datasource",
        type="cosmosdb",
        connection_string=cosmos_connection_string,
        container=SearchIndexerDataContainer(name=config.cosmosdb_container)
    )
    
    indexer_client.create_or_update_data_source_connection(data_source)
    print(f"✅ Data source creado: {data_source.name}")
    
    # Crear indexer con field mappings
    indexer = SearchIndexer(
        name=config.azure_search_index,
        data_source_name=data_source.name,
        target_index_name=config.azure_search_index,
        field_mappings=[
            # Mapeo directo de campos comunes
            FieldMapping(source_field_name="id", target_field_name="id"),
            FieldMapping(source_field_name="chunkId", target_field_name="chunkId"),
            FieldMapping(source_field_name="sectionContent", target_field_name="sectionContent"),
            FieldMapping(source_field_name="Title", target_field_name="Title"),
            FieldMapping(source_field_name="docTitle", target_field_name="docTitle"),
            FieldMapping(source_field_name="Pages", target_field_name="Pages"),
            FieldMapping(source_field_name="topLanguage", target_field_name="topLanguage"),
            FieldMapping(source_field_name="nChunk", target_field_name="nChunk"),
            FieldMapping(source_field_name="isDeleted", target_field_name="isDeleted"),
            FieldMapping(source_field_name="isCreated", target_field_name="isCreated"),
            FieldMapping(source_field_name="embedding", target_field_name="embedding"),
            
            # Campos opcionales (si existen en Cosmos)
            FieldMapping(source_field_name="QuestionsText", target_field_name="QuestionsText"),
            FieldMapping(source_field_name="docSummary", target_field_name="docSummary"),
        ]
    )
    
    result = indexer_client.create_or_update_indexer(indexer)
    print(f"✅ Indexer creado: {result.name}")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("CREANDO INFRAESTRUCTURA DE AZURE SEARCH")
    print("="*70 + "\n")
    
    create_search_index()
    
    # Descomentar cuando estés listo para crear el indexer
    # create_indexer()
    
    print("\n" + "="*70)
    print("COMPLETADO")
    print("="*70)