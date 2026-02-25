"""
Wikipedia article chunking pipeline.

This module exposes :func:`get_wikipedia_text_split`, which mirrors the
signature of :func:`document_ingestion.doc_chunking.get_text_split` but is
specialised for Wikipedia article files (JSON or TXT).

Implementation roadmap
----------------------
1. Download the Wikipedia article blob from Azure Blob Storage.
2. Parse the content:
   - **.json** blobs: extract the ``"text"`` (or ``"content"``) field.
   - **.txt** blobs: read the raw text directly.
3. Pre-process the article:
   - Strip infoboxes, citation markers, and disambiguation notices.
   - Re-structure as Markdown (section headings → ``# / ## / ###``).
4. Call ``processchunks.markdown_percentage()`` to split into token-bounded
   chunks that respect heading boundaries.
5. For each chunk, call ``openai_service.get_embedding()`` and then
   ``processchunks.upload_chunks()`` to persist to Cosmos DB.

Metadata fields (``doc_entity``) populated by the runner
---------------------------------------------------------
- ``source_collection = "wikipedia"``
- ``language`` — ISO 639-1 code (e.g. ``"en"``)
- ``id_caso = "wikipedia-<language>"``
- ``equipo = "wikipedia"``
"""

from __future__ import annotations


def get_wikipedia_text_split(
    blob_name: str,
    doc_id: str,
    doc_entity: dict,
    session_id: str,
    *,
    call_id: str = "",
    cdu: str = "DOCPROCESS",
) -> None:
    """Process a Wikipedia article into chunks and upload to Cosmos DB.

    Parameters
    ----------
    blob_name:
        Path of the file in Azure Blob Storage, e.g.
        ``"wikipedia/en/json/Literature.json"``.
    doc_id:
        Unique document identifier used for deduplication in Cosmos DB.
    doc_entity:
        Validated metadata dictionary produced by
        ``DocEntity(...).model_dump(exclude_none=True)``.
        Expected keys: ``id``, ``doc_id``, ``doc_nombre``, ``id_caso``,
        ``usuario``, ``equipo``, ``language``, ``source_collection``.
    session_id:
        Session identifier for log traceability.
    call_id:
        Optional call identifier (used in logging).
    cdu:
        Functional unit code, forwarded to downstream services.

    Raises
    ------
    NotImplementedError
        Until this function is fully implemented.

    Notes
    -----
    Planned imports once implemented::

        from services.azure_storage_service import get_specific_file_from_blob_container
        from services.openai_service import get_embedding
        from document_ingestion.processchunks import (
            upload_chunks,
            markdown_percentage,
            mark_existing_chunks_as_deleted,
        )
        import config
    """
    raise NotImplementedError(
        "Wikipedia chunking is not yet implemented. "
        "See the module docstring for the implementation roadmap."
    )
