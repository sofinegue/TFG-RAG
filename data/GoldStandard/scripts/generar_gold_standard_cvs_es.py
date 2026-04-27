"""
Script para generar el Gold Standard del caso de uso de CVs en español.
Genera 80-100 preguntas únicas con respuestas computadas directamente de los datos.

Autor: Generado automáticamente para el TFG
Fecha: 2026-04-17

    python -m data.GoldStandard.scripts.generar_gold_standard_cvs_es
"""

import json
import os
import random
from collections import Counter, defaultdict
from pathlib import Path

random.seed(42)

# ─────────────────────────────────────────────
# 1. CARGAR TODOS LOS CVs
# ─────────────────────────────────────────────
CV_DIR = Path(__file__).parent.parent.parent / "cvs" / "es"
OUTPUT_DIR = Path(__file__).parent.parent

cvs = {}
for f in sorted(CV_DIR.glob("cv_*.json")):
    with open(f, encoding="utf-8") as fh:
        cv = json.load(fh)
        cv_id = f.stem  # e.g. cv_001
        cvs[cv_id] = cv

print(f"Cargados {len(cvs)} CVs")

# ─────────────────────────────────────────────
# 2. CONSTRUIR ÍNDICES INVERTIDOS
# ─────────────────────────────────────────────
idx_hard_skill = defaultdict(list)       # skill -> [nombre, ...]
idx_soft_skill = defaultdict(list)
idx_puesto = defaultdict(list)
idx_estudio = defaultdict(list)
idx_otro = defaultdict(list)
idx_nombre_cv = {}                       # nombre -> cv_id
idx_cv_data = {}                         # cv_id -> cv completo

for cv_id, cv in cvs.items():
    nombre = cv["nombre_apellidos"]
    idx_nombre_cv[nombre] = cv_id
    idx_cv_data[cv_id] = cv

    for s in cv.get("hard_skills", []):
        idx_hard_skill[s].append(nombre)
    for s in cv.get("soft_skills", []):
        idx_soft_skill[s].append(nombre)
    idx_puesto[cv.get("puesto", "")].append(nombre)
    for e in cv.get("estudios", []):
        idx_estudio[e].append(nombre)
    for o in cv.get("otros", []):
        idx_otro[o].append(nombre)

# Índices auxiliares: experiencia por área
idx_exp_area = defaultdict(list)  # keyword -> [nombre]
for cv_id, cv in cvs.items():
    nombre = cv["nombre_apellidos"]
    for exp in cv.get("experiencia", []):
        idx_exp_area[exp].append(nombre)

# Contar skills para rankings
hard_skill_counts = Counter()
soft_skill_counts = Counter()
puesto_counts = Counter()
estudio_counts = Counter()
otro_counts = Counter()
skills_per_person = {}

for cv_id, cv in cvs.items():
    nombre = cv["nombre_apellidos"]
    hs = cv.get("hard_skills", [])
    ss = cv.get("soft_skills", [])
    hard_skill_counts.update(hs)
    soft_skill_counts.update(ss)
    puesto_counts[cv.get("puesto", "")] += 1
    estudio_counts.update(cv.get("estudios", []))
    otro_counts.update(cv.get("otros", []))
    skills_per_person[nombre] = {
        "hard": len(hs),
        "soft": len(ss),
        "total": len(hs) + len(ss),
        "estudios": len(cv.get("estudios", [])),
        "experiencia": len(cv.get("experiencia", [])),
        "otros": len(cv.get("otros", []))
    }

# Funciones auxiliares para seleccionar datos interesantes
def pick_skill_with_n_people(idx, min_n=2, max_n=15):
    """Elige un skill que tenga entre min_n y max_n personas."""
    candidates = [(k, v) for k, v in idx.items() if min_n <= len(v) <= max_n]
    if not candidates:
        candidates = [(k, v) for k, v in idx.items() if len(v) >= 1]
    return random.choice(candidates)

def pick_skill_with_exactly_n(idx, n):
    """Elige un skill con exactamente n personas."""
    candidates = [(k, v) for k, v in idx.items() if len(v) == n]
    if candidates:
        return random.choice(candidates)
    return pick_skill_with_n_people(idx, max(1, n-2), n+2)

def pick_random_person():
    nombre = random.choice(list(idx_nombre_cv.keys()))
    cv_id = idx_nombre_cv[nombre]
    return nombre, cv_id, cvs[cv_id]

def pick_person_with_field(field, min_items=1):
    candidates = [(n, idx_nombre_cv[n], cvs[idx_nombre_cv[n]]) 
                  for n in idx_nombre_cv 
                  if len(cvs[idx_nombre_cv[n]].get(field, [])) >= min_items]
    return random.choice(candidates)

# Personas con idiomas en "otros"
def get_idioma_personas(idioma_keyword):
    """Busca en 'otros' todas las personas que tengan alguna entrada con el keyword de idioma."""
    result = []
    for cv_id, cv in cvs.items():
        for o in cv.get("otros", []):
            if idioma_keyword.lower() in o.lower():
                result.append(cv["nombre_apellidos"])
                break
    return result

# Personas con experiencia que contenga un keyword
def get_experiencia_keyword(keyword):
    result = []
    for cv_id, cv in cvs.items():
        for exp in cv.get("experiencia", []):
            if keyword.lower() in exp.lower():
                result.append(cv["nombre_apellidos"])
                break
    return result

# Personas que tengan al menos 2 skills concretas
def get_personas_multi_skill(skills):
    result = []
    for cv_id, cv in cvs.items():
        hs = set(cv.get("hard_skills", []))
        if all(s in hs for s in skills):
            result.append(cv["nombre_apellidos"])
    return result

# Personas con un puesto Y un skill
def get_personas_puesto_skill(puesto, skill):
    result = []
    for cv_id, cv in cvs.items():
        if cv.get("puesto") == puesto and skill in cv.get("hard_skills", []):
            result.append(cv["nombre_apellidos"])
    return result

# Personas con un estudio Y un skill
def get_personas_estudio_skill(estudio, skill):
    result = []
    for cv_id, cv in cvs.items():
        if estudio in cv.get("estudios", []) and skill in cv.get("hard_skills", []):
            result.append(cv["nombre_apellidos"])
    return result

# ─────────────────────────────────────────────
# 3. GENERAR LAS 200 PREGUNTAS
# ─────────────────────────────────────────────

preguntas = []
used_ids = set()
q_id = 0

def add_q(categoria, pregunta, respuesta, tipo_respuesta="lista_personas", cv_ref=None, metadata=None):
    global q_id
    q_id += 1
    entry = {
        "id": q_id,
        "categoria": categoria,
        "pregunta": pregunta,
        "tipo_respuesta": tipo_respuesta,
    }
    if isinstance(respuesta, list):
        try:
            entry["respuesta"] = sorted(respuesta)
        except TypeError:
            entry["respuesta"] = respuesta
        entry["num_resultados"] = len(respuesta)
    else:
        entry["respuesta"] = respuesta
    if cv_ref:
        entry["cv_referencia"] = cv_ref
    if metadata:
        entry["metadata"] = metadata
    preguntas.append(entry)

