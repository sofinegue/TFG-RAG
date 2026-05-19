"""
Script to generate the Gold Standard for the CVs use case in English.
Generates 80-100 unique questions with answers computed directly from the data.
Author: Auto-generated for TFG
Date: 2026-04-17
    python -m src.test.scripts.gold_standard.generate_gold_standard_cvs_en
"""
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
random.seed(42)
# ─────────────────────────────────────────────
# 1. LOAD ALL CVs
# ─────────────────────────────────────────────
CV_DIR = Path(__file__).parent.parent.parent / "data" / "cvs" / "en"
OUTPUT_DIR = Path(__file__).parent.parent / "data"
cvs = {}
for f in sorted(CV_DIR.glob("cv_*.json")):
    with open(f, encoding="utf-8") as fh:
        cv = json.load(fh)
        cv_id = f.stem
        cvs[cv_id] = cv
print(f"Loaded {len(cvs)} CVs")
# ─────────────────────────────────────────────
# 2. BUILD INVERTED INDEXES
# ─────────────────────────────────────────────
idx_hard_skill = defaultdict(list)
idx_soft_skill = defaultdict(list)
idx_puesto = defaultdict(list)
idx_estudio = defaultdict(list)
idx_otro = defaultdict(list)
idx_nombre_cv = {}
for cv_id, cv in cvs.items():
    nombre = cv["nombre_apellidos"]
    idx_nombre_cv[nombre] = cv_id
    for s in cv.get("hard_skills", []):
        idx_hard_skill[s].append(nombre)
    for s in cv.get("soft_skills", []):
        idx_soft_skill[s].append(nombre)
    idx_puesto[cv.get("puesto", "")].append(nombre)
    for e in cv.get("estudios", []):
        idx_estudio[e].append(nombre)
    for o in cv.get("otros", []):
        idx_otro[o].append(nombre)
hard_skill_counts = Counter()
soft_skill_counts = Counter()
puesto_counts = Counter()
estudio_counts = Counter()
skills_per_person = {}
for cv_id, cv in cvs.items():
    nombre = cv["nombre_apellidos"]
    hs = cv.get("hard_skills", [])
    ss = cv.get("soft_skills", [])
    hard_skill_counts.update(hs)
    soft_skill_counts.update(ss)
    puesto_counts[cv.get("puesto", "")] += 1
    estudio_counts.update(cv.get("estudios", []))
    skills_per_person[nombre] = {
        "hard": len(hs), "soft": len(ss), "total": len(hs) + len(ss),
        "estudios": len(cv.get("estudios", [])),
        "experiencia": len(cv.get("experiencia", [])),
        "otros": len(cv.get("otros", []))
    }
def get_lang_personas(keyword):
    result = []
    for cv in cvs.values():
        for o in cv.get("otros", []):
            if keyword.lower() in o.lower():
                result.append(cv["nombre_apellidos"])
                break
    return result
def get_exp_keyword(keyword):
    result = []
    for cv in cvs.values():
        for exp in cv.get("experiencia", []):
            if keyword.lower() in exp.lower():
                result.append(cv["nombre_apellidos"])
                break
    return result
# ─────────────────────────────────────────────
# 3. GENERATE QUESTIONS
# ─────────────────────────────────────────────
preguntas = []
q_id = 0
def add_q(cat, question, answer, ans_type="person_list", cv_ref=None):
    global q_id
    q_id += 1
    entry = {"id": q_id, "categoria": cat, "pregunta": question, "tipo_respuesta": ans_type}
    if isinstance(answer, list):
        try:
            entry["respuesta"] = sorted(answer)
        except TypeError:
            entry["respuesta"] = answer
        entry["num_resultados"] = len(answer)
    else:
        entry["respuesta"] = answer
    if cv_ref:
        entry["cv_referencia"] = cv_ref
    preguntas.append(entry)
# Iteradores
hs_keys = list(idx_hard_skill.keys()); random.shuffle(hs_keys); hs_it = iter(hs_keys)
pu_keys = list(idx_puesto.keys()); random.shuffle(pu_keys); pu_it = iter(pu_keys)
est_keys = list(idx_estudio.keys()); random.shuffle(est_keys); est_it = iter(est_keys)
ss_keys = list(idx_soft_skill.keys()); random.shuffle(ss_keys); ss_it = iter(ss_keys)
per_keys = list(idx_nombre_cv.keys()); random.shuffle(per_keys); per_it = iter(per_keys)
per_exp = [n for n in idx_nombre_cv if len(cvs[idx_nombre_cv[n]].get("experiencia", [])) > 0]
random.shuffle(per_exp); exp_it = iter(per_exp)
def nhs(): return next(hs_it)
def npu(): return next(pu_it)
def nest(): return next(est_it)
def nss(): return next(ss_it)
def nper():
    n = next(per_it); return n, idx_nombre_cv[n], cvs[idx_nombre_cv[n]]
def nexp():
    n = next(exp_it); return n, idx_nombre_cv[n], cvs[idx_nombre_cv[n]]
