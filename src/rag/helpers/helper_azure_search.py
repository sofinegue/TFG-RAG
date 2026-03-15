"""
Helper para Azure Search – ejecutar y esperar a que finalice un indexer
Adaptado de src_rag para usar imports absolutos (src.*)
"""
from azure.search.documents.indexes import SearchIndexerClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceNotFoundError
from src.config import config
from datetime import datetime
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
    Ejecuta un indexer de Azure Search y espera a que finalice.

    Args:
        indexer_name: Nombre del indexer a ejecutar.
        max_retries: Número máximo de sondeos antes de rendirse.
        delay: Segundos entre sondeos.
        conflict_retries: Contador interno de reintentos por conflicto.
        max_conflict_retries: Máximo de reintentos por conflicto (409).
        SessionId: ID de sesión (para logging).
        Call_id: ID de llamada (para logging).
    """
    startrun = datetime.now()
    output = ""
    success = True
    status_code = 0

    try:
        indexers_client = SearchIndexerClient(
            config.azure_search_endpoint,
            AzureKeyCredential(config.azure_search_key)
        )

        # Verificar existencia del indexer
        try:
            indexers_client.get_indexer(indexer_name)
        except ResourceNotFoundError:
            error_msg = (
                f"Indexer '{indexer_name}' no encontrado en "
                f"'{config.azure_search_endpoint}'"
            )
            print(f"❌ {error_msg}")
            return False, error_msg, 404

        # Iniciar el indexer
        try:
            indexers_client.run_indexer(indexer_name)
            print(f"▶️  Indexer '{indexer_name}' iniciado")
        except Exception as e:
            error_str = str(e)
            if "409" in error_str or "Conflict" in error_str:
                if conflict_retries < max_conflict_retries:
                    wait_time = 30 * (conflict_retries + 1)
                    print(f"⚠️  Conflicto al iniciar indexer. Reintento en {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    return await run_and_wait_for_indexer(
                        indexer_name,
                        max_retries=max_retries,
                        delay=delay,
                        conflict_retries=conflict_retries + 1,
                        max_conflict_retries=max_conflict_retries,
                        SessionId=SessionId,
                        Call_id=Call_id
                    )
                else:
                    print(f"❌ Demasiados conflictos al iniciar indexer: {e}")
                    return False, str(e), 409

        # Sondear hasta que finalice
        for attempt in range(max_retries):
            await asyncio.sleep(delay)
            status = indexers_client.get_indexer_status(indexer_name)
            last_run = status.last_result

            if last_run:
                run_status = last_run.status
                print(f"   🔄 [{attempt + 1}/{max_retries}] Estado: {run_status}")

                if run_status == "success":
                    elapsed = (datetime.now() - startrun).total_seconds()
                    output = f"Indexer '{indexer_name}' completado en {elapsed:.1f}s"
                    print(f"   ✅ {output}")
                    return True, output, 200

                elif run_status in ("transientFailure", "persistentFailure", "failed"):
                    error_msg = f"Indexer falló con estado: {run_status}"
                    if last_run.errors:
                        error_msg += f" | Errores: {[str(e) for e in last_run.errors[:3]]}"
                    print(f"   ❌ {error_msg}")
                    return False, error_msg, 500

        # Timeout
        timeout_msg = (
            f"Indexer '{indexer_name}' no completó en "
            f"{max_retries * delay}s"
        )
        print(f"   ⏰ {timeout_msg}")
        return False, timeout_msg, 408

    except Exception as e:
        error_msg = f"Error inesperado ejecutando indexer: {e}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return False, error_msg, 500
