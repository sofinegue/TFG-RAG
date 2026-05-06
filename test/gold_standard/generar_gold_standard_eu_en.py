"""
Script to generate the Gold Standard for the EU documents use case in English.
Generates 80-100 unique questions with answers extracted directly from the documents.

Data structure: Official Journal of the EU (L series) documents in JSON format
  - archivo, idioma, num_paginas, contenido, paginas

Author: Auto-generated for TFG
Date: 2026-04-17
"""

import json
import re
import random
from collections import Counter, defaultdict
from pathlib import Path

random.seed(42)

# ─────────────────────────────────────────────
# 1. LOAD ALL DOCUMENTS
# ─────────────────────────────────────────────
EU_DIR = Path(__file__).parent.parent.parent / "data" / "eu" / "en" / "json"
OUTPUT_DIR = Path(__file__).parent.parent / "data"

docs = {}
for f in sorted(EU_DIR.glob("*.json")):
    with open(f, encoding="utf-8") as fh:
        doc = json.load(fh)
        docs[doc["archivo"].replace(".pdf", "")] = doc

print(f"Loaded {len(docs)} documents")

# ─────────────────────────────────────────────
# 2. ANALYSE AND BUILD INDEXES
# ─────────────────────────────────────────────

doc_info = {}
for doc_id, doc in docs.items():
    text = doc["contenido"][:3000]

    # Document type
    m = re.search(r'(REGULATION|DECISION|CORRIGENDUM|AGREEMENT|DIRECTIVE)', text)
    tipo = m.group(1) if m else "OTHER"

    # Document code (e.g. 2026/193)
    m_code = re.search(r'(\d{4}/\d+)\s', text)
    code = m_code.group(1) if m_code else doc_id

    # Full title
    m_title = re.search(r'((?:COMMISSION\s+)?(?:IMPLEMENTING\s+|DELEGATED\s+)?(?:REGULATION|DECISION|CORRIGENDUM|DIRECTIVE|AGREEMENT)[\s\S]*?)(?:\n(?:THE EUROPEAN|Having regard|This|Whereas|\(Text))', text)
    titulo = m_title.group(1).replace('\n', ' ').strip() if m_title else ""
    titulo = re.sub(r'\s+', ' ', titulo)

    # Issuing body
    organos = []
    if "COMMISSION" in text[:2000]:
        organos.append("European Commission")
    if "COUNCIL" in text[:2000]:
        organos.append("Council")
    if "EUROPEAN PARLIAMENT" in text[:2000]:
        organos.append("European Parliament")

    # Document date
    m_fecha = re.search(r'of\s+(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', text)
    fecha = f"{m_fecha.group(1)} {m_fecha.group(2)} {m_fecha.group(3)}" if m_fecha else ""

    # Number of articles
    articulos_found = re.findall(r'Article\s+(\d+)', text + doc["contenido"][3000:])
    num_articulos = max([int(a) for a in articulos_found]) if articulos_found else 0

    # Number of recitals
    considerandos = re.findall(r'\((\d+)\)\s', doc["contenido"][:10000])
    num_considerandos = max([int(c) for c in considerandos]) if considerandos else 0

    # Cross-references
    refs = re.findall(r'(?:Regulation|Decision|Directive)\s+\([A-Z]+\)\s+(?:No\s*)?(\d{4}/\d+)', doc["contenido"])
    refs_unicas = sorted(set(refs))

    doc_info[doc_id] = {
        "tipo": tipo,
        "codigo": code,
        "titulo": titulo[:300],
        "organos": organos,
        "fecha": fecha,
        "num_paginas": doc["num_paginas"],
        "num_chars": len(doc["contenido"]),
        "num_palabras": len(doc["contenido"].split()),
        "num_articulos": num_articulos,
        "num_considerandos": num_considerandos,
        "refs": refs_unicas[:20],
    }

# Indexes
idx_tipo = defaultdict(list)
idx_organo = defaultdict(list)
for doc_id, info in doc_info.items():
    idx_tipo[info["tipo"]].append(doc_id)
    for org in info["organos"]:
        idx_organo[org].append(doc_id)

# Content search
def buscar_en_contenido(keyword):
    result = []
    for doc_id, doc in docs.items():
        if keyword.lower() in doc["contenido"].lower():
            result.append(doc_id)
    return result

# Debug info
for doc_id, info in doc_info.items():
    print(f"  {doc_id}: {info['tipo']} | {info['fecha']} | {info['num_paginas']} pgs | {info['num_articulos']} arts | orgs: {info['organos']}")

print(f"\nTypes: {dict(Counter(i['tipo'] for i in doc_info.values()))}")
print(f"Bodies: {dict(Counter(o for i in doc_info.values() for o in i['organos']))}")

# ─────────────────────────────────────────────
# 3. GENERATE QUESTIONS
# ─────────────────────────────────────────────
preguntas = []
q_id = 0

def add_q(cat, pregunta, respuesta, tipo="texto"):
    global q_id
    q_id += 1
    entry = {"id": q_id, "categoria": cat, "pregunta": pregunta, "tipo_respuesta": tipo}
    if isinstance(respuesta, list):
        try:
            entry["respuesta"] = sorted(respuesta)
        except TypeError:
            entry["respuesta"] = respuesta
        entry["num_resultados"] = len(respuesta)
    else:
        entry["respuesta"] = respuesta
    preguntas.append(entry)


doc_ids = list(docs.keys())
random.shuffle(doc_ids)
d_iter = iter(doc_ids)

def next_doc():
    d = next(d_iter)
    return d, docs[d], doc_info[d]


# ═══════════════════════════════════════════════
# CAT 1: DOCUMENT IDENTIFICATION (25)
# ═══════════════════════════════════════════════

