"""
Módulo de Retrieval - Búsqueda Híbrida con Query Expansion Inteligente
Recupera información relevante usando Azure Search (Vector + Semantic + Keyword)
"""

import re
from typing import List, Dict, TypedDict
from concurrent.futures import ThreadPoolExecutor

from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.models import VectorizedQuery
from openai import AzureOpenAI

from config import config
from prompts.promptTemplates import PromptTemplates


class ChunkData(TypedDict):
    """Estructura de datos para un chunk recuperado"""
    chunk_id: str
    title: str
    content: str
    doc_title: str
    pages: str
    score: float
    reranker_score: float
    metadata: Dict


class RetrieverState(TypedDict):
    """Estado del retriever para LangGraph"""
    query: str
    synthetic_queries: List[str]
    chunks_retrieved: List[ChunkData]
    user_id: str
    conversation_history: List[Dict]
    timestamps: Dict[str, float]
    rag_mode: str  # ✅ AÑADIR


class Retriever:
    """Retriever con búsqueda híbrida + Query Expansion Inteligente"""
    
    def __init__(self):
        self.config = config
        self.prompts = PromptTemplates()
        
        # Cliente de Azure Search
        self.search_client = SearchClient(
            endpoint=config.azure_search_endpoint,
            index_name=config.azure_search_index,
            credential=AzureKeyCredential(config.azure_search_key)
        )
        
        # Cliente de Azure OpenAI para embeddings
        embedding_config = config.get_embedding_model_config()
        self.embedding_client = AzureOpenAI(
            api_key=embedding_config.api_key,
            api_version=embedding_config.api_version,
            azure_endpoint=embedding_config.api_base
        )
        self.embedding_deployment = embedding_config.deployment
        
        # Cliente de Azure OpenAI para generación de queries
        chat_config = config.get_chat_model_config()
        self.chat_client = AzureOpenAI(
            api_key=chat_config.api_key,
            api_version=chat_config.api_version,
            azure_endpoint=chat_config.api_base
        )
        self.chat_deployment = chat_config.deployment
    
    def _expand_query_with_context(self, query: str, history: List[Dict]) -> str:
        """
        Expande queries usando extracción de nombres + validación LLM
        """
        if not history or len(history) < 2:
            return query
        
        # 1️⃣ FASE 1: Extraer nombres del historial con regex (más confiable)
        import re
        
        recent_history = history[-4:]
        history_text = "\n".join([
            f"{msg['role'].upper()}: {msg['content'][:400]}"
            for msg in recent_history
        ])
        
        # Extraer todos los nombres propios completos (Nombre Apellido Apellido)
        # Patrón: palabras que empiezan con mayúscula, seguidas de otras con mayúscula
        name_pattern = r'\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3}\b'
        found_names = re.findall(name_pattern, history_text)
        
        # Filtrar nombres válidos (más de 2 palabras = nombre completo)
        full_names = [name for name in found_names if len(name.split()) >= 2]
        # Eliminar duplicados manteniendo orden
        unique_names = list(dict.fromkeys(full_names))
        
        print(f"      🔍 Nombres encontrados en historial: {unique_names[:5]}")  # Max 5 para debug
        
        # 2️⃣ FASE 2: Usar LLM para decidir si expandir y cómo
        expansion_prompt = f"""Analiza si esta query necesita información del contexto conversacional.

    CONVERSACIÓN RECIENTE:
    {history_text}

    NOMBRES IDENTIFICADOS: {', '.join(unique_names[:10]) if unique_names else 'ninguno'}

    QUERY ACTUAL:
    {query}

    TAREA:
    Si la query usa términos genéricos (pronombres plurales como "tienen", "son", etc.) y en el historial se mencionaron personas/candidatos específicos, expande la query incluyendo:
    - TODOS los nombres de la lista "NOMBRES IDENTIFICADOS" que sean relevantes
    - Términos técnicos o certificaciones mencionadas
    - La intención de la pregunta

    REGLAS:
    - Si la query ya es específica, devuélvela sin cambios
    - Si usa plural y hay múltiples nombres, incluye TODOS (no solo uno)
    - Máximo 15 palabras
    - Solo nombres, tecnologías y términos clave

    EJEMPLOS:

    NOMBRES IDENTIFICADOS: Irena Ventsislávova, David Soler
    Query: "son seniors?"
    Expandida: "Irena Ventsislávova David Soler nivel senior experiencia"

    NOMBRES IDENTIFICADOS: Álvaro Pérez
    Query: "y alguien más?"
    Expandida: "otros candidatos UiPath no Álvaro Pérez"

    NOMBRES IDENTIFICADOS: ninguno
    Query: "qué seniority tienen?"
    Expandida: "qué seniority tienen?"

    Responde SOLO con la query expandida:"""

        try:
            print(f"      🔍 Analizando expansión con LLM...")
            response = self.chat_client.chat.completions.create(
                model=self.chat_deployment,
                messages=[{"role": "user", "content": expansion_prompt}],
                temperature=0.1,  # Muy bajo para máxima consistencia
                max_tokens=70
            )
            
            expanded = response.choices[0].message.content.strip().strip('"').strip("'")
            
            # Validación
            if len(expanded.split()) > 20 or expanded == "" or "\n" in expanded:
                print(f"      ⚠️ Expansión inválida del LLM")
                # Fallback: construir manualmente si hay nombres
                if unique_names and any(word in query.lower() for word in ["tienen", "son", "están", "qué", "cuál"]):
                    manual_expansion = f"{query} {' '.join(unique_names[:3])}"
                    print(f"      🔧 Usando expansión manual: '{manual_expansion}'")
                    return manual_expansion
                return query
            
            if expanded.lower() != query.lower():
                print(f"      ✨ Query expandida: '{expanded}'")
            else:
                print(f"      ✓ Query no necesita expansión")
            
            return expanded
            
        except Exception as e:
            print(f"      ⚠️ Error en expansión LLM: {e}")
            # Fallback: expansión manual con regex
            if unique_names and any(word in query.lower() for word in ["tienen", "son", "están"]):
                fallback = f"{query} {' '.join(unique_names[:3])}"
                print(f"      🔧 Usando fallback con nombres: '{fallback}'")
                return fallback
            return query
    
    def generate_synthetic_queries(self, query: str) -> List[str]:
        """
        Genera queries sintéticas usando RAG Fusion
        """
        if not config.use_rag_fusion:
            return [query]
        
        k = config.rag_fusion_queries - 1
        
        prompt = self.prompts.rag_fusion_synthetic_queries(query, k)
        
        try:
            response = self.chat_client.chat.completions.create(
                model=self.chat_deployment,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500
            )
            
            synthetic_text = response.choices[0].message.content
            
            # Parsear las queries generadas
            queries = re.sub(r'\d+\.\s*', '', synthetic_text).strip().split('\n')
            queries = [q.strip() for q in queries if q.strip()]
            
            # Insertar la query original al inicio
            queries.insert(0, query)
            
            return queries[:config.rag_fusion_queries]
            
        except Exception as e:
            print(f"Error generando queries sintéticas: {e}")
            return [query]
    
    def get_embedding(self, text: str) -> List[float]:
        """Genera embedding para un texto"""
        try:
            response = self.embedding_client.embeddings.create(
                model=self.embedding_deployment,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generando embedding: {e}")
            raise
    
    def hybrid_search(self, query: str, top_k: int = 10) -> List[Dict]:
        """Búsqueda híbrida: texto + vector"""
        try:
            query_embedding = self.get_embedding(query)
            
            results = self.search_client.search(
                search_text=query,
                vector_queries=[
                    VectorizedQuery(
                        vector=query_embedding,
                        k_nearest_neighbors=top_k,
                        fields="embedding"
                    )
                ],
                top=top_k,
                select=["id", "chunkId", "sectionContent", "Title", "docTitle", "Pages"]
            )
            
            chunks = []
            for result in results:
                chunks.append({
                    "chunk_id": result.get("chunkId"),
                    "id": result.get("id"),
                    "content": result.get("sectionContent"),
                    "title": result.get("Title"),
                    "doc_title": result.get("docTitle"),
                    "pages": result.get("Pages"),
                    "score": result.get("@search.score", 0),
                    "reranker_score": 1.0
                })
            
            return chunks
            
        except Exception as e:
            print(f"Error en búsqueda híbrida: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def rag_fusion_retrieve(self, queries: List[str]) -> List[ChunkData]:
        """Recupera chunks usando múltiples queries y fusiona resultados"""
        all_chunks = []
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.hybrid_search, q) for q in queries]
            
            for future in futures:
                chunks = future.result()
                all_chunks.extend(chunks)
        
        # Fusionar usando RRF
        chunk_scores = {}
        for rank, chunk in enumerate(all_chunks, 1):
            chunk_id = chunk["chunk_id"]
            rrf_score = 1 / (60 + rank)
            
            if chunk_id in chunk_scores:
                chunk_scores[chunk_id]["rrf_score"] += rrf_score
            else:
                chunk["rrf_score"] = rrf_score
                chunk_scores[chunk_id] = chunk
        
        # Ordenar por RRF score
        ranked_chunks = sorted(
            chunk_scores.values(),
            key=lambda x: x.get("rrf_score", 0),
            reverse=True
        )
        
        # Filtrar por score mínimo
        filtered_chunks = [
            c for c in ranked_chunks
            if c.get("reranker_score", 0) >= config.min_relevance_score
        ]
        
        return filtered_chunks[:config.max_chunks_used]
    
    def retrieve(self, state: RetrieverState) -> RetrieverState:
        """
        Función principal para LangGraph - CON QUERY EXPANSION
        """
        query = state["query"]
        rag_mode = state.get("rag_mode", "agent")  # ✅ AÑADIR
        
        # ✅ SALTAR RETRIEVAL EN MODO AGENT
        if rag_mode == "agent":
            print("   🤖 Modo Agent Builder: Saltando retrieval de Azure Search")
            state["synthetic_queries"] = []
            state["chunks_retrieved"] = []
            return state
        
        # ✅ CONTINUAR SOLO SI MODO GPT
        conversation_history = state.get("conversation_history", [])
        
        print(f"   🔍 Query original: {query}")
        
        # ✅ EXPANSIÓN INTELIGENTE DE QUERY
        expanded_query = self._expand_query_with_context(query, conversation_history)
        
        # Generar queries sintéticas con la query expandida
        synthetic_queries = self.generate_synthetic_queries(expanded_query)
        
        print(f"   📝 Queries sintéticas generadas: {len(synthetic_queries)}")
        for i, sq in enumerate(synthetic_queries, 1):
            print(f"      {i}. {sq[:80]}{'...' if len(sq) > 80 else ''}")
        
        # Recuperar chunks
        chunks = self.rag_fusion_retrieve(synthetic_queries)
        
        print(f"   ✅ {len(chunks)} chunks recuperados y rankeados")
        
        # Actualizar estado
        state["synthetic_queries"] = synthetic_queries
        state["chunks_retrieved"] = chunks
        
        return state