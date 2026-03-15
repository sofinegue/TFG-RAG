"""
Servicio de Cosmos DB para operaciones CRUD
"""
from azure.cosmos import CosmosClient
from src.config import config
from datetime import datetime
from typing import List, Dict, Optional


def cosmos_container_connection(key, endpoint, database_id, container_id):
    """
    Conecta a un container de Cosmos DB
    
    Args:
        key: Cosmos key
        endpoint: Cosmos endpoint
        database_id: ID de la base de datos
        container_id: ID del container
        
    Returns:
        Container client
    """
    client = CosmosClient(endpoint, key)
    database = client.get_database_client(database_id)
    container = database.get_container_client(container_id)
    return container


def upload_doc_cosmos(endpoint, cosmos_key, dbname, container_db, data, session_id="", call_id="", cdu=""):
    """
    Sube/actualiza un documento en Cosmos DB
    
    Args:
        endpoint: Cosmos endpoint
        cosmos_key: Cosmos key
        dbname: Nombre de la base de datos
        container_db: Nombre del container
        data: Datos a insertar
        session_id: ID de sesión
        call_id: ID de llamada
        cdu: Código de unidad
    """
    startrun = datetime.now()
    output = ""
    response = None
    
    try:
        container = cosmos_container_connection(cosmos_key, endpoint, dbname, container_db)
        response = container.upsert_item(data)
        output = "OK"
        
    except Exception as e:
        print(f'Error al hacer upsert en Cosmos: {e}')
        output = str(e)
    
    # Log opcional
    if config.enable_kibana and session_id:
        _log_cosmos_operation("upsert", "insert", response, endpoint, dbname, container_db, 
                             call_id, startrun, output, session_id, cdu)


def get_querys_cosmos(query, container_name, session_id="", call_id="", cdu=""):
    """
    Ejecuta una query en Cosmos DB
    
    Args:
        query: Query SQL de Cosmos
        container_name: Nombre del container
        session_id: ID de sesión
        call_id: ID de llamada
        cdu: Código de unidad
        
    Returns:
        Lista de resultados
    """
    startrun = datetime.now()
    output = ""
    result = []
    
    try:
        cosmos_db_id = config.cosmosdb_database
        cosmos_container_id = container_name
        
        container = cosmos_container_connection(
            config.cosmos_key, 
            config.cosmos_endpoint, 
            cosmos_db_id, 
            cosmos_container_id
        )
        
        result = list(container.query_items(query, enable_cross_partition_query=True))
        output = "OK"
        
    except Exception as e:
        print(f'Error ejecutando query en Cosmos: {e}')
        output = str(e)
    
    # Log opcional
    if config.enable_kibana and session_id:
        _log_cosmos_operation(query, "get", result, config.cosmos_endpoint, cosmos_db_id, 
                             cosmos_container_id, call_id, startrun, output, session_id, cdu)
    
    return result


def _log_cosmos_operation(body, action_type, obj, url, db, collection, call_id, startrun, response, session_id, cdu):
    """Log de operaciones Cosmos a Kibana (opcional)"""
    try:
        # from helpers import helper_adapter_kibana
        
        if action_type.lower() == "get":
            status = 200 if obj else 999
        elif action_type.lower() == "insert":
            status = 201 if obj else 999
        else:
            status = 999
        
        # helper_adapter_kibana.sendKibanaAPI(
        #     Url=url,
        #     DB=db,
        #     COL=collection,
        #     Body=str(body)[:200],
        #     StatusCode=status,
        #     Output=response,
        #     Socket="Helper_cosmos",
        #     Id_normalizado=f"cosmos_{action_type}",
        #     Call_id=call_id,
        #     SessionId=session_id,
        #     CDU=cdu,
        #     TotalTime=(datetime.now() - startrun).total_seconds() * 1000
        # )
    except Exception as e:
        print(f"Error logging Cosmos operation: {e}")