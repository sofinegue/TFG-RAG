"""
src.document_ingestion.eu.runner_eu
Runner para el pipeline de chunking de documentos legislativos europeos (EU)
Ejecuta el chunking sobre todos los PDFs de EUR-Lex almacenados en Blob Storage
bajo ``data/eu/<language>/`` y los sube a Cosmos DB (Chunks-EU)
Uso:
    python -m src.document_ingestion.eu.runner_eu                          # todos los idiomas
    python -m src.document_ingestion.eu.runner_eu --language en             # solo inglés
    python -m src.document_ingestion.eu.runner_eu --file legislation_2001.pdf --language en
    python -m src.document_ingestion.eu.runner_eu --file data/eu/en/legislation_2001.pdf
"""
from __future__ import annotations
import argparse
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional
from src.document_ingestion.eu.doc_chunking_eu import get_text_split_eu
from src.services.azure_storage_service import list_json_configs_from_blob
from src.models.doc_model import DocEntity
from src.config import config
BLOB_EU_PREFIX = "data/eu/"
EU_LANGUAGES = ["en", "es", "fr", "pt", "it"]
def _list_eu_pdfs(language: str) -> list[str]:
    """lista todos los PDFs bajo ``data/eu/<language>/``"""
    from azure.storage.blob import BlobServiceClient
    prefix = f"{BLOB_EU_PREFIX}{language}/"
    connect_str = (
        f"DefaultEndpointsProtocol=https;"
        f"AccountName={config.azure_storage_account_name};"
        f"AccountKey={config.azure_storage_key};"
        f"EndpointSuffix=core.windows.net"
    )
    print(f"[DEBUG] Conectando a Blob Storage: cuenta={config.azure_storage_account_name}, container={config.azure_container_name}")
    print(f"[DEBUG] Buscando blobs con prefijo: '{prefix}'")
    client = BlobServiceClient.from_connection_string(connect_str)
    container_client = client.get_container_client(config.azure_container_name)
    pdf_files = []
    for blob in container_client.list_blobs(name_starts_with=prefix):
        if blob.name.lower().endswith(".pdf"):
            pdf_files.append(blob.name)
    client.close()
    print(f"[DEBUG] PDFs encontrados: {len(pdf_files)}")
    return sorted(pdf_files)
def _discover_languages() -> list[str]:
    """Descubre los idiomas disponibles bajo ``data/eu/``"""
    from azure.storage.blob import BlobServiceClient
    connect_str = (
        f"DefaultEndpointsProtocol=https;"
        f"AccountName={config.azure_storage_account_name};"
        f"AccountKey={config.azure_storage_key};"
        f"EndpointSuffix=core.windows.net"
    )
    client = BlobServiceClient.from_connection_string(connect_str)
    container_client = client.get_container_client(config.azure_container_name)
    languages = set()
    for blob in container_client.list_blobs(name_starts_with=BLOB_EU_PREFIX):
        parts = blob.name.replace("\\", "/").split("/")
        if len(parts) >= 3 and parts[0] == "data" and parts[1] == "eu":
            languages.add(parts[2])
    client.close()
    return sorted(languages)
