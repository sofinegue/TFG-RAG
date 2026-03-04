"""
src.document_ingestion.cvs.doc_chunking_cvs

Funciones para generar chunks semánticos de CVs a partir de JSON estructurado.
"""
from __future__ import annotations

import re
import tiktoken
from typing import Any, Dict, List

from src.config import config


# Tokenizador para contar tokens
encoding = tiktoken.encoding_for_model(config.azure_openai_emb_name)

# Tipos de chunk
CHUNK_TYPES: List[str] = ["experience", "education", "skills"]


# ===========================================================================
# CVProcessor — generación de chunks semánticos
# ===========================================================================

class CVProcessor:
    """Procesador de datos estructurados de CV con generación de chunks semánticos.

    Convierte un diccionario JSON de CV en 3 chunks optimizados para RAG,
    preservando relaciones entre habilidades, roles y formación.
    """

    def __init__(self) -> None:
        self.nombre_apellidos: str = ""
        self.puesto: str = ""
        self.experiencia: List[str] = []
        self.estudios: List[str] = []
        self.hard_skills: List[str] = []
        self.soft_skills: List[str] = []
        self.otros: List[str] = []

    # ── Constructores ──────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CVProcessor":
        """Crea una instancia de CVProcessor a partir de un diccionario.

        Acepta tanto ``"hard_skills"`` como ``"hard skills"`` (con espacio).
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

    # ── Metadatos derivados ────────────────────────────────────────────────

    def calculate_years_of_experience(self) -> int:
        """Estima años totales de experiencia a partir de rangos de fechas."""
        years = 0
        for entry in self.experiencia:
            matches = re.findall(r'(\d{4})\s*[-–]\s*(\d{4})', entry)
            for start_str, end_str in matches:
                try:
                    diff = int(end_str) - int(start_str)
                    years = max(years, diff)
                except ValueError:
                    pass
        return years

    # def get_skill_domains(self) -> List[str]:
    #     """Extrae dominios tecnológicos a partir de experiencia y hard_skills."""
    #     domain_keywords = {
    #         "backend":  ["python", "java", "node", "django", "spring", "fastapi", ".net", "c#"],
    #         "frontend": ["react", "vue", "angular", "javascript", "typescript", "css", "html"],
    #         "data":     ["sql", "spark", "hadoop", "analytics", "tableau", "power bi", "etl"],
    #         "devops":   ["docker", "kubernetes", "jenkins", "gitlab", "aws", "azure", "ci/cd"],
    #         "mobile":   ["ios", "android", "flutter", "react native", "swift", "kotlin"],
    #         "ai/ml":    ["machine learning", "deep learning", "nlp", "tensorflow", "pytorch"],
    #         "cloud":    ["aws", "azure", "gcp", "cloud", "serverless"],
    #         "security": ["cybersecurity", "ciberseguridad", "owasp", "pentesting", "soc"],
    #     }
    #     combined = " ".join(self.experiencia + self.hard_skills).lower()
    #     return sorted({
    #         domain
    #         for domain, kws in domain_keywords.items()
    #         if any(kw in combined for kw in kws)
    #     })

    # def _detect_education_levels(self) -> List[str]:
    #     """Detecta niveles educativos a partir de los estudios."""
    #     edu_text = " ".join(self.estudios).lower()
    #     level_keywords = {
    #         "doctorate":   ["doctorado", "phd", "ph.d", "dr."],
    #         "master":      ["máster", "master", "mba", "postgrado", "postgraduate"],
    #         "degree":      ["licenciatura", "degree", "grado", "ingeniería", "bachelor", "engineering"],
    #         "vocational":  ["formación profesional", "fp", "técnico", "vocational", "cfgs"],
    #     }
    #     return sorted({
    #         level
    #         for level, kws in level_keywords.items()
    #         if any(kw in edu_text for kw in kws)
    #     })

    # ── Generación de chunks ──────────────────────────────────────────────

    def generate_experience_chunk(self) -> Dict[str, Any]:
        """Genera el chunk de experiencia profesional.
        
        sectionContent incluye: puesto, experiencia, otros.
        """
        puesto_text = f"PUESTO: {self.puesto}" if self.puesto else ""
        exp_text = "\n".join(f"• {item}" for item in self.experiencia) if self.experiencia else "• Sin experiencia registrada"
        otros_text = "\n".join(f"• {item}" for item in self.otros) if self.otros else ""
        years_exp = self.calculate_years_of_experience()
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
            "years_of_experience": years_exp,
            # "skill_domains": domains,
        }

        return {"type": "experience", "content": content, "metadata": metadata}

    def generate_education_chunk(self) -> Dict[str, Any]:
        """Genera el chunk de formación académica.
        
        sectionContent incluye: estudios, hard_skills.
        """
        edu_text = "\n".join(f"• {item}" for item in self.estudios) if self.estudios else "• Sin formación registrada"
        otros_text = "\n".join(f"• {item}" for item in self.otros) if self.otros else ""
        hard_text = ", ".join(self.hard_skills) if self.hard_skills else ""
        # levels = self._detect_education_levels()

        content = f"NOMBRE_APELLIDOS: {self.nombre_apellidos}\n\nESTUDIOS:\n{edu_text}"
        if hard_text:
            content += f"\n\nHARD_SKILLS:\n{hard_text}"
        if otros_text:
            content += f"\n\nOTROS:\n{otros_text}"

        metadata = {
            "chunk_type": "education",
            "nombre_apellidos": self.nombre_apellidos,
            "estudios": self.estudios,
            "hard_skills": self.hard_skills,
            "otros": self.otros,
            # "education_levels": levels,
        }

        return {"type": "education", "content": content, "metadata": metadata}

    def generate_skills_chunk(self) -> Dict[str, Any]:
        """Genera el chunk de competencias.
        
        sectionContent incluye: hard_skills, soft_skills, otros.
        """
        hard_text = ", ".join(self.hard_skills) if self.hard_skills else "Sin hard skills registradas"
        soft_text = ", ".join(self.soft_skills) if self.soft_skills else "Sin soft skills registradas"
        otros_text = "\n".join(f"• {item}" for item in self.otros) if self.otros else ""

        content = (
            f"NOMBRE_APELLIDOS: {self.nombre_apellidos}\n"
            f"POSICIÓN OBJETIVO: {self.puesto}\n\n"
            f"HARD_SKILLS:\n{hard_text}\n\n"
            f"SOFT_SKILLS:\n{soft_text}"
        )
        if otros_text:
            content += f"\n\nOTROS:\n{otros_text}"

        metadata = {
            "chunk_type": "skills",
            "nombre_apellidos": self.nombre_apellidos,
            "puesto": self.puesto,
            "hard_skills": self.hard_skills,
            "soft_skills": self.soft_skills,
            "otros": self.otros,
        }

        return {"type": "skills", "content": content, "metadata": metadata}

    def generate_semantic_chunks(self) -> List[Dict[str, Any]]:
        """Genera los 3 chunks semánticos del CV (experiencia, formación, skills)."""
        return [
            self.generate_experience_chunk(),
            self.generate_education_chunk(),
            self.generate_skills_chunk(),
        ]

    def get_global_metadata(self, language: str = "es") -> Dict[str, Any]:
        """Metadatos globales aplicables a todos los chunks del mismo CV."""
        return {
            "nombre_apellidos": self.nombre_apellidos,
            "puesto": self.puesto,
            "language": language,
            # "skill_domains": self.get_skill_domains(),
            "years_of_experience": self.calculate_years_of_experience(),
        }