d, doc, info = next_doc()
add_q("identification", f"What type of document is {info['codigo']}?", info["tipo"])
d, doc, info = next_doc()
add_q("identification", f"What is document {info['codigo']} about?", info["titulo"])
d, doc, info = next_doc()
add_q("identification", f"Who issued document {info['codigo']}?", info["organos"], "lista")
d, doc, info = next_doc()
add_q("identification", f"What is the date of document {info['codigo']}?", info["fecha"])
d, doc, info = next_doc()
add_q("identification", f"Give me the full title of document {d}.", info["titulo"])
d, doc, info = next_doc()
add_q("identification", f"Which European institution is responsible for document {info['codigo']}?", info["organos"], "lista")
d, doc, info = next_doc()
add_q("identification", f"Identify the type and date of document {info['codigo']}.", {"tipo": info["tipo"], "fecha": info["fecha"]}, "objeto")
d, doc, info = next_doc()
add_q("identification", f"How many pages does document {info['codigo']} have?", info["num_paginas"], "numero")
d, doc, info = next_doc()
add_q("identification", f"Summarise in one sentence the content of document {d}.", info["titulo"])
d, doc, info = next_doc()
add_q("identification", f"What does document number {info['codigo']} refer to?", info["titulo"])
d, doc, info = next_doc()
add_q("identification", f"How many articles does document {info['codigo']} contain?", info["num_articulos"], "numero")
d, doc, info = next_doc()
add_q("identification", f"Provide the main metadata of document {d}.",
      {"tipo": info["tipo"], "fecha": info["fecha"], "organos": info["organos"], "paginas": info["num_paginas"]}, "objeto")
d, doc, info = next_doc()
add_q("identification", f"What is the content of the document with code {info['codigo']}?", info["titulo"])
d, doc, info = next_doc()
add_q("identification", f"Which body approved document {info['codigo']}?", info["organos"], "lista")
d, doc, info = next_doc()
add_q("identification", f"I need to know what {d} is about. What is its main subject?", info["titulo"])
d, doc, info = next_doc()
add_q("identification", f"On what date was document {info['codigo']} adopted?", info["fecha"])
d, doc, info = next_doc()
add_q("identification", f"Briefly describe the purpose of document {info['codigo']}.", info["titulo"])
d, doc, info = next_doc()
add_q("identification", f"How many recitals does document {info['codigo']} have?", info["num_considerandos"], "numero")

remaining = list(d_iter)
if remaining:
    d = remaining[0]
    info = doc_info[d]
    add_q("identification", f"Approximately how many words does document {info['codigo']} have?", info["num_palabras"], "numero")

for i, d in enumerate(list(doc_info.keys())[:6]):
    info = doc_info[d]
    templates = [
        f"Is document {d} a regulation or a decision?",
        f"How many pages does the file {d} have?",
        f"State the date of adoption of {d}.",
        f"Which institutions participated in the drafting of {d}?",
        f"Give me a summary of document {d}.",
        f"What is the numerical code of the document contained in {d}?",
    ]
    respuestas = [
        info["tipo"],
        info["num_paginas"],
        info["fecha"],
        info["organos"],
        info["titulo"],
        info["codigo"],
    ]
    tipos = ["texto", "numero", "texto", "lista", "texto", "texto"]
    add_q("identification", templates[i], respuestas[i], tipos[i])


# ═══════════════════════════════════════════════
# CAT 2: SEARCH BY DOCUMENT TYPE (15)
# ═══════════════════════════════════════════════

add_q("search_by_type", "How many regulations are there in the database?", len(idx_tipo.get("REGULATION", [])), "numero")
add_q("search_by_type", "How many decisions does the collection contain?", len(idx_tipo.get("DECISION", [])), "numero")
add_q("search_by_type", "List all available regulations.", idx_tipo.get("REGULATION", []), "lista_documentos")
add_q("search_by_type", "Give me all decisions from the database.", idx_tipo.get("DECISION", []), "lista_documentos")
add_q("search_by_type", "What types of legislative documents do we have?", sorted(set(i["tipo"] for i in doc_info.values())), "lista")
add_q("search_by_type", "Is there any corrigendum document?",
      {"existe": "CORRIGENDUM" in idx_tipo or any("Corrigendum" in docs[d]["contenido"][:500] for d in docs),
       "documentos": idx_tipo.get("CORRIGENDUM", []) + [d for d in docs if "Corrigendum" in docs[d]["contenido"][:500]]}, "booleano")
add_q("search_by_type", "Filter documents that are implementing regulations.",
      [d for d in docs if "IMPLEMENTING REGULATION" in docs[d]["contenido"][:1000]], "lista_documentos")
add_q("search_by_type", "Which documents were issued by the European Commission?", idx_organo.get("European Commission", []), "lista_documentos")
add_q("search_by_type", "Which documents were approved by the Council?", idx_organo.get("Council", []), "lista_documentos")
add_q("search_by_type", "Are there any documents from the European Parliament?", idx_organo.get("European Parliament", []), "lista_documentos")
add_q("search_by_type", "How many documents did the European Commission issue?", len(idx_organo.get("European Commission", [])), "numero")
add_q("search_by_type", "What documents from 2026 do we have?",
      [d for d, i in doc_info.items() if "2026" in i["fecha"]], "lista_documentos")
add_q("search_by_type", "Which are the documents from 2025?",
      [d for d, i in doc_info.items() if "2025" in i["fecha"]], "lista_documentos")
add_q("search_by_type", "Find documents containing implementing decisions.",
      [d for d in docs if "IMPLEMENTING DECISION" in docs[d]["contenido"][:1000]], "lista_documentos")