# ═══════════════════════════════════════════════
# CAT 1: SEARCH BY HARD SKILL (25)
# ═══════════════════════════════════════════════
s=nhs(); add_q("search_by_skill", f"Which people are proficient in {s}?", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"I need a complete list of candidates who know {s}.", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"Give me the names of all professionals with expertise in {s}.", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"Who has {s} among their technical skills?", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"I'm looking for profiles that include {s} on their CV. Who are they?", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"list every person whose resume reflects experience with {s}.", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"Which candidates are known to work with {s}?", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"Identify the professionals who have {s} as a technical competency.", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"Could you tell me who possesses the {s} skill?", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"For a project requiring {s}, which people are available?", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"Show me all candidates with {s} in their profile.", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"Is there anyone in the database who knows {s}? Who are they?", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"Compile a list of people who have {s} in their hard skills.", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"I'm assembling a team that needs {s}. Whom should I consider?", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"Which candidates mention {s} among their competencies?", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"Tell me every person who appears with the skill {s}.", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"What profiles stand out for knowing {s}?", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"Filter the CVs and return only those containing {s}.", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"Provide the list of employees who use {s} in their work.", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"Who among our candidates claims to know {s}?", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"Gather the names of those with training or experience in {s}.", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"According to available CVs, which people are familiar with {s}?", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"Are there any professionals in our database with {s}? list them.", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"Extract from the system everyone who has {s} as a skill.", idx_hard_skill[s])
s=nhs(); add_q("search_by_skill", f"To whom could we assign {s} tasks based on their CV?", idx_hard_skill[s])
# ═══════════════════════════════════════════════
# CAT 2: SEARCH BY POSITION (20)
# ═══════════════════════════════════════════════
p=npu(); add_q("search_by_position", f"Who works as a {p}?", idx_puesto[p])
p=npu(); add_q("search_by_position", f"Give me the list of people whose position is {p}.", idx_puesto[p])
p=npu(); add_q("search_by_position", f"I need to know which candidates hold the role of {p}.", idx_puesto[p])
p=npu(); add_q("search_by_position", f"How many and which professionals are listed as {p} in their CVs?", idx_puesto[p], "person_list_with_count")
p=npu(); add_q("search_by_position", f"State all names of those who serve as {p}.", idx_puesto[p])
p=npu(); add_q("search_by_position", f"Which people currently hold the title of {p}?", idx_puesto[p])
p=npu(); add_q("search_by_position", f"Locate in the database every {p}.", idx_puesto[p])
p=npu(); add_q("search_by_position", f"Could you tell me who the registered {p}s are?", idx_puesto[p])
p=npu(); add_q("search_by_position", f"Display the complete list of candidates with the position of {p}.", idx_puesto[p])
p=npu(); add_q("search_by_position", f"Do we have any {p}s on the team? Tell me their names.", idx_puesto[p])
p=npu(); add_q("search_by_position", f"Select all people who work as {p}.", idx_puesto[p])
p=npu(); add_q("search_by_position", f"I'm looking for someone who is a {p}. Who is available?", idx_puesto[p])
p=npu(); add_q("search_by_position", f"From the set of CVs, identify those who present themselves as {p}.", idx_puesto[p])
p=npu(); add_q("search_by_position", f"Who has {p} as their professional title?", idx_puesto[p])
p=npu(); add_q("search_by_position", f"Retrieve all professionals categorized under the position {p}.", idx_puesto[p])
p=npu(); add_q("search_by_position", f"I'm interested in hiring a {p}. What options are in the database?", idx_puesto[p])
p=npu(); add_q("search_by_position", f"For which people is their position indicated as {p}?", idx_puesto[p])
p=npu(); add_q("search_by_position", f"If I filter by position = '{p}', what names appear?", idx_puesto[p])
p=npu(); add_q("search_by_position", f"Are there candidates whose current role is {p}? Enumerate them.", idx_puesto[p])
p=npu(); add_q("search_by_position", f"Return a list of available {p}s.", idx_puesto[p])
# ═══════════════════════════════════════════════
# CAT 3: SEARCH BY EDUCATION (20)
# ═══════════════════════════════════════════════
e=nest(); add_q("search_by_education", f"Who has studied {e}?", idx_estudio[e])
e=nest(); add_q("search_by_education", f"list all candidates who hold a degree in {e}.", idx_estudio[e])
e=nest(); add_q("search_by_education", f"Which people in the database completed {e}?", idx_estudio[e])
e=nest(); add_q("search_by_education", f"Tell me the names of those who have the qualification {e}.", idx_estudio[e])
e=nest(); add_q("search_by_education", f"Which candidates include {e} in their academic background?", idx_estudio[e])
e=nest(); add_q("search_by_education", f"I need to identify everyone with studies in {e}.", idx_estudio[e])
e=nest(); add_q("search_by_education", f"Search the CVs for people whose education includes {e}.", idx_estudio[e])
e=nest(); add_q("search_by_education", f"Are there professionals with a {e}? Who are they?", idx_estudio[e])
e=nest(); add_q("search_by_education", f"Extract the list of people who graduated in {e}.", idx_estudio[e])
e=nest(); add_q("search_by_education", f"Show me candidates whose education includes {e}.", idx_estudio[e])
e=nest(); add_q("search_by_education", f"Who is recorded as having completed {e}?", idx_estudio[e])
e=nest(); add_q("search_by_education", f"Which team members have training in {e}?", idx_estudio[e])
e=nest(); add_q("search_by_education", f"Enumerate the professionals with a qualification in {e}.", idx_estudio[e])
e=nest(); add_q("search_by_education", f"Which of the candidates holds a {e}?", idx_estudio[e])
e=nest(); add_q("search_by_education", f"Among all CVs, which ones reflect {e} as a study?", idx_estudio[e])
e=nest(); add_q("search_by_education", f"Filter by education and give me the people with {e}.", idx_estudio[e])
e=nest(); add_q("search_by_education", f"Can you find out who has a {e} on their resume?", idx_estudio[e])
e=nest(); add_q("search_by_education", f"Provide the candidates who hold {e}.", idx_estudio[e])
e=nest(); add_q("search_by_education", f"Which people's profiles show they studied {e}?", idx_estudio[e])
e=nest(); add_q("search_by_education", f"Check the database and tell me who has {e} as a qualification.", idx_estudio[e])
# ═══════════════════════════════════════════════
# CAT 4: SEARCH BY LANGUAGE / OTHER (15)
# ═══════════════════════════════════════════════
add_q("search_by_language", "Which candidates speak French at any level?", get_lang_personas("French"))
add_q("search_by_language", "Give me all professionals who have Spanish on their CV.", get_lang_personas("Spanish"))
add_q("search_by_language", "Who declares knowledge of German at any level?", get_lang_personas("German"))
add_q("search_by_language", "I need people who speak Portuguese. Are there any?", get_lang_personas("Portuguese"))
add_q("search_by_language", "Identify candidates with Italian mentioned in their profile.", get_lang_personas("Italian"))
add_q("search_by_language", "Show me who has Japanese as a language.", get_lang_personas("Japanese"))
add_q("search_by_language", "Which professionals mention Chinese or Mandarin in their profile?", get_lang_personas("Chinese") + get_lang_personas("Mandarin"))
add_q("search_by_language", "Find people who identify as self-taught.",
      [cv["nombre_apellidos"] for cv in cvs.values() if any("self-taught" in o.lower() or "autodidact" in o.lower() or "Self-taught" in o for o in cv.get("otros", []))])
