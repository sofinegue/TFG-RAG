"""
Servicio de procesamiento de documentos con chunking
"""
import re
from config import config
from models.doc_model import DocumentsToProcessREQ
from services.cosmos_service import cosmos_container_connection
from datetime import datetime
from document_ingestion.doc_chunking import get_text_split
from models.doc_status_enum import DocStatus
from helpers.helper_azure_search import run_and_wait_for_indexer
import asyncio
from models.Timestamps import Timestamps
from uuid import uuid4
from azure.cosmos import exceptions

# Configuración
endpoint = config.cosmos_endpoint
key = config.cosmos_key 
database_id = config.cosmosdb_process_db
container_id = config.cosmosdb_process_container
max_workers_docs = config.max_workers_docs

# Semáforos para control de concurrencia
global_semaphore = asyncio.Semaphore(max_workers_docs)
index_semaphore = asyncio.Semaphore(1)


def sanitize_id_for_search(raw_id: str) -> str:
    """
    Sanitiza un ID para Azure Search.
    Solo permite: letras, dígitos, _, -, =
    """
    sanitized = raw_id.replace('.', '-')
    sanitized = sanitized.replace('__', '-')
    sanitized = re.sub(r'[^a-zA-Z0-9_\-=]', '-', sanitized)
    return sanitized


async def load_and_process_documents(
    docs: DocumentsToProcessREQ, 
    timestamps_list, 
    session_id: str, 
    startrun, 
    cdu: str = ""
):
    """
    Carga y procesa documentos con chunking
    """
    try:
        timestamps_list.append(Timestamps("02 initProcessDocuments"))
        print("Iniciando servicio de procesamiento de documentos")
        
        timestamps_list.append(Timestamps("03 LoadDocumentsInContainer"))
        
        container = cosmos_container_connection(key, endpoint, database_id, container_id)
        
        await load_docs_to_process(docs, container)
        
        timestamps_list.append(Timestamps("04 initProcessDocuments"))
        
        ingested_docs, timestamps_list = await initiate_doc_ingestion(
            container, 
            docs.get_formula, 
            docs.id_llamada, 
            timestamps_list, 
            session_id, 
            cdu
        )
        
        timestamps_list.append(Timestamps("07 RunIndexer"))
        
        indexer_name = config.azure_search_indexer
        
        if indexer_name:
            try:
                async with index_semaphore:
                    await run_and_wait_for_indexer(
                        indexer_name=indexer_name, 
                        SessionId=session_id
                    )
            except Exception as indexer_error:
                print(f"⚠️ Warning: Indexer error (no crítico): {indexer_error}")
                print("   Los chunks se han guardado en Cosmos correctamente")
        else:
            print("ℹ️ No hay indexer configurado, saltando paso de indexación")
        
        for doc in ingested_docs:
            doc['status'] = DocStatus.PROCESSED.value
            await asyncio.to_thread(container.replace_item, item=doc['id'], body=doc)
        
    except Exception as e:
        print(f"Error en procesamiento de documentos: {e}")
        import traceback
        traceback.print_exc()


async def load_docs_to_process(docs: DocumentsToProcessREQ, cosmos_container):
    """
    Carga documentos en Cosmos DB con status PENDING
    Usa UUID puro para evitar conflictos
    """
    for i, d in enumerate(docs.documentos):
        try:
            d_dict = d.dict() if hasattr(d, 'dict') else d.model_dump()
        except AttributeError:
            d_dict = d.model_dump()
        
        incoming_doc_id = (
            d_dict.get("doc_id")
            or d_dict.get("id")
            or d_dict.get("filename")
            or f"{docs.id_llamada}_{uuid4()}"
        )
        
        # UUID puro para garantizar unicidad
        cosmos_id = sanitize_id_for_search(str(uuid4()))
        
        body = {
            **d_dict,
            "id": cosmos_id,
            "doc_id": incoming_doc_id,
            "id_llamada": str(docs.id_llamada),
            "id_caso": str(docs.id_caso),
            "equipo": str(docs.equipo),
            "usuario": str(docs.usuario),
            "status": DocStatus.PENDING.value,
        }
        
        if "doc_nombre" not in body:
            body["doc_nombre"] = (
                d_dict.get("doc_nombre")
                or d_dict.get("filename")
                or "documento_sin_nombre"
            )
        
        try:
            await asyncio.to_thread(cosmos_container.upsert_item, body=body)
            print(f"  ✓ Doc {i+1}/{len(docs.documentos)} cargado: {body['doc_nombre']}")
        
        except Exception as e:
            print(f"  ✗ Error doc {i+1}: {e}")
            continue


async def initiate_doc_ingestion(
    cosmos_container, 
    get_formulas, 
    id_llamada, 
    timestamps_list, 
    session_id, 
    cdu
):
    """
    Inicia el proceso de chunking de documentos
    """
    print("Iniciando chunking de documentos...")
    timestamps_list.append(Timestamps("05 GetPendingDocs"))
    
    pending_value = DocStatus.PENDING.value
    
    query = (
        f"SELECT * FROM c "
        f"WHERE c.status = {pending_value} "
        f"AND c.id_llamada = '{id_llamada}'"
    )
    
    print(f"Query: {query}")
    pending_docs = list(
        cosmos_container.query_items(
            query=query, 
            enable_cross_partition_query=True
        )
    )
    
    print(f"Documentos pendientes: {len(pending_docs)}")
    
    timestamps_list.append(Timestamps("06 ProcessPendingDocs"))
    
    tasks = []
    ingested_docs = []
    
    for doc in pending_docs:
        doc['status'] = DocStatus.PROCESSING.value
        await asyncio.to_thread(
            cosmos_container.replace_item, 
            item=doc['id'], 
            body=doc
        )
        
        tasks.append(
            process_document_async_semaphore(
                doc, 
                get_formulas, 
                cosmos_container, 
                max_workers_docs, 
                session_id, 
                cdu
            )
        )
    
    for task in asyncio.as_completed(tasks):
        try:
            ingested_docs.append(await task)
        except Exception as e:
            print(f"Error en tarea de chunking: {e}")
    
    return ingested_docs, timestamps_list


async def process_document_async_semaphore(
    doc, 
    get_formulas, 
    cosmos_container, 
    max_workers_docs, 
    session_id, 
    cdu
):
    """
    Procesa un documento individual con chunking
    """
    async with global_semaphore:
        try:
            doc_nombre = (
                doc.get('doc_nombre') 
                or doc.get('filename') 
                or "documento_sin_nombre"
            )
            doc_id = doc['doc_id']
            
            print(f"  📄 Chunking: {doc_nombre}")
            
            await asyncio.to_thread(
                get_text_split, 
                doc_nombre, 
                doc_id, 
                get_formulas, 
                session_id, 
                doc, 
                cdu
            )
            
            print(f"  ✅ Chunking completado: {doc_nombre}")
            
            return doc
            
        except Exception as e:
            print(f"  ✗ Error chunking {doc.get('doc_id')}: {e}")
            import traceback
            traceback.print_exc()
            raise