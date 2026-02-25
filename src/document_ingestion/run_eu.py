"""
Runner for chunking EU regulatory documents stored in data/eu/<language>/.

Assumes that each file has already been uploaded to Azure Blob Storage
under the same relative path: ``eu/<language>/<filename>``.

Usage
-----
    python -m document_ingestion.run_eu --language es
    python -m document_ingestion.run_eu --language fr --limit 10 --dry-run
    python -m document_ingestion.run_eu --language pt --get-formulas --session-id MY_SESSION
"""

from __future__ import annotations

import argparse
import logging
import uuid
from pathlib import Path

from document_ingestion.doc_chunking import get_text_split
from document_ingestion.run_utils import (
    EXTENSIONS_DOCS,
    add_common_args,
    collect_local_files,
    generate_session_id,
    print_run_summary,
)
from models.doc_model import DocEntity

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_args() -> argparse.Namespace:
    logger.info("Building CLI arguments...")
    parser = argparse.ArgumentParser(
        description="Chunk EU regulatory documents for a given language.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    add_common_args(parser)
    parser.add_argument(
        "--get-formulas",
        action="store_true",
        help="Enable formula extraction for PDF files (Document Intelligence).",
    )
    args = parser.parse_args()
    logger.info(f"Arguments parsed: language={args.language}, limit={getattr(args, 'limit', None)}, dry_run={args.dry_run}")
    return args


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    logger.info("Starting EU document chunking process...")
    args = build_args()
    language = args.language.strip().lower()
    logger.info(f"Processing language: {language}")

    project_root = Path(__file__).resolve().parents[2]
    logger.debug(f"Project root: {project_root}")
    local_folder = project_root / "data" / "eu" / language
    logger.info(f"Local folder path: {local_folder}")

    if not local_folder.exists():
        logger.error(f"Expected folder not found: {local_folder}")
        raise FileNotFoundError(
            f"Expected folder not found: {local_folder}\n"
            f"Make sure data/eu/{language}/ exists."
        )

    logger.info("Collecting local files...")
    files = collect_local_files(local_folder, allowed_exts=EXTENSIONS_DOCS)
    logger.info(f"Found {len(files)} files in total")

    if args.limit and args.limit > 0:
        logger.info(f"Applying limit: {args.limit} files")
        files = files[: args.limit]

    if not files:
        logger.warning(f"No processable files found in data/eu/{language}/")
        return

    blob_prefix = f"eu/{language}"
    session_id = args.session_id or generate_session_id("EU", language)
    logger.info(f"Session ID: {session_id}")
    logger.info(f"Blob prefix: {blob_prefix}")

    print_run_summary(local_folder, language, files, session_id, blob_prefix)

    for index, file_path in enumerate(files, start=1):
        blob_name = f"{blob_prefix}/{file_path.name}"
        logger.info(f"Processing file {index}/{len(files)}: {file_path.name}")

        try:
            doc_entity = DocEntity(
                id=str(uuid.uuid4()),
                doc_id=blob_name,
                doc_nombre=blob_name,
                id_caso=f"eu-{language}",
                usuario="local-runner",
                equipo="eu",
                language=language,
                source_collection="eu",
            ).model_dump(exclude_none=True)
            logger.debug(f"DocEntity created with ID: {doc_entity['id']}")

            status = "[DRY-RUN]" if args.dry_run else f"[{index}/{len(files)}]"
            print(f"{status} {blob_name}")

            if args.dry_run:
                logger.info(f"Dry-run mode: skipping processing for {blob_name}")
                continue

            logger.info(f"Starting text split for {blob_name}...")
            get_text_split(
                blob_name=blob_name,
                docId=blob_name,
                get_formulas=args.get_formulas,
                SessionId=session_id,
                doc_entity=doc_entity,
                CDU="DOCPROCESS",
            )
            logger.info(f"Successfully processed {blob_name}")

        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {str(e)}", exc_info=True)
            continue

    logger.info("Process finished successfully.")


if __name__ == "__main__":
    main()
