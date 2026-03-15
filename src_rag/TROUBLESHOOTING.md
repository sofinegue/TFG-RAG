# 🔧 Troubleshooting - RAG Modular

Soluciones a problemas comunes durante la instalación y ejecución.

---

## 📦 Problemas de Instalación

### Error: Conflictos de dependencias

**Síntoma:**
```
ERROR: Cannot install -r requirements.txt because these package versions have conflicting dependencies.
```

**Solución 1: Usar versiones mínimas**
```bash
# Instalar con versiones mínimas (más flexible)
pip install -r requirements-minimal.txt
```

**Solución 2: Instalar manualmente por orden**
```bash
# 1. Instalar dependencias base
pip install python-dotenv pydantic typing-extensions

# 2. Instalar LangGraph y LangChain
pip install langgraph langchain-core

# 3. Instalar Azure
pip install azure-search-documents azure-core azure-storage-blob azure-identity

# 4. Instalar OpenAI
pip install openai

# 5. Instalar Streamlit
pip install streamlit

# 6. Verificar instalación
pip list | grep -E "langgraph|langchain|azure|openai|streamlit"
```

**Solución 3: Usar entorno virtual limpio**
```bash
# Crear nuevo entorno virtual
python -m venv venv_rag
source venv_rag/bin/activate  # Linux/Mac
# o
venv_rag\Scripts\activate  # Windows

# Actualizar pip
pip install --upgrade pip setuptools wheel

# Instalar requirements
pip install -r requirements.txt
```

**Solución 4: Instalar sin dependencias y resolver manualmente**
```bash
pip install --no-deps -r requirements.txt
pip install --upgrade pip
pip check  # Ver qué falta
pip install [paquetes_faltantes]
```

---

## 🔐 Problemas de Autenticación Azure

### Error: "Unauthorized" o "Access Denied"

**Síntoma:**
```
azure.core.exceptions.ClientAuthenticationError: Unauthorized
```

**Verificaciones:**
1. **Revisa las credenciales en .env**
   ```bash
   # Verifica que las variables estén configuradas
   cat .env | grep AZURE
   ```

2. **Verifica el formato del endpoint**
   ```bash
   # CORRECTO (sin "/" al final)
   AZURE_SEARCH_ENDPOINT="https://tu-servicio.search.windows.net"
   
   # INCORRECTO
   AZURE_SEARCH_ENDPOINT="https://tu-servicio.search.windows.net/"
   ```

3. **Verifica la API key**
   ```bash
   # La key debe ser la Admin Key, no Query Key
   # Encuéntrala en Azure Portal > Tu Search Service > Keys
   ```

4. **Test de conexión**
   ```python
   # test_azure_connection.py
   from azure.search.documents import SearchClient
   from azure.core.credentials import AzureKeyCredential
   import os
   from dotenv import load_dotenv
   
   load_dotenv()
   
   try:
       client = SearchClient(
           endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
           index_name=os.getenv("AZURE_SEARCH_INDEX"),
           credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY"))
       )
       results = client.search("test", top=1)
       print("✅ Conexión exitosa a Azure Search")
   except Exception as e:
       print(f"❌ Error: {e}")
   ```

---

## 🤖 Problemas con OpenAI

### Error: "Invalid API key"

**Solución:**
```bash
# Verifica que uses la key de Azure OpenAI, no OpenAI directo
# Azure OpenAI key se ve así: 1234567890abcdef...
# OpenAI key se ve así: sk-proj-...

# Test de conexión
python -c "
from openai import AzureOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv('AZURE_OPENAI_KEY'),
    api_version='2024-02-15-preview',
    azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT')
)

print('✅ Conexión OpenAI exitosa')
"
```

### Error: "Model not found"

**Solución:**
```bash
# Verifica que el modelo esté desplegado en tu instancia
# En Azure Portal: Tu OpenAI Resource > Model deployments

# El nombre del modelo debe coincidir EXACTAMENTE con el deployment name
CHAT_MODEL="gpt-4"  # Usa el nombre de TU deployment
```

---

## 📊 Problemas con LangGraph

### Error: "No attribute 'StateGraph'"

**Solución:**
```bash
# Actualiza LangGraph
pip install --upgrade langgraph langchain-core

# Verifica versión
python -c "import langgraph; print(langgraph.__version__)"
```

### Error: "checkpointer" argument

**Si usas versión antigua de LangGraph:**
```python
# appLangGraph.py - Cambiar línea de compilación

# NUEVO (LangGraph >= 0.2.0)
from langgraph.checkpoint.memory import MemorySaver
memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)

# ANTIGUO (si usas versión < 0.2.0)
graph = workflow.compile()
```

---

## 🎨 Problemas con Streamlit

### Error: "Command not found: streamlit"

**Solución:**
```bash
# Instalar o reinstalar Streamlit
pip install --upgrade streamlit

# Verificar instalación
streamlit --version

# Si sigue sin funcionar, usar python -m
python -m streamlit run webApp.py
```

### Puerto ocupado (8501)

**Solución:**
```bash
# Usar puerto alternativo
streamlit run webApp.py --server.port 8502

# O encontrar y matar proceso
# Linux/Mac
lsof -ti:8501 | xargs kill -9

# Windows
netstat -ano | findstr :8501
taskkill /PID [PID_NUMBER] /F
```