# ═══════════════════════════════════════════════
# CATEGORÍA 1: BÚSQUEDA POR HARD SKILL (25 preguntas)
# Cada una con una formulación completamente distinta.
# ═══════════════════════════════════════════════

hs_keys = list(idx_hard_skill.keys())
random.shuffle(hs_keys)
hs_iter = iter(hs_keys)

def next_hs():
    return next(hs_iter)

s = next_hs()
add_q("busqueda_por_skill", f"¿Qué personas dominan {s}?", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"Necesito un listado completo de candidatos que sepan {s}.", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"Dame los nombres de todos los profesionales con conocimientos en {s}.", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"¿Quiénes tienen {s} entre sus habilidades técnicas?", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"Busco perfiles que incluyan {s} en su currículum. ¿Cuáles son?", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"Enumera a todas las personas cuyo CV refleje experiencia con {s}.", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"¿De qué candidatos consta que manejan {s}?", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"Identifica a los profesionales que tienen {s} como competencia técnica.", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"¿Podrías indicarme quiénes cuentan con la habilidad de {s}?", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"Para un proyecto que requiere {s}, ¿qué personas están disponibles?", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"Muéstrame todos los candidatos con {s} en su perfil.", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"¿Hay alguien en la base de datos que sepa {s}? ¿Quiénes?", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"Haz una relación de las personas que figuran con {s} en sus hard skills.", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"Estoy armando un equipo que necesita {s}. ¿A quiénes puedo considerar?", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"¿Qué candidatos mencionan {s} dentro de sus competencias?", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"Dime todas las personas que aparezcan con la skill {s}.", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"¿Cuáles son los perfiles que destacan por saber {s}?", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"Filtra los CVs y devuélveme solo los que contengan {s}.", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"Proporciona la lista de empleados que utilizan {s} en su trabajo.", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"¿Quién de nuestros candidatos declara saber {s}?", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"Recopila los nombres de quienes tienen formación o experiencia en {s}.", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"Según los CVs disponibles, ¿qué personas conocen {s}?", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"¿Existe algún profesional en nuestra base con {s}? Lístamelos.", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"Extrae del sistema a todos aquellos que tengan {s} como habilidad.", idx_hard_skill[s])

s = next_hs()
add_q("busqueda_por_skill", f"¿A qué personas les podríamos asignar tareas de {s} según su CV?", idx_hard_skill[s])


# ═══════════════════════════════════════════════
# CATEGORÍA 2: BÚSQUEDA POR PUESTO (20 preguntas)
# ═══════════════════════════════════════════════

pu_keys = list(idx_puesto.keys())
random.shuffle(pu_keys)
pu_iter = iter(pu_keys)

def next_pu():
    return next(pu_iter)

p = next_pu()
add_q("busqueda_por_puesto", f"¿Quiénes trabajan como {p}?", idx_puesto[p])

p = next_pu()
add_q("busqueda_por_puesto", f"Dame la lista de personas cuyo puesto sea {p}.", idx_puesto[p])

p = next_pu()
add_q("busqueda_por_puesto", f"Necesito saber qué candidatos ocupan el rol de {p}.", idx_puesto[p])

p = next_pu()
add_q("busqueda_por_puesto", f"¿Cuántos y cuáles profesionales figuran como {p} en sus CVs?", idx_puesto[p],
      tipo_respuesta="lista_personas_con_conteo")

p = next_pu()
add_q("busqueda_por_puesto", f"Indica todos los nombres de quienes se desempeñan como {p}.", idx_puesto[p])

p = next_pu()
add_q("busqueda_por_puesto", f"¿Qué personas tienen el cargo de {p} actualmente?", idx_puesto[p])

p = next_pu()
add_q("busqueda_por_puesto", f"Localiza en la base de datos a todos los {p}.", idx_puesto[p])

p = next_pu()
add_q("busqueda_por_puesto", f"¿Podrías decirme quiénes son los {p} registrados?", idx_puesto[p])

p = next_pu()
add_q("busqueda_por_puesto", f"Muestra el listado completo de candidatos con puesto de {p}.", idx_puesto[p])

p = next_pu()
add_q("busqueda_por_puesto", f"¿Tenemos {p} en el equipo? Dime sus nombres.", idx_puesto[p])

p = next_pu()
add_q("busqueda_por_puesto", f"Selecciona a todas las personas que ejercen de {p}.", idx_puesto[p])

p = next_pu()
add_q("busqueda_por_puesto", f"Estoy buscando a alguien que sea {p}. ¿Quiénes hay?", idx_puesto[p])

p = next_pu()
add_q("busqueda_por_puesto", f"Identifica del conjunto de CVs a quienes se presentan como {p}.", idx_puesto[p])

p = next_pu()
add_q("busqueda_por_puesto", f"¿Quién tiene como título profesional {p}?", idx_puesto[p])

p = next_pu()
add_q("busqueda_por_puesto", f"Recoge todos los profesionales categorizados bajo el puesto {p}.", idx_puesto[p])

p = next_pu()
add_q("busqueda_por_puesto", f"Me interesa contratar un {p}. ¿Qué opciones hay en la base?", idx_puesto[p])

p = next_pu()
add_q("busqueda_por_puesto", f"¿De qué personas se indica que su posición es {p}?", idx_puesto[p])

p = next_pu()
add_q("busqueda_por_puesto", f"Si filtro por puesto = '{p}', ¿qué nombres aparecen?", idx_puesto[p])

p = next_pu()
add_q("busqueda_por_puesto", f"¿Hay candidatos cuyo rol actual sea {p}? Enuméralos.", idx_puesto[p])

p = next_pu()
add_q("busqueda_por_puesto", f"Devuélveme una relación de los {p} disponibles.", idx_puesto[p])


# ═══════════════════════════════════════════════
# CATEGORÍA 3: BÚSQUEDA POR FORMACIÓN (20 preguntas)
# ═══════════════════════════════════════════════

est_keys = list(idx_estudio.keys())
random.shuffle(est_keys)
est_iter = iter(est_keys)

def next_est():
    return next(est_iter)

e = next_est()
add_q("busqueda_por_formacion", f"¿Quiénes han estudiado {e}?", idx_estudio[e])

e = next_est()
add_q("busqueda_por_formacion", f"Lista a todos los candidatos que tengan la titulación de {e}.", idx_estudio[e])

e = next_est()
add_q("busqueda_por_formacion", f"¿Qué personas de la base de datos cursaron {e}?", idx_estudio[e])

e = next_est()
add_q("busqueda_por_formacion", f"Dime los nombres de quienes poseen el título de {e}.", idx_estudio[e])

e = next_est()
add_q("busqueda_por_formacion", f"¿Cuáles candidatos incluyen {e} en su formación académica?", idx_estudio[e])

e = next_est()
add_q("busqueda_por_formacion", f"Necesito identificar a todas las personas con estudios en {e}.", idx_estudio[e])

e = next_est()
add_q("busqueda_por_formacion", f"Busca en los CVs quiénes tienen como estudio {e}.", idx_estudio[e])

