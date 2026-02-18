"""
Estados de procesamiento de documentos
"""
from enum import Enum

class DocStatus(Enum):
    PENDING = 1
    PROCESSING = 2
    PROCESSED = 3