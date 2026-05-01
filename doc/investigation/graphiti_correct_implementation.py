​import json
import logging
import os
import re
import asyncio
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from collections import Counter
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.aio import DocumentIntelligenceClient as AsyncDocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from langchain_text_splitters import RecursiveCharacterTextSplitter

if TYPE_CHECKING:
    from src.services.ingestion import IngestionJob

from storage.neo4j.neo4j_dropper import Neo4jDropper
from storage.sharepoint.sharepoint_manager import SharePointManager
from storage.postgres.database_manager import DatabaseManager
from storage.postgres.repositories.documents_repository import DocumentRepository
from storage.neo4j.neo4j_graphiti import GraphitiClientService
from src.tools.document_tools import convert_office_to_pdf
load_dotenv()


class Neo4jIngestion:
    """Handles document ingestion pipeline including extraction, chunking,
    storage, and preparation for Neo4j graph insertion.
    """

    def __init__(self) -> None:
        self.sp_manager = SharePointManager()
        self.neo4j_dropper = Neo4jDropper()
        self.db_manager = DatabaseManager.get_instance()
        self.document_repo = DocumentRepository(self.db_manager)
        self.azure_document_intelligence_client = DocumentIntelligenceClient(
            endpoint=os.getenv("AZURE_FORM_RECOGNIZER_ENDPOINT"),
            credential=AzureKeyCredential(os.getenv("AZURE_FORM_RECOGNIZER_KEY")),
        )
        self.async_azure_di_client = AsyncDocumentIntelligenceClient(
            endpoint=os.getenv("AZURE_FORM_RECOGNIZER_ENDPOINT"),
            credential=AzureKeyCredential(os.getenv("AZURE_FORM_RECOGNIZER_KEY")),
        )
        self.graphiti_service = GraphitiClientService()
        self.logger = logging.getLogger(__name__)

    async def ingest_all(self):
        """Ingests all documents listed in SharePoint into the system using parallel processing."""
        await self.db_manager.init_pool()
        
        # Get all documents and filter out folders
        all_documents = await self.document_repo.list()
        documents = [doc for doc in all_documents if doc.get("document_type") != "FOLDER"]
        
        # Get max processable size and concurrency limit from environment
        MAX_PROCESSABLE_SIZE_MB = int(os.getenv("MAX_PROCESSABLE_SIZE_MB", "1000"))
        max_size_bytes = MAX_PROCESSABLE_SIZE_MB * 1024 * 1024
        max_concurrent = int(os.getenv("MAX_CONCURRENT_INGESTIONS", "3"))
        
        # Filter out oversized documents
        valid_documents = []
        for document in documents:
            document_size = document.get("size", 0)
            document_size_mb = document_size / 1024 / 1024 if document_size else 0
            
            if document_size > max_size_bytes:
                self.logger.warning(
                    f"Skipping document ID {document['id']} ({document['document_path']}): "
                    f"size {document_size_mb:.2f} MB exceeds maximum {MAX_PROCESSABLE_SIZE_MB} MB"
                )
            else:
                valid_documents.append(document)
        
        self.logger.info(
            f"Found {len(documents)} documents total, {len(valid_documents)} valid for ingestion "
            f"(excluding folders and oversized files). Processing with {max_concurrent} concurrent workers."
        )
        
        # Process documents in parallel with semaphore to limit concurrency
        await self._process_documents_parallel(valid_documents, max_concurrent)

    @staticmethod
    def startup_ingestion_with_limit(max_documents: Optional[int] = None):
        """Start background ingestion for first-time setup with optional document limit.
        Creates one job per document and starts them automatically.
        
        Args:
            max_documents: Maximum number of documents to ingest (None = all documents)
        """
        # Schedule the actual ingestion work as a background task
        asyncio.create_task(Neo4jIngestion._startup_ingestion_async(max_documents))
        logging.info("✅ Startup ingestion scheduled in background")
    
    @staticmethod
    def prepare_startup_ingestion_jobs(max_documents: Optional[int] = None):
        """Prepare ingestion jobs for first-time setup without starting them.
        Creates jobs in PENDING state that can be started from the frontend.
        
        Args:
            max_documents: Maximum number of documents to prepare (None = all documents)
        """
        # Schedule the job preparation as a background task
        asyncio.create_task(Neo4jIngestion._prepare_jobs_async(max_documents))
        logging.info("✅ Preparing ingestion jobs in background (not started)")
    
    @staticmethod
    async def _startup_ingestion_async(max_documents: Optional[int] = None):
        """Internal async method that performs the actual startup ingestion work.
        Creates a fresh Neo4jIngestion instance to avoid blocking during initialization.
        """
        from src.services.ingestion import IngestionManager, DocumentIngestionStatus
        from datetime import datetime
        import uuid
        
        try:
            # Create ingestion instance here in background (not during startup)
            neo4j_ingestion = Neo4jIngestion()
            
            # Ensure database pool is initialized
            await neo4j_ingestion.db_manager.init_pool()
            
            # Get documents for ingestion
            all_documents = await neo4j_ingestion.document_repo.list()
            documents = [doc for doc in all_documents if doc.get("document_type") != "FOLDER"]
            
            # Limit documents if configured
            if max_documents is not None:
                documents = documents[:max_documents]
                neo4j_ingestion.logger.info(f"⚠️ Testing mode: limiting ingestion to {len(documents)} documents")
            
            # Create one job per document and start them
            ingestion_manager = IngestionManager()
            job_ids = []
            
            for doc in documents:
                doc_id = doc.get("id")
                doc_path = doc.get("document_path", f"document_{doc_id}")
                job_id = f"startup_doc_{doc_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
                
                # Create job for single document
                job = await ingestion_manager.create_job(job_id, 1, priority=1)
                job.update_document_status(doc_id, DocumentIngestionStatus.PENDING, doc_path)
                
                # Persist document status to database immediately
                await ingestion_manager._sync_job_to_db(job)
                
                # Start ingestion in background
                started = await ingestion_manager.start_ingestion(job_id, doc_id)
                if started:
                    job_ids.append(job_id)
            
            neo4j_ingestion.logger.info(
                f"✅ Started {len(job_ids)} background ingestion jobs for {len(documents)} documents (tracking enabled)"
            )
        except Exception as e:
            logging.error(f"Error in startup ingestion: {e}", exc_info=True)
    
    @staticmethod
    async def _prepare_jobs_async(max_documents: Optional[int] = None):
        """Internal async method that prepares jobs without starting ingestion.
        Creates a fresh Neo4jIngestion instance to avoid blocking during initialization.
        """
        from src.services.ingestion import IngestionManager, DocumentIngestionStatus
        from datetime import datetime
        import uuid
        
        try:
            # Create ingestion instance here in background (not during startup)
            neo4j_ingestion = Neo4jIngestion()
            
            # Ensure database pool is initialized
            await neo4j_ingestion.db_manager.init_pool()
            
            # Get documents for ingestion
            all_documents = await neo4j_ingestion.document_repo.list()
            documents = [doc for doc in all_documents if doc.get("document_type") != "FOLDER"]
            
            # Limit documents if configured
            if max_documents is not None:
                documents = documents[:max_documents]
                neo4j_ingestion.logger.info(f"⚠️ Testing mode: limiting to {len(documents)} documents")
            
            # Create one job per document (but don't start them)
            ingestion_manager = IngestionManager()
            job_ids = []
            
            for doc in documents:
                doc_id = doc.get("id")
                doc_path = doc.get("document_path", f"document_{doc_id}")
                job_id = f"startup_doc_{doc_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
                
                # Create job for single document (stays in PENDING state)
                job = await ingestion_manager.create_job(job_id, 1, priority=1)
                job.update_document_status(doc_id, DocumentIngestionStatus.PENDING, doc_path)
                
                # Persist document status to database immediately
                await ingestion_manager._sync_job_to_db(job)
                
                job_ids.append(job_id)
            
            neo4j_ingestion.logger.info(
                f"✅ Prepared {len(job_ids)} ingestion jobs (PENDING state). Start them from the frontend."
            )
        except Exception as e:
            logging.error(f"Error preparing ingestion jobs: {e}", exc_info=True)

    async def ingest_single_document_with_tracking(self, job: 'IngestionJob', document_id: int):
        """Ingest a single document with progress tracking via IngestionJob.
        
        Args:
            job: IngestionJob instance for tracking progress
            document_id: ID of the document to ingest
        """
        from src.services.ingestion import DocumentIngestionStatus, PipelineStep, StepStatus
        
        # Check for cancel/stop before starting
        if job.cancel_requested or job.stop_requested:
            self.logger.info(f"Job {job.job_id}: Stop/cancel requested, skipping document {document_id}")
            return
        
        await self.db_manager.init_pool()
        
        # Get the specific document
        all_documents = await self.document_repo.list()
        document = next((doc for doc in all_documents if doc.get("id") == document_id), None)
        
        if not document:
            error_msg = f"Document ID {document_id} not found"
            self.logger.error(error_msg)
            job.mark_processed(document_id, success=False, error=error_msg)
            return
        
        document_path = document["document_path"]
        document_size = document.get("size", 0)
        document_size_mb = document_size / 1024 / 1024 if document_size else 0
        
        # Check size limits
        MAX_PROCESSABLE_SIZE_MB = int(os.getenv("MAX_PROCESSABLE_SIZE_MB", "1000"))
        max_size_bytes = MAX_PROCESSABLE_SIZE_MB * 1024 * 1024
        
        if document_size > max_size_bytes:
            error_msg = f"File size ({document_size_mb:.2f} MB) exceeds limit"
            self.logger.warning(f"Skipping document ID {document_id} ({document_path}): {error_msg}")
            job.update_document_status(document_id, DocumentIngestionStatus.SKIPPED, document_path, error_msg)
            job.skipped_documents += 1
            job.mark_processed(document_id, success=False, error=error_msg)
            return
        
        # Update to processing
        job.update_document_status(document_id, DocumentIngestionStatus.PROCESSING, document_path)
        
        try:
            # Track pipeline steps
            job.update_pipeline_step(document_id, PipelineStep.FETCH_METADATA, StepStatus.RUNNING)
            # Metadata is already fetched, mark as completed
            job.update_pipeline_step(document_id, PipelineStep.FETCH_METADATA, StepStatus.COMPLETED)
            
            # Ingest the document (pass job for tracking remaining steps)
            await self.ingest_document(document_id, document_path, job)
            
            job.mark_processed(document_id, success=True)
            self.logger.info(f"Job {job.job_id}: ✅ Successfully ingested document ID {document_id}")
        except Exception as e:
            error_msg = str(e)
            job.mark_processed(document_id, success=False, error=error_msg)
            self.logger.error(f"Job {job.job_id}: ❌ Failed to ingest document ID {document_id}: {error_msg}")

    async def ingest_all_with_tracking(self, job: 'IngestionJob'):
        """Ingests all documents with progress tracking via IngestionJob.
        
        Args:
            job: IngestionJob instance for tracking progress
        """
        from src.services.ingestion import DocumentIngestionStatus
        
        await self.db_manager.init_pool()
        
        # Get all documents and filter out folders
        all_documents = await self.document_repo.list()
        documents = [doc for doc in all_documents if doc.get("document_type") != "FOLDER"]
        
        # Get max processable size and concurrency limit from environment
        MAX_PROCESSABLE_SIZE_MB = int(os.getenv("MAX_PROCESSABLE_SIZE_MB", "1000"))
        max_size_bytes = MAX_PROCESSABLE_SIZE_MB * 1024 * 1024
        max_concurrent = int(os.getenv("MAX_CONCURRENT_INGESTIONS", "3"))
        
        # Filter and initialize document statuses
        valid_documents = []
        for document in documents:
            document_id = document["id"]
            document_path = document["document_path"]
            document_size = document.get("size", 0)
            document_size_mb = document_size / 1024 / 1024 if document_size else 0
            
            if document_size > max_size_bytes:
                self.logger.warning(
                    f"Skipping document ID {document_id} ({document_path}): "
                    f"size {document_size_mb:.2f} MB exceeds maximum {MAX_PROCESSABLE_SIZE_MB} MB"
                )
                job.update_document_status(
                    document_id, DocumentIngestionStatus.SKIPPED, 
                    document_path, f"File size ({document_size_mb:.2f} MB) exceeds limit"
                )
                job.skipped_documents += 1
            else:
                valid_documents.append(document)
                job.update_document_status(
                    document_id, DocumentIngestionStatus.PENDING, document_path
                )
        
        self.logger.info(
            f"Job {job.job_id}: Found {len(documents)} documents total, "
            f"{len(valid_documents)} valid for ingestion. "
            f"Processing with {max_concurrent} concurrent workers."
        )
        
        # Process documents in parallel with tracking
        await self._process_documents_parallel_with_tracking(valid_documents, max_concurrent, job)

    async def _process_documents_parallel(self, documents: List[Dict], max_concurrent: int):
        """Process documents in parallel with concurrency limit.
        
        Args:
            documents: List of document dictionaries to process
            max_concurrent: Maximum number of concurrent ingestion tasks
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(document: Dict):
            async with semaphore:
                postgres_id = document["id"]
                document_path = document["document_path"]
                document_size = document.get("size", 0)
                document_size_mb = document_size / 1024 / 1024 if document_size else 0
                
                self.logger.info(
                    f"[Queue] Starting ingestion for document ID {postgres_id} at {document_path} "
                    f"(size: {document_size_mb:.2f} MB)"
                )
                
                try:
                    await self.ingest_document(postgres_id, document_path)
                    self.logger.info(f"[Queue] ✅ Successfully ingested document ID {postgres_id}")
                except Exception as e:
                    self.logger.error(f"[Queue] ❌ Failed to ingest document ID {postgres_id}: {str(e)}")
        
        # Create tasks for all documents
        tasks = [process_with_semaphore(doc) for doc in documents]
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Summary
        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = len(results) - successful
        self.logger.info(
            f"[Queue] Ingestion completed: {successful} successful, {failed} failed out of {len(documents)} documents"
        )

    async def _process_documents_parallel_with_tracking(
        self, documents: List[Dict], max_concurrent: int, job: 'IngestionJob'
    ):
        """Process documents in parallel with progress tracking.
        
        Args:
            documents: List of document dictionaries to process
            max_concurrent: Maximum number of concurrent ingestion tasks
            job: IngestionJob for progress tracking
        """
        from src.services.ingestion import DocumentIngestionStatus
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(document: Dict):
            # Check if stop was requested
            if job.stop_requested:
                self.logger.info(f"Job {job.job_id}: Stop requested, skipping document {document['id']}")
                return
            
            async with semaphore:
                postgres_id = document["id"]
                document_path = document["document_path"]
                document_size = document.get("size", 0)
                document_size_mb = document_size / 1024 / 1024 if document_size else 0
                
                # Update status to processing
                job.update_document_status(
                    postgres_id, DocumentIngestionStatus.PROCESSING, document_path
                )
                
                self.logger.info(
                    f"Job {job.job_id}: Starting ingestion for document ID {postgres_id} "
                    f"at {document_path} (size: {document_size_mb:.2f} MB)"
                )
                
                try:
                    await self.ingest_document(postgres_id, document_path)
                    job.mark_processed(postgres_id, success=True)
                    self.logger.info(f"Job {job.job_id}: ✅ Successfully ingested document ID {postgres_id}")
                except Exception as e:
                    error_msg = str(e)
                    job.mark_processed(postgres_id, success=False, error=error_msg)
                    self.logger.error(f"Job {job.job_id}: ❌ Failed to ingest document ID {postgres_id}: {error_msg}")
        
        # Create tasks for all documents
        tasks = [process_with_semaphore(doc) for doc in documents]
        
        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        
        self.logger.info(
            f"Job {job.job_id}: Ingestion completed - "
            f"{job.successful_documents} successful, "
            f"{job.failed_documents} failed, "
            f"{job.skipped_documents} skipped out of {job.total_documents} documents"
        )

    async def queue_document_ingestion(self, postgres_id: int, document_path: str):
        """Queue a single document for ingestion (for user uploads).
        
        Args:
            postgres_id: Document ID in PostgreSQL
            document_path: Path to the document
        """
        self.logger.info(f"[Queue] Queuing document ID {postgres_id} for ingestion")
        
        # Create background task for ingestion
        asyncio.create_task(self._ingest_with_error_handling(postgres_id, document_path))
        
        self.logger.info(f"[Queue] Document ID {postgres_id} queued successfully")
    
    async def _ingest_with_error_handling(self, postgres_id: int, document_path: str):
        """Wrapper for ingestion with error handling for background tasks.
        
        Args:
            postgres_id: Document ID in PostgreSQL
            document_path: Path to the document
        """
        try:
            await self.ingest_document(postgres_id, document_path)
            self.logger.info(f"[Queue] ✅ Background ingestion completed for document ID {postgres_id}")
        except Exception as e:
            self.logger.error(f"[Queue] ❌ Background ingestion failed for document ID {postgres_id}: {str(e)}")


    async def ingest_document(self, postgres_id: int, document_path: str, job: 'IngestionJob' = None) -> None:
        """Orchestrates the ingestion process for a document.

        Args:
            postgres_id: The document ID stored in Postgres.
            document_path: The local or SharePoint path to the document.
            job: Optional IngestionJob instance for tracking pipeline steps.
        """
        # Helper to check for stop/cancel requests
        def should_stop() -> bool:
            return job and (job.stop_requested or job.cancel_requested)
        
        try:
            self.logger.info(f"[Step 1/8] Processing paths for document {postgres_id}")
            sharepoint_path, docname_without_ext = self._process_paths(document_path)
            self.logger.info(f"[Step 1/8] ✓ Paths processed: {sharepoint_path}")
        except Exception as e:
            self.logger.error(f"[Step 1/8] ✗ Failed to process paths: {str(e)}")
            raise
        
        # Check for stop after path processing
        if should_stop():
            self.logger.info(f"[Ingestion] Stop/cancel requested for document {postgres_id}, aborting")
            return

        try:
            self.logger.info("[Step 2/8] Downloading document from SharePoint")
            if job:
                from src.services.ingestion import PipelineStep, StepStatus
                job.update_pipeline_step(postgres_id, PipelineStep.DOWNLOAD_FILE, StepStatus.RUNNING)
            
            file_content = await self._download_document(sharepoint_path)
            file_size_mb = len(file_content) / 1024 / 1024
            self.logger.info(f"[Step 2/8] ✓ Downloaded {len(file_content)} bytes ({file_size_mb:.2f} MB)")
            
            # Check if file is too large to process (even with conversion)
            MAX_PROCESSABLE_SIZE_MB = int(os.getenv("MAX_PROCESSABLE_SIZE_MB", "1000"))
            if file_size_mb > MAX_PROCESSABLE_SIZE_MB:
                error_msg = (
                    f"Document {postgres_id} is too large ({file_size_mb:.2f} MB > {MAX_PROCESSABLE_SIZE_MB} MB). "
                    "Skipping ingestion."
                )
                self.logger.warning(error_msg)
                if job:
                    job.update_pipeline_step(postgres_id, PipelineStep.DOWNLOAD_FILE, StepStatus.FAILED, error_msg)
                raise RuntimeError(error_msg)
            
            if job:
                job.update_pipeline_step(postgres_id, PipelineStep.DOWNLOAD_FILE, StepStatus.COMPLETED)
            
            # Yield to event loop to prioritize API requests
            await asyncio.sleep(0)
        except Exception as e:
            self.logger.error(f"[Step 2/8] ✗ Failed to download document: {str(e)}")
            if job:
                from src.services.ingestion import PipelineStep, StepStatus
                job.update_pipeline_step(postgres_id, PipelineStep.DOWNLOAD_FILE, StepStatus.FAILED, str(e))
            raise

        # NEW STEP: Convert large Office files to PDF before processing
        try:
            self.logger.info("[Step 2.5/8] Checking if document needs conversion")
            file_content, original_format = await self._convert_if_needed(file_content, document_path)
            if original_format:
                self.logger.info(f"[Step 2.5/8] ✓ Converted {original_format.upper()} to PDF ({len(file_content)} bytes)")
            else:
                self.logger.info("[Step 2.5/8] ✓ No conversion needed")
            
            # Yield to event loop to prioritize API requests
            await asyncio.sleep(0)
        except Exception as e:
            self.logger.error(f"[Step 2.5/8] ✗ Failed to convert document: {str(e)}")
            raise

        try:
            self.logger.info("[Step 3/8] Extracting text from document")
            if job:
                from src.services.ingestion import PipelineStep, StepStatus
                job.update_pipeline_step(postgres_id, PipelineStep.EXTRACT_TEXT, StepStatus.RUNNING)
            
            markdown_content, result = await self._extract_text_async(file_content)
            self.logger.info(f"[Step 3/8] ✓ Extracted {len(markdown_content)} characters of text")
            
            if job:
                job.update_pipeline_step(postgres_id, PipelineStep.EXTRACT_TEXT, StepStatus.COMPLETED)
            
            # Yield to event loop to prioritize API requests
            await asyncio.sleep(0)
        except Exception as e:
            self.logger.error(f"[Step 3/8] ✗ Failed to extract text: {str(e)}")
            if job:
                from src.services.ingestion import PipelineStep, StepStatus
                job.update_pipeline_step(postgres_id, PipelineStep.EXTRACT_TEXT, StepStatus.FAILED, str(e))
            raise

        try:
            self.logger.info("[Step 5/8] Chunking output content")
            chunks = await self._chunk_output(markdown_content)
            self.logger.info(f"[Step 5/8] ✓ Created {len(chunks)} chunks")
            logging.info(f"Sample chunk: {chunks[0]['content'][:200]}...")
            
            # Yield to event loop to prioritize API requests
            await asyncio.sleep(0)
        except Exception as e:
            self.logger.error(f"[Step 5/8] ✗ Failed to chunk output content: {str(e)}")
            raise
        
        # Check for stop before the expensive Graphiti push
        if should_stop():
            self.logger.info(f"[Ingestion] Stop/cancel requested for document {postgres_id}, aborting before Graphiti push")
            return
        
        try:
            self.logger.info("[Step 7/8] Pushing chunks to Graphiti (Neo4j)")
            if job:
                from src.services.ingestion import PipelineStep, StepStatus
                # Mark GENERATE_EMBEDDINGS as running (happens inside _push_to_graphiti)
                job.update_pipeline_step(postgres_id, PipelineStep.GENERATE_EMBEDDINGS, StepStatus.RUNNING)
            
            await self._push_to_graphiti(document_path, chunks, postgres_id)
            self.logger.info("[Step 7/8] ✓ Chunks pushed to Graphiti")
            
            if job:
                # Mark embeddings as completed and Neo4j storage as completed
                job.update_pipeline_step(postgres_id, PipelineStep.GENERATE_EMBEDDINGS, StepStatus.COMPLETED)
                job.update_pipeline_step(postgres_id, PipelineStep.STORE_NEO4J, StepStatus.COMPLETED)
        except Exception as e:
            self.logger.error(f"[Step 7/8] ✗ Failed to push to Graphiti: {str(e)}")
            
            # Cleanup: Remove any partial data from Neo4j to avoid orphaned chunks
            try:
                self.logger.info(f"[Cleanup] Removing partial data from Neo4j for document {postgres_id}")
                cleanup_success = await self.graphiti_service.delete_document_by_group_id(str(postgres_id))
                if cleanup_success:
                    self.logger.info(f"[Cleanup] ✓ Successfully removed partial data for document {postgres_id}")
                else:
                    self.logger.warning(f"[Cleanup] ⚠️ Could not remove partial data for document {postgres_id}")
            except Exception as cleanup_error:
                self.logger.error(f"[Cleanup] ✗ Failed to cleanup partial data for document {postgres_id}: {str(cleanup_error)}")
            
            if job:
                from src.services.ingestion import PipelineStep, StepStatus
                # Determine which step failed
                error_msg = str(e).lower()
                if "embedding" in error_msg:
                    job.update_pipeline_step(postgres_id, PipelineStep.GENERATE_EMBEDDINGS, StepStatus.FAILED, str(e))
                else:
                    job.update_pipeline_step(postgres_id, PipelineStep.STORE_NEO4J, StepStatus.FAILED, str(e))
            raise

        # Update document status to ACTIVE after successful ingestion
        try:
            self.logger.info("[Step 8/8] Updating document status to ACTIVE")
            if job:
                from src.services.ingestion import PipelineStep, StepStatus
                job.update_pipeline_step(postgres_id, PipelineStep.UPDATE_DATABASE, StepStatus.RUNNING)
            
            await self.document_repo.update_document_status(postgres_id, "ACTIVE")
            self.logger.info("[Step 8/8] ✓ Document status updated to ACTIVE")
            
            if job:
                job.update_pipeline_step(postgres_id, PipelineStep.UPDATE_DATABASE, StepStatus.COMPLETED)
        except Exception as e:
            self.logger.error(f"[Step 8/8] ✗ Failed to update document status: {str(e)}")
            if job:
                from src.services.ingestion import PipelineStep, StepStatus
                job.update_pipeline_step(postgres_id, PipelineStep.UPDATE_DATABASE, StepStatus.FAILED, str(e))
            # Don't raise - ingestion was successful, just status update failed
        
        self.logger.info(f"✅ Document {postgres_id} successfully ingested (all 8 steps completed)")

    def _process_paths(self, document_path: str) -> tuple[str, str]:
        """Converts document path to Graph API path and extracts clean filename.

        Args:
            document_path: Original document path from database.

        Returns:
            Tuple of (graph_api_path, filename_without_extension)
        """
        # Ensure document_path is a string (convert if it's an integer ID)
        if not isinstance(document_path, str):
            raise ValueError(f"document_path must be a string, got {type(document_path).__name__}: {document_path}")
        
        # Use Graph API path for downloading (doesn't include site root)
        graph_api_path = self.sp_manager.to_graph_api_path(document_path)
        filename_without_ext = os.path.splitext(document_path)[0].split('/')[-1]
        return graph_api_path, filename_without_ext


    async def _download_document(self, sharepoint_path: str) -> bytes:
        """Downloads document from SharePoint using disk-based streaming for large files.

        Args:
            sharepoint_path: Path in SharePoint.

        Returns:
            File content as bytes.
        """
        self.logger.info(f"Downloading document from SharePoint: {sharepoint_path}")
        # Use disk-based streaming for files larger than configured threshold (default 50MB)
        # This prevents memory issues with large PowerPoint/video files
        large_file_threshold = int(os.getenv("LARGE_FILE_THRESHOLD_MB", "50"))
        return await self.sp_manager.download_file(
            sharepoint_path,
            use_disk_for_large_files=True,
            large_file_threshold_mb=large_file_threshold
        )

    async def _convert_if_needed(self, file_content: bytes, document_path: str) -> tuple[bytes, str | None]:
        """Converts large Office files to PDF to avoid Azure Document Intelligence size limits.
        Azure Document Intelligence has a limit of ~200MB for analysis.
        
        Args:
            file_content: Original file content as bytes.
            document_path: Path to determine file extension.
            
        Returns:
            Tuple of (converted_content, original_format) or (original_content, None) if no conversion needed
            
        Raises:
            RuntimeError: If file is too large to process even with conversion
        """
        # Extract file extension
        file_extension = document_path.lower().split('.')[-1] if '.' in document_path else ''
        
        # Azure Document Intelligence size limit is approximately 200MB
        AZURE_DI_SIZE_LIMIT_MB = int(os.getenv("AZURE_DI_SIZE_LIMIT_MB", "200"))
        # Maximum file size for conversion attempt (1GB)
        MAX_CONVERTIBLE_SIZE_MB = int(os.getenv("MAX_CONVERTIBLE_SIZE_MB", "1000"))
        file_size_mb = len(file_content) / 1024 / 1024
        
        # Note: Size limit check now happens in ingest_document before download
        # This is here as an additional safety check
        if file_size_mb > MAX_CONVERTIBLE_SIZE_MB:
            error_msg = (
                f"File size ({file_size_mb:.2f} MB) exceeds maximum processable size "
                f"({MAX_CONVERTIBLE_SIZE_MB} MB). Document should have been filtered earlier."
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Check if file needs conversion
        convertible_formats = ['pptx', 'ppt', 'docx', 'doc']
        needs_conversion = (
            file_extension in convertible_formats and 
            file_size_mb > AZURE_DI_SIZE_LIMIT_MB
        )
        
        if needs_conversion:
            self.logger.info(
                f"File size ({file_size_mb:.2f} MB) exceeds Azure Document Intelligence limit "
                f"({AZURE_DI_SIZE_LIMIT_MB} MB). Converting {file_extension.upper()} to PDF..."
            )
            try:
                converted_content = convert_office_to_pdf(file_content, file_extension)
                converted_size_mb = len(converted_content) / 1024 / 1024
                
                # Check if converted file is still too large
                if converted_size_mb > AZURE_DI_SIZE_LIMIT_MB:
                    self.logger.warning(
                        f"Converted PDF ({converted_size_mb:.2f} MB) still exceeds limit "
                        f"({AZURE_DI_SIZE_LIMIT_MB} MB). Document is too complex/large to process."
                    )
                    raise RuntimeError(
                        f"Converted PDF ({converted_size_mb:.2f} MB) exceeds processing limit. "
                        "Document is too complex."
                    )
                
                self.logger.info(
                    f"Successfully converted {file_extension.upper()} to PDF. "
                    f"Size reduced from {file_size_mb:.2f} MB to {converted_size_mb:.2f} MB"
                )
                return converted_content, file_extension
            except Exception as conv_error:
                self.logger.error(
                    f"Failed to convert {file_extension.upper()} to PDF: {str(conv_error)}. "
                    f"Skipping document."
                )
                # Re-raise to skip this document
                raise RuntimeError(f"Conversion failed: {str(conv_error)}")
        
        # No conversion needed
        return file_content, None


    async def _extract_text_async(self, file_content: bytes):
        """
        Extracts plain text using the async Azure Document Intelligence client.

        Args:
            file_content: File content as bytes.

        Returns:
            text_content: Extracted text.
            result: Full analysis result object.
        """
        poller = await self.async_azure_di_client.begin_analyze_document(
            model_id="prebuilt-read",
            body=file_content,
            content_type="application/octet-stream"
        )

        result = await poller.result()
        text_content = result.content

        self.logger.info("Text extraction (prebuilt-read) completed (async).")
        return text_content, result

    async def _chunk_output(self, text: str) -> List[Dict[str, Any]]:
        """
        Splits plain text into chunks using RecursiveCharacterTextSplitter.
        Produces chunks of ~2000 chars with 400-char overlap.
        Returns a list of {"id": int, "content": str}.
        """

        # Create splitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=400,
        )

        # Direct chunking of the input text
        chunks = text_splitter.split_text(text)

        logging.info(f"Generated {len(chunks)} chunks via RecursiveCharacterTextSplitter")
        for c in chunks:
            logging.info(f"Chunk length: {len(c)}")

        # Build the final output structure
        output = [
            {"id": i, "content": chunk}
            for i, chunk in enumerate(chunks)
        ]

        self.logger.info(
            f"Generated {len(output)} final chunks using RecursiveCharacterTextSplitter"
        )

        return output

    async def _push_to_graphiti(self, sharepoint_path: str, chunks: List[Dict[str, Any]], postgres_id: int):
        graphiti_doc = {
            "title": sharepoint_path,
            "chunks": [chunk["content"] for chunk in chunks]
        }

        await self.graphiti_service.ingest_documents(
            documents=[graphiti_doc],
            postgres_id=postgres_id  
        )

        self.logger.info("Chunks pushed to Graphiti.")


    def eliminar_figuras_repetidas(self, texto) -> str:
        """
        Docstring for eliminar_figuras_repetidas
        
        Args:
            texto: Markdown text.

        Returns:
           texto:  Filtered text with repeated <figure> tags removed.
        """
        # Patrón para detectar etiquetas <figure> con su contenido
        patron_figura = r"(<figure>[\s\S]*?<\/figure>)"
        
        # Encontrar todas las figuras completas en el documento
        figuras = re.findall(patron_figura, texto)
        
        # Contar cuántas veces aparece cada figura
        contador_figuras = Counter(figuras)
        
        # Eliminar las figuras que se repiten más de una vez
        for figura, conteo in contador_figuras.items():
            if conteo > 1:
                # Reemplazar todas las instancias de la figura repetida
                texto = re.sub(re.escape(figura), "", texto)
        
        return texto
    
    def detect_and_remove_headers_footers(self, content: str, min_repetitions: int = 7) -> str:
        """
        Removes repeated header/footer lines based purely on text frequency.
        No page count required.
        
        Args:
            content: Markdown text.
            min_repetitions: Minimum number of times a line must repeat to be removed.
        
        Returns:
            Filtered text with repeated headers/footers removed.
        """

        # Patterns for lines that must NOT be removed even if repeated
        special_patterns = [
            r":selected:", r":unselected:",
            r"\bs[ií]\b", r"\bno(n?)\b",
            r"procede"
        ]
        special_regex = re.compile("|".join(special_patterns), re.IGNORECASE)

        lines = content.split("\n")
        counter = Counter(lines)

        # Identify repeated lines NOT matching protected patterns
        repeated_lines = [
            line for line, count in counter.items()
            if count >= min_repetitions and not special_regex.search(line.lower())
        ]

        # Remove them
        filtered = "\n".join(line for line in lines if line not in repeated_lines)

        return filtered
    
    def detect_and_remove_duplicate_tables(self, markdown_text: str, min_occurrences: int = 3) -> str:
        """
        Removes markdown tables that appear multiple times in the document.
        Pure text-based logic — no page numbers required.
        
        Args:
            markdown_text: Extracted markdown text.
            min_occurrences: Number of occurrences needed to consider a table duplicated.
        
        Returns:
            Markdown text with duplicated tables removed.
        """

        tables = self.extract_tables(markdown_text)
        table_counter = Counter(tables)

        # Identify duplicated table blocks
        duplicated_tables = [tbl for tbl, count in table_counter.items() if count >= min_occurrences]

        # Remove them from the document
        cleaned_text = markdown_text
        for tbl in duplicated_tables:
            cleaned_text = cleaned_text.replace(tbl, "")

        return cleaned_text
    
    def extract_tables(self, markdown_text: str) -> list[str]:
        """
        Extracts markdown tables (| a | b | ...) from text.
        Looks for contiguous table-like blocks.
        """

        lines = markdown_text.split("\n")
        tables = []
        current_table = []

        for line in lines:
            if line.strip().startswith("|") and line.strip().endswith("|"):
                current_table.append(line)
            else:
                if current_table:
                    tables.append("\n".join(current_table))
                    current_table = []
        if current_table:
            tables.append("\n".join(current_table))

        return tables

    def _merge_small_chunks(self, chunks: List[str], min_size: int = 200) -> List[str]:
        """
        Merge chunks smaller than min_size into the previous chunk.
        
        Args:
            chunks: List of text chunks.
            min_size: Minimum size threshold.

        Returns:
            Merged list of chunks.
        """
        if not chunks:
            return []

        merged = [chunks[0]]

        for chunk in chunks[1:]:
            if len(chunk) < min_size:
                # merge into previous
                merged[-1] = merged[-1].rstrip() + "\n" + chunk.lstrip()
            else:
                merged.append(chunk)

        return merged
    
    def _sliding_window_chunks(self, text: str, size: int = 1000, overlap: int = 200) -> List[str]:
        """Create sliding-window text chunks with a given size and overlap."""
        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + size, text_len)
            chunk = text[start:end].strip()
            chunks.append(chunk)
            if end == text_len:
                break
            start = start + size - overlap

        return chunks


# Alias for backward compatibility and service usage
Neo4jIngestionService = Neo4jIngestion
    
