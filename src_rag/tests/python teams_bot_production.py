# """
# 🤖 Microsoft Teams Bot con Agent Builder
# Bot completo con autenticación para chats 1-1

# Instalación:
# pip install botbuilder-core botbuilder-schema aiohttp python-dotenv
# """

# import os
# import sys
# import traceback
# from typing import List
# from datetime import datetime

# from aiohttp import web
# from aiohttp.web import Request, Response

# from botbuilder.core import (
#     BotFrameworkAdapter,
#     BotFrameworkAdapterSettings,
#     TurnContext,
#     ActivityHandler,
#     MessageFactory
# )
# from botbuilder.schema import (
#     Activity,
#     ActivityTypes,
#     ChannelAccount,
#     Attachment,
#     HeroCard,
#     CardAction,
#     ActionTypes
# )

# # ============================================
# # 🔒 CONFIGURACIÓN SSL PARA ZSCALER/PROXIES
# # ============================================
# import ssl
# import urllib3
# import warnings

# # Deshabilitar verificación SSL (solo para desarrollo con Zscaler)
# os.environ['PYTHONHTTPSVERIFY'] = '0'
# os.environ['REQUESTS_CA_BUNDLE'] = ''
# os.environ['CURL_CA_BUNDLE'] = ''
# os.environ['SSL_CERT_FILE'] = ''

# # Deshabilitar warnings de SSL
# urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# # Configurar SSL para no verificar certificados
# ssl._create_default_https_context = ssl._create_unverified_context

# print("✅ SSL verificación deshabilitada (modo desarrollo con proxy)")

# # ============================================
# # 🔒 MONKEY PATCH PARA REQUESTS Y MSREST
# # ============================================
# import requests
# from requests.adapters import HTTPAdapter
# from urllib3.util.ssl_ import create_urllib3_context

# # Guardar las funciones originales UNA SOLA VEZ
# _original_get = requests.get
# _original_post = requests.post
# _original_session_request = requests.Session.request

# # Parchear requests.get
# def patched_get(url, **kwargs):
#     kwargs['verify'] = False
#     return _original_get(url, **kwargs)

# # Parchear requests.post
# def patched_post(url, **kwargs):
#     kwargs['verify'] = False
#     return _original_post(url, **kwargs)

# # Parchear requests.Session.request (esto cubre msrest)
# def patched_session_request(self, method, url, **kwargs):
#     kwargs['verify'] = False
#     return _original_session_request(self, method, url, **kwargs)

# # Aplicar los parches
# requests.get = patched_get
# requests.api.get = patched_get
# requests.post = patched_post
# requests.api.post = patched_post
# requests.Session.request = patched_session_request

# print("✅ Requests y msrest parcheados para ignorar SSL")

# # Importar dotenv y workflow
# from dotenv import load_dotenv
# from agent_builder_workflow import run_workflow, WorkflowInput

# # Cargar variables de entorno
# load_dotenv()

# # ============================================
# # 🔐 CONFIGURACIÓN DE AUTENTICACIÓN
# # ============================================

# APP_ID = os.getenv("MICROSOFT_APP_ID")
# APP_PASSWORD = os.getenv("MICROSOFT_APP_PASSWORD")
# APP_TYPE = os.getenv("MICROSOFT_APP_TYPE", "SingleTenant")
# APP_TENANT_ID = os.getenv("MICROSOFT_APP_TENANT_ID", "")

# # Debug de credenciales
# print(f"\n🐛 DEBUG - Credenciales cargadas:")
# print(f"   APP_ID: {APP_ID}")
# print(f"   APP_PASSWORD existe: {bool(APP_PASSWORD)}")
# print(f"   APP_PASSWORD length: {len(APP_PASSWORD) if APP_PASSWORD else 0}")
# print(f"   APP_TENANT_ID existe: {bool(APP_TENANT_ID)}")
# print(f"   APP_TENANT_ID length: {len(APP_TENANT_ID) if APP_TENANT_ID else 0}")