e = next_est()
add_q("busqueda_por_formacion", f"¿Hay profesionales con la carrera de {e}? ¿Quiénes son?", idx_estudio[e])

e = next_est()
add_q("busqueda_por_formacion", f"Extrae la lista de personas que se graduaron en {e}.", idx_estudio[e])

e = next_est()
add_q("busqueda_por_formacion", f"Muéstrame candidatos cuya formación incluya {e}.", idx_estudio[e])

e = next_est()
add_q("busqueda_por_formacion", f"¿A quiénes les consta haber completado {e}?", idx_estudio[e])

e = next_est()
add_q("busqueda_por_formacion", f"¿Qué miembros del equipo tienen formación en {e}?", idx_estudio[e])

e = next_est()
add_q("busqueda_por_formacion", f"Enumera los profesionales con titulación en {e}.", idx_estudio[e])

e = next_est()
add_q("busqueda_por_formacion", f"¿Quién de los candidatos cuenta con un {e}?", idx_estudio[e])

e = next_est()
add_q("busqueda_por_formacion", f"De entre todos los CVs, ¿cuáles reflejan {e} como estudio?", idx_estudio[e])

e = next_est()
add_q("busqueda_por_formacion", f"Filtra por formación y dame las personas con {e}.", idx_estudio[e])

e = next_est()
add_q("busqueda_por_formacion", f"¿Se puede saber quiénes tienen el {e} en su currículum?", idx_estudio[e])

e = next_est()
add_q("busqueda_por_formacion", f"Proporciona los candidatos que acreditan {e}.", idx_estudio[e])

e = next_est()
add_q("busqueda_por_formacion", f"¿Qué personas reflejan haber estudiado {e}?", idx_estudio[e])

e = next_est()
add_q("busqueda_por_formacion", f"Revisa la base de datos y dime quiénes tienen {e} como titulación.", idx_estudio[e])


# ═══════════════════════════════════════════════
# CATEGORÍA 4: BÚSQUEDA POR IDIOMA / OTROS (15 preguntas)
# ═══════════════════════════════════════════════

add_q("busqueda_por_idioma", "¿Qué candidatos hablan inglés a nivel C1 o superior?",
      sorted(set(get_idioma_personas("Inglés C1") + get_idioma_personas("Inglés C2") + 
                 get_idioma_personas("Inglés nativo") + get_idioma_personas("Inglés bilingüe"))))

add_q("busqueda_por_idioma", "Dame todos los profesionales que tengan francés en su CV.",
      get_idioma_personas("Francés"))

add_q("busqueda_por_idioma", "¿Quiénes declaran saber alemán en cualquier nivel?",
      get_idioma_personas("Alemán"))

add_q("busqueda_por_idioma", "Necesito personas que hablen portugués. ¿Hay alguna?",
      get_idioma_personas("Portugués"))

add_q("busqueda_por_idioma", "Identifica a los candidatos con nivel de inglés B2.",
      get_idioma_personas("Inglés B2"))

add_q("busqueda_por_idioma", "¿Cuáles profesionales mencionan italiano en su perfil?",
      get_idioma_personas("Italiano"))

add_q("busqueda_por_idioma", "Muéstrame quiénes tienen japonés como idioma.",
      get_idioma_personas("Japonés"))

add_q("busqueda_por_idioma", "Busca personas que se identifiquen como autodidactas.",
      [cv["nombre_apellidos"] for cv in cvs.values() if "Autodidacta" in cv.get("otros", [])])

add_q("busqueda_por_idioma", "¿Qué candidatos prefieren modalidad remota?",
      [cv["nombre_apellidos"] for cv in cvs.values() 
       if any("remoto" in o.lower() or "remota" in o.lower() for o in cv.get("otros", []))])

add_q("busqueda_por_idioma", "¿Quiénes tienen experiencia en startups según su CV?",
      [cv["nombre_apellidos"] for cv in cvs.values() 
       if any("startup" in o.lower() for o in cv.get("otros", []))])

add_q("busqueda_por_idioma", "Lista los candidatos que mencionan tener disponibilidad inmediata.",
      [cv["nombre_apellidos"] for cv in cvs.values()
       if any("disponibilidad inmediata" in o.lower() for o in cv.get("otros", []))])

add_q("busqueda_por_idioma", "¿Qué personas indican que son speaker en conferencias?",
      [cv["nombre_apellidos"] for cv in cvs.values()
       if any("speaker" in o.lower() for o in cv.get("otros", []))])

add_q("busqueda_por_idioma", "Encuentra a quienes mencionan chino o mandarín en su perfil.",
      get_idioma_personas("Chino") + get_idioma_personas("Mandarín"))

add_q("busqueda_por_idioma", "¿Hay candidatos con experiencia en sector bancario?",
      [cv["nombre_apellidos"] for cv in cvs.values()
       if any("bancario" in o.lower() or "banca" in o.lower() for o in cv.get("otros", []))])

add_q("busqueda_por_idioma", "¿Quiénes prefieren contrato indefinido según sus datos?",
      [cv["nombre_apellidos"] for cv in cvs.values()
       if any("indefinido" in o.lower() for o in cv.get("otros", []))])


# ═══════════════════════════════════════════════
# CATEGORÍA 5: CONSULTA INDIVIDUAL - DATOS DE UNA PERSONA (25 preguntas)
# ═══════════════════════════════════════════════

personas_list = list(idx_nombre_cv.keys())
random.shuffle(personas_list)
p_iter = iter(personas_list)

def next_person():
    n = next(p_iter)
    return n, idx_nombre_cv[n], cvs[idx_nombre_cv[n]]

n, cid, cv = next_person()
add_q("consulta_individual", f"¿Cuál es el puesto de {n}?", cv["puesto"], "valor_unico", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"Dime las hard skills que tiene {n}.", cv.get("hard_skills", []), "lista_skills", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"¿Qué formación académica aparece en el CV de {n}?", cv.get("estudios", []), "lista_estudios", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"¿Cuáles son las soft skills de {n}?", cv.get("soft_skills", []), "lista_skills", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"Consulta el perfil de {n} y dime su puesto actual.", cv["puesto"], "valor_unico", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"¿Qué información adicional (otros) consta en el CV de {n}?", cv.get("otros", []), "lista_otros", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"Me gustaría saber qué habilidades técnicas posee {n}.", cv.get("hard_skills", []), "lista_skills", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"¿De qué trabaja {n}?", cv["puesto"], "valor_unico", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"¿En qué se ha formado {n}? Dame sus estudios.", cv.get("estudios", []), "lista_estudios", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"Quiero ver el perfil completo de {n}. ¿Qué competencias blandas tiene?", cv.get("soft_skills", []), "lista_skills", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"Describe las competencias técnicas de {n}.", cv.get("hard_skills", []), "lista_skills", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"¿A qué puesto se dedica {n} según su currículum?", cv["puesto"], "valor_unico", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"Dime qué estudios ha cursado {n}.", cv.get("estudios", []), "lista_estudios", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"¿Tiene {n} alguna certificación, idioma u otra información relevante?", cv.get("otros", []), "lista_otros", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"Necesito conocer las tecnologías que maneja {n}.", cv.get("hard_skills", []), "lista_skills", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"¿Cuál es la posición profesional de {n}?", cv["puesto"], "valor_unico", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"Revisa el CV de {n} y extrae sus aptitudes personales.", cv.get("soft_skills", []), "lista_skills", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"¿Qué titulaciones constan en el perfil de {n}?", cv.get("estudios", []), "lista_estudios", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"Pon a mi disposición las habilidades técnicas que aparecen en el CV de {n}.", cv.get("hard_skills", []), "lista_skills", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"¿Qué rol desempeña {n}?", cv["puesto"], "valor_unico", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"¿Cuáles son los datos complementarios del perfil de {n}?", cv.get("otros", []), "lista_otros", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"Indícame las herramientas y lenguajes que domina {n}.", cv.get("hard_skills", []), "lista_skills", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"¿Qué cualidades interpersonales se le atribuyen a {n}?", cv.get("soft_skills", []), "lista_skills", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"Quisiera saber la formación de {n}. ¿Puedes ayudarme?", cv.get("estudios", []), "lista_estudios", cid)

