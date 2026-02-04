import json
import random
# import traceback

from pathlib import Path

from src.generate_data.cv_dataloader import CVDataLoader


NUM_CVS = 300
OUTPUT_DIR_ES = Path("data/cvs/es")
OUTPUT_DIR_EN = Path("data/cvs/en")

random.seed(22)


# Initialize data loaders for both languages
loader_es = CVDataLoader(data_dir='data/cv_plantilla/es')
loader_en = CVDataLoader(data_dir='data/cv_plantilla/en')


# Helper functions

def generar_nombre(loader):
    """Generates a full name with surnames"""
    return f"{random.choice(loader.nombres)} {random.choice(loader.apellidos)} {random.choice(loader.apellidos)}"


def generar_experiencia(puesto, min_años, max_años, loader, num_experiencias_max=5):
    """Generates professional experience descriptions"""
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


def generar_estudios(loader):
    """Generates list of studies following realistic logic"""
    estudios = []
    
    # Decide if include VT (40% probability of including)
    incluir_fp = random.random() < 0.4
    
    if incluir_fp:
        # VT: 1-3 elements
        num_fp = min(random.randint(1, 3), len(loader.fp))
        if num_fp > 0:
            estudios.extend(random.sample(loader.fp, k=num_fp))
        
        # Bachelor: 0-1 (optional if VT)
        if random.random() < 0.5 and len(loader.grado) > 0:
            estudios.extend(random.sample(loader.grado, k=1))
    else:
        # No VT: Bachelor mandatory (1)
        if len(loader.grado) > 0:
            estudios.extend(random.sample(loader.grado, k=1))
    
    # Master: 0-2 (only if Bachelor)
    if any("Bachelor" in e or "Degree" in e for e in estudios):
        num_masters = random.randint(0, 2)
        if num_masters > 0 and len(loader.master) >= num_masters:
            estudios.extend(random.sample(loader.master, k=num_masters))
            
            # PhD: 0-1 (only if at least 1 Master)
            if num_masters >= 1 and random.random() < 0.5:
                if len(loader.doctorado) > 0:
                    estudios.extend(random.sample(loader.doctorado, k=1))
    
    return estudios


def generar_lista(opciones, min_n, max_n):
    """Generates random list of elements from options"""
    # Adjust max if less options available
    max_n = min(max_n, len(opciones))
    min_n = min(min_n, max_n)
    
    if max_n == 0:
        return []
    
    n = random.randint(min_n, max_n)
    return random.sample(opciones, k=n)


# CV Generation

def generar_cv(loader):
    """Generates a complete CV with random data"""
    puesto = random.choice(loader.puestos)
    
    # Combine others + courses and certifications
    otros_completo = loader.otros + loader.cursos_y_certificaciones
    
    return {
        "nombre_apellidos": generar_nombre(loader),
        "puesto": puesto,
        "experiencia": generar_experiencia(puesto, min_años=0, max_años=4, loader=loader),
        "estudios": generar_estudios(loader),
        "hard_skills": generar_lista(loader.hard_skills, min_n=3, max_n=10),
        "soft_skills": generar_lista(loader.soft_skills, min_n=2, max_n=7),
        "otros": generar_lista(otros_completo, min_n=2, max_n=8)
    }


def main():
    """Generates multiple CVs in both languages and saves them in JSON files"""
    # Create output directories if they don't exist
    OUTPUT_DIR_ES.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR_EN.mkdir(parents=True, exist_ok=True)
    
    print(f"Iniciating generation of {NUM_CVS} CVs in Spanish and English...")
    print(f"\nSpanish data loaded:")
    print(f"   - {len(loader_es.nombres)} names")
    print(f"   - {len(loader_es.apellidos)} surnames")
    print(f"   - {len(loader_es.puestos)} positions")
    print(f"   - {len(loader_es.hard_skills)} hard skills")
    print(f"   - {len(loader_es.soft_skills)} soft skills")
    print(f"   - {len(loader_es.experiencia_templates)} experience templates")
    
    print(f"\nEnglish data loaded:")
    print(f"   - {len(loader_en.nombres)} names")
    print(f"   - {len(loader_en.apellidos)} surnames")
    print(f"   - {len(loader_en.puestos)} positions")
    print(f"   - {len(loader_en.hard_skills)} hard skills")
    print(f"   - {len(loader_en.soft_skills)} soft skills")
    print(f"   - {len(loader_en.experiencia_templates)} experience templates")
    print()
    
    # Generate CVs
    for i in range(1, NUM_CVS + 1):
        # Spanish CV
        cv_es = generar_cv(loader_es)
        filename_es = OUTPUT_DIR_ES / f"cv_{i:03d}.json"
        
        with open(filename_es, "w", encoding="utf-8") as f:
            json.dump(cv_es, f, ensure_ascii=False, indent=2)
        
        # English CV
        cv_en = generar_cv(loader_en)
        filename_en = OUTPUT_DIR_EN / f"cv_{i:03d}.json"
        
        with open(filename_en, "w", encoding="utf-8") as f:
            json.dump(cv_en, f, ensure_ascii=False, indent=2)
        
        # if i % 50 == 0:
        #     print(f"Generated {i}/{NUM_CVS} CVs in both languages...")
    
    print(f"\nGeneration completed! {NUM_CVS} CVs saved in both languages:")
    print(f"   Spanish: {OUTPUT_DIR_ES.absolute()}")
    print(f"   English: {OUTPUT_DIR_EN.absolute()}")
    
    # # Statistics
    # print("\nStatistics:")
    # total_size_es = sum(f.stat().st_size for f in OUTPUT_DIR_ES.glob("cv_*.json"))
    # total_size_en = sum(f.stat().st_size for f in OUTPUT_DIR_EN.glob("cv_*.json"))
    # print(f"   Spanish CVs total size: {total_size_es / 1024:.2f} KB")
    # print(f"   Spanish CVs average: {total_size_es / NUM_CVS / 1024:.2f} KB per CV")
    # print(f"   English CVs total size: {total_size_en / 1024:.2f} KB")
    # print(f"   English CVs average: {total_size_en / NUM_CVS / 1024:.2f} KB per CV")


# if __name__ == "__main__":
#     try:
#         main()
#     except Exception as e:
#         print(f"\nError during generation: {e}")
#         traceback.print_exc()