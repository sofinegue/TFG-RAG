
"""
src.document_ingestion.cvs.runner_cvs

Runner para el pipeline de chunking de CVs.

Ejecuta el chunking sobre todos los CVs JSON almacenados en Blob Storage
bajo ``data/cvs/<language>/`` y los sube a Cosmos DB.

Uso:
    python -m src.document_ingestion.cvs.runner_cvs                   # todos los idiomas
    python -m src.document_ingestion.cvs.runner_cvs --language es     # solo español
    python -m src.document_ingestion.cvs.runner_cvs --language en     # solo inglés
"""

import argparse
import uuid
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Optional

from src.document_ingestion.cvs.doc_chunking_cvs import get_text_split_cv
from src.services.azure_storage_service import list_json_configs_from_blob
from src.services.cosmos_service import get_querys_cosmos
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

        print(f"\n--- content ---")
        print(chunk.get("content", ""))

        print(f"\n--- metadata ---")
        meta = chunk.get("metadata", {})
        print(json.dumps(meta, indent=2, ensure_ascii=False))

        # Mostrar campos clave del documento Cosmos (sin embedding)
        print(f"\n--- campos Cosmos ---")
        cosmos_fields = {k: v for k, v in chunk.items()
                         if k not in ("content", "metadata", "embedding")}
        print(json.dumps(cosmos_fields, indent=2, ensure_ascii=False, default=str))

    print(f"\n{'=' * 70}")


# ===========================================================================
# Pipeline principal
# ===========================================================================

MAX_WORKERS = 5  # hilos concurrentes por idioma (ajustar según límites de Azure)


def _process_cv(
    blob_path: str,
    language: str,
    session_id: str,
    idx: int,
    total: int,
) -> tuple[str, bool, str]:
    """Procesa un único CV. Devuelve (cv_id, éxito, mensaje_error)."""
    cv_id = blob_path.replace(BLOB_CVS_PREFIX, "")

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
        print(f"  [{idx}/{total}] {cv_id} — OK")
        return (cv_id, True, "")
    except Exception as e:
        print(f"  [{idx}/{total}] {cv_id} — ERROR: {e}")
        return (cv_id, False, str(e))


def run_cv_chunking(language: str, max_workers: int = MAX_WORKERS) -> None:
    """Ejecuta el chunking de todos los CVs de un idioma dado (en paralelo)."""
    print(f"\n{'=' * 60}")
    print(f"  CHUNKING DE CVs — idioma: {language}")
    print(f"{'=' * 60}")

    json_names = _list_cv(language)
    if not json_names:
        print(f"  No se encontraron CVs en data/cvs/{language}/")
        return

    session_id = _generate_session_id(language)
    total = len(json_names)
    workers = min(max_workers, total)

    print(f"  Container  : {config.azure_container_name}")
    print(f"  Prefix     : {BLOB_CVS_PREFIX}{language}/")
    print(f"  CVs found  : {total}")
    print(f"  Workers    : {workers}")
    print(f"  Session ID : {session_id}")
    print("-" * 60)

    ok_count = 0
    err_count = 0
    errors: list[tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _process_cv, blob_path, language, session_id, idx, total
            ): blob_path
            for idx, blob_path in enumerate(json_names, start=1)
        }

        for future in as_completed(futures):
            cv_id, success, err_msg = future.result()
            if success:
                ok_count += 1
            else:
                err_count += 1
                errors.append((cv_id, err_msg))

    print(f"\n{'-' * 60}")
    print(f"  Resultado ({language}): {ok_count} OK / {err_count} errores / {total} total")
    if errors:
        print(f"\n  Errores detallados:")
        for cv_id, msg in errors:
            print(f"    - {cv_id}: {msg}")
    print(f"{'=' * 60}\n")

# ===========================================================================
# Diagnóstico: detectar CVs con chunks faltantes
# ===========================================================================

EXPECTED_CHUNK_TYPES = {"experience", "education", "skills"}