n, cid, cv = next_person()
add_q("consulta_individual", f"¿Qué cargo ocupa {n} según la información disponible?", cv["puesto"], "valor_unico", cid)


# ═══════════════════════════════════════════════
# CATEGORÍA 6: CONSULTA INDIVIDUAL - EXPERIENCIA (15 preguntas)
# ═══════════════════════════════════════════════

# Seleccionar personas con experiencia no vacía
personas_con_exp = [n for n in idx_nombre_cv if len(cvs[idx_nombre_cv[n]].get("experiencia", [])) > 0]
random.shuffle(personas_con_exp)
exp_iter = iter(personas_con_exp)

def next_person_exp():
    n = next(exp_iter)
    return n, idx_nombre_cv[n], cvs[idx_nombre_cv[n]]

n, cid, cv = next_person_exp()
add_q("consulta_experiencia", f"¿En qué ha trabajado {n}?", cv.get("experiencia", []), "lista_experiencia", cid)

n, cid, cv = next_person_exp()
add_q("consulta_experiencia", f"Descríbeme la experiencia profesional de {n}.", cv.get("experiencia", []), "lista_experiencia", cid)

n, cid, cv = next_person_exp()
add_q("consulta_experiencia", f"¿Qué experiencia laboral tiene registrada {n}?", cv.get("experiencia", []), "lista_experiencia", cid)

n, cid, cv = next_person_exp()
add_q("consulta_experiencia", f"Dame un resumen de la trayectoria de {n}.", cv.get("experiencia", []), "lista_experiencia", cid)

n, cid, cv = next_person_exp()
add_q("consulta_experiencia", f"¿Cuáles son las funciones que ha desempeñado {n} según su CV?", cv.get("experiencia", []), "lista_experiencia", cid)

n, cid, cv = next_person_exp()
add_q("consulta_experiencia", f"Me interesa saber el recorrido profesional de {n}.", cv.get("experiencia", []), "lista_experiencia", cid)

n, cid, cv = next_person_exp()
add_q("consulta_experiencia", f"¿Qué tareas y roles ha tenido {n} a lo largo de su carrera?", cv.get("experiencia", []), "lista_experiencia", cid)

n, cid, cv = next_person_exp()
add_q("consulta_experiencia", f"Explícame la experiencia que se detalla en el perfil de {n}.", cv.get("experiencia", []), "lista_experiencia", cid)

n, cid, cv = next_person_exp()
add_q("consulta_experiencia", f"¿En qué proyectos o áreas ha participado {n}?", cv.get("experiencia", []), "lista_experiencia", cid)

n, cid, cv = next_person_exp()
add_q("consulta_experiencia", f"Consulta la sección de experiencia de {n} y cuéntame qué aparece.", cv.get("experiencia", []), "lista_experiencia", cid)

n, cid, cv = next_person_exp()
add_q("consulta_experiencia", f"¿Qué background laboral posee {n}?", cv.get("experiencia", []), "lista_experiencia", cid)

n, cid, cv = next_person_exp()
add_q("consulta_experiencia", f"Háblame de lo que ha hecho profesionalmente {n}.", cv.get("experiencia", []), "lista_experiencia", cid)

n, cid, cv = next_person_exp()
add_q("consulta_experiencia", f"¿Puedes detallarme en qué ha estado involucrado {n}?", cv.get("experiencia", []), "lista_experiencia", cid)

n, cid, cv = next_person_exp()
add_q("consulta_experiencia", f"Me gustaría revisar la experiencia acumulada de {n}.", cv.get("experiencia", []), "lista_experiencia", cid)

n, cid, cv = next_person_exp()
add_q("consulta_experiencia", f"Dime las responsabilidades previas que constan en el CV de {n}.", cv.get("experiencia", []), "lista_experiencia", cid)


# ═══════════════════════════════════════════════
# CATEGORÍA 7: PREGUNTAS DE CONTEO (20 preguntas)
# ═══════════════════════════════════════════════

s = next_hs()
add_q("conteo", f"¿Cuántas personas saben {s}?", len(idx_hard_skill[s]), "numero")

s = next_hs()
add_q("conteo", f"¿Cuál es el número total de candidatos que dominan {s}?", len(idx_hard_skill[s]), "numero")

p = next_pu()
add_q("conteo", f"¿Cuántos {p} hay registrados en la base de datos?", len(idx_puesto[p]), "numero")

e = next_est()
add_q("conteo", f"¿Cuántas personas han estudiado {e}?", len(idx_estudio[e]), "numero")

add_q("conteo", "¿Cuántos CVs hay en total en el sistema?", len(cvs), "numero")

add_q("conteo", "¿Cuántos puestos distintos existen entre todos los candidatos?",
      len(set(cv["puesto"] for cv in cvs.values())), "numero")

s = next_hs()
add_q("conteo", f"Cuenta los profesionales que incluyen {s} en sus competencias.", len(idx_hard_skill[s]), "numero")

p = next_pu()
add_q("conteo", f"Dime cuántas personas trabajan como {p}.", len(idx_puesto[p]), "numero")

add_q("conteo", "¿Cuántas hard skills diferentes se mencionan en todos los CVs?",
      len(idx_hard_skill), "numero")

add_q("conteo", "¿Cuántas titulaciones distintas aparecen en la base de datos?",
      len(idx_estudio), "numero")

s = next_hs()
add_q("conteo", f"¿A cuántos candidatos les podemos atribuir conocimientos de {s}?", len(idx_hard_skill[s]), "numero")

add_q("conteo", "¿Cuántas soft skills distintas se recogen en el conjunto de CVs?",
      len(idx_soft_skill), "numero")

add_q("conteo", "Del total de candidatos, ¿cuántos tienen experiencia laboral registrada (al menos una entrada)?",
      len([cv for cv in cvs.values() if len(cv.get("experiencia", [])) > 0]), "numero")

