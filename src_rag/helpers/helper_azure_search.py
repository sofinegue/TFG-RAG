"""
Helper para Azure Search - Run indexer
"""
from azure.search.documents.indexes import SearchIndexerClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceNotFoundError  # ✅ AÑADIDO
from config import config
from datetime import datetime, timedelta, timezone
import asyncio


async def run_and_wait_for_indexer(
    indexer_name: str, 
    max_retries: int = 20, 
    delay: int = 1, 
    conflict_retries: int = 0, 
    max_conflict_retries: int = 3,
    SessionId: str = "",
    Call_id: str = ""
):
    """
    Ejecuta un indexer de Azure Search y espera a que termine
    
    Args:
        indexer_name: Nombre del indexer
        max_retries: Número máximo de reintentos
        delay: Segundos entre verificaciones
        conflict_retries: Contador de reintentos por conflicto
        max_conflict_retries: Máximo de reintentos por conflicto
        SessionId: ID de sesión
        Call_id: ID de llamada
    """
    startrun = datetime.now()
    output = ""
    success = True
    status_code = 0
    cdu = "DOCPROCESS"
    
    try:
        indexers_client = SearchIndexerClient(
            config.azure_search_endpoint,
            AzureKeyCredential(config.azure_search_key)
        )
        
        # ✅ AÑADIDO: Verificar que el indexer existe
        try:
            indexers_client.get_indexer(indexer_name)
        except ResourceNotFoundError:
            error_msg = f"Indexer '{indexer_name}' no encontrado en '{config.azure_search_endpoint}'"
            print(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        # Calcular tiempo actual
        actual_time = datetime.now() - timedelta(hours=int(config.hour_diff))
        actual_time_format = actual_time.replace(tzinfo=timezone.utc)
        int_actual_time = int(actual_time_format.timestamp())
        
        # Ejecutar indexer
        # indexers_client.run_indexer(indexer_name)
        print(f"Indexer no ejecutado: {indexer_name}")
        
        # Esperar a que termine
        retries = 0
        status = False
        
        while retries < max_retries:
            indexer_status = indexers_client.get_indexer_status(indexer_name)
            index_time = indexer_status.last_result.end_time if indexer_status.last_result else None
            
            if index_time is None:
                status = False
                print("  Obteniendo estado del indexer...")
            else:
                index_time_format = index_time.replace(tzinfo=timezone.utc)
                int_index_time = int(index_time_format.timestamp())
                print(f"  Index:{index_time_format} vs Actual:{actual_time_format}")
                status = int_index_time > int_actual_time
            
            if not status:
                await asyncio.sleep(delay)
                retries += 1
            else:
                output = "OK"
                status_code = 200
                print("✅ Indexer completado exitosamente")
                return
        
        print("⚠️ Indexer no completó en el tiempo esperado")
        output = "Timeout"
        status_code = 408
        success = False
    
    # ✅ AÑADIDO: Manejo específico de ResourceNotFoundError
    except ResourceNotFoundError as e:
        error_message = str(e)
        print(f"❌ Indexer no encontrado: {error_message}")
        output = f"Indexer not found: {error_message}"
        success = False
        status_code = 404
        raise  # Re-lanzar para que el llamador lo maneje
    
    except Exception as e:
        error_message = str(e)
        print(f"❌ Error ejecutando indexer: {error_message}")
        
        # Reintentar si es conflicto de concurrencia
        if "conflict" in error_message.lower() and conflict_retries < max_conflict_retries:
            print(f"Conflicto detectado, reintentando en 5s... (Intento {conflict_retries + 1})")
            await asyncio.sleep(5)
            await run_and_wait_for_indexer(
                indexer_name, max_retries, delay, 
                conflict_retries + 1, max_conflict_retries,
                SessionId, Call_id
            )
        else:
            output = f"Error: {error_message}"
            success = False
            status_code = 999
            raise  # Re-lanzar para que el llamador lo maneje