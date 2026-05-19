from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import DocumentAnalysisFeature
from src.config import config
# from helpers.kibana.helper_kibana import sendKibanaAPI
from datetime import datetime
import asyncio
async def get_content_from_document(file_download, SessionId="", Call_id="", retries=3, boolformulas: bool = False):
    CDU = "DOCPROCESS"
    output = ""
    success = True
    statusCode = 0
    startrun = datetime.now()
    try:
        document_intelligence_client = DocumentIntelligenceClient(
            endpoint=config.doc_intel_url,  # ✅ minúsculas
            credential=AzureKeyCredential(config.doc_intel_key)  # ✅ minúscu
        )
        if boolformulas:
            print("Obteniendo content con formulas")
            poller = document_intelligence_client.begin_analyze_document(
                "prebuilt-layout",
                body=file_download,
                content_type="application/octet-stream",
                features=[DocumentAnalysisFeature.FORMULAS, DocumentAnalysisFeature.LANGUAGES],
                output_content_format="markdown",
            )
        else:
            poller = document_intelligence_client.begin_analyze_document(
                "prebuilt-layout",
                body=file_download,
                content_type="application/octet-stream",
                output_content_format="markdown",
            )
        result = poller.result()
        # # Guardar en un .txt
        # output_path = f"{SessionId or 'document'}_outputppt.txt"
        # with open(output_path, "w", encoding="utf-8") as f:
        #     f.write(str(result))
        statusCode = 200
        output = "OK"
        # _logAdapterDocIntelligence(
        #     "",
        #     output,
        #     statusCode,
        #     Config.DOC_INTEL_URL,
        #     success,
        #     startrun,
        #     SessionId=SessionId,
        #     Call_id=Call_id,
        #     CDU=CDU,
        # )
        return result
    except Exception as e:
        error_message = str(e)
        output = "Error Exception: " + error_message
        success = False
        statusCode = 999
        print("Failed getting content from Document Intelligence: ", error_message)
        if retries > 0:
            print(f"Retrying... Attempts left: {retries - 1}")
            await asyncio.sleep(5)
            return await get_content_from_document(
                file_download, SessionId, Call_id, retries=retries - 1, boolformulas=boolformulas
            )
        else:
            print("Max retries reached. Operation failed.")
            # try:
            #     _logAdapterDocIntelligence(
            #         "",
            #         output,
            #         statusCode,
            #         Config.DOC_INTEL_URL,
            #         success,
            #         startrun,
            #         SessionId=SessionId,
            #         Call_id=Call_id,
            #         CDU=CDU,
            #     )
            # except Exception as err:
            #     print(f"Error log kibana webhook {str(err)}")
# def _logAdapterDocIntelligence(Body,Output,StatusCode,Url,Success,Startrun,SessionId="",Call_id="",CDU=""):
#     sendKibanaAPI(
#                   Body=Body,
#                   StatusCode=StatusCode,
#                   Url=Url,
#                   Output=Output, 
#                   Socket="Helper_DocIntelligence",
#                   TotalTime=(datetime.now() - Startrun).total_seconds() * 1000,
#                   Success=Success,
#                   SessionId=SessionId,
#                   Call_id=Call_id,
#                   CDU=CDU
#                   )