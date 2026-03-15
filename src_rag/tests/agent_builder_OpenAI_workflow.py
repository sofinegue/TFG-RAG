# # agent_builder_workflow.py
# """
# Workflow generado por Agent Builder - Configuración completa para EY
# """
# import os
# import warnings
# import httpx

# # ✅ API KEY HARDCODEADA (temporal para deployment)
# api_key = os.getenv("AGENT_BUILDER_OPENAI_API_KEY")

# # ✅ CONFIGURAR COMO VARIABLE DE ENTORNO
# os.environ["OPENAI_API_KEY"] = api_key

# # ✅ CONFIGURAR SSL - ANTES DE IMPORTAR AGENTS
# warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# # ✅ MONKEY PATCH HTTPX PARA DESACTIVAR SSL GLOBALMENTE
# import ssl
# _original_create_default_context = ssl.create_default_context

# def _no_verify_context(*args, **kwargs):
#     ctx = _original_create_default_context(*args, **kwargs)
#     ctx.check_hostname = False
#     ctx.verify_mode = ssl.CERT_NONE
#     return ctx

# ssl.create_default_context = _no_verify_context

# print("✅ Configuración inicial:")
# print(f"   API Key: {api_key[:20]}... (hardcodeada)")
# print(f"   SSL Verify: Desactivado globalmente")

# # ===== IMPORTS DEL AGENT BUILDER =====
# from agents import function_tool, FileSearchTool, Agent, ModelSettings, TResponseInputItem, Runner, RunConfig
# from pydantic import BaseModel
# from openai.types.shared.reasoning import Reasoning

# print("✅ Agents SDK cargado con configuración personalizada")

# # ===== TOOL DEFINITIONS =====
# @function_tool
# def get_weather(location: str, unit: str):
#     """Herramienta de ejemplo"""
#     pass

# file_search = FileSearchTool(
#     vector_store_ids=["vs_68e4cc1d8abc8191b4a17c4c8e851d78"]
# )

# # ===== SCHEMAS =====
# class GptknowledgeCvsdatabaseSchema(BaseModel):
#     operating_procedure: str

# class CvsDatabaseSchema(BaseModel):
#     output_text: str
#     sources_array: list[str]

# # ===== AGENTE PRINCIPAL =====
# cvs_database = Agent(
#     name="CVs database",
#     instructions="""You are a expert in EY team CVs (RAG system):
# Explore EY CV external information using the tools you have (file search or vector search). 
# Analyze any relevant data, checking your work.
# Make sure to output a concise and short answer.
# Answer in the same language than the query.
# Suggest a follow up question related to the previous question, and to one of the skills, experiences or people mentioned in previous search. Do not suggest anything out of your duties (answering questions about EY team CVs):
# DO: suggest new questions about specific skills, experiences, seniority, names, team etc. or organizing the information of people in a different way.
# DO NOT: suggest exporting to any file, sending mails or performing other external tool tasks.
# Be exhaustive while searching.""",
#     model="gpt-5-mini-2025-08-07",
#     tools=[file_search],
#     output_type=CvsDatabaseSchema,
#     model_settings=ModelSettings(
#         store=True,
#         reasoning=Reasoning(effort="low", summary="auto")
#     )
# )

# # ===== WORKFLOW INPUT =====
# class WorkflowInput(BaseModel):
#     input_as_text: str

# # ===== MAIN WORKFLOW =====
# async def run_workflow(workflow_input: WorkflowInput):
#     """
#     Ejecuta el workflow completo del Agent Builder
    
#     Returns:
#         dict con output_text, sources_array y usage_info
#     """
#     state = {
#         "previous_question": None,
#         "previous_question2": None
#     }
    
#     workflow = workflow_input.model_dump()
    
#     state["previous_question2"] = state.get("previous_question")
#     state["previous_question"] = workflow["input_as_text"]
    
#     print(f"🔎 Ejecutando workflow para: {workflow['input_as_text'][:50]}...")
    
#     # ✅ Ejecutar workflow
#     cvs_database_result_temp = await Runner.run(
#         cvs_database,
#         input=[
#             {
#                 "role": "user",
#                 "content": [
#                     {
#                         "type": "input_text",
#                         "text": f"""client question: {workflow["input_as_text"]}
# previous question: {state["previous_question"]} 
# previous question of previous question: {state["previous_question2"]}"""
#                     }
#                 ]
#             }
#         ],
#         run_config=RunConfig(
#             trace_metadata={
#                 "__trace_source__": "agent-builder",
#                 "workflow_id": "wf_68e537eb33308190a6c178aab4544c660805529ccbc9a198"
#             }
#         )
#     )
    
#     print("✅ Workflow ejecutado")
    
