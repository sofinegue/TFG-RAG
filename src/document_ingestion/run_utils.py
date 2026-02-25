"""
Shared utilities for all document ingestion runners.

Each runner (EU docs, CVs, Wikipedia) imports from here to avoid duplication.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Extension sets
# ---------------------------------------------------------------------------

EXTENSIONS_DOCS: frozenset[str] = frozenset({".pdf", ".txt"})
EXTENSIONS_JSON: frozenset[str] = frozenset({".json"})
EXTENSIONS_ALL: frozenset[str] = frozenset({".pdf", ".txt", ".json"})


# ---------------------------------------------------------------------------
# File collection
# ---------------------------------------------------------------------------


def collect_local_files(
    local_folder: Path,
    allowed_exts: frozenset[str] | None = None,
    *,
    recursive: bool = False,
) -> list[Path]:
    """Return a sorted list of files in *local_folder* filtered by extension.

    Parameters
    ----------
    local_folder:
        Directory to scan.
    allowed_exts:
        Set of lower-case extensions to keep (e.g. ``{".pdf", ".json"}``).
        Defaults to :data:`EXTENSIONS_ALL`.
    recursive:
        If ``True``, walk subdirectories as well.
    """
    if allowed_exts is None:
        allowed_exts = EXTENSIONS_ALL

    if recursive:
        candidates = local_folder.rglob("*")
    else:
        candidates = local_folder.iterdir()

    files = [
        p
        for p in candidates
        if p.is_file() and p.suffix.lower() in allowed_exts
    ]
    return sorted(files, key=lambda p: p.name.lower())


# ---------------------------------------------------------------------------
# CLI argument helpers
# ---------------------------------------------------------------------------


def add_common_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Attach the standard CLI flags shared by every runner.

    Adds: ``--language``, ``--limit``, ``--dry-run``, ``--session-id``.
    """
    parser.add_argument(
        "--language",
        type=str,
        default="es",
        help="Language to process (e.g. es, en, fr, it, pt). Default: es.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of files to process. 0 = no limit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be processed without running chunking.",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        default="",
        help="Optional session ID for traceability. Auto-generated if omitted.",
    )
    return parser


# ---------------------------------------------------------------------------
# Session ID
# ---------------------------------------------------------------------------


def generate_session_id(prefix: str, language: str) -> str:
    """Return a timestamped session ID like ``EU_ES_20260225_143012``."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix.upper()}_{language.upper()}_{ts}"


# ---------------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------------


def print_run_summary(
    local_folder: Path,
    language: str,
    files: list[Path],
    session_id: str,
    blob_prefix: str,
) -> None:
    """Print a human-readable summary before the run starts."""
    print(f"\n{'─' * 55}")
    print(f"  Local folder : {local_folder}")
    print(f"  Language     : {language}")
    print(f"  Files found  : {len(files)}")
    print(f"  Files content : {files}")
    print(f"  Session ID   : {session_id}")
    print(f"  Blob prefix  : {blob_prefix}/<filename>")
    print(f"{'─' * 55}\n")
