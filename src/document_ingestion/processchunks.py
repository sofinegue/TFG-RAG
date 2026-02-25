from config import config as Config
import json
from services.openai_service import get_embedding
from services.cosmos_service import upload_doc_cosmos
from langchain_text_splitters import MarkdownHeaderTextSplitter  # ✅ CORREGIDO
import uuid  # ✅ AÑADIDO (faltaba este import)
from datetime import datetime
import hashlib
import re
import unicodedata
from collections import Counter
import tiktoken
from typing import Any, Dict, List, Optional
import os

# Set Config Cosmos DB
cosmosendpoint = Config.cosmos_endpoint  # ✅ minúsculas
cosmoskey = Config.cosmos_key  # ✅ minúsculas
dbname = Config.cosmosdb_database  # ✅ nombre corregido
containerdbname = Config.cosmosdb_container_cvs  # ✅ nombre corregido
sublotes_flag = Config.sublotes_flag  # ✅ ya es bool, no necesita bool(int(...))

# Cargar el tokenizador
encoding = tiktoken.get_encoding("cl100k_base")

def mark_existing_chunks_as_deleted(doc_title: str, cosmos_endpoint: str, cosmos_key: str, db_name: str, container_name: str):
    """
    Marca como borrados (isDeleted=True) todos los chunks existentes de un documento
    antes de subir nuevos chunks
    
    Args:
        doc_title: Nombre del documento (sin UUID)
        cosmos_endpoint: Endpoint de Cosmos
        cosmos_key: Key de Cosmos
        db_name: Nombre de la base de datos
        container_name: Nombre del container
    
    Returns:
        int: Número de chunks marcados como borrados
    """
    try:
        from services.cosmos_service import cosmos_container_connection
        
        container = cosmos_container_connection(cosmos_key, cosmos_endpoint, db_name, container_name)
        
        # Query para encontrar todos los chunks del documento que no estén ya borrados
        query = f"SELECT * FROM c WHERE c.docTitle = '{doc_title}' AND c.isDeleted = false"
        
        existing_chunks = list(container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        if not existing_chunks:
            return 0
        
        print(f"    🗑️ Marcando {len(existing_chunks)} chunks previos de '{doc_title}' como borrados...")
        
        marked_count = 0
        for chunk in existing_chunks:
            try:
                chunk['isDeleted'] = True
                container.replace_item(item=chunk['id'], body=chunk)
                marked_count += 1
            except Exception as e:
                print(f"      ⚠️ Error marcando chunk {chunk.get('id')}: {e}")
        
        print(f"    ✅ {marked_count} chunks marcados como borrados")
        return marked_count
        
    except Exception as e:
        print(f"    ⚠️ Error marcando chunks como borrados: {e}")
        return 0


# Variable global para controlar si ya se verificó este documento en esta sesión
_checked_documents = set()


def upload_chunks(index, page_number, title, array, content, blob_name, topl, tables, formulas, doc_entity, SessionId, Call_id, CDU):
    try: 
        normalized_blob_name = (blob_name or "").replace("\\", "/")
        path_parts = [part for part in normalized_blob_name.split("/") if part]
        source_collection = path_parts[0] if len(path_parts) > 0 else doc_entity.get("source_collection", "")
        source_language = path_parts[1] if len(path_parts) > 1 else doc_entity.get("language", "")

        # ✅ Verificar y marcar chunks previos SOLO en el primer chunk (index == 1)
        if index == 1 and blob_name not in _checked_documents:
            print(f"  🔍 Verificando chunks previos de '{blob_name}'...")
            mark_existing_chunks_as_deleted(
                doc_title=blob_name,
                cosmos_endpoint=cosmosendpoint,  # ✅ Pasar como parámetro
                cosmos_key=cosmoskey,            # ✅ Pasar como parámetro
                db_name=dbname,                  # ✅ Pasar como parámetro
                container_name=containerdbname   # ✅ Pasar como parámetro
            )
            _checked_documents.add(blob_name)
        
        # Generar ID y sanitizarlo para Azure Search
        raw_id = str(uuid.uuid4())
        id = re.sub(r'[^a-zA-Z0-9_\-=]', '-', raw_id)
        
        title = title.replace("#", "").strip()
        title = re.sub(r'\\{1,3}', '', title)

        # Eliminar marca de pagina del content
        content = re.sub(r'PG\d+', '', content, flags=re.DOTALL).strip()
        # Eliminar checkbox del embedding
        embeddingcontent = content.replace(":selected:", "").replace(":unselected:", "")
        
        chunkid = generate_chunkid(blob_name, content, title, page_number)

        # Intentamos contar los tokens usando tiktoken
        tokenl = encoding.encode(content)
        datapoints_list = load_datapoints()
        datapoints = extract_datapoints(content, datapoints_list) if datapoints_list else []
        
        paragraph_data = {
            "id": id,
            "chunkId": chunkid,
            "docTitle": blob_name,
            "sourcePath": normalized_blob_name,
            "sourceCollection": source_collection,
            "sourceLanguage": source_language,
            "sectionContent": content,
            "embeddingContent": embeddingcontent,
            "QuestionsText": "",
            "docSummary": "",
            "Content_length": len(tokenl),
            "isCreated": datetime.now().isoformat(),
            "Pages": page_number,
            "Contains_checkbox": contains_checkbox(content),
            "Contains_selected_checkbox": contains_selected_checkbox(content),
            "Contains_lote": contains_lote(content, sublotes_flag),
            "Contains_formulas": bool(formulas),
            "Datapoints": datapoints,
            "Title": title,
            "Sections": array,
            "nChunk": index,
            "isDeleted": False,
            "topLanguage": topl,
            "Tables": tables,
            "Formulas": formulas,
            "embedding": get_embedding(embeddingcontent, Config.azure_openai_emb_name, SessionId, Call_id, CDU, doc_entity)
        }

        ### COSMOS DB
        upload_doc_cosmos(cosmosendpoint, cosmoskey, dbname, containerdbname, paragraph_data, SessionId, Call_id, CDU)
        
    except Exception as err:
        print(f"ERROR AL SUBIR EL CHUNK A COSMOS: {err}")

# Limpieza de falsos checkbox 
def clean_false_checkbox(result, text, confidence):
    # Guardo todos los checkbox en una lista
    selectionMarks = []
    for page in result.pages:
        if 'selectionMarks' in page.keys():
            for selectionMark in page['selectionMarks']:
                selectionMarks.append(selectionMark)

    # Identifico todos los checkbox del contenido y elimino los que no superen el % confianza
    pattern = re.compile(r':(selected|unselected):')
    last_pos, new_content = 0 , '' 
    for i, match in enumerate(pattern.finditer(text)):
        start, end = match.span()
        fin = end if selectionMarks[i]['confidence'] > confidence else start
        new_content += text[last_pos:fin]     
        last_pos = end 

    new_content += text[last_pos:]
    return new_content


def detect_headers(content, level):
    """
    Detecta encabezados basados en el nivel de '###' de markdown.
    
    :param content: El texto donde buscar encabezados.
    :param level: Nivel del encabezado. Por ejemplo, 1 para '#', 2 para '##', y así sucesivamente.
    :return: Una lista de encabezados limpios.
    """
    header_pattern = r"^\s*{}(?!#)(.+)".format('#' * level)
    headers = re.findall(header_pattern, content, re.MULTILINE)
    cleaned_headers = delete_noise(headers)
    return cleaned_headers

def detect_and_remove_headers_footers(content, total_pages, avg = 0, min_occurrences = 7):

    # Lineas con los siguientes patrones no deben eliminarse
    special_patterns = [
        r":selected:", r":unselected:", 
        r"\bs[ií]\b",  r"\bno(n?)\b",                       
        r"procede"
    ]

    special_regex = re.compile("|".join(special_patterns), re.IGNORECASE)
    
    # Identificacion y eliminación de lineas repetidas
    lines = content.split('\n')
    counter = Counter(lines)
    common_lines = [
        line for line, count in counter.items()
        if count >= min_occurrences 
        and count > int(total_pages * avg) # TODO: calcular % min ocurrencias 
        and not special_regex.search(line.lower())
    ]

    filtered_lines = "\n".join(line for line in lines if line not in common_lines)

    return filtered_lines

def get_most_common_locale(result):
    locale_counts = {}
    for language in result.languages:
        if language.confidence > 0.8:
            locale = language.locale
            if locale in locale_counts:
                locale_counts[locale] += 1
            else:
                locale_counts[locale] = 1
    sorted_locales = sorted(locale_counts.items(), key=lambda item: item[1], reverse=True)
    return sorted_locales[0][0] if sorted_locales else None

def convert_table_to_markdown(table):
    markdown_table = ""
    max_row = max(cell.row_index for cell in table.cells) + 1
    max_col = max(cell.column_index for cell in table.cells) + 1
    table_matrix = [["" for _ in range(max_col)] for _ in range(max_row)]
    for cell in table.cells:
        table_matrix[cell.row_index][cell.column_index] = cell.content

    for row in table_matrix:
        markdown_table += "|" + "|".join(row) + "|\n"
    return markdown_table

def get_top_locale(payload: Dict[str, Any], default: str = "und") -> str:
    """
    Devuelve el 'locale' con mayor 'confidence' del objeto JSON.
    - Si faltan campos, ignora esas entradas.
    - Si no hay idiomas válidos, devuelve 'default' (und = undefined).
    """
    languages: List[Dict[str, Any]] = payload.get("languages", [])
    if not isinstance(languages, list):
        return default

    top: Optional[Dict[str, Any]] = None

    for item in languages:
        try:
            locale = item["locale"]
            conf = float(item["confidence"])
        except (KeyError, TypeError, ValueError):
            continue  # entrada mal formada, la saltamos

        if top is None or conf > top["confidence"]:
            top = {"locale": locale, "confidence": conf}

    return top["locale"] if top else default

def es_tabla_markdown(contenido):
    """
    Determina si una sección del contenido contiene una tabla en formato Markdown.
    Una tabla en Markdown suele contener barras verticales '|' o líneas separadoras '---'.
    """
    lineas = contenido.split("\n")
    for linea in lineas:
        if "|" in linea or re.match(r"^\s*---", linea):
            return True
    return False

def combinar_splits_tablas(sub_splits, max_tokens, distancia_maxima=50):
    """
    Combina splits que contienen tablas o están cerca de ellas (menos de X caracteres entre tablas).
    
    Parámetros:
    sub_splits (list): Lista de fragmentos ya divididos.
    max_tokens (int): Número máximo de tokens antes de permitir dividir tablas.
    distancia_maxima (int): Distancia máxima en caracteres entre dos tablas para evitar separarlas.
    
    Retorna:
    list: Lista combinada de splits respetando las tablas.
    """
    final_splits = []
    i = 0
    
    while i < len(sub_splits):
        current_split = sub_splits[i]
        current_tokens = len(encoding.encode(current_split))
        
        if es_tabla_markdown(current_split):
            # Verificamos la distancia al siguiente fragmento
            if i < len(sub_splits) - 1:
                next_split = sub_splits[i + 1]
                next_tokens = len(encoding.encode(next_split))
                
                # Si el siguiente fragmento también es una tabla o está muy cerca
                if es_tabla_markdown(next_split):
                    distancia = len(current_split) + len(next_split)
                    if distancia <= distancia_maxima and current_tokens + next_tokens <= max_tokens:
                        # Combinar los splits si cumplen las condiciones
                        current_split += next_split
                        i += 1  # Avanzar un índice adicional porque combinamos los splits
                    else:
                        final_splits.append(current_split)
                else:
                    final_splits.append(current_split)
            else:
                final_splits.append(current_split)
        else:
            final_splits.append(current_split)
        
        i += 1

    return final_splits

def dividir_con_solapamiento(texto, longitud, solapamiento):
    """
    Divide un texto en partes con un solapamiento específico entre cada parte.
    No divide si el fragmento contiene una tabla Markdown.

    Parámetros:
    texto (str): El texto a dividir.
    longitud (int): La longitud de cada parte.
    solapamiento (int): El número de caracteres que se solapan entre cada parte.

    Retorna:
    list: Una lista de partes del texto.
    """
    if longitud <= solapamiento:
        raise ValueError("La longitud debe ser mayor que el solapamiento")
    
    # Si el contenido tiene una tabla, no lo dividimos
    if es_tabla_markdown(texto):
        return [texto]  # Devolver el fragmento completo sin dividir
    
    partes = []
    for i in range(0, len(texto), longitud - solapamiento):
        parte = texto[i:i + longitud]
        partes.append(parte)
        if len(parte) < longitud:
            break  # No dividir más si la parte es más corta que la longitud solicitada
    return partes

def dividir_chunk_con_tablas(chunk, max_tokens, distancia_tokens=50):
    """
    Divide un chunk que contiene tablas sin separar las tablas, asegurándose de que
    ningún chunk exceda el límite de tokens y que las tablas que están a menos de 50 tokens de distancia no se separen.
    
    Parámetros:
    chunk (str): El chunk a dividir.
    max_tokens (int): El número máximo de tokens permitido por chunk.
    distancia_tokens (int): La distancia mínima en tokens entre tablas para evitar separarlas.
    
    Retorna:
    list: Lista de chunks resultantes después de la división.
    """
    lineas = chunk.split("\n")
    current_chunk = ""
    final_chunks = []
    current_tokens = 0
    last_table_end_tokens = None

    for linea in lineas:
        tokens_linea = len(encoding.encode(linea))

        # Si la línea es parte de una tabla, verificamos la distancia desde la última tabla
        if es_tabla_markdown(linea):
            if last_table_end_tokens is not None:
                # Verificar si la distancia desde la última tabla es menor que distancia_tokens
                if current_tokens - last_table_end_tokens <= distancia_tokens:
                    # Mantener la tabla dentro del mismo chunk
                    current_chunk += linea + "\n"
                    current_tokens += tokens_linea
                    continue
            
            # Actualizar el punto final de la última tabla
            last_table_end_tokens = current_tokens + tokens_linea

        # Si agregar esta línea excede el límite de tokens
        if current_tokens + tokens_linea > max_tokens:
            # Guardar el chunk actual y empezar uno nuevo
            final_chunks.append(current_chunk.strip())
            current_chunk = linea + "\n"
            current_tokens = tokens_linea
            last_table_end_tokens = None  # Reiniciamos el contador de distancia
        else:
            current_chunk += linea + "\n"
            current_tokens += tokens_linea

    # Agregar el último chunk
    if current_chunk:
        final_chunks.append(current_chunk.strip())
    
    return final_chunks

def dividir_si_excede_max_tokens(split, max_tokens, chunk_size, chunk_overlap_percentage):
    """
    Divide un split si excede los max_tokens, utilizando lógica de separación de tablas si corresponde,
    o la función dividir_con_solapamiento si no hay tablas.

    Parámetros:
    split (str): El fragmento a dividir.
    max_tokens (int): El número máximo de tokens permitido.
    chunk_size (int): La longitud de cada fragmento.
    chunk_overlap_percentage (float): El porcentaje de solapamiento entre fragmentos.

    Retorna:
    list: Lista de fragmentos resultantes después de la división si es necesario.
    """
    token_count = len(encoding.encode(split))

    if token_count > max_tokens:
        if es_tabla_markdown(split):
            # Separar según la lógica de separación de tablas
            return dividir_chunk_con_tablas(split, max_tokens)
        else:
            # Aplicar la división con solapamiento
            overlap = int(chunk_size * chunk_overlap_percentage)
            return dividir_con_solapamiento(split, chunk_size, overlap)
    else:
        return [split]

def markdown_percentage(content, chunk_size, chunk_overlap_percentage, min_tokens, max_tokens):
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
        ("####", "Header 4"),
        ("#####", "Header 5"),
    ]

    # Dividir por encabezados de Markdown
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on, strip_headers=False)
    md_header_splits = markdown_splitter.split_text(content)

    # Combinar fragmentos pequeños
    combined_splits = []
    buffer = ""

    for split in md_header_splits:
        tokens = len(encoding.encode(split.page_content))
        if tokens <= min_tokens:
            buffer += split.page_content + " \n "
            # Controlar problemas de tiktoken
            combined_tokens = encoding.encode(buffer)
            if len(combined_tokens) > min_tokens:
                combined_splits.append(buffer)
                buffer = ""
        else:
            if buffer:
                combined_splits.append(buffer)
                buffer = ""
            combined_splits.append(split.page_content)
    if buffer:  # Agregar cualquier contenido restante en el buffer
        combined_splits.append(buffer)

    final_splits = []

    # Primero, combinar splits si contienen tablas cercanas
    combined_splits = combinar_splits_tablas(combined_splits, max_tokens)

    # Luego, aplicar la división con solapamiento solo si algún fragmento es demasiado grande
    for split_content in combined_splits:
        maximum_token = 4000
        sub_splits = dividir_si_excede_max_tokens(split_content, maximum_token, chunk_size, chunk_overlap_percentage)
        final_splits.extend(sub_splits)
    
    return final_splits