# # Verificar credenciales
# if not APP_ID or not APP_PASSWORD:
#     print("\n❌ ERROR: Faltan credenciales de Microsoft")
#     print("\nAsegúrate de tener en tu .env:")
#     print("  MICROSOFT_APP_ID=tu-app-id")
#     print("  MICROSOFT_APP_PASSWORD=tu-app-password")
#     print("\nVer: setup_azure_bot.md para obtener credenciales")
#     sys.exit(1)

# print("\n" + "="*60)
# print("🔐 Configuración de Autenticación")
# print("="*60)
# print(f"App ID: {APP_ID[:20]}...")
# print(f"App Type: {APP_TYPE}")
# print(f"Tenant ID: {APP_TENANT_ID[:20] if APP_TENANT_ID else 'N/A'}...")
# print("="*60 + "\n")

# # Configurar adapter con autenticación Y Tenant ID
# SETTINGS = BotFrameworkAdapterSettings(
#     app_id=APP_ID,
#     app_password=APP_PASSWORD,
#     channel_auth_tenant=APP_TENANT_ID
# )

# print("⚠️  MODO DESARROLLO: Autenticación deshabilitada")
# print("⚠️  Esto SOLO funciona para testing local, NO para Teams real")

# print(f"✅ Adapter configurado con Tenant ID: {APP_TENANT_ID[:20] if APP_TENANT_ID else 'N/A'}...")

# ADAPTER = BotFrameworkAdapter(SETTINGS)


# # ============================================
# # 🎯 MANEJO DE ERRORES
# # ============================================

# async def on_error(context: TurnContext, error: Exception):
#     """
#     Maneja errores globales del bot
#     """
#     print(f"\n❌ ERROR en bot:")
#     print(f"   Tipo: {type(error).__name__}")
#     print(f"   Mensaje: {str(error)}")
#     traceback.print_exc()
    
#     # Enviar mensaje al usuario
#     error_message = (
#         "Lo siento, ocurrió un error al procesar tu mensaje. "
#         "Por favor, intenta de nuevo o contacta al administrador."
#     )
    
#     try:
#         await context.send_activity(MessageFactory.text(error_message))
#     except Exception as send_error:
#         print(f"❌ Error enviando mensaje de error: {send_error}")

# ADAPTER.on_turn_error = on_error


# # ============================================
# # 🤖 BOT PRINCIPAL
# # ============================================

# class EYRAGBot(ActivityHandler):
#     """
#     Bot de EY que usa Agent Builder para responder consultas
#     """
    
#     def __init__(self):
#         super().__init__()
#         self.conversation_history = {}  # Historial por usuario
#         print("✅ EY RAG Bot inicializado")
    
#     async def on_message_activity(self, turn_context: TurnContext):
#         """
#         Maneja mensajes entrantes de usuarios
#         """
#         # Extraer información del mensaje
#         user_message = turn_context.activity.text.strip()
#         user_id = turn_context.activity.from_property.id
#         user_name = turn_context.activity.from_property.name or "Usuario"
#         conversation_id = turn_context.activity.conversation.id
#         channel_id = turn_context.activity.channel_id
        
#         print(f"\n{'='*60}")
#         print(f"📨 Mensaje recibido:")
#         print(f"   Usuario: {user_name} ({user_id})")
#         print(f"   Canal: {channel_id}")
#         print(f"   Conversación: {conversation_id}")
#         print(f"   Mensaje: {user_message[:100]}...")
#         print(f"{'='*60}")
        
#         # Manejar comandos especiales
#         if user_message.lower() in ['/help', 'help', 'ayuda']:
#             await self._send_help(turn_context, user_name)
#             return
        
#         if user_message.lower() in ['/clear', 'clear', 'limpiar']:
#             self.conversation_history[user_id] = []
#             await turn_context.send_activity("🗑️ Historial limpiado")
#             return
        
#         # Mostrar indicador de "escribiendo..."
#         await turn_context.send_activity(
#             Activity(type=ActivityTypes.typing)
#         )
        
#         try:
#             # ✅ Ejecutar Agent Builder workflow
#             print(f"🚀 Ejecutando Agent Builder...")
#             start_time = datetime.now()
            