add_q("search_by_language", "Which candidates prefer remote work?",
      [cv["nombre_apellidos"] for cv in cvs.values() if any("remote" in o.lower() for o in cv.get("otros", []))])
add_q("search_by_language", "Who has startup experience according to their CV?",
      [cv["nombre_apellidos"] for cv in cvs.values() if any("startup" in o.lower() for o in cv.get("otros", []))])
add_q("search_by_language", "list candidates who mention immediate availability.",
      [cv["nombre_apellidos"] for cv in cvs.values() if any("immediate" in o.lower() or "available now" in o.lower() for o in cv.get("otros", []))])
add_q("search_by_language", "Which people indicate they are conference speakers?",
      [cv["nombre_apellidos"] for cv in cvs.values() if any("speaker" in o.lower() for o in cv.get("otros", []))])
add_q("search_by_language", "Are there candidates with banking sector experience?",
      [cv["nombre_apellidos"] for cv in cvs.values() if any("banking" in o.lower() or "bank" in o.lower() for o in cv.get("otros", []))])
add_q("search_by_language", "Who is open to relocation based on their profile?",
      [cv["nombre_apellidos"] for cv in cvs.values() if any("relocation" in o.lower() for o in cv.get("otros", []))])
add_q("search_by_language", "Find candidates who have Scrum Master certification.",
      [cv["nombre_apellidos"] for cv in cvs.values() if any("scrum master" in o.lower() for o in cv.get("otros", []))])