def generate_chunkid(doctitle, content, title, page):
    title = title if title is not None else ""
    #subtitle = subtitle if subtitle is not None else ""
    page = page if page is not None else ""
    
    # Crear un identificador único basado en el contenido y el título
    hash_input = (doctitle + content + title + page).encode('utf-8')
    hash_output = hashlib.sha256(hash_input).hexdigest()
    return hash_output

def detect_title(content):
    matches = re.findall(r"^\s*#\s(?!#)(.+)", content, re.MULTILINE)
    return matches[-1] if matches else ''

def detect_subtitle(content):
    matches = re.findall(r"^\s*##\s(?!#)(.+)", content, re.MULTILINE)
    return matches[-1] if matches else ''

def detect_threeheader(content):
    matches = re.findall(r"^\s*###\s(?!#)(.+)", content, re.MULTILINE)
    return matches[-1] if matches else ''

def detect_fourheader(content):
    matches = re.findall(r"^\s*####\s(?!#)(.+)", content, re.MULTILINE)
    return matches[-1] if matches else ''

def detect_fiveheader(content):
    matches = re.findall(r"^\s*#####\s(?!#)(.+)", content, re.MULTILINE)
    return matches[-1] if matches else ''

def contains_checkbox(content):
    # Busca los checkbox ":selected:" o ":unselected:"
    return bool(re.search(r':selected:|:unselected:', content.lower()))

