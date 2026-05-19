"""
Script para gerar o Gold Standard do caso de uso dos documentos da UE em português.
Gera 80-100 perguntas únicas com respostas extraídas diretamente dos documentos.
Estrutura de dados: documentos do Jornal Oficial da UE (série L) em formato JSON
  - archivo, idioma, num_paginas, contenido, paginas
Autor: Gerado automaticamente para o TFG
Data: 2026-04-17
"""
import json
import re
import random
from collections import Counter, defaultdict
from pathlib import Path
random.seed(42)
# ─────────────────────────────────────────────
# 1. CARREGAR TODOS OS DOCUMENTOS
# ─────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[3]
EU_DIR = ROOT / "data" / "eu" / "pt" / "json"
OUTPUT_DIR = ROOT / "src" / "test" / "gold_standard_data"
docs = {}
for f in sorted(EU_DIR.glob("*.json")):
    with open(f, encoding="utf-8") as fh:
        doc = json.load(fh)
        docs[doc["archivo"].replace(".pdf", "")] = doc
print(f"Carregados {len(docs)} documentos")
# ─────────────────────────────────────────────
# 2. ANALISAR E CONSTRUIR ÍNDICES
# ─────────────────────────────────────────────
doc_info = {}
for doc_id, doc in docs.items():
    text = doc["contenido"][:3000]
    # Tipo de documento
    m = re.search(r'(REGULAMENTO|DECISÃO|RETIFICAÇÃO|ACORDO|DIRETIVA)', text)
    tipo = m.group(1) if m else "OUTRO"
    # Código do documento
    m_code = re.search(r'(\d{4}/\d+)\s', text)
    code = m_code.group(1) if m_code else doc_id
    # Título completo
    m_title = re.search(r'((?:REGULAMENTO|DECISÃO|RETIFICAÇÃO|DIRETIVA|ACORDO)[\s\S]*?)(?:\n(?:A COMISSÃO|O CONSELHO|O PARLAMENTO|Tendo em|considerando|\(Texto))', text)
    titulo = m_title.group(1).replace('\n', ' ').strip() if m_title else ""
    titulo = re.sub(r'\s+', ' ', titulo)
    # Organismo emissor
    organos = []
    if "COMISSÃO" in text[:2000]:
        organos.append("Comissão Europeia")
    if "CONSELHO" in text[:2000]:
        organos.append("Conselho")
    if "PARLAMENTO EUROPEU" in text[:2000]:
        organos.append("Parlamento Europeu")
    # Data do documento
    m_fecha = re.search(r'de\s+(\d{1,2})\s+de\s+(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})', text)
    fecha = f"{m_fecha.group(1)} de {m_fecha.group(2)} de {m_fecha.group(3)}" if m_fecha else ""
    # Número de artigos
    articulos_found = re.findall(r'Artigo\s+(\d+)', text + doc["contenido"][3000:])
    num_articulos = max([int(a) for a in articulos_found]) if articulos_found else 0
    # Número de considerandos
    considerandos = re.findall(r'\((\d+)\)\s', doc["contenido"][:10000])
    num_considerandos = max([int(c) for c in considerandos]) if considerandos else 0
    # Referências cruzadas
    refs = re.findall(r'(?:Regulamento|Decisão|Diretiva)\s+\([A-Z]+\)\s+(?:n\.o\s*)?(\d{4}/\d+)', doc["contenido"])
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
# Índices
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
print(f"\nTipos: {dict(Counter(i['tipo'] for i in doc_info.values()))}")
print(f"Órgãos: {dict(Counter(o for i in doc_info.values() for o in i['organos']))}")
# ─────────────────────────────────────────────
# 3. GERAR PERGUNTAS
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
# CAT 1: IDENTIFICAÇÃO DE DOCUMENTOS (25)
# ═══════════════════════════════════════════════
d, doc, info = next_doc()
add_q("identificacao", f"Que tipo de documento é {info['codigo']}?", info["tipo"])
d, doc, info = next_doc()
add_q("identificacao", f"Do que trata o documento {info['codigo']}?", info["titulo"])
d, doc, info = next_doc()
add_q("identificacao", f"Quem emitiu o documento {info['codigo']}?", info["organos"], "lista")
d, doc, info = next_doc()
add_q("identificacao", f"Qual é a data do documento {info['codigo']}?", info["fecha"])
d, doc, info = next_doc()
add_q("identificacao", f"Dê-me o título completo do documento {d}.", info["titulo"])
d, doc, info = next_doc()
add_q("identificacao", f"Qual instituição europeia é responsável pelo documento {info['codigo']}?", info["organos"], "lista")
d, doc, info = next_doc()
add_q("identificacao", f"Identifique o tipo e a data do documento {info['codigo']}.", {"tipo": info["tipo"], "fecha": info["fecha"]}, "objeto")
d, doc, info = next_doc()
add_q("identificacao", f"Quantas páginas tem o documento {info['codigo']}?", info["num_paginas"], "numero")
d, doc, info = next_doc()
add_q("identificacao", f"Resuma numa frase o conteúdo do documento {d}.", info["titulo"])
d, doc, info = next_doc()
add_q("identificacao", f"A que se refere o documento número {info['codigo']}?", info["titulo"])
d, doc, info = next_doc()
add_q("identificacao", f"Quantos artigos contém o documento {info['codigo']}?", info["num_articulos"], "numero")
d, doc, info = next_doc()
add_q("identificacao", f"Forneça os metadados principais do documento {d}.",
      {"tipo": info["tipo"], "fecha": info["fecha"], "organos": info["organos"], "paginas": info["num_paginas"]}, "objeto")