add_q("conteo", "¿Cuántas personas no tienen ninguna experiencia reflejada en su CV?",
      len([cv for cv in cvs.values() if len(cv.get("experiencia", [])) == 0]), "numero")

add_q("conteo", "¿Cuántos candidatos hablan al menos un idioma aparte del español?",
      len([cv for cv in cvs.values() if any(
          any(lang in o for lang in ["Inglés", "Francés", "Alemán", "Italiano", "Portugués", "Chino", "Japonés", "Árabe", "Ruso", "Coreano"])
          for o in cv.get("otros", []))]), "numero")

e = next_est()
add_q("conteo", f"¿Cuántos profesionales tienen {e} en su formación?", len(idx_estudio[e]), "numero")

add_q("conteo", "¿Cuántos candidatos tienen más de 5 hard skills en su perfil?",
      len([cv for cv in cvs.values() if len(cv.get("hard_skills", [])) > 5]), "numero")

add_q("conteo", "¿Cuántas personas mencionan ser autodidactas?",
      len([cv for cv in cvs.values() if "Autodidacta" in cv.get("otros", [])]), "numero")

add_q("conteo", "¿Cuántos candidatos tienen más de una titulación académica?",
      len([cv for cv in cvs.values() if len(cv.get("estudios", [])) > 1]), "numero")

add_q("conteo", "¿Cuántas personas tienen al menos 4 soft skills en su CV?",
      len([cv for cv in cvs.values() if len(cv.get("soft_skills", [])) >= 4]), "numero")


# ═══════════════════════════════════════════════
# CATEGORÍA 8: MULTI-CRITERIO (25 preguntas)
# ═══════════════════════════════════════════════

# 8.1 - Skill + Skill
s1, s2 = next_hs(), next_hs()
r = get_personas_multi_skill([s1, s2])
add_q("multi_criterio", f"¿Qué personas saben tanto {s1} como {s2}?", r)

s1, s2 = next_hs(), next_hs()
r = get_personas_multi_skill([s1, s2])
add_q("multi_criterio", f"Encuentra candidatos que dominen {s1} y también {s2}.", r)

s1, s2 = next_hs(), next_hs()
r = get_personas_multi_skill([s1, s2])
add_q("multi_criterio", f"¿Quiénes combinan en su perfil {s1} junto con {s2}?", r)

# 8.2 - Puesto + Skill
p = next_pu()
s = next_hs()
r = get_personas_puesto_skill(p, s)
add_q("multi_criterio", f"¿Hay algún {p} que además sepa {s}?", r)

p = next_pu()
s = next_hs()
r = get_personas_puesto_skill(p, s)
add_q("multi_criterio", f"Busco un {p} con conocimientos en {s}. ¿Existe?", r)

p = next_pu()
s = next_hs()
r = get_personas_puesto_skill(p, s)
add_q("multi_criterio", f"De los {p}, ¿cuáles tienen también {s} como competencia?", r)

p = next_pu()
s = next_hs()
r = get_personas_puesto_skill(p, s)
add_q("multi_criterio", f"Filtra por puesto {p} y skill {s}. ¿Quiénes cumplen ambos criterios?", r)

# 8.3 - Estudio + Skill
e = next_est()
s = next_hs()
r = get_personas_estudio_skill(e, s)
add_q("multi_criterio", f"¿Quiénes han estudiado {e} y además saben {s}?", r)

e = next_est()
s = next_hs()
r = get_personas_estudio_skill(e, s)
add_q("multi_criterio", f"Localiza personas con formación en {e} que manejen {s}.", r)

# 8.4 - Puesto + Idioma
p = next_pu()
r = [cv["nombre_apellidos"] for cv in cvs.values() 
     if cv.get("puesto") == p and any("Inglés" in o for o in cv.get("otros", []))]
add_q("multi_criterio", f"¿Qué {p} hablan inglés?", r)

p = next_pu()
r = [cv["nombre_apellidos"] for cv in cvs.values()
     if cv.get("puesto") == p and any("Francés" in o for o in cv.get("otros", []))]
add_q("multi_criterio", f"Necesito un {p} que sepa francés. ¿Hay alguno?", r)

# 8.5 - Skill + Experiencia keyword
s = next_hs()
kw = "machine learning"
r = [cv["nombre_apellidos"] for cv in cvs.values()
     if s in cv.get("hard_skills", []) and any(kw in exp.lower() for exp in cv.get("experiencia", []))]
add_q("multi_criterio", f"¿Quiénes saben {s} y tienen experiencia en machine learning?", r)

s = next_hs()
kw = "cloud"
r = [cv["nombre_apellidos"] for cv in cvs.values()
     if s in cv.get("hard_skills", []) and any(kw in exp.lower() for exp in cv.get("experiencia", []))]
add_q("multi_criterio", f"Busco candidatos con la skill {s} que además hayan trabajado con cloud.", r)

# 8.6 - Formación + Puesto
e = next_est()
p = next_pu()
r = [cv["nombre_apellidos"] for cv in cvs.values()
     if cv.get("puesto") == p and e in cv.get("estudios", [])]
add_q("multi_criterio", f"¿Hay algún {p} que tenga {e}?", r)

# 8.7 - Skill + Soft skill
s = next_hs()
ss_keys = list(idx_soft_skill.keys())
random.shuffle(ss_keys)
ss = ss_keys[0]
r = [cv["nombre_apellidos"] for cv in cvs.values()
     if s in cv.get("hard_skills", []) and ss in cv.get("soft_skills", [])]
add_q("multi_criterio", f"¿Qué personas combinan la skill técnica {s} con la competencia de {ss}?", r)

ss = ss_keys[1]
s = next_hs()
r = [cv["nombre_apellidos"] for cv in cvs.values()
     if s in cv.get("hard_skills", []) and ss in cv.get("soft_skills", [])]
add_q("multi_criterio", f"Encuentra candidatos con {s} que además tengan {ss} como soft skill.", r)

# 8.8 - Varias condiciones más
s = next_hs()
r = [cv["nombre_apellidos"] for cv in cvs.values()
     if s in cv.get("hard_skills", []) and any("startup" in o.lower() for o in cv.get("otros", []))]
add_q("multi_criterio", f"¿Quiénes saben {s} y tienen experiencia en startups?", r)

p = next_pu()
r = [cv["nombre_apellidos"] for cv in cvs.values()
     if cv.get("puesto") == p and "Autodidacta" in cv.get("otros", [])]
add_q("multi_criterio", f"De los {p}, ¿cuáles se consideran autodidactas?", r)

s1, s2, s3 = next_hs(), next_hs(), next_hs()
r = [cv["nombre_apellidos"] for cv in cvs.values()
     if all(sk in cv.get("hard_skills", []) for sk in [s1, s2, s3])]
add_q("multi_criterio", f"¿Existe algún candidato que domine simultáneamente {s1}, {s2} y {s3}?", r)

e = next_est()
r = [cv["nombre_apellidos"] for cv in cvs.values()
     if e in cv.get("estudios", []) and any("Inglés" in o for o in cv.get("otros", []))]
