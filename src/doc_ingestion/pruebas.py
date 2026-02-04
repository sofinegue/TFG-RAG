import os

from typing import List

class CVProcessor():
    # Usamos Field con alias para manejar los espacios en las keys del JSON
    nombre_apellidos: str
    puesto: str
    experiencia: List[str]
    estudios: List[str]
    hard_skills: List[str]
    soft_skills: List[str]
    otros: List[str]

    def generate_semantic_chunk(self) -> str:
        """
        Convierte el objeto estructurado en un bloque de texto enriquecido.
        Mantiene la cohesión para evitar el chunking tradicional.
        """
        # Procesamos las listas para convertirlas en bloques de texto legibles
        exp_text = "\n".join([f"- {item}" for item in self.experiencia])
        edu_text = "\n".join([f"- {item}" for item in self.estudios])
        otros_text = "\n".join([f"- {item}" for item in self.otros])
        
        chunk = (
            f"NOMBRE COMPLETO: {self.nombre_apellidos}\n"
            f"PUESTO: {self.puesto}\n\n"
            f"EXPERIENCIA PROFESIONAL:\n{exp_text}\n\n"
            f"FORMACIÓN ACADÉMICA:\n{edu_text}\n\n"
            f"COMPETENCIAS TÉCNICAS: {', '.join(self.hard_skills)}\n"
            f"COMPETENCIAS TRANSVERSALES: {', '.join(self.soft_skills)}\n\n"
            f"INFORMACIÓN ADICIONAL:\n{otros_text}"
        )
        return chunk

    def get_metadata(self, language: str = "es") -> dict:
        """Genera metadatos optimizados para filtrado."""
        return {
            "document_type": "cv",
            "name": self.nombre_apellidos,
            "position": self.puesto,
            "experience": self.experiencia,
            "skills": self.hard_skills + self.soft_skills,
            "language": language
        }

# --- Utilities: normalización y carga desde archivo ---
import json

def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data


# Añadimos un constructor alternativo desde dict
@classmethod
def from_dict(cls, d: dict):
    # aseguramos que las keys necesarias existan
    get = lambda k, default: d.get(k, default)
    inst = cls()
    inst.nombre_apellidos = get("nombre_apellidos", "")
    inst.puesto = get("puesto", "")
    inst.experiencia = get("experiencia", [])
    inst.estudios = get("estudios", [])
    # soportar tanto 'hard_skills' como 'hard_skills' normalizado de 'hard skills'
    inst.hard_skills = get("hard_skills", [])
    inst.soft_skills = get("soft_skills", [])
    inst.otros = get("otros", [])
    return inst

# Asociamos el método a la clase
CVProcessor.from_dict = from_dict

# --- Ejemplo de ejecución usando un path ---
path_en = os.path.join("data", "cvs", "en", "cv_001.json")
path_es = os.path.join("data", "cvs", "es", "cv_001.json")

# Cargar y normalizar desde archivo
data_en = load_json(path_en)
cv = CVProcessor.from_dict(data_en)

# Obtenemos el resultado
contextual_text = cv.generate_semantic_chunk()
metadata = cv.get_metadata()

print(f"Processed file: {path_en}")
print(f"Contextual Text:\n{contextual_text}")
print("\nMetadata:")
for key, value in metadata.items():
    print(f"  {key}: {value}")