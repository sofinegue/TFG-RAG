"""
Servicio de Azure Storage para blobs
"""
import asyncio
import json
import os
from typing import Optional, List, Dict
from azure.data.tables import TableServiceClient
from azure.storage.blob.aio import BlobServiceClient as AsyncBlobServiceClient
from azure.storage.blob import ContentSettings, generate_blob_sas, BlobSasPermissions, BlobServiceClient 
from datetime import datetime, timezone, timedelta

from fastapi.responses import JSONResponse
from config import config
from models.doc_model import BlobRef

azure_storage_account = config.azure_storage_account
azure_storage_key_assistants = config.azure_storage_key_assistants
azure_container_name_assistants = config.azure_container_name_assistants
# azure_container_name_deleted_assistants = config.azure_container_name_deleted_assistants if config.agent_builder_openai_api_key else None


def upload_json_config_to_blob(
    account_name: str,
    account_key: str,
    container_name: str,
    json_content: dict,
    blob_name: str
) -> str:
    """
    Sube un JSON de configuración al blob storage en la carpeta configs/
    """
    print(f"Subiendo JSON a blob: {blob_name}")

    # Asegurar que el blob_name no tenga la extensión
    if blob_name.endswith('.json'):
        blob_name = blob_name[:-5]
    
    blob_name = f"{blob_name}.json"
    json_str = json.dumps(json_content, indent=2, ensure_ascii=False)
    
    # Crear conexión al blob storage
    connect_str = (
        f"DefaultEndpointsProtocol=https;"
        f"AccountName={account_name};"
        f"AccountKey={account_key};"
        f"EndpointSuffix=core.windows.net"
    )
    
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    
    try:
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)
        
        # Usar ContentSettings en lugar de dict
        blob_client.upload_blob(
            json_str.encode('utf-8'),
            overwrite=True,
            content_settings=ContentSettings(content_type='application/json')
        )
        
        print(f"✅ JSON subido: {blob_name}")
        return blob_name
        
    except Exception as e:
        print(f"❌ Error al subir JSON: {e}")
        raise
    finally:
        blob_service_client.close()


def list_json_configs_from_blob(
    account_name: str,
    account_key: str,
    container_name: str,
    prefix: str = "config-jsons/"
) -> List[str]:
    """
    Lista todos los archivos JSON de configuración en el blob storage bajo un prefijo dado.
    """
    connect_str = (
        f"DefaultEndpointsProtocol=https;"
        f"AccountName={account_name};"
        f"AccountKey={account_key};"
        f"EndpointSuffix=core.windows.net"
    )
    
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    
    try:
        container_client = blob_service_client.get_container_client(container_name)

        json_files = []

        # ✅ USAR EL PREFIX (si está vacío, lista todo)
        if prefix:
            blobs = container_client.list_blobs(name_starts_with=prefix)
        else:
            blobs = container_client.list_blobs()
        
        for blob in blobs:
            if blob.name.endswith(".json"):
                # ✅ Excluir configs GPT del listado de asistentes SOLO si no estamos buscando GPT configs
                if blob.name.startswith("gpt-configs/") and not prefix.startswith("gpt-configs"):
                    continue
                json_files.append(blob.name)
        
        print(f"📋 Encontrados {len(json_files)} archivos JSON en '{container_name}' (prefix: '{prefix}')")    
        return sorted(json_files, reverse=True)
    
    except Exception as e:
        print(f"❌ Error al listar JSONs en '{container_name}': {e}")
        raise
    
    finally:
        blob_service_client.close()


