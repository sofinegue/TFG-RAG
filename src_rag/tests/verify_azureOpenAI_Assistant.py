"""
Script para verificar y listar assistants en Azure OpenAI
"""
import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_AGENT_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_AGENT_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_AGENT_API_VERSION", "2024-05-01-preview")
)

print("\n" + "="*60)
print("VERIFICACIÓN DE ASSISTANTS EN AZURE OPENAI")
print("="*60)

# Listar todos los assistants
print("\n📋 Listando assistants...")
try:
    assistants = client.beta.assistants.list(limit=20)
    
    if not assistants.data:
        print("❌ No hay assistants creados")
    else:
        print(f"✅ Encontrados {len(assistants.data)} assistant(s):\n")
        
        for i, asst in enumerate(assistants.data, 1):
            print(f"{i}. ID: {asst.id}")
            print(f"   Nombre: {asst.name}")
            print(f"   Modelo: {asst.model}")
            print(f"   Creado: {asst.created_at}")
            print(f"   Tools: {[tool.type for tool in asst.tools]}")
            
            # Verificar vector stores
            if hasattr(asst, 'tool_resources') and asst.tool_resources:
                if hasattr(asst.tool_resources, 'file_search') and asst.tool_resources.file_search:
                    vs_ids = asst.tool_resources.file_search.vector_store_ids
                    print(f"   Vector Stores: {vs_ids}")
                else:
                    print(f"   Vector Stores: None")
            else:
                print(f"   Vector Stores: None")
            print()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Verificar assistant específico del .env
print("\n" + "="*60)
assistant_id = os.getenv("AZURE_ASSISTANT_ID")

if assistant_id:
    print(f"🔍 Verificando assistant del .env: {assistant_id}")
    try:
        assistant = client.beta.assistants.retrieve(assistant_id)
        print(f"✅ Assistant encontrado!")
        print(f"   Nombre: {assistant.name}")
        print(f"   Modelo: {assistant.model}")
        print(f"   Estado: Activo")
    except Exception as e:
        print(f"❌ Assistant no encontrado: {e}")
else:
    print("⚠️  No hay AZURE_ASSISTANT_ID en .env")

print("="*60 + "\n")