add_q("multi_criterio", f"¿Quiénes tienen un {e} y además hablan inglés?", r)

s = next_hs()
r = [cv["nombre_apellidos"] for cv in cvs.values()
     if s in cv.get("hard_skills", []) and len(cv.get("experiencia", [])) >= 3]
add_q("multi_criterio", f"Busco personas con {s} que tengan al menos 3 entradas de experiencia.", r)

p = next_pu()
r = [cv["nombre_apellidos"] for cv in cvs.values()
     if cv.get("puesto") == p and len(cv.get("hard_skills", [])) >= 8]
add_q("multi_criterio", f"¿Qué {p} tienen 8 o más hard skills?", r)

s = next_hs()
r = [cv["nombre_apellidos"] for cv in cvs.values()
     if s in cv.get("hard_skills", []) and any("remoto" in o.lower() or "remota" in o.lower() for o in cv.get("otros", []))]
add_q("multi_criterio", f"¿Hay candidatos con {s} que prefieran trabajar en remoto?", r)

s = next_hs()
r = [cv["nombre_apellidos"] for cv in cvs.values()
     if s in cv.get("hard_skills", []) and len(cv.get("estudios", [])) >= 2]
add_q("multi_criterio", f"Encuentra personas que sepan {s} y que tengan dos o más titulaciones.", r)

p = next_pu()
r = [cv["nombre_apellidos"] for cv in cvs.values()
     if cv.get("puesto") == p and any("bancario" in o.lower() or "banca" in o.lower() for o in cv.get("otros", []))]
add_q("multi_criterio", f"¿Algún {p} con experiencia en el sector bancario?", r)


# ═══════════════════════════════════════════════
# CATEGORÍA 9: EXISTENCIA (SÍ/NO) (15 preguntas)
# ═══════════════════════════════════════════════

s = next_hs()
p = next_pu()
r = any(s in cv.get("hard_skills", []) and cv.get("puesto") == p for cv in cvs.values())
personas_r = [cv["nombre_apellidos"] for cv in cvs.values() if s in cv.get("hard_skills", []) and cv.get("puesto") == p]
add_q("existencia", f"¿Hay alguien que sea {p} y sepa {s}?", 
      {"existe": r, "personas": sorted(personas_r)} if r else {"existe": r}, "booleano_con_detalle")

s = next_hs()
e = next_est()
r = any(s in cv.get("hard_skills", []) and e in cv.get("estudios", []) for cv in cvs.values())
personas_r = [cv["nombre_apellidos"] for cv in cvs.values() if s in cv.get("hard_skills", []) and e in cv.get("estudios", [])]
add_q("existencia", f"¿Existe algún candidato con {s} y titulación en {e}?",
      {"existe": r, "personas": sorted(personas_r)} if r else {"existe": r}, "booleano_con_detalle")

s = "Rust"
r_personas = idx_hard_skill.get(s, [])
add_q("existencia", f"¿Tenemos a alguien en la base de datos que domine {s}?",
      {"existe": len(r_personas) > 0, "personas": sorted(r_personas)}, "booleano_con_detalle")

s = "COBOL"
r_personas = idx_hard_skill.get(s, [])
add_q("existencia", f"¿Alguno de los candidatos menciona {s} en su CV?",
      {"existe": len(r_personas) > 0, "personas": sorted(r_personas)} if r_personas else {"existe": False}, "booleano_con_detalle")

r_personas = get_idioma_personas("Ruso")
add_q("existencia", "¿Contamos con algún profesional que hable ruso?",
      {"existe": len(r_personas) > 0, "personas": sorted(r_personas)} if r_personas else {"existe": False}, "booleano_con_detalle")

r_personas = get_idioma_personas("Árabe")
add_q("existencia", "¿Hay candidatos que sepan árabe?",
      {"existe": len(r_personas) > 0, "personas": sorted(r_personas)} if r_personas else {"existe": False}, "booleano_con_detalle")

s = next_hs()
r = any(s in cv.get("hard_skills", []) and "Autodidacta" in cv.get("otros", []) for cv in cvs.values())
personas_r = [cv["nombre_apellidos"] for cv in cvs.values() if s in cv.get("hard_skills", []) and "Autodidacta" in cv.get("otros", [])]
add_q("existencia", f"¿Hay algún autodidacta que sepa {s}?",
      {"existe": r, "personas": sorted(personas_r)} if r else {"existe": r}, "booleano_con_detalle")

r_personas = [cv["nombre_apellidos"] for cv in cvs.values() if len(cv.get("hard_skills", [])) >= 10]
add_q("existencia", "¿Existe algún candidato con 10 o más hard skills?",
      {"existe": len(r_personas) > 0, "personas": sorted(r_personas)}, "booleano_con_detalle")

r_personas = [cv["nombre_apellidos"] for cv in cvs.values() if len(cv.get("estudios", [])) >= 4]
add_q("existencia", "¿Hay alguien que tenga 4 o más titulaciones académicas?",
      {"existe": len(r_personas) > 0, "personas": sorted(r_personas)}, "booleano_con_detalle")

s1, s2 = next_hs(), next_hs()
r = any(all(sk in cv.get("hard_skills", []) for sk in [s1, s2]) for cv in cvs.values())
personas_r = [cv["nombre_apellidos"] for cv in cvs.values() if all(sk in cv.get("hard_skills", []) for sk in [s1, s2])]
add_q("existencia", f"¿Hay alguien que combine {s1} y {s2} en sus habilidades?",
      {"existe": r, "personas": sorted(personas_r)} if r else {"existe": r}, "booleano_con_detalle")

r_personas = [cv["nombre_apellidos"] for cv in cvs.values()
              if any("disponibilidad inmediata" in o.lower() for o in cv.get("otros", []))
              and any("Inglés" in o for o in cv.get("otros", []))]
add_q("existencia", "¿Tenemos candidatos con disponibilidad inmediata que hablen inglés?",
      {"existe": len(r_personas) > 0, "personas": sorted(r_personas)} if r_personas else {"existe": False}, "booleano_con_detalle")

r_personas = [cv["nombre_apellidos"] for cv in cvs.values()
              if len(cv.get("experiencia", [])) >= 5]
add_q("existencia", "¿Existe algún candidato con 5 o más entradas de experiencia?",
      {"existe": len(r_personas) > 0, "personas": sorted(r_personas)} if r_personas else {"existe": False}, "booleano_con_detalle")

r_personas = [cv["nombre_apellidos"] for cv in cvs.values()
              if any("Alemán" in o for o in cv.get("otros", []))
              and any("Francés" in o for o in cv.get("otros", []))]
add_q("existencia", "¿Hay alguien que hable tanto alemán como francés?",
      {"existe": len(r_personas) > 0, "personas": sorted(r_personas)} if r_personas else {"existe": False}, "booleano_con_detalle")

r_personas = [cv["nombre_apellidos"] for cv in cvs.values()
              if any("Contributor" in o or "open source" in o.lower() or "Open Source" in o for o in cv.get("otros", []))]
