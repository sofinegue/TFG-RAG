"""
Runner for chunking Wikipedia articles stored in data/wikipedia/<language>/.

Assumes that each article has already been uploaded to Azure Blob Storage
under the same relative path:
  ``wikipedia/<language>/json/<filename>``
  ``wikipedia/<language>/txt/<filename>``

Usage
-----
    python -m document_ingestion.run_wikipedia --language en
    python -m document_ingestion.run_wikipedia --language en --format json
    python -m document_ingestion.run_wikipedia --language en --limit 20 --dry-run
    python -m document_ingestion.run_wikipedia --language en --session-id MY_SESSION

Notes
-----
Wikipedia chunking (``get_wikipedia_text_split``) is currently mocked.
See ``document_ingestion/wikipedia_text_split.py`` for the implementation roadmap.

Folder structure expected on disk::

    data/wikipedia/
        en/
            json/   ← Wikipedia articles as JSON
            txt/    ← Wikipedia articles as plain text
        es/
            json/
            txt/
"""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path

from document_ingestion.run_utils import (
    EXTENSIONS_ALL,
    EXTENSIONS_JSON,
    add_common_args,
    collect_local_files,
    generate_session_id,
    print_run_summary,
)
from document_ingestion.wikipedia_text_split import get_wikipedia_text_split
from models.doc_model import DocEntity

_FORMAT_CHOICES = ("json", "txt", "all")
_FORMAT_EXTS: dict[str, frozenset[str]] = {
    "json": EXTENSIONS_JSON,
    "txt": frozenset({".txt"}),
    "all": EXTENSIONS_ALL,
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Chunk Wikipedia articles for a given language.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    add_common_args(parser)
    parser.add_argument(
        "--format",
        choices=_FORMAT_CHOICES,
        default="all",
        help="File format to process: 'json', 'txt', or 'all' (default).",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# File collection helpers
# ---------------------------------------------------------------------------


def collect_wikipedia_files(language_folder: Path, fmt: str) -> list[Path]:
    """Collect articles from the json/ and/or txt/ subdirectories.

    Parameters
    ----------
    language_folder:
        e.g. ``data/wikipedia/en/``
    fmt:
        One of ``"json"``, ``"txt"``, or ``"all"``.
    """
    allowed = _FORMAT_EXTS[fmt]
    files: list[Path] = []

    for subdir in ("json", "txt"):
        sub_path = language_folder / subdir
        if not sub_path.exists():
            continue
        # Only pick extensions relevant to this subdir
        subdir_exts = frozenset({f".{subdir}"}) & allowed
        if not subdir_exts:
            # e.g. user asked for json-only but we're in txt/
            continue
        files.extend(collect_local_files(sub_path, allowed_exts=subdir_exts))

    return sorted(files, key=lambda p: p.name.lower())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    args = build_args()
    language = args.language.strip().lower()
    fmt = args.format

    project_root = Path(__file__).resolve().parents[2]
    language_folder = project_root / "data" / "wikipedia" / language

    if not language_folder.exists():
        raise FileNotFoundError(
            f"Expected folder not found: {language_folder}\n"
            f"Make sure data/wikipedia/{language}/ exists."
        )

    files = collect_wikipedia_files(language_folder, fmt)
    if args.limit and args.limit > 0:
        files = files[: args.limit]

    if not files:
        print(f"No files found in data/wikipedia/{language}/ for format '{fmt}'")
        return

    blob_prefix = f"wikipedia/{language}"
    session_id = args.session_id or generate_session_id("WIKI", language)

    print_run_summary(language_folder, language, files, session_id, blob_prefix)

    for index, file_path in enumerate(files, start=1):
        # Preserve subfolder in blob path: wikipedia/en/json/Literature.json
        subdir = file_path.parent.name   # "json" or "txt"
        blob_name = f"{blob_prefix}/{subdir}/{file_path.name}"

        doc_entity = DocEntity(
            id=str(uuid.uuid4()),
            doc_id=blob_name,
            doc_nombre=blob_name,
            id_caso=f"wikipedia-{language}",
            usuario="local-runner",
            equipo="wikipedia",
            language=language,
            source_collection="wikipedia",
        ).model_dump(exclude_none=True)

        status = "[DRY-RUN]" if args.dry_run else f"[{index}/{len(files)}]"
        print(f"{status} {blob_name}")

        if args.dry_run:
            continue

        get_wikipedia_text_split(
            blob_name=blob_name,
            doc_id=blob_name,
            doc_entity=doc_entity,
            session_id=session_id,
            cdu="DOCPROCESS",
        )

    print("\nProcess finished.")


if __name__ == "__main__":
    main()