#             result = await run_workflow(
#                 WorkflowInput(input_as_text=user_message)
#             )
            
#             elapsed_time = (datetime.now() - start_time).total_seconds()
            
#             # Extraer resultados
#             answer = result.get("output_text", "No pude generar una respuesta.")
#             sources = result.get("sources_array", [])
#             usage = result.get("usage", {})
            
#             print(f"✅ Respuesta generada en {elapsed_time:.2f}s")
#             print(f"   Caracteres: {len(answer)}")
#             print(f"   Fuentes: {len(sources)}")
#             print(f"   Tokens: {usage.get('total_tokens', 0):,}")
            
#             # Guardar en historial
#             if user_id not in self.conversation_history:
#                 self.conversation_history[user_id] = []
            
#             self.conversation_history[user_id].append({
#                 "query": user_message,
#                 "answer": answer,
#                 "timestamp": datetime.now().isoformat()
#             })
            
#             # Enviar respuesta formateada
#             await self._send_rag_response(
#                 turn_context=turn_context,
#                 query=user_message,
#                 answer=answer,
#                 sources=sources,
#                 usage=usage,
#                 elapsed_time=elapsed_time
#             )
            
#         except Exception as e:
#             error_msg = f"❌ Error procesando tu consulta: {str(e)}"
#             print(error_msg)
#             traceback.print_exc()
            
#             await turn_context.send_activity(
#                 MessageFactory.text(
#                     "Lo siento, hubo un error al procesar tu consulta. "
#                     "Por favor, intenta reformular tu pregunta."
#                 )
#             )
    
#     async def on_members_added_activity(
#         self, 
#         members_added: List[ChannelAccount], 
#         turn_context: TurnContext
#     ):
#         """
#         Se ejecuta cuando un usuario inicia el chat
#         """
#         for member in members_added:
#             if member.id != turn_context.activity.recipient.id:
#                 user_name = member.name or "usuario"
                
#                 welcome_text = f"""
# 👋 ¡Hola {user_name}! Soy el **Asistente RAG de EY**.

# Puedo ayudarte con:
# - 📋 Información sobre CVs del equipo
# - 💼 Experiencia técnica y certificaciones
# - 🔍 Búsqueda en la base de conocimiento
# - 🎯 Y mucho más...

# **Comandos disponibles:**
# - `/help` - Muestra esta ayuda
# - `/clear` - Limpia el historial de conversación

# ¿En qué puedo ayudarte hoy?
#                 """
                
#                 await turn_context.send_activity(
#                     MessageFactory.text(welcome_text.strip())
#                 )
    
#     async def _send_help(self, turn_context: TurnContext, user_name: str):
#         """Envía mensaje de ayuda"""
#         help_text = f"""
# 📖 **Ayuda - EY RAG Assistant**

# Hola {user_name}, aquí está la guía de uso:

# **¿Qué puedo hacer?**
# - Responder preguntas sobre el equipo de EY
# - Buscar información en CVs
# - Encontrar expertos en tecnologías específicas
# - Consultar experiencia y certificaciones

# **Ejemplos de preguntas:**
# - "¿Quién tiene experiencia en Python?"
# - "Encuentra personas con certificaciones cloud"
# - "¿Quiénes son Senior Managers con inglés avanzado?"

# **Comandos:**
# - `/help` - Muestra esta ayuda
# - `/clear` - Limpia historial

# **Tips:**
# - Sé específico en tus preguntas
# - Puedo entender preguntas en español e inglés
# - Si la respuesta no es clara, reformula la pregunta

# ¿Tienes alguna pregunta?
#         """
        
#         await turn_context.send_activity(
#             MessageFactory.text(help_text.strip())
#         )
    
#     async def _send_rag_response(
#         self,
#         turn_context: TurnContext,
#         query: str,
#         answer: str,
#         sources: List[str],
#         usage: dict,
#         elapsed_time: float
#     ):
#         """
#         Envía la respuesta usando Hero Card
#         """
#         # Crear acciones para fuentes (máximo 3)
#         actions = []
#         for i, source in enumerate(sources[:3], 1):
#             if source.startswith("http"):
#                 actions.append(
#                     CardAction(
#                         type=ActionTypes.open_url,
#                         title=f"📄 Fuente {i}",
#                         value=source
#                     )
#                 )
        