add_q("existencia", "¿Algún candidato menciona contribuciones a proyectos open source?",
      {"existe": len(r_personas) > 0, "personas": sorted(r_personas)} if r_personas else {"existe": False}, "booleano_con_detalle")

r_personas = [cv["nombre_apellidos"] for cv in cvs.values()
              if any("mentor" in o.lower() for o in cv.get("otros", []))]
add_q("existencia", "¿Hay profesionales que indiquen experiencia como mentores?",
      {"existe": len(r_personas) > 0, "personas": sorted(r_personas)} if r_personas else {"existe": False}, "booleano_con_detalle")


# ═══════════════════════════════════════════════
# CATEGORÍA 10: AGREGACIÓN / RANKING (20 preguntas)
# ═══════════════════════════════════════════════

# Top N hard skills más comunes
top5_hs = hard_skill_counts.most_common(5)
add_q("agregacion", "¿Cuáles son las 5 hard skills más frecuentes entre todos los candidatos?",
      [{"skill": s, "frecuencia": c} for s, c in top5_hs], "ranking")

top10_hs = hard_skill_counts.most_common(10)
add_q("agregacion", "Dame un ranking de las 10 habilidades técnicas más repetidas en los CVs.",
      [{"skill": s, "frecuencia": c} for s, c in top10_hs], "ranking")

# Top soft skills
top5_ss = soft_skill_counts.most_common(5)
add_q("agregacion", "¿Cuáles son las 5 soft skills más habituales entre los profesionales?",
      [{"skill": s, "frecuencia": c} for s, c in top5_ss], "ranking")

# Top puestos
top5_p = puesto_counts.most_common(5)
add_q("agregacion", "¿Cuáles son los 5 puestos de trabajo más comunes en la base de datos?",
      [{"puesto": p, "frecuencia": c} for p, c in top5_p], "ranking")

top3_p = puesto_counts.most_common(3)
add_q("agregacion", "Dime los 3 roles profesionales con mayor representación.",
      [{"puesto": p, "frecuencia": c} for p, c in top3_p], "ranking")

# Top estudios
top5_e = estudio_counts.most_common(5)
add_q("agregacion", "¿Qué 5 titulaciones son las más frecuentes entre los candidatos?",
      [{"estudio": e, "frecuencia": c} for e, c in top5_e], "ranking")

# Persona con más hard skills
max_hs_persona = max(skills_per_person.items(), key=lambda x: x[1]["hard"])
add_q("agregacion", "¿Quién es la persona con más hard skills? ¿Cuántas tiene?",
      {"persona": max_hs_persona[0], "cantidad": max_hs_persona[1]["hard"]}, "valor_con_detalle")

# Persona con más soft skills
max_ss_persona = max(skills_per_person.items(), key=lambda x: x[1]["soft"])
add_q("agregacion", "¿Qué candidato tiene el mayor número de soft skills?",
      {"persona": max_ss_persona[0], "cantidad": max_ss_persona[1]["soft"]}, "valor_con_detalle")

# Persona con más estudios
max_est_persona = max(skills_per_person.items(), key=lambda x: x[1]["estudios"])
add_q("agregacion", "¿Quién acumula más titulaciones académicas en su CV?",
      {"persona": max_est_persona[0], "cantidad": max_est_persona[1]["estudios"]}, "valor_con_detalle")

# Persona con más experiencia (entradas)
max_exp_persona = max(skills_per_person.items(), key=lambda x: x[1]["experiencia"])
add_q("agregacion", "¿Qué persona tiene más entradas de experiencia laboral?",
      {"persona": max_exp_persona[0], "cantidad": max_exp_persona[1]["experiencia"]}, "valor_con_detalle")

# Media de hard skills
avg_hs = round(sum(sp["hard"] for sp in skills_per_person.values()) / len(skills_per_person), 2)
add_q("agregacion", "¿Cuál es la media de hard skills por candidato?",
      avg_hs, "numero")

# Media de soft skills
avg_ss = round(sum(sp["soft"] for sp in skills_per_person.values()) / len(skills_per_person), 2)
add_q("agregacion", "¿Cuál es el promedio de soft skills por persona?",
      avg_ss, "numero")

# Hard skill menos común
bottom5_hs = hard_skill_counts.most_common()[-5:]
add_q("agregacion", "¿Cuáles son las 5 hard skills menos frecuentes en toda la base?",
      [{"skill": s, "frecuencia": c} for s, c in bottom5_hs], "ranking")

# Puesto menos común
bottom3_p = puesto_counts.most_common()[-3:]
add_q("agregacion", "¿Qué 3 puestos de trabajo son los menos comunes?",
      [{"puesto": p, "frecuencia": c} for p, c in bottom3_p], "ranking")

# Distribución: cuántas personas tienen exactamente N hard skills
hs_distribution = Counter(sp["hard"] for sp in skills_per_person.values())
add_q("agregacion", "¿Cómo se distribuyen los candidatos según su número de hard skills?",
      {str(k): v for k, v in sorted(hs_distribution.items())}, "distribucion")

# Los 5 idiomas más mencionados (de 'otros')
idiomas_keywords = ["Inglés", "Francés", "Alemán", "Italiano", "Portugués", "Chino", "Japonés", "Árabe", "Ruso", "Coreano", "Rumano"]
idioma_counts = {}
for kw in idiomas_keywords:
    cnt = len(get_idioma_personas(kw))
    if cnt > 0:
        idioma_counts[kw] = cnt
top_idiomas = sorted(idioma_counts.items(), key=lambda x: -x[1])[:5]
add_q("agregacion", "¿Cuáles son los 5 idiomas más mencionados por los candidatos?",
      [{"idioma": i, "frecuencia": c} for i, c in top_idiomas], "ranking")

# Persona con más entradas en 'otros'
max_otros = max(skills_per_person.items(), key=lambda x: x[1]["otros"])
add_q("agregacion", "¿Quién tiene más información adicional (otros) en su perfil?",
      {"persona": max_otros[0], "cantidad": max_otros[1]["otros"]}, "valor_con_detalle")

# Total de skills únicas (hard + soft)
add_q("agregacion", "¿Cuántas competencias únicas (hard + soft) se recogen en toda la base de datos?",
      len(idx_hard_skill) + len(idx_soft_skill), "numero")

# Persona con más competencias totales
max_total = max(skills_per_person.items(), key=lambda x: x[1]["total"])
add_q("agregacion", "¿Qué candidato acumula el mayor número de competencias en total (hard + soft)?",
      {"persona": max_total[0], "hard_skills": max_total[1]["hard"], "soft_skills": max_total[1]["soft"], "total": max_total[1]["total"]}, "valor_con_detalle")

# Top 3 estudios con más personas
top3_e = estudio_counts.most_common(3)
add_q("agregacion", "Clasifica las 3 formaciones académicas más populares y cuántas personas las han cursado.",
      [{"estudio": e, "frecuencia": c} for e, c in top3_e], "ranking")


# ═══════════════════════════════════════════════
# CATEGORÍA EXTRA: BÚSQUEDA POR SOFT SKILL (10 preguntas)
# ═══════════════════════════════════════════════

