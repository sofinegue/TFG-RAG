"""
Servicio de OpenAI para embeddings y completions
"""
import tiktoken
from openai import AzureOpenAI
from src.config import config
from datetime import datetime
from typing import Optional

# Configuración
encoding = tiktoken.encoding_for_model("gpt-4")


def num_tokens_from_string(string: str) -> int:
    """Cuenta tokens en un string"""
    num_tokens = len(encoding.encode(string))
    return num_tokens


def get_embedding(text: str, model: str, session_id: str = "", call_id: str = "", cdu: str = "", entity: dict = {}):
    """
    Genera embedding usando Azure OpenAI desde MODELS_CONFIG
    """
    startrun = datetime.now()
    embedding = None
    
    try:
        # ✅ Obtener configuración desde MODELS_CONFIG
        embedding_config = config.get_embedding_model_config()
        
        client = AzureOpenAI(
            azure_endpoint=embedding_config.api_base,
            api_key=embedding_config.api_key,
            api_version=embedding_config.api_version,
        )
        
        # Generar embedding
        response = client.embeddings.create(
            input=text,
            model=embedding_config.deployment
        )
        
        embedding = response.data[0].embedding
        
        # Log si es necesario
        # if config.enable_kibana and session_id:
        #     _log_embedding(text, embedding, startrun, session_id, call_id, cdu)
        
        return embedding
        
    except Exception as e:
        print(f"Error obteniendo embedding: {e}")
        import traceback
        traceback.print_exc()
        
        # if config.enable_kibana and session_id:
        #     _log_embedding(text, None, startrun, session_id, call_id, cdu, error=str(e))
        
        raise


def get_response_from_gpt(
    prompt: str,
    temperature: float,
    model: str,
    max_tokens: int,
    cdu: str = "",
    session_id: str = "",
    call_id: str = "",
    try_retry: bool = True,
    entity: dict = {},
    logit_bias: dict = {}
):
    """
    Obtiene respuesta de GPT usando MODELS_CONFIG
    """
    startrun = datetime.now()
    
    try:
        # ✅ Obtener configuración desde MODELS_CONFIG
        chat_config = config.get_chat_model_config()
        
        client = AzureOpenAI(
            azure_endpoint=chat_config.api_base,
            api_key=chat_config.api_key,
            api_version=chat_config.api_version
        )
        
        response = client.chat.completions.create(
            model=chat_config.deployment,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            logit_bias=logit_bias
        )
        
        output = response.choices[0].message.content
        
        # if config.enable_kibana and session_id:
        #     _log_completion(prompt, output, startrun, session_id, call_id, cdu, model)
        
        return output
        
    except Exception as e:
        print(f"Error en GPT: {e}")
        
        # if config.enable_kibana and session_id:
        #     _log_completion(prompt, None, startrun, session_id, call_id, cdu, model, error=str(e))
        
        raise


# def _log_embedding(text, embedding, startrun, session_id, call_id, cdu, error=None):
#     """Log de embeddings a Kibana (opcional)"""
#     try:
#         from helpers import helper_adapter_kibana
        
#         status = 200 if embedding else 999
#         output = "OK" if embedding else error
        
#         embedding_config = config.get_embedding_model_config()
        
#         helper_adapter_kibana.sendKibanaAPI(
#             Url=embedding_config.api_base,
#             Body=text[:200],
#             StatusCode=status,
#             Output=output,
#             Socket="Helper_openai",
#             Id_normalizado="embedding",
#             TotalTime=(datetime.now() - startrun).total_seconds() * 1000,
#             Success=embedding is not None,
#             SessionId=session_id,
#             Call_id=call_id,
#             CDU=cdu
#         )
#     except Exception as e:
#         print(f"Error logging embedding: {e}")


# def _log_completion(prompt, output, startrun, session_id, call_id, cdu, model, error=None):
#     """Log de completions a Kibana (opcional)"""
#     try:
#         from helpers import helper_adapter_kibana
        
#         status = 200 if output else 999
#         chat_config = config.get_chat_model_config()
        
#         helper_adapter_kibana.sendKibanaAPI(
#             Url=chat_config.api_base,
#             Body=prompt[:200],
#             StatusCode=status,
#             Output=(output[:200] if output else error),
#             Socket="Helper_openai",
#             Id_normalizado=model,
#             TotalTime=(datetime.now() - startrun).total_seconds() * 1000,
#             Success=output is not None,
#             SessionId=session_id,
#             Call_id=call_id,
#             CDU=cdu
#         )
#     except Exception as e:
#         print(f"Error logging completion: {e}")