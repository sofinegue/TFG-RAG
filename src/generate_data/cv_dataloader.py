import json
from pathlib import Path
from typing import List


class CVDataLoader:
    """
    Cargador de datos para generación de CVs.
    Los archivos JSON se encuentran en data/cv_plantilla/
    """
    
    def __init__(self, data_dir='data/cv_plantilla/es'):
        self.data_dir = Path(data_dir)
    
    def _load(self, filename):
        filepath = self.data_dir / filename
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @property
    def nombres(self) -> List[str]:
        """Retorna lista de nombres"""
        return self._load('personas.json')['nombres']
    
    @property
    def apellidos(self) -> List[str]:
        """Retorna lista de apellidos"""
        return self._load('personas.json')['apellidos']
    
    @property
    def puestos(self) -> List[str]:
        """Retorna lista de puestos de trabajo"""
        return self._load('puestos.json')['puestos']
    
    @property
    def experiencia_templates(self) -> List[str]:
        """Retorna plantillas de descripciones de experiencia"""
        return self._load('experiencia.json')['templates']
    
    @property
    def fp(self) -> List[str]:
        """Retorna lista de Formación Profesional (FP)"""
        return self._load('formacion.json')['fp']
    
    @property
    def grado(self) -> List[str]:
        """Retorna lista de Grados universitarios"""
        return self._load('formacion.json')['grado']
    
    @property
    def master(self) -> List[str]:
        """Retorna lista de Másteres"""
        return self._load('formacion.json')['master']
    
    @property
    def doctorado(self) -> List[str]:
        """Retorna lista de Doctorados"""
        return self._load('formacion.json')['doctorado']
    
    @property
    def cursos_y_certificaciones(self) -> List[str]:
        """Retorna lista de cursos y certificaciones"""
        return self._load('otros.json').get('cursos_y_certificaciones', [])
    
    @property
    def hard_skills(self) -> List[str]:
        """Retorna lista completa de hard skills"""
        return self._load('skills.json')['hard_skills']
    
    @property
    def soft_skills(self) -> List[str]:
        """Retorna lista de soft skills"""
        return self._load('skills.json')['soft_skills']
    
    @property
    def otros(self) -> List[str]:
        """Retorna lista de información adicional (idiomas, disponibilidad, etc.)"""
        return self._load('otros.json')['otros']
    
    @property
    def sectores(self) -> List[str]:
        """Retorna lista de sectores industriales"""
        return self._load('experiencia.json')['sectores']
    
    @property
    def areas(self) -> List[str]:
        """Retorna lista de áreas de trabajo"""
        return self._load('experiencia.json')['areas']
    
    @property
    def tareas(self) -> List[str]:
        """Retorna lista de tareas/actividades"""
        return self._load('experiencia.json')['tareas']
    
    @property
    def objetivos(self) -> List[str]:
        """Retorna lista de objetivos profesionales"""
        return self._load('experiencia.json')['objetivos']
    
    def get_all_formacion(self) -> dict:
        """Retorna toda la formación organizada por tipo"""
        return {
            'fp': self.fp,
            'grado': self.grado,
            'master': self.master,
            'doctorado': self.doctorado,
            'cursos_y_certificaciones': self.cursos_y_certificaciones
        }
    
    def get_all_skills(self) -> dict:
        """Retorna todas las skills organizadas"""
        return {
            'hard_skills': self.hard_skills,
            'soft_skills': self.soft_skills
        }
    
    def __repr__(self):
        return f"CVDataLoader(data_dir='{self.data_dir}')"


# Ejemplo de uso
if __name__ == "__main__":
    # Inicializar el loader
    loader = CVDataLoader()
    
    # Acceder a los datos
    print(f"Total nombres: {len(loader.nombres)}")
    print(f"Total apellidos: {len(loader.apellidos)}")
    print(f"Total puestos: {len(loader.puestos)}")
    print(f"Total hard skills: {len(loader.hard_skills)}")
    print(f"Total soft skills: {len(loader.soft_skills)}")
    
    # Ejemplos
    print(f"\nPrimeros 5 nombres: {loader.nombres[:5]}")
    print(f"Primeros 5 puestos: {loader.puestos[:5]}")
    print(f"Primeros 5 sectores: {loader.sectores[:5]}")
    
    # Obtener toda la formación
    formacion = loader.get_all_formacion()
    print(f"\nTipos de formación disponibles: {list(formacion.keys())}")
    print(f"Total FP: {len(formacion['fp'])}")
    print(f"Total Grados: {len(formacion['grado'])}")
    print(f"Total Másteres: {len(formacion['master'])}")