add_q("search_by_type", "Which documents are delegated regulations?",
      [d for d in docs if "DELEGATED REGULATION" in docs[d]["contenido"][:1000]], "lista_documentos")


# ═══════════════════════════════════════════════
# CAT 3: SEARCH BY CONTENT / TOPIC (30)
# ═══════════════════════════════════════════════

temas = [
    ("fishing", "Which documents deal with fishing?"),
    ("medical devices", "Which documents refer to medical devices?"),
    ("Morocco", "Which documents make reference to Morocco?"),
    ("restrictive measures", "List the documents dealing with restrictive measures."),
    ("harmonised standards", "Which documents refer to harmonised standards?"),
    ("fishing opportunities", "Which documents regulate fishing opportunities?"),
    ("pesticides", "Are there documents mentioning pesticides or pesticide residues?"),
    ("Regulation (EU) 2017/745", "Which documents refer to Regulation (EU) 2017/745?"),
    ("African swine fever", "Are there documents about African swine fever?"),
    ("avian influenza", "Which documents mention avian influenza or bird flu?"),
    ("substances of human origin", "Is there any document about substances of human origin?"),
    ("geographical indication", "Which documents deal with geographical indications?"),
    ("European Fund", "Which documents refer to a European Fund?"),
    ("Tunisia", "Is Tunisia mentioned in any of the documents?"),
    ("Euro-Mediterranean", "Which documents refer to the Euro-Mediterranean agreement?"),
    ("sterilisation", "Are there documents about product sterilisation?"),
    ("Atlantic", "Which documents mention the Atlantic?"),
    ("Mediterranean", "List the documents referring to the Mediterranean."),
    ("Association Council", "Which documents mention an Association Council?"),
    ("annex", "Which documents contain or amend annexes?"),
    ("import", "Which documents deal with imports?"),
    ("CFSP", "Are there documents related to the Common Foreign and Security Policy (CFSP)?"),
    ("sanctions", "Which documents refer to sanctions?"),
    ("food safety", "Are there documents about food safety?"),
    ("Official Journal", "In how many documents is the Official Journal referenced?"),
    ("honey", "Is there any document mentioning honey?"),
    ("third countries", "Which documents refer to third countries?"),
    ("biocompatibility", "Is biocompatibility mentioned in any document?"),
    ("Baltic", "Which documents refer to the Baltic Sea?"),
    ("residues", "List the documents containing the word residues."),
]

for kw, pregunta in temas:
    r = buscar_en_contenido(kw)
    add_q("search_by_content", pregunta, r, "lista_documentos")


# ═══════════════════════════════════════════════
# CAT 4: COUNTING AND STATISTICS (25)
# ═══════════════════════════════════════════════

add_q("counting", "How many documents are there in total in the database?", len(docs), "numero")
add_q("counting", "How many pages do all documents have in total?",
      sum(d["num_paginas"] for d in docs.values()), "numero")
add_q("counting", "Which is the longest document by number of pages?",
      {"documento": max(doc_info.items(), key=lambda x: x[1]["num_paginas"])[0],
       "paginas": max(i["num_paginas"] for i in doc_info.values())}, "objeto")
add_q("counting", "Which is the shortest document?",
      {"documento": min(doc_info.items(), key=lambda x: x[1]["num_paginas"])[0],
       "paginas": min(i["num_paginas"] for i in doc_info.values())}, "objeto")
add_q("counting", "How many words are there in total across all documents?",
      sum(i["num_palabras"] for i in doc_info.values()), "numero")

avg_pags = round(sum(i["num_paginas"] for i in doc_info.values()) / len(doc_info), 1)
add_q("counting", "What is the average number of pages per document?", avg_pags, "numero")

avg_words = round(sum(i["num_palabras"] for i in doc_info.values()) / len(doc_info), 1)
add_q("counting", "What is the average number of words per document?", avg_words, "numero")

add_q("counting", "How many documents have more than 50 pages?",
      len([d for d, i in doc_info.items() if i["num_paginas"] > 50]), "numero")
add_q("counting", "How many documents have fewer than 10 pages?",
      len([d for d, i in doc_info.items() if i["num_paginas"] < 10]), "numero")

top5 = sorted(doc_info.items(), key=lambda x: -x[1]["num_paginas"])[:5]
add_q("counting", "What are the 5 longest documents?",
      [{"documento": d, "paginas": i["num_paginas"]} for d, i in top5], "ranking")

bot5 = sorted(doc_info.items(), key=lambda x: x[1]["num_paginas"])[:5]
add_q("counting", "What are the 5 shortest documents?",
      [{"documento": d, "paginas": i["num_paginas"]} for d, i in bot5], "ranking")

add_q("counting", "How many different types of documents exist?",
      len(set(i["tipo"] for i in doc_info.values())), "numero")

tipo_counts = Counter(i["tipo"] for i in doc_info.values())
add_q("counting", "What is the distribution of documents by type?",
      [{"tipo": t, "cantidad": c} for t, c in tipo_counts.most_common()], "ranking")

add_q("counting", "How many documents mention the word 'fishing'?",
      len(buscar_en_contenido("fishing")), "numero")
add_q("counting", "How many documents contain numbered articles?",
      len([d for d, i in doc_info.items() if i["num_articulos"] > 0]), "numero")

max_arts = max(doc_info.items(), key=lambda x: x[1]["num_articulos"])
add_q("counting", "Which document has the most articles?",
      {"documento": max_arts[0], "num_articulos": max_arts[1]["num_articulos"]}, "objeto")

add_q("counting", "How many documents were issued in January 2026?",
      len([d for d, i in doc_info.items() if "January 2026" in i["fecha"]]), "numero")