# ═══════════════════════════════════════════════
# CAT 5: INDIVIDUAL QUERY (25)
# ═══════════════════════════════════════════════
n,cid,cv=nper(); add_q("individual_query", f"What is {n}'s position?", cv["puesto"], "single_value", cid)
n,cid,cv=nper(); add_q("individual_query", f"Tell me the hard skills that {n} has.", cv.get("hard_skills",[]), "skill_list", cid)
n,cid,cv=nper(); add_q("individual_query", f"What academic background appears on {n}'s CV?", cv.get("estudios",[]), "education_list", cid)
n,cid,cv=nper(); add_q("individual_query", f"What are {n}'s soft skills?", cv.get("soft_skills",[]), "skill_list", cid)
n,cid,cv=nper(); add_q("individual_query", f"Look up {n}'s profile and tell me their current position.", cv["puesto"], "single_value", cid)
n,cid,cv=nper(); add_q("individual_query", f"What additional information (others) is on {n}'s CV?", cv.get("otros",[]), "other_list", cid)
n,cid,cv=nper(); add_q("individual_query", f"I'd like to know what technical abilities {n} possesses.", cv.get("hard_skills",[]), "skill_list", cid)
n,cid,cv=nper(); add_q("individual_query", f"What does {n} do for a living?", cv["puesto"], "single_value", cid)
n,cid,cv=nper(); add_q("individual_query", f"What education does {n} have? Give me their studies.", cv.get("estudios",[]), "education_list", cid)
n,cid,cv=nper(); add_q("individual_query", f"I want to see {n}'s full profile. What interpersonal skills do they have?", cv.get("soft_skills",[]), "skill_list", cid)
n,cid,cv=nper(); add_q("individual_query", f"Describe {n}'s technical competencies.", cv.get("hard_skills",[]), "skill_list", cid)
n,cid,cv=nper(); add_q("individual_query", f"What role does {n} hold according to their resume?", cv["puesto"], "single_value", cid)
n,cid,cv=nper(); add_q("individual_query", f"Tell me what degrees {n} has obtained.", cv.get("estudios",[]), "education_list", cid)
n,cid,cv=nper(); add_q("individual_query", f"Does {n} have any certifications, languages, or other relevant info?", cv.get("otros",[]), "other_list", cid)
n,cid,cv=nper(); add_q("individual_query", f"I need to know the technologies {n} works with.", cv.get("hard_skills",[]), "skill_list", cid)
n,cid,cv=nper(); add_q("individual_query", f"What is {n}'s professional designation?", cv["puesto"], "single_value", cid)
n,cid,cv=nper(); add_q("individual_query", f"Review {n}'s CV and extract their personal aptitudes.", cv.get("soft_skills",[]), "skill_list", cid)
n,cid,cv=nper(); add_q("individual_query", f"What qualifications are listed on {n}'s profile?", cv.get("estudios",[]), "education_list", cid)
n,cid,cv=nper(); add_q("individual_query", f"Provide me with the technical skills shown on {n}'s CV.", cv.get("hard_skills",[]), "skill_list", cid)
n,cid,cv=nper(); add_q("individual_query", f"What role does {n} perform?", cv["puesto"], "single_value", cid)
n,cid,cv=nper(); add_q("individual_query", f"What supplementary data is on {n}'s profile?", cv.get("otros",[]), "other_list", cid)
n,cid,cv=nper(); add_q("individual_query", f"Indicate the tools and languages {n} masters.", cv.get("hard_skills",[]), "skill_list", cid)
n,cid,cv=nper(); add_q("individual_query", f"What interpersonal qualities are attributed to {n}?", cv.get("soft_skills",[]), "skill_list", cid)
n,cid,cv=nper(); add_q("individual_query", f"I would like to know {n}'s educational background. Can you help?", cv.get("estudios",[]), "education_list", cid)
n,cid,cv=nper(); add_q("individual_query", f"What job title does {n} hold according to the available data?", cv["puesto"], "single_value", cid)
# ═══════════════════════════════════════════════
# CAT 6: EXPERIENCE QUERY (15)
# ═══════════════════════════════════════════════
n,cid,cv=nexp(); add_q("experience_query", f"What has {n} worked on?", cv.get("experiencia",[]), "experience_list", cid)
n,cid,cv=nexp(); add_q("experience_query", f"Describe {n}'s professional experience.", cv.get("experiencia",[]), "experience_list", cid)
n,cid,cv=nexp(); add_q("experience_query", f"What work experience does {n} have on record?", cv.get("experiencia",[]), "experience_list", cid)
n,cid,cv=nexp(); add_q("experience_query", f"Give me a summary of {n}'s career path.", cv.get("experiencia",[]), "experience_list", cid)
n,cid,cv=nexp(); add_q("experience_query", f"What functions has {n} performed according to their CV?", cv.get("experiencia",[]), "experience_list", cid)
n,cid,cv=nexp(); add_q("experience_query", f"I'm interested in {n}'s professional background.", cv.get("experiencia",[]), "experience_list", cid)
n,cid,cv=nexp(); add_q("experience_query", f"What tasks and roles has {n} had throughout their career?", cv.get("experiencia",[]), "experience_list", cid)
n,cid,cv=nexp(); add_q("experience_query", f"Walk me through the experience detailed in {n}'s profile.", cv.get("experiencia",[]), "experience_list", cid)
n,cid,cv=nexp(); add_q("experience_query", f"What projects or areas has {n} been involved in?", cv.get("experiencia",[]), "experience_list", cid)
n,cid,cv=nexp(); add_q("experience_query", f"Check {n}'s experience section and tell me what it says.", cv.get("experiencia",[]), "experience_list", cid)
n,cid,cv=nexp(); add_q("experience_query", f"What professional background does {n} have?", cv.get("experiencia",[]), "experience_list", cid)
n,cid,cv=nexp(); add_q("experience_query", f"Tell me about {n}'s professional track record.", cv.get("experiencia",[]), "experience_list", cid)
n,cid,cv=nexp(); add_q("experience_query", f"Can you detail what {n} has been involved in?", cv.get("experiencia",[]), "experience_list", cid)
n,cid,cv=nexp(); add_q("experience_query", f"I'd like to review {n}'s accumulated experience.", cv.get("experiencia",[]), "experience_list", cid)
n,cid,cv=nexp(); add_q("experience_query", f"Share the previous responsibilities listed on {n}'s CV.", cv.get("experiencia",[]), "experience_list", cid)
# ═══════════════════════════════════════════════
# CAT 7: COUNTING (20)
# ═══════════════════════════════════════════════
s=nhs(); add_q("counting", f"How many people know {s}?", len(idx_hard_skill[s]), "number")
s=nhs(); add_q("counting", f"What is the total number of candidates proficient in {s}?", len(idx_hard_skill[s]), "number")
p=npu(); add_q("counting", f"How many {p}s are registered in the database?", len(idx_puesto[p]), "number")
e=nest(); add_q("counting", f"How many people studied {e}?", len(idx_estudio[e]), "number")
add_q("counting", "How many CVs are there in total in the system?", len(cvs), "number")
add_q("counting", "How many distinct positions exist among all candidates?", len(set(cv["puesto"] for cv in cvs.values())), "number")
s=nhs(); add_q("counting", f"Count the professionals who include {s} in their competencies.", len(idx_hard_skill[s]), "number")
p=npu(); add_q("counting", f"Tell me how many people work as {p}.", len(idx_puesto[p]), "number")
add_q("counting", "How many different hard skills are mentioned across all CVs?", len(idx_hard_skill), "number")
add_q("counting", "How many distinct qualifications appear in the database?", len(idx_estudio), "number")
s=nhs(); add_q("counting", f"How many candidates can be attributed knowledge of {s}?", len(idx_hard_skill[s]), "number")
add_q("counting", "How many distinct soft skills are collected across all CVs?", len(idx_soft_skill), "number")
add_q("counting", "Of all candidates, how many have at least one work experience entry?",
      len([cv for cv in cvs.values() if len(cv.get("experiencia",[])) > 0]), "number")
add_q("counting", "How many people have no experience reflected on their CV?",
      len([cv for cv in cvs.values() if len(cv.get("experiencia",[])) == 0]), "number")