def download_json_config_from_blob(
    account_name: str,
    account_key: str,
    container_name: str,
    blob_name: str
) -> Dict:
    """
    Descarga un JSON de configuración del blob storage de manera síncrona.
    
    Args:
        account_name: Nombre de la cuenta de Azure Storage
        account_key: Key de la cuenta
        container_name: Nombre del contenedor
        blob_name: Nombre completo del blob (ej: configs/config_20250102_153045.json)
    
    Returns:
        Diccionario con la configuración parseada
    """
    connect_str = (
        f"DefaultEndpointsProtocol=https;"
        f"AccountName={account_name};"
        f"AccountKey={account_key};"
        f"EndpointSuffix=core.windows.net"
    )
    
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    
    try:
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)
        
        # Descargar blob
        blob_data = blob_client.download_blob()
        json_bytes = blob_data.readall()
        json_data = json.loads(json_bytes.decode("utf-8"))
        
        return json_data
    
    except json.JSONDecodeError as e:
        print(f"❌ Error al parsear JSON: {e}")
        raise ValueError(f"El archivo {blob_name} no contiene JSON válido")
    
    except Exception as e:
        print(f"❌ Error al descargar JSON: {e}")
        raise
    
    finally:
        blob_service_client.close()

def delete_json_config_from_blob(
    account_name: str,
    account_key: str,
    container_name: str,
    blob_name: str
) -> bool:
    """
    Mueve el JSON de configuración al contenedor de eliminados y luego lo borra del contenedor original.
    
    Args:
        account_name: Nombre de la cuenta de Azure Storage
        account_key: Key de la cuenta
        container_name: Nombre del contenedor
        blob_name: Nombre completo del blob a eliminar.
    
    Returns:
        True si se movió y eliminó correctamente, False en caso contrario.

    """
    connect_str = (
        f"DefaultEndpointsProtocol=https;"
        f"AccountName={account_name};"
        f"AccountKey={account_key};"
        f"EndpointSuffix=core.windows.net"
    )
    
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    
    try:
        source_container_client = blob_service_client.get_container_client(container_name)
        source_blob_client = source_container_client.get_blob_client(blob_name)

        # # Si hay contenedor de eliminados configurado, mover ahí primero
        # if azure_container_name_deleted_assistants:
        #     # Descargamos datos del asistente a eliminar
        #     blob_data = source_blob_client.download_blob().readall()

        #     deleted_container_client = blob_service_client.get_container_client(azure_container_name_deleted_assistants)
        #     deleted_blob_client = deleted_container_client.get_blob_client(blob_name)

        #     # Subimos el asistente al contenedor de eliminados
        #     deleted_blob_client.upload_blob(blob_data, overwrite=True)

        # Borramos el asistente del contenedor original
        source_blob_client.delete_blob()
        
        return True
        
    except Exception as e:
        print(f"❌ Error al eliminar JSON: {e}")
        return False
    finally:
        blob_service_client.close()

