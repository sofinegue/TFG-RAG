
"""
src.document_ingestion.runner

Runner para el pipeline de chunking de CVs.

Ejecuta el chunking sobre todos los CVs JSON almacenados en Blob Storage
bajo ``data/cvs/<language>/`` y los sube a Cosmos DB.

Uso:
    python -m src.document_ingestion.runner                  # todos los idiomas
    python -m src.document_ingestion.runner --language es     # solo español
    python -m src.document_ingestion.runner --language en     # solo inglés
"""

import argparse
import uuid
from datetime import datetime
from typing import List, Optional

from src.document_ingestion.cvs.doc_chunking_cvs import get_text_split_cv
from src.services.azure_storage_service import list_json_configs_from_blob
from src.models.doc_model import DocEntity
from src.config import config


# ===========================================================================
# Helpers
# ===========================================================================

BLOB_CVS_PREFIX = "data/cvs/"


def _list_cv(language: str) -> List[str]:
    """Lista todos los archivos JSON bajo ``data/cvs/<language>/``."""
    prefix = f"{BLOB_CVS_PREFIX}{language}/"
    return list_json_configs_from_blob(
        account_name=config.azure_storage_account_name,
        account_key=config.azure_storage_key,
        container_name=config.azure_container_name,
        prefix=prefix,
    )


def _discover_languages() -> List[str]:
    """Descubre los idiomas disponibles listando subcarpetas de ``data/cvs/``."""
    all_blobs = list_json_configs_from_blob(
        account_name=config.azure_storage_account_name,
        account_key=config.azure_storage_key,
        container_name=config.azure_container_name,
        prefix=BLOB_CVS_PREFIX,
    )
    languages = set()
    for blob_name in all_blobs:
        parts = blob_name.replace("\\", "/").split("/")
        if len(parts) >= 4 and parts[0] == "data" and parts[1] == "cvs":
            languages.add(parts[2])
    return sorted(languages)


def _generate_session_id(language: str) -> str:
    """Genera un session ID con timestamp."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"CVS_{language.upper()}_{ts}"


def _pretty_print_chunks(chunks: list) -> None:
    """Imprime los chunks de forma legible por pantalla."""
    for i, chunk in enumerate(chunks, start=1):
        print(f"\n{'=' * 70}")
        print(f"  CHUNK {i}/{len(chunks)}  —  type: {chunk.get('Sections', ['?'])[0]}")
        print(f"  Title   : {chunk.get('Title', '')}")
        print(f"  Tokens  : {chunk.get('Content_length', 0)}")
        print(f"  Language: {chunk.get('sourceLanguage', '')}")
        print(f"{'=' * 70}")

        print(f"\n--- sectionContent ---")
        print(chunk.get("sectionContent", ""))

        print(f"\n--- metadata ---")
        meta = chunk.get("metadata", {})
        print(json.dumps(meta, indent=2, ensure_ascii=False))

        # Mostrar campos clave del documento Cosmos (sin embedding)
        print(f"\n--- campos Cosmos ---")
        cosmos_fields = {k: v for k, v in chunk.items()
                         if k not in ("sectionContent", "metadata", "embedding")}
        print(json.dumps(cosmos_fields, indent=2, ensure_ascii=False, default=str))

    print(f"\n{'=' * 70}")


# ===========================================================================
# Pipeline principal
# ===========================================================================

def run_cv_chunking(language: str) -> None:
    """Ejecuta el chunking de todos los CVs de un idioma dado."""
    print(f"\n{'=' * 60}")
    print(f"  CHUNKING DE CVs — idioma: {language}")
    print(f"{'=' * 60}")

    json_names = _list_cv(language)
    if not json_names:
        print(f"  No se encontraron CVs en data/cvs/{language}/")
        return

    session_id = _generate_session_id(language)

    print(f"  Container  : {config.azure_container_name}")
    print(f"  Prefix     : {BLOB_CVS_PREFIX}{language}/")
    print(f"  CVs found  : {len(json_names)}")
    print(f"  Session ID : {session_id}")
    print("-" * 60)

    ok_count = 0
    err_count = 0

    for idx, blob_path in enumerate(json_names, start=1):
        cv_id = blob_path.replace(BLOB_CVS_PREFIX, "")   # es/cv_XXX.json
        print(f"\n  [{idx}/{len(json_names)}] {cv_id}")

        doc_entity = DocEntity(
            id=str(uuid.uuid4()),
            doc_id=blob_path,
            doc_nombre=cv_id,
            id_caso=f"cvs-{language}",
            usuario="runner",
            equipo="cvs",
            source_collection="cvs",
            language=language,
        ).model_dump(exclude_none=True)

        try:
            get_text_split_cv(
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
    print(f"  Resultado ({language}): {ok_count} OK / {err_count} errores / {len(json_names)} total")
    print(f"{'=' * 60}\n")
    
    # # 3. Ejecutar pipeline (dry-run: no sube a Cosmos, devuelve chunks)
    # chunks = get_text_split_cv(
    #     docId=blob_path,
    #     SessionId=session_id,
    #     doc_entity=doc_entity,
    #     CDU="DOCPROCESS",
    # )

    # # 4. Mostrar resultado
    # if chunks:
    #     print(f"\n  >>> Se generaron {len(chunks)} chunks. Mostrando a continuación:\n")
    #     _pretty_print_chunks(chunks)
    # else:
    #     print("  >>> No se generaron chunks (revisa errores arriba).")

# ===========================================================================
# Entry point
# ===========================================================================

def main(language: Optional[str] = None) -> None:
    if language:
        run_cv_chunking(language.strip().lower())
    else:
        print("No se especificó idioma — descubriendo idiomas disponibles...")
        languages = _discover_languages()
        if not languages:
            print("No se encontraron CVs en Blob Storage bajo data/cvs/")
            return
        print(f"Idiomas encontrados: {languages}")
        for lang in languages:
            run_cv_chunking(lang)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Chunking de CVs desde Azure Blob Storage → Cosmos DB",
    )
    parser.add_argument(
        "--language",
        type=str,
        default=None,
        help="Idioma a procesar (es, en, ...). Si no se indica, procesa todos.",
    )
    args = parser.parse_args()
    main(language=args.language)