add_q("counting", "How many documents were issued in December 2025?",
      len([d for d, i in doc_info.items() if "December 2025" in i["fecha"]]), "numero")

add_q("counting", "How many documents mention sanctions or restrictive measures?",
      len(set(buscar_en_contenido("sanctions") + buscar_en_contenido("restrictive measures"))), "numero")

add_q("counting", "How many documents reference other EU regulations?",
      len([d for d, i in doc_info.items() if len(i["refs"]) > 0]), "numero")

total_refs = sum(len(i["refs"]) for i in doc_info.values())
add_q("counting", "How many cross-references to other documents are there in total?", total_refs, "numero")

add_q("counting", "How many documents exceed 100 pages?",
      len([d for d, i in doc_info.items() if i["num_paginas"] > 100]), "numero")

add_q("counting", "How many characters does the longest document have?",
      max(i["num_chars"] for i in doc_info.values()), "numero")

add_q("counting", "How many documents contain the word 'Regulation'?",
      len(buscar_en_contenido("Regulation")), "numero")


# ═══════════════════════════════════════════════
# CAT 5: CROSS-REFERENCES (20)
# ═══════════════════════════════════════════════

docs_con_refs = [(d, i) for d, i in doc_info.items() if len(i["refs"]) >= 2]
random.shuffle(docs_con_refs)
ref_iter = iter(docs_con_refs)

for template in [
    "Which other regulations or decisions does document {} reference?",
    "List the legislation cited in document {}.",
    "What prior legislation does document {} mention?",
    "What are the normative references in document {}?",
    "Give me the references to other legislative acts found in {}.",
    "Which regulations does document {} amend or cite?",
    "Identify the EU legislation referenced in {}.",
    "What other legislation is document {} related to?",
    "Enumerate the regulations and decisions cited in {}.",
    "What legal basis is mentioned in document {}?",
]:
    try:
        d, i = next(ref_iter)
        add_q("cross_references", template.format(i["codigo"]), i["refs"], "lista_referencias")
    except StopIteration:
        break

all_refs = defaultdict(list)
for d, i in doc_info.items():
    for r in i["refs"]:
        all_refs[r].append(d)

shared_refs = [(r, ds) for r, ds in all_refs.items() if len(ds) >= 2]
random.shuffle(shared_refs)

for template in [
    "Which documents reference {}?",
    "Which documents cite {}?",
    "List the documents that mention {}.",
    "In how many documents is {} referenced?",
    "Which documents are related to {}?",
]:
    if shared_refs:
        ref, ds = shared_refs.pop()
        ref_name = f"Regulation/Decision {ref}"
        add_q("cross_references", template.format(ref_name), ds, "lista_documentos")

for d, i in list(doc_info.items())[:5]:
    if i["refs"]:
        add_q("cross_references", f"How many references to other acts does document {i['codigo']} contain?",
              len(i["refs"]), "numero")


# ═══════════════════════════════════════════════
# CAT 6: DOCUMENT STRUCTURE (20)
# ═══════════════════════════════════════════════

for d, i in list(doc_info.items()):
    if i["num_articulos"] > 0:
        break
d_art = d
info_art = doc_info[d_art]

add_q("structure", f"How many articles does document {info_art['codigo']} have?", info_art["num_articulos"], "numero")

docs_con_consid = [(d, i) for d, i in doc_info.items() if i["num_considerandos"] > 0]
random.shuffle(docs_con_consid)

for idx, template in enumerate([
    "How many recitals does document {} have?",
    "How many recitals are there in the preamble of {}?",
    "State the number of recitals in document {}.",
    "How many points does the recital part of {} contain?",
    "Give me the total number of recitals in {}.",
]):
    if idx < len(docs_con_consid):
        d, i = docs_con_consid[idx]
        add_q("structure", template.format(i["codigo"]), i["num_considerandos"], "numero")

docs_con_anexo = buscar_en_contenido("ANNEX")
add_q("structure", "Which documents contain annexes?", docs_con_anexo, "lista_documentos")
add_q("structure", "How many documents include annexes?", len(docs_con_anexo), "numero")

docs_con_tabla = buscar_en_contenido("table")
add_q("structure", "Which documents contain tables?", docs_con_tabla, "lista_documentos")

arts_por_doc = sorted([(d, i["num_articulos"]) for d, i in doc_info.items() if i["num_articulos"] > 0],
                      key=lambda x: -x[1])
add_q("structure", "Which documents have articles and how many does each have?",
      [{"documento": d, "num_articulos": n} for d, n in arts_por_doc], "ranking")

add_q("structure", "List all documents ordered by number of pages from highest to lowest.",
      [{"documento": d, "paginas": i["num_paginas"]} for d, i in sorted(doc_info.items(), key=lambda x: -x[1]["num_paginas"])], "ranking")

docs_con_porcentaje = buscar_en_contenido("%")
add_q("structure", "Which documents contain percentage data?", docs_con_porcentaje, "lista_documentos")

docs_con_aplicacion = buscar_en_contenido("shall apply from")
add_q("structure", "Which documents specify a date of application?", docs_con_aplicacion, "lista_documentos")

docs_transitorio = buscar_en_contenido("transitional provisions")
if not docs_transitorio:
    docs_transitorio = buscar_en_contenido("transitional")
add_q("structure", "Are there documents with transitional provisions?", docs_transitorio, "lista_documentos")

docs_obligatorio = buscar_en_contenido("binding in its entirety")
add_q("structure", "Which documents declare themselves binding in their entirety?", docs_obligatorio, "lista_documentos")

all_docs_summary = [{"documento": d, "tipo": i["tipo"], "fecha": i["fecha"], "paginas": i["num_paginas"]}
                    for d, i in sorted(doc_info.items())]
