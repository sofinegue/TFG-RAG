"""
Servicio para gestionar Vector Stores en Azure AI Projects
Permite subir documentos y gestionarlos via API
VERSIÓN CON SOPORTE MULTITHREADING
"""
import os
import time
from typing import List, Optional, Dict, Any
from pathlib import Path
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


class VectorStoreService:
    """
    Servicio para gestionar Vector Stores de Azure AI Projects
    """
    
    def __init__(
        self,
        project_endpoint: str,
        credential = None
    ):
        """
        Inicializa el servicio de Vector Store
        
        Args:
            project_endpoint: Endpoint del proyecto de Azure AI
            credential: Credencial de Azure (por defecto DefaultAzureCredential)
        """
        if credential is None:
            credential = DefaultAzureCredential()
        
        self.project = AIProjectClient(
            credential=credential,
            endpoint=project_endpoint
        )
        self.endpoint = project_endpoint
        self._lock = threading.Lock()  # Para thread-safety en prints
    
    def create_vector_store(self, name: str) -> str:
        """
        Crea un nuevo vector store
        
        Args:
            name: Nombre del vector store
            
        Returns:
            ID del vector store creado
        """
        try:
            vector_store = self.project.agents.vector_stores.create_and_poll(
                name=name
            )
            print(f"✅ Vector Store creado: {vector_store.id}")
            return vector_store.id
        except Exception as e:
            print(f"❌ Error creando vector store: {e}")
            raise
    
    def upload_file(self, file_path: str) -> str:
        """
        Sube un archivo a Azure AI Projects
        
        Args:
            file_path: Ruta al archivo local
            
        Returns:
            ID del archivo subido
        """
        try:
            with open(file_path, "rb") as file:
                uploaded_file = self.project.agents.files.upload_and_poll(
                    file=file,
                    purpose="assistants"
                )
            
            filename = Path(file_path).name
            # Print thread-safe
            with self._lock:
                print(f"📤 Archivo subido: {filename} -> {uploaded_file.id}")
            return uploaded_file.id
            
        except Exception as e:
            with self._lock:
                print(f"❌ Error subiendo archivo {file_path}: {e}")
            raise
    
    def add_file_to_vector_store(
        self,
        vector_store_id: str,
        file_id: str
    ) -> Dict[str, Any]:
        """
        Añade un archivo ya subido a un vector store
        
        Args:
            vector_store_id: ID del vector store
            file_id: ID del archivo
            
        Returns:
            Información del archivo en el vector store
        """
        try:
            vector_store_file = self.project.agents.vector_store_files.create_and_poll(
                vector_store_id=vector_store_id,
                file_id=file_id
            )
            
            with self._lock:
                print(f"✅ Archivo {file_id} añadido al vector store")
            
            return {
                "id": vector_store_file.id,
                "vector_store_id": vector_store_id,
                "status": vector_store_file.status
            }
            
        except Exception as e:
            with self._lock:
                print(f"❌ Error añadiendo archivo {file_id} al vector store: {e}")
            raise
    
    def upload_and_add_file(
        self,
        vector_store_id: str,
        file_path: str
    ) -> Dict[str, Any]:
        """
        Sube un archivo y lo añade al vector store en un solo paso
        
        Args:
            vector_store_id: ID del vector store
            file_path: Ruta al archivo local
            
        Returns:
            Información del proceso
        """
        # 1. Subir archivo
        file_id = self.upload_file(file_path)
        
        # 2. Añadir al vector store con retry si falla
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = self.add_file_to_vector_store(vector_store_id, file_id)
                return result
            except Exception as e:
                if attempt < max_retries - 1:
                    with self._lock:
                        print(f"⚠️  Reintentando añadir archivo {file_id} (intento {attempt + 2}/{max_retries})...")
                    time.sleep(2 ** attempt)  # Backoff exponencial
                else:
                    raise
    
    def _upload_single_file_worker(
        self,
        vector_store_id: str,
        file_path: str
    ) -> Dict[str, Any]:
        """
        Worker para subir un archivo individual (usado en multithreading)
        
        Args:
            vector_store_id: ID del vector store
            file_path: Ruta al archivo
            
        Returns:
            Resultado de la operación
        """
        filename = Path(file_path).name
        
        try:
            result = self.upload_and_add_file(
                vector_store_id=vector_store_id,
                file_path=file_path
            )
            return {
                "file_path": file_path,
                "filename": filename,
                "success": True,
                **result
            }
        except Exception as e:
            return {
                "file_path": file_path,
                "filename": filename,
                "success": False,
                "error": str(e)
            }
    
    def upload_multiple_files(
        self,
        vector_store_id: str,
        file_paths: List[str],
        show_progress: bool = True,
        max_workers: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Sube múltiples archivos a un vector store con multithreading
        
        Args:
            vector_store_id: ID del vector store
            file_paths: Lista de rutas a archivos
            show_progress: Mostrar barra de progreso
            max_workers: Número máximo de hilos concurrentes (default: 5)
            
        Returns:
            Lista con información de cada archivo subido
        """
        results = []
        
        print(f"\n📦 Subiendo {len(file_paths)} archivos al vector store...")
        print(f"⚡ Usando {max_workers} hilos concurrentes\n")
        
        # Usar ThreadPoolExecutor para subidas concurrentes
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Crear futures para todas las tareas
            future_to_file = {
                executor.submit(
                    self._upload_single_file_worker,
                    vector_store_id,
                    file_path
                ): file_path
                for file_path in file_paths
            }
            
            # Procesar resultados conforme se completan
            if show_progress:
                with tqdm(total=len(file_paths), desc="Subiendo archivos") as pbar:
                    for future in as_completed(future_to_file):
                        result = future.result()
                        results.append(result)
                        
                        # Actualizar descripción con el último archivo procesado
                        filename = result['filename'][:30]
                        pbar.set_description(f"Subiendo: {filename}")
                        pbar.update(1)
            else:
                for future in as_completed(future_to_file):
                    results.append(future.result())
        
        # Resumen
        successful = sum(1 for r in results if r.get("success"))
        print(f"\n{'='*60}")
        print(f"✅ Subidos correctamente: {successful}/{len(file_paths)}")
        if successful < len(file_paths):
            failed = len(file_paths) - successful
            print(f"❌ Fallidos: {failed}")
        print(f"{'='*60}\n")
        
        return results
    
    def list_vector_stores(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Lista todos los vector stores
        
        Args:
            limit: Número máximo de vector stores a listar
            
        Returns:
            Lista de vector stores
        """
        try:
            vector_stores = self.project.agents.vector_stores.list(limit=limit)
            
            vs_list = []
            for vs in vector_stores:
                vs_list.append({
                    "id": vs.id,
                    "name": vs.name,
                    "status": vs.status,
                    "file_counts": vs.file_counts,
                    "created_at": vs.created_at
                })
            
            return vs_list
            
        except Exception as e:
            print(f"❌ Error listando vector stores: {e}")
            raise
    
    def list_vector_store_files(
        self,
        vector_store_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Lista los archivos en un vector store
        
        Args:
            vector_store_id: ID del vector store
            limit: Número máximo de archivos a listar
            
        Returns:
            Lista de archivos
        """
        try:
            files = self.project.agents.vector_store_files.list(
                vector_store_id=vector_store_id,
                limit=limit
            )
            
            file_list = []
            for file in files:
                file_list.append({
                    "id": file.id,
                    "status": file.status,
                    "created_at": file.created_at
                })
            
            return file_list
            
        except Exception as e:
            print(f"❌ Error listando archivos: {e}")
            raise
    
    def delete_file_from_vector_store(
        self,
        vector_store_id: str,
        file_id: str
    ) -> bool:
        """
        Elimina un archivo de un vector store
        
        Args:
            vector_store_id: ID del vector store
            file_id: ID del archivo
            
        Returns:
            True si se eliminó correctamente
        """
        try:
            self.project.agents.vector_store_files.delete(
                vector_store_id=vector_store_id,
                file_id=file_id
            )
            print(f"🗑️ Archivo {file_id} eliminado del vector store")
            return True
        except Exception as e:
            print(f"❌ Error eliminando archivo: {e}")
            return False
    
    def get_vector_store_info(self, vector_store_id: str) -> Dict[str, Any]:
        """
        Obtiene información de un vector store
        
        Args:
            vector_store_id: ID del vector store
            
        Returns:
            Información del vector store
        """
        try:
            vs = self.project.agents.vector_stores.retrieve(vector_store_id)
            
            return {
                "id": vs.id,
                "name": vs.name,
                "status": vs.status,
                "file_counts": vs.file_counts,
                "created_at": vs.created_at
            }
        except Exception as e:
            print(f"❌ Error obteniendo info del vector store: {e}")
            raise
    
    def scan_folder(self, folder_path: str, extensions: List[str] = None) -> List[str]:
        """
        Escanea una carpeta y retorna todos los archivos con las extensiones especificadas
        
        Args:
            folder_path: Ruta a la carpeta
            extensions: Lista de extensiones permitidas (ej: ['.pdf', '.docx', '.txt'])
                       Si es None, incluye todas las extensiones
            
        Returns:
            Lista de rutas completas a archivos
        """
        if extensions is None:
            extensions = [
                '.pdf', '.docx', '.doc', '.txt', '.md', 
                '.json', '.csv', '.xlsx', '.pptx', '.html'
            ]
        
        folder = Path(folder_path)
        if not folder.exists():
            raise FileNotFoundError(f"La carpeta no existe: {folder_path}")
        
        if not folder.is_dir():
            raise NotADirectoryError(f"No es una carpeta: {folder_path}")
        
        files = []
        for ext in extensions:
            files.extend(folder.rglob(f"*{ext}"))
        
        return [str(f) for f in files]