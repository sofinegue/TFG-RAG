"""
src.document_ingestion.eu.runner_eu

Runner para el pipeline de chunking de documentos legislativos europeos (EU).

Ejecuta el chunking sobre todos los PDFs de EUR-Lex almacenados en Blob Storage
bajo ``data/eu/<language>/`` y los sube a Cosmos DB (Chunks-EU).

Uso:
    python -m src.document_ingestion.eu.runner_eu                  # todos los idiomas
    python -m src.document_ingestion.eu.runner_eu --language en     # solo inglés
    python -m src.document_ingestion.eu.runner_eu --language es     # solo español
"""
from __future__ import annotations

import argparse
import uuid
from datetime import datetime
from typing import List, Optional

from src.document_ingestion.eu.doc_chunking_eu import get_text_split_eu
from src.services.azure_storage_service import list_json_configs_from_blob
from src.models.doc_model import DocEntity
from src.config import config


BLOB_EU_PREFIX = "data/eu/"

EU_LANGUAGES = ["en", "es", "fr", "pt", "it"]


def _list_eu_pdfs(language: str) -> List[str]:
    """Lista todos los PDFs bajo ``data/eu/<language>/``."""
    from azure.storage.blob import BlobServiceClient

    prefix = f"{BLOB_EU_PREFIX}{language}/"
    connect_str = (
        f"DefaultEndpointsProtocol=https;"
        f"AccountName={config.azure_storage_account_name};"
        f"AccountKey={config.azure_storage_key};"
        f"EndpointSuffix=core.windows.net"
    )
    client = BlobServiceClient.from_connection_string(connect_str)
    container_client = client.get_container_client(config.azure_container_name)

    pdf_files = []
    for blob in container_client.list_blobs(name_starts_with=prefix):
        if blob.name.lower().endswith(".pdf"):
            pdf_files.append(blob.name)
    client.close()
    return sorted(pdf_files)


def _discover_languages() -> List[str]:
    """Descubre los idiomas disponibles bajo ``data/eu/``."""
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
    """Ejecuta el chunking de todos los PDFs EU de un idioma dado."""
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

    for idx, blob_path in enumerate(pdf_names, start=1):
        short_name = blob_path.replace(BLOB_EU_PREFIX, "")
        print(f"\n  [{idx}/{len(pdf_names)}] {short_name}")

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

        try:
            get_text_split_eu(
                docId=blob_path,
                SessionId=session_id,
                doc_entity=doc_entity,
                CDU="DOCPROCESS",
            )
            ok_count += 1
        except Exception as e:
            err_count += 1
            print(f"    ERROR: {e}")

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
    args = parser.parse_args()
    main(language=args.language)
