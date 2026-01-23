import json
import random
from pathlib import Path

from src.generate_data.cv_dataloader import CVDataLoader


NUM_CVS = 300
OUTPUT_DIR = Path("data/cvs")

random.seed(22)


# Inicializar el loader de datos
loader = CVDataLoader(data_dir='data/cv_plantilla')


# Funciones auxiliares

def generar_nombre():
    """Genera un nombre completo con apellidos"""
    return f"{random.choice(loader.nombres)} {random.choice(loader.apellidos)} {random.choice(loader.apellidos)}"


def generar_experiencia(puesto, min_años, max_años, num_experiencias_max=5):
    """Genera descripciones de experiencia profesional"""
    n = random.randint(0, num_experiencias_max)
    experiencias = []
    
    for _ in range(n):
        template = random.choice(loader.experiencia_templates)
        experiencias.append(
            template.format(
                puesto=puesto,
                años=random.randint(min_años, max_años),
                sector=random.choice(loader.sectores),
                area=random.choice(loader.areas),
                tarea=random.choice(loader.tareas),
                objetivo=random.choice(loader.objetivos)
            )
        )
    
    return experiencias


def generar_estudios():
    """Genera lista de estudios siguiendo una lógica realista"""
    estudios = []
    
    # Decidir si incluir FP (60% de probabilidad de NO incluir)
    incluir_fp = random.random() < 0.4
    
    if incluir_fp:
        # FP: 1-3 elementos
        num_fp = min(random.randint(1, 3), len(loader.fp))
        estudios.extend(random.sample(loader.fp, k=num_fp))
        
        # Grado: 0-1 (opcional si hay FP)
        if random.random() < 0.5 and len(loader.grado) > 0:
            estudios.extend(random.sample(loader.grado, k=1))
    else:
        # Sin FP: Grado obligatorio (1)
        if len(loader.grado) > 0:
            estudios.extend(random.sample(loader.grado, k=1))
    
    # Máster: 0-2 (solo si hay Grado)
    if any("Grado" in e or "Bachelor" in e for e in estudios):
        num_masters = random.randint(0, 2)
        if num_masters > 0 and len(loader.master) >= num_masters:
            estudios.extend(random.sample(loader.master, k=num_masters))
            
            # Doctorado: 0-1 (solo si hay al menos 1 Máster)
            if num_masters >= 1 and random.random() < 0.5:
                if len(loader.doctorado) > 0:
                    estudios.extend(random.sample(loader.doctorado, k=1))
    
    return estudios


def generar_lista(opciones, min_n, max_n):
    """Genera una lista aleatoria de elementos de las opciones"""
    # Ajustar el máximo si hay menos opciones disponibles
    max_n = min(max_n, len(opciones))
    min_n = min(min_n, max_n)
    
    if max_n == 0:
        return []
    
    n = random.randint(min_n, max_n)
    return random.sample(opciones, k=n)


# Generación de CVs

def generar_cv():
    """Genera un CV completo con datos aleatorios"""
    puesto = random.choice(loader.puestos)
    
    # Combinar otros + cursos y certificaciones
    otros_completo = loader.otros + loader.cursos_y_certificaciones
    
    return {
        "nombre_apellidos": generar_nombre(),
        "puesto": puesto,
        "experiencia": generar_experiencia(puesto, min_años=0, max_años=4),
        "estudios": generar_estudios(),
        "hard_skills": generar_lista(loader.hard_skills, min_n=3, max_n=10),
        "soft_skills": generar_lista(loader.soft_skills, min_n=2, max_n=7),
        "otros": generar_lista(otros_completo, min_n=2, max_n=8)
    }


def main():
    """Genera múltiples CVs y los guarda en archivos JSON"""
    # Crear directorio de salida si no existe
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"Iniciando generación de {NUM_CVS} CVs...")
    print(f"Datos cargados:")
    print(f"   - {len(loader.nombres)} nombres")
    print(f"   - {len(loader.apellidos)} apellidos")
    print(f"   - {len(loader.puestos)} puestos")
    print(f"   - {len(loader.hard_skills)} hard skills")
    print(f"   - {len(loader.soft_skills)} soft skills")
    print(f"   - {len(loader.experiencia_templates)} templates de experiencia")
    print()
    
    # Generar CVs
    for i in range(1, NUM_CVS + 1):
        cv = generar_cv()
        filename = OUTPUT_DIR / f"cv_{i:03d}.json"
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(cv, f, ensure_ascii=False, indent=2)
        
        print(f"CV {i:03d} generado: {cv['nombre_apellidos']} - {cv['puesto']}")
    
    print(f"\nGeneración completada! {NUM_CVS} CVs guardados en: {OUTPUT_DIR.absolute()}")
    
    # Estadísticas
    print("\nEstadísticas:")
    total_size = sum(f.stat().st_size for f in OUTPUT_DIR.glob("cv_*.json"))
    print(f"   - Tamaño total: {total_size / 1024:.2f} KB")
    print(f"   - Promedio por CV: {total_size / NUM_CVS / 1024:.2f} KB")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nError durante la generación: {e}")
        import traceback
        traceback.print_exc()