d, doc, info = next_doc()
add_q("identificacao", f"Qual é o conteúdo do documento com o código {info['codigo']}?", info["titulo"])
d, doc, info = next_doc()
add_q("identificacao", f"Que organismo aprovou o documento {info['codigo']}?", info["organos"], "lista")
d, doc, info = next_doc()
add_q("identificacao", f"Preciso de saber do que trata {d}. Qual é o seu tema principal?", info["titulo"])
d, doc, info = next_doc()
add_q("identificacao", f"Em que data foi adotado o documento {info['codigo']}?", info["fecha"])
d, doc, info = next_doc()
add_q("identificacao", f"Descreva brevemente o objeto do documento {info['codigo']}.", info["titulo"])
d, doc, info = next_doc()
add_q("identificacao", f"Quantos considerandos tem o documento {info['codigo']}?", info["num_considerandos"], "numero")
remaining = list(d_iter)
if remaining:
    d = remaining[0]
    info = doc_info[d]
    add_q("identificacao", f"Quantas palavras contém aproximadamente o documento {info['codigo']}?", info["num_palabras"], "numero")
for i, d in enumerate(list(doc_info.keys())[:6]):
    info = doc_info[d]
    templates = [
        f"O documento {d} é um regulamento ou uma decisão?",
        f"Quantas páginas tem o ficheiro {d}?",
        f"Indique a data de adoção de {d}.",
        f"Que instituições participaram na elaboração de {d}?",
        f"Dê-me um resumo do documento {d}.",
        f"Qual é o código numérico do documento contido em {d}?",
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
    add_q("identificacao", templates[i], respuestas[i], tipos[i])
# ═══════════════════════════════════════════════
# CAT 2: PESQUISA POR TIPO DE DOCUMENTO (15)
# ═══════════════════════════════════════════════
add_q("pesquisa_por_tipo", "Quantos regulamentos existem na base de dados?", len(idx_tipo.get("REGULAMENTO", [])), "numero")
add_q("pesquisa_por_tipo", "Quantas decisões contém a coleção?", len(idx_tipo.get("DECISÃO", [])), "numero")
add_q("pesquisa_por_tipo", "liste todos os regulamentos disponíveis.", idx_tipo.get("REGULAMENTO", []), "lista_documentos")
add_q("pesquisa_por_tipo", "Dê-me todas as decisões da base de dados.", idx_tipo.get("DECISÃO", []), "lista_documentos")
add_q("pesquisa_por_tipo", "Que tipos de documentos legislativos temos?", sorted(set(i["tipo"] for i in doc_info.values())), "lista")
add_q("pesquisa_por_tipo", "Existe algum documento de tipo retificação?",
      {"existe": "RETIFICAÇÃO" in idx_tipo or any("Retificação" in docs[d]["contenido"][:500] for d in docs),
       "documentos": idx_tipo.get("RETIFICAÇÃO", []) + [d for d in docs if "Retificação" in docs[d]["contenido"][:500]]}, "booleano")
add_q("pesquisa_por_tipo", "Filtre os documentos que são regulamentos de execução.",
      [d for d in docs if "REGULAMENTO DE EXECUÇÃO" in docs[d]["contenido"][:1000]], "lista_documentos")
add_q("pesquisa_por_tipo", "Quais são os documentos emitidos pela Comissão Europeia?", idx_organo.get("Comissão Europeia", []), "lista_documentos")
add_q("pesquisa_por_tipo", "Quais documentos foram aprovados pelo Conselho?", idx_organo.get("Conselho", []), "lista_documentos")
add_q("pesquisa_por_tipo", "Existem documentos do Parlamento Europeu?", idx_organo.get("Parlamento Europeu", []), "lista_documentos")
add_q("pesquisa_por_tipo", "Quantos documentos emitiu a Comissão Europeia?", len(idx_organo.get("Comissão Europeia", [])), "numero")
add_q("pesquisa_por_tipo", "Que documentos de 2026 temos?",
      [d for d, i in doc_info.items() if "2026" in i["fecha"]], "lista_documentos")
add_q("pesquisa_por_tipo", "Quais são os documentos de 2025?",
      [d for d, i in doc_info.items() if "2025" in i["fecha"]], "lista_documentos")
add_q("pesquisa_por_tipo", "Procure documentos que contenham decisões de execução.",
      [d for d in docs if "DECISÃO DE EXECUÇÃO" in docs[d]["contenido"][:1000]], "lista_documentos")
add_q("pesquisa_por_tipo", "Quais documentos são regulamentos delegados?",
      [d for d in docs if "REGULAMENTO DELEGADO" in docs[d]["contenido"][:1000]], "lista_documentos")
# ═══════════════════════════════════════════════
# CAT 3: PESQUISA POR CONTEÚDO / TEMÁTICA (30)
# ═══════════════════════════════════════════════
temas = [
    ("pesca", "Quais documentos tratam de pesca?"),
    ("dispositivos médicos", "Quais documentos se referem a dispositivos médicos?"),
    ("Marrocos", "Em que documentos é mencionado Marrocos?"),
    ("medidas restritivas", "liste os documentos que tratam de medidas restritivas."),
    ("normas harmonizadas", "Quais documentos fazem referência a normas harmonizadas?"),
    ("possibilidades de pesca", "Quais documentos regulam as possibilidades de pesca?"),
    ("pesticidas", "Existem documentos que mencionam pesticidas ou resíduos de pesticidas?"),
    ("Regulamento (UE) 2017/745", "Quais documentos fazem referência ao Regulamento (UE) 2017/745?"),
    ("peste suína", "Existem documentos sobre a peste suína?"),
    ("gripe aviária", "Quais documentos mencionam a gripe aviária?"),
    ("substâncias de origem humana", "Existe algum documento sobre substâncias de origem humana?"),
    ("indicação geográfica", "Quais documentos tratam de indicações geográficas?"),
    ("Fundo Europeu", "Quais documentos fazem referência a um Fundo Europeu?"),
    ("Tunísia", "A Tunísia é mencionada em algum dos documentos?"),
    ("Euro-Mediterrânico", "Quais documentos fazem referência ao acordo Euro-Mediterrânico?"),
    ("esterilização", "Existem documentos sobre esterilização de produtos?"),
    ("Atlântico", "Quais documentos mencionam o Atlântico?"),
    ("Mediterrâneo", "liste os documentos que se referem ao Mediterrâneo."),
    ("Conselho de Associação", "Quais documentos mencionam um Conselho de Associação?"),
    ("anexo", "Quais documentos contêm ou alteram anexos?"),
    ("importação", "Quais documentos tratam de importações?"),
    ("PESC", "Existem documentos relacionados com a Política Externa e de Segurança Comum (PESC)?"),
    ("sanções", "Quais documentos fazem referência a sanções?"),
    ("segurança alimentar", "Existem documentos sobre segurança alimentar?"),
    ("Jornal Oficial", "Em quantos documentos se faz referência ao Jornal Oficial?"),
    ("mel", "Existe algum documento que mencione o mel?"),
    ("países terceiros", "Quais documentos fazem referência a países terceiros?"),
    ("biocompatibilidade", "A biocompatibilidade é mencionada em algum documento?"),
    ("Báltico", "Quais documentos fazem referência ao mar Báltico?"),
    ("resíduos", "liste os documentos que contenham a palavra resíduos."),
]
for kw, pregunta in temas:
    r = buscar_en_contenido(kw)
    add_q("pesquisa_por_conteudo", pregunta, r, "lista_documentos")
# ═══════════════════════════════════════════════
# CAT 4: CONTAGEM E ESTATÍSTICAS (25)
# ═══════════════════════════════════════════════
add_q("contagem", "Quantos documentos existem no total na base de dados?", len(docs), "numero")
add_q("contagem", "Quantas páginas somam todos os documentos juntos?",
      sum(d["num_paginas"] for d in docs.values()), "numero")
add_q("contagem", "Qual é o documento mais longo em número de páginas?",
      {"documento": max(doc_info.items(), key=lambda x: x[1]["num_paginas"])[0],
       "paginas": max(i["num_paginas"] for i in doc_info.values())}, "objeto")
add_q("contagem", "Qual é o documento mais curto?",
      {"documento": min(doc_info.items(), key=lambda x: x[1]["num_paginas"])[0],
       "paginas": min(i["num_paginas"] for i in doc_info.values())}, "objeto")
add_q("contagem", "Quantas palavras existem no total em todos os documentos?",
      sum(i["num_palabras"] for i in doc_info.values()), "numero")
avg_pags = round(sum(i["num_paginas"] for i in doc_info.values()) / len(doc_info), 1)
add_q("contagem", "Qual é a média de páginas por documento?", avg_pags, "numero")
avg_words = round(sum(i["num_palabras"] for i in doc_info.values()) / len(doc_info), 1)
add_q("contagem", "Qual é a média de palavras por documento?", avg_words, "numero")
add_q("contagem", "Quantos documentos têm mais de 50 páginas?",
      len([d for d, i in doc_info.items() if i["num_paginas"] > 50]), "numero")
add_q("contagem", "Quantos documentos têm menos de 10 páginas?",
      len([d for d, i in doc_info.items() if i["num_paginas"] < 10]), "numero")
top5 = sorted(doc_info.items(), key=lambda x: -x[1]["num_paginas"])[:5]
add_q("contagem", "Quais são os 5 documentos mais extensos?",
      [{"documento": d, "paginas": i["num_paginas"]} for d, i in top5], "ranking")
bot5 = sorted(doc_info.items(), key=lambda x: x[1]["num_paginas"])[:5]
add_q("contagem", "Quais são os 5 documentos mais breves?",
      [{"documento": d, "paginas": i["num_paginas"]} for d, i in bot5], "ranking")
add_q("contagem", "Quantos tipos diferentes de documentos existem?",
      len(set(i["tipo"] for i in doc_info.values())), "numero")
tipo_counts = Counter(i["tipo"] for i in doc_info.values())
add_q("contagem", "Qual é a distribuição de documentos por tipo?",
      [{"tipo": t, "cantidad": c} for t, c in tipo_counts.most_common()], "ranking")
add_q("contagem", "Quantos documentos mencionam a palavra «pesca»?",
      len(buscar_en_contenido("pesca")), "numero")
add_q("contagem", "Quantos documentos contêm artigos numerados?",
      len([d for d, i in doc_info.items() if i["num_articulos"] > 0]), "numero")
max_arts = max(doc_info.items(), key=lambda x: x[1]["num_articulos"])
add_q("contagem", "Qual documento tem mais artigos?",
      {"documento": max_arts[0], "num_articulos": max_arts[1]["num_articulos"]}, "objeto")
add_q("contagem", "Quantos documentos foram emitidos em janeiro de 2026?",
      len([d for d, i in doc_info.items() if "janeiro de 2026" in i["fecha"]]), "numero")
add_q("contagem", "Quantos documentos foram emitidos em dezembro de 2025?",
      len([d for d, i in doc_info.items() if "dezembro de 2025" in i["fecha"]]), "numero")
add_q("contagem", "Quantos documentos mencionam sanções ou medidas restritivas?",
      len(set(buscar_en_contenido("sanções") + buscar_en_contenido("medidas restritivas"))), "numero")
add_q("contagem", "Quantos documentos fazem referência a outros regulamentos da UE?",
      len([d for d, i in doc_info.items() if len(i["refs"]) > 0]), "numero")
total_refs = sum(len(i["refs"]) for i in doc_info.values())
add_q("contagem", "Quantas referências cruzadas a outros documentos existem no total?", total_refs, "numero")
add_q("contagem", "Quantos documentos ultrapassam as 100 páginas?",
      len([d for d, i in doc_info.items() if i["num_paginas"] > 100]), "numero")
add_q("contagem", "Quantos caracteres tem o documento mais longo?",
      max(i["num_chars"] for i in doc_info.values()), "numero")
add_q("contagem", "Quantos documentos contêm a palavra «Regulamento»?",
      len(buscar_en_contenido("Regulamento")), "numero")
# ═══════════════════════════════════════════════
# CAT 5: REFERÊNCIAS CRUZADAS (20)
# ═══════════════════════════════════════════════
docs_con_refs = [(d, i) for d, i in doc_info.items() if len(i["refs"]) >= 2]
random.shuffle(docs_con_refs)
ref_iter = iter(docs_con_refs)
for template in [
    "A que outros regulamentos ou decisões faz referência o documento {}?",
    "liste as normas citadas no documento {}.",
    "Que legislação anterior menciona o documento {}?",
    "Quais são as referências normativas do documento {}?",
    "Dê-me as referências a outros atos legislativos que aparecem em {}.",
    "Que regulamentos modifica ou cita o documento {}?",
    "Identifique a legislação da UE referenciada em {}.",
    "Com que outra legislação está relacionado o documento {}?",
    "Enumere os regulamentos e decisões citados em {}.",
    "Que base jurídica é mencionada no documento {}?",
]:
    try:
        d, i = next(ref_iter)
        add_q("referencias_cruzadas", template.format(i["codigo"]), i["refs"], "lista_referencias")
    except StopIteration:
        break
all_refs = defaultdict(list)
for d, i in doc_info.items():
    for r in i["refs"]:
        all_refs[r].append(d)
shared_refs = [(r, ds) for r, ds in all_refs.items() if len(ds) >= 2]
random.shuffle(shared_refs)
for template in [
    "Quais documentos fazem referência ao {}?",
    "Quais documentos citam o {}?",
    "liste os documentos que mencionam o {}.",
    "Em quantos documentos é referenciado o {}?",
    "Quais documentos estão relacionados com o {}?",
]:
    if shared_refs:
        ref, ds = shared_refs.pop()
        ref_name = f"Regulamento/Decisão {ref}"
        add_q("referencias_cruzadas", template.format(ref_name), ds, "lista_documentos")
for d, i in list(doc_info.items())[:5]:
    if i["refs"]:
        add_q("referencias_cruzadas", f"Quantas referências a outros atos contém o documento {i['codigo']}?",
              len(i["refs"]), "numero")
# ═══════════════════════════════════════════════
# CAT 6: ESTRUTURA DOS DOCUMENTOS (20)
# ═══════════════════════════════════════════════
for d, i in list(doc_info.items()):
    if i["num_articulos"] > 0:
        break
d_art = d
info_art = doc_info[d_art]
add_q("estrutura", f"Quantos artigos tem o documento {info_art['codigo']}?", info_art["num_articulos"], "numero")
docs_con_consid = [(d, i) for d, i in doc_info.items() if i["num_considerandos"] > 0]
random.shuffle(docs_con_consid)
for idx, template in enumerate([
    "Quantos considerandos tem o documento {}?",
    "Quantos considerandos contém o preâmbulo de {}?",
    "Indique o número de considerandos do documento {}.",
    "Quantos pontos tem a parte considerativa de {}?",
    "Dê-me o número total de considerandos de {}.",
]):
    if idx < len(docs_con_consid):
        d, i = docs_con_consid[idx]
        add_q("estrutura", template.format(i["codigo"]), i["num_considerandos"], "numero")
docs_con_anexo = buscar_en_contenido("ANEXO")
add_q("estrutura", "Quais documentos contêm anexos?", docs_con_anexo, "lista_documentos")
add_q("estrutura", "Quantos documentos incluem anexos?", len(docs_con_anexo), "numero")
docs_con_tabla = buscar_en_contenido("quadro")
add_q("estrutura", "Quais documentos contêm quadros ou tabelas?", docs_con_tabla, "lista_documentos")
arts_por_doc = sorted([(d, i["num_articulos"]) for d, i in doc_info.items() if i["num_articulos"] > 0],
                      key=lambda x: -x[1])
add_q("estrutura", "Quais documentos têm artigos e quantos tem cada um?",
      [{"documento": d, "num_articulos": n} for d, n in arts_por_doc], "ranking")
add_q("estrutura", "liste todos os documentos ordenados por número de páginas de maior a menor.",
      [{"documento": d, "paginas": i["num_paginas"]} for d, i in sorted(doc_info.items(), key=lambda x: -x[1]["num_paginas"])], "ranking")
docs_con_porcentaje = buscar_en_contenido("%")
add_q("estrutura", "Quais documentos contêm dados percentuais?", docs_con_porcentaje, "lista_documentos")
docs_con_aplicacion = buscar_en_contenido("é aplicável a partir de")
add_q("estrutura", "Quais documentos especificam uma data de aplicação?", docs_con_aplicacion, "lista_documentos")
docs_transitorio = buscar_en_contenido("disposições transitórias")
if not docs_transitorio:
    docs_transitorio = buscar_en_contenido("transitória")
add_q("estrutura", "Existem documentos com disposições transitórias?", docs_transitorio, "lista_documentos")
docs_obligatorio = buscar_en_contenido("obrigatório em todos os seus elementos")
add_q("estrutura", "Quais documentos se declaram obrigatórios em todos os seus elementos?", docs_obligatorio, "lista_documentos")
all_docs_summary = [{"documento": d, "tipo": i["tipo"], "fecha": i["fecha"], "paginas": i["num_paginas"]}
                    for d, i in sorted(doc_info.items())]
add_q("estrutura", "Dê-me uma visão geral de todos os documentos com tipo, data e número de páginas.", all_docs_summary, "tabla")
# ═══════════════════════════════════════════════
# CAT 7: EXISTÊNCIA E VERIFICAÇÃO (20)
# ═══════════════════════════════════════════════
add_q("existencia", "Existe algum documento sobre pesca no Atlântico?",
      {"existe": len(set(buscar_en_contenido("pesca")) & set(buscar_en_contenido("Atlântico"))) > 0,
       "documentos": sorted(set(buscar_en_contenido("pesca")) & set(buscar_en_contenido("Atlântico")))}, "booleano")
add_q("existencia", "Existe algum regulamento de execução na base de dados?",
      {"existe": len([d for d in docs if "REGULAMENTO DE EXECUÇÃO" in docs[d]["contenido"][:1000]]) > 0,
       "documentos": [d for d in docs if "REGULAMENTO DE EXECUÇÃO" in docs[d]["contenido"][:1000]]}, "booleano")
add_q("existencia", "Existem documentos que tratam da Ucrânia?",
      {"existe": len(buscar_en_contenido("Ucrânia")) > 0, "documentos": buscar_en_contenido("Ucrânia")}, "booleano")
add_q("existencia", "A Rússia é mencionada em algum documento?",
      {"existe": len(buscar_en_contenido("Rússia")) > 0, "documentos": buscar_en_contenido("Rússia")}, "booleano")
add_q("existencia", "Existe algum documento sobre inteligência artificial?",
      {"existe": len(buscar_en_contenido("inteligência artificial")) > 0, "documentos": buscar_en_contenido("inteligência artificial")}, "booleano")
add_q("existencia", "Existem documentos sobre alterações climáticas?",
      {"existe": len(buscar_en_contenido("alterações climáticas")) > 0, "documentos": buscar_en_contenido("alterações climáticas")}, "booleano")
add_q("existencia", "Existem documentos relativos aos direitos humanos?",
      {"existe": len(buscar_en_contenido("direitos humanos")) > 0, "documentos": buscar_en_contenido("direitos humanos")}, "booleano")
add_q("existencia", "A China é mencionada em algum documento?",
      {"existe": len(buscar_en_contenido("China")) > 0, "documentos": buscar_en_contenido("China")}, "booleano")
add_q("existencia", "Existem documentos sobre política agrícola?",
      {"existe": len(buscar_en_contenido("agrícola")) > 0, "documentos": buscar_en_contenido("agrícola")}, "booleano")
add_q("existencia", "Existe algum documento que mencione o euro?",
      {"existe": len(buscar_en_contenido("euro")) > 0, "documentos": buscar_en_contenido("euro")}, "booleano")
add_q("existencia", "A OTAN é mencionada em algum documento?",
      {"existe": len(buscar_en_contenido("OTAN")) > 0, "documentos": buscar_en_contenido("OTAN")}, "booleano")
add_q("existencia", "Existem documentos sobre proteção de dados?",
      {"existe": len(buscar_en_contenido("proteção de dados")) > 0, "documentos": buscar_en_contenido("proteção de dados")}, "booleano")
add_q("existencia", "Existe algum documento sobre transportes?",
      {"existe": len(buscar_en_contenido("transporte")) > 0, "documentos": buscar_en_contenido("transporte")}, "booleano")
add_q("existencia", "A Síria é mencionada em algum dos documentos?",
      {"existe": len(buscar_en_contenido("Síria")) > 0, "documentos": buscar_en_contenido("Síria")}, "booleano")
add_q("existencia", "Existem documentos sobre energia?",
      {"existe": len(buscar_en_contenido("energia")) > 0, "documentos": buscar_en_contenido("energia")}, "booleano")
add_q("existencia", "Existe algum documento relativo ao Espaço Económico Europeu (EEE)?",
      {"existe": len(buscar_en_contenido("EEE")) > 0, "documentos": buscar_en_contenido("EEE")}, "booleano")
add_q("existencia", "A Bielorrússia é mencionada em algum documento?",
      {"existe": len(buscar_en_contenido("Bielorrússia")) > 0, "documentos": buscar_en_contenido("Bielorrússia")}, "booleano")
add_q("existencia", "Existe algum documento sobre alfândegas ou tarifas?",
      {"existe": len(set(buscar_en_contenido("alfândega") + buscar_en_contenido("tarifa"))) > 0,
       "documentos": sorted(set(buscar_en_contenido("alfândega") + buscar_en_contenido("tarifa")))}, "booleano")
add_q("existencia", "Existe algum documento sobre medicamentos?",
      {"existe": len(buscar_en_contenido("medicamento")) > 0, "documentos": buscar_en_contenido("medicamento")}, "booleano")
add_q("existencia", "Existe algum documento que mencione uma denominação de origem protegida (DOP)?",
      {"existe": len(buscar_en_contenido("DOP")) > 0, "documentos": buscar_en_contenido("DOP")}, "booleano")
# ═══════════════════════════════════════════════
# CAT 8: LISTAGEM E CATÁLOGO (15)
# ═══════════════════════════════════════════════
add_q("listagem", "Dê-me a lista completa de todos os documentos disponíveis.", sorted(docs.keys()), "lista_documentos")
add_q("listagem", "Quais são todos os documentos na base de dados?", sorted(docs.keys()), "lista_documentos")
add_q("listagem", "Enumere todos os documentos da coleção.", sorted(docs.keys()), "lista_documentos")
add_q("listagem", "Preciso de ver o catálogo completo dos documentos da UE.", sorted(docs.keys()), "lista_documentos")
add_q("listagem", "Mostre-me uma lista de todos os documentos do Jornal Oficial disponíveis.", sorted(docs.keys()), "lista_documentos")
for org in sorted(idx_organo.keys()):
    add_q("listagem", f"liste todos os documentos emitidos pela {org}.", sorted(idx_organo[org]), "lista_documentos")
for tipo in sorted(idx_tipo.keys()):
    add_q("listagem", f"liste todos os documentos de tipo {tipo}.", sorted(idx_tipo[tipo]), "lista_documentos")
docs_2025 = sorted([d for d, i in doc_info.items() if "2025" in i["fecha"]])
docs_2026 = sorted([d for d, i in doc_info.items() if "2026" in i["fecha"]])
add_q("listagem", "Quais documentos são do ano 2025?", docs_2025, "lista_documentos")
add_q("listagem", "Quais documentos correspondem ao ano 2026?", docs_2026, "lista_documentos")
# ═══════════════════════════════════════════════
# CAT 9: COMPARAÇÕES E RELAÇÕES (30)
# ═══════════════════════════════════════════════
d_max = max(doc_info.items(), key=lambda x: x[1]["num_paginas"])
d_min = min(doc_info.items(), key=lambda x: x[1]["num_paginas"])
add_q("relacoes", "Qual é o documento mais longo e qual é o mais curto?",
      {"mais_longo": {"documento": d_max[0], "paginas": d_max[1]["num_paginas"]},
       "mais_curto": {"documento": d_min[0], "paginas": d_min[1]["num_paginas"]}}, "objeto")
add_q("relacoes", "Quantas vezes o documento mais extenso é maior do que o mais breve?",
      round(d_max[1]["num_paginas"] / d_min[1]["num_paginas"], 1), "numero")
pesca_docs = set(buscar_en_contenido("pesca"))
sanitarios_docs = set(buscar_en_contenido("sanitário"))
add_q("relacoes", "Existem documentos que tratem simultaneamente de pesca e saúde?",
      sorted(pesca_docs & sanitarios_docs), "lista_documentos")
top_refs = sorted(doc_info.items(), key=lambda x: -len(x[1]["refs"]))[:5]
add_q("relacoes", "Quais são os 5 documentos com mais referências a outros atos legislativos?",
      [{"documento": d, "num_referencias": len(i["refs"])} for d, i in top_refs], "ranking")
paises = ["Espanha", "França", "Alemanha", "Itália", "Portugal", "Grécia", "Marrocos", "Tunísia", "Noruega", "Islândia"]
for pais in paises:
    docs_pais = buscar_en_contenido(pais)
    add_q("relacoes", f"Em que documentos é mencionado(a) {pais}?", docs_pais, "lista_documentos")
add_q("relacoes", "Quais documentos foram emitidos conjuntamente pelo Parlamento Europeu e pelo Conselho?",
      sorted(set(idx_organo.get("Parlamento Europeu", [])) & set(idx_organo.get("Conselho", []))), "lista_documentos")
add_q("relacoes", "Quais documentos estão relacionados com saúde ou questões médicas?",
      sorted(set(buscar_en_contenido("sanitário") + buscar_en_contenido("saúde") + buscar_en_contenido("medicamento"))), "lista_documentos")
add_q("relacoes", "Quais documentos tratam de comércio internacional ou relações externas?",
      sorted(set(buscar_en_contenido("comércio") + buscar_en_contenido("relações externas") + buscar_en_contenido("acordo comercial"))), "lista_documentos")
docs_disposiciones = buscar_en_contenido("entra em vigor")
add_q("relacoes", "Quais documentos contêm disposições sobre entrada em vigor?", docs_disposiciones, "lista_documentos")
regs = idx_tipo.get("REGULAMENTO", [])
if len(regs) >= 2:
    r1, r2 = regs[0], regs[1]
    add_q("relacoes", f"Compare os documentos {doc_info[r1]['codigo']} e {doc_info[r2]['codigo']}: o que têm em comum?",
          {"tipo_comum": "REGULAMENTO",
           "doc1": {"codigo": doc_info[r1]["codigo"], "fecha": doc_info[r1]["fecha"], "paginas": doc_info[r1]["num_paginas"]},
           "doc2": {"codigo": doc_info[r2]["codigo"], "fecha": doc_info[r2]["fecha"], "paginas": doc_info[r2]["num_paginas"]}}, "objeto")
docs_por_fecha = sorted(doc_info.items(), key=lambda x: x[1]["fecha"], reverse=True)
add_q("relacoes", "Quais são os documentos mais recentes?",
      [{"documento": d, "fecha": i["fecha"]} for d, i in docs_por_fecha[:5]], "ranking")
docs_seguridad = sorted(set(buscar_en_contenido("segurança") + buscar_en_contenido("defesa")))
add_q("relacoes", "Quais documentos tratam de segurança ou defesa?", docs_seguridad, "lista_documentos")
docs_ambiente = sorted(set(buscar_en_contenido("ambiente") + buscar_en_contenido("ambiental")))
add_q("relacoes", "Existem documentos relacionados com o ambiente?", docs_ambiente, "lista_documentos")
top_arts = sorted(doc_info.items(), key=lambda x: -x[1]["num_articulos"])[:5]
add_q("relacoes", "Quais são os 5 documentos com mais artigos?",
      [{"documento": d, "num_articulos": i["num_articulos"]} for d, i in top_arts], "ranking")
meses = Counter()
for d, i in doc_info.items():
    m = re.search(r'(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)', i["fecha"])
    if m:
        meses[m.group(1)] += 1
add_q("relacoes", "Como se distribuem os documentos por mês de emissão?",
      [{"mes": m, "quantidade": c} for m, c in meses.most_common()], "ranking")
# ═══════════════════════════════════════════════
# CAT 10: CONTEÚDO ESPECÍFICO / DETALHE (25)
# ═══════════════════════════════════════════════
for d_id in list(doc_info.keys())[:8]:
    text = docs[d_id]["contenido"]
    info = doc_info[d_id]
    if info["num_articulos"] >= 2:
        m_art1 = re.search(r'Artigo\s+1\.?[°o]?\s*\n([\s\S]*?)(?:Artigo\s+2|\Z)', text)
        if m_art1:
            art1_text = m_art1.group(1).strip()[:500]
            art1_text = re.sub(r'\s+', ' ', art1_text)
            add_q("conteudo_especifico",
                  f"Qual é o conteúdo do Artigo 1.° do documento {info['codigo']}?",
                  art1_text, "texto_largo")
            break
for d_id in list(doc_info.keys()):
    if doc_info[d_id]["num_paginas"] >= 3:
        pag2 = docs[d_id]["paginas"][1][:300] if len(docs[d_id]["paginas"]) > 1 else ""
        if pag2.strip():
            pag2_clean = re.sub(r'\s+', ' ', pag2).strip()
            add_q("conteudo_especifico",
                  f"Que informação aparece na página 2 do documento {doc_info[d_id]['codigo']}?",
                  pag2_clean, "texto_largo")
            break
docs_vigor = []
for d_id, doc in docs.items():
    m = re.search(r'entra em vigor\s+(?:no\s+|em\s+)?(.+?)(?:\.|$)', doc["contenido"])
    if m:
        docs_vigor.append({"documento": d_id, "entrada_em_vigor": m.group(1).strip()[:100]})
if docs_vigor:
    add_q("conteudo_especifico", "Quais documentos especificam a data de entrada em vigor e quando é?",
          docs_vigor, "lista_detallada")
docs_ambito = []
for d_id, doc in docs.items():
    m = re.search(r'(?:âmbito de aplicação|aplica-se a|aplicável a)[\s:]*(.{50,300})', doc["contenido"], re.IGNORECASE)
    if m:
        docs_ambito.append(d_id)
add_q("conteudo_especifico", "Quais documentos definem o seu âmbito de aplicação?", docs_ambito, "lista_documentos")
docs_definiciones = buscar_en_contenido("definições")
add_q("conteudo_especifico", "Quais documentos contêm uma secção de definições?", docs_definiciones, "lista_documentos")
docs_deroga = buscar_en_contenido("é revogado")
add_q("conteudo_especifico", "Quais documentos contêm cláusulas de revogação?", docs_deroga, "lista_documentos")
docs_modifica = buscar_en_contenido("é alterado")
add_q("conteudo_especifico", "Quais documentos alteram legislação preexistente?", docs_modifica, "lista_documentos")
docs_comite = buscar_en_contenido("comité")
add_q("conteudo_especifico", "Em quais documentos se faz referência a comités?", docs_comite, "lista_documentos")
docs_destinatarios = buscar_en_contenido("destinatários")
if not docs_destinatarios:
    docs_destinatarios = buscar_en_contenido("Estados-Membros são os destinatários")
add_q("conteudo_especifico", "Quais documentos mencionam os seus destinatários?", docs_destinatarios, "lista_documentos")
docs_tratado = buscar_en_contenido("Tratado sobre o Funcionamento")
add_q("conteudo_especifico", "Quais documentos se baseiam no Tratado sobre o Funcionamento da União Europeia?",
      docs_tratado, "lista_documentos")
docs_espana = buscar_en_contenido("Espanha")
add_q("conteudo_especifico", "Em que documentos é referida a Espanha?", docs_espana, "lista_documentos")
docs_especies = buscar_en_contenido("espécies")
add_q("conteudo_especifico", "Quais documentos fazem referência a espécies animais ou vegetais?", docs_especies, "lista_documentos")
docs_cuotas = buscar_en_contenido("quota")
add_q("conteudo_especifico", "Quais documentos mencionam quotas?", docs_cuotas, "lista_documentos")
docs_sancion_det = buscar_en_contenido("congelamento de fundos")
if not docs_sancion_det:
    docs_sancion_det = buscar_en_contenido("congelamento")
add_q("conteudo_especifico", "Quais documentos mencionam o congelamento de fundos?", docs_sancion_det, "lista_documentos")
docs_plazos = buscar_en_contenido("prazo")
add_q("conteudo_especifico", "Em quais documentos são estabelecidos prazos?", docs_plazos, "lista_documentos")
docs_publicacion = buscar_en_contenido("publicação no Jornal Oficial")
add_q("conteudo_especifico", "Quais documentos mencionam a sua publicação no Jornal Oficial?", docs_publicacion, "lista_documentos")
docs_dictamen = buscar_en_contenido("parecer")
add_q("conteudo_especifico", "Quais documentos fazem referência a pareceres?", docs_dictamen, "lista_documentos")
docs_eemm = buscar_en_contenido("Estados-Membros")
add_q("conteudo_especifico", "Quantos documentos fazem referência aos Estados-Membros?",
      len(docs_eemm), "numero")
docs_personas = buscar_en_contenido("pessoa singular")
if not docs_personas:
    docs_personas = buscar_en_contenido("pessoa singular")
add_q("conteudo_especifico", "Quais documentos mencionam pessoas singulares?", docs_personas, "lista_documentos")
docs_toneladas = buscar_en_contenido("tonelada")
add_q("conteudo_especifico", "Quais documentos fazem referência a toneladas?", docs_toneladas, "lista_documentos")
docs_cooperacion = buscar_en_contenido("cooperação")
add_q("conteudo_especifico", "Em quais documentos é mencionada a cooperação?", docs_cooperacion, "lista_documentos")
# ═══════════════════════════════════════════════
# CAT 11: DOCUMENTOS_CRUZADOS (requer Knowledge Graph)
# ═══════════════════════════════════════════════
# Estas perguntas REQUEREM sintetizar informações de 2+ documentos.
# Um RAG vetorial básico recupera chunks de forma independente e falha quando
# a resposta só pode ser construída relacionando fatos de múltiplos documentos.
_ref_to_docs = defaultdict(set)
for _d, _info in doc_info.items():
    for _ref in _info.get("refs", []):
        _ref_to_docs[_ref].add(_d)
_ref_ranking = sorted(_ref_to_docs.items(), key=lambda x: (-len(x[1]), x[0]))
if _ref_ranking and len(_ref_ranking[0][1]) >= 2:
    _top_ref, _top_docs = _ref_ranking[0]
    add_q("documentos_cruzados",
          f"liste TODOS os documentos do corpus que citam o regulamento {_top_ref}.",
          sorted(_top_docs), "lista_documentos")
if len(_ref_ranking) >= 2 and len(_ref_ranking[1][1]) >= 2:
    _ref2, _docs2 = _ref_ranking[1]
    add_q("documentos_cruzados",
          f"Quantos documentos do corpus fazem referência ao regulamento {_ref2}?",
          len(_docs2), "numero")
add_q("documentos_cruzados",
      "Quantos atos legislativos externos distintos são citados em todo o corpus?",
      len(_ref_to_docs), "numero")
_multi_cited = sorted(r for r, ds in _ref_to_docs.items() if len(ds) >= 2)
add_q("documentos_cruzados",
      "Quais regulamentos externos são citados por 2 ou mais documentos do corpus?",
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
    add_q("documentos_cruzados",
          f"Quais atos legislativos são citados TANTO pelo documento {doc_info[_d1]['codigo']} COMO pelo documento {doc_info[_d2]['codigo']}?",
          _common, "lista_referencias")
if _pair_shared_refs:
    _d1, _d2, _common = _pair_shared_refs[0]
    add_q("documentos_cruzados",
          "Qual par de documentos do corpus partilha mais referências cruzadas? Quantas partilham?",
          {"documento_1": doc_info[_d1]["codigo"], "documento_2": doc_info[_d2]["codigo"],
           "num_partilhadas": len(_common), "refs_partilhadas": _common}, "objeto")
_doc_codes = {info["codigo"]: d for d, info in doc_info.items() if info.get("codigo")}
_internal_refs = []
for _d, _info in doc_info.items():
    for _ref in _info.get("refs", []):
        if _ref in _doc_codes and _doc_codes[_ref] != _d:
            _internal_refs.append((_d, _doc_codes[_ref]))
if _internal_refs:
    _d1, _d2 = _internal_refs[0]
    add_q("documentos_cruzados",
          f"O documento {doc_info[_d1]['codigo']} cita outro documento que também está no nosso corpus. Identifique-o e descreva do que trata.",
          {"citante": doc_info[_d1]["codigo"], "citado": doc_info[_d2]["codigo"],
           "titulo_citado": doc_info[_d2]["titulo"][:200]}, "objeto")
_no_refs = sorted(d for d, info in doc_info.items() if not info.get("refs"))
add_q("documentos_cruzados",
      "Quais documentos do corpus não citam nenhum outro ato legislativo?",
      _no_refs, "lista_documentos")
_most_citing = sorted(doc_info.items(), key=lambda x: -len(x[1].get("refs", [])))[:3]
add_q("documentos_cruzados",
      "Quais são os 3 documentos que citam o maior número de regulamentos externos? Indique códigos e quantidades.",
      [{"documento": doc_info[_d]["codigo"], "num_referencias": len(_i.get("refs", []))} for _d, _i in _most_citing], "ranking")
_comision_docs = sorted(idx_organo.get("Comissão Europeia", []))
if _comision_docs:
    add_q("documentos_cruzados",
          "Entre os documentos emitidos pela Comissão Europeia, liste os seus códigos e datas.",
          [{"documento": _d, "codigo": doc_info[_d]["codigo"], "fecha": doc_info[_d]["fecha"]}
           for _d in _comision_docs], "ranking")
# ═══════════════════════════════════════════════
# FILTRO: REDUZIR A 80-100 PERGUNTAS
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
    if cat == "documentos_cruzados":
        _filtered[cat] = qs
    else:
        _filtered[cat] = _remove_similar(qs, "pregunta")
_total_f = sum(len(v) for k, v in _filtered.items() if k != "documentos_cruzados") or 1
_selected = []
for cat, qs in sorted(_filtered.items()):
    if cat == "documentos_cruzados":
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
print(f"\n→ Reduzido de {len(preguntas)} para {len(_selected)} perguntas (alvo: 80-100)")
preguntas = _selected
# ═══════════════════════════════════════════════
# VERIFICAÇÃO E EXPORTAÇÃO
# ═══════════════════════════════════════════════
texts = [q["pregunta"] for q in preguntas]
dupes = [t for t in texts if texts.count(t) > 1]
if dupes:
    print(f"\nAVISO: {len(set(dupes))} perguntas duplicadas:")
    for d in set(dupes):
        print(f"  - {d}")
else:
    print("\nOK Todas as perguntas são únicas")
print(f"Total de perguntas geradas: {len(preguntas)}")
cat_counts = Counter(q["categoria"] for q in preguntas)
print("\nDistribuição por categoria:")
for cat, cnt in sorted(cat_counts.items()):
    print(f"  {cat}: {cnt}")
gold_standard = {
    "gold_standard": {
        "caso_uso": "documentos_ue",
        "idioma": "pt",
        "total_preguntas": len(preguntas),
        "total_documentos_analizados": len(docs),
        "fecha_generacion": "2026-04-17",
        "categorias": dict(sorted(cat_counts.items())),
        "descripcion": "Gold standard para avaliar um sistema RAG sobre documentos do Jornal Oficial da UE "
                       "em português (regulamentos, decisões, retificações). Contém perguntas de identificação, "
                       "pesquisa por tipo, pesquisa por conteúdo, contagem, referências cruzadas, estrutura, "
                       "existência, listagem, relações e conteúdo específico. Inclui uma categoria "
                       "'documentos_cruzados' com perguntas multi-hop (referências partilhadas, cadeias de "
                       "citação, agregações multi-documento) desenhadas para expor as limitações do RAG "
                       "vetorial básico. Todas as respostas calculadas a partir dos dados.",
        "preguntas": preguntas
    }
}
output_path = OUTPUT_DIR / "gold_standard_eu_pt.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(gold_standard, f, ensure_ascii=False, indent=2)
print(f"\nOK Gold standard guardado em: {output_path}")
