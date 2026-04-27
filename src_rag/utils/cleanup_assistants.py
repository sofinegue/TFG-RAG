"""
Script para limpiar assistants no usados en Azure OpenAI
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

# Assistant que QUEREMOS MANTENER
KEEP_ASSISTANT_ID = os.getenv("AZURE_ASSISTANT_ID")

print("\n" + "="*60)
print("LIMPIEZA DE ASSISTANTS EN AZURE OPENAI")
print("="*60)

# Listar todos
assistants = client.beta.assistants.list(limit=50)

print(f"\n📋 Encontrados {len(assistants.data)} assistant(s)")
print(f"✅ Mantendremos: {KEEP_ASSISTANT_ID}\n")

to_delete = []

for asst in assistants.data:
    if asst.id == KEEP_ASSISTANT_ID:
        print(f"✅ MANTENER: {asst.id} - {asst.name}")
    else:
        print(f"❌ ELIMINAR: {asst.id} - {asst.name}")
        to_delete.append(asst)

if not to_delete:
    print("\n✅ No hay assistants para eliminar")
else:
    print(f"\n⚠️  Se eliminarán {len(to_delete)} assistant(s)")
    response = input("¿Continuar? (yes/no): ")
    
    if response.lower() in ['yes', 'y', 'si', 's']:
        for asst in to_delete:
            try:
                client.beta.assistants.delete(asst.id)
                print(f"   ✅ Eliminado: {asst.id}")
            except Exception as e:
                print(f"   ❌ Error eliminando {asst.id}: {e}")
        print("\n✅ Limpieza completada")
    else:
        print("\n❌ Operación cancelada")

print("="*60 + "\n")