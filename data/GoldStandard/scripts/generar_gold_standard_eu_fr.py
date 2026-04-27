"""
Script pour générer le Gold Standard du cas d'usage des documents de l'UE en français.
Génère 80-100 questions uniques avec des réponses extraites directement des documents.

Structure de données : documents du Journal officiel de l'UE (série L) au format JSON
  - archivo, idioma, num_paginas, contenido, paginas

Auteur : Généré automatiquement pour le TFG
Date : 2026-04-17
"""

import json
import re
import random
from collections import Counter, defaultdict
from pathlib import Path

random.seed(42)

# ─────────────────────────────────────────────
# 1. CHARGER TOUS LES DOCUMENTS
# ─────────────────────────────────────────────
EU_DIR = Path(__file__).parent.parent.parent / "eu" / "fr" / "json"
OUTPUT_DIR = Path(__file__).parent.parent

docs = {}
for f in sorted(EU_DIR.glob("*.json")):
    with open(f, encoding="utf-8") as fh:
        doc = json.load(fh)
        docs[doc["archivo"].replace(".pdf", "")] = doc

print(f"Chargés {len(docs)} documents")

# ─────────────────────────────────────────────
# 2. ANALYSER ET CONSTRUIRE DES INDEX
# ─────────────────────────────────────────────

doc_info = {}
for doc_id, doc in docs.items():
    text = doc["contenido"][:3000]

    # Type de document
    m = re.search(r'(RÈGLEMENT|DÉCISION|RECTIFICATIF|ACCORD|DIRECTIVE)', text)
    tipo = m.group(1) if m else "AUTRE"

    # Code du document
    m_code = re.search(r'(\d{4}/\d+)\s', text)
    code = m_code.group(1) if m_code else doc_id

    # Titre complet
    m_title = re.search(r'((?:RÈGLEMENT|DÉCISION|RECTIFICATIF|DIRECTIVE|ACCORD)[\s\S]*?)(?:\n(?:LA COMMISSION|LE CONSEIL|LE PARLEMENT|vu\s|considérant|\(Texte))', text)
    titulo = m_title.group(1).replace('\n', ' ').strip() if m_title else ""
    titulo = re.sub(r'\s+', ' ', titulo)

    # Organisme émetteur
    organos = []
    if "COMMISSION" in text[:2000]:
        organos.append("Commission européenne")
    if "CONSEIL" in text[:2000]:
        organos.append("Conseil")
    if "PARLEMENT EUROPÉEN" in text[:2000]:
        organos.append("Parlement européen")

    # Date du document
    m_fecha = re.search(r'du\s+(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})', text)
    fecha = f"{m_fecha.group(1)} {m_fecha.group(2)} {m_fecha.group(3)}" if m_fecha else ""

    # Nombre d'articles
    articulos_found = re.findall(r'Article\s+(\d+)', text + doc["contenido"][3000:])
    num_articulos = max([int(a) for a in articulos_found]) if articulos_found else 0

    # Nombre de considérants
    considerandos = re.findall(r'\((\d+)\)\s', doc["contenido"][:10000])
    num_considerandos = max([int(c) for c in considerandos]) if considerandos else 0

    # Références croisées
    refs = re.findall(r'(?:règlement|décision|directive)\s+\([A-Z]+\)\s+(?:n[°o]\s*)?(\d{4}/\d+)', doc["contenido"], re.IGNORECASE)
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

# Index
idx_tipo = defaultdict(list)
idx_organo = defaultdict(list)
for doc_id, info in doc_info.items():
    idx_tipo[info["tipo"]].append(doc_id)
    for org in info["organos"]:
        idx_organo[org].append(doc_id)

def buscar_en_contenido(keyword):
    result = []
    for doc_id, doc in docs.items():
        if keyword.lower() in doc["contenido"].lower():
            result.append(doc_id)
    return result

# Debug
for doc_id, info in doc_info.items():
    print(f"  {doc_id}: {info['tipo']} | {info['fecha']} | {info['num_paginas']} p. | {info['num_articulos']} arts | org: {info['organos']}")

print(f"\nTypes : {dict(Counter(i['tipo'] for i in doc_info.values()))}")
print(f"Organes : {dict(Counter(o for i in doc_info.values() for o in i['organos']))}")

# ─────────────────────────────────────────────
# 3. GÉNÉRER LES QUESTIONS
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
# CAT 1 : IDENTIFICATION DES DOCUMENTS (25)
# ═══════════════════════════════════════════════

d, doc, info = next_doc()
add_q("identification", f"Quel est le type du document {info['codigo']} ?", info["tipo"])
d, doc, info = next_doc()
add_q("identification", f"De quoi traite le document {info['codigo']} ?", info["titulo"])
d, doc, info = next_doc()
add_q("identification", f"Qui a émis le document {info['codigo']} ?", info["organos"], "lista")
d, doc, info = next_doc()
add_q("identification", f"Quelle est la date du document {info['codigo']} ?", info["fecha"])
d, doc, info = next_doc()
add_q("identification", f"Donnez-moi le titre complet du document {d}.", info["titulo"])
d, doc, info = next_doc()
add_q("identification", f"Quelle institution européenne est responsable du document {info['codigo']} ?", info["organos"], "lista")
d, doc, info = next_doc()
add_q("identification", f"Identifiez le type et la date du document {info['codigo']}.", {"tipo": info["tipo"], "fecha": info["fecha"]}, "objeto")
d, doc, info = next_doc()
add_q("identification", f"Combien de pages comporte le document {info['codigo']} ?", info["num_paginas"], "numero")
d, doc, info = next_doc()
add_q("identification", f"Résumez en une phrase le contenu du document {d}.", info["titulo"])
d, doc, info = next_doc()
add_q("identification", f"À quoi se réfère le document numéro {info['codigo']} ?", info["titulo"])
d, doc, info = next_doc()
add_q("identification", f"Combien d'articles contient le document {info['codigo']} ?", info["num_articulos"], "numero")
d, doc, info = next_doc()
add_q("identification", f"Fournissez les métadonnées principales du document {d}.",
      {"tipo": info["tipo"], "fecha": info["fecha"], "organos": info["organos"], "paginas": info["num_paginas"]}, "objeto")
d, doc, info = next_doc()
add_q("identification", f"Quel est le contenu du document avec le code {info['codigo']} ?", info["titulo"])
d, doc, info = next_doc()
add_q("identification", f"Quel organisme a approuvé le document {info['codigo']} ?", info["organos"], "lista")
d, doc, info = next_doc()
add_q("identification", f"J'ai besoin de savoir de quoi traite {d}. Quel est son sujet principal ?", info["titulo"])
d, doc, info = next_doc()
add_q("identification", f"À quelle date le document {info['codigo']} a-t-il été adopté ?", info["fecha"])
d, doc, info = next_doc()
add_q("identification", f"Décrivez brièvement l'objet du document {info['codigo']}.", info["titulo"])
d, doc, info = next_doc()
add_q("identification", f"Combien de considérants comporte le document {info['codigo']} ?", info["num_considerandos"], "numero")

remaining = list(d_iter)
if remaining:
    d = remaining[0]
    info = doc_info[d]
    add_q("identification", f"Combien de mots contient approximativement le document {info['codigo']} ?", info["num_palabras"], "numero")

for i, d in enumerate(list(doc_info.keys())[:6]):
    info = doc_info[d]
    templates = [
        f"Le document {d} est-il un règlement ou une décision ?",
        f"Combien de pages fait le fichier {d} ?",
        f"Indiquez la date d'adoption de {d}.",
        f"Quelles institutions ont participé à l'élaboration de {d} ?",
        f"Donnez-moi un résumé du document {d}.",
        f"Quel est le code numérique du document contenu dans {d} ?",
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
# CAT 2 : RECHERCHE PAR TYPE DE DOCUMENT (15)
# ═══════════════════════════════════════════════

add_q("recherche_par_type", "Combien de règlements y a-t-il dans la base de données ?", len(idx_tipo.get("RÈGLEMENT", [])), "numero")
add_q("recherche_par_type", "Combien de décisions la collection contient-elle ?", len(idx_tipo.get("DÉCISION", [])), "numero")
add_q("recherche_par_type", "Listez tous les règlements disponibles.", idx_tipo.get("RÈGLEMENT", []), "lista_documentos")
add_q("recherche_par_type", "Donnez-moi toutes les décisions de la base de données.", idx_tipo.get("DÉCISION", []), "lista_documentos")
add_q("recherche_par_type", "Quels types de documents législatifs avons-nous ?", sorted(set(i["tipo"] for i in doc_info.values())), "lista")
add_q("recherche_par_type", "Y a-t-il un document de type rectificatif ?",
      {"existe": "RECTIFICATIF" in idx_tipo or any("Rectificatif" in docs[d]["contenido"][:500] for d in docs),
       "documentos": idx_tipo.get("RECTIFICATIF", []) + [d for d in docs if "Rectificatif" in docs[d]["contenido"][:500]]}, "booleano")
add_q("recherche_par_type", "Filtrer les documents qui sont des règlements d'exécution.",
      [d for d in docs if "RÈGLEMENT D'EXÉCUTION" in docs[d]["contenido"][:1000] or "RÈGLEMENT D\u2019EXÉCUTION" in docs[d]["contenido"][:1000]], "lista_documentos")
add_q("recherche_par_type", "Quels sont les documents émis par la Commission européenne ?", idx_organo.get("Commission européenne", []), "lista_documentos")
add_q("recherche_par_type", "Quels documents ont été approuvés par le Conseil ?", idx_organo.get("Conseil", []), "lista_documentos")
add_q("recherche_par_type", "Y a-t-il des documents du Parlement européen ?", idx_organo.get("Parlement européen", []), "lista_documentos")
add_q("recherche_par_type", "Combien de documents la Commission européenne a-t-elle émis ?", len(idx_organo.get("Commission européenne", [])), "numero")
add_q("recherche_par_type", "Quels documents de 2026 avons-nous ?",
      [d for d, i in doc_info.items() if "2026" in i["fecha"]], "lista_documentos")
add_q("recherche_par_type", "Quels sont les documents de 2025 ?",
      [d for d, i in doc_info.items() if "2025" in i["fecha"]], "lista_documentos")
add_q("recherche_par_type", "Chercher les documents contenant des décisions d'exécution.",
      [d for d in docs if "DÉCISION D'EXÉCUTION" in docs[d]["contenido"][:1000] or "DÉCISION D\u2019EXÉCUTION" in docs[d]["contenido"][:1000]], "lista_documentos")
add_q("recherche_par_type", "Quels documents sont des règlements délégués ?",
      [d for d in docs if "RÈGLEMENT DÉLÉGUÉ" in docs[d]["contenido"][:1000]], "lista_documentos")


# ═══════════════════════════════════════════════
# CAT 3 : RECHERCHE PAR CONTENU / THÉMATIQUE (30)
# ═══════════════════════════════════════════════

temas = [
    ("pêche", "Quels documents traitent de la pêche ?"),
    ("dispositifs médicaux", "Quels documents font référence aux dispositifs médicaux ?"),
    ("Maroc", "Dans quels documents le Maroc est-il mentionné ?"),
    ("mesures restrictives", "Listez les documents traitant de mesures restrictives."),
    ("normes harmonisées", "Quels documents font référence à des normes harmonisées ?"),
    ("possibilités de pêche", "Quels documents réglementent les possibilités de pêche ?"),
    ("pesticides", "Y a-t-il des documents mentionnant des pesticides ou résidus de pesticides ?"),
    ("Règlement (UE) 2017/745", "Quels documents font référence au Règlement (UE) 2017/745 ?"),
    ("peste porcine", "Y a-t-il des documents sur la peste porcine ?"),
    ("influenza aviaire", "Quels documents mentionnent l'influenza aviaire ou la grippe aviaire ?"),
    ("substances d'origine humaine", "Y a-t-il un document sur les substances d'origine humaine ?"),
    ("indication géographique", "Quels documents traitent des indications géographiques ?"),
    ("Fonds européen", "Quels documents font référence à un Fonds européen ?"),
    ("Tunisie", "La Tunisie est-elle mentionnée dans l'un des documents ?"),
    ("euroméditerranéen", "Quels documents font référence à l'accord euroméditerranéen ?"),
    ("stérilisation", "Y a-t-il des documents sur la stérilisation de produits ?"),
    ("Atlantique", "Quels documents mentionnent l'Atlantique ?"),
    ("Méditerranée", "Listez les documents qui se réfèrent à la Méditerranée."),
    ("Conseil d'association", "Quels documents mentionnent un Conseil d'association ?"),
    ("annexe", "Quels documents contiennent ou modifient des annexes ?"),
    ("importation", "Quels documents traitent des importations ?"),
    ("PESC", "Y a-t-il des documents liés à la Politique étrangère et de sécurité commune (PESC) ?"),
    ("sanctions", "Quels documents font référence à des sanctions ?"),
    ("sécurité alimentaire", "Y a-t-il des documents sur la sécurité alimentaire ?"),
    ("Journal officiel", "Dans combien de documents le Journal officiel est-il référencé ?"),
    ("miel", "Y a-t-il un document qui mentionne le miel ?"),
    ("pays tiers", "Quels documents font référence aux pays tiers ?"),
    ("biocompatibilité", "La biocompatibilité est-elle mentionnée dans un document ?"),
    ("Baltique", "Quels documents font référence à la mer Baltique ?"),
    ("résidus", "Listez les documents contenant le mot résidus."),
]

for kw, pregunta in temas:
    r = buscar_en_contenido(kw)
    add_q("recherche_par_contenu", pregunta, r, "lista_documentos")


# ═══════════════════════════════════════════════
# CAT 4 : COMPTAGE ET STATISTIQUES (25)
# ═══════════════════════════════════════════════

add_q("comptage", "Combien de documents y a-t-il au total dans la base de données ?", len(docs), "numero")
add_q("comptage", "Combien de pages totalisent tous les documents réunis ?",
      sum(d["num_paginas"] for d in docs.values()), "numero")
add_q("comptage", "Quel est le document le plus long en nombre de pages ?",
      {"documento": max(doc_info.items(), key=lambda x: x[1]["num_paginas"])[0],
       "paginas": max(i["num_paginas"] for i in doc_info.values())}, "objeto")
add_q("comptage", "Quel est le document le plus court ?",
      {"documento": min(doc_info.items(), key=lambda x: x[1]["num_paginas"])[0],
       "paginas": min(i["num_paginas"] for i in doc_info.values())}, "objeto")
add_q("comptage", "Combien de mots y a-t-il au total dans tous les documents ?",
      sum(i["num_palabras"] for i in doc_info.values()), "numero")

avg_pags = round(sum(i["num_paginas"] for i in doc_info.values()) / len(doc_info), 1)
add_q("comptage", "Quelle est la moyenne de pages par document ?", avg_pags, "numero")

avg_words = round(sum(i["num_palabras"] for i in doc_info.values()) / len(doc_info), 1)
add_q("comptage", "Quelle est la moyenne de mots par document ?", avg_words, "numero")

add_q("comptage", "Combien de documents ont plus de 50 pages ?",
      len([d for d, i in doc_info.items() if i["num_paginas"] > 50]), "numero")
add_q("comptage", "Combien de documents ont moins de 10 pages ?",
      len([d for d, i in doc_info.items() if i["num_paginas"] < 10]), "numero")

top5 = sorted(doc_info.items(), key=lambda x: -x[1]["num_paginas"])[:5]
add_q("comptage", "Quels sont les 5 documents les plus longs ?",
      [{"documento": d, "paginas": i["num_paginas"]} for d, i in top5], "ranking")

bot5 = sorted(doc_info.items(), key=lambda x: x[1]["num_paginas"])[:5]
add_q("comptage", "Quels sont les 5 documents les plus courts ?",
      [{"documento": d, "paginas": i["num_paginas"]} for d, i in bot5], "ranking")

add_q("comptage", "Combien de types de documents différents existent ?",
      len(set(i["tipo"] for i in doc_info.values())), "numero")

tipo_counts = Counter(i["tipo"] for i in doc_info.values())
add_q("comptage", "Quelle est la répartition des documents par type ?",
      [{"tipo": t, "cantidad": c} for t, c in tipo_counts.most_common()], "ranking")

add_q("comptage", "Combien de documents mentionnent le mot « pêche » ?",
      len(buscar_en_contenido("pêche")), "numero")
add_q("comptage", "Combien de documents contiennent des articles numérotés ?",
      len([d for d, i in doc_info.items() if i["num_articulos"] > 0]), "numero")

max_arts = max(doc_info.items(), key=lambda x: x[1]["num_articulos"])
add_q("comptage", "Quel document a le plus d'articles ?",
      {"documento": max_arts[0], "num_articulos": max_arts[1]["num_articulos"]}, "objeto")

add_q("comptage", "Combien de documents ont été émis en janvier 2026 ?",
      len([d for d, i in doc_info.items() if "janvier 2026" in i["fecha"]]), "numero")
add_q("comptage", "Combien de documents ont été émis en décembre 2025 ?",
      len([d for d, i in doc_info.items() if "décembre 2025" in i["fecha"]]), "numero")

add_q("comptage", "Combien de documents mentionnent des sanctions ou des mesures restrictives ?",
      len(set(buscar_en_contenido("sanctions") + buscar_en_contenido("mesures restrictives"))), "numero")

add_q("comptage", "Combien de documents font référence à d'autres règlements de l'UE ?",
      len([d for d, i in doc_info.items() if len(i["refs"]) > 0]), "numero")

total_refs = sum(len(i["refs"]) for i in doc_info.values())
add_q("comptage", "Combien de références croisées à d'autres documents y a-t-il au total ?", total_refs, "numero")

add_q("comptage", "Combien de documents dépassent les 100 pages ?",
      len([d for d, i in doc_info.items() if i["num_paginas"] > 100]), "numero")

add_q("comptage", "Combien de caractères comporte le document le plus long ?",
      max(i["num_chars"] for i in doc_info.values()), "numero")

add_q("comptage", "Combien de documents contiennent le mot « Règlement » ?",
      len(buscar_en_contenido("Règlement")), "numero")


# ═══════════════════════════════════════════════
# CAT 5 : RÉFÉRENCES CROISÉES (20)
# ═══════════════════════════════════════════════

docs_con_refs = [(d, i) for d, i in doc_info.items() if len(i["refs"]) >= 2]
random.shuffle(docs_con_refs)
ref_iter = iter(docs_con_refs)

for template in [
    "À quels autres règlements ou décisions le document {} fait-il référence ?",
    "Listez les normes citées dans le document {}.",
    "Quelle législation antérieure le document {} mentionne-t-il ?",
    "Quelles sont les références normatives du document {} ?",
    "Donnez-moi les références à d'autres actes législatifs figurant dans {}.",
    "Quels règlements le document {} modifie-t-il ou cite-t-il ?",
    "Identifiez la législation de l'UE référencée dans {}.",
    "À quelle autre législation le document {} est-il lié ?",
    "Énumérez les règlements et décisions cités dans {}.",
    "Quelle base juridique est mentionnée dans le document {} ?",
]:
    try:
        d, i = next(ref_iter)
        add_q("references_croisees", template.format(i["codigo"]), i["refs"], "lista_referencias")
    except StopIteration:
        break

all_refs = defaultdict(list)
for d, i in doc_info.items():
    for r in i["refs"]:
        all_refs[r].append(d)

shared_refs = [(r, ds) for r, ds in all_refs.items() if len(ds) >= 2]
random.shuffle(shared_refs)

for template in [
    "Quels documents font référence au {} ?",
    "Quels documents citent le {} ?",
    "Listez les documents qui mentionnent le {}.",
    "Dans combien de documents le {} est-il référencé ?",
    "Quels documents sont liés au {} ?",
]:
    if shared_refs:
        ref, ds = shared_refs.pop()
        ref_name = f"Règlement/Décision {ref}"
        add_q("references_croisees", template.format(ref_name), ds, "lista_documentos")

for d, i in list(doc_info.items())[:5]:
    if i["refs"]:
        add_q("references_croisees", f"Combien de références à d'autres actes le document {i['codigo']} contient-il ?",
              len(i["refs"]), "numero")


# ═══════════════════════════════════════════════
# CAT 6 : STRUCTURE DES DOCUMENTS (20)
# ═══════════════════════════════════════════════

for d, i in list(doc_info.items()):
    if i["num_articulos"] > 0:
        break
d_art = d
info_art = doc_info[d_art]

add_q("structure", f"Combien d'articles comporte le document {info_art['codigo']} ?", info_art["num_articulos"], "numero")

docs_con_consid = [(d, i) for d, i in doc_info.items() if i["num_considerandos"] > 0]
random.shuffle(docs_con_consid)

for idx, template in enumerate([
    "Combien de considérants comporte le document {} ?",
    "Combien de considérants compte le préambule de {} ?",
    "Indiquez le nombre de considérants du document {}.",
    "Combien de points la partie considérative de {} contient-elle ?",
    "Donnez-moi le nombre total de considérants de {}.",
]):
    if idx < len(docs_con_consid):
        d, i = docs_con_consid[idx]
        add_q("structure", template.format(i["codigo"]), i["num_considerandos"], "numero")

docs_con_anexo = buscar_en_contenido("ANNEXE")
add_q("structure", "Quels documents contiennent des annexes ?", docs_con_anexo, "lista_documentos")
add_q("structure", "Combien de documents incluent des annexes ?", len(docs_con_anexo), "numero")

docs_con_tabla = buscar_en_contenido("tableau")
add_q("structure", "Quels documents contiennent des tableaux ?", docs_con_tabla, "lista_documentos")

arts_por_doc = sorted([(d, i["num_articulos"]) for d, i in doc_info.items() if i["num_articulos"] > 0],
                      key=lambda x: -x[1])
add_q("structure", "Quels documents ont des articles et combien en a chacun ?",
      [{"documento": d, "num_articulos": n} for d, n in arts_por_doc], "ranking")

add_q("structure", "Listez tous les documents classés par nombre de pages du plus grand au plus petit.",
      [{"documento": d, "paginas": i["num_paginas"]} for d, i in sorted(doc_info.items(), key=lambda x: -x[1]["num_paginas"])], "ranking")

docs_con_porcentaje = buscar_en_contenido("%")
add_q("structure", "Quels documents contiennent des données en pourcentage ?", docs_con_porcentaje, "lista_documentos")

docs_con_aplicacion = buscar_en_contenido("est applicable à partir")
add_q("structure", "Quels documents précisent une date d'application ?", docs_con_aplicacion, "lista_documentos")

docs_transitorio = buscar_en_contenido("dispositions transitoires")
if not docs_transitorio:
    docs_transitorio = buscar_en_contenido("transitoire")
add_q("structure", "Y a-t-il des documents avec des dispositions transitoires ?", docs_transitorio, "lista_documentos")

docs_obligatorio = buscar_en_contenido("obligatoire dans tous ses éléments")
add_q("structure", "Quels documents se déclarent obligatoires dans tous leurs éléments ?", docs_obligatorio, "lista_documentos")

all_docs_summary = [{"documento": d, "tipo": i["tipo"], "fecha": i["fecha"], "paginas": i["num_paginas"]}
                    for d, i in sorted(doc_info.items())]
add_q("structure", "Donnez-moi une vue d'ensemble de tous les documents avec leur type, date et nombre de pages.", all_docs_summary, "tabla")


# ═══════════════════════════════════════════════
# CAT 7 : EXISTENCE ET VÉRIFICATION (20)
# ═══════════════════════════════════════════════

add_q("existence", "Y a-t-il un document sur la pêche dans l'Atlantique ?",
      {"existe": len(set(buscar_en_contenido("pêche")) & set(buscar_en_contenido("Atlantique"))) > 0,
       "documentos": sorted(set(buscar_en_contenido("pêche")) & set(buscar_en_contenido("Atlantique")))}, "booleano")

add_q("existence", "Existe-t-il un règlement d'exécution dans la base de données ?",
      {"existe": len([d for d in docs if "RÈGLEMENT D'EXÉCUTION" in docs[d]["contenido"][:1000] or "RÈGLEMENT D\u2019EXÉCUTION" in docs[d]["contenido"][:1000]]) > 0,
       "documentos": [d for d in docs if "RÈGLEMENT D'EXÉCUTION" in docs[d]["contenido"][:1000] or "RÈGLEMENT D\u2019EXÉCUTION" in docs[d]["contenido"][:1000]]}, "booleano")

add_q("existence", "Y a-t-il des documents traitant de l'Ukraine ?",
      {"existe": len(buscar_en_contenido("Ukraine")) > 0, "documentos": buscar_en_contenido("Ukraine")}, "booleano")

add_q("existence", "La Russie est-elle mentionnée dans un document ?",
      {"existe": len(buscar_en_contenido("Russie")) > 0, "documentos": buscar_en_contenido("Russie")}, "booleano")

add_q("existence", "Y a-t-il un document sur l'intelligence artificielle ?",
      {"existe": len(buscar_en_contenido("intelligence artificielle")) > 0, "documentos": buscar_en_contenido("intelligence artificielle")}, "booleano")

add_q("existence", "Y a-t-il des documents sur le changement climatique ?",
      {"existe": len(buscar_en_contenido("changement climatique")) > 0, "documentos": buscar_en_contenido("changement climatique")}, "booleano")

add_q("existence", "Y a-t-il des documents relatifs aux droits de l'homme ?",
      {"existe": len(buscar_en_contenido("droits de l'homme")) > 0, "documentos": buscar_en_contenido("droits de l'homme")}, "booleano")

add_q("existence", "La Chine est-elle mentionnée dans un document ?",
      {"existe": len(buscar_en_contenido("Chine")) > 0, "documentos": buscar_en_contenido("Chine")}, "booleano")

add_q("existence", "Y a-t-il des documents sur la politique agricole ?",
      {"existe": len(buscar_en_contenido("agricole")) > 0, "documentos": buscar_en_contenido("agricole")}, "booleano")

add_q("existence", "Y a-t-il un document mentionnant l'euro ?",
      {"existe": len(buscar_en_contenido("euro")) > 0, "documentos": buscar_en_contenido("euro")}, "booleano")

add_q("existence", "L'OTAN est-elle mentionnée dans un document ?",
      {"existe": len(buscar_en_contenido("OTAN")) > 0, "documentos": buscar_en_contenido("OTAN")}, "booleano")

add_q("existence", "Y a-t-il des documents sur la protection des données ?",
      {"existe": len(buscar_en_contenido("protection des données")) > 0, "documentos": buscar_en_contenido("protection des données")}, "booleano")

add_q("existence", "Y a-t-il un document sur les transports ?",
      {"existe": len(buscar_en_contenido("transport")) > 0, "documentos": buscar_en_contenido("transport")}, "booleano")

add_q("existence", "La Syrie est-elle mentionnée dans l'un des documents ?",
      {"existe": len(buscar_en_contenido("Syrie")) > 0, "documentos": buscar_en_contenido("Syrie")}, "booleano")

add_q("existence", "Y a-t-il des documents traitant de l'énergie ?",
      {"existe": len(buscar_en_contenido("énergie")) > 0, "documentos": buscar_en_contenido("énergie")}, "booleano")

add_q("existence", "Y a-t-il un document relatif à l'Espace économique européen (EEE) ?",
      {"existe": len(buscar_en_contenido("EEE")) > 0, "documentos": buscar_en_contenido("EEE")}, "booleano")

add_q("existence", "La Biélorussie est-elle mentionnée dans un document ?",
      {"existe": len(buscar_en_contenido("Biélorussie")) > 0, "documentos": buscar_en_contenido("Biélorussie")}, "booleano")

add_q("existence", "Y a-t-il un document sur les douanes ou les tarifs ?",
      {"existe": len(set(buscar_en_contenido("douane") + buscar_en_contenido("tarif"))) > 0,
       "documentos": sorted(set(buscar_en_contenido("douane") + buscar_en_contenido("tarif")))}, "booleano")

add_q("existence", "Y a-t-il un document sur les médicaments ?",
      {"existe": len(buscar_en_contenido("médicament")) > 0, "documentos": buscar_en_contenido("médicament")}, "booleano")

add_q("existence", "Y a-t-il un document mentionnant une appellation d'origine protégée (AOP) ?",
      {"existe": len(buscar_en_contenido("AOP")) > 0, "documentos": buscar_en_contenido("AOP")}, "booleano")


# ═══════════════════════════════════════════════
# CAT 8 : LISTAGE ET CATALOGUE (15)
# ═══════════════════════════════════════════════

add_q("listage", "Donnez-moi la liste complète de tous les documents disponibles.", sorted(docs.keys()), "lista_documentos")
add_q("listage", "Quels sont tous les documents de la base de données ?", sorted(docs.keys()), "lista_documentos")
add_q("listage", "Énumérez tous les documents de la collection.", sorted(docs.keys()), "lista_documentos")
add_q("listage", "J'ai besoin de voir le catalogue complet des documents de l'UE.", sorted(docs.keys()), "lista_documentos")
add_q("listage", "Montrez-moi une liste de tous les documents du Journal officiel disponibles.", sorted(docs.keys()), "lista_documentos")

for org in sorted(idx_organo.keys()):
    add_q("listage", f"Listez tous les documents émis par {org}.", sorted(idx_organo[org]), "lista_documentos")

for tipo in sorted(idx_tipo.keys()):
    add_q("listage", f"Listez tous les documents de type {tipo}.", sorted(idx_tipo[tipo]), "lista_documentos")

docs_2025 = sorted([d for d, i in doc_info.items() if "2025" in i["fecha"]])
docs_2026 = sorted([d for d, i in doc_info.items() if "2026" in i["fecha"]])
add_q("listage", "Quels documents datent de l'année 2025 ?", docs_2025, "lista_documentos")
add_q("listage", "Quels documents correspondent à l'année 2026 ?", docs_2026, "lista_documentos")


# ═══════════════════════════════════════════════
# CAT 9 : COMPARAISONS ET RELATIONS (30)
# ═══════════════════════════════════════════════

d_max = max(doc_info.items(), key=lambda x: x[1]["num_paginas"])
d_min = min(doc_info.items(), key=lambda x: x[1]["num_paginas"])
add_q("relations", "Quel est le document le plus long et lequel est le plus court ?",
      {"plus_long": {"documento": d_max[0], "paginas": d_max[1]["num_paginas"]},
       "plus_court": {"documento": d_min[0], "paginas": d_min[1]["num_paginas"]}}, "objeto")

add_q("relations", "Combien de fois le document le plus long est-il plus grand que le plus court ?",
      round(d_max[1]["num_paginas"] / d_min[1]["num_paginas"], 1), "numero")

pesca_docs = set(buscar_en_contenido("pêche"))
sanitarios_docs = set(buscar_en_contenido("sanitaire"))
add_q("relations", "Y a-t-il des documents traitant simultanément de pêche et de santé ?",
      sorted(pesca_docs & sanitarios_docs), "lista_documentos")

top_refs = sorted(doc_info.items(), key=lambda x: -len(x[1]["refs"]))[:5]
add_q("relations", "Quels sont les 5 documents avec le plus de références à d'autres actes législatifs ?",
      [{"documento": d, "num_referencias": len(i["refs"])} for d, i in top_refs], "ranking")

pays = ["Espagne", "France", "Allemagne", "Italie", "Portugal", "Grèce", "Maroc", "Tunisie", "Norvège", "Islande"]
for pais in pays:
    docs_pais = buscar_en_contenido(pais)
    add_q("relations", f"Dans quels documents {pais} est-il mentionné ?", docs_pais, "lista_documentos")

add_q("relations", "Quels documents ont été émis conjointement par le Parlement européen et le Conseil ?",
      sorted(set(idx_organo.get("Parlement européen", [])) & set(idx_organo.get("Conseil", []))), "lista_documentos")

add_q("relations", "Quels documents sont liés à la santé ou aux questions médicales ?",
      sorted(set(buscar_en_contenido("sanitaire") + buscar_en_contenido("santé") + buscar_en_contenido("médicament"))), "lista_documentos")

add_q("relations", "Quels documents traitent du commerce international ou des relations extérieures ?",
      sorted(set(buscar_en_contenido("commerce") + buscar_en_contenido("relations extérieures") + buscar_en_contenido("accord commercial"))), "lista_documentos")

docs_disposiciones = buscar_en_contenido("entre en vigueur")
add_q("relations", "Quels documents contiennent des dispositions sur l'entrée en vigueur ?", docs_disposiciones, "lista_documentos")

regs = idx_tipo.get("RÈGLEMENT", [])
if len(regs) >= 2:
    r1, r2 = regs[0], regs[1]
    add_q("relations", f"Comparez les documents {doc_info[r1]['codigo']} et {doc_info[r2]['codigo']} : qu'ont-ils en commun ?",
          {"type_commun": "RÈGLEMENT",
           "doc1": {"codigo": doc_info[r1]["codigo"], "fecha": doc_info[r1]["fecha"], "paginas": doc_info[r1]["num_paginas"]},
           "doc2": {"codigo": doc_info[r2]["codigo"], "fecha": doc_info[r2]["fecha"], "paginas": doc_info[r2]["num_paginas"]}}, "objeto")

docs_por_fecha = sorted(doc_info.items(), key=lambda x: x[1]["fecha"], reverse=True)
add_q("relations", "Quels sont les documents les plus récents ?",
      [{"documento": d, "fecha": i["fecha"]} for d, i in docs_por_fecha[:5]], "ranking")

docs_seguridad = sorted(set(buscar_en_contenido("sécurité") + buscar_en_contenido("défense")))
add_q("relations", "Quels documents traitent de sécurité ou de défense ?", docs_seguridad, "lista_documentos")

docs_ambiente = sorted(set(buscar_en_contenido("environnement") + buscar_en_contenido("environnemental")))
add_q("relations", "Y a-t-il des documents liés à l'environnement ?", docs_ambiente, "lista_documentos")

top_arts = sorted(doc_info.items(), key=lambda x: -x[1]["num_articulos"])[:5]
add_q("relations", "Quels sont les 5 documents avec le plus d'articles ?",
      [{"documento": d, "num_articulos": i["num_articulos"]} for d, i in top_arts], "ranking")

meses = Counter()
for d, i in doc_info.items():
    m = re.search(r'(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)', i["fecha"])
    if m:
        meses[m.group(1)] += 1
add_q("relations", "Comment les documents se répartissent-ils par mois d'émission ?",
      [{"mois": m, "quantite": c} for m, c in meses.most_common()], "ranking")


# ═══════════════════════════════════════════════
# CAT 10 : CONTENU SPÉCIFIQUE / DÉTAIL (25)
# ═══════════════════════════════════════════════

for d_id in list(doc_info.keys())[:8]:
    text = docs[d_id]["contenido"]
    info = doc_info[d_id]
    if info["num_articulos"] >= 2:
        m_art1 = re.search(r'Article\s+(?:premier|1)\s*\n([\s\S]*?)(?:Article\s+2|\Z)', text)
        if m_art1:
            art1_text = m_art1.group(1).strip()[:500]
            art1_text = re.sub(r'\s+', ' ', art1_text)
            add_q("contenu_specifique",
                  f"Quel est le contenu de l'Article premier du document {info['codigo']} ?",
                  art1_text, "texto_largo")
            break

for d_id in list(doc_info.keys()):
    if doc_info[d_id]["num_paginas"] >= 3:
        pag2 = docs[d_id]["paginas"][1][:300] if len(docs[d_id]["paginas"]) > 1 else ""
        if pag2.strip():
            pag2_clean = re.sub(r'\s+', ' ', pag2).strip()
            add_q("contenu_specifique",
                  f"Quelle information apparaît en page 2 du document {doc_info[d_id]['codigo']} ?",
                  pag2_clean, "texto_largo")
            break

docs_vigor = []
for d_id, doc in docs.items():
    m = re.search(r'entre en vigueur\s+(?:le\s+)?(.+?)(?:\.|$)', doc["contenido"])
    if m:
        docs_vigor.append({"documento": d_id, "entree_en_vigueur": m.group(1).strip()[:100]})

if docs_vigor:
    add_q("contenu_specifique", "Quels documents précisent leur date d'entrée en vigueur et quand est-ce ?",
          docs_vigor, "lista_detallada")

docs_ambito = []
for d_id, doc in docs.items():
    m = re.search(r'(?:champ d.application|s.applique à|applicable à)[\s:]*(.{50,300})', doc["contenido"], re.IGNORECASE)
    if m:
        docs_ambito.append(d_id)
add_q("contenu_specifique", "Quels documents définissent leur champ d'application ?", docs_ambito, "lista_documentos")

docs_definiciones = buscar_en_contenido("définitions")
add_q("contenu_specifique", "Quels documents contiennent une section de définitions ?", docs_definiciones, "lista_documentos")

docs_deroga = buscar_en_contenido("est abrogé")
add_q("contenu_specifique", "Quels documents contiennent des clauses d'abrogation ?", docs_deroga, "lista_documentos")

docs_modifica = buscar_en_contenido("est modifié")
add_q("contenu_specifique", "Quels documents modifient une législation préexistante ?", docs_modifica, "lista_documentos")

docs_comite = buscar_en_contenido("comité")
add_q("contenu_specifique", "Dans quels documents fait-on référence à des comités ?", docs_comite, "lista_documentos")

docs_destinatarios = buscar_en_contenido("destinataires")
if not docs_destinatarios:
    docs_destinatarios = buscar_en_contenido("États membres sont destinataires")
add_q("contenu_specifique", "Quels documents mentionnent leurs destinataires ?", docs_destinatarios, "lista_documentos")

docs_tratado = buscar_en_contenido("traité sur le fonctionnement")
add_q("contenu_specifique", "Quels documents se fondent sur le traité sur le fonctionnement de l'Union européenne ?",
      docs_tratado, "lista_documentos")

docs_espana = buscar_en_contenido("Espagne")
add_q("contenu_specifique", "Dans quels documents l'Espagne est-elle référencée ?", docs_espana, "lista_documentos")

docs_especies = buscar_en_contenido("espèces")
add_q("contenu_specifique", "Quels documents font référence à des espèces animales ou végétales ?", docs_especies, "lista_documentos")

docs_cuotas = buscar_en_contenido("quota")
add_q("contenu_specifique", "Quels documents mentionnent des quotas ?", docs_cuotas, "lista_documentos")

docs_sancion_det = buscar_en_contenido("gel des avoirs")
add_q("contenu_specifique", "Quels documents mentionnent le gel des avoirs ?", docs_sancion_det, "lista_documentos")

docs_plazos = buscar_en_contenido("délai")
add_q("contenu_specifique", "Dans quels documents des délais sont-ils établis ?", docs_plazos, "lista_documentos")

docs_publicacion = buscar_en_contenido("publication au Journal officiel")
add_q("contenu_specifique", "Quels documents mentionnent leur publication au Journal officiel ?", docs_publicacion, "lista_documentos")

docs_dictamen = buscar_en_contenido("avis")
add_q("contenu_specifique", "Quels documents font référence à des avis ?", docs_dictamen, "lista_documentos")

docs_eemm = buscar_en_contenido("États membres")
add_q("contenu_specifique", "Combien de documents font référence aux États membres ?",
      len(docs_eemm), "numero")

docs_personas = buscar_en_contenido("personne physique")
add_q("contenu_specifique", "Quels documents mentionnent des personnes physiques ?", docs_personas, "lista_documentos")

docs_toneladas = buscar_en_contenido("tonne")
add_q("contenu_specifique", "Quels documents font référence à des tonnes ?", docs_toneladas, "lista_documentos")

docs_cooperacion = buscar_en_contenido("coopération")
add_q("contenu_specifique", "Dans quels documents la coopération est-elle mentionnée ?", docs_cooperacion, "lista_documentos")


# ═══════════════════════════════════════════════
# FILTRE : RÉDUIRE À 80-100 QUESTIONS
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

print(f"\n→ Réduit de {len(preguntas)} à {len(_selected)} questions (cible : 80-100)")
preguntas = _selected

# ═══════════════════════════════════════════════
# VÉRIFICATION ET EXPORTATION
# ═══════════════════════════════════════════════
texts = [q["pregunta"] for q in preguntas]
dupes = [t for t in texts if texts.count(t) > 1]
if dupes:
    print(f"\nATTENTION : {len(set(dupes))} questions en double :")
    for d in set(dupes):
        print(f"  - {d}")
else:
    print("\n✓ Toutes les questions sont uniques")

print(f"Total de questions générées : {len(preguntas)}")

cat_counts = Counter(q["categoria"] for q in preguntas)
print("\nRépartition par catégorie :")
for cat, cnt in sorted(cat_counts.items()):
    print(f"  {cat}: {cnt}")

gold_standard = {
    "gold_standard": {
        "caso_uso": "documentos_ue",
        "idioma": "fr",
        "total_preguntas": len(preguntas),
        "total_documentos_analizados": len(docs),
        "fecha_generacion": "2026-04-17",
        "categorias": dict(sorted(cat_counts.items())),
        "descripcion": "Gold standard pour évaluer un système RAG sur les documents du Journal officiel de l'UE "
                       "en français (règlements, décisions, rectificatifs). Contient des questions d'identification, "
                       "de recherche par type, de recherche par contenu, de comptage, de références croisées, de structure, "
                       "d'existence, de listage, de relations et de contenu spécifique. Toutes les réponses calculées à partir des données.",
        "preguntas": preguntas
    }
}

output_path = OUTPUT_DIR / "gold_standard_eu_fr.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(gold_standard, f, ensure_ascii=False, indent=2)

print(f"\n✓ Gold standard sauvegardé dans : {output_path}")