add_q("structure", "Give me an overview of all documents with their type, date and number of pages.", all_docs_summary, "tabla")


# ═══════════════════════════════════════════════
# CAT 7: EXISTENCE AND VERIFICATION (20)
# ═══════════════════════════════════════════════

add_q("existence", "Is there any document about Atlantic fishing?",
      {"existe": len(set(buscar_en_contenido("fishing")) & set(buscar_en_contenido("Atlantic"))) > 0,
       "documentos": sorted(set(buscar_en_contenido("fishing")) & set(buscar_en_contenido("Atlantic")))}, "booleano")

add_q("existence", "Is there any implementing regulation in the database?",
      {"existe": len([d for d in docs if "IMPLEMENTING REGULATION" in docs[d]["contenido"][:1000]]) > 0,
       "documentos": [d for d in docs if "IMPLEMENTING REGULATION" in docs[d]["contenido"][:1000]]}, "booleano")

add_q("existence", "Are there documents dealing with Ukraine?",
      {"existe": len(buscar_en_contenido("Ukraine")) > 0, "documentos": buscar_en_contenido("Ukraine")}, "booleano")

add_q("existence", "Is Russia mentioned in any document?",
      {"existe": len(buscar_en_contenido("Russia")) > 0, "documentos": buscar_en_contenido("Russia")}, "booleano")

add_q("existence", "Is there any document about artificial intelligence?",
      {"existe": len(buscar_en_contenido("artificial intelligence")) > 0, "documentos": buscar_en_contenido("artificial intelligence")}, "booleano")

add_q("existence", "Are there documents about climate change?",
      {"existe": len(buscar_en_contenido("climate change")) > 0, "documentos": buscar_en_contenido("climate change")}, "booleano")

add_q("existence", "Are there documents relating to human rights?",
      {"existe": len(buscar_en_contenido("human rights")) > 0, "documentos": buscar_en_contenido("human rights")}, "booleano")

add_q("existence", "Is China mentioned in any document?",
      {"existe": len(buscar_en_contenido("China")) > 0, "documentos": buscar_en_contenido("China")}, "booleano")

add_q("existence", "Are there documents about agricultural policy?",
      {"existe": len(buscar_en_contenido("agricultural")) > 0, "documentos": buscar_en_contenido("agricultural")}, "booleano")

add_q("existence", "Is there any document that mentions the euro?",
      {"existe": len(buscar_en_contenido("euro")) > 0, "documentos": buscar_en_contenido("euro")}, "booleano")

add_q("existence", "Is NATO referenced in any document?",
      {"existe": len(buscar_en_contenido("NATO")) > 0, "documentos": buscar_en_contenido("NATO")}, "booleano")

add_q("existence", "Are there documents about data protection?",
      {"existe": len(buscar_en_contenido("data protection")) > 0, "documentos": buscar_en_contenido("data protection")}, "booleano")

add_q("existence", "Is there any document about transport?",
      {"existe": len(buscar_en_contenido("transport")) > 0, "documentos": buscar_en_contenido("transport")}, "booleano")

add_q("existence", "Is Syria mentioned in any of the documents?",
      {"existe": len(buscar_en_contenido("Syria")) > 0, "documentos": buscar_en_contenido("Syria")}, "booleano")

add_q("existence", "Are there documents dealing with energy?",
      {"existe": len(buscar_en_contenido("energy")) > 0, "documentos": buscar_en_contenido("energy")}, "booleano")

add_q("existence", "Is there any document relating to the European Economic Area (EEA)?",
      {"existe": len(buscar_en_contenido("EEA")) > 0, "documentos": buscar_en_contenido("EEA")}, "booleano")

add_q("existence", "Is Belarus mentioned in any document?",
      {"existe": len(buscar_en_contenido("Belarus")) > 0, "documentos": buscar_en_contenido("Belarus")}, "booleano")

add_q("existence", "Is there any document about customs or tariffs?",
      {"existe": len(set(buscar_en_contenido("customs") + buscar_en_contenido("tariff"))) > 0,
       "documentos": sorted(set(buscar_en_contenido("customs") + buscar_en_contenido("tariff")))}, "booleano")

add_q("existence", "Is there any document about medicines?",
      {"existe": len(buscar_en_contenido("medicinal")) > 0, "documentos": buscar_en_contenido("medicinal")}, "booleano")

add_q("existence", "Is there any document mentioning a protected designation of origin (PDO)?",
      {"existe": len(buscar_en_contenido("PDO")) > 0, "documentos": buscar_en_contenido("PDO")}, "booleano")


# ═══════════════════════════════════════════════
# CAT 8: LISTING AND CATALOGUE (15)
# ═══════════════════════════════════════════════

add_q("listing", "Give me the complete list of all available documents.", sorted(docs.keys()), "lista_documentos")
add_q("listing", "What are all the documents in the database?", sorted(docs.keys()), "lista_documentos")
add_q("listing", "Enumerate all the documents we have in the collection.", sorted(docs.keys()), "lista_documentos")
add_q("listing", "I need to see the full catalogue of EU documents.", sorted(docs.keys()), "lista_documentos")
add_q("listing", "Show me a list of all available Official Journal documents.", sorted(docs.keys()), "lista_documentos")

for org in sorted(idx_organo.keys()):
    add_q("listing", f"List all documents issued by the {org}.", sorted(idx_organo[org]), "lista_documentos")

for tipo in sorted(idx_tipo.keys()):
    add_q("listing", f"List all documents of type {tipo}.", sorted(idx_tipo[tipo]), "lista_documentos")