async def upload_blob_file_async(
    account_name: str,
    account_key: str,
    container_name: str,
    input_file: bytes,
    destination_blob: str,
    content_type: str = "application/octet-stream",
) -> BlobRef:
    """
    Sube un archivo a Azure Blob Storage
    
    Args:
        account_name: Nombre de la cuenta de storage
        account_key: Key de la cuenta
        container_name: Nombre del container
        input_file: Bytes del archivo
        destination_blob: Nombre del blob destino
        content_type: Content type del archivo
        
    Returns:
        BlobRef con información del blob subido
    """
    connect_str = (
        f"DefaultEndpointsProtocol=https;AccountName={account_name};"
        f"AccountKey={account_key};EndpointSuffix=core.windows.net"
    )
    
    blob_client = BlobServiceClient.from_connection_string(connect_str)
    
    try:
        container_client = blob_client.get_container_client(container_name)
        
        await container_client.upload_blob(
            name=destination_blob,
            data=input_file,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        
        return BlobRef(
            blob_name=destination_blob,
            filename=destination_blob.split("__")[-1],
            size=len(input_file),
            content_type=content_type,
        )
    finally:
        await blob_client.close()

def save_assistant_id_to_blob(assistant_key: str, assistant_id: str) -> bool:
    """
    Actualiza el archivo JSON del asistente en blob storage añadiendo el assistant_id
    
    Args:
        assistant_key: ID del asistente (ej: 'ugen')
        assistant_id: ID del asistente de Azure (ej: 'asst_28JyMy7foylpjekt4jAWwA4n')
    
    Returns:
        bool: True si se guardó correctamente
    """
    try:
        # ✅ USAR LAS VARIABLES CORRECTAS DEL MÓDULO
        connect_str = (
            f"DefaultEndpointsProtocol=https;"
            f"AccountName={azure_storage_account};"
            f"AccountKey={azure_storage_key_assistants};"
            f"EndpointSuffix=core.windows.net"
        )
        
        blob_service_client = BlobServiceClient.from_connection_string(connect_str)
        container_client = blob_service_client.get_container_client(azure_container_name_assistants)
        
        # ✅ EL BLOB SE LLAMA DIRECTAMENTE assistant_key.json (sin prefijo)
        blob_name = f"{assistant_key}.json"
        blob_client = container_client.get_blob_client(blob_name)
        
        # Descargar JSON actual
        print(f"   📥 Descargando configuración actual de: {blob_name}")
        blob_data = blob_client.download_blob().readall()
        config = json.loads(blob_data.decode('utf-8'))
        
        # Añadir/actualizar assistant_id
        config['assistant_id'] = assistant_id
        print(f"   ✏️  Actualizando assistant_id: {assistant_id}")
        
        # Subir JSON actualizado con content_settings
        updated_json = json.dumps(config, indent=2, ensure_ascii=False)
        blob_client.upload_blob(
            updated_json.encode('utf-8'),
            overwrite=True,
            content_settings=ContentSettings(content_type='application/json')
        )
        
        print(f"   ✅ assistant_id guardado en blob: {blob_name}")
        return True
        
    except Exception as e:
        print(f"   ❌ Error guardando assistant_id en blob: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            blob_service_client.close()
        except:
            pass
            
async def get_specific_file_from_blob_container(
    account_name: str,
    account_key: str,
    container_name: str,
    specific_blob_name: str,
    SessionId: str = "",
    Call_id: str = "",
    CDU: str = ""
) -> Optional[bytes]:
    """
    Descarga un blob de Azure Storage con reintentos
    
    Args:
        account_name: Nombre de la cuenta
        account_key: Key de la cuenta
        container_name: Container
        specific_blob_name: Nombre del blob
        SessionId: ID de sesión
        Call_id: ID de llamada
        CDU: Código de unidad
        
    Returns:
        Bytes del archivo o None si falla
    """
    connect_str = (
        f"DefaultEndpointsProtocol=https;AccountName={account_name};"
        f"AccountKey={account_key};EndpointSuffix=core.windows.net"
    )
    
    retry_intervals = [2, 5, 10]
    total_attempts = len(retry_intervals) + 1
    
    print(f"Descargando blob: {specific_blob_name}")
    
    for attempt in range(total_attempts):
        blob_client = AsyncBlobServiceClient.from_connection_string(connect_str)
        
        try:
            print(f"blob client = {blob_client}")
            container_client = blob_client.get_container_client(container_name)
            print(f"container client = {container_client}")
            blob_client_obj = container_client.get_blob_client(specific_blob_name)
            print(f"blob client obj = {blob_client_obj}")
            
            stream = await blob_client_obj.download_blob()
            print(f"✅ Blob encontrado: {specific_blob_name}, descargando contenido...")
            blob_bytes = await stream.readall()
            
            print(f"✅ Blob descargado: {specific_blob_name}")
            return blob_bytes
            
        except Exception as e:
            print(f"❌ Intento {attempt + 1} falló: {e}")
            
            if attempt < len(retry_intervals):
                wait_time = retry_intervals[attempt]
                print(f"  Esperando {wait_time}s antes de reintentar...")
                await asyncio.sleep(wait_time)
            else:
                print("  Todos los intentos fallaron")
                return None
        finally:
            await blob_client.close()
    
    return None


def generate_shared_access_signature_blob_files(
    blob_file_name: str,
    account_name: str,
    account_key: str,
    container_name: str,
) -> str:
    """
    Genera SAS token para un blob
    
    Args:
        blob_file_name: Nombre del blob
        account_name: Cuenta de storage
        account_key: Key de la cuenta
        container_name: Container
        
    Returns:
        URL con SAS token
    """
    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=container_name,
        blob_name=blob_file_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(tz=timezone.utc) + timedelta(hours=1),
    )
    
    sas_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_file_name}?{sas_token}"
    return sas_url