def _generate_session_id(language: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"EU_{language.upper()}_{ts}"
def run_eu_chunking(language: str) -> None:
    """Ejecuta el chunking de todos los PDFs EU de un idioma dado"""
    print(f"\n{'=' * 60}")
    print(f"  CHUNKING DE EU — idioma: {language}")
    print(f"{'=' * 60}")
    pdf_names = _list_eu_pdfs(language)
    if not pdf_names:
        print(f"  No se encontraron PDFs en data/eu/{language}/")
        return
    session_id = _generate_session_id(language)
    print(f"  Container  : {config.azure_container_name}")
    print(f"  Prefix     : {BLOB_EU_PREFIX}{language}/")
    print(f"  PDFs found : {len(pdf_names)}")
    print(f"  Session ID : {session_id}")
    print("-" * 60)
    ok_count = 0
    err_count = 0
    def _process_pdf(blob_path: str) -> None:
        short_name = blob_path.replace(BLOB_EU_PREFIX, "")
        doc_entity = DocEntity(
            id=str(uuid.uuid4()),
            doc_id=blob_path,
            doc_nombre=short_name,
            id_caso=f"eu-{language}",
            usuario="runner",
            equipo="eu",
            source_collection="eu",
            language=language,
        ).model_dump(exclude_none=True)
        get_text_split_eu(
            docId=blob_path,
            SessionId=session_id,
            doc_entity=doc_entity,
            CDU="DOCPROCESS",
        )
    max_workers = min(len(pdf_names), config.max_workers_docs or 4)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_pdf, bp): bp for bp in pdf_names}
        for idx, future in enumerate(as_completed(futures), start=1):
            blob_path = futures[future]
            short_name = blob_path.replace(BLOB_EU_PREFIX, "")
            try:
                future.result()
                ok_count += 1
                print(f"  [{idx}/{len(pdf_names)}] OK {short_name}")
            except Exception as e:
                err_count += 1
                print(f"  [{idx}/{len(pdf_names)}] KO {short_name} — ERROR: {e}")
    print(f"\n{'-' * 60}")
    print(f"  Resultado ({language}): {ok_count} OK / {err_count} errores / {len(pdf_names)} total")
    print(f"{'=' * 60}\n")
def main(language: Optional[str] = None) -> None:
    if language:
        run_eu_chunking(language.strip().lower())
    else:
        print("No se especificó idioma — descubriendo idiomas disponibles...")
        languages = _discover_languages()
        if not languages:
            print("No se encontraron PDFs en Blob Storage bajo data/eu/")
            return
        print(f"Idiomas encontrados: {languages}")
        for lang in languages:
            run_eu_chunking(lang)
def run_single_eu(file: str, language: Optional[str] = None) -> None:
    """Procesa un único PDF EU dado su nombre o ruta de blob
    Parámetros
    ----------
    file :
        Ruta completa del blob (``data/eu/en/legislation_2001.pdf``) o solo
        el nombre del fichero (``legislation_2001.pdf``).  En este último caso
        se requiere ``language``
    language :
        Idioma (``en``, ``es``…).  Solo necesario si ``file`` no es una ruta
        completa
    """
    file = file.replace("\\", "/")
    # Resolver ruta completa
    if file.startswith("data/eu/"):
        blob_path = file
        parts = blob_path.split("/")
        lang = parts[2] if len(parts) > 2 else (language or "en")
    else:
        if not language:
            raise ValueError(
                "--language es obligatorio cuando --file es solo un nombre de fichero."
            )
        lang = language.strip().lower()
        fname = file if file.lower().endswith(".pdf") else file + ".pdf"
        blob_path = f"{BLOB_EU_PREFIX}{lang}/{fname}"
    session_id = _generate_session_id(lang)
    short_name = blob_path.replace(BLOB_EU_PREFIX, "")
    print(f"\n{'=' * 60}")
    print(f"  CHUNKING EU — documento único")
    print(f"  Blob path  : {blob_path}")
    print(f"  Session ID : {session_id}")
    print(f"{'=' * 60}")
    doc_entity = DocEntity(
        id=str(uuid.uuid4()),
        doc_id=blob_path,
        doc_nombre=short_name,
        id_caso=f"eu-{lang}",
        usuario="runner",
        equipo="eu",
        source_collection="eu",
        language=lang,
    ).model_dump(exclude_none=True)
    get_text_split_eu(
        docId=blob_path,
        SessionId=session_id,
        doc_entity=doc_entity,
        CDU="DOCPROCESS",
    )
    print(f"\n  OK {short_name} procesado correctamente.")
    print(f"{'=' * 60}\n")
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Chunking de EU PDFs desde Azure Blob Storage → Cosmos DB",
    )
    parser.add_argument(
        "--language",
        type=str,
        default=None,
        help="Idioma a procesar (en, es, fr, pt, it). Si no se indica, procesa todos.",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help=(
            "Procesa un único fichero. Acepta ruta completa de blob "
            "(data/eu/en/doc.pdf) o solo el nombre (doc.pdf) junto con --language."
        ),
    )
    args = parser.parse_args()
    if args.file:
        run_single_eu(args.file, language=args.language)
    else:
        main(language=args.language)