docs_2025 = sorted([d for d, i in doc_info.items() if "2025" in i["fecha"]])
docs_2026 = sorted([d for d, i in doc_info.items() if "2026" in i["fecha"]])
add_q("listing", "Which documents are from the year 2025?", docs_2025, "lista_documentos")
add_q("listing", "Which documents correspond to the year 2026?", docs_2026, "lista_documentos")


# ═══════════════════════════════════════════════
# CAT 9: COMPARISONS AND RELATIONSHIPS (30)
# ═══════════════════════════════════════════════

d_max = max(doc_info.items(), key=lambda x: x[1]["num_paginas"])
d_min = min(doc_info.items(), key=lambda x: x[1]["num_paginas"])
add_q("relationships", "Which is the longest document and which is the shortest?",
      {"longest": {"documento": d_max[0], "paginas": d_max[1]["num_paginas"]},
       "shortest": {"documento": d_min[0], "paginas": d_min[1]["num_paginas"]}}, "objeto")

add_q("relationships", "How many times longer is the longest document compared to the shortest?",
      round(d_max[1]["num_paginas"] / d_min[1]["num_paginas"], 1), "numero")

pesca_docs = set(buscar_en_contenido("fishing"))
sanitarios_docs = set(buscar_en_contenido("health"))
add_q("relationships", "Are there documents dealing simultaneously with fishing and health topics?",
      sorted(pesca_docs & sanitarios_docs), "lista_documentos")

top_refs = sorted(doc_info.items(), key=lambda x: -len(x[1]["refs"]))[:5]
add_q("relationships", "What are the 5 documents with the most references to other legislative acts?",
      [{"documento": d, "num_referencias": len(i["refs"])} for d, i in top_refs], "ranking")

countries = ["Spain", "France", "Germany", "Italy", "Portugal", "Greece", "Morocco", "Tunisia", "Norway", "Iceland"]
for pais in countries:
    docs_pais = buscar_en_contenido(pais)
    add_q("relationships", f"In which documents is {pais} mentioned?", docs_pais, "lista_documentos")

add_q("relationships", "Which documents were jointly issued by the European Parliament and the Council?",
      sorted(set(idx_organo.get("European Parliament", [])) & set(idx_organo.get("Council", []))), "lista_documentos")

add_q("relationships", "Which documents are related to health or medical matters?",
      sorted(set(buscar_en_contenido("health") + buscar_en_contenido("medical") + buscar_en_contenido("medicinal"))), "lista_documentos")

add_q("relationships", "Which documents deal with international trade or external relations?",
      sorted(set(buscar_en_contenido("trade") + buscar_en_contenido("external relations") + buscar_en_contenido("trade agreement"))), "lista_documentos")

docs_disposiciones = buscar_en_contenido("shall enter into force")
add_q("relationships", "Which documents contain provisions on entry into force?", docs_disposiciones, "lista_documentos")

regs = idx_tipo.get("REGULATION", [])
if len(regs) >= 2:
    r1, r2 = regs[0], regs[1]
    add_q("relationships", f"Compare documents {doc_info[r1]['codigo']} and {doc_info[r2]['codigo']}: what do they have in common?",
          {"common_type": "REGULATION",
           "doc1": {"codigo": doc_info[r1]["codigo"], "fecha": doc_info[r1]["fecha"], "paginas": doc_info[r1]["num_paginas"]},
           "doc2": {"codigo": doc_info[r2]["codigo"], "fecha": doc_info[r2]["fecha"], "paginas": doc_info[r2]["num_paginas"]}}, "objeto")

docs_por_fecha = sorted(doc_info.items(), key=lambda x: x[1]["fecha"], reverse=True)
add_q("relationships", "Which are the most recent documents?",
      [{"documento": d, "fecha": i["fecha"]} for d, i in docs_por_fecha[:5]], "ranking")

docs_seguridad = sorted(set(buscar_en_contenido("security") + buscar_en_contenido("defence")))
add_q("relationships", "Which documents address security or defence topics?", docs_seguridad, "lista_documentos")

docs_ambiente = sorted(set(buscar_en_contenido("environment") + buscar_en_contenido("environmental")))
add_q("relationships", "Are there documents related to the environment?", docs_ambiente, "lista_documentos")

top_arts = sorted(doc_info.items(), key=lambda x: -x[1]["num_articulos"])[:5]
add_q("relationships", "What are the 5 documents with the most articles?",
      [{"documento": d, "num_articulos": i["num_articulos"]} for d, i in top_arts], "ranking")

meses = Counter()
for d, i in doc_info.items():
    m = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)', i["fecha"])
    if m:
        meses[m.group(1)] += 1
add_q("relationships", "How are the documents distributed by month of issuance?",
      [{"month": m, "count": c} for m, c in meses.most_common()], "ranking")


# ═══════════════════════════════════════════════
# CAT 10: SPECIFIC CONTENT / DETAIL (25)
# ═══════════════════════════════════════════════

for d_id in list(doc_info.keys())[:8]:
    text = docs[d_id]["contenido"]
    info = doc_info[d_id]
    if info["num_articulos"] >= 2:
        m_art1 = re.search(r'Article\s+1\s*\n([\s\S]*?)(?:Article\s+2|\Z)', text)
        if m_art1:
            art1_text = m_art1.group(1).strip()[:500]
            art1_text = re.sub(r'\s+', ' ', art1_text)
            add_q("specific_content",
                  f"What is the content of Article 1 of document {info['codigo']}?",
                  art1_text, "texto_largo")
            break

for d_id in list(doc_info.keys()):
    if doc_info[d_id]["num_paginas"] >= 3:
        pag2 = docs[d_id]["paginas"][1][:300] if len(docs[d_id]["paginas"]) > 1 else ""
        if pag2.strip():
            pag2_clean = re.sub(r'\s+', ' ', pag2).strip()
            add_q("specific_content",
                  f"What information appears on page 2 of document {doc_info[d_id]['codigo']}?",
                  pag2_clean, "texto_largo")
            break

