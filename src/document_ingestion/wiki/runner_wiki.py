"""
src.document_ingestion.wiki.runner_wiki

Runner para el pipeline de chunking de artículos de Wikipedia.

Ejecuta el chunking sobre todos los JSONs de Wikipedia almacenados en
Blob Storage bajo ``data/wikipedia/<language>/json/`` y los sube a
Cosmos DB (Chunks-Wiki).

Uso:
    python -m src.document_ingestion.wiki.runner_wiki                          # todos los idiomas
    python -m src.document_ingestion.wiki.runner_wiki --language es             # solo español
    python -m src.document_ingestion.wiki.runner_wiki --file Writer.json --language en
    python -m src.document_ingestion.wiki.runner_wiki --file data/wikipedia/en/json/Writer.json
"""
from __future__ import annotations

import argparse
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Optional

from src.document_ingestion.wiki.doc_chunking_wiki import get_text_split_wiki
from src.services.azure_storage_service import list_json_configs_from_blob
from src.models.doc_model import DocEntity
from src.config import config


BLOB_WIKI_PREFIX = "data/wikipedia/"

WIKI_LANGUAGES = ["en", "es"]


def _list_wiki_jsons(language: str) -> List[str]:
    """Lista todos los JSONs bajo ``data/wikipedia/<language>/json/``."""
    prefix = f"{BLOB_WIKI_PREFIX}{language}/json/"
    return list_json_configs_from_blob(
        account_name=config.azure_storage_account_name,
        account_key=config.azure_storage_key,
        container_name=config.azure_container_name,
        prefix=prefix,
    )


def _discover_languages() -> List[str]:
    """Descubre los idiomas disponibles bajo ``data/wikipedia/``."""
    all_blobs = list_json_configs_from_blob(
        account_name=config.azure_storage_account_name,
        account_key=config.azure_storage_key,
        container_name=config.azure_container_name,
        prefix=BLOB_WIKI_PREFIX,
    )
    languages = set()
    for blob_name in all_blobs:
        parts = blob_name.replace("\\", "/").split("/")
        if len(parts) >= 3 and parts[0] == "data" and parts[1] == "wikipedia":
            languages.add(parts[2])
    return sorted(languages)


def _generate_session_id(language: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"WIKI_{language.upper()}_{ts}"


def run_wiki_chunking(language: str) -> None:
    """Ejecuta el chunking de todos los artículos Wikipedia de un idioma dado."""
    print(f"\n{'=' * 60}")
    print(f"  CHUNKING DE WIKIPEDIA — idioma: {language}")
    print(f"{'=' * 60}")

    json_names = _list_wiki_jsons(language)
    if not json_names:
        print(f"  No se encontraron JSONs en data/wikipedia/{language}/json/")
        return

    session_id = _generate_session_id(language)

    print(f"  Container  : {config.azure_container_name}")
    print(f"  Prefix     : {BLOB_WIKI_PREFIX}{language}/json/")
    print(f"  JSONs found: {len(json_names)}")
    print(f"  Session ID : {session_id}")
    print("-" * 60)

    ok_count = 0
    err_count = 0

    def _process_article(blob_path: str) -> bool:
        short_name = blob_path.replace(BLOB_WIKI_PREFIX, "")
        doc_entity = DocEntity(
            id=str(uuid.uuid4()),
            doc_id=blob_path,
            doc_nombre=short_name,
            id_caso=f"wiki-{language}",
            usuario="runner",
            equipo="wikipedia",
            source_collection="wikipedia",
            language=language,
        ).model_dump(exclude_none=True)

        get_text_split_wiki(
            docId=blob_path,
            SessionId=session_id,
            doc_entity=doc_entity,
            CDU="DOCPROCESS",
        )
        return True

    max_workers = min(len(json_names), config.max_workers_docs or 4)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_article, bp): bp for bp in json_names}
        for idx, future in enumerate(as_completed(futures), start=1):
            blob_path = futures[future]
            short_name = blob_path.replace(BLOB_WIKI_PREFIX, "")
            try:
                future.result()
                ok_count += 1
                print(f"  [{idx}/{len(json_names)}] ✓ {short_name}")
            except Exception as e:
                err_count += 1
                print(f"  [{idx}/{len(json_names)}] ✗ {short_name} — ERROR: {e}")

    print(f"\n{'-' * 60}")
    print(f"  Resultado ({language}): {ok_count} OK / {err_count} errores / {len(json_names)} total")
    print(f"{'=' * 60}\n")


def main(language: Optional[str] = None) -> None:
    if language:
        run_wiki_chunking(language.strip().lower())
    else:
        print("No se especificó idioma — descubriendo idiomas disponibles...")
        languages = _discover_languages()
        if not languages:
            print("No se encontraron artículos en Blob Storage bajo data/wikipedia/")
            return
        print(f"Idiomas encontrados: {languages}")
        for lang in languages:
            run_wiki_chunking(lang)


def run_single_wiki(file: str, language: Optional[str] = None) -> None:
    """Procesa un único artículo Wikipedia dado su nombre o ruta de blob.

    Parámetros
    ----------
    file :
        Ruta completa del blob (``data/wikipedia/en/json/Writer.json``) o el
        nombre/título del artículo (``Writer`` o ``Writer.json``).  En este
        último caso se requiere ``language``.
    language :
        Idioma (``en``, ``es``).  Solo necesario si ``file`` no es una ruta
        completa.
    """
    file = file.replace("\\", "/")

    # Resolver ruta completa
    if file.startswith("data/wikipedia/"):
        blob_path = file
        parts = blob_path.split("/")
        lang = parts[2] if len(parts) > 2 else (language or "en")
    else:
        if not language:
            raise ValueError(
                "--language es obligatorio cuando --file es solo un nombre de fichero."
            )
        lang = language.strip().lower()
        fname = file if file.lower().endswith(".json") else file + ".json"
        blob_path = f"{BLOB_WIKI_PREFIX}{lang}/json/{fname}"

    session_id = _generate_session_id(lang)
    short_name = blob_path.replace(BLOB_WIKI_PREFIX, "")

    print(f"\n{'=' * 60}")
    print(f"  CHUNKING WIKI — documento único")
    print(f"  Blob path  : {blob_path}")
    print(f"  Session ID : {session_id}")
    print(f"{'=' * 60}")

    doc_entity = DocEntity(
        id=str(uuid.uuid4()),
        doc_id=blob_path,
        doc_nombre=short_name,
        id_caso=f"wiki-{lang}",
        usuario="runner",
        equipo="wikipedia",
        source_collection="wikipedia",
        language=lang,
    ).model_dump(exclude_none=True)

    get_text_split_wiki(
        docId=blob_path,
        SessionId=session_id,
        doc_entity=doc_entity,
        CDU="DOCPROCESS",
    )
    print(f"\n  ✓ {short_name} procesado correctamente.")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Chunking de Wikipedia desde Azure Blob Storage → Cosmos DB",
    )
    parser.add_argument(
        "--language",
        type=str,
        default=None,
        help="Idioma a procesar (es, en). Si no se indica, procesa todos.",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help=(
            "Procesa un único artículo. Acepta ruta completa de blob "
            "(data/wikipedia/en/json/Writer.json) o solo el nombre/título "
            "(Writer o Writer.json) junto con --language."
        ),
    )
    args = parser.parse_args()

    if args.file:
        run_single_wiki(args.file, language=args.language)
    else:
        main(language=args.language)