add_q("counting", "How many candidates speak at least one language besides English?",
      len([cv for cv in cvs.values() if any(
          any(lang in o for lang in ["French","German","Italian","Portuguese","Chinese","Japanese","Arabic","Russian","Korean","Spanish"])
          for o in cv.get("otros",[]))]), "number")
e=nest(); add_q("counting", f"How many professionals have {e} in their education?", len(idx_estudio[e]), "number")
add_q("counting", "How many candidates have more than 5 hard skills on their profile?",
      len([cv for cv in cvs.values() if len(cv.get("hard_skills",[])) > 5]), "number")
add_q("counting", "How many candidates have more than one academic qualification?",
      len([cv for cv in cvs.values() if len(cv.get("estudios",[])) > 1]), "number")
add_q("counting", "How many people have at least 4 soft skills on their CV?",
      len([cv for cv in cvs.values() if len(cv.get("soft_skills",[])) >= 4]), "number")
add_q("counting", "How many candidates are open to relocation?",
      len([cv for cv in cvs.values() if any("relocation" in o.lower() for o in cv.get("otros",[]))]), "number")
# ═══════════════════════════════════════════════
# CAT 8: MULTI-CRITERIA (25)
# ═══════════════════════════════════════════════
s1,s2=nhs(),nhs()
r=[cv["nombre_apellidos"] for cv in cvs.values() if all(sk in cv.get("hard_skills",[]) for sk in [s1,s2])]
add_q("multi_criteria", f"Which people know both {s1} and {s2}?", r)
s1,s2=nhs(),nhs()
r=[cv["nombre_apellidos"] for cv in cvs.values() if all(sk in cv.get("hard_skills",[]) for sk in [s1,s2])]
add_q("multi_criteria", f"Find candidates who master both {s1} and {s2}.", r)
s1,s2=nhs(),nhs()
r=[cv["nombre_apellidos"] for cv in cvs.values() if all(sk in cv.get("hard_skills",[]) for sk in [s1,s2])]
add_q("multi_criteria", f"Who combines {s1} and {s2} in their profile?", r)
p,s=npu(),nhs()
r=[cv["nombre_apellidos"] for cv in cvs.values() if cv.get("puesto")==p and s in cv.get("hard_skills",[])]
add_q("multi_criteria", f"Is there any {p} who also knows {s}?", r)
p,s=npu(),nhs()
r=[cv["nombre_apellidos"] for cv in cvs.values() if cv.get("puesto")==p and s in cv.get("hard_skills",[])]
add_q("multi_criteria", f"I'm looking for a {p} with knowledge of {s}. Do they exist?", r)
p,s=npu(),nhs()
r=[cv["nombre_apellidos"] for cv in cvs.values() if cv.get("puesto")==p and s in cv.get("hard_skills",[])]
add_q("multi_criteria", f"Among the {p}s, which ones also have {s} as a competency?", r)
p,s=npu(),nhs()
r=[cv["nombre_apellidos"] for cv in cvs.values() if cv.get("puesto")==p and s in cv.get("hard_skills",[])]
add_q("multi_criteria", f"Filter by position {p} and skill {s}. Who meets both criteria?", r)
e,s=nest(),nhs()
r=[cv["nombre_apellidos"] for cv in cvs.values() if e in cv.get("estudios",[]) and s in cv.get("hard_skills",[])]
add_q("multi_criteria", f"Who has studied {e} and also knows {s}?", r)
e,s=nest(),nhs()
r=[cv["nombre_apellidos"] for cv in cvs.values() if e in cv.get("estudios",[]) and s in cv.get("hard_skills",[])]
add_q("multi_criteria", f"Find people with education in {e} who work with {s}.", r)
p=npu()
r=[cv["nombre_apellidos"] for cv in cvs.values() if cv.get("puesto")==p and any("French" in o for o in cv.get("otros",[]))]
add_q("multi_criteria", f"Which {p}s speak French?", r)
p=npu()
r=[cv["nombre_apellidos"] for cv in cvs.values() if cv.get("puesto")==p and any("German" in o for o in cv.get("otros",[]))]
add_q("multi_criteria", f"I need a {p} who knows German. Is there one?", r)
s=nhs()
r=[cv["nombre_apellidos"] for cv in cvs.values() if s in cv.get("hard_skills",[]) and any("machine learning" in exp.lower() for exp in cv.get("experiencia",[]))]
add_q("multi_criteria", f"Who knows {s} and has experience in machine learning?", r)
s=nhs()
r=[cv["nombre_apellidos"] for cv in cvs.values() if s in cv.get("hard_skills",[]) and any("cloud" in exp.lower() for exp in cv.get("experiencia",[]))]
add_q("multi_criteria", f"Find candidates with the skill {s} who have also worked with cloud.", r)
e,p=nest(),npu()
r=[cv["nombre_apellidos"] for cv in cvs.values() if cv.get("puesto")==p and e in cv.get("estudios",[])]
add_q("multi_criteria", f"Is there any {p} who holds a {e}?", r)
s=nhs(); ss=nss()
r=[cv["nombre_apellidos"] for cv in cvs.values() if s in cv.get("hard_skills",[]) and ss in cv.get("soft_skills",[])]
add_q("multi_criteria", f"Which people combine the technical skill {s} with the soft skill {ss}?", r)
s=nhs(); ss=nss()
r=[cv["nombre_apellidos"] for cv in cvs.values() if s in cv.get("hard_skills",[]) and ss in cv.get("soft_skills",[])]
add_q("multi_criteria", f"Find candidates with {s} who also have {ss} as a soft skill.", r)
s=nhs()
r=[cv["nombre_apellidos"] for cv in cvs.values() if s in cv.get("hard_skills",[]) and any("startup" in o.lower() for o in cv.get("otros",[]))]
add_q("multi_criteria", f"Who knows {s} and has startup experience?", r)
p=npu()
r=[cv["nombre_apellidos"] for cv in cvs.values() if cv.get("puesto")==p and any("self-taught" in o.lower() or "autodidact" in o.lower() for o in cv.get("otros",[]))]
add_q("multi_criteria", f"Among the {p}s, which ones consider themselves self-taught?", r)
s1,s2,s3=nhs(),nhs(),nhs()
r=[cv["nombre_apellidos"] for cv in cvs.values() if all(sk in cv.get("hard_skills",[]) for sk in [s1,s2,s3])]
add_q("multi_criteria", f"Is there any candidate who masters {s1}, {s2} and {s3} simultaneously?", r)
e=nest()
r=[cv["nombre_apellidos"] for cv in cvs.values() if e in cv.get("estudios",[]) and any("French" in o for o in cv.get("otros",[]))]
add_q("multi_criteria", f"Who has a {e} and also speaks French?", r)
s=nhs()
r=[cv["nombre_apellidos"] for cv in cvs.values() if s in cv.get("hard_skills",[]) and len(cv.get("experiencia",[])) >= 3]
add_q("multi_criteria", f"Find people with {s} who have at least 3 experience entries.", r)
p=npu()
r=[cv["nombre_apellidos"] for cv in cvs.values() if cv.get("puesto")==p and len(cv.get("hard_skills",[])) >= 8]
add_q("multi_criteria", f"Which {p}s have 8 or more hard skills?", r)
s=nhs()
r=[cv["nombre_apellidos"] for cv in cvs.values() if s in cv.get("hard_skills",[]) and any("remote" in o.lower() for o in cv.get("otros",[]))]
add_q("multi_criteria", f"Are there candidates with {s} who prefer remote work?", r)
s=nhs()
r=[cv["nombre_apellidos"] for cv in cvs.values() if s in cv.get("hard_skills",[]) and len(cv.get("estudios",[])) >= 2]
add_q("multi_criteria", f"Find people who know {s} and have two or more qualifications.", r)
p=npu()
r=[cv["nombre_apellidos"] for cv in cvs.values() if cv.get("puesto")==p and any("banking" in o.lower() for o in cv.get("otros",[]))]
add_q("multi_criteria", f"Any {p} with banking sector experience?", r)
# ═══════════════════════════════════════════════
# CAT 9: EXISTENCE (YES/NO) (15)
# ═══════════════════════════════════════════════
s,p=nhs(),npu()
r=[cv["nombre_apellidos"] for cv in cvs.values() if s in cv.get("hard_skills",[]) and cv.get("puesto")==p]
add_q("existence", f"Is there anyone who is a {p} and knows {s}?", {"exists": len(r)>0, "people": sorted(r)} if r else {"exists": False}, "boolean_with_detail")
s,e=nhs(),nest()
r=[cv["nombre_apellidos"] for cv in cvs.values() if s in cv.get("hard_skills",[]) and e in cv.get("estudios",[])]
add_q("existence", f"Does any candidate have {s} and a degree in {e}?", {"exists": len(r)>0, "people": sorted(r)} if r else {"exists": False}, "boolean_with_detail")
s="Rust"; r=idx_hard_skill.get(s,[])
add_q("existence", f"Do we have anyone in the database who masters {s}?", {"exists": len(r)>0, "people": sorted(r)} if r else {"exists": False}, "boolean_with_detail")
s="COBOL"; r=idx_hard_skill.get(s,[])
add_q("existence", f"Does any candidate mention {s} on their CV?", {"exists": len(r)>0, "people": sorted(r)} if r else {"exists": False}, "boolean_with_detail")
r=get_lang_personas("Russian")
add_q("existence", "Do we have any professional who speaks Russian?", {"exists": len(r)>0, "people": sorted(r)} if r else {"exists": False}, "boolean_with_detail")
r=get_lang_personas("Arabic")
add_q("existence", "Are there candidates who know Arabic?", {"exists": len(r)>0, "people": sorted(r)} if r else {"exists": False}, "boolean_with_detail")
s=nhs()
r=[cv["nombre_apellidos"] for cv in cvs.values() if s in cv.get("hard_skills",[]) and any("self-taught" in o.lower() for o in cv.get("otros",[]))]
add_q("existence", f"Is there any self-taught person who knows {s}?", {"exists": len(r)>0, "people": sorted(r)} if r else {"exists": False}, "boolean_with_detail")
r=[cv["nombre_apellidos"] for cv in cvs.values() if len(cv.get("hard_skills",[])) >= 10]
add_q("existence", "Is there any candidate with 10 or more hard skills?", {"exists": len(r)>0, "people": sorted(r)}, "boolean_with_detail")
r=[cv["nombre_apellidos"] for cv in cvs.values() if len(cv.get("estudios",[])) >= 4]
add_q("existence", "Is there anyone with 4 or more academic qualifications?", {"exists": len(r)>0, "people": sorted(r)} if r else {"exists": False}, "boolean_with_detail")
s1,s2=nhs(),nhs()
r=[cv["nombre_apellidos"] for cv in cvs.values() if all(sk in cv.get("hard_skills",[]) for sk in [s1,s2])]
add_q("existence", f"Is there someone who combines {s1} and {s2} in their skills?", {"exists": len(r)>0, "people": sorted(r)} if r else {"exists": False}, "boolean_with_detail")
r=[cv["nombre_apellidos"] for cv in cvs.values() if any("immediate" in o.lower() for o in cv.get("otros",[])) and any("French" in o for o in cv.get("otros",[]))]
add_q("existence", "Do we have candidates with immediate availability who speak French?", {"exists": len(r)>0, "people": sorted(r)} if r else {"exists": False}, "boolean_with_detail")
r=[cv["nombre_apellidos"] for cv in cvs.values() if len(cv.get("experiencia",[])) >= 5]
add_q("existence", "Is there any candidate with 5 or more experience entries?", {"exists": len(r)>0, "people": sorted(r)} if r else {"exists": False}, "boolean_with_detail")
r=[cv["nombre_apellidos"] for cv in cvs.values() if any("German" in o for o in cv.get("otros",[])) and any("French" in o for o in cv.get("otros",[]))]
add_q("existence", "Is there anyone who speaks both German and French?", {"exists": len(r)>0, "people": sorted(r)} if r else {"exists": False}, "boolean_with_detail")
r=[cv["nombre_apellidos"] for cv in cvs.values() if any("open source" in o.lower() or "contributor" in o.lower() for o in cv.get("otros",[]))]
add_q("existence", "Does any candidate mention open source contributions?", {"exists": len(r)>0, "people": sorted(r)} if r else {"exists": False}, "boolean_with_detail")
r=[cv["nombre_apellidos"] for cv in cvs.values() if any("mentor" in o.lower() for o in cv.get("otros",[]))]
add_q("existence", "Are there professionals who indicate mentoring experience?", {"exists": len(r)>0, "people": sorted(r)} if r else {"exists": False}, "boolean_with_detail")
# ═══════════════════════════════════════════════
# CAT 10: AGGREGATION / RANKING (20)
# ═══════════════════════════════════════════════
top5_hs = hard_skill_counts.most_common(5)
add_q("aggregation", "What are the 5 most frequent hard skills among all candidates?", [{"skill":s,"frequency":c} for s,c in top5_hs], "ranking")
top10_hs = hard_skill_counts.most_common(10)
add_q("aggregation", "Give me a ranking of the 10 most repeated technical skills in the CVs.", [{"skill":s,"frequency":c} for s,c in top10_hs], "ranking")
top5_ss = soft_skill_counts.most_common(5)
add_q("aggregation", "What are the 5 most common soft skills among professionals?", [{"skill":s,"frequency":c} for s,c in top5_ss], "ranking")
top5_p = puesto_counts.most_common(5)
add_q("aggregation", "What are the 5 most common job positions in the database?", [{"position":p,"frequency":c} for p,c in top5_p], "ranking")
top3_p = puesto_counts.most_common(3)
add_q("aggregation", "Tell me the 3 professional roles with the highest representation.", [{"position":p,"frequency":c} for p,c in top3_p], "ranking")
top5_e = estudio_counts.most_common(5)
add_q("aggregation", "Which 5 qualifications are the most frequent among candidates?", [{"education":e,"frequency":c} for e,c in top5_e], "ranking")
max_hs = max(skills_per_person.items(), key=lambda x: x[1]["hard"])
add_q("aggregation", "Who is the person with the most hard skills? How many do they have?", {"person": max_hs[0], "count": max_hs[1]["hard"]}, "value_with_detail")
max_ss = max(skills_per_person.items(), key=lambda x: x[1]["soft"])
add_q("aggregation", "Which candidate has the highest number of soft skills?", {"person": max_ss[0], "count": max_ss[1]["soft"]}, "value_with_detail")
max_est = max(skills_per_person.items(), key=lambda x: x[1]["estudios"])
add_q("aggregation", "Who has the most academic qualifications on their CV?", {"person": max_est[0], "count": max_est[1]["estudios"]}, "value_with_detail")
max_exp = max(skills_per_person.items(), key=lambda x: x[1]["experiencia"])
add_q("aggregation", "Which person has the most work experience entries?", {"person": max_exp[0], "count": max_exp[1]["experiencia"]}, "value_with_detail")
avg_hs = round(sum(sp["hard"] for sp in skills_per_person.values()) / len(skills_per_person), 2)
add_q("aggregation", "What is the average number of hard skills per candidate?", avg_hs, "number")
avg_ss = round(sum(sp["soft"] for sp in skills_per_person.values()) / len(skills_per_person), 2)
add_q("aggregation", "What is the average number of soft skills per person?", avg_ss, "number")
bottom5_hs = hard_skill_counts.most_common()[-5:]
add_q("aggregation", "What are the 5 least frequent hard skills in the entire database?", [{"skill":s,"frequency":c} for s,c in bottom5_hs], "ranking")
bottom3_p = puesto_counts.most_common()[-3:]
add_q("aggregation", "Which 3 job positions are the least common?", [{"position":p,"frequency":c} for p,c in bottom3_p], "ranking")
hs_dist = Counter(sp["hard"] for sp in skills_per_person.values())
add_q("aggregation", "How are candidates distributed by their number of hard skills?", {str(k):v for k,v in sorted(hs_dist.items())}, "distribution")
langs = ["French","German","Italian","Portuguese","Chinese","Japanese","Arabic","Russian","Korean","Spanish"]
lang_counts = {kw: len(get_lang_personas(kw)) for kw in langs}
lang_counts = {k:v for k,v in lang_counts.items() if v>0}
top_langs = sorted(lang_counts.items(), key=lambda x:-x[1])[:5]
add_q("aggregation", "What are the 5 most mentioned languages by candidates?", [{"language":i,"frequency":c} for i,c in top_langs], "ranking")
max_otros = max(skills_per_person.items(), key=lambda x: x[1]["otros"])
add_q("aggregation", "Who has the most additional information (others) on their profile?", {"person": max_otros[0], "count": max_otros[1]["otros"]}, "value_with_detail")
add_q("aggregation", "How many unique competencies (hard + soft) are collected across the entire database?", len(idx_hard_skill) + len(idx_soft_skill), "number")
max_total = max(skills_per_person.items(), key=lambda x: x[1]["total"])
add_q("aggregation", "Which candidate has the highest total number of competencies (hard + soft)?",
      {"person": max_total[0], "hard_skills": max_total[1]["hard"], "soft_skills": max_total[1]["soft"], "total": max_total[1]["total"]}, "value_with_detail")
