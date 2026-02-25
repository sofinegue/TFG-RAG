"""
CV chunking strategies and semantic chunk generation.

This module provides the CVProcessor class for converting structured CV JSON
into semantic chunks optimized for RAG retrieval.

Chunking Strategy
-----------------
Each CV is split into **3 semantic chunks** (rather than one monolithic chunk)
to improve vector search relevance:

1. **Experience Chunk** — Contains all professional experience with context
2. **Education Chunk** — Contains all formal education with technical details
3. **Skills Chunk** — Contains all hard and soft skills with proficiency hints

Each chunk is enriched with metadata extracted from the entire CV (name, position,
years of experience, skill domains, etc.) to improve filtering and recall during
vector search.
"""

import json
import os
from typing import List, Dict, Any, Optional


class CVProcessor:
    """Structured CV data processor with semantic chunk generation.
    
    This class handles conversion of CV JSON data into semantically meaningful
    chunks suitable for RAG retrieval, while preserving relationships between
    skills, roles, and educational background.
    
    Attributes
    ----------
    nombre_apellidos : str
        Full name of the person
    puesto : str
        Current or target job position
    experiencia : List[str]
        Professional experience entries (roles, companies, durations)
    estudios : List[str]
        Educational background (degrees, institutions, fields)
    hard_skills : List[str]
        Technical skills (languages, tools, frameworks)
    soft_skills : List[str]
        Soft skills (communication, leadership, creativity)
    otros : List[str]
        Additional information (certifications, languages, hobbies)
    """

    def __init__(self):
        self.nombre_apellidos: str = ""
        self.puesto: str = ""
        self.experiencia: List[str] = []
        self.estudios: List[str] = []
        self.hard_skills: List[str] = []
        self.soft_skills: List[str] = []
        self.otros: List[str] = []

    def calculate_years_of_experience(self) -> int:
        """Estimate total years of experience from entries."""
        import re
        years = 0
        for entry in self.experiencia:
            # Look for patterns like "2020-2023", "5 años", etc.
            matches = re.findall(r'(\d{4})\s*[-–]\s*(\d{4}|\d+)', entry)
            for match in matches:
                try:
                    start = int(match[0])
                    end_str = match[1]
                    end = int(end_str) if len(end_str) == 4 else int(end_str)
                    years = max(years, end - start)
                except (ValueError, IndexError):
                    pass
        return years

    def get_skill_domains(self) -> List[str]:
        """Extract potential skill domains from experience and education."""
        domains = set()
        
        # Extract from experiencia
        keywords = {
            'backend': ['python', 'java', 'node', 'django', 'spring', 'fastapi'],
            'frontend': ['react', 'vue', 'angular', 'javascript', 'css', 'html'],
            'data': ['sql', 'python', 'spark', 'hadoop', 'analytics', 'tableau'],
            'devops': ['docker', 'kubernetes', 'jenkins', 'gitlab', 'aws', 'azure'],
            'mobile': ['ios', 'android', 'flutter', 'react native', 'swift'],
            'ai/ml': ['machine learning', 'deep learning', 'nlp', 'tensorflow', 'pytorch'],
        }
        
        combined_text = ' '.join(self.experiencia + self.hard_skills).lower()
        for domain, keywords_list in keywords.items():
            if any(kw in combined_text for kw in keywords_list):
                domains.add(domain)
        
        return sorted(list(domains))

    def generate_experience_chunk(self) -> Dict[str, Any]:
        """Generate experience-focused semantic chunk with enriched metadata.
        
        Returns
        -------
        dict
            Dictionary with keys:
            - 'type': 'experience'
            - 'content': Formatted experience text
            - 'metadata': Enriched with years, domains, position, name
        """
        exp_text = "\n".join([f"• {item}" for item in self.experiencia])
        years_exp = self.calculate_years_of_experience()
        domains = self.get_skill_domains()
        
        return {
            'type': 'experience',
            'content': (
                f"CANDIDATO: {self.nombre_apellidos}\n"
                f"POSICIÓN ACTUAL/OBJETIVO: {self.puesto}\n\n"
                f"EXPERIENCIA PROFESIONAL:\n{exp_text}"
            ),
            'name': self.nombre_apellidos,
            'position': self.puesto,
            'years_of_experience': years_exp,
            'skill_domains': domains,
            'num_experiences': len(self.experiencia),
        }

    def generate_education_chunk(self) -> Dict[str, Any]:
        """Generate education-focused semantic chunk with enriched metadata.
        
        Returns
        -------
        dict
            Dictionary with keys:
            - 'type': 'education'
            - 'content': Formatted education text
            - 'metadata': Enriched with field of study, levels
        """
        edu_text = "\n".join([f"• {item}" for item in self.estudios])
        
        # Extract education levels
        levels = set()
        level_keywords = {
            'doctorate': ['doctorado', 'phd', 'dr.'],
            'master': ['máster', 'master', 'mba', 'postgrado'],
            'degree': ['licenciatura', 'degree', 'grado', 'ingeniería'],
            'vocational': ['formación profesional', 'fp', 'técnico'],
        }
        for level, keywords in level_keywords.items():
            if any(kw in edu_text.lower() for kw in keywords):
                levels.add(level)
        
        return {
            'type': 'education',
            'content': (
                f"CANDIDATO: {self.nombre_apellidos}\n\n"
                f"FORMACIÓN ACADÉMICA:\n{edu_text}"
            ),
            'name': self.nombre_apellidos,
            'education_levels': sorted(list(levels)),
            'num_studies': len(self.estudios),
            'additional_info': self.otros,
        }

    def generate_skills_chunk(self) -> Dict[str, Any]:
        """Generate skills-focused semantic chunk with enriched metadata.
        
        Returns
        -------
        dict
            Dictionary with keys:
            - 'type': 'skills'
            - 'content': Formatted skills text
            - 'metadata': Enriched with skill counts, categories
        """
        hard_skills_text = ", ".join(self.hard_skills)
        soft_skills_text = ", ".join(self.soft_skills)
        
        return {
            'type': 'skills',
            'content': (
                f"CANDIDATO: {self.nombre_apellidos}\n"
                f"POSICIÓN OBJETIVO: {self.puesto}\n\n"
                f"COMPETENCIAS TÉCNICAS:\n{hard_skills_text}\n\n"
                f"COMPETENCIAS TRANSVERSALES:\n{soft_skills_text}"
            ),
            'name': self.nombre_apellidos,
            'position': self.puesto,
            'hard_skills': self.hard_skills,
            'soft_skills': self.soft_skills,
            'num_hard_skills': len(self.hard_skills),
            'num_soft_skills': len(self.soft_skills),
            'total_skills': len(self.hard_skills) + len(self.soft_skills),
        }

    def generate_semantic_chunks(self) -> List[Dict[str, Any]]:
        """Generate all 3 semantic chunks from CV data.
        
        Returns
        -------
        List[Dict[str, Any]]
            List of three dictionaries (experience, education, skills chunks),
            each with 'type', 'content', and 'metadata' keys.
        """
        return [
            self.generate_experience_chunk(),
            self.generate_education_chunk(),
            self.generate_skills_chunk(),
        ]

    def get_global_metadata(self, language: str = "es") -> Dict[str, Any]:
        """Generate global metadata for the entire CV profile.
        
        Parameters
        ----------
        language : str
            ISO 639-1 language code (default: "es")
        
        Returns
        -------
        dict
            Global metadata applicable to all chunks from this CV
        """
        return {
            'name': self.nombre_apellidos,
            'position': self.puesto,
            'language': language,
            'skill_domains': self.get_skill_domains(),
            'years_of_experience': self.calculate_years_of_experience(),
            'total_hard_skills': len(self.hard_skills),
            'total_soft_skills': len(self.soft_skills),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CVProcessor":
        """Create a CVProcessor instance from a raw dictionary.
        
        Parameters
        ----------
        d : dict
            Dictionary with CV data (expected keys: nombre_apellidos, puesto,
            experiencia, estudios, hard_skills, soft_skills, otros)
        
        Returns
        -------
        CVProcessor
            Initialized processor instance
        """
        inst = cls()
        inst.nombre_apellidos = d.get("nombre_apellidos", "")
        inst.puesto = d.get("puesto", "")
        inst.experiencia = d.get("experiencia", [])
        inst.estudios = d.get("estudios", [])
        inst.hard_skills = d.get("hard_skills", [])
        inst.soft_skills = d.get("soft_skills", [])
        inst.otros = d.get("otros", [])
        return inst


# ============================================================================
# Utility Functions
# ============================================================================


def load_json(path: str) -> Dict[str, Any]:
    """Load JSON file with UTF-8 encoding.
    
    Parameters
    ----------
    path : str
        File path to JSON file
    
    Returns
    -------
    dict
        Parsed JSON content
    """
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ============================================================================
# Example usage (uncomment to test)
# ============================================================================

if __name__ == "__main__":
    # Example: Load and process a CV
    sample_cv_data = {
        "nombre_apellidos": "Juan García López",
        "puesto": "Senior Software Engineer",
        "experiencia": [
            "Backend Developer at TechCorp (2020-2023), Python/FastAPI",
            "Junior Developer at StartUp Inc (2018-2020), Python/Django",
        ],
        "estudios": [
            "Bachelor's in Computer Science, Universidad de Madrid (2018)",
            "Master's in AI, Universidad Técnica (2022)",
        ],
        "hard_skills": [
            "Python", "FastAPI", "Django", "PostgreSQL", 
            "Docker", "AWS", "Kubernetes"
        ],
        "soft_skills": [
            "Team Leadership", "Project Management", "Communication", "Problem Solving"
        ],
        "otros": [
            "AWS Solutions Architect Associate Certification",
            "Speaker at Python conferences",
        ],
    }
    
    # Create processor and generate chunks
    cv = CVProcessor.from_dict(sample_cv_data)
    chunks = cv.generate_semantic_chunks()
    global_metadata = cv.get_global_metadata("es")
    
    print("=" * 70)
    print(f"CV PROFILE: {cv.nombre_apellidos}")
    print("=" * 70)
    print(f"Global Metadata: {json.dumps(global_metadata, indent=2, ensure_ascii=False)}\n")
    
    for i, chunk in enumerate(chunks, 1):
        print(f"\n{'─' * 70}")
        print(f"CHUNK {i} ({chunk['type'].upper()})")
        print(f"{'─' * 70}")
        print(f"Content:\n{chunk['content']}")
        print(f"\nMetadata: {json.dumps(chunk['metadata'], indent=2, ensure_ascii=False)}")