ss_all = list(idx_soft_skill.keys())
random.shuffle(ss_all)
ss_iter = iter(ss_all)

def next_ss():
    return next(ss_iter)

ss = next_ss()
add_q("busqueda_por_soft_skill", f"¿Qué personas tienen {ss} como soft skill?", idx_soft_skill[ss])

ss = next_ss()
add_q("busqueda_por_soft_skill", f"Lista a los candidatos que mencionan {ss} entre sus competencias blandas.", idx_soft_skill[ss])

ss = next_ss()
add_q("busqueda_por_soft_skill", f"¿Quiénes destacan por su {ss} según los CVs?", idx_soft_skill[ss])

ss = next_ss()
add_q("busqueda_por_soft_skill", f"Dame todos los profesionales cuya soft skill incluya {ss}.", idx_soft_skill[ss])

ss = next_ss()
add_q("busqueda_por_soft_skill", f"Identifica a quienes poseen la competencia de {ss}.", idx_soft_skill[ss])

ss = next_ss()
add_q("busqueda_por_soft_skill", f"¿Cuáles candidatos reflejan {ss} como habilidad interpersonal?", idx_soft_skill[ss])

ss = next_ss()
add_q("busqueda_por_soft_skill", f"Busca perfiles que incluyan {ss} entre sus aptitudes personales.", idx_soft_skill[ss])

ss = next_ss()
add_q("busqueda_por_soft_skill", f"¿Hay personas que se caractericen por su {ss}?", idx_soft_skill[ss])

ss = next_ss()
add_q("busqueda_por_soft_skill", f"Encuentra a los candidatos que tienen {ss} en su currículum.", idx_soft_skill[ss])

ss = next_ss()
add_q("busqueda_por_soft_skill", f"¿Qué miembros del equipo cuentan con {ss} como competencia blanda?", idx_soft_skill[ss])


# ═══════════════════════════════════════════════
# CATEGORÍA EXTRA: PREGUNTAS DE EXPERIENCIA POR KEYWORD (10 preguntas)
# ═══════════════════════════════════════════════

keywords_exp = ["machine learning", "cloud", "microservicios", "DevOps", "ágil", 
                "API", "datos", "seguridad", "liderazgo", "automatiz"]

add_q("busqueda_por_experiencia", "¿Qué personas tienen experiencia en machine learning?",
      get_experiencia_keyword("machine learning"))

add_q("busqueda_por_experiencia", "Dame los candidatos cuya experiencia mencione proyectos cloud.",
      get_experiencia_keyword("cloud"))

add_q("busqueda_por_experiencia", "¿Quiénes han trabajado con microservicios según su CV?",
      get_experiencia_keyword("microservicio"))

add_q("busqueda_por_experiencia", "Encuentra a los profesionales con experiencia en DevOps.",
      get_experiencia_keyword("DevOps"))

add_q("busqueda_por_experiencia", "¿Qué candidatos mencionan metodologías ágiles en su experiencia?",
      get_experiencia_keyword("ágil"))

add_q("busqueda_por_experiencia", "Identifica a quienes tienen experiencia desarrollando APIs.",
      get_experiencia_keyword("API"))

add_q("busqueda_por_experiencia", "¿Quiénes reflejan en su experiencia trabajo con datos o análisis de datos?",
      get_experiencia_keyword("datos"))

add_q("busqueda_por_experiencia", "Localiza candidatos con experiencia en seguridad o ciberseguridad.",
      get_experiencia_keyword("seguridad"))

add_q("busqueda_por_experiencia", "¿Qué personas han tenido roles de liderazgo según su experiencia?",
      get_experiencia_keyword("liderazgo"))

add_q("busqueda_por_experiencia", "Busca profesionales cuya experiencia incluya automatización de procesos.",
      get_experiencia_keyword("automatiz"))


# ═══════════════════════════════════════════════
# FILTRO: REDUCIR A 80-100 PREGUNTAS
# ═══════════════════════════════════════════════
from difflib import SequenceMatcher as _SM

def _sim(a, b):
    return _SM(None, a.lower(), b.lower()).ratio()

def _remove_similar(qs, field, threshold=0.6):
    kept = []
    for q in qs:
        if not any(_sim(q[field], k[field]) > threshold for k in kept):
            kept.append(q)
    return kept

_TARGET = 90
_by_cat = defaultdict(list)
for q in preguntas:
    _by_cat[q["categoria"]].append(q)

_filtered = {}
for cat, qs in _by_cat.items():
    _filtered[cat] = _remove_similar(qs, "pregunta")

_total_f = sum(len(v) for v in _filtered.values())
_selected = []
for cat, qs in sorted(_filtered.items()):
    n = max(2, round(len(qs) / _total_f * _TARGET))
    _selected.extend(qs[:n])

if len(_selected) > 100:
    _selected = _selected[:100]
elif len(_selected) < 80:
    _remaining = [q for cat, qs in sorted(_filtered.items()) for q in qs if q not in _selected]
    _selected.extend(_remaining[:80 - len(_selected)])

_selected.sort(key=lambda q: q["id"])
for i, q in enumerate(_selected, 1):
    q["id"] = i

print(f"\n→ Reducido de {len(preguntas)} a {len(_selected)} preguntas (objetivo: 80-100)")
preguntas = _selected

# ═══════════════════════════════════════════════
# VERIFICACIÓN Y EXPORTACIÓN
# ═══════════════════════════════════════════════

# Verificar que todas las preguntas son distintas
textos = [q["pregunta"] for q in preguntas]
if len(textos) != len(set(textos)):
    dupes = [t for t in textos if textos.count(t) > 1]
    print(f"ADVERTENCIA: {len(dupes)} preguntas duplicadas detectadas")
else:
    print("✓ Todas las preguntas son únicas")

print(f"Total de preguntas generadas: {len(preguntas)}")

# Contar por categoría
cat_counts = Counter(q["categoria"] for q in preguntas)
print("\nDistribución por categoría:")
for cat, cnt in sorted(cat_counts.items()):
    print(f"  {cat}: {cnt}")

# Construir JSON final
gold_standard = {
    "gold_standard": {
        "caso_uso": "cvs",
        "idioma": "es",
        "total_preguntas": len(preguntas),
        "total_cvs_analizados": len(cvs),
        "fecha_generacion": "2026-04-17",
        "categorias": dict(sorted(cat_counts.items())),
        "descripcion": "Gold standard para evaluar un sistema RAG sobre una base de datos de CVs en español. "
                       "Contiene preguntas de búsqueda por skills, puestos, formación, idiomas, consultas "
                       "individuales, conteo, filtros multi-criterio, existencia y agregación/ranking. "
                       "Todas las respuestas han sido computadas directamente de los datos fuente.",
        "preguntas": preguntas
    }
}

output_path = OUTPUT_DIR / "gold_standard_cvs_es.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(gold_standard, f, ensure_ascii=False, indent=2)

print(f"\n✓ Gold standard guardado en: {output_path}")
