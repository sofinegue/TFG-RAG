# 🎨 Guía de Personalización - RAG Modular

Esta guía te ayudará a adaptar el sistema RAG para diferentes clientes y casos de uso.

## 📋 Tabla de Contenidos

1. [Personalización Básica](#personalización-básica)
2. [Personalización de Prompts](#personalización-de-prompts)
3. [Personalización de UI](#personalización-de-ui)
4. [Agregar Nodos al Grafo](#agregar-nodos-al-grafo)
5. [Casos de Uso Específicos](#casos-de-uso-específicos)
6. [Mejores Prácticas](#mejores-prácticas)

---

## Personalización Básica

### 1. Variables de Entorno (.env)

La forma más rápida de personalizar:

```bash
# Identidad del cliente
CLIENT_NAME="Acme Corp"
PROJECT_NAME="Asistente de Soporte"
LANGUAGE="es"

# Personalización UI
UI_THEME_COLOR="#FF6B6B"
UI_LOGO_URL="https://acme.com/logo.png"
UI_WELCOME_MESSAGE="¡Bienvenido al soporte de Acme!"

# Configuración RAG
MAX_CHUNKS_USED=7
MIN_RELEVANCE_SCORE=0.8
USE_RAG_FUSION=true
```

### 2. Configuración Programática (config.py)

Para configuraciones más complejas:

```python
from config import RAGConfig

# Crear configuración personalizada
custom_config = RAGConfig(
    client_name="Acme Corp",
    project_name="Asistente Especializado",
    max_chunks_used=10,
    temperature=0.5,
    # ... más configuraciones
)
```

---

## Personalización de Prompts

### Método 1: Extender PromptTemplates

Crea una clase personalizada en `promptTemplates.py`:

```python
class AcmePrompts(PromptTemplates):
    """Prompts personalizados para Acme Corp"""
    
    @staticmethod
    def rag_main_generation(query, context, max_chars=None):
        max_chars = max_chars or config.max_answer_chars
        
        context_text = ""
        for i, chunk in enumerate(context, 1):
            context_text += f"\n[Documento {i}]: {chunk['content']}\n"
        
        return f"""Eres el asistente oficial de Acme Corp, especializado en atención al cliente.

POLÍTICA DE RESPUESTA:
- Siempre mantén un tono amigable y profesional
- Si no estás seguro, recomienda contactar a soporte
- Incluye números de contacto cuando sea relevante

CONTEXTO:
{context_text}

PREGUNTA DEL CLIENTE:
{query}

RESPUESTA (máximo {max_chars} caracteres):"""
```

### Método 2: Usar Templates Externos

Crea archivos `.txt` en `prompt_templates/`:

```python
# En promptTemplates.py
def load_prompt_from_file(self, filename: str, **kwargs) -> str:
    """Carga prompt desde archivo"""
    with open(f"prompt_templates/{filename}", "r") as f:
        template = f.read()
    return template.format(**kwargs)
```

---

## Personalización de UI

### 1. Temas Predefinidos

Crea temas en `webApp.py`:

```python
THEMES = {
    "corporate": {
        "primary_color": "#1f77b4",
        "bg_color": "#ffffff",
        "text_color": "#333333"
    },
    "dark": {
        "primary_color": "#00d4ff",
        "bg_color": "#1a1a1a",
        "text_color": "#ffffff"
    },
    "medical": {
        "primary_color": "#2ecc71",
        "bg_color": "#f8f9fa",
        "text_color": "#2c3e50"
    }
}

# Aplicar tema
theme = THEMES.get(config.ui_theme, "corporate")
st.set_page_config(page_title=config.project_name, ...)
```

### 2. Componentes Personalizados

Agrega widgets específicos del cliente:

```python
def render_acme_sidebar():
    """Sidebar personalizado para Acme"""
    with st.sidebar:
        st.image("assets/acme_logo.png")
        st.markdown("### 📞 Contacto Rápido")
        st.button("☎️ Llamar a Soporte")
        st.button("📧 Enviar Email")
        
        with st.expander("🆘 Ayuda Rápida"):
            st.write("- Horario: 9:00 - 18:00")
            st.write("- Tel: 900-123-456")
            st.write("- Email: soporte@acme.com")
```

### 3. Formateo de Respuestas

Personaliza cómo se muestran las respuestas:

```python
def render_acme_message(message):
    """Renderiza mensaje con formato Acme"""
    if message["role"] == "assistant":
        # Agregar logo de Acme
        st.markdown(f"""
        <div style="border-left: 4px solid #FF6B6B; padding: 1rem;">
            <img src="acme_icon.png" width="30">
            <strong>Asistente Acme</strong>
            <p>{message['content']}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Agregar rating
        col1, col2, col3 = st.columns([1, 1, 4])
        with col1:
            if st.button("👍"):
                st.success("¡Gracias!")
        with col2:
            if st.button("👎"):
                st.text_area("¿Qué salió mal?")
```

---

## Agregar Nodos al Grafo

### 1. Nodo de Validación Personalizada

```python
# En appLangGraph.py

def validate_acme_input(self, state: RAGState) -> RAGState:
    """Validación específica de Acme"""
    query = state["query"].lower()
    
    # Detectar preguntas fuera de alcance
    out_of_scope = ["precio", "factura", "pago"]
    if any(word in query for word in out_of_scope):
        state["error"] = "redirect_to_billing"
        state["answer"] = """
        Esta pregunta debe ser manejada por nuestro departamento de facturación.
        Por favor contacta: facturacion@acme.com
        """
        return state
    
    return state

# Agregar al grafo
workflow.add_node("validate_acme", self.validate_acme_input)
workflow.add_edge("validate_input", "validate_acme")
workflow.add_edge("validate_acme", "retrieve")
```

### 2. Nodo de Post-Procesamiento

```python
def acme_post_process(self, state: RAGState) -> RAGState:
    """Post-procesa respuesta para Acme"""
    answer = state["answer"]
    
    # Agregar disclaimer
    disclaimer = "\n\n---\n<small>Esta información es orientativa. Para casos específicos, consulta con nuestro equipo.</small>"
    
    # Agregar enlaces rápidos
    quick_links = """
    \n\n**Enlaces útiles:**
    - [Portal de Cliente](https://acme.com/portal)
    - [FAQ](https://acme.com/faq)
    - [Contacto](https://acme.com/contacto)
    """
    
    state["answer"] = answer + disclaimer + quick_links
    return state

# Agregar al grafo
workflow.add_node("post_process", self.acme_post_process)
workflow.add_edge("generate", "post_process")
workflow.add_edge("post_process", END)
```

### 3. Nodo de Logging/Analytics

```python
def log_to_analytics(self, state: RAGState) -> RAGState:
    """Registra interacción en sistema de analytics"""
    import requests
    
    analytics_data = {
        "user_id": state["user_id"],
        "query": state["query"],
        "answered": bool(state["answer"]),
        "chunks_used": len(state["chunks_used"]),
        "timestamp": datetime.now().isoformat()
    }
    
    # Enviar a endpoint de analytics
    try:
        requests.post(
            "https://analytics.acme.com/api/rag",
            json=analytics_data,
            timeout=2
        )
    except Exception as e:
        print(f"Warning: Analytics logging failed: {e}")
    
    return state

# Agregar como nodo paralelo
workflow.add_node("analytics", self.log_to_analytics)
workflow.add_edge("generate", "analytics")
```

---

## Casos de Uso Específicos

### 1. Retail - Asistente de Tienda

```bash
# .env
CLIENT_NAME="MegaStore"
PROJECT_NAME="Asistente de Compras"
UI_THEME_COLOR="#E74C3C"
MAX_CHUNKS_USED=3
USE_RAG_FUSION=true
```

```python
# Prompts específicos
class RetailPrompts(PromptTemplates):
    @staticmethod
    def rag_main_generation(query, context, max_chars=None):
        return f"""Eres un asistente de ventas experto en MegaStore.

OBJETIVOS:
1. Ayudar al cliente a encontrar productos
2. Recomendar alternativas
3. Informar sobre promociones

CATÁLOGO DISPONIBLE:
{context}

CONSULTA DEL CLIENTE:
{query}

Proporciona una respuesta útil, amigable y orientada a la venta."""
```

### 2. Healthcare - Consultas Médicas

```bash
# .env
CLIENT_NAME="HealthCare Plus"
PROJECT_NAME="Asistente Médico"
LANGUAGE="es"
MAX_ANSWER_CHARS=2000
INCLUDE_SOURCES=true
MIN_RELEVANCE_SCORE=0.9
```

```python
class HealthcarePrompts(PromptTemplates):
    @staticmethod
    def rag_main_generation(query, context, max_chars=None):
        return f"""Eres un asistente médico informativo de HealthCare Plus.

IMPORTANTE:
- NO proporciones diagnósticos
- NO recomiendes medicamentos específicos
- SIEMPRE recomienda consultar con un profesional
- Proporciona información general y educativa

INFORMACIÓN MÉDICA DISPONIBLE:
{context}

CONSULTA:
{query}

RESPUESTA INFORMATIVA:"""

# Agregar nodo de disclaimer
def add_medical_disclaimer(self, state: RAGState) -> RAGState:
    disclaimer = """
    
    ⚠️ **AVISO IMPORTANTE**: Esta información es solo orientativa y educativa. 
    No reemplaza la consulta con un profesional de la salud. 
    Si tienes síntomas, consulta inmediatamente con tu médico.
    """
    state["answer"] = state["answer"] + disclaimer
    return state
```

### 3. Educación - Tutor Virtual

```bash
# .env
CLIENT_NAME="EduPlatform"
PROJECT_NAME="Tutor Virtual"
LANGUAGE="es"
USE_RAG_FUSION=true
RAG_FUSION_QUERIES=7
TEMPERATURE=0.5
```

```python
class EducationPrompts(PromptTemplates):
    @staticmethod
    def rag_main_generation(query, context, max_chars=None):
        return f"""Eres un tutor virtual experto y paciente de EduPlatform.

ESTILO DE ENSEÑANZA:
- Explica conceptos paso a paso
- Usa ejemplos y analogías
- Adapta la explicación al nivel del estudiante
- Fomenta el pensamiento crítico

MATERIAL EDUCATIVO:
{context}

PREGUNTA DEL ESTUDIANTE:
{query}

EXPLICACIÓN DIDÁCTICA:"""

# Agregar ejercicios de práctica
def add_practice_exercises(self, state: RAGState) -> RAGState:
    answer = state["answer"]
    
    exercises = """
    
    📝 **Ejercicios de Práctica:**
    1. Intenta explicar este concepto con tus propias palabras
    2. ¿Puedes pensar en un ejemplo del mundo real?
    3. ¿Qué pregunta adicional tienes sobre este tema?
    """
    
    state["answer"] = answer + exercises
    return state
```

### 4. Legal - Consultas Legales

```python
class LegalPrompts(PromptTemplates):
    @staticmethod
    def rag_main_generation(query, context, max_chars=None):
        return f"""Eres un asistente legal informativo.

MARCO LEGAL:
{context}

CONSULTA:
{query}

IMPORTANTE:
- Proporciona información general sobre el tema
- Cita artículos o leyes relevantes
- NO proporciones asesoría legal específica
- Recomienda consultar con un abogado

INFORMACIÓN LEGAL:"""
```

---

## Mejores Prácticas

### 1. Estructura de Proyecto por Cliente

```
mi-rag-proyecto/
├── configs/
│   ├── client_a.env
│   ├── client_b.env
│   └── client_c.env
├── prompts/
│   ├── client_a_prompts.py
│   ├── client_b_prompts.py
│   └── default_prompts.py
└── themes/
    ├── client_a_theme.py
    └── client_b_theme.py
```

### 2. Factory Pattern para Clientes

```python
# client_factory.py
class ClientFactory:
    """Factory para crear configuraciones por cliente"""
    
    @staticmethod
    def create_client(client_name: str):
        clients = {
            "acme": {
                "config": "configs/acme.env",
                "prompts": AcmePrompts,
                "theme": AcmeTheme,
                "custom_nodes": ["validate_acme", "post_process_acme"]
            },
            "healthcare": {
                "config": "configs/healthcare.env",
                "prompts": HealthcarePrompts,
                "theme": HealthcareTheme,
                "custom_nodes": ["medical_disclaimer"]
            }
        }
        
        return clients.get(client_name, clients["default"])

# Uso
client = ClientFactory.create_client("acme")
```

### 3. Testing por Cliente

```python
# tests/test_client_specific.py
@pytest.mark.parametrize("client,query,expected_in_answer", [
    ("acme", "horarios", "9:00 - 18:00"),
    ("healthcare", "dolor cabeza", "consulta con un profesional"),
    ("education", "explica fotosíntesis", "paso a paso"),
])
def test_client_responses(client, query, expected_in_answer):
    # Configurar cliente
    config_client(client)
    
    # Ejecutar RAG
    result = rag_graph.run(query, user_id="test")
    
    # Verificar
    assert expected_in_answer in result["answer"].lower()
```

### 4. Documentación por Cliente

Crea un README específico para cada cliente:

```markdown
# Acme Corp - RAG Assistant

## Configuración Específica
- Idioma: Español
- Tema: Corporativo Rojo
- Horario de respuesta: 9:00 - 18:00

## Características Especiales
- Validación de preguntas de facturación
- Redirect automático a departamentos
- Integración con CRM

## Contactos
- Soporte técnico: tech@acme.com
- Contacto del proyecto: pm@acme.com
```

---

## Checklist de Personalización

Antes de entregar un POC, verifica:

- [ ] Variables de entorno configuradas
- [ ] Logo del cliente agregado
- [ ] Colores corporativos aplicados
- [ ] Prompts personalizados
- [ ] Mensajes de bienvenida adaptados
- [ ] Disclaimers legales incluidos
- [ ] Contactos de soporte actualizados
- [ ] Tests específicos del cliente
- [ ] Documentación actualizada
- [ ] Demo funcional preparada

---

**¡Listo para personalizar!** 🎨

Para más ayuda, consulta el README.md principal o contacta al equipo de desarrollo.