def upload_assistant_config_to_blob(
    assistant_config: dict,
    assistant_id: str
) -> str:
    """
    Sube una configuración de asistente al blob storage assistants-jsons
    
    Args:
        assistant_config: Diccionario con la configuración del asistente
        assistant_id: ID único del asistente
    
    Returns:
        Nombre del blob creado
    """
    blob_name = f"{assistant_id}.json"
    
    return upload_json_config_to_blob(
        account_name=azure_storage_account,
        account_key=azure_storage_key_assistants,
        container_name=azure_container_name_assistants,
        json_content=assistant_config,
        blob_name=blob_name
    )

def download_assistant_config_from_blob(assistant_id: str) -> dict:
    """
    Descarga una configuración de asistente desde blob storage assistants-jsons
    
    Args:
        assistant_id: ID del asistente
    
    Returns:
        Diccionario con la configuración del asistente
    """
    blob_name = f"{assistant_id}.json"
    
    return download_json_config_from_blob(
        account_name=azure_storage_account,
        account_key=azure_storage_key_assistants,
        container_name=azure_container_name_assistants,
        blob_name=blob_name
    )

def list_assistant_configs_from_blob() -> List[str]:
    """
    Lista todos los asistentes configurados en blob storage assistants-jsons
    con validación de configuraciones (solo logging)
    
    Returns:
        Lista de IDs de asistentes (sin extensión .json)
    """
    all_configs = list_json_configs_from_blob(
        account_name=azure_storage_account,
        account_key=azure_storage_key_assistants,
        container_name=azure_container_name_assistants,
        prefix=""
    )
    
    print(f"🔍 Archivos encontrados: {all_configs}")
    
    assistant_ids = [
        blob.replace(".json", "")
        for blob in all_configs
        if blob.endswith(".json")
    ]
    
    print(f"🔍 IDs extraídos: {assistant_ids}")
    
    # ✅ VALIDAR CADA ASISTENTE (solo para logging, no cambia el return)
    validation_stats = {"total": 0, "valid": 0, "with_warnings": 0, "invalid": 0}
    
    for assistant_id in assistant_ids:
        try:
            assistant_data = download_assistant_config_from_blob(assistant_id)
            validation_stats["total"] += 1
            
            has_errors = False
            has_warnings = False
            
            # ✅ VALIDACIÓN CONDICIONAL DE API KEY
            api_type = assistant_data.get("api_type", "azure")
            
            if api_type == "azure":
                # Azure OpenAI Service: REQUIERE api_key
                api_key = assistant_data.get("api_key", "").strip()
                if not api_key:
                    has_errors = True
                    print(f"   ❌ CRÍTICO: '{assistant_id}' de tipo 'azure' NO tiene api_key")
                    print(f"       Este asistente NO funcionará hasta que se configure una api_key válida")
                    print(f"       Archivo: {assistant_id}.json en blob storage '{azure_container_name_assistants}'")
            
            # elif api_type == "azure_ai_projects":
            #     # Azure AI Projects: NO requiere api_key (usa Azure AD)
            #     print(f"   ℹ️ '{assistant_id}' usa Azure AD (no requiere api_key)")
            
            else:
                pass
            
            # Validar campos requeridos
            if not assistant_data.get("endpoint", "").strip():
                has_errors = True
                print(f"   ❌ '{assistant_id}' falta 'endpoint'")
            
            if not assistant_data.get("deployment", "").strip():
                has_errors = True
                print(f"   ❌ '{assistant_id}' falta 'deployment'")
            
            # Validar campos opcionales
            if not assistant_data.get("vector_store_id", "").strip():
                has_warnings = True
                print(f"   ⚠️  '{assistant_id}' no tiene 'vector_store_id'")
            
            if not assistant_data.get("prompt", "").strip():
                has_warnings = True
                print(f"   ⚠️  '{assistant_id}' no tiene 'prompt' personalizado")
            
            # Actualizar stats
            if has_errors:
                validation_stats["invalid"] += 1
                print(f"   ❌ '{assistant_id}' tiene ERRORES CRÍTICOS y NO funcionará")
            elif has_warnings:
                validation_stats["with_warnings"] += 1
                print(f"   ⚠️  '{assistant_id}' tiene advertencias pero puede funcionar")
            else:
                validation_stats["valid"] += 1
                print(f"   ✅ '{assistant_id}' validado correctamente")
            
        except Exception as e:
            print(f"   ❌ ERROR al validar '{assistant_id}': {e}")
            validation_stats["invalid"] += 1
    
    # Resumen
    print(f"📊 Resumen de validación de asistentes:")
    print(f"   Total: {validation_stats['total']}")
    print(f"   ✅ Válidos: {validation_stats['valid']}")
    print(f"   ⚠️  Con advertencias: {validation_stats['with_warnings']}")
    print(f"   ❌ Inválidos: {validation_stats['invalid']}")
    
    if validation_stats['invalid'] > 0:
        print(f"\n⚠️  ATENCIÓN: {validation_stats['invalid']} asistente(s) NO funcionarán debido a errores críticos")
        print(f"   Revisa los mensajes anteriores para corregir las configuraciones")
    
    # ✅ RETORNAR SOLO LA LISTA DE IDs
    return assistant_ids

