"""
verify_index.py - Verificar configuración del índice
"""
from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential
from config import config

client = SearchIndexClient(
    endpoint=config.azure_search_endpoint,
    credential=AzureKeyCredential(config.azure_search_key)
)

index = client.get_index(config.azure_search_index)

print(f"\n{'='*70}")
print(f"ÍNDICE: {index.name}")
print(f"{'='*70}\n")

# Vector Search
if index.vector_search:
    print("✅ Vector Search configurado")
    if index.vector_search.profiles:
        for profile in index.vector_search.profiles:
            print(f"   - Profile: {profile.name}")
    if index.vector_search.algorithms:
        for algo in index.vector_search.algorithms:
            print(f"   - Algorithm: {algo.name}")
else:
    print("❌ Vector Search NO configurado")

print()

# Semantic Search
if index.semantic_search:
    if index.semantic_search.configurations:
        print("✅ Semantic Search configurado")
        for sem_config in index.semantic_search.configurations:
            print(f"   - Config: {sem_config.name}")
            if sem_config.prioritized_fields:
                pf = sem_config.prioritized_fields
                if pf.title_field:
                    print(f"     Title: {pf.title_field.field_name}")
                if pf.content_fields:
                    print(f"     Content: {[f.field_name for f in pf.content_fields]}")
                if pf.keywords_fields:
                    print(f"     Keywords: {[f.field_name for f in pf.keywords_fields]}")
    else:
        print("⚠️  Semantic Search está habilitado pero sin configuraciones")
else:
    print("❌ Semantic Search NO configurado")

print()

# Similarity
if index.similarity:
    print(f"Similarity: {type(index.similarity).__name__}")
else:
    print("Similarity: Default")

print(f"\n{'='*70}\n")