top3_e = estudio_counts.most_common(3)
add_q("aggregation", "Rank the top 3 most popular academic qualifications and how many people have them.", [{"education":e,"frequency":c} for e,c in top3_e], "ranking")
# ═══════════════════════════════════════════════
# CAT 11: SEARCH BY SOFT SKILL (10)
# ═══════════════════════════════════════════════
ss=nss(); add_q("search_by_soft_skill", f"Which people have {ss} as a soft skill?", idx_soft_skill[ss])
ss=nss(); add_q("search_by_soft_skill", f"list the candidates who mention {ss} among their interpersonal skills.", idx_soft_skill[ss])
ss=nss(); add_q("search_by_soft_skill", f"Who stands out for their {ss} according to the CVs?", idx_soft_skill[ss])
ss=nss(); add_q("search_by_soft_skill", f"Give me all professionals whose soft skills include {ss}.", idx_soft_skill[ss])
ss=nss(); add_q("search_by_soft_skill", f"Identify those who possess the competency of {ss}.", idx_soft_skill[ss])
ss=nss(); add_q("search_by_soft_skill", f"Which candidates reflect {ss} as an interpersonal ability?", idx_soft_skill[ss])
ss=nss(); add_q("search_by_soft_skill", f"Search for profiles that include {ss} among their personal aptitudes.", idx_soft_skill[ss])
ss=nss(); add_q("search_by_soft_skill", f"Are there people characterized by their {ss}?", idx_soft_skill[ss])
ss=nss(); add_q("search_by_soft_skill", f"Find the candidates who have {ss} on their resume.", idx_soft_skill[ss])
ss=nss(); add_q("search_by_soft_skill", f"Which team members possess {ss} as a soft competency?", idx_soft_skill[ss])
# ═══════════════════════════════════════════════
# CAT 12: SEARCH BY EXPERIENCE KEYWORD (10)
# ═══════════════════════════════════════════════
add_q("search_by_experience", "Which people have experience in machine learning?", get_exp_keyword("machine learning"))
add_q("search_by_experience", "Give me candidates whose experience mentions cloud projects.", get_exp_keyword("cloud"))
add_q("search_by_experience", "Who has worked with microservices according to their CV?", get_exp_keyword("microservic"))
add_q("search_by_experience", "Find professionals with DevOps experience.", get_exp_keyword("DevOps"))
add_q("search_by_experience", "Which candidates mention agile methodologies in their experience?", get_exp_keyword("agile"))
add_q("search_by_experience", "Identify those who have experience developing APIs.", get_exp_keyword("API"))
add_q("search_by_experience", "Who reflects data or data analysis work in their experience?", get_exp_keyword("data"))
add_q("search_by_experience", "Locate candidates with experience in security or cybersecurity.", get_exp_keyword("security"))
add_q("search_by_experience", "Which people have had leadership roles according to their experience?", get_exp_keyword("leadership"))
add_q("search_by_experience", "Find professionals whose experience includes process automation.", get_exp_keyword("automat"))
# ═══════════════════════════════════════════════
# FILTER: REDUCE TO 80-100 QUESTIONS
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
print(f"\n→ Reduced from {len(preguntas)} to {len(_selected)} questions (target: 80-100)")
preguntas = _selected
# ═══════════════════════════════════════════════
# VERIFY AND EXPORT
# ═══════════════════════════════════════════════
texts = [q["pregunta"] for q in preguntas]
if len(texts) != len(set(texts)):
    dupes = [t for t in texts if texts.count(t) > 1]
    print(f"WARNING: {len(dupes)} duplicate questions detected")
else:
    print("OK All questions are unique")
print(f"Total questions generated: {len(preguntas)}")
cat_counts = Counter(q["categoria"] for q in preguntas)
print("\nDistribution by category:")
for cat, cnt in sorted(cat_counts.items()):
    print(f"  {cat}: {cnt}")
gold_standard = {
    "gold_standard": {
        "caso_uso": "cvs",
        "idioma": "en",
        "total_preguntas": len(preguntas),
        "total_cvs_analizados": len(cvs),
        "fecha_generacion": "2026-04-17",
        "categorias": dict(sorted(cat_counts.items())),
        "descripcion": "Gold standard for evaluating a RAG system on an English CV database. "
                       "Contains questions about skill search, positions, education, languages, "
                       "individual queries, counting, multi-criteria filters, existence and ranking. "
                       "All answers computed directly from source data.",
        "preguntas": preguntas
    }
}
output_path = OUTPUT_DIR / "gold_standard_cvs_en.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(gold_standard, f, ensure_ascii=False, indent=2)
print(f"\nOK Gold standard saved to: {output_path}")