def diagnose_cv_chunks(language: str) -> dict:
    """Compara blobs en Storage con chunks en Cosmos y reporta fallos.

    Returns
    -------
    dict con claves:
        - ``missing_entirely``: CVs sin ningún chunk en Cosmos
        - ``incomplete``: CVs con <3 chunks (indica qué tipos faltan)
        - ``ok``: CVs con 3/3 chunks
    """
    print(f"\n{'=' * 60}")
    print(f"  DIAGNÓSTICO DE CVs — idioma: {language}")
    print(f"{'=' * 60}")

    # 1. Listar blobs
    json_names = _list_cv(language)
    if not json_names:
        print(f"  No se encontraron CVs en data/cvs/{language}/")
        return {"missing_entirely": [], "incomplete": {}, "ok": []}

    print(f"  Blobs encontrados: {len(json_names)}")

    # 2. Consultar Cosmos: todos los chunks no borrados de CVs de este idioma
    query = (
        "SELECT c.sourcePath, c.chunk_type FROM c "
        "WHERE c.sourceCollection = 'cvs' "
        "AND c.isDeleted = false "
        f"AND CONTAINS(c.sourcePath, 'data/cvs/{language}/')"
    )
    cosmos_chunks = get_querys_cosmos(query, config.cosmosdb_container_cvs)

    # 3. Agrupar chunks por sourcePath
    chunks_by_cv: dict[str, set[str]] = {}
    for doc in cosmos_chunks:
        sp = doc.get("sourcePath", "")
        ct = doc.get("chunk_type", "")
        chunks_by_cv.setdefault(sp, set()).add(ct)

    print(f"  CVs con chunks en Cosmos: {len(chunks_by_cv)}")

    # 4. Clasificar
    missing_entirely: list[str] = []
    incomplete: dict[str, list[str]] = {}
    ok: list[str] = []

    for blob_path in json_names:
        found_types = chunks_by_cv.get(blob_path, set())
        missing_types = EXPECTED_CHUNK_TYPES - found_types

        if not found_types:
            missing_entirely.append(blob_path)
        elif missing_types:
            incomplete[blob_path] = sorted(missing_types)
        else:
            ok.append(blob_path)

    # 5. Report
    print(f"\n  --- Resultado ---")
    print(f"  OK (3/3 chunks)      : {len(ok)}")
    print(f"  Incompletos          : {len(incomplete)}")
    print(f"  Sin ningún chunk     : {len(missing_entirely)}")
    print(f"  Total blobs          : {len(json_names)}")

    if incomplete:
        print(f"\n  CVs incompletos (faltan chunks):")
        for blob, missing in sorted(incomplete.items()):
            short = blob.replace(BLOB_CVS_PREFIX, "")
            print(f"    - {short}: faltan {missing}")

    if missing_entirely:
        print(f"\n  CVs sin ningún chunk:")
        for blob in sorted(missing_entirely):
            short = blob.replace(BLOB_CVS_PREFIX, "")
            print(f"    - {short}")

    print(f"{'=' * 60}\n")
    return {"missing_entirely": missing_entirely, "incomplete": incomplete, "ok": ok}


def rerun_failed_cvs(language: str, max_workers: int = MAX_WORKERS) -> None:
    """Diagnostica y re-procesa solo los CVs que tienen chunks faltantes."""
    result = diagnose_cv_chunks(language)

    failed_blobs = result["missing_entirely"] + list(result["incomplete"].keys())
    if not failed_blobs:
        print("  No hay CVs fallidos — todo OK.")
        return

    print(f"\n  Re-procesando {len(failed_blobs)} CVs fallidos...")

    session_id = _generate_session_id(language)
    total = len(failed_blobs)
    workers = min(max_workers, total)

    ok_count = 0
    err_count = 0
    errors: list[tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _process_cv, blob_path, language, session_id, idx, total
            ): blob_path
            for idx, blob_path in enumerate(failed_blobs, start=1)
        }
        for future in as_completed(futures):
            cv_id, success, err_msg = future.result()
            if success:
                ok_count += 1
            else:
                err_count += 1
                errors.append((cv_id, err_msg))

    print(f"\n{'-' * 60}")
    print(f"  Rerun ({language}): {ok_count} OK / {err_count} errores / {total} total")
    if errors:
        print(f"\n  Errores persistentes:")
        for cv_id, msg in errors:
            print(f"    - {cv_id}: {msg}")
    print(f"{'=' * 60}\n")


# ===========================================================================
# Entry point
# ===========================================================================

def main(language: Optional[str] = None, max_workers: int = MAX_WORKERS,
         diagnose: bool = False, rerun_failed: bool = False) -> None:
    languages_to_process: List[str] = []

    if language:
        languages_to_process = [language.strip().lower()]
    else:
        print("No se especificó idioma — descubriendo idiomas disponibles...")
        languages_to_process = _discover_languages()
        if not languages_to_process:
            print("No se encontraron CVs en Blob Storage bajo data/cvs/")
            return
        print(f"Idiomas encontrados: {languages_to_process}")

    for lang in languages_to_process:
        if diagnose:
            diagnose_cv_chunks(lang)
        elif rerun_failed:
            rerun_failed_cvs(lang, max_workers=max_workers)
        else:
            run_cv_chunking(lang, max_workers=max_workers)


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
    parser.add_argument(
        "--workers",
        type=int,
        default=MAX_WORKERS,
        help=f"Número de hilos concurrentes (default: {MAX_WORKERS}).",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Solo diagnosticar: muestra qué CVs tienen chunks faltantes.",
    )
    parser.add_argument(
        "--rerun-failed",
        action="store_true",
        help="Diagnosticar y re-procesar solo los CVs con chunks faltantes.",
    )
    args = parser.parse_args()
    main(
        language=args.language,
        max_workers=args.workers,
        diagnose=args.diagnose,
        rerun_failed=args.rerun_failed,
    )
