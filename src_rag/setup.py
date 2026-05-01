"""
Script de setup interactivo para configurar el proyecto RAG
"""

import os
import sys
from pathlib import Path


def print_header(text):
    """Imprime un header decorado"""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70 + "\n")


def print_step(number, text):
    """Imprime un paso numerado"""
    print(f"\n{'='*5} PASO {number}: {text} {'='*5}\n")


def check_python_version():
    """Verifica la versión de Python"""
    print_step(1, "Verificando versión de Python")
    
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print("❌ Error: Se requiere Python 3.9 o superior")
        print(f"   Versión actual: {version.major}.{version.minor}.{version.micro}")
        return False
    
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} detectado")
    return True


def create_directories():
    """Crea los directorios necesarios"""
    print_step(2, "Creando estructura de directorios")
    
    directories = [
        "models",
        "logs",
        "data",
        "tests",
        "prompt_templates"  # Por si se quieren usar archivos externos
    ]
    
    for directory in directories:
        path = Path(directory)
        if not path.exists():
            path.mkdir(parents=True)
            print(f"✅ Creado: {directory}/")
        else:
            print(f"ℹ️  Ya existe: {directory}/")


def setup_env_file():
    """Configura el archivo .env de forma interactiva"""
    print_step(3, "Configuración de variables de entorno")
    
    if Path(".env").exists():
        response = input("\n⚠️  El archivo .env ya existe. ¿Sobrescribir? (s/N): ")
        if response.lower() != 's':
            print("ℹ️  Manteniendo .env existente")
            return
    
    print("\n📝 Por favor, proporciona la siguiente información:")
    print("   (Presiona Enter para usar valores por defecto)\n")
    
    # Recopilar información
    config = {}
    
    # Cliente
    config['CLIENT_NAME'] = input("Nombre del cliente [Demo Client]: ").strip() or "Demo Client"
    config['PROJECT_NAME'] = input("Nombre del proyecto [RAG Assistant]: ").strip() or "RAG Assistant"
    config['LANGUAGE'] = input("Idioma (es/en/pt) [es]: ").strip() or "es"
    
    print("\n🔐 Credenciales de Azure Search:")
    config['AZURE_SEARCH_ENDPOINT'] = input("  Endpoint: ").strip()
    config['AZURE_SEARCH_KEY'] = input("  API Key: ").strip()
    config['AZURE_SEARCH_INDEX'] = input("  Nombre del índice: ").strip()
    
    print("\n🔐 Credenciales de Azure OpenAI:")
    config['AZURE_OPENAI_ENDPOINT'] = input("  Endpoint: ").strip()
    config['AZURE_OPENAI_KEY'] = input("  API Key: ").strip()
    config['CHAT_MODEL'] = input("  Modelo de chat [gpt-4]: ").strip() or "gpt-4"
    config['EMBEDDING_MODEL'] = input("  Modelo de embeddings [text-embedding-ada-002]: ").strip() or "text-embedding-ada-002"
    
    print("\n⚙️  Configuración avanzada (opcional):")
    config['UI_THEME_COLOR'] = input("  Color del tema (hex) [#1f77b4]: ").strip() or "#1f77b4"
    config['USE_RAG_FUSION'] = input("  Usar RAG Fusion? (true/false) [true]: ").strip() or "true"
    config['MAX_CHUNKS_USED'] = input("  Máximo de chunks [5]: ").strip() or "5"
    
    # Escribir archivo .env
    with open(".env", "w") as f:
        f.write("# ============================================\n")
        f.write("# CONFIGURACIÓN RAG MODULAR\n")
        f.write(f"# Proyecto: {config['PROJECT_NAME']}\n")
        f.write(f"# Cliente: {config['CLIENT_NAME']}\n")
        f.write("# ============================================\n\n")
        
        f.write("# === IDENTIDAD DEL CLIENTE ===\n")
        f.write(f"CLIENT_NAME=\"{config['CLIENT_NAME']}\"\n")
        f.write(f"PROJECT_NAME=\"{config['PROJECT_NAME']}\"\n")
        f.write(f"LANGUAGE=\"{config['LANGUAGE']}\"\n\n")
        
        f.write("# === AZURE SEARCH ===\n")
        f.write(f"AZURE_SEARCH_ENDPOINT=\"{config['AZURE_SEARCH_ENDPOINT']}\"\n")
        f.write(f"AZURE_SEARCH_KEY=\"{config['AZURE_SEARCH_KEY']}\"\n")
        f.write(f"AZURE_SEARCH_INDEX=\"{config['AZURE_SEARCH_INDEX']}\"\n")
        f.write("AZURE_SEARCH_TOP_K=10\n\n")
        
        f.write("# === AZURE OPENAI ===\n")
        f.write(f"AZURE_OPENAI_ENDPOINT=\"{config['AZURE_OPENAI_ENDPOINT']}\"\n")
        f.write(f"AZURE_OPENAI_KEY=\"{config['AZURE_OPENAI_KEY']}\"\n")
        f.write("AZURE_OPENAI_API_VERSION=\"2024-02-15-preview\"\n\n")
        
        f.write("# === MODELOS ===\n")
        f.write(f"CHAT_MODEL=\"{config['CHAT_MODEL']}\"\n")
        f.write(f"EMBEDDING_MODEL=\"{config['EMBEDDING_MODEL']}\"\n")
        f.write("TEMPERATURE=0.3\n")
        f.write("MAX_TOKENS=1500\n\n")
        
        f.write("# === CONFIGURACIÓN RAG ===\n")
        f.write(f"USE_RAG_FUSION={config['USE_RAG_FUSION']}\n")
        f.write("RAG_FUSION_QUERIES=5\n")
        f.write(f"MAX_CHUNKS_USED={config['MAX_CHUNKS_USED']}\n")
        f.write("MIN_RELEVANCE_SCORE=0.7\n\n")
        
        f.write("# === GENERACIÓN ===\n")
        f.write("MAX_ANSWER_CHARS=1200\n")
        f.write("INCLUDE_SOURCES=true\n")
        f.write("STREAM_RESPONSE=false\n\n")
        
        f.write("# === UI ===\n")
        f.write(f"UI_THEME_COLOR=\"{config['UI_THEME_COLOR']}\"\n")
        f.write("UI_WELCOME_MESSAGE=\"¡Hola! Soy tu asistente RAG. ¿En qué puedo ayudarte?\"\n\n")
        
        f.write("# === OTROS ===\n")
        f.write("LOG_LEVEL=\"INFO\"\n")
        f.write("ENABLE_KIBANA=false\n")
        f.write("CONCURRENCY=true\n")
    
    print("\n✅ Archivo .env creado exitosamente")


