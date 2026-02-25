"""
Runner for chunking CV documents stored in Azure Blob Storage.

Lists CV JSON blobs from the ``investigation-rag-usecases`` container
under the prefix ``cvs/<language>/``, downloads each one, chunks it into
3 semantic pieces (experience, education, skills) and uploads the chunks
to Cosmos DB (container ``Chunks-CVs``).

Usage
-----
    python -m document_ingestion.run_cvs --language es
    python -m document_ingestion.run_cvs --language en --limit 5 --dry-run
    python -m document_ingestion.run_cvs --language es --session-id MY_SESSION
"""

from __future__ import annotations

import argparse
import uuid

from tqdm import tqdm
from document_ingestion.cv_text_split import get_cv_text_split
from document_ingestion.run_utils import (
    add_common_args,
    generate_session_id,
)
from services.azure_storage_service import list_json_configs_from_blob
from models.doc_model import DocEntity
from config import config


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Chunk CV JSON documents for a given language.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    add_common_args(parser)
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _list_cv_blobs(language: str) -> list[str]:
    """Return blob names under ``data/cvs/<language>/`` from Azure Storage."""
    prefix = f"data/cvs/{language}/"
    return list_json_configs_from_blob(
        account_name=config.azure_storage_account,
        account_key=config.azure_storage_key,
        container_name=config.azure_container_name,   # investigation-rag-usecases
        prefix=prefix,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    args = build_args()
    language = args.language.strip().lower()

    # Step 1 — List CV blobs from Azure Blob Storage
    print(f"\n🔍 Listing CV blobs in container '{config.azure_container_name}' "
          f"with prefix 'data/cvs/{language}/'...")
    blob_names = _list_cv_blobs(language)

    if args.limit and args.limit > 0:
        blob_names = blob_names[: args.limit]

    if not blob_names:
        print(f"No CV JSON blobs found under cvs/{language}/")
        return

    session_id = args.session_id or generate_session_id("CVS", language)

    # Summary
    print(f"\n{'─' * 55}")
    print(f"  Container    : {config.azure_container_name}")
    print(f"  Language     : {language}")
    print(f"  Blobs found  : {len(blob_names)}")
    print(f"  Session ID   : {session_id}")
    print(f"{'─' * 55}\n")

    for blob_name in blob_names:
        print(f"  • {blob_name}")
    print()

    # Step 2 — Process each blob
    progress = tqdm(
        blob_names,
        desc="📄 Processing CVs",
        unit="cv",
        ncols=90,
        disable=args.dry_run,
    )

    for index, blob_name in enumerate(progress, start=1):
        file_name = blob_name.rsplit("/", 1)[-1]
        progress.set_postfix_str(file_name, refresh=True)

        doc_entity = DocEntity(
            id=str(uuid.uuid4()),
            doc_id=blob_name,
            doc_nombre=file_name,
            id_caso=f"cvs-{language}",
            usuario="local-runner",
            equipo="cvs",
            language=language,
            source_collection="cvs",
        ).model_dump(exclude_none=True)

        if args.dry_run:
            print(f"[DRY-RUN] {blob_name}")
            continue

        # Download from Blob Storage → chunk → upload to Cosmos
        get_cv_text_split(
            blob_name=blob_name,
            doc_id=blob_name,
            doc_entity=doc_entity,
            session_id=session_id,
            cdu="DOCPROCESS",
        )

    print("\n✅ Process finished.")


if __name__ == "__main__":
    main()