def contains_selected_checkbox(content):
    # Busca los checkbox ":selected:" o ":unselected:"
    return bool(re.search(r':selected:', content.lower()))

def contains_lote(content, sublotes_flag):
    # Buscar la palabra "lote" seguida de un espacio y un número
    if sublotes_flag:
        return bool(re.search(r'\b(lote|lot|sorta|lotes|lots|loteak|asko|sublote|sublotes|sublot|sublots|subloteak|sublotea)\b', content.lower()))
    else:
        return bool(re.search(r'\b(lote|lot|sorta|lotes|lots|loteak|asko)\b', content.lower()))

def contains_lote_plural(content, sublotes_flag):
    # Buscar la palabra "lote" seguida de un espacio y un número
    if sublotes_flag:
        return bool(re.search(r'\b(lotes|lots|loteak|asko|sublots|subloteak|sublotes)\b', content.lower()))
    else:
        return bool(re.search(r'\b(lotes|lots|loteak|asko)\b', content.lower()))

def extract_lotes(content, sublotes_flag):
    
    # Regex para detectar lotes con formato de número único o lista de números
    regex_lote = r'\b(lote|lot|sorta|lotes|lots|loteak|asko)\b[ \t]*[:|Nº]*[ \t]*(\b([1-9]|[12][0-9]|30)\b(?:\s*(?:,|y)\s*\b([1-9]|[12][0-9]|30)\b)*)\b'
    matches_lote = re.finditer(regex_lote, content, re.IGNORECASE)
    unique_matches = set()  # Usar un conjunto para evitar duplicados



    # Agregar lotes detectados al conjunto
    for match in matches_lote:
        lotes_str = match.group(2)
        if sublotes_flag:
            lotes = re.findall(r'\d+(?:\.\d+|[A-Z]?)', lotes_str)  # Detecta números, decimales o letras
        else: 
            lotes = re.findall(r'\d+', lotes_str)  # Encontrar todos los números en el string del lote
        for lote in lotes:
            lote_text = f"lote {lote}"
            unique_matches.add(lote_text)

    
    if sublotes_flag:
        # Regex adicional para detectar sublotes independientes con decimales o letras
        regex_sublote = r'\b(lote|lot|sorta|lotes|lots|loteak|asko|sublote|sublotes|sublot|sublots|subloteak|sublotea)[ \t]*(\d+(?:\.\d+|[A-Z])?(?:\s*(?:,|y)\s*\d+(?:\.\d+|[A-Z])?)*)\b'
        matches_sublote = re.finditer(regex_sublote, content, re.IGNORECASE)
        
        # Agregar sublotes detectados al conjunto
        for match in matches_sublote:
            sublotes_str = match.group(2)
            sublotes = re.findall(r'\d+(?:\.\d+|[A-Z]?)', sublotes_str)
            for sublote in sublotes:
                lote_text = f"lote {sublote}"  # Cambiado a "lote" en vez de "sublote"
                unique_matches.add(lote_text)

    order_key = sort_key if sublotes_flag else lambda x: int(x.split()[-1])

    return sorted(unique_matches, key=order_key)