docs_vigor = []
for d_id, doc in docs.items():
    m = re.search(r'shall enter into force\s+(?:on\s+)?(.+?)(?:\.|$)', doc["contenido"])
    if m:
        docs_vigor.append({"documento": d_id, "entry_into_force": m.group(1).strip()[:100]})

if docs_vigor:
    add_q("specific_content", "Which documents specify their date of entry into force and when is it?",
          docs_vigor, "lista_detallada")

docs_ambito = []
for d_id, doc in docs.items():
    m = re.search(r'(?:scope|shall apply to|applicable to)[\s:]*(.{50,300})', doc["contenido"], re.IGNORECASE)
    if m:
        docs_ambito.append(d_id)
add_q("specific_content", "Which documents define their scope of application?", docs_ambito, "lista_documentos")

docs_definiciones = buscar_en_contenido("definitions")
add_q("specific_content", "Which documents contain a definitions section?", docs_definiciones, "lista_documentos")

docs_deroga = buscar_en_contenido("is repealed")
add_q("specific_content", "Which documents contain repeal clauses?", docs_deroga, "lista_documentos")

docs_modifica = buscar_en_contenido("is amended")
add_q("specific_content", "Which documents amend pre-existing legislation?", docs_modifica, "lista_documentos")

docs_comite = buscar_en_contenido("committee")
add_q("specific_content", "In which documents are committees referred to?", docs_comite, "lista_documentos")

docs_destinatarios = buscar_en_contenido("addressees")
if not docs_destinatarios:
    docs_destinatarios = buscar_en_contenido("addressed to the Member States")
add_q("specific_content", "Which documents mention their addressees?", docs_destinatarios, "lista_documentos")

docs_tratado = buscar_en_contenido("Treaty on the Functioning")
add_q("specific_content", "Which documents are based on the Treaty on the Functioning of the European Union?",
      docs_tratado, "lista_documentos")

docs_espana = buscar_en_contenido("Spain")
add_q("specific_content", "Which documents contain references to Spain?", docs_espana, "lista_documentos")

docs_especies = buscar_en_contenido("species")
add_q("specific_content", "Which documents refer to animal or plant species?", docs_especies, "lista_documentos")

docs_cuotas = buscar_en_contenido("quota")
add_q("specific_content", "Which documents mention quotas?", docs_cuotas, "lista_documentos")

docs_sancion_det = buscar_en_contenido("freezing of assets")
add_q("specific_content", "Which documents mention the freezing of assets?", docs_sancion_det, "lista_documentos")

docs_plazos = buscar_en_contenido("deadline")
add_q("specific_content", "In which documents are deadlines established?", docs_plazos, "lista_documentos")

docs_publicacion = buscar_en_contenido("publication in the Official Journal")
add_q("specific_content", "Which documents mention their publication in the Official Journal?", docs_publicacion, "lista_documentos")

docs_dictamen = buscar_en_contenido("opinion")
add_q("specific_content", "Which documents refer to opinions?", docs_dictamen, "lista_documentos")

docs_eemm = buscar_en_contenido("Member States")
add_q("specific_content", "How many documents refer to the Member States?",
      len(docs_eemm), "numero")

docs_personas = buscar_en_contenido("natural person")
add_q("specific_content", "Which documents mention natural persons?", docs_personas, "lista_documentos")

docs_toneladas = buscar_en_contenido("tonnes")
add_q("specific_content", "Which documents refer to tonnes?", docs_toneladas, "lista_documentos")

docs_cooperacion = buscar_en_contenido("cooperation")
add_q("specific_content", "In which documents is cooperation mentioned?", docs_cooperacion, "lista_documentos")


# ═══════════════════════════════════════════════
# CAT 11: CROSS-DOCUMENT (Knowledge Graph required)
# ═══════════════════════════════════════════════
# These questions REQUIRE synthesising information from 2+ documents.
# Basic vector RAG retrieves chunks independently and fails when the answer
# can only be constructed by relating facts across multiple documents.
# A knowledge graph (GraphRAG) should outperform basic RAG here.

# --- Build reverse index: which external regulation is cited by which docs ---
_ref_to_docs = defaultdict(set)
for _d, _info in doc_info.items():
    for _ref in _info.get("refs", []):
        _ref_to_docs[_ref].add(_d)

_ref_ranking = sorted(_ref_to_docs.items(), key=lambda x: (-len(x[1]), x[0]))

# Q1: Which docs cite the most-referenced regulation (requires aggregation)
if _ref_ranking and len(_ref_ranking[0][1]) >= 2:
    _top_ref, _top_docs = _ref_ranking[0]
    add_q("cross_document",
          f"List ALL documents in our corpus that cite regulation {_top_ref}.",
          sorted(_top_docs), "lista_documentos")

# Q2: Counting how many docs cite a given regulation
if len(_ref_ranking) >= 2 and len(_ref_ranking[1][1]) >= 2:
    _ref2, _docs2 = _ref_ranking[1]
    add_q("cross_document",
          f"How many documents in the corpus reference regulation {_ref2}?",
          len(_docs2), "numero")

# Q3: Total distinct cross-references in corpus
add_q("cross_document",
      "How many distinct external legislative acts are referenced across the entire corpus?",
      len(_ref_to_docs), "numero")

# Q4: Regulations cited by 2+ docs (multi-doc pattern)
_multi_cited = sorted(r for r, ds in _ref_to_docs.items() if len(ds) >= 2)
add_q("cross_document",
      "Which external regulations are cited by 2 or more documents in our corpus?",
      _multi_cited, "lista_referencias")