#     # ========================================================================
#     # ✅ EXTRAER USAGE INFO desde raw_responses
#     # ========================================================================
#     usage_info = {
#         "prompt_tokens": 0,
#         "completion_tokens": 0,
#         "total_tokens": 0,
#         "cached_tokens": 0,
#         "reasoning_tokens": 0,
#         "models_used": []
#     }
    
#     # Extraer desde raw_responses (donde Agent Builder guarda el usage)
#     if hasattr(cvs_database_result_temp, 'raw_responses') and cvs_database_result_temp.raw_responses:
#         for response in cvs_database_result_temp.raw_responses:
#             if hasattr(response, 'usage') and response.usage:
#                 u = response.usage
                
#                 # Tokens básicos
#                 usage_info["prompt_tokens"] += getattr(u, 'input_tokens', 0) or 0
#                 usage_info["completion_tokens"] += getattr(u, 'output_tokens', 0) or 0
#                 usage_info["total_tokens"] += getattr(u, 'total_tokens', 0) or 0
                
#                 # Cached tokens
#                 if hasattr(u, 'input_tokens_details') and u.input_tokens_details:
#                     if hasattr(u.input_tokens_details, 'cached_tokens'):
#                         usage_info["cached_tokens"] += u.input_tokens_details.cached_tokens or 0
                
#                 # Reasoning tokens
#                 if hasattr(u, 'output_tokens_details') and u.output_tokens_details:
#                     if hasattr(u.output_tokens_details, 'reasoning_tokens'):
#                         usage_info["reasoning_tokens"] += u.output_tokens_details.reasoning_tokens or 0
            
#             # Capturar modelo usado
#             if hasattr(response, 'model'):
#                 model_name = response.model
#                 if model_name and model_name not in usage_info["models_used"]:
#                     usage_info["models_used"].append(model_name)
        
#         # Si no encontramos modelo, usar el del agente
#         if not usage_info["models_used"] and hasattr(cvs_database_result_temp, 'last_agent'):
#             agent = cvs_database_result_temp.last_agent
#             if hasattr(agent, 'model') and agent.model:
#                 usage_info["models_used"].append(agent.model)
        
#         # Calcular total si no viene
#         if usage_info["total_tokens"] == 0:
#             usage_info["total_tokens"] = usage_info["prompt_tokens"] + usage_info["completion_tokens"]
    
#     # Log de tokens
#     print(f"🎫 Tokens: {usage_info['total_tokens']} total ({usage_info['prompt_tokens']} input + {usage_info['completion_tokens']} output)")
#     if usage_info["cached_tokens"] > 0:
#         print(f"   💾 Cached: {usage_info['cached_tokens']} tokens")
#     if usage_info["reasoning_tokens"] > 0:
#         print(f"   🧠 Reasoning: {usage_info['reasoning_tokens']} tokens")
#     if usage_info["models_used"]:
#         print(f"   🤖 Modelos: {', '.join(usage_info['models_used'])}")
    
#     # ✅ Parsear resultado
#     try:
#         cvs_database_result = {
#             "output_text": cvs_database_result_temp.final_output.model_dump_json(),
#             "output_parsed": cvs_database_result_temp.final_output.model_dump()
#         }
        
#         end_result = {
#             "output_text": cvs_database_result["output_parsed"]["output_text"],
#             "sources_array": cvs_database_result["output_parsed"].get("sources_array", []),
#             "usage": usage_info  # ✅ INCLUIR USAGE INFO
#         }
        
#         print(f"📄 Respuesta: {len(end_result['output_text'])} chars")
#         print(f"📚 Fuentes: {len(end_result.get('sources_array', []))}")
        
#         return end_result
        
#     except Exception as e:
#         print(f"⚠️ Error parseando resultado: {e}")
#         # Fallback
#         return {
#             "output_text": str(cvs_database_result_temp.final_output),
#             "sources_array": [],
#             "usage": usage_info  # ✅ INCLUIR USAGE INFO incluso en error
#         }


# # ===== TEST =====
# if __name__ == "__main__":
#     import asyncio
    
#     print("\n" + "="*60)
#     print("TEST DEL AGENT BUILDER WORKFLOW")
#     print("="*60)
    
#     async def test():
#         print("\n🧪 Test: Query simple")
#         result = await run_workflow(WorkflowInput(input_as_text="¿Quién tiene experiencia en Python?"))
#         print(f"\n✅ Output: {result['output_text'][:200]}...")
#         print(f"✅ Fuentes: {len(result.get('sources_array', []))}")
#         print(f"✅ Usage: {result.get('usage', {})}")
    
#     try:
#         asyncio.run(test())
#         print("\n" + "="*60)
#         print("✅ Test completado exitosamente")
#         print("="*60)
#     except Exception as e:
#         print(f"\n❌ Error en test: {e}")
#         import traceback
#         traceback.print_exc()