# Función de ordenación para manejar número principal y sublotes
def sort_key(value):
    # Extraer el número principal y la parte secundaria (decimal o letra)
    match = re.match(r'\w+\s+(\d+)(?:\.(\d+)|([A-Z]))?', value)
    if match:
        main_num = int(match.group(1))  # Número principal
        sub_num = int(match.group(2)) if match.group(2) else float('inf')  # Parte decimal si existe
        has_letter_or_decimal = 1 if match.group(2) or match.group(3) else 0  # Determina si tiene decimal o letra
        return (main_num, has_letter_or_decimal, sub_num)
    return (float('inf'), float('inf'), float('inf'))  # Para manejar posibles errores

def get_last_detected_lote(content):
    regex = r'\b(lote|lot|sorta|lotes|lots|loteak|asko)\b[ \t]*[:|Nº]*[ \t]*(\b([1-9]|[12][0-9]|30)\b(?:\s*(?:,|y)\s*\b([1-9]|[12][0-9]|30)\b)*)\b'
    matches = re.finditer(regex, content, re.IGNORECASE)
    last_detected_lote = None  # Variable para almacenar el último lote detectado

    for match in matches:
        lotes_str = match.group(2)
        lotes = re.findall(r'\d+', lotes_str)  # Encontrar todos los números en el string del lote
        for lote in lotes:
            lote_text = f"lote {lote}"  # Formatear adecuadamente
            last_detected_lote = lote_text  # Actualizar el último lote detectado
    
    return last_detected_lote