def get_users_from_table(
    account_name: Optional[str] = None,
    account_key: Optional[str] = None,
    table_name: str = "users",
    query_filter: Optional[str] = None,
    select_fields: Optional[List[str]] = None
) -> List[Dict]:
    """
    Recupera entidades de la tabla 'users' en Azure Table Storage
    
    Args:
        account_name: Nombre de la cuenta de storage (opcional, usa config si no se proporciona)
        account_key: Key de la cuenta (opcional, usa config si no se proporciona)
        table_name: Nombre de la tabla (default: 'users')
        query_filter: Filtro OData para consultas específicas (ej: "PartitionKey eq 'admin'")
        select_fields: Lista de campos específicos a recuperar (ej: ['email', 'name'])
    
    Returns:
        Lista de diccionarios con las entidades de la tabla
    
    Example:
        # Obtener todos los usuarios
        users = get_users_from_table()
        
        # Obtener usuarios con filtro
        admins = get_users_from_table(query_filter="username eq 'admin'")
        
        # Obtener solo campos específicos
        passwords = get_users_from_table(select_fields=['username', 'password'])
    """
    # Usar credenciales de config si no se proporcionan
    if not account_name:
        account_name = config.azure_storage_account
    if not account_key:
        account_key = config.azure_storage_key_assistants
    
    # Crear connection string
    connection_string = (
        f"DefaultEndpointsProtocol=https;"
        f"AccountName={account_name};"
        f"AccountKey={account_key};"
        f"EndpointSuffix=core.windows.net"
    )
    
    # Crear cliente de Table Service
    table_service_client = TableServiceClient.from_connection_string(connection_string)
    
    try:
        # Obtener cliente de la tabla
        table_client = table_service_client.get_table_client(table_name)
        
        # Preparar parámetros de consulta
        query_params = {}
        if query_filter:
            query_params['query_filter'] = query_filter
        if select_fields:
            query_params['select'] = select_fields
        
        # Consultar entidades
        entities = table_client.query_entities(query_filter=query_filter, **query_params)
        
        # Convertir a lista de diccionarios
        users_list = []
        for entity in entities:
            user_dict = dict(entity)
            users_list.append(user_dict)
        
        print(f"✅ {len(users_list)} usuarios recuperados de la tabla '{table_name}'")
        return users_list
        
    except Exception as e:
        print(f"❌ Error al recuperar usuarios de la tabla: {e}")
        raise
    
    finally:
        table_service_client.close()