# Q5: Shared cross-references between document pairs
_doc_refs_set = {d: set(i.get("refs", [])) for d, i in doc_info.items()}
_doc_keys_list = sorted(_doc_refs_set.keys())
_pair_shared_refs = []
for _i, _d1 in enumerate(_doc_keys_list):
    for _d2 in _doc_keys_list[_i + 1:]:
        _common = _doc_refs_set[_d1] & _doc_refs_set[_d2]
        if _common:
            _pair_shared_refs.append((_d1, _d2, sorted(_common)))
_pair_shared_refs.sort(key=lambda x: -len(x[2]))

if _pair_shared_refs:
    _d1, _d2, _common = _pair_shared_refs[0]
    add_q("cross_document",
          f"Which legislative acts are referenced by BOTH document {doc_info[_d1]['codigo']} AND document {doc_info[_d2]['codigo']}?",
          _common, "lista_referencias")

# Q6: Most related pair (requires comparing ALL pairs)
if _pair_shared_refs:
    _d1, _d2, _common = _pair_shared_refs[0]
    add_q("cross_document",
          "Which pair of documents in the corpus shares the most cross-references? How many shared references do they have?",
          {"document_1": doc_info[_d1]["codigo"], "document_2": doc_info[_d2]["codigo"],
           "shared_count": len(_common), "shared_refs": _common}, "objeto")

# Q7: Multi-hop — doc cites another doc that IS in the corpus
_doc_codes = {info["codigo"]: d for d, info in doc_info.items() if info.get("codigo")}
_internal_refs = []
for _d, _info in doc_info.items():
    for _ref in _info.get("refs", []):
        if _ref in _doc_codes and _doc_codes[_ref] != _d:
            _internal_refs.append((_d, _doc_codes[_ref]))

if _internal_refs:
    _d1, _d2 = _internal_refs[0]
    add_q("cross_document",
          f"Document {doc_info[_d1]['codigo']} cites another document that is also in our corpus. Identify the cited document and describe what it addresses.",
          {"citing": doc_info[_d1]["codigo"], "cited": doc_info[_d2]["codigo"],
           "cited_title": doc_info[_d2]["titulo"][:200]}, "objeto")

# Q8: Documents with no outgoing cross-references
_no_refs = sorted(d for d, info in doc_info.items() if not info.get("refs"))
add_q("cross_document",
      "Which documents in the corpus do not cite any other legislative act?",
      _no_refs, "lista_documentos")

# Q9: Top-3 most-citing documents (requires comparing all docs)
_most_citing = sorted(doc_info.items(), key=lambda x: -len(x[1].get("refs", [])))[:3]
add_q("cross_document",
      "Which 3 documents cite the largest number of external regulations? Provide codes and counts.",
      [{"document": doc_info[_d]["codigo"], "num_references": len(_i.get("refs", []))} for _d, _i in _most_citing], "ranking")

# Q10: Synthesis across topic + institution
_comision_docs = set(idx_organo.get("European Commission", []))
_all_topics = buscar_en_contenido("fish") or buscar_en_contenido("trade") or buscar_en_contenido("health")
_synthesis_docs = sorted(_comision_docs & set(_all_topics))
if _synthesis_docs:
    add_q("cross_document",
          "Among documents issued by the European Commission, list their codes and dates (requires correlating body and metadata across multiple documents).",
          [{"document": _d, "codigo": doc_info[_d]["codigo"], "fecha": doc_info[_d]["fecha"]}
           for _d in sorted(_comision_docs)], "ranking")


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
    if cat == "cross_document":
        _filtered[cat] = qs
    else:
        _filtered[cat] = _remove_similar(qs, "pregunta")

_total_f = sum(len(v) for k, v in _filtered.items() if k != "cross_document") or 1
_selected = []
for cat, qs in sorted(_filtered.items()):
    if cat == "cross_document":
        _selected.extend(qs)
    else:
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
# VERIFICATION AND EXPORT
# ═══════════════════════════════════════════════
texts = [q["pregunta"] for q in preguntas]
dupes = [t for t in texts if texts.count(t) > 1]
if dupes:
    print(f"\nWARNING: {len(set(dupes))} duplicate questions:")
    for d in set(dupes):
        print(f"  - {d}")
else:
    print("\n✓ All questions are unique")

print(f"Total questions generated: {len(preguntas)}")

cat_counts = Counter(q["categoria"] for q in preguntas)
print("\nDistribution by category:")
for cat, cnt in sorted(cat_counts.items()):
    print(f"  {cat}: {cnt}")

gold_standard = {
    "gold_standard": {
        "caso_uso": "documentos_ue",
        "idioma": "en",
        "total_preguntas": len(preguntas),
        "total_documentos_analizados": len(docs),
        "fecha_generacion": "2026-04-17",
        "categorias": dict(sorted(cat_counts.items())),
        "descripcion": "Gold standard for evaluating a RAG system on Official Journal of the EU documents "
                       "in English (regulations, decisions, corrigenda). Contains questions on identification, "
                       "type search, content search, counting, cross-references, structure, "
                       "existence, listing, relationships and specific content. Includes a 'cross_document' "
                       "category with multi-hop questions (shared cross-references, reference chains, "
                       "multi-doc aggregations) designed to expose the limits of basic vector RAG "
                       "and to be answerable by a knowledge graph. All answers computed from data.",
        "preguntas": preguntas
    }
}

output_path = OUTPUT_DIR / "gold_standard_eu_en.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(gold_standard, f, ensure_ascii=False, indent=2)

print(f"\n✓ Gold standard saved to: {output_path}")