def normalize_text(text):
    """Normalizar el texto convirtiendo a minúsculas y eliminando tildes."""
    text = text.lower()
    text = ''.join((c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn'))  # Elimina tildes
    return text

### GET KEYWORDS (DATAPOINTS)
def load_datapoints(filename='datapoints_list.json'):
    """Cargar datapoints desde un archivo JSON. Si no existe, devuelve None."""
    if not os.path.exists(filename):
        return None
    
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            data = json.load(file)
            return data.get('datapoints')
    except (json.JSONDecodeError, KeyError):
        # Si el JSON está corrupto o no tiene la clave esperada
        return None

def extract_datapoints(content, datapoints_list):
    """Extraer datapoints basado en una lista de términos buscados."""
    normalized_content = normalize_text(content)
    found_datapoints = []
    for datapoint in datapoints_list:
        sub_datapoints = datapoint.split(',')
        primary_datapoint = sub_datapoints[0].strip()
        for sub_datapoint in sub_datapoints:
            if normalize_text(sub_datapoint.strip()) in normalized_content:
                found_datapoints.append(primary_datapoint)
                break  # Solo añade una vez por cada datapoint principal
    return found_datapoints

def delete_noise(titles):
    cleaned_titles = []
    for title in titles:
        # Limpieza de espacios y ## al principio de la línea
        title_cleaned = title.strip()
        # Elimina las barras invertidas, excepto cuando están antes de un punto
        cleaned_title = re.sub(r'\\\.', '.', title_cleaned)
        cleaned_titles.append(cleaned_title)
    return cleaned_titles

def extract_tables(markdown_text):
    # Expresión regular para detectar tablas en formato Markdown
    table_pattern = re.compile(r'(\|(?:[^\n]*\|)+\n(?:\|[^\n]*\|)+)', re.MULTILINE)
    tables = table_pattern.findall(markdown_text)
    return tables

def get_first_60_percent(content):
    # Obtenemos el primer 60% del contenido de la tabla
    split_index = int(len(content) * 0.6)
    return content[:split_index]

def extract_pg_number(table):
    # Busca PGNumero dentro de la tabla
    pg_pattern = re.compile(r'(PG\d+)')
    match = pg_pattern.search(table)
    return match.group(0) if match else None

def compare_tables(table1, table2):
    # Comparamos el primer 60% del contenido de ambas tablas
    table1_60 = get_first_60_percent(table1)
    table2_60 = get_first_60_percent(table2)
    return table1_60 == table2_60

def detect_and_remove_duplicate_tables(markdown_text, total_pages, min_occurrences_percentage=0.2):
    tables = extract_tables(markdown_text)
    pg_numbers = []
    table_counter = Counter()

    # Contar la frecuencia de cada tabla en el documento
    for table in tables:
        table_counter[table] += 1
        pg_number = extract_pg_number(table)
        if pg_number:
            pg_numbers.append(pg_number)

    # Definir el umbral de ocurrencias para eliminar (mínimo 20% de las páginas)
    min_occurrences = int(total_pages * min_occurrences_percentage)

    # Identificar tablas comunes que ocurren en más del 20% de las páginas
    common_tables = [
        table for table, count in table_counter.items()
        if count >= min_occurrences
    ]

    unique_tables = []
    duplicate_tables = []

    # Comparamos las tablas comunes y eliminamos las duplicadas
    for table in common_tables:
        is_duplicate = False
        for unique_table in unique_tables:
            if compare_tables(table, unique_table):
                is_duplicate = True
                duplicate_tables.append(table)
                break
        if not is_duplicate:
            unique_tables.append(table)

    # Eliminar las tablas duplicadas del contenido original
    for duplicate in duplicate_tables:
        markdown_text = markdown_text.replace(duplicate, '')

    # Añadir los números de página que se detectaron en las tablas eliminadas
    for pg_number in pg_numbers:
        markdown_text += f'\n{pg_number}\n'

    return markdown_text


def eliminar_figuras_repetidas(texto):
    # Patrón para detectar etiquetas <figure> con su contenido
    patron_figura = r"(<figure>[\s\S]*?<[^>]*figure>)"
     
    # Encontrar todas las figuras completas en el documento
    figuras = re.findall(patron_figura, texto)
    
    # Contar cuántas veces aparece cada figura
    contador_figuras = Counter(figuras)
    
    # Eliminar las figuras que se repiten más de una vez
    for figura, conteo in contador_figuras.items():
        if conteo > 1:
            # Reemplazar todas las instancias de la figura repetida
            texto = re.sub(re.escape(figura), "", texto)
    
    return texto