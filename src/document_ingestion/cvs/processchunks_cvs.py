"""
src.document_ingestion.cvs.doc_chunking_cvs
Funciones para generar chunks semánticos de CVs a partir de JSON estructurado
"""
from __future__ import annotations

import tiktoken

from typing import Any

from src.config import config


encoding = tiktoken.encoding_for_model(config.azure_openai_emb_name)
CHUNK_TYPES: list[str] = ["experience", "education", "skills"]

class CVProcessor:
    """Procesador de datos estructurados de CV con generación de chunks semánticos
    Convierte un diccionario JSON de CV en 3 chunks optimizados para RAG,
    preservando relaciones entre habilidades, roles y formación
    """

    def __init__(self) -> None:
        self.nombre_apellidos: str = ""
        self.puesto: str = ""
        self.experiencia: list[str] = []
        self.estudios: list[str] = []
        self.hard_skills: list[str] = []
        self.soft_skills: list[str] = []
        self.otros: list[str] = []

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CVProcessor":
        """
        Crea una instancia de CVProcessor a partir de un diccionario
        Acepta tanto "hard_skills" como "hard skills" (con espacio)
        Args:
            d (dict[str, Any]): Diccionario con datos del CV
        Returns:
            CVProcessor: Instancia con datos cargados
        """
        inst = cls()
        inst.nombre_apellidos = d.get("nombre_apellidos", "")
        inst.puesto = d.get("puesto", "")
        inst.experiencia = d.get("experiencia", [])
        inst.estudios = d.get("estudios", [])
        inst.hard_skills = d.get("hard_skills") or d.get("hard skills", [])
        inst.soft_skills = d.get("soft_skills") or d.get("soft skills", [])
        inst.otros = d.get("otros", [])
        return inst

    def generate_experience_chunk(self) -> dict[str, Any]:
        """
        Genera el chunk de experiencia profesional. El campo "content" incluye: puesto, experiencia, otros
        Returns:
            dict[str, Any]: Chunk con tipo "experience", contenido formateado y metadatos relevantes
        """
        puesto_text = f"PUESTO: {self.puesto}" if self.puesto else ""
        exp_text = "\n".join(f"• {item}" for item in self.experiencia) if self.experiencia else "• Sin experiencia registrada"
        otros_text = "\n".join(f"• {item}" for item in self.otros) if self.otros else ""
        # years_exp = self.calculate_years_of_experience()
        # domains = self.get_skill_domains()
        content = f"NOMBRE_APELLIDOS: {self.nombre_apellidos}\n{puesto_text}\n\nEXPERIENCIA:\n{exp_text}"
        if otros_text:
            content += f"\n\nOTROS:\n{otros_text}"
        metadata = {
            "chunk_type": "experience",
            "nombre_apellidos": self.nombre_apellidos,
            "puesto": self.puesto,
            "experiencia": self.experiencia,
            "otros": self.otros,
            # "years_of_experience": years_exp,
        }
        return {"type": "experience", "content": content, "metadata": metadata}

    def generate_education_chunk(self) -> dict[str, Any]:
        """
        Genera el chunk de formación académica. El campo "content" incluye: estudios, hard_skills
        Returns:
            dict[str, Any]: Chunk con tipo "education", contenido formateado y metadatos relevantes
        """
        edu_text = "\n".join(f"• {item}" for item in self.estudios) if self.estudios else "• Sin formación registrada"
        otros_text = "\n".join(f"• {item}" for item in self.otros) if self.otros else ""
        content = f"NOMBRE_APELLIDOS: {self.nombre_apellidos}\n\nESTUDIOS:\n{edu_text}"
        if otros_text:
            content += f"\n\nOTROS:\n{otros_text}"
        metadata = {
            "chunk_type": "education",
            "nombre_apellidos": self.nombre_apellidos,
            "estudios": self.estudios,
            "otros": self.otros,
        }
        return {"type": "education", "content": content, "metadata": metadata}

    def generate_skills_chunk(self) -> dict[str, Any]:
        """
        Genera el chunk de competencias. El campo "content" incluye: hard_skills, soft_skills, otros
        Returns:
            dict[str, Any]: Chunk con tipo "skills", contenido formateado y metadatos relevantes
        """
        hard_text = ", ".join(self.hard_skills) if self.hard_skills else "Sin hard skills registradas"
        soft_text = ", ".join(self.soft_skills) if self.soft_skills else "Sin soft skills registradas"
        content = (
            f"NOMBRE_APELLIDOS: {self.nombre_apellidos}\n"
            f"POSICIÓN OBJETIVO: {self.puesto}\n\n"
            f"HARD_SKILLS:\n{hard_text}\n\n"
            f"SOFT_SKILLS:\n{soft_text}"
        )
        metadata = {
            "chunk_type": "skills",
            "nombre_apellidos": self.nombre_apellidos,
            "puesto": self.puesto,
            "hard_skills": self.hard_skills,
            "soft_skills": self.soft_skills,
        }
        return {"type": "skills", "content": content, "metadata": metadata}

    def generate_semantic_chunks(self) -> list[dict[str, Any]]:
        """
        Genera los 3 chunks semánticos del CV (experiencia, formación, skills)
        Returns:
            list[dict[str, Any]]: lista de chunks semánticos de un CV
        """
        return [
            self.generate_experience_chunk(),
            self.generate_education_chunk(),
            self.generate_skills_chunk(),
        ]

    def get_global_metadata(self, language: str = "es") -> dict[str, Any]:
        """
        Metadatos globales aplicables a todos los chunks del mismo CV
        Args:
            language (str): Idioma de los metadatos. Por defecto es "es"
        Returns:
            dict[str, Any]: Diccionario con metadatos globales del CV
        """
        return {
            "nombre_apellidos": self.nombre_apellidos,
            "puesto": self.puesto,
            "language": language,
        }
