from src.services.azure_storage_service import get_specific_file_from_blob_container
from src.config import config
from src.services.docintelligence_service import get_content_from_document
from datetime import datetime
import re
import tiktoken
import asyncio
# from helpers import helper_adapter_kibana
from src.models.Timestamps import Timestamps
from src.models.doc_model import DocEntity
from src.document_ingestion import processchunks
from difflib import SequenceMatcher

# Set Config Azure Blob Storage
storageaccountname = config.azure_storage_account
storageaccountkey = config.azure_storage_key
containername = config.azure_container_name
cosmosendpoint = config.cosmos_endpoint
cosmoskey = config.cosmos_key
dbname = config.cosmosdb_database
containerdbname = config.cosmosdb_container
sublotes_flag = config.sublotes_flag
# Cargar el tokenizador
encoding = tiktoken.encoding_for_model(config.azure_openai_emb_name)
# Sublotes True / False
sublotes_flag = config.sublotes_flag

def get_text_split(blob_name, docId, get_formulas: bool = False, SessionId="", doc_entity=None, CDU: str=""):
    if doc_entity is None:
        doc_entity = {}
    doc_entity = DocEntity(**doc_entity).model_dump(exclude_none=True)

    timestamps_List = []
    timestamps_List.append(Timestamps("01 init"))
    boolformulas = "false"
    idcaso = doc_entity.get("id_caso")
    success = True
    startrun = datetime.now()
    formula_pattern = r"(\$\$.*?\$\$|\\\[.*?\\\]|\\\(.*?\\\)|\\[a-zA-Z]+|\^|_|\\frac|\\sum|\\int|\\begin{.*?}|\\end{.*?})"
    CDU = "DOCPROCESS"

    if get_formulas and docId.lower().endswith(('.pdf')):
        boolformulas = True
    else:
        boolformulas = False

    ExceptionReason = ""
    try:
        Call_id = SessionId + docId.split("_")[0]
        blob_names = [docId]
        
        display_name = doc_entity.get("doc_nombre", docId)
        
        for blob_name in blob_names:    
            print(f"Now processing: Doc ID {docId} and {blob_name}")
            lchunks = 0
            last_page_number = 0
            timestamps_List.append(Timestamps("02 getDoc"))
            
            # Descargar la informacion del documento que se va a enviar al DOC INTELLIGENCE
            file_download = asyncio.run(get_specific_file_from_blob_container(
                storageaccountname, storageaccountkey, containername, docId, SessionId, Call_id, CDU
            ))

            timestamps_List.append(Timestamps("03 ReadDoc"))
            
            result = asyncio.run(get_content_from_document(
                file_download=file_download, SessionId=SessionId, boolformulas=boolformulas
            ))
            
            # Obtener el contenido completo del documento
            full_content = result.content
            timestamps_List.append(Timestamps("04 getPagesInfo"))
            
            # Crear un diccionario para almacenar el contenido por página
            page_contents = {}

            if docId.lower().endswith(('.pdf')):
                for paragraph in result.paragraphs:
                    for region in paragraph.bounding_regions:
                        page_number = region.page_number
                        content = paragraph.content

                        if re.search(formula_pattern, content):
                            continue
                        
                        if page_number > last_page_number:
                            last_page_number = page_number
                        
                        if page_number not in page_contents:
                            page_contents[page_number] = {"paragraphs": [content]}
                        else:
                            page_contents[page_number]["paragraphs"].append(content)
            else: 
                for page in getattr(result, "pages", []) or []:
                    page_number = getattr(page, "page_number", None) or getattr(page, "pageNumber", None)

                    page_text_parts = []
                    if getattr(page, "spans", None):
                        for sp in page.spans:
                            start = sp.offset
                            end = start + sp.length
                            page_text_parts.append(full_content[start:end])
                        page_text = "".join(page_text_parts).strip()
                    elif getattr(page, "lines", None):
                        page_text = "\n".join(getattr(ln, "content", "") for ln in page.lines).strip()
                    else:
                        related_paragraphs = []
                        for p in getattr(result, "paragraphs", []) or []:
                            for br in getattr(p, "bounding_regions", []) or []:
                                if getattr(br, "page_number", None) == page_number:
                                    related_paragraphs.append(p.content)
                                    break
                        page_text = "\n\n".join(related_paragraphs).strip()

                    if formula_pattern and re.search(formula_pattern, page_text):
                        continue

                    if page_number and page_number > last_page_number:
                        last_page_number = page_number

                    page_contents[page_number] = {"paragraphs": [page_text]}

            # Generar el contenido con etiquetas de páginas
            last_position = 0
            for page_number in sorted(page_contents.keys()):
                page_label = f" PG{page_number} "
                paragraphs = page_contents[page_number]["paragraphs"]
                
                if not paragraphs:
                    continue
                
                last_content = paragraphs[-1]
                
                if len(paragraphs) <= 2:
                    middle_content = paragraphs[0]
                else:
                    middle_index = len(paragraphs) // 2
                    middle_content = paragraphs[middle_index]

                if len(paragraphs) != 1:
                    middle_position = full_content.find(middle_content, last_position)
                    if middle_position != -1:
                        middle_position += len(middle_content)
                        full_content = full_content[:middle_position] + f"\n[MIDDLE PG{page_number}]" + full_content[middle_position:]
                        last_position = middle_position

                last_position = full_content.find(last_content, last_position)
                if last_position != -1:
                    last_position += len(last_content)
                    full_content = full_content[:last_position] + f"\n{page_label}" + full_content[last_position:]

            full_content = re.sub(r'\n\[MIDDLE PG\d+\]', '', full_content, flags=re.DOTALL).strip()

            # Procesamiento de fórmulas
            formulas_dict = {}
            if boolformulas:
                for page in result.pages:
                    page_number = page.page_number
                    page_formulas = []
                    
                    if hasattr(page, 'formulas') and page.formulas is not None:
                        for formula in page.formulas:
                            page_formulas.append(formula.value)
                    
                    if page_formulas:
                        formulas_dict[page_number] = page_formulas

                sections = full_content.split("PG")
                updated_content = ""

                for i, section in enumerate(sections):
                    if i == 0 and not section.strip():
                        continue

                    page_number = i + 1
                    page_content = section.strip()
                    watermark = f"PG{page_number}"

                    page_lines = page_content.splitlines()
                    processed_page_content = ""

                    for line in page_lines:
                        if page_number in formulas_dict and formulas_dict[page_number]:
                            if ":formula:" in line:
                                formula_to_insert = formulas_dict[page_number].pop(0)
                                line = line.replace(":formula:", f"{formula_to_insert}", 1)
                        
                        processed_page_content += line + "\n"

                    if page_number in formulas_dict and not formulas_dict[page_number]:
                        del formulas_dict[page_number]

                    updated_content += processed_page_content.strip() + "\n" + watermark + "\n"

                full_content = updated_content
                full_content = re.sub(r'\n?Formula="[^"]+"\n?', '', full_content)

            timestamps_List.append(Timestamps("05 getTablesInfo"))
            
            # Procesamiento de tablas
            tables_by_page = {}
            if result.tables is not None:
                tables_info = []
                tables_on_page = {}
                
                for table_idx, table in enumerate(result.tables):
                    table_content = processchunks.convert_table_to_markdown(table)
                    column_count = table.column_count
                    page_numbers = set()
                    for region in table.bounding_regions:
                        page_numbers.add(region.page_number)
                    page_numbers = sorted(page_numbers)
                    
                    table_info = {
                        'index': table_idx,
                        'table': table,
                        'content': table_content,
                        'column_count': column_count,
                        'page_numbers': page_numbers
                    }
                    tables_info.append(table_info)
                    
                    for page_number in page_numbers:
                        if page_number not in tables_on_page:
                            tables_on_page[page_number] = []
                        tables_on_page[page_number].append(table_info)
                
                page_last_tables = {}
                for page_number, tables in tables_on_page.items():
                    page_last_tables[page_number] = tables[-1]
                
                last_table_starts = {}
                for page_number, info in page_last_tables.items():
                    start_content = info['content'][:40]
                    if start_content not in last_table_starts:
                        last_table_starts[start_content] = 0
                    last_table_starts[start_content] += 1
                
                total_pages = len(tables_on_page)
                footer_table_starts = set()
                for start_content, count in last_table_starts.items():
                    if count >= total_pages / 2:
                        footer_table_starts.add(start_content)
                
                for idx, info in enumerate(tables_info):
                    table_content = info['content']
                    column_count = info['column_count']
                    page_numbers = info['page_numbers']
                    
                    is_footer = False
                    for page_number in page_numbers:
                        if (page_number in page_last_tables and
                            page_last_tables[page_number]['index'] == info['index']):
                            start_content = table_content[:40]
                            if start_content in footer_table_starts:
                                is_footer = True
                                break
                    
                    if is_footer:
                        continue
                    
                    found_ongoing = False
                    for prev_idx in range(idx - 1, -1, -1):
                        prev_info = tables_info[prev_idx]
                        if prev_info['content'][:40] in footer_table_starts:
                            continue
                        if (prev_info['column_count'] == column_count and
                            prev_info['page_numbers'][-1] + 1 == page_numbers[0]):
                            combined_content = prev_info.get('combined_content', prev_info['content']) + '\n' + table_content
                            prev_info['combined_content'] = combined_content
                            prev_info['page_numbers'] += page_numbers
                            info['combined'] = True
                            found_ongoing = True
                            break
                    
                    if not found_ongoing and not info.get('combined', False):
                        info['combined_content'] = table_content
                
                for info in tables_info:
                    if info.get('combined', False):
                        continue
                    content = info.get('combined_content', info['content'])
                    for page_number in info['page_numbers']:
                        if page_number not in tables_by_page:
                            tables_by_page[page_number] = [content]
                        else:
                            if content not in tables_by_page[page_number]:
                                tables_by_page[page_number].append(content)

            formulas_by_page = {}
            if boolformulas:
                for page in result.pages:
                    page_number = page.page_number
                    page_formulas = []
                    
                    if hasattr(page, 'formulas') and page.formulas is not None:
                        for formula in page.formulas:
                            if formula.confidence > 0.5:
                                page_formulas.append(formula.value)
                    
                    if page_formulas:
                        formulas_by_page[page_number] = page_formulas

            assert isinstance(full_content, str), "El contenido del documento no es una cadena de texto"

            timestamps_List.append(Timestamps("06 removeContentNoise"))
            
            # Limpieza de contenido
            filtered_full_content = processchunks.clean_false_checkbox(result, full_content, confidence=0.7)
            filtered_full_content = processchunks.detect_and_remove_headers_footers(filtered_full_content, last_page_number)
            filtered_full_content = processchunks.eliminar_figuras_repetidas(filtered_full_content)
            filtered_full_content = processchunks.detect_and_remove_duplicate_tables(filtered_full_content, last_page_number)
            filtered_full_content = re.sub(r'(?:(:selected:|:unselected:)( ?)){4,}', '', filtered_full_content, flags=re.MULTILINE)
            filtered_full_content = re.sub(r'(?m)(^(:selected:|:unselected:)\s*$\n){4,}', '', filtered_full_content, flags=re.MULTILINE)
            filtered_full_content = re.sub(r'((:selected:|:unselected:)( ?)<figure>|<figure>( ?)(:selected:|:unselected:))', '', filtered_full_content, flags=re.MULTILINE)
            filtered_full_content = re.sub(r'(?:(:formula:)( ?)){4,}', '', filtered_full_content, flags=re.MULTILINE)
            filtered_full_content = re.sub(r'(?m)(^(:formula:)\s*$\n){4,}', '', filtered_full_content, flags=re.MULTILINE)
            filtered_full_content = re.sub(r'((:formula:)( ?)<figure>|<figure>( ?)(:formula:))', '', filtered_full_content, flags=re.MULTILINE)
            filtered_full_content = re.sub(r'!\[\]\(figures/(\d+)\)\n', '', filtered_full_content, flags=re.DOTALL).strip()
            filtered_full_content = re.sub(r':formula:', '', filtered_full_content, flags=re.IGNORECASE).strip()
            filtered_full_content = re.sub(r'<!--\s*PageNumber="[^"]*"\s*-->', '', filtered_full_content, flags=re.DOTALL).strip()
            filtered_full_content = re.sub(r'<!--\s*PageHeader=.*?-->"', '', filtered_full_content, flags=re.DOTALL).strip()
            filtered_full_content = re.sub(r'<!--\s*PageHeader="[^"]*"\s*-->', '', filtered_full_content, flags=re.DOTALL).strip()
            filtered_full_content = re.sub(r'<!--\s*(.*?)\s*-->', r'\1', filtered_full_content, flags=re.DOTALL).strip()
            filtered_full_content = re.sub(r'PageHeader="([^"]*)"', r'\1', filtered_full_content, flags=re.DOTALL).strip()
            filtered_full_content = re.sub(r'PageFooter="([^"]*)"', r'\1', filtered_full_content, flags=re.DOTALL).strip()
            filtered_full_content = re.sub(r'FigureContent="([^"]*)"', r'\1', filtered_full_content, flags=re.DOTALL).strip()
            filtered_full_content = re.sub(r'\n\[MIDDLE PG\d+\]', '', filtered_full_content, flags=re.DOTALL).strip()
            filtered_full_content = re.sub(r'<figure>\n.{0,5}</figure>', '', filtered_full_content, flags=re.DOTALL).strip()

            timestamps_List.append(Timestamps("07 ChunkingProcess"))

            chunks = processchunks.markdown_percentage(filtered_full_content, 2000, 0.1, 1000, 3000)

            output_path = f"{SessionId or 'document'}_output_chunkscontent.txt"
            # with open(output_path, "w", encoding="utf-8") as f:
            #     f.write(str(chunks))
            
            lchunks = len(chunks)
            print(f"{docId}: Número de chunks del documento {lchunks}")
            
            title = ""
            last_apartado = ""
            last_subapartado = ""
            last_threeheader = ""
            last_fourheader = ""
            last_fiveheader = ""
            array_apartados = []
            array_subapartados = []
            array = []
            page_range = ""
            
            if boolformulas:
                most_common_locale = processchunks.get_most_common_locale(result)
            else:
                most_common_locale = "es"
            
            first_page = 1

            timestamps_List.append(Timestamps("08 sendChunksToCosmos"))
            prev_last_page, prev_chunk = 0, ''

            print(f"{docId}: Uploading chunks to Cosmos...")
            
            for index, chunk in enumerate(chunks):
                pages = re.findall(r'PG(\d+)', chunk)
                if pages:
                    first_page = int(pages[0])
                    last_page = int(pages[-1])
                    
                    if last_page is not None and not chunk[-10:].__contains__(f"PG{last_page}"):
                        last_page += 1

                    page_range = f"{first_page}-{last_page}"
                else:
                    if index == 0:
                        first_page = last_page = 1
                        page_range = f"{last_page}"
                    elif index != 0 and prev_chunk[-10:].__contains__(f"PG{prev_last_page}"):
                        last_page += 1
                        page_range = f"{last_page}"
                    elif index != 0 and not prev_chunk[-10:].__contains__(f"PG{prev_last_page}"):
                        page_range = f"{last_page}"

                if first_page == last_page:
                    page_range = f"{first_page}"

                prev_last_page, prev_chunk = last_page, chunk

                title = processchunks.detect_title(chunk)
                array_apartados = processchunks.detect_headers(chunk, 1)
                array_subapartados = processchunks.detect_headers(chunk, 2)
                array_threeheader = processchunks.detect_headers(chunk, 3)
                array_fourheader = processchunks.detect_headers(chunk, 4)
                array_fiveheader = processchunks.detect_headers(chunk, 5)
                array = array_apartados + array_subapartados + array_threeheader + array_fourheader + array_fiveheader

                current_apartado = processchunks.detect_title(chunk)
                current_subapartado = processchunks.detect_subtitle(chunk)
                current_threeheader = processchunks.detect_threeheader(chunk)
                current_fourheader = processchunks.detect_fourheader(chunk)
                current_fiveheader = processchunks.detect_fiveheader(chunk)
                
                if current_apartado:
                    last_apartado = current_apartado
                if current_subapartado:
                    last_subapartado = current_subapartado
                if current_threeheader:
                    last_threeheader = current_threeheader
                if current_fourheader:
                    last_fourheader = current_fourheader
                if current_fiveheader:
                    last_fiveheader = current_fiveheader

                if not current_fiveheader and not current_fourheader and not current_threeheader and not current_subapartado and not current_apartado and last_fiveheader:
                    chunk = last_fiveheader + "\n" + chunk
                if not current_fourheader and not current_threeheader and not current_subapartado and not current_apartado and last_fourheader:
                    chunk = last_fourheader + "\n" + chunk
                if not current_threeheader and not current_subapartado and not current_apartado and last_threeheader:
                    chunk = last_threeheader + "\n" + chunk
                if not current_subapartado and not current_apartado and last_subapartado:
                    chunk = last_subapartado + "\n" + chunk
                if not current_apartado and last_apartado:
                    chunk = last_apartado + "\n" + chunk

                tables = []
                if pages:
                    for page_num in range(first_page, last_page + 1):
                        if page_num in tables_by_page:
                            for table in tables_by_page[page_num]:
                                if table not in tables:
                                    tables.append(table)
                else:
                    if last_page in tables_by_page:
                        for table in tables_by_page[last_page]:
                            if table not in tables:
                                tables.append(table)

                formulas = []
                if boolformulas:
                    if pages:
                        for page_num in range(first_page, last_page + 1):
                            if page_num in formulas_by_page:
                                for formula in formulas_by_page[page_num]:
                                    if formula not in formulas:
                                        formulas.append(formula)
                    else:
                        if last_page in formulas_by_page:
                            for formula in formulas_by_page[last_page]:
                                if formula not in formulas:
                                    formulas.append(formula)

                # ✅ Usar display_name en lugar de blob_name
                processchunks.upload_chunks(
                    index + 1, 
                    page_range, 
                    title, 
                    array, 
                    chunk, 
                    display_name,
                    most_common_locale, 
                    tables, 
                    formulas, 
                    doc_entity, 
                    SessionId, 
                    Call_id, 
                    CDU
                )
            
            print(f"{docId}: {lchunks} chunks uploaded to Cosmos")
            
    except Exception as err:
        success = False
        print(f"Enviando error al webhook del ID del documento: {docId}")
        if len(timestamps_List) > 0:
            ExceptionReason = f"Error en {timestamps_List[-1].get_nombre()}: {err}"
        else:
            ExceptionReason = f"Error: {err}"
        print(ExceptionReason)
    
    # try:
    #     _logAdapterTransaction(timestamps=timestamps_List,
    #                         CDU= CDU,
    #                         SessionId=SessionId,
    #                         Call_id=Call_id,
    #                         startrun=startrun,
    #                         success=success,
    #                         doc_entity=doc_entity,
    #                         nchunks=lchunks,
    #                         npages = last_page_number,
    #                         ExceptionReason=ExceptionReason
    #                         )
    # except Exception as err:
    #         print(f"Error en el log de chunk: {err}")

