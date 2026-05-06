"""
Generador unificado del Gold Standard de CVs (EN + ES).

Produce dos JSON paralelos (gold_standard_cvs_en.json y gold_standard_cvs_es.json)
con EXACTAMENTE las mismas preguntas (traducidas) y respuestas calculadas de forma
independiente sobre cada dataset (300 CVs en/300 CVs es).

Filosofía:
  * Las preguntas combinan criterios (AND / OR) sobre skills, puestos, idiomas,
    temas (otros) y palabras clave de experiencia para obtener listas de respuesta
    largas y representativas (no truncadas a unos pocos nombres).
  * Cada pregunta es paramétrica: parámetros elegidos de pools que existen en
    ambos datasets, así la pregunta tiene sentido y respuesta no vacía en EN y ES.
  * Las preguntas de tipo "individual" se omiten porque los nombres difieren
    entre datasets y romperían el paralelismo exacto.

    python -m data.GoldStandard.scripts.generar_gold_standard_cvs_paralelo
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent      # test/
CV_BASE = ROOT.parent / "data" / "cvs"             # data/cvs
OUTPUT_DIR = ROOT / "data"                         # test/data


# ─────────────────────────────────────────────
# 1. CARGA DE DATOS
# ─────────────────────────────────────────────
def load_cvs(lang: str) -> dict[str, dict]:
    cvs: dict[str, dict] = {}
    for f in sorted((CV_BASE / lang).glob("cv_*.json")):
        with open(f, encoding="utf-8") as fh:
            cvs[f.stem] = json.load(fh)
    return cvs


DATASETS = {"en": load_cvs("en"), "es": load_cvs("es")}
print(f"EN={len(DATASETS['en'])} CVs   ES={len(DATASETS['es'])} CVs")


# ─────────────────────────────────────────────
# 2. HELPERS DE PREDICADOS
# ─────────────────────────────────────────────
def has_skill(cv: dict, skill: str) -> bool:
    """True si el skill está en hard_skills O aparece como palabra clave
    en la sección de experiencia. Refleja el lenguaje natural de las
    preguntas ("sabe de X" / "ha trabajado con X").
    """
    if skill in cv.get("hard_skills", []):
        return True
    skill_l = skill.lower()
    # Aceptamos prefijo razonable: "Microservices" -> "microservic"
    needle = skill_l[:-1] if skill_l.endswith("s") else skill_l
    for exp in cv.get("experiencia", []):
        if needle in exp.lower():
            return True
    return False


def has_position(cv: dict, puesto: str) -> bool:
    return cv.get("puesto") == puesto


def has_kw_in(cv: dict, fields: list[str], kw: str) -> bool:
    kw_l = kw.lower()
    for field in fields:
        for item in cv.get(field, []):
            if kw_l in item.lower():
                return True
    return False


def has_lang(cv: dict, kw) -> bool:
    """Detecta un idioma en `otros`. `kw` puede ser un string o una lista de
    palabras clave (cualquier coincidencia cuenta). Útil para reconocer
    certificaciones de idioma además del nombre del idioma (p. ej. DELF/DALF
    para francés, Goethe-Zertifikat/TestDaF para alemán).
    """
    keywords = [kw] if isinstance(kw, str) else list(kw)
    return any(has_kw_in(cv, ["otros"], k) for k in keywords)


def has_topic(cv: dict, kw: str) -> bool:
    """Tema / palabra clave en otros o experiencia."""
    return has_kw_in(cv, ["otros", "experiencia"], kw)


def names_where(cvs: dict[str, dict], pred: Callable[[dict], bool]) -> list[str]:
    return sorted({cv["nombre_apellidos"] for cv in cvs.values() if pred(cv)})


# ─────────────────────────────────────────────
# 3. POOLS DE PARÁMETROS (existen en ambos datasets)
# ─────────────────────────────────────────────
# Skills hard compartidos (texto idéntico, mayoría términos técnicos en inglés).
SKILLS = [
    "Elasticsearch", "WebSockets", "UML", "Apache Kafka", "Microservices",
    "Hexagonal Architecture", "Apache Airflow", "Event-Driven Architecture",
    "gRPC", "Flask", "OpenCV", "Serverless Architecture", "AWS Glue", "COBOL",
    "Playwright", "Django", "BERT", "Google Analytics 4", "D3.js",
    "PyTorch Lightning", "GitHub Flow", "Phoenix (Elixir)", "F#", "Ubuntu",
    "Excel", "Redshift", "Inventory Management", "MQTT", "NetSuite",
    "Image Classification",
]

# Puestos compartidos.
POSITIONS = [
    "iOS Developer", "PhD Researcher", "Web Developer", "React Developer",
    "Software Architect", "Network Engineer", "Lead Developer",
    "Android Developer", "Salesforce Developer", "Visual Designer",
    "Help Desk Technician", "IT Manager", "QA Consultant", "Brand Manager",
    "Agile Coach", "Security Consultant", "Tableau Developer",
    "Digital Transformation Consultant", "Technical Product Manager",
    "QA Automation Engineer", "Customer Success Manager", "Software Tester",
]

# Idiomas: (label_en, label_es, kw_en, kw_es).
# Cada kw_* es una tupla de palabras clave (se considera que la persona habla
# el idioma si CUALQUIERA de las kws aparece en `otros`). Incluimos el nombre
# del idioma y sus certificaciones más comunes.
LANGUAGES = [
    ("French",     "francés",
        ("French",  "DELF", "DALF"),
        ("Francés", "DELF", "DALF")),
    ("German",     "alemán",
        ("German",  "Goethe-Zertifikat", "TestDaF"),
        ("Alemán",  "Goethe-Zertifikat", "TestDaF")),
    ("Italian",    "italiano",
        ("Italian",  "CILS", "CELI", "PLIDA"),
        ("Italiano", "CILS", "CELI", "PLIDA")),
    ("Portuguese", "portugués",
        ("Portuguese",   "CAPLE", "CELPE-Bras"),
        ("Portugués",    "CAPLE", "CELPE-Bras")),
    ("Japanese",   "japonés",
        ("Japanese", "JLPT"),
        ("Japonés",  "JLPT")),
    ("Russian",    "ruso",
        ("Russian", "TORFL"),
        ("Ruso",    "TORFL")),
    ("Arabic",     "árabe",
        ("Arabic",),
        ("Árabe",)),
]

# Tema (label_en, label_es, kw_en, kw_es) — busca en otros + experiencia.
TOPICS = [
    ("startups",                    "startups",                          "startup",         "startup"),
    ("remote work",                 "trabajo remoto",                    "remote",          "remot"),
    ("open source",                 "open source",                       "open source",     "open source"),
    ("hackathons",                  "hackathones",                       "hackathon",       "hackathon"),
    ("mentoring",                   "mentoría",                          "mentor",          "mentor"),
    ("e-commerce",                  "e-commerce",                        "e-commerce",      "e-commerce"),
    ("fintech",                     "fintech",                           "fintech",         "fintech"),
    ("banking",                     "banca",                             "bank",            "banc"),
    ("self-taught learning",        "autodidactismo",                    "self-taught",     "autodidact"),
]

# Palabras clave técnicas presentes en experiencia (versión EN y ES).
EXP_KEYWORDS = [
    ("microservices",        "microservicios",        "microservic",     "microservic"),
    ("data",                 "datos",                 "data",            "datos"),
    ("cloud",                "cloud",                 "cloud",           "cloud"),
    ("DevOps",               "DevOps",                "DevOps",          "DevOps"),
    ("agile methodologies",  "metodologías ágiles",   "agile",           "ágil"),
    ("APIs",                 "APIs",                  "API",             "API"),
    ("automation",           "automatización",        "automat",         "automat"),
    ("technical documentation","documentación técnica","documentation",  "documentación"),
]


# ─────────────────────────────────────────────
# 4. RECOLECTOR DE PREGUNTAS
# ─────────────────────────────────────────────
QUESTIONS: list[dict] = []


def add(categoria: str, q_en: str, q_es: str,
        fn: Callable[[dict], list], tipo: str = "person_list"):
    QUESTIONS.append({
        "categoria": categoria,
        "q_en": q_en,
        "q_es": q_es,
        "fn": fn,
        "tipo": tipo,
    })


def add_count(q_en: str, q_es: str, fn: Callable[[dict], int]):
    QUESTIONS.append({
        "categoria": "counting",
        "q_en": q_en,
        "q_es": q_es,
        "fn": fn,
        "tipo": "number",
    })


# ─────────────────────────────────────────────
# 5. CATEGORÍA: BÚSQUEDA SIMPLE POR SKILL  (8)
# ─────────────────────────────────────────────
for s in SKILLS[:8]:
    add(
        "search_by_skill",
        f"Which candidates have {s} among their hard skills?",
        f"¿Qué candidatos tienen {s} entre sus hard skills?",
        (lambda s=s: lambda cvs: names_where(cvs, lambda c: has_skill(c, s)))(),
    )

# ─────────────────────────────────────────────
# 6. CATEGORÍA: BÚSQUEDA SIMPLE POR PUESTO  (6)
# ─────────────────────────────────────────────
for p in POSITIONS[:6]:
    add(
        "search_by_position",
        f"Who is registered with the position of {p}?",
        f"¿Quién está registrado con el puesto de {p}?",
        (lambda p=p: lambda cvs: names_where(cvs, lambda c: has_position(c, p)))(),
    )

# ─────────────────────────────────────────────
# 7. CATEGORÍA: BÚSQUEDA SIMPLE POR IDIOMA  (5)
# ─────────────────────────────────────────────
for lab_en, lab_es, kw_en, kw_es in LANGUAGES[:5]:
    add(
        "search_by_language",
        f"Which professionals declare knowledge of {lab_en}?",
        f"¿Qué profesionales declaran conocimientos de {lab_es}?",
        (lambda kw_en=kw_en, kw_es=kw_es: lambda cvs:
            names_where(cvs, lambda c, k=(kw_en if cvs is DATASETS["en"] else kw_es): has_lang(c, k)))(),
    )

# ─────────────────────────────────────────────
# 8. CATEGORÍA: BÚSQUEDA SIMPLE POR TEMA  (6)
# ─────────────────────────────────────────────
for lab_en, lab_es, kw_en, kw_es in TOPICS[:6]:
    add(
        "search_by_topic",
        f"Which candidates mention {lab_en} in their profile?",
        f"¿Qué candidatos mencionan {lab_es} en su perfil?",
        (lambda kw_en=kw_en, kw_es=kw_es: lambda cvs:
            names_where(cvs, lambda c, k=(kw_en if cvs is DATASETS["en"] else kw_es): has_topic(c, k)))(),
    )

# ─────────────────────────────────────────────
# 9. CATEGORÍA: COMBINACIONES AND
# Usamos pools amplios (idioma, tema, palabra clave de experiencia) para que
# las intersecciones devuelvan listas razonables y no triviales.
# ─────────────────────────────────────────────
# 9.1 Idioma AND palabra clave de experiencia (caso "francés + microservicios")
AND_LANG_EXP = [
    (LANGUAGES[0], EXP_KEYWORDS[0]),  # French + microservices
    (LANGUAGES[1], EXP_KEYWORDS[2]),  # German + cloud
    (LANGUAGES[2], EXP_KEYWORDS[3]),  # Italian + DevOps
    (LANGUAGES[3], EXP_KEYWORDS[4]),  # Portuguese + agile
    (LANGUAGES[4], EXP_KEYWORDS[6]),  # Japanese + automation
]
for (lab_en, lab_es, kw_en, kw_es), (le, ls, ke, kse) in AND_LANG_EXP:
    add(
        "multi_criteria_and",
        f"Which people speak {lab_en} AND have worked with {le}?",
        f"¿Qué personas hablan {lab_es} Y han trabajado con {ls}?",
        (lambda kw_en=kw_en, kw_es=kw_es, ke=ke, kse=kse: lambda cvs:
            names_where(cvs, lambda c,
                        L=(kw_en if cvs is DATASETS["en"] else kw_es),
                        K=(ke if cvs is DATASETS["en"] else kse):
                        has_lang(c, L) and has_kw_in(c, ["experiencia"], K)))(),
    )

# 9.2 Tema AND palabra clave de experiencia
AND_TOPIC_EXP = [
    (TOPICS[0], EXP_KEYWORDS[2]),   # startups + cloud
    (TOPICS[1], EXP_KEYWORDS[3]),   # remote + DevOps
    (TOPICS[2], EXP_KEYWORDS[6]),   # open source + automation
    (TOPICS[3], EXP_KEYWORDS[4]),   # hackathons + agile
]
for (tle, tls, tke, tkse), (le, ls, ke, kse) in AND_TOPIC_EXP:
    add(
        "multi_criteria_and",
        f"Which candidates mention {tle} AND have experience in {le}?",
        f"¿Qué candidatos mencionan {tls} Y tienen experiencia en {ls}?",
        (lambda tke=tke, tkse=tkse, ke=ke, kse=kse: lambda cvs:
            names_where(cvs, lambda c,
                        T=(tke if cvs is DATASETS["en"] else tkse),
                        K=(ke if cvs is DATASETS["en"] else kse):
                        has_topic(c, T) and has_kw_in(c, ["experiencia"], K)))(),
    )

# 9.3 Idioma AND tema
AND_LANG_TOPIC = [
    (LANGUAGES[0], TOPICS[2]),   # French + open source
    (LANGUAGES[1], TOPICS[0]),   # German + startups
    (LANGUAGES[2], TOPICS[1]),   # Italian + remote
    (LANGUAGES[3], TOPICS[3]),   # Portuguese + hackathons
]
for (lab_en, lab_es, kw_en, kw_es), (tle, tls, tke, tkse) in AND_LANG_TOPIC:
    add(
        "multi_criteria_and",
        f"Which people speak {lab_en} AND mention {tle} on their CV?",
        f"¿Qué personas hablan {lab_es} Y mencionan {tls} en su CV?",
        (lambda kw_en=kw_en, kw_es=kw_es, tke=tke, tkse=tkse: lambda cvs:
            names_where(cvs, lambda c,
                        L=(kw_en if cvs is DATASETS["en"] else kw_es),
                        T=(tke if cvs is DATASETS["en"] else tkse):
                        has_lang(c, L) and has_topic(c, T)))(),
    )

# 9.4 Tema AND tema
AND_TOPIC_TOPIC = [
    (TOPICS[0], TOPICS[3]),   # startups AND hackathons
    (TOPICS[1], TOPICS[2]),   # remote AND open source
    (TOPICS[6], TOPICS[7]),   # fintech AND banking
]
for (tle1, tls1, tke1, tkse1), (tle2, tls2, tke2, tkse2) in AND_TOPIC_TOPIC:
    add(
        "multi_criteria_and",
        f"Which candidates mention BOTH {tle1} AND {tle2}?",
        f"¿Qué candidatos mencionan A LA VEZ {tls1} Y {tls2}?",
        (lambda tke1=tke1, tkse1=tkse1, tke2=tke2, tkse2=tkse2: lambda cvs:
            names_where(cvs, lambda c,
                        A=(tke1 if cvs is DATASETS["en"] else tkse1),
                        B=(tke2 if cvs is DATASETS["en"] else tkse2):
                        has_topic(c, A) and has_topic(c, B)))(),
    )

# 9.5 Idioma AND idioma (políglotas)
AND_LANG_LANG = [
    (LANGUAGES[0], LANGUAGES[1]),  # French + German
    (LANGUAGES[0], LANGUAGES[2]),  # French + Italian
]
for (le1, ls1, ke1, kse1), (le2, ls2, ke2, kse2) in AND_LANG_LANG:
    add(
        "multi_criteria_and",
        f"Which people speak both {le1} and {le2}?",
        f"¿Qué personas hablan a la vez {ls1} y {ls2}?",
        (lambda ke1=ke1, kse1=kse1, ke2=ke2, kse2=kse2: lambda cvs:
            names_where(cvs, lambda c,
                        a=(ke1 if cvs is DATASETS["en"] else kse1),
                        b=(ke2 if cvs is DATASETS["en"] else kse2):
                        has_lang(c, a) and has_lang(c, b)))(),
    )

# 9.6 Experiencia AND experiencia
AND_EXP_EXP = [
    (EXP_KEYWORDS[0], EXP_KEYWORDS[2]),   # microservices + cloud
    (EXP_KEYWORDS[3], EXP_KEYWORDS[6]),   # DevOps + automation
    (EXP_KEYWORDS[4], EXP_KEYWORDS[5]),   # agile + APIs
]
for (le1, ls1, ke1, kse1), (le2, ls2, ke2, kse2) in AND_EXP_EXP:
    add(
        "multi_criteria_and",
        f"Which people have experience in BOTH {le1} AND {le2}?",
        f"¿Qué personas tienen experiencia en {ls1} Y en {ls2}?",
        (lambda ke1=ke1, kse1=kse1, ke2=ke2, kse2=kse2: lambda cvs:
            names_where(cvs, lambda c,
                        a=(ke1 if cvs is DATASETS["en"] else kse1),
                        b=(ke2 if cvs is DATASETS["en"] else kse2):
                        has_kw_in(c, ["experiencia"], a)
                        and has_kw_in(c, ["experiencia"], b)))(),
    )

# ─────────────────────────────────────────────
# 10. CATEGORÍA: COMBINACIONES OR  (≈22)
# Diseñadas para producir respuestas largas (decenas/cientos de candidatos).
# ─────────────────────────────────────────────
# 10.1 Idioma OR skill — el caso pedido por el usuario.
OR_LANG_SKILL = [
    (LANGUAGES[0], "Microservices"),
    (LANGUAGES[1], "Apache Kafka"),
    (LANGUAGES[2], "Django"),
    (LANGUAGES[3], "Elasticsearch"),
    (LANGUAGES[4], "OpenCV"),
    (LANGUAGES[5], "BERT"),
    (LANGUAGES[6], "Flask"),
]
for (lab_en, lab_es, kw_en, kw_es), s in OR_LANG_SKILL:
    add(
        "multi_criteria_or",
        f"Who speaks {lab_en} OR knows {s} (any of the two)?",
        f"¿Quién habla {lab_es} O conoce {s} (cualquiera de los dos)?",
        (lambda kw_en=kw_en, kw_es=kw_es, s=s: lambda cvs:
            names_where(cvs, lambda c, k=(kw_en if cvs is DATASETS["en"] else kw_es):
                        has_lang(c, k) or has_skill(c, s)))(),
    )

# 10.2 Skill OR skill
OR_SKILL_SKILL = [
    ("Microservices", "Apache Kafka"),
    ("Django", "Flask"),
    ("Elasticsearch", "Redshift"),
    ("OpenCV", "BERT"),
    ("Apache Airflow", "AWS Glue"),
    ("WebSockets", "gRPC"),
]
for s1, s2 in OR_SKILL_SKILL:
    add(
        "multi_criteria_or",
        f"Which candidates know {s1} OR {s2}?",
        f"¿Qué candidatos conocen {s1} O {s2}?",
        (lambda s1=s1, s2=s2: lambda cvs:
            names_where(cvs, lambda c: has_skill(c, s1) or has_skill(c, s2)))(),
    )

# 10.3 Tema OR tema
OR_TOPIC_TOPIC = [
    (TOPICS[0], TOPICS[3]),   # startups OR hackathons
    (TOPICS[2], TOPICS[4]),   # open source OR mentoring
    (TOPICS[6], TOPICS[7]),   # fintech OR banking
]
for (le1, ls1, ke1, kse1), (le2, ls2, ke2, kse2) in OR_TOPIC_TOPIC:
    add(
        "multi_criteria_or",
        f"Which candidates mention {le1} OR {le2} in their profile?",
        f"¿Qué candidatos mencionan {ls1} O {ls2} en su perfil?",
        (lambda ke1=ke1, kse1=kse1, ke2=ke2, kse2=kse2: lambda cvs:
            names_where(cvs, lambda c,
                        a=(ke1 if cvs is DATASETS["en"] else kse1),
                        b=(ke2 if cvs is DATASETS["en"] else kse2):
                        has_topic(c, a) or has_topic(c, b)))(),
    )

# 10.4 Idioma OR idioma
OR_LANG_LANG = [
    (LANGUAGES[0], LANGUAGES[1]),  # French OR German
    (LANGUAGES[2], LANGUAGES[3]),  # Italian OR Portuguese
    (LANGUAGES[4], LANGUAGES[5]),  # Japanese OR Russian
]
for (le1, ls1, ke1, kse1), (le2, ls2, ke2, kse2) in OR_LANG_LANG:
    add(
        "multi_criteria_or",
        f"Who speaks {le1} OR {le2}?",
        f"¿Quién habla {ls1} O {ls2}?",
        (lambda ke1=ke1, kse1=kse1, ke2=ke2, kse2=kse2: lambda cvs:
            names_where(cvs, lambda c,
                        a=(ke1 if cvs is DATASETS["en"] else kse1),
                        b=(ke2 if cvs is DATASETS["en"] else kse2):
                        has_lang(c, a) or has_lang(c, b)))(),
    )

# 10.5 Puesto OR puesto
OR_POS_POS = [
    ("iOS Developer", "Android Developer"),
    ("Web Developer", "React Developer"),
    ("Software Architect", "Lead Developer"),
]
for p1, p2 in OR_POS_POS:
    add(
        "multi_criteria_or",
        f"Who works as {p1} OR {p2}?",
        f"¿Quién trabaja como {p1} O {p2}?",
        (lambda p1=p1, p2=p2: lambda cvs:
            names_where(cvs, lambda c: has_position(c, p1) or has_position(c, p2)))(),
    )

# 10.6 Experiencia keyword OR skill
OR_EXP_SKILL = [
    (EXP_KEYWORDS[0], "Apache Kafka"),  # microservices OR Kafka
    (EXP_KEYWORDS[1], "BERT"),          # machine learning OR BERT
    (EXP_KEYWORDS[2], "AWS Glue"),      # cloud OR Glue
    (EXP_KEYWORDS[3], "GitHub Flow"),   # DevOps OR GitHub Flow
]
for (le, ls, ke, kse), s in OR_EXP_SKILL:
    add(
        "multi_criteria_or",
        f"Who has experience in {le} OR knows {s}?",
        f"¿Quién tiene experiencia en {ls} O conoce {s}?",
        (lambda ke=ke, kse=kse, s=s: lambda cvs:
            names_where(cvs, lambda c, k=(ke if cvs is DATASETS["en"] else kse):
                        has_kw_in(c, ["experiencia"], k) or has_skill(c, s)))(),
    )

# ─────────────────────────────────────────────
# 11. CATEGORÍA: BÚSQUEDA POR EXPERIENCIA (4)
# ─────────────────────────────────────────────
for le, ls, ke, kse in EXP_KEYWORDS[:4]:
    add(
        "search_by_experience",
        f"Which people have experience related to {le}?",
        f"¿Qué personas tienen experiencia relacionada con {ls}?",
        (lambda ke=ke, kse=kse: lambda cvs:
            names_where(cvs, lambda c, k=(ke if cvs is DATASETS["en"] else kse):
                        has_kw_in(c, ["experiencia"], k)))(),
    )

# ─────────────────────────────────────────────
# 12. CATEGORÍA: COUNTING  (10)
# ─────────────────────────────────────────────
add_count(
    "How many CVs are loaded in total?",
    "¿Cuántos CVs hay cargados en total?",
    lambda cvs: len(cvs),
)
add_count(
    "How many distinct positions appear in the database?",
    "¿Cuántos puestos distintos aparecen en la base de datos?",
    lambda cvs: len({c.get("puesto", "") for c in cvs.values()}),
)
add_count(
    "How many distinct hard skills appear across all CVs?",
    "¿Cuántas hard skills distintas aparecen en todos los CVs?",
    lambda cvs: len({s for c in cvs.values() for s in c.get("hard_skills", [])}),
)
add_count(
    "How many candidates have at least 8 hard skills?",
    "¿Cuántos candidatos tienen al menos 8 hard skills?",
    lambda cvs: sum(1 for c in cvs.values() if len(c.get("hard_skills", [])) >= 8),
)
# Combos AND/OR contadas
_FR_EN = LANGUAGES[0][2]
_FR_ES = LANGUAGES[0][3]
add_count(
    "How many candidates speak French AND know Microservices?",
    "¿Cuántos candidatos hablan francés Y conocen Microservices?",
    lambda cvs: len(names_where(cvs, lambda c, k=(_FR_EN if cvs is DATASETS["en"] else _FR_ES):
                                has_lang(c, k) and has_skill(c, "Microservices"))),
)
add_count(
    "How many candidates speak French OR know Microservices?",
    "¿Cuántos candidatos hablan francés O conocen Microservices?",
    lambda cvs: len(names_where(cvs, lambda c, k=(_FR_EN if cvs is DATASETS["en"] else _FR_ES):
                                has_lang(c, k) or has_skill(c, "Microservices"))),
)
add_count(
    "How many candidates know Django OR Flask?",
    "¿Cuántos candidatos conocen Django O Flask?",
    lambda cvs: len(names_where(cvs, lambda c: has_skill(c, "Django") or has_skill(c, "Flask"))),
)
add_count(
    "How many candidates speak any of: French, German, Italian, Portuguese?",
    "¿Cuántos candidatos hablan alguno de: francés, alemán, italiano o portugués?",
    lambda cvs: len(names_where(cvs, lambda c, en=(cvs is DATASETS["en"]):
                                any(has_lang(c, kw_tuple)
                                    for kw_tuple in ([le for _, _, le, _ in LANGUAGES[:4]] if en
                                                     else [ls for _, _, _, ls in LANGUAGES[:4]])))),
)
add_count(
    "How many candidates mention startups OR hackathons in their profile?",
    "¿Cuántos candidatos mencionan startups O hackathones en su perfil?",
    lambda cvs: len(names_where(cvs, lambda c:
                                has_topic(c, "startup") or has_topic(c, "hackathon"))),
)
add_count(
    "How many candidates have experience related to microservices OR cloud?",
    "¿Cuántos candidatos tienen experiencia relacionada con microservicios O cloud?",
    lambda cvs: len(names_where(cvs, lambda c, en=(cvs is DATASETS["en"]):
                                has_kw_in(c, ["experiencia"], "microservic")
                                or has_kw_in(c, ["experiencia"], "cloud"))),
)


# ─────────────────────────────────────────────
# 13. RENDERIZAR LOS DOS JSON
# ─────────────────────────────────────────────
def build_payload(lang: str) -> dict:
    cvs = DATASETS[lang]
    cat_counter: Counter = Counter()
    preguntas = []
    for i, q in enumerate(QUESTIONS, 1):
        cat_counter[q["categoria"]] += 1
        respuesta = q["fn"](cvs)
        entry = {
            "id": i,
            "categoria": q["categoria"],
            "pregunta": q["q_en"] if lang == "en" else q["q_es"],
            "tipo_respuesta": q["tipo"],
            "respuesta": respuesta,
        }
        if isinstance(respuesta, list):
            entry["num_resultados"] = len(respuesta)
        preguntas.append(entry)

    return {
        "gold_standard": {
            "caso_uso": "cvs",
            "idioma": lang,
            "total_preguntas": len(preguntas),
            "total_cvs_analizados": len(cvs),
            "fecha_generacion": "2026-05-01",
            "categorias": dict(sorted(cat_counter.items())),
            "descripcion": (
                "Gold standard paralelo EN/ES para evaluar un sistema RAG sobre 300 CVs. "
                "Las preguntas son idénticas en ambos idiomas (mismo orden e índice) y están "
                "diseñadas combinando criterios AND y OR sobre skills, puestos, idiomas, "
                "temas (otros) y palabras clave de experiencia para producir listas de "
                "respuesta largas y representativas. Las respuestas se computan directamente "
                "sobre los datos fuente."
            ),
            "preguntas": preguntas,
        }
    }


def write_json(lang: str):
    payload = build_payload(lang)
    out = OUTPUT_DIR / f"gold_standard_cvs_{lang}.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    longitudes = [p["num_resultados"] for p in payload["gold_standard"]["preguntas"]
                  if "num_resultados" in p]
    if longitudes:
        avg = sum(longitudes) / len(longitudes)
        print(f"  {lang}: {len(payload['gold_standard']['preguntas'])} preguntas | "
              f"longitud media respuesta = {avg:.1f} | "
              f"min={min(longitudes)} max={max(longitudes)} -> {out.name}")
    else:
        print(f"  {lang}: {len(payload['gold_standard']['preguntas'])} preguntas -> {out.name}")


print(f"Total de plantillas de pregunta: {len(QUESTIONS)}")
write_json("en")
write_json("es")
print("OK.")
