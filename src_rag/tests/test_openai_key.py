"""
Test con detalles completos del error de conexión - SIN VERIFICAR SSL
"""
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("AGENT_BUILDER_OPENAI_API_KEY")  # ✅ Cambiado a OPENAI_API_KEY

print("=" * 60)
print("DEBUG DE CONEXIÓN - SIN VERIFICAR SSL")
print("=" * 60)

if not api_key:
    print("❌ No hay API key en AGENT_BUILDER_OPENAI_API_KEY")
    # Intentar con el nombre alternativo
    api_key = os.getenv("AGENT_BUILDER_OPENAI_API_KEY")
    if api_key:
        print("⚠️  Encontrada en AGENT_BUILDER_OPENAI_API_KEY")
    else:
        print("\n💡 Asegúrate de tener en .env:")
        print("   OPENAI_API_KEY=sk-proj-tu-key-aqui")
        exit(1)

print(f"✅ API Key: {api_key[:20]}...")

# Test con más detalles - SIN VERIFICAR SSL
try:
    from openai import OpenAI
    import httpx
    import warnings
    
    # ✅ Silenciar warnings de SSL
    warnings.filterwarnings('ignore', message='Unverified HTTPS request')
    
    print("\n🔌 Intentando conectar SIN verificar SSL...")
    print(f"   Timeout: 30 segundos")
    print(f"   SSL Verify: FALSE (desactivado)")
    
    # ✅ Cliente con SSL desactivado
    client = OpenAI(
        api_key=api_key,
        timeout=30.0,
        max_retries=0,
        http_client=httpx.Client(
            timeout=30.0,
            verify=False  # ← DESACTIVA VERIFICACIÓN SSL
        )
    )
    
    print("\n   Enviando request de prueba...")
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Di solo: Test OK"}],
        max_tokens=10
    )
    
    print("\n🎉 ¡FUNCIONA!")
    print(f"   Respuesta: {response.choices[0].message.content}")
    print(f"   Modelo: {response.model}")
    print(f"   Tokens: {response.usage.total_tokens}")
    
    print("\n✅ El problema era el certificado SSL corporativo")
    print("   Solución aplicada: verify=False")

except Exception as e:
    print(f"\n❌ Error detallado:")
    print(f"   Tipo: {type(e).__name__}")
    print(f"   Mensaje: {str(e)}")
    
    # Ver el error interno
    if hasattr(e, '__cause__'):
        print(f"\n   Causa raíz: {type(e.__cause__).__name__}")
        print(f"   Detalle: {str(e.__cause__)}")
    
    # Traceback completo
    import traceback
    print("\n📋 Traceback completo:")
    traceback.print_exc()

print("\n" + "=" * 60)