####### KIBANA
# def _logAdapterTransaction(timestamps,CDU,SessionId, startrun,Call_id, success, doc_entity, nchunks,npages,ExceptionReason):
#         timestamps.append(Timestamps("end"))
#         DATA_LECTOR= {
#             "id_unico": doc_entity.get("id"),
#             "doc_id": doc_entity.get("doc_id"),
#             "doc_nombre": doc_entity.get("doc_nombre"),
#             "nchunks":nchunks,
#             "npages": npages
#         }
#         #DATA_Lector_Extraction["respuesta"]=response
#         #   #timesJson = helper_adapter_kibana.createTimesJson(dif_searchdocsms,dif_openaims,dif_ms)
#         TotalTimeStepsJson =  helper_adapter_kibana.createTotalTimeStepsJson(timestamps)
#         #timestampsJson =  helper_adapter_kibana.createTimestampsJson(timestamps)

#         helper_adapter_kibana.sendKibanaTransacciones(SessionId=SessionId,
#                                                 Call_id=Call_id,
#                                                 IDU=Call_id,
#                                                 CasoTES=doc_entity.get("id_caso"),
#                                                 User=doc_entity.get("usuario"),
#                                                 Equipo=doc_entity.get("equipo"),
#                                                 Success=success,
#                                                 ExceptionReason=ExceptionReason,
#                                                 Type=CDU,
#                                                 TotalTime_Steps_lector_documents=TotalTimeStepsJson,
#                                                 TotalTime=(datetime.now() - startrun).total_seconds() * 1000,
#                                                 DATA_LECTOR=DATA_LECTOR
#                                                 )