#         # Información de footer
#         footer_lines = []
#         if usage.get("total_tokens", 0) > 0:
#             footer_lines.append(f"🎫 {usage['total_tokens']:,} tokens")
#         if sources:
#             footer_lines.append(f"📚 {len(sources)} fuentes")
#         footer_lines.append(f"⏱️ {elapsed_time:.1f}s")
        
#         footer = " | ".join(footer_lines)
        
#         # Crear Hero Card
#         card = HeroCard(
#             title="💡 Respuesta",
#             subtitle=f"Pregunta: {query[:100]}{'...' if len(query) > 100 else ''}",
#             text=answer,
#             buttons=actions if actions else None
#         )
        
#         # Enviar card
#         attachment = Attachment(
#             content_type="application/vnd.microsoft.card.hero",
#             content=card
#         )
        
#         reply = MessageFactory.attachment(attachment)
#         await turn_context.send_activity(reply)
        
#         # Enviar footer como mensaje separado
#         if footer:
#             await turn_context.send_activity(
#                 MessageFactory.text(f"_{footer}_")
#             )


# # ============================================
# # 🌐 SERVIDOR WEB
# # ============================================

# BOT = EYRAGBot()


# async def messages(req: Request) -> Response:
#     """
#     Endpoint principal que recibe mensajes de Teams
#     """
#     # Verificar que sea POST
#     if req.method != "POST":
#         return Response(status=405, text="Method not allowed")
    
#     # Obtener body y header de autorización
#     body = await req.json()
#     auth_header = req.headers.get("Authorization", "")
    
#     # Crear actividad
#     activity = Activity().deserialize(body)
    
#     # Función callback para procesar el mensaje
#     async def call_bot(turn_context: TurnContext):
#         await BOT.on_turn(turn_context)
    
#     # ⚠️ MODO DESARROLLO: Procesar SIN validación de autenticación
#     try:
#         # Ignorar el auth_header y procesar directamente
#         await ADAPTER.process_activity(activity, auth_header, call_bot)  # ← Usar el auth_header real
#         return Response(status=200)
#     except Exception as e:
#         print(f"❌ Error procesando actividad: {e}")
#         traceback.print_exc()
#         return Response(status=500, text=str(e))


# async def health_check(req: Request) -> Response:
#     """Health check endpoint"""
#     return Response(
#         text="🤖 EY RAG Bot is running!\n\n" + 
#              f"App ID: {APP_ID[:20]}...\n" +
#              f"Status: ✅ Active",
#         status=200
#     )


# def create_app() -> web.Application:
#     """Crea la aplicación web"""
#     app = web.Application()
    
#     # Rutas
#     app.router.add_post("/api/messages", messages)
#     app.router.add_get("/api/messages", health_check)
#     app.router.add_get("/health", health_check)
#     app.router.add_get("/", health_check)
    
#     return app


# # ============================================
# # 🚀 MAIN
# # ============================================

# if __name__ == "__main__":
#     print("\n" + "="*60)
#     print("🚀 INICIANDO EY RAG BOT PARA MICROSOFT TEAMS")
#     print("="*60)
#     print(f"\n📡 Endpoints:")
#     print(f"   - Messages: http://localhost:3978/api/messages")
#     print(f"   - Health:   http://localhost:3978/health")
#     print(f"\n⚠️  IMPORTANTE:")
#     print(f"   1. Asegúrate de tener el túnel activo")
#     print(f"   2. URL configurada en Azure Bot Configuration")
#     print(f"   3. Ejemplo: https://tu-url.devtunnels.ms/api/messages")
#     print("="*60 + "\n")
    
#     app = create_app()
    
#     try:
#         web.run_app(app, host="0.0.0.0", port=3978)
#     except KeyboardInterrupt:
#         print("\n\n👋 Bot detenido por el usuario")
#     except Exception as e:
#         print(f"\n❌ Error fatal: {e}")
#         traceback.print_exc()