def install_dependencies():
    """Instala las dependencias necesarias"""
    print_step(4, "Instalando dependencias")
    
    if not Path("requirements.txt").exists():
        print("❌ Error: No se encontró requirements.txt")
        return False
    
    response = input("\n¿Instalar dependencias ahora? (S/n): ")
    if response.lower() == 'n':
        print("ℹ️  Puedes instalarlas más tarde con: pip install -r requirements.txt")
        return True
    
    print("\n📦 Instalando paquetes...")
    import subprocess
    
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        print("\n✅ Dependencias instaladas correctamente")
        return True
    except subprocess.CalledProcessError:
        print("\n❌ Error instalando dependencias")
        return False


def create_init_files():
    """Crea archivos __init__.py necesarios"""
    print_step(5, "Creando archivos de inicialización")
    
    init_files = {
        "models/__init__.py": '''"""
Paquete de modelos RAG
"""

from .retriever import Retriever, RetrieverState
from .generator import Generator, GeneratorState

__all__ = ["Retriever", "RetrieverState", "Generator", "GeneratorState"]
''',
        "tests/__init__.py": '''"""
Tests para el sistema RAG
"""
'''
    }
    
    for file_path, content in init_files.items():
        path = Path(file_path)
        if not path.exists():
            path.write_text(content)
            print(f"✅ Creado: {file_path}")
        else:
            print(f"ℹ️  Ya existe: {file_path}")


def verify_installation():
    """Verifica que todo esté correctamente instalado"""
    print_step(6, "Verificando instalación")
    
    checks = []
    
    # Verificar archivos principales
    required_files = [
        "config.py",
        "promptTemplates.py",
        "appLangGraph.py",
        "webApp.py",
        "models/retriever.py",
        "models/generator.py",
        ".env"
    ]
    
    print("📄 Verificando archivos:")
    for file in required_files:
        exists = Path(file).exists()
        status = "✅" if exists else "❌"
        print(f"   {status} {file}")
        checks.append(exists)
    
    # Verificar importaciones
    print("\n📦 Verificando importaciones:")
    modules = [
        "pydantic",
        "openai",
        "azure.search.documents",
        "langgraph",
        "streamlit"
    ]
    
    for module in modules:
        try:
            __import__(module)
            print(f"   ✅ {module}")
            checks.append(True)
        except ImportError:
            print(f"   ❌ {module}")
            checks.append(False)
    
    return all(checks)


def print_next_steps():
    """Imprime los siguientes pasos"""
    print_header("✅ INSTALACIÓN COMPLETADA")
    
    print("📋 Próximos pasos:\n")
    print("1. Revisa y ajusta el archivo .env con tus credenciales")
    print("2. Ejecuta la aplicación web:")
    print("   $ streamlit run webApp.py")
    print("\n3. O prueba con ejemplos:")
    print("   $ python example_usage.py")
    print("\n4. Visualiza el grafo:")
    print("   $ make visualize")
    print("\n5. Ejecuta los tests:")
    print("   $ pytest tests/")
    print("\n📚 Consulta el README.md para más información")
    print("\n💡 Usa 'make help' para ver comandos disponibles\n")


def main():
    """Función principal del setup"""
    print_header("🚀 SETUP - RAG MODULAR CON LANGGRAPH")
    
    print("Este script te ayudará a configurar tu proyecto RAG.\n")
    print("Durante el proceso se:")
    print("  • Verificará tu entorno Python")
    print("  • Creará la estructura de directorios")
    print("  • Configurará variables de entorno")
    print("  • Instalará dependencias")
    print("  • Verificará la instalación\n")
    
    response = input("¿Continuar? (S/n): ")
    if response.lower() == 'n':
        print("\n👋 Setup cancelado")
        return
    
    # Ejecutar pasos del setup
    steps = [
        ("Verificar Python", check_python_version),
        ("Crear directorios", lambda: (create_directories(), True)[1]),
        ("Configurar .env", lambda: (setup_env_file(), True)[1]),
        ("Instalar dependencias", install_dependencies),
        ("Crear archivos init", lambda: (create_init_files(), True)[1]),
        ("Verificar instalación", verify_installation)
    ]
    
    success = True
    for i, (name, func) in enumerate(steps, 1):
        try:
            result = func()
            if result is False:
                success = False
                print(f"\n⚠️  Advertencia en: {name}")
        except Exception as e:
            print(f"\n❌ Error en {name}: {e}")
            success = False
    
    if success:
        print_next_steps()
    else:
        print("\n⚠️  El setup completó con algunas advertencias.")
        print("    Revisa los mensajes anteriores para más detalles.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Setup interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        sys.exit(1)