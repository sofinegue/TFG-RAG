from pydantic import BaseModel, Field
from typing import List, Optional

class DocStatus:
    """Estados del documento"""
    PENDING = 1
    PROCESSING = 2
    PROCESSED = 3

class BlobRef(BaseModel):
    blob_name: str
    filename: str
    size: int
    content_type: Optional[str] = None

class Documento(BaseModel):
    id: str
    status: int = DocStatus.PENDING
    doc_id: str
    doc_nombre: str

class DocumentsToProcessREQ(BaseModel):
    """Request para procesar documentos"""
    id_llamada: str
    id_caso: str
    usuario: Optional[str] = None
    equipo: str
    get_formula: bool = False
    documentos: List[Documento]