---

## 🔍 Problemas de Retrieval

### No se recuperan chunks

**Diagnóstico:**
```python
# test_retrieval.py
from models.retriever import Retriever

retriever = Retriever()

state = {
    "query": "test query",
    "user_id": "test",
    "chunks_retrieved": [],
    "synthetic_queries": [],
    "timestamps": {}
}

result = retriever.retrieve(state)
print(f"Chunks recuperados: {len(result['chunks_retrieved'])}")
print(f"Queries sintéticas: {result['synthetic_queries']}")
```

**Soluciones:**
1. **Verifica que el índice tenga documentos**
   ```python
   from azure.search.documents import SearchClient
   from azure.core.credentials import AzureKeyCredential
   import os
   
   client = SearchClient(
       endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
       index_name=os.getenv("AZURE_SEARCH_INDEX"),
       credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY"))
   )
   
   # Contar documentos
   results = client.search("*", include_total_count=True)
   print(f"Total documentos: {results.get_count()}")
   ```

2. **Ajusta el score mínimo**
   ```bash
   # En .env
   MIN_RELEVANCE_SCORE=0.5  # Reducir si no hay resultados
   ```

3. **Desactiva RAG Fusion temporalmente**
   ```bash
   USE_RAG_FUSION=false
   ```

---

## 💾 Problemas de Memoria

### Error: "Out of memory"

**Solución:**
```bash
# Reducir número de chunks
MAX_CHUNKS_USED=3
AZURE_SEARCH_TOP_K=5

# Reducir tamaño de respuesta
MAX_TOKENS=500
MAX_ANSWER_CHARS=500
```

---

## 🐛 Debug Mode

### Activar logging detallado

```python
# Al inicio de config.py
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/rag_debug.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

### Script de diagnóstico completo

```python
# diagnostico.py
import os
from dotenv import load_dotenv

load_dotenv()

print("="*60)
print("DIAGNÓSTICO DEL SISTEMA RAG")
print("="*60)

# 1. Verificar variables de entorno
print("\n1. Variables de entorno:")
required_vars = [
    "AZURE_SEARCH_ENDPOINT",
    "AZURE_SEARCH_KEY",
    "AZURE_SEARCH_INDEX",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_KEY",
    "CHAT_MODEL",
    "EMBEDDING_MODEL"
]

for var in required_vars:
    value = os.getenv(var)
    status = "✅" if value else "❌"
    masked = value[:10] + "..." if value and len(value) > 10 else value
    print(f"  {status} {var}: {masked}")

# 2. Verificar importaciones
print("\n2. Importaciones:")
modules = {
    "pydantic": "pydantic",
    "openai": "openai",
    "azure.search": "azure.search.documents",
    "langgraph": "langgraph",
    "streamlit": "streamlit"
}

for name, module in modules.items():
    try:
        __import__(module)
        print(f"  ✅ {name}")
    except ImportError as e:
        print(f"  ❌ {name}: {e}")

# 3. Test de conexiones
print("\n3. Conexiones:")

# Azure Search
try:
    from azure.search.documents import SearchClient
    from azure.core.credentials import AzureKeyCredential
    
    client = SearchClient(
        endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        index_name=os.getenv("AZURE_SEARCH_INDEX"),
        credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY"))
    )
    results = client.search("*", top=1)
    print("  ✅ Azure Search")
except Exception as e:
    print(f"  ❌ Azure Search: {e}")

# Azure OpenAI
try:
    from openai import AzureOpenAI
    
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_KEY"),
        api_version="2024-02-15-preview",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
    )
    print("  ✅ Azure OpenAI")
except Exception as e:
    print(f"  ❌ Azure OpenAI: {e}")

# 4. Test del grafo
print("\n4. Test del grafo RAG:")
try:
    from appLangGraph import rag_graph
    print("  ✅ Grafo inicializado")
    
    # Test básico
    result = rag_graph.run("test", user_id="diagnostic")
    print("  ✅ Ejecución exitosa")
except Exception as e:
    print(f"  ❌ Error: {e}")

print("\n" + "="*60)
print("FIN DEL DIAGNÓSTICO")
print("="*60)
```

**Ejecutar:**
```bash
python diagnostico.py
```

---

## 🆘 Soporte Adicional

Si ninguna solución funciona:

1. **Crea un issue con esta información:**
   - Versión de Python: `python --version`
   - Sistema operativo
   - Output de `pip list`
   - Mensaje de error completo
   - Output del script de diagnóstico

2. **Revisa logs:**
   ```bash
   # Ver últimos errores
   tail -f logs/rag_debug.log
   ```

3. **Entorno limpio:**
   ```bash
   # Última opción: reinstalación completa
   deactivate
   rm -rf venv
   python -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements-minimal.txt
   ```

---

## ✅ Checklist de Verificación

Antes de reportar un problema, verifica:

- [ ] Python >= 3.9
- [ ] Entorno virtual activado
- [ ] `.env` configurado correctamente
- [ ] Credenciales de Azure válidas
- [ ] Índice de Azure Search con documentos
- [ ] Modelo OpenAI desplegado
- [ ] Puertos disponibles (8501)
- [ ] Script de diagnóstico ejecutado

---

**¿Necesitas más ayuda?** Revisa el README.md o ejecuta `make help`