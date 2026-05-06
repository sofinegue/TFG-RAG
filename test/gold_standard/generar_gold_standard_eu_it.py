"""
Script per generare il Gold Standard del caso d'uso dei documenti dell'UE in italiano.
Genera 80-100 domande uniche con risposte estratte direttamente dai documenti.

Struttura dei dati: documenti della Gazzetta ufficiale dell'UE (serie L) in formato JSON
  - archivo, idioma, num_paginas, contenido, paginas

Autore: Generato automaticamente per il TFG
Data: 2026-04-17
"""

import json
import re
import random
from collections import Counter, defaultdict
from pathlib import Path

random.seed(42)

# ─────────────────────────────────────────────
# 1. CARICARE TUTTI I DOCUMENTI
# ─────────────────────────────────────────────
EU_DIR = Path(__file__).parent.parent.parent / "data" / "eu" / "it" / "json"
OUTPUT_DIR = Path(__file__).parent.parent / "data"

docs = {}
for f in sorted(EU_DIR.glob("*.json")):
    with open(f, encoding="utf-8") as fh:
        doc = json.load(fh)
        docs[doc["archivo"].replace(".pdf", "")] = doc

print(f"Caricati {len(docs)} documenti")

# ─────────────────────────────────────────────
# 2. ANALIZZARE E COSTRUIRE INDICI
# ─────────────────────────────────────────────

doc_info = {}
for doc_id, doc in docs.items():
    text = doc["contenido"][:3000]

    # Tipo di documento
    m = re.search(r'(REGOLAMENTO|DECISIONE|RETTIFICA|ACCORDO|DIRETTIVA)', text)
    tipo = m.group(1) if m else "ALTRO"

    # Codice del documento
    m_code = re.search(r'(\d{4}/\d+)\s', text)
    code = m_code.group(1) if m_code else doc_id

    # Titolo completo
    m_title = re.search(r'((?:REGOLAMENTO|DECISIONE|RETTIFICA|DIRETTIVA|ACCORDO)[\s\S]*?)(?:\n(?:LA COMMISSIONE|IL CONSIGLIO|IL PARLAMENTO|visto|considerando|\(Testo))', text)
    titulo = m_title.group(1).replace('\n', ' ').strip() if m_title else ""
    titulo = re.sub(r'\s+', ' ', titulo)

    # Organo emittente
    organos = []
    if "COMMISSIONE" in text[:2000]:
        organos.append("Commissione europea")
    if "CONSIGLIO" in text[:2000]:
        organos.append("Consiglio")
    if "PARLAMENTO EUROPEO" in text[:2000]:
        organos.append("Parlamento europeo")

    # Data del documento
    m_fecha = re.search(r'del\s+(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+(\d{4})', text)
    fecha = f"{m_fecha.group(1)} {m_fecha.group(2)} {m_fecha.group(3)}" if m_fecha else ""

    # Numero di articoli
    articulos_found = re.findall(r'Articolo\s+(\d+)', text + doc["contenido"][3000:])
    num_articulos = max([int(a) for a in articulos_found]) if articulos_found else 0

    # Numero di considerando
    considerandos = re.findall(r'\((\d+)\)\s', doc["contenido"][:10000])
    num_considerandos = max([int(c) for c in considerandos]) if considerandos else 0

    # Riferimenti incrociati
    refs = re.findall(r'(?:regolamento|decisione|direttiva)\s+\([A-Z]+\)\s+(?:n\.\s*)?(\d{4}/\d+)', doc["contenido"], re.IGNORECASE)
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

# Indici
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
    print(f"  {doc_id}: {info['tipo']} | {info['fecha']} | {info['num_paginas']} p. | {info['num_articulos']} art. | org: {info['organos']}")

print(f"\nTipi: {dict(Counter(i['tipo'] for i in doc_info.values()))}")
print(f"Organi: {dict(Counter(o for i in doc_info.values() for o in i['organos']))}")

# ─────────────────────────────────────────────
# 3. GENERARE DOMANDE
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
# CAT 1: IDENTIFICAZIONE DEI DOCUMENTI (25)
# ═══════════════════════════════════════════════

d, doc, info = next_doc()
add_q("identificazione", f"Che tipo di documento è {info['codigo']}?", info["tipo"])
d, doc, info = next_doc()
add_q("identificazione", f"Di cosa tratta il documento {info['codigo']}?", info["titulo"])
d, doc, info = next_doc()
add_q("identificazione", f"Chi ha emesso il documento {info['codigo']}?", info["organos"], "lista")
d, doc, info = next_doc()
add_q("identificazione", f"Qual è la data del documento {info['codigo']}?", info["fecha"])
d, doc, info = next_doc()
add_q("identificazione", f"Dammi il titolo completo del documento {d}.", info["titulo"])
d, doc, info = next_doc()
add_q("identificazione", f"Quale istituzione europea è responsabile del documento {info['codigo']}?", info["organos"], "lista")
d, doc, info = next_doc()
add_q("identificazione", f"Identifica il tipo e la data del documento {info['codigo']}.", {"tipo": info["tipo"], "fecha": info["fecha"]}, "objeto")
d, doc, info = next_doc()
add_q("identificazione", f"Quante pagine ha il documento {info['codigo']}?", info["num_paginas"], "numero")
d, doc, info = next_doc()
add_q("identificazione", f"Riassumi in una frase il contenuto del documento {d}.", info["titulo"])
d, doc, info = next_doc()
add_q("identificazione", f"A cosa si riferisce il documento numero {info['codigo']}?", info["titulo"])
d, doc, info = next_doc()
add_q("identificazione", f"Quanti articoli contiene il documento {info['codigo']}?", info["num_articulos"], "numero")
d, doc, info = next_doc()
add_q("identificazione", f"Fornisci i metadati principali del documento {d}.",
      {"tipo": info["tipo"], "fecha": info["fecha"], "organos": info["organos"], "paginas": info["num_paginas"]}, "objeto")
d, doc, info = next_doc()
add_q("identificazione", f"Qual è il contenuto del documento con codice {info['codigo']}?", info["titulo"])
d, doc, info = next_doc()
add_q("identificazione", f"Quale organismo ha approvato il documento {info['codigo']}?", info["organos"], "lista")
d, doc, info = next_doc()
add_q("identificazione", f"Ho bisogno di sapere di cosa tratta {d}. Qual è il suo argomento principale?", info["titulo"])
d, doc, info = next_doc()
add_q("identificazione", f"In quale data è stato adottato il documento {info['codigo']}?", info["fecha"])
d, doc, info = next_doc()
add_q("identificazione", f"Descrivi brevemente l'oggetto del documento {info['codigo']}.", info["titulo"])
d, doc, info = next_doc()
add_q("identificazione", f"Quanti considerando ha il documento {info['codigo']}?", info["num_considerandos"], "numero")

remaining = list(d_iter)
if remaining:
    d = remaining[0]
    info = doc_info[d]
    add_q("identificazione", f"Quante parole contiene approssimativamente il documento {info['codigo']}?", info["num_palabras"], "numero")

for i, d in enumerate(list(doc_info.keys())[:6]):
    info = doc_info[d]
    templates = [
        f"Il documento {d} è un regolamento o una decisione?",
        f"Quante pagine ha il file {d}?",
        f"Indica la data di adozione di {d}.",
        f"Quali istituzioni hanno partecipato all'elaborazione di {d}?",
        f"Dammi un riassunto del documento {d}.",
        f"Qual è il codice numerico del documento contenuto in {d}?",
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
    add_q("identificazione", templates[i], respuestas[i], tipos[i])


# ═══════════════════════════════════════════════
# CAT 2: RICERCA PER TIPO DI DOCUMENTO (15)
# ═══════════════════════════════════════════════

add_q("ricerca_per_tipo", "Quanti regolamenti ci sono nel database?", len(idx_tipo.get("REGOLAMENTO", [])), "numero")
add_q("ricerca_per_tipo", "Quante decisioni contiene la raccolta?", len(idx_tipo.get("DECISIONE", [])), "numero")
add_q("ricerca_per_tipo", "Elenca tutti i regolamenti disponibili.", idx_tipo.get("REGOLAMENTO", []), "lista_documentos")
add_q("ricerca_per_tipo", "Dammi tutte le decisioni del database.", idx_tipo.get("DECISIONE", []), "lista_documentos")
add_q("ricerca_per_tipo", "Quali tipi di atti legislativi abbiamo?", sorted(set(i["tipo"] for i in doc_info.values())), "lista")
add_q("ricerca_per_tipo", "C'è un documento di tipo rettifica?",
      {"existe": "RETTIFICA" in idx_tipo or any("Rettifica" in docs[d]["contenido"][:500] for d in docs),
       "documentos": idx_tipo.get("RETTIFICA", []) + [d for d in docs if "Rettifica" in docs[d]["contenido"][:500]]}, "booleano")
add_q("ricerca_per_tipo", "Filtra i documenti che sono regolamenti di esecuzione.",
      [d for d in docs if "REGOLAMENTO DI ESECUZIONE" in docs[d]["contenido"][:1000]], "lista_documentos")
add_q("ricerca_per_tipo", "Quali documenti sono emessi dalla Commissione europea?", idx_organo.get("Commissione europea", []), "lista_documentos")
add_q("ricerca_per_tipo", "Quali documenti sono stati approvati dal Consiglio?", idx_organo.get("Consiglio", []), "lista_documentos")
add_q("ricerca_per_tipo", "Ci sono documenti del Parlamento europeo?", idx_organo.get("Parlamento europeo", []), "lista_documentos")
add_q("ricerca_per_tipo", "Quanti documenti ha emesso la Commissione europea?", len(idx_organo.get("Commissione europea", [])), "numero")
add_q("ricerca_per_tipo", "Quali documenti del 2026 abbiamo?",
      [d for d, i in doc_info.items() if "2026" in i["fecha"]], "lista_documentos")
add_q("ricerca_per_tipo", "Quali sono i documenti del 2025?",
      [d for d, i in doc_info.items() if "2025" in i["fecha"]], "lista_documentos")
add_q("ricerca_per_tipo", "Cerca documenti che contengano decisioni di esecuzione.",
      [d for d in docs if "DECISIONE DI ESECUZIONE" in docs[d]["contenido"][:1000]], "lista_documentos")
add_q("ricerca_per_tipo", "Quali documenti sono regolamenti delegati?",
      [d for d in docs if "REGOLAMENTO DELEGATO" in docs[d]["contenido"][:1000]], "lista_documentos")


# ═══════════════════════════════════════════════
# CAT 3: RICERCA PER CONTENUTO / TEMATICA (30)
# ═══════════════════════════════════════════════

temas = [
    ("pesca", "Quali documenti trattano di pesca?"),
    ("dispositivi medici", "Quali documenti si riferiscono ai dispositivi medici?"),
    ("Marocco", "In quali documenti è menzionato il Marocco?"),
    ("misure restrittive", "Elenca i documenti che trattano di misure restrittive."),
    ("norme armonizzate", "Quali documenti fanno riferimento a norme armonizzate?"),
    ("possibilità di pesca", "Quali documenti regolano le possibilità di pesca?"),
    ("pesticidi", "Ci sono documenti che menzionano pesticidi o residui di pesticidi?"),
    ("Regolamento (UE) 2017/745", "Quali documenti fanno riferimento al Regolamento (UE) 2017/745?"),
    ("peste suina", "Ci sono documenti sulla peste suina?"),
    ("influenza aviaria", "Quali documenti menzionano l'influenza aviaria?"),
    ("sostanze di origine umana", "C'è un documento sulle sostanze di origine umana?"),
    ("indicazione geografica", "Quali documenti trattano di indicazioni geografiche?"),
    ("Fondo europeo", "Quali documenti fanno riferimento a un Fondo europeo?"),
    ("Tunisia", "La Tunisia è menzionata in qualche documento?"),
    ("euromediterraneo", "Quali documenti fanno riferimento all'accordo euromediterraneo?"),
    ("sterilizzazione", "Ci sono documenti sulla sterilizzazione di prodotti?"),
    ("Atlantico", "Quali documenti menzionano l'Atlantico?"),
    ("Mediterraneo", "Elenca i documenti che si riferiscono al Mediterraneo."),
    ("Consiglio di associazione", "Quali documenti menzionano un Consiglio di associazione?"),
    ("allegato", "Quali documenti contengono o modificano allegati?"),
    ("importazione", "Quali documenti trattano di importazioni?"),
    ("PESC", "Ci sono documenti relativi alla Politica estera e di sicurezza comune (PESC)?"),
    ("sanzioni", "Quali documenti fanno riferimento a sanzioni?"),
    ("sicurezza alimentare", "Ci sono documenti sulla sicurezza alimentare?"),
    ("Gazzetta ufficiale", "In quanti documenti si fa riferimento alla Gazzetta ufficiale?"),
    ("miele", "C'è un documento che menziona il miele?"),
    ("paesi terzi", "Quali documenti fanno riferimento ai paesi terzi?"),
    ("biocompatibilità", "La biocompatibilità è menzionata in qualche documento?"),
    ("Baltico", "Quali documenti fanno riferimento al mar Baltico?"),
    ("residui", "Elenca i documenti contenenti la parola residui."),
]

for kw, pregunta in temas:
    r = buscar_en_contenido(kw)
    add_q("ricerca_per_contenuto", pregunta, r, "lista_documentos")


# ═══════════════════════════════════════════════
# CAT 4: CONTEGGIO E STATISTICHE (25)
# ═══════════════════════════════════════════════

add_q("conteggio", "Quanti documenti ci sono in totale nel database?", len(docs), "numero")
add_q("conteggio", "Quante pagine hanno in totale tutti i documenti?",
      sum(d["num_paginas"] for d in docs.values()), "numero")
add_q("conteggio", "Qual è il documento più lungo per numero di pagine?",
      {"documento": max(doc_info.items(), key=lambda x: x[1]["num_paginas"])[0],
       "paginas": max(i["num_paginas"] for i in doc_info.values())}, "objeto")
add_q("conteggio", "Qual è il documento più corto?",
      {"documento": min(doc_info.items(), key=lambda x: x[1]["num_paginas"])[0],
       "paginas": min(i["num_paginas"] for i in doc_info.values())}, "objeto")
add_q("conteggio", "Quante parole ci sono in totale in tutti i documenti?",
      sum(i["num_palabras"] for i in doc_info.values()), "numero")

avg_pags = round(sum(i["num_paginas"] for i in doc_info.values()) / len(doc_info), 1)
add_q("conteggio", "Qual è la media di pagine per documento?", avg_pags, "numero")

avg_words = round(sum(i["num_palabras"] for i in doc_info.values()) / len(doc_info), 1)
add_q("conteggio", "Qual è la media di parole per documento?", avg_words, "numero")

add_q("conteggio", "Quanti documenti hanno più di 50 pagine?",
      len([d for d, i in doc_info.items() if i["num_paginas"] > 50]), "numero")
add_q("conteggio", "Quanti documenti hanno meno di 10 pagine?",
      len([d for d, i in doc_info.items() if i["num_paginas"] < 10]), "numero")

top5 = sorted(doc_info.items(), key=lambda x: -x[1]["num_paginas"])[:5]
add_q("conteggio", "Quali sono i 5 documenti più lunghi?",
      [{"documento": d, "paginas": i["num_paginas"]} for d, i in top5], "ranking")

bot5 = sorted(doc_info.items(), key=lambda x: x[1]["num_paginas"])[:5]
add_q("conteggio", "Quali sono i 5 documenti più brevi?",
      [{"documento": d, "paginas": i["num_paginas"]} for d, i in bot5], "ranking")

add_q("conteggio", "Quanti tipi diversi di documenti esistono?",
      len(set(i["tipo"] for i in doc_info.values())), "numero")

tipo_counts = Counter(i["tipo"] for i in doc_info.values())
add_q("conteggio", "Qual è la distribuzione dei documenti per tipo?",
      [{"tipo": t, "cantidad": c} for t, c in tipo_counts.most_common()], "ranking")

add_q("conteggio", "Quanti documenti menzionano la parola «pesca»?",
      len(buscar_en_contenido("pesca")), "numero")
add_q("conteggio", "Quanti documenti contengono articoli numerati?",
      len([d for d, i in doc_info.items() if i["num_articulos"] > 0]), "numero")

max_arts = max(doc_info.items(), key=lambda x: x[1]["num_articulos"])
add_q("conteggio", "Quale documento ha il maggior numero di articoli?",
      {"documento": max_arts[0], "num_articulos": max_arts[1]["num_articulos"]}, "objeto")

add_q("conteggio", "Quanti documenti sono stati emessi a gennaio 2026?",
      len([d for d, i in doc_info.items() if "gennaio 2026" in i["fecha"]]), "numero")
add_q("conteggio", "Quanti documenti sono stati emessi a dicembre 2025?",
      len([d for d, i in doc_info.items() if "dicembre 2025" in i["fecha"]]), "numero")

add_q("conteggio", "Quanti documenti menzionano sanzioni o misure restrittive?",
      len(set(buscar_en_contenido("sanzioni") + buscar_en_contenido("misure restrittive"))), "numero")

add_q("conteggio", "Quanti documenti fanno riferimento ad altri regolamenti dell'UE?",
      len([d for d, i in doc_info.items() if len(i["refs"]) > 0]), "numero")

total_refs = sum(len(i["refs"]) for i in doc_info.values())
add_q("conteggio", "Quanti riferimenti incrociati ad altri documenti ci sono in totale?", total_refs, "numero")

add_q("conteggio", "Quanti documenti superano le 100 pagine?",
      len([d for d, i in doc_info.items() if i["num_paginas"] > 100]), "numero")

add_q("conteggio", "Quanti caratteri ha il documento più lungo?",
      max(i["num_chars"] for i in doc_info.values()), "numero")

add_q("conteggio", "Quanti documenti contengono la parola «Regolamento»?",
      len(buscar_en_contenido("Regolamento")), "numero")


# ═══════════════════════════════════════════════
# CAT 5: RIFERIMENTI INCROCIATI (20)
# ═══════════════════════════════════════════════

docs_con_refs = [(d, i) for d, i in doc_info.items() if len(i["refs"]) >= 2]
random.shuffle(docs_con_refs)
ref_iter = iter(docs_con_refs)

for template in [
    "A quali altri regolamenti o decisioni fa riferimento il documento {}?",
    "Elenca le norme citate nel documento {}.",
    "Quale legislazione precedente menziona il documento {}?",
    "Quali sono i riferimenti normativi del documento {}?",
    "Dammi i riferimenti ad altri atti legislativi presenti in {}.",
    "Quali regolamenti modifica o cita il documento {}?",
    "Identifica la legislazione dell'UE menzionata in {}.",
    "A quale altra legislazione è collegato il documento {}?",
    "Elenca i regolamenti e le decisioni citati in {}.",
    "Quale base giuridica è menzionata nel documento {}?",
]:
    try:
        d, i = next(ref_iter)
        add_q("riferimenti_incrociati", template.format(i["codigo"]), i["refs"], "lista_referencias")
    except StopIteration:
        break

all_refs = defaultdict(list)
for d, i in doc_info.items():
    for r in i["refs"]:
        all_refs[r].append(d)

shared_refs = [(r, ds) for r, ds in all_refs.items() if len(ds) >= 2]
random.shuffle(shared_refs)

for template in [
    "Quali documenti fanno riferimento al {}?",
    "Quali documenti citano il {}?",
    "Elenca i documenti che menzionano il {}.",
    "In quanti documenti è referenziato il {}?",
    "Quali documenti sono collegati al {}?",
]:
    if shared_refs:
        ref, ds = shared_refs.pop()
        ref_name = f"Regolamento/Decisione {ref}"
        add_q("riferimenti_incrociati", template.format(ref_name), ds, "lista_documentos")

for d, i in list(doc_info.items())[:5]:
    if i["refs"]:
        add_q("riferimenti_incrociati", f"Quanti riferimenti ad altri atti contiene il documento {i['codigo']}?",
              len(i["refs"]), "numero")


# ═══════════════════════════════════════════════
# CAT 6: STRUTTURA DEI DOCUMENTI (20)
# ═══════════════════════════════════════════════

for d, i in list(doc_info.items()):
    if i["num_articulos"] > 0:
        break
d_art = d
info_art = doc_info[d_art]

add_q("struttura", f"Quanti articoli ha il documento {info_art['codigo']}?", info_art["num_articulos"], "numero")

docs_con_consid = [(d, i) for d, i in doc_info.items() if i["num_considerandos"] > 0]
random.shuffle(docs_con_consid)

for idx, template in enumerate([
    "Quanti considerando ha il documento {}?",
    "Quanti considerando contiene il preambolo di {}?",
    "Indica il numero di considerando del documento {}.",
    "Quanti punti ha la parte considerativa di {}?",
    "Dammi il numero totale di considerando di {}.",
]):
    if idx < len(docs_con_consid):
        d, i = docs_con_consid[idx]
        add_q("struttura", template.format(i["codigo"]), i["num_considerandos"], "numero")

docs_con_anexo = buscar_en_contenido("ALLEGATO")
add_q("struttura", "Quali documenti contengono allegati?", docs_con_anexo, "lista_documentos")
add_q("struttura", "Quanti documenti includono allegati?", len(docs_con_anexo), "numero")

docs_con_tabla = buscar_en_contenido("tabella")
add_q("struttura", "Quali documenti contengono tabelle?", docs_con_tabla, "lista_documentos")

arts_por_doc = sorted([(d, i["num_articulos"]) for d, i in doc_info.items() if i["num_articulos"] > 0],
                      key=lambda x: -x[1])
add_q("struttura", "Quali documenti hanno articoli e quanti ne ha ciascuno?",
      [{"documento": d, "num_articulos": n} for d, n in arts_por_doc], "ranking")

add_q("struttura", "Elenca tutti i documenti ordinati per numero di pagine dal maggiore al minore.",
      [{"documento": d, "paginas": i["num_paginas"]} for d, i in sorted(doc_info.items(), key=lambda x: -x[1]["num_paginas"])], "ranking")

docs_con_porcentaje = buscar_en_contenido("%")
add_q("struttura", "Quali documenti contengono dati percentuali?", docs_con_porcentaje, "lista_documentos")

docs_con_aplicacion = buscar_en_contenido("si applica a decorrere")
add_q("struttura", "Quali documenti specificano una data di applicazione?", docs_con_aplicacion, "lista_documentos")

docs_transitorio = buscar_en_contenido("disposizioni transitorie")
if not docs_transitorio:
    docs_transitorio = buscar_en_contenido("transitoria")
add_q("struttura", "Ci sono documenti con disposizioni transitorie?", docs_transitorio, "lista_documentos")

docs_obligatorio = buscar_en_contenido("obbligatorio in tutti i suoi elementi")
add_q("struttura", "Quali documenti si dichiarano obbligatori in tutti i loro elementi?", docs_obligatorio, "lista_documentos")

all_docs_summary = [{"documento": d, "tipo": i["tipo"], "fecha": i["fecha"], "paginas": i["num_paginas"]}
                    for d, i in sorted(doc_info.items())]
add_q("struttura", "Dammi una panoramica di tutti i documenti con tipo, data e numero di pagine.", all_docs_summary, "tabla")


# ═══════════════════════════════════════════════
# CAT 7: ESISTENZA E VERIFICA (20)
# ═══════════════════════════════════════════════

add_q("esistenza", "C'è un documento sulla pesca nell'Atlantico?",
      {"existe": len(set(buscar_en_contenido("pesca")) & set(buscar_en_contenido("Atlantico"))) > 0,
       "documentos": sorted(set(buscar_en_contenido("pesca")) & set(buscar_en_contenido("Atlantico")))}, "booleano")

add_q("esistenza", "Esiste un regolamento di esecuzione nel database?",
      {"existe": len([d for d in docs if "REGOLAMENTO DI ESECUZIONE" in docs[d]["contenido"][:1000]]) > 0,
       "documentos": [d for d in docs if "REGOLAMENTO DI ESECUZIONE" in docs[d]["contenido"][:1000]]}, "booleano")

add_q("esistenza", "Ci sono documenti che trattano dell'Ucraina?",
      {"existe": len(buscar_en_contenido("Ucraina")) > 0, "documentos": buscar_en_contenido("Ucraina")}, "booleano")

add_q("esistenza", "La Russia è menzionata in qualche documento?",
      {"existe": len(buscar_en_contenido("Russia")) > 0, "documentos": buscar_en_contenido("Russia")}, "booleano")

add_q("esistenza", "C'è un documento sull'intelligenza artificiale?",
      {"existe": len(buscar_en_contenido("intelligenza artificiale")) > 0, "documentos": buscar_en_contenido("intelligenza artificiale")}, "booleano")

add_q("esistenza", "Ci sono documenti sul cambiamento climatico?",
      {"existe": len(buscar_en_contenido("cambiamento climatico")) > 0, "documentos": buscar_en_contenido("cambiamento climatico")}, "booleano")

add_q("esistenza", "Ci sono documenti relativi ai diritti umani?",
      {"existe": len(buscar_en_contenido("diritti umani")) > 0, "documentos": buscar_en_contenido("diritti umani")}, "booleano")

add_q("esistenza", "La Cina è menzionata in qualche documento?",
      {"existe": len(buscar_en_contenido("Cina")) > 0, "documentos": buscar_en_contenido("Cina")}, "booleano")

add_q("esistenza", "Ci sono documenti sulla politica agricola?",
      {"existe": len(buscar_en_contenido("agricola")) > 0, "documentos": buscar_en_contenido("agricola")}, "booleano")

add_q("esistenza", "C'è un documento che menziona l'euro?",
      {"existe": len(buscar_en_contenido("euro")) > 0, "documentos": buscar_en_contenido("euro")}, "booleano")

add_q("esistenza", "La NATO è menzionata in qualche documento?",
      {"existe": len(buscar_en_contenido("NATO")) > 0, "documentos": buscar_en_contenido("NATO")}, "booleano")

add_q("esistenza", "Ci sono documenti sulla protezione dei dati?",
      {"existe": len(buscar_en_contenido("protezione dei dati")) > 0, "documentos": buscar_en_contenido("protezione dei dati")}, "booleano")

add_q("esistenza", "C'è un documento sui trasporti?",
      {"existe": len(buscar_en_contenido("trasporto")) > 0, "documentos": buscar_en_contenido("trasporto")}, "booleano")

add_q("esistenza", "La Siria è menzionata in qualche documento?",
      {"existe": len(buscar_en_contenido("Siria")) > 0, "documentos": buscar_en_contenido("Siria")}, "booleano")

add_q("esistenza", "Ci sono documenti sull'energia?",
      {"existe": len(buscar_en_contenido("energia")) > 0, "documentos": buscar_en_contenido("energia")}, "booleano")

add_q("esistenza", "C'è un documento relativo allo Spazio economico europeo (SEE)?",
      {"existe": len(buscar_en_contenido("SEE")) > 0, "documentos": buscar_en_contenido("SEE")}, "booleano")

add_q("esistenza", "La Bielorussia è menzionata in qualche documento?",
      {"existe": len(buscar_en_contenido("Bielorussia")) > 0, "documentos": buscar_en_contenido("Bielorussia")}, "booleano")

add_q("esistenza", "C'è un documento sulle dogane o i dazi?",
      {"existe": len(set(buscar_en_contenido("dogana") + buscar_en_contenido("dazio"))) > 0,
       "documentos": sorted(set(buscar_en_contenido("dogana") + buscar_en_contenido("dazio")))}, "booleano")

add_q("esistenza", "C'è un documento sui medicinali?",
      {"existe": len(buscar_en_contenido("medicinale")) > 0, "documentos": buscar_en_contenido("medicinale")}, "booleano")

add_q("esistenza", "C'è un documento che menziona una denominazione di origine protetta (DOP)?",
      {"existe": len(buscar_en_contenido("DOP")) > 0, "documentos": buscar_en_contenido("DOP")}, "booleano")


# ═══════════════════════════════════════════════
# CAT 8: ELENCO E CATALOGO (15)
# ═══════════════════════════════════════════════

add_q("elenco", "Dammi la lista completa di tutti i documenti disponibili.", sorted(docs.keys()), "lista_documentos")
add_q("elenco", "Quali sono tutti i documenti nel database?", sorted(docs.keys()), "lista_documentos")
add_q("elenco", "Elenca tutti i documenti della raccolta.", sorted(docs.keys()), "lista_documentos")
add_q("elenco", "Ho bisogno di vedere il catalogo completo dei documenti dell'UE.", sorted(docs.keys()), "lista_documentos")
add_q("elenco", "Mostrami una lista di tutti i documenti della Gazzetta ufficiale disponibili.", sorted(docs.keys()), "lista_documentos")

for org in sorted(idx_organo.keys()):
    add_q("elenco", f"Elenca tutti i documenti emessi dalla {org}.", sorted(idx_organo[org]), "lista_documentos")

for tipo in sorted(idx_tipo.keys()):
    add_q("elenco", f"Elenca tutti i documenti di tipo {tipo}.", sorted(idx_tipo[tipo]), "lista_documentos")

docs_2025 = sorted([d for d, i in doc_info.items() if "2025" in i["fecha"]])
docs_2026 = sorted([d for d, i in doc_info.items() if "2026" in i["fecha"]])
add_q("elenco", "Quali documenti sono dell'anno 2025?", docs_2025, "lista_documentos")
add_q("elenco", "Quali documenti corrispondono all'anno 2026?", docs_2026, "lista_documentos")


# ═══════════════════════════════════════════════
# CAT 9: CONFRONTI E RELAZIONI (30)
# ═══════════════════════════════════════════════

d_max = max(doc_info.items(), key=lambda x: x[1]["num_paginas"])
d_min = min(doc_info.items(), key=lambda x: x[1]["num_paginas"])
add_q("relazioni", "Qual è il documento più lungo e quale il più corto?",
      {"piu_lungo": {"documento": d_max[0], "paginas": d_max[1]["num_paginas"]},
       "piu_corto": {"documento": d_min[0], "paginas": d_min[1]["num_paginas"]}}, "objeto")

add_q("relazioni", "Quante volte il documento più lungo è più grande del più corto?",
      round(d_max[1]["num_paginas"] / d_min[1]["num_paginas"], 1), "numero")

pesca_docs = set(buscar_en_contenido("pesca"))
sanitarios_docs = set(buscar_en_contenido("sanitario"))
add_q("relazioni", "Ci sono documenti che trattano contemporaneamente di pesca e sanità?",
      sorted(pesca_docs & sanitarios_docs), "lista_documentos")

top_refs = sorted(doc_info.items(), key=lambda x: -len(x[1]["refs"]))[:5]
add_q("relazioni", "Quali sono i 5 documenti con più riferimenti ad altri atti legislativi?",
      [{"documento": d, "num_referencias": len(i["refs"])} for d, i in top_refs], "ranking")

paesi = ["Spagna", "Francia", "Germania", "Italia", "Portogallo", "Grecia", "Marocco", "Tunisia", "Norvegia", "Islanda"]
for pais in paesi:
    docs_pais = buscar_en_contenido(pais)
    add_q("relazioni", f"In quali documenti viene menzionata {pais}?", docs_pais, "lista_documentos")

add_q("relazioni", "Quali documenti sono stati emessi congiuntamente dal Parlamento europeo e dal Consiglio?",
      sorted(set(idx_organo.get("Parlamento europeo", [])) & set(idx_organo.get("Consiglio", []))), "lista_documentos")

add_q("relazioni", "Quali documenti sono relativi alla salute o a questioni mediche?",
      sorted(set(buscar_en_contenido("sanitario") + buscar_en_contenido("salute") + buscar_en_contenido("medicinale"))), "lista_documentos")

add_q("relazioni", "Quali documenti trattano di commercio internazionale o relazioni esterne?",
      sorted(set(buscar_en_contenido("commercio") + buscar_en_contenido("relazioni esterne") + buscar_en_contenido("accordo commerciale"))), "lista_documentos")

docs_disposiciones = buscar_en_contenido("entra in vigore")
add_q("relazioni", "Quali documenti contengono disposizioni sull'entrata in vigore?", docs_disposiciones, "lista_documentos")

regs = idx_tipo.get("REGOLAMENTO", [])
if len(regs) >= 2:
    r1, r2 = regs[0], regs[1]
    add_q("relazioni", f"Confronta i documenti {doc_info[r1]['codigo']} e {doc_info[r2]['codigo']}: cosa hanno in comune?",
          {"tipo_comune": "REGOLAMENTO",
           "doc1": {"codigo": doc_info[r1]["codigo"], "fecha": doc_info[r1]["fecha"], "paginas": doc_info[r1]["num_paginas"]},
           "doc2": {"codigo": doc_info[r2]["codigo"], "fecha": doc_info[r2]["fecha"], "paginas": doc_info[r2]["num_paginas"]}}, "objeto")

docs_por_fecha = sorted(doc_info.items(), key=lambda x: x[1]["fecha"], reverse=True)
add_q("relazioni", "Quali sono i documenti più recenti?",
      [{"documento": d, "fecha": i["fecha"]} for d, i in docs_por_fecha[:5]], "ranking")

docs_seguridad = sorted(set(buscar_en_contenido("sicurezza") + buscar_en_contenido("difesa")))
add_q("relazioni", "Quali documenti trattano di sicurezza o difesa?", docs_seguridad, "lista_documentos")

docs_ambiente = sorted(set(buscar_en_contenido("ambiente") + buscar_en_contenido("ambientale")))
add_q("relazioni", "Ci sono documenti relativi all'ambiente?", docs_ambiente, "lista_documentos")

top_arts = sorted(doc_info.items(), key=lambda x: -x[1]["num_articulos"])[:5]
add_q("relazioni", "Quali sono i 5 documenti con il maggior numero di articoli?",
      [{"documento": d, "num_articulos": i["num_articulos"]} for d, i in top_arts], "ranking")

meses = Counter()
for d, i in doc_info.items():
    m = re.search(r'(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)', i["fecha"])
    if m:
        meses[m.group(1)] += 1
add_q("relazioni", "Come si distribuiscono i documenti per mese di emissione?",
      [{"mese": m, "quantita": c} for m, c in meses.most_common()], "ranking")


# ═══════════════════════════════════════════════
# CAT 10: CONTENUTO SPECIFICO / DETTAGLIO (25)
# ═══════════════════════════════════════════════

for d_id in list(doc_info.keys())[:8]:
    text = docs[d_id]["contenido"]
    info = doc_info[d_id]
    if info["num_articulos"] >= 2:
        m_art1 = re.search(r'Articolo\s+1\s*\n([\s\S]*?)(?:Articolo\s+2|\Z)', text)
        if m_art1:
            art1_text = m_art1.group(1).strip()[:500]
            art1_text = re.sub(r'\s+', ' ', art1_text)
            add_q("contenuto_specifico",
                  f"Qual è il contenuto dell'Articolo 1 del documento {info['codigo']}?",
                  art1_text, "texto_largo")
            break

for d_id in list(doc_info.keys()):
    if doc_info[d_id]["num_paginas"] >= 3:
        pag2 = docs[d_id]["paginas"][1][:300] if len(docs[d_id]["paginas"]) > 1 else ""
        if pag2.strip():
            pag2_clean = re.sub(r'\s+', ' ', pag2).strip()
            add_q("contenuto_specifico",
                  f"Quali informazioni compaiono a pagina 2 del documento {doc_info[d_id]['codigo']}?",
                  pag2_clean, "texto_largo")
            break

docs_vigor = []
for d_id, doc in docs.items():
    m = re.search(r'entra in vigore\s+(?:il\s+)?(.+?)(?:\.|$)', doc["contenido"])
    if m:
        docs_vigor.append({"documento": d_id, "entrata_in_vigore": m.group(1).strip()[:100]})

if docs_vigor:
    add_q("contenuto_specifico", "Quali documenti specificano la data di entrata in vigore e quando?",
          docs_vigor, "lista_detallada")

docs_ambito = []
for d_id, doc in docs.items():
    m = re.search(r'(?:ambito di applicazione|si applica a|applicabile a)[\s:]*(.{50,300})', doc["contenido"], re.IGNORECASE)
    if m:
        docs_ambito.append(d_id)
add_q("contenuto_specifico", "Quali documenti definiscono il loro ambito di applicazione?", docs_ambito, "lista_documentos")

docs_definiciones = buscar_en_contenido("definizioni")
add_q("contenuto_specifico", "Quali documenti contengono una sezione di definizioni?", docs_definiciones, "lista_documentos")

docs_deroga = buscar_en_contenido("è abrogato")
add_q("contenuto_specifico", "Quali documenti contengono clausole di abrogazione?", docs_deroga, "lista_documentos")

docs_modifica = buscar_en_contenido("è modificato")
add_q("contenuto_specifico", "Quali documenti modificano legislazione preesistente?", docs_modifica, "lista_documentos")

docs_comite = buscar_en_contenido("comitato")
add_q("contenuto_specifico", "In quali documenti si fa riferimento a comitati?", docs_comite, "lista_documentos")

docs_destinatarios = buscar_en_contenido("destinatari")
if not docs_destinatarios:
    docs_destinatarios = buscar_en_contenido("Stati membri sono destinatari")
add_q("contenuto_specifico", "Quali documenti menzionano i loro destinatari?", docs_destinatarios, "lista_documentos")

docs_tratado = buscar_en_contenido("trattato sul funzionamento")
add_q("contenuto_specifico", "Quali documenti si basano sul trattato sul funzionamento dell'Unione europea?",
      docs_tratado, "lista_documentos")

docs_espana = buscar_en_contenido("Spagna")
add_q("contenuto_specifico", "In quali documenti è citata la Spagna?", docs_espana, "lista_documentos")

docs_especies = buscar_en_contenido("specie")
add_q("contenuto_specifico", "Quali documenti fanno riferimento a specie animali o vegetali?", docs_especies, "lista_documentos")

docs_cuotas = buscar_en_contenido("contingente")
add_q("contenuto_specifico", "Quali documenti menzionano contingenti?", docs_cuotas, "lista_documentos")

docs_sancion_det = buscar_en_contenido("congelamento dei capitali")
if not docs_sancion_det:
    docs_sancion_det = buscar_en_contenido("congelamento")
add_q("contenuto_specifico", "Quali documenti menzionano il congelamento dei beni?", docs_sancion_det, "lista_documentos")

docs_plazos = buscar_en_contenido("termine")
add_q("contenuto_specifico", "In quali documenti sono stabiliti dei termini?", docs_plazos, "lista_documentos")

docs_publicacion = buscar_en_contenido("pubblicazione nella Gazzetta ufficiale")
add_q("contenuto_specifico", "Quali documenti menzionano la loro pubblicazione nella Gazzetta ufficiale?", docs_publicacion, "lista_documentos")

docs_dictamen = buscar_en_contenido("parere")
add_q("contenuto_specifico", "Quali documenti fanno riferimento a pareri?", docs_dictamen, "lista_documentos")

docs_eemm = buscar_en_contenido("Stati membri")
add_q("contenuto_specifico", "Quanti documenti fanno riferimento agli Stati membri?",
      len(docs_eemm), "numero")

docs_personas = buscar_en_contenido("persona fisica")
add_q("contenuto_specifico", "Quali documenti menzionano persone fisiche?", docs_personas, "lista_documentos")

docs_toneladas = buscar_en_contenido("tonnellat")
add_q("contenuto_specifico", "Quali documenti fanno riferimento a tonnellate?", docs_toneladas, "lista_documentos")

docs_cooperacion = buscar_en_contenido("cooperazione")
add_q("contenuto_specifico", "In quali documenti è menzionata la cooperazione?", docs_cooperacion, "lista_documentos")


# ═══════════════════════════════════════════════
# CAT 11: DOCUMENTI_INCROCIATI (richiede Knowledge Graph)
# ═══════════════════════════════════════════════
# Queste domande RICHIEDONO la sintesi di informazioni da 2+ documenti.
# Un RAG vettoriale di base recupera chunk in modo indipendente e fallisce quando
# la risposta può essere costruita solo collegando fatti di più documenti.

_ref_to_docs = defaultdict(set)
for _d, _info in doc_info.items():
    for _ref in _info.get("refs", []):
        _ref_to_docs[_ref].add(_d)

_ref_ranking = sorted(_ref_to_docs.items(), key=lambda x: (-len(x[1]), x[0]))

if _ref_ranking and len(_ref_ranking[0][1]) >= 2:
    _top_ref, _top_docs = _ref_ranking[0]
    add_q("documenti_incrociati",
          f"Elenca TUTTI i documenti del corpus che citano il regolamento {_top_ref}.",
          sorted(_top_docs), "lista_documentos")

if len(_ref_ranking) >= 2 and len(_ref_ranking[1][1]) >= 2:
    _ref2, _docs2 = _ref_ranking[1]
    add_q("documenti_incrociati",
          f"Quanti documenti del corpus fanno riferimento al regolamento {_ref2}?",
          len(_docs2), "numero")

add_q("documenti_incrociati",
      "Quanti atti legislativi esterni distinti sono citati nell'intero corpus?",
      len(_ref_to_docs), "numero")

_multi_cited = sorted(r for r, ds in _ref_to_docs.items() if len(ds) >= 2)
add_q("documenti_incrociati",
      "Quali regolamenti esterni sono citati da 2 o più documenti del corpus?",
      _multi_cited, "lista_referencias")

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
    add_q("documenti_incrociati",
          f"Quali atti legislativi sono citati SIA dal documento {doc_info[_d1]['codigo']} CHE dal documento {doc_info[_d2]['codigo']}?",
          _common, "lista_referencias")

if _pair_shared_refs:
    _d1, _d2, _common = _pair_shared_refs[0]
    add_q("documenti_incrociati",
          "Quale coppia di documenti del corpus condivide il maggior numero di riferimenti incrociati? Quanti ne condividono?",
          {"documento_1": doc_info[_d1]["codigo"], "documento_2": doc_info[_d2]["codigo"],
           "num_condivisi": len(_common), "refs_condivisi": _common}, "objeto")

_doc_codes = {info["codigo"]: d for d, info in doc_info.items() if info.get("codigo")}
_internal_refs = []
for _d, _info in doc_info.items():
    for _ref in _info.get("refs", []):
        if _ref in _doc_codes and _doc_codes[_ref] != _d:
            _internal_refs.append((_d, _doc_codes[_ref]))

if _internal_refs:
    _d1, _d2 = _internal_refs[0]
    add_q("documenti_incrociati",
          f"Il documento {doc_info[_d1]['codigo']} cita un altro documento presente nel nostro corpus. Identificalo e descrivi di cosa tratta.",
          {"citante": doc_info[_d1]["codigo"], "citato": doc_info[_d2]["codigo"],
           "titolo_citato": doc_info[_d2]["titulo"][:200]}, "objeto")

_no_refs = sorted(d for d, info in doc_info.items() if not info.get("refs"))
add_q("documenti_incrociati",
      "Quali documenti del corpus non citano nessun altro atto legislativo?",
      _no_refs, "lista_documentos")

_most_citing = sorted(doc_info.items(), key=lambda x: -len(x[1].get("refs", [])))[:3]
add_q("documenti_incrociati",
      "Quali sono i 3 documenti che citano il maggior numero di regolamenti esterni? Indica codici e quantità.",
      [{"documento": doc_info[_d]["codigo"], "num_riferimenti": len(_i.get("refs", []))} for _d, _i in _most_citing], "ranking")

_comision_docs = sorted(idx_organo.get("Commissione europea", []))
if _comision_docs:
    add_q("documenti_incrociati",
          "Tra i documenti emessi dalla Commissione europea, elenca i loro codici e date.",
          [{"documento": _d, "codigo": doc_info[_d]["codigo"], "fecha": doc_info[_d]["fecha"]}
           for _d in _comision_docs], "ranking")


# ═══════════════════════════════════════════════
# FILTRO: RIDURRE A 80-100 DOMANDE
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
    if cat == "documenti_incrociati":
        _filtered[cat] = qs
    else:
        _filtered[cat] = _remove_similar(qs, "pregunta")

_total_f = sum(len(v) for k, v in _filtered.items() if k != "documenti_incrociati") or 1
_selected = []
for cat, qs in sorted(_filtered.items()):
    if cat == "documenti_incrociati":
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

print(f"\n→ Ridotto da {len(preguntas)} a {len(_selected)} domande (obiettivo: 80-100)")
preguntas = _selected

# ═══════════════════════════════════════════════
# VERIFICA ED ESPORTAZIONE
# ═══════════════════════════════════════════════
texts = [q["pregunta"] for q in preguntas]
dupes = [t for t in texts if texts.count(t) > 1]
if dupes:
    print(f"\nATTENZIONE: {len(set(dupes))} domande duplicate:")
    for d in set(dupes):
        print(f"  - {d}")
else:
    print("\n✓ Tutte le domande sono uniche")

print(f"Totale domande generate: {len(preguntas)}")

cat_counts = Counter(q["categoria"] for q in preguntas)
print("\nDistribuzione per categoria:")
for cat, cnt in sorted(cat_counts.items()):
    print(f"  {cat}: {cnt}")

gold_standard = {
    "gold_standard": {
        "caso_uso": "documentos_ue",
        "idioma": "it",
        "total_preguntas": len(preguntas),
        "total_documentos_analizados": len(docs),
        "fecha_generacion": "2026-04-17",
        "categorias": dict(sorted(cat_counts.items())),
        "descripcion": "Gold standard per valutare un sistema RAG sui documenti della Gazzetta ufficiale dell'UE "
                       "in italiano (regolamenti, decisioni, rettifiche). Contiene domande di identificazione, "
                       "ricerca per tipo, ricerca per contenuto, conteggio, riferimenti incrociati, struttura, "
                       "esistenza, elenco, relazioni e contenuto specifico. Include una categoria "
                       "'documenti_incrociati' con domande multi-hop (riferimenti condivisi, catene di "
                       "citazioni, aggregazioni multi-documento) progettate per esporre i limiti del RAG "
                       "vettoriale di base. Tutte le risposte calcolate dai dati.",
        "preguntas": preguntas
    }
}

output_path = OUTPUT_DIR / "gold_standard_eu_it.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(gold_standard, f, ensure_ascii=False, indent=2)

print(f"\n✓ Gold standard salvato in: {output_path}")
