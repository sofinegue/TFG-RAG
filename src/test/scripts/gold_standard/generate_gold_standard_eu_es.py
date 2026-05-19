"""
Script para generar el Gold Standard del caso de uso de documentos de la UE en español.
Genera 80-100 preguntas únicas con respuestas extraídas directamente de los documentos.
Estructura de datos: documentos del Diario Oficial de la UE (serie L) en formato JSON
  - archivo, idioma, num_paginas, contenido, paginas
Autor: Generado automáticamente para el TFG
Fecha: 2026-04-17
"""
import json
import re
import random
from collections import Counter, defaultdict
from pathlib import Path
random.seed(42)
# ─────────────────────────────────────────────
# 1. CARGAR TODOS LOS DOCUMENTOS
# ─────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[3]
EU_DIR = ROOT / "data" / "eu" / "es" / "json"
OUTPUT_DIR = ROOT / "src" / "test" / "gold_standard_data"
docs = {}
for f in sorted(EU_DIR.glob("*.json")):
    with open(f, encoding="utf-8") as fh:
        doc = json.load(fh)
        docs[doc["archivo"].replace(".pdf", "")] = doc
print(f"Cargados {len(docs)} documentos")
# ─────────────────────────────────────────────
# 2. ANALIZAR Y CONSTRUIR ÍNDICES
# ─────────────────────────────────────────────
# Extraer metadatos de cada documento
doc_info = {}
for doc_id, doc in docs.items():
    text = doc["contenido"][:3000]
    # Tipo de documento
    m = re.search(r'(REGLAMENTO|DECISIÓN|CORRECCIÓN|RECTIFICACIÓN|ACUERDO|DIRECTIVA)', text)
    tipo = m.group(1) if m else "OTRO"
    # Código del documento (ej. 2026/193)
    m_code = re.search(r'(\d{4}/\d+)\s', text)
    code = m_code.group(1) if m_code else doc_id
    # Título completo (primera línea significativa con el tipo)
    m_title = re.search(r'((?:REGLAMENTO|DECISIÓN|CORRECCIÓN|RECTIFICACIÓN|DIRECTIVA|ACUERDO)[\s\S]*?)(?:\n(?:LA COMISIÓN|EL CONSEJO|EL PARLAMENTO|Visto|\(Texto|\(Diario))', text)
    titulo = m_title.group(1).replace('\n', ' ').strip() if m_title else ""
    # Limpiar espacios múltiples
    titulo = re.sub(r'\s+', ' ', titulo)
    # Órgano emisor
    organos = []
    if "COMISIÓN" in text[:2000]:
        organos.append("Comisión Europea")
    if "CONSEJO" in text[:2000]:
        organos.append("Consejo")
    if "PARLAMENTO EUROPEO" in text[:2000]:
        organos.append("Parlamento Europeo")
    # Fecha del documento
    m_fecha = re.search(r'de\s+(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\s+(\d{4})', text)
    fecha = f"{m_fecha.group(1)} de {m_fecha.group(2)} de {m_fecha.group(3)}" if m_fecha else ""
    # Número de artículos
    articulos_found = re.findall(r'Artículo\s+(\d+)', text + doc["contenido"][3000:])
    num_articulos = max([int(a) for a in articulos_found]) if articulos_found else 0
    # Número de considerandos
    considerandos = re.findall(r'\((\d+)\)\s', doc["contenido"][:10000])
    num_considerandos = max([int(c) for c in considerandos]) if considerandos else 0
    # Buscar referencias a reglamentos/decisiones citados
    refs = re.findall(r'(?:Reglamento|Decisión|Directiva)\s+\([A-Z]+\)\s+(?:n\.o\s*)?(\d{4}/\d+)', doc["contenido"])
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
# Búsqueda en contenido
def buscar_en_contenido(keyword):
    result = []
    for doc_id, doc in docs.items():
        if keyword.lower() in doc["contenido"].lower():
            result.append(doc_id)
    return result
# Debug info
for doc_id, info in doc_info.items():
    print(f"  {doc_id}: {info['tipo']} | {info['fecha']} | {info['num_paginas']} págs | {info['num_articulos']} arts | orgs: {info['organos']}")
print(f"\nTipos: {dict(Counter(i['tipo'] for i in doc_info.values()))}")
print(f"Órganos: {dict(Counter(o for i in doc_info.values() for o in i['organos']))}")
# ─────────────────────────────────────────────
# 3. GENERAR PREGUNTAS
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
# CAT 1: IDENTIFICACIÓN DE DOCUMENTOS (25)
# ═══════════════════════════════════════════════
d, doc, info = next_doc()
add_q("identificacion", f"¿Qué tipo de documento es {info['codigo']}?", info["tipo"])
d, doc, info = next_doc()
add_q("identificacion", f"¿De qué trata el documento {info['codigo']}?", info["titulo"])
d, doc, info = next_doc()
add_q("identificacion", f"¿Quién emitió el documento {info['codigo']}?", info["organos"], "lista")
d, doc, info = next_doc()
add_q("identificacion", f"¿Cuál es la fecha del documento {info['codigo']}?", info["fecha"])
d, doc, info = next_doc()
add_q("identificacion", f"Dame el título completo del documento {d}.", info["titulo"])
d, doc, info = next_doc()
add_q("identificacion", f"¿Qué institución europea es responsable del documento {info['codigo']}?", info["organos"], "lista")
d, doc, info = next_doc()
add_q("identificacion", f"Identifica el tipo y la fecha del documento {info['codigo']}.", {"tipo": info["tipo"], "fecha": info["fecha"]}, "objeto")
d, doc, info = next_doc()
add_q("identificacion", f"¿Cuántas páginas tiene el documento {info['codigo']}?", info["num_paginas"], "numero")
d, doc, info = next_doc()
add_q("identificacion", f"Resume en una frase el contenido del documento {d}.", info["titulo"])
d, doc, info = next_doc()
add_q("identificacion", f"¿A qué se refiere el documento número {info['codigo']}?", info["titulo"])
d, doc, info = next_doc()
add_q("identificacion", f"¿Cuántos artículos contiene el documento {info['codigo']}?", info["num_articulos"], "numero")
d, doc, info = next_doc()
add_q("identificacion", f"Proporciona los metadatos principales del documento {d}.",
      {"tipo": info["tipo"], "fecha": info["fecha"], "organos": info["organos"], "paginas": info["num_paginas"]}, "objeto")
d, doc, info = next_doc()
add_q("identificacion", f"¿Cuál es el contenido del documento con código {info['codigo']}?", info["titulo"])
d, doc, info = next_doc()
add_q("identificacion", f"¿Qué organismo aprobó el documento {info['codigo']}?", info["organos"], "lista")
d, doc, info = next_doc()
add_q("identificacion", f"Necesito saber de qué trata {d}. ¿Cuál es su tema principal?", info["titulo"])
d, doc, info = next_doc()
add_q("identificacion", f"¿En qué fecha fue adoptado el documento {info['codigo']}?", info["fecha"])
d, doc, info = next_doc()
add_q("identificacion", f"Describe brevemente el objeto del documento {info['codigo']}.", info["titulo"])
d, doc, info = next_doc()
add_q("identificacion", f"¿Cuántos considerandos tiene el documento {info['codigo']}?", info["num_considerandos"], "numero")
# Los que quedan del iterador
remaining = list(d_iter)
if remaining:
    d = remaining[0]
    info = doc_info[d]
    add_q("identificacion", f"¿Cuántas palabras tiene aproximadamente el documento {info['codigo']}?", info["num_palabras"], "numero")
# Preguntas sobre documentos específicos con referencia al archivo
for i, d in enumerate(list(doc_info.keys())[:6]):
    info = doc_info[d]
    templates = [
        f"¿El documento {d} es un reglamento o una decisión?",
        f"¿Cuántas páginas tiene el archivo {d}?",
        f"Indica la fecha de aprobación de {d}.",
        f"¿Qué instituciones participaron en la elaboración de {d}?",
        f"Dame un resumen del documento {d}.",
        f"¿Cuál es el código numérico del documento contenido en {d}?",
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
    add_q("identificacion", templates[i], respuestas[i], tipos[i])
# ═══════════════════════════════════════════════
# CAT 2: BÚSQUEDA POR TIPO DE DOCUMENTO (15)
# ═══════════════════════════════════════════════
add_q("busqueda_por_tipo", "¿Cuántos reglamentos hay en la base de datos?", len(idx_tipo.get("REGLAMENTO", [])), "numero")
add_q("busqueda_por_tipo", "¿Cuántas decisiones contiene la colección?", len(idx_tipo.get("DECISIÓN", [])), "numero")
add_q("busqueda_por_tipo", "lista todos los reglamentos disponibles.", idx_tipo.get("REGLAMENTO", []), "lista_documentos")
add_q("busqueda_por_tipo", "Dame todas las decisiones de la base de datos.", idx_tipo.get("DECISIÓN", []), "lista_documentos")
add_q("busqueda_por_tipo", "¿Qué tipos de documentos legislativos tenemos?", sorted(set(i["tipo"] for i in doc_info.values())), "lista")
add_q("busqueda_por_tipo", "¿Hay algún documento de tipo corrección de errores?",
      {"existe": "CORRECCIÓN" in idx_tipo or any("Corrección" in docs[d]["contenido"][:500] for d in docs),
       "documentos": idx_tipo.get("CORRECCIÓN", []) + [d for d in docs if "Corrección" in docs[d]["contenido"][:500]]}, "booleano")
add_q("busqueda_por_tipo", "Filtra los documentos que sean reglamentos de ejecución.",
      [d for d in docs if "REGLAMENTO DE EJECUCIÓN" in docs[d]["contenido"][:1000] or "REGLAMENTO DE EJECUCIÓN" in docs[d]["contenido"][:1000].upper()], "lista_documentos")
add_q("busqueda_por_tipo", "¿Cuáles son los documentos emitidos por la Comisión Europea?", idx_organo.get("Comisión Europea", []), "lista_documentos")
add_q("busqueda_por_tipo", "¿Qué documentos fueron aprobados por el Consejo?", idx_organo.get("Consejo", []), "lista_documentos")
add_q("busqueda_por_tipo", "¿Hay documentos del Parlamento Europeo?", idx_organo.get("Parlamento Europeo", []), "lista_documentos")
add_q("busqueda_por_tipo", "¿Cuántos documentos emitió la Comisión Europea?", len(idx_organo.get("Comisión Europea", [])), "numero")
add_q("busqueda_por_tipo", "¿Qué documentos de 2026 tenemos?",
      [d for d, i in doc_info.items() if "2026" in i["fecha"]], "lista_documentos")
add_q("busqueda_por_tipo", "¿Cuáles son los documentos de 2025?",
      [d for d, i in doc_info.items() if "2025" in i["fecha"]], "lista_documentos")
add_q("busqueda_por_tipo", "Busca documentos que contengan decisiones de ejecución.",
      [d for d in docs if "DECISIÓN DE EJECUCIÓN" in docs[d]["contenido"][:1000]], "lista_documentos")
add_q("busqueda_por_tipo", "¿Qué documentos son reglamentos delegados?",
      [d for d in docs if "REGLAMENTO DELEGADO" in docs[d]["contenido"][:1000]], "lista_documentos")
# ═══════════════════════════════════════════════
# CAT 3: BÚSQUEDA POR CONTENIDO / TEMÁTICA (30)
# ═══════════════════════════════════════════════
temas = [
    ("pesca", "¿Qué documentos tratan sobre pesca?"),
    ("productos sanitarios", "¿Cuáles documentos se refieren a productos sanitarios?"),
    ("Marruecos", "¿En qué documentos se menciona a Marruecos?"),
    ("medidas restrictivas", "lista los documentos que traten sobre medidas restrictivas."),
    ("normas armonizadas", "¿Qué documentos hacen referencia a normas armonizadas?"),
    ("posibilidades de pesca", "¿Cuáles documentos regulan las posibilidades de pesca?"),
    ("plaguicidas", "¿Hay documentos que mencionen plaguicidas o residuos de plaguicidas?"),
    ("Reglamento (UE) 2017/745", "¿Qué documentos hacen referencia al Reglamento (UE) 2017/745?"),
    ("peste porcina", "¿Existen documentos sobre la peste porcina?"),
    ("influenza aviar", "¿Qué documentos mencionan la influenza aviar o gripe aviar?"),
    ("sustancias de origen humano", "¿Hay algún documento sobre sustancias de origen humano?"),
    ("indicación geográfica", "¿Qué documentos tratan sobre indicaciones geográficas?"),
    ("Fondo Europeo", "¿Cuáles documentos hacen referencia a un Fondo Europeo?"),
    ("Túnez", "¿Se menciona a Túnez en alguno de los documentos?"),
    ("Euromediterráneo", "¿Qué documentos hacen referencia al acuerdo Euromediterráneo?"),
    ("esterilización", "¿Hay documentos sobre esterilización de productos?"),
    ("Atlántico", "¿Qué documentos mencionan el Atlántico?"),
    ("Mediterráneo", "lista los documentos que se refieran al Mediterráneo."),
    ("Consejo de Asociación", "¿Qué documentos mencionan un Consejo de Asociación?"),
    ("anexo", "¿Cuáles documentos contienen o modifican anexos?"),
    ("importación", "¿Qué documentos tratan sobre importaciones?"),
    ("PESC", "¿Hay documentos relacionados con la Política Exterior y de Seguridad Común (PESC)?"),
    ("sanciones", "¿Qué documentos hacen referencia a sanciones?"),
    ("seguridad alimentaria", "¿Existen documentos sobre seguridad alimentaria?"),
    ("Diario Oficial", "¿En cuántos documentos se hace referencia al Diario Oficial?"),
    ("Miel", "¿Hay algún documento que mencione la miel?"),
    ("terceros países", "¿Qué documentos hacen referencia a terceros países?"),
    ("biocompatibilidad", "¿Se menciona la biocompatibilidad en algún documento?"),
    ("Báltico", "¿Qué documentos hacen referencia al mar Báltico?"),
    ("residuos", "lista los documentos que contengan la palabra residuos."),
]
for kw, pregunta in temas:
    r = buscar_en_contenido(kw)
    add_q("busqueda_por_contenido", pregunta, r, "lista_documentos")
# ═══════════════════════════════════════════════
# CAT 4: CONTEO Y ESTADÍSTICAS (25)
# ═══════════════════════════════════════════════
add_q("conteo", "¿Cuántos documentos hay en total en la base de datos?", len(docs), "numero")
add_q("conteo", "¿Cuántas páginas suman todos los documentos juntos?",
      sum(d["num_paginas"] for d in docs.values()), "numero")
add_q("conteo", "¿Cuál es el documento más largo en número de páginas?",
      {"documento": max(doc_info.items(), key=lambda x: x[1]["num_paginas"])[0],
       "paginas": max(i["num_paginas"] for i in doc_info.values())}, "objeto")
add_q("conteo", "¿Cuál es el documento más corto?",
      {"documento": min(doc_info.items(), key=lambda x: x[1]["num_paginas"])[0],
       "paginas": min(i["num_paginas"] for i in doc_info.values())}, "objeto")
add_q("conteo", "¿Cuántas palabras hay en total en todos los documentos?",
      sum(i["num_palabras"] for i in doc_info.values()), "numero")
avg_pags = round(sum(i["num_paginas"] for i in doc_info.values()) / len(doc_info), 1)
add_q("conteo", "¿Cuál es la media de páginas por documento?", avg_pags, "numero")
avg_words = round(sum(i["num_palabras"] for i in doc_info.values()) / len(doc_info), 1)
add_q("conteo", "¿Cuál es el promedio de palabras por documento?", avg_words, "numero")
add_q("conteo", "¿Cuántos documentos tienen más de 50 páginas?",
      len([d for d, i in doc_info.items() if i["num_paginas"] > 50]), "numero")
add_q("conteo", "¿Cuántos documentos tienen menos de 10 páginas?",
      len([d for d, i in doc_info.items() if i["num_paginas"] < 10]), "numero")
top5 = sorted(doc_info.items(), key=lambda x: -x[1]["num_paginas"])[:5]
add_q("conteo", "¿Cuáles son los 5 documentos más extensos?",
      [{"documento": d, "paginas": i["num_paginas"]} for d, i in top5], "ranking")
bot5 = sorted(doc_info.items(), key=lambda x: x[1]["num_paginas"])[:5]
add_q("conteo", "¿Cuáles son los 5 documentos más breves?",
      [{"documento": d, "paginas": i["num_paginas"]} for d, i in bot5], "ranking")
add_q("conteo", "¿Cuántos tipos diferentes de documentos existen?",
      len(set(i["tipo"] for i in doc_info.values())), "numero")
tipo_counts = Counter(i["tipo"] for i in doc_info.values())
add_q("conteo", "¿Cuál es la distribución de documentos por tipo?",
      [{"tipo": t, "cantidad": c} for t, c in tipo_counts.most_common()], "ranking")
add_q("conteo", "¿Cuántos documentos mencionan la palabra 'pesca'?",
      len(buscar_en_contenido("pesca")), "numero")
add_q("conteo", "¿Cuántos documentos contienen artículos numerados?",
      len([d for d, i in doc_info.items() if i["num_articulos"] > 0]), "numero")
max_arts = max(doc_info.items(), key=lambda x: x[1]["num_articulos"])
add_q("conteo", "¿Qué documento tiene más artículos?",
      {"documento": max_arts[0], "num_articulos": max_arts[1]["num_articulos"]}, "objeto")
add_q("conteo", "¿Cuántos documentos fueron emitidos en enero de 2026?",
      len([d for d, i in doc_info.items() if "enero de 2026" in i["fecha"]]), "numero")
add_q("conteo", "¿Cuántos documentos fueron emitidos en diciembre de 2025?",
      len([d for d, i in doc_info.items() if "diciembre de 2025" in i["fecha"]]), "numero")
add_q("conteo", "¿Cuántos documentos mencionan sanciones o medidas restrictivas?",
      len(set(buscar_en_contenido("sanciones") + buscar_en_contenido("medidas restrictivas"))), "numero")
add_q("conteo", "¿Cuántos documentos hacen referencia a otros reglamentos de la UE?",
      len([d for d, i in doc_info.items() if len(i["refs"]) > 0]), "numero")
total_refs = sum(len(i["refs"]) for i in doc_info.values())
add_q("conteo", "¿Cuántas referencias cruzadas a otros documentos hay en total?", total_refs, "numero")
add_q("conteo", "¿Cuántos documentos superan las 100 páginas?",
      len([d for d, i in doc_info.items() if i["num_paginas"] > 100]), "numero")
add_q("conteo", "¿Cuántos caracteres tiene el documento más largo?",
      max(i["num_chars"] for i in doc_info.values()), "numero")
add_q("conteo", "¿Cuántos documentos contienen la palabra 'Reglamento'?",
      len(buscar_en_contenido("Reglamento")), "numero")
# ═══════════════════════════════════════════════
# CAT 5: REFERENCIAS CRUZADAS (20)
# ═══════════════════════════════════════════════
# Documentos que referencian a otros
docs_con_refs = [(d, i) for d, i in doc_info.items() if len(i["refs"]) >= 2]
random.shuffle(docs_con_refs)
ref_iter = iter(docs_con_refs)
for template in [
    "¿A qué otros reglamentos o decisiones hace referencia el documento {}?",
    "lista las normas citadas en el documento {}.",
    "¿Qué legislación previa menciona el documento {}?",
    "¿Cuáles son las referencias normativas del documento {}?",
    "Dame las referencias a otros actos legislativos que aparecen en {}.",
    "¿Qué reglamentos modifica o cita el documento {}?",
    "Identifica las normas de la UE referenciadas en {}.",
    "¿Con qué otra legislación está relacionado el documento {}?",
    "Enumera los reglamentos y decisiones citados en {}.",
    "¿Qué base jurídica se menciona en el documento {}?",
]:
    try:
        d, i = next(ref_iter)
        add_q("referencias_cruzadas", template.format(i["codigo"]), i["refs"], "lista_referencias")
    except StopIteration:
        break
# Documentos que comparten referencias
all_refs = defaultdict(list)
for d, i in doc_info.items():
    for r in i["refs"]:
        all_refs[r].append(d)
shared_refs = [(r, ds) for r, ds in all_refs.items() if len(ds) >= 2]
random.shuffle(shared_refs)
for template in [
    "¿Qué documentos hacen referencia al {}?",
    "¿Cuáles documentos citan el {}?",
    "lista los documentos que mencionan el {}.",
    "¿En cuántos documentos se referencia el {}?",
    "¿Qué documentos están relacionados con el {}?",
]:
    if shared_refs:
        ref, ds = shared_refs.pop()
        ref_name = f"Reglamento/Decisión {ref}"
        add_q("referencias_cruzadas", template.format(ref_name), ds, "lista_documentos")
# Referencias individuales
for d, i in list(doc_info.items())[:5]:
    if i["refs"]:
        add_q("referencias_cruzadas", f"¿Cuántas referencias a otros actos contiene el documento {i['codigo']}?",
              len(i["refs"]), "numero")
# ═══════════════════════════════════════════════
# CAT 6: ESTRUCTURA DE LOS DOCUMENTOS (20)
# ═══════════════════════════════════════════════
for d, i in list(doc_info.items()):
    if i["num_articulos"] > 0:
        break
d_art = d
info_art = doc_info[d_art]
add_q("estructura", f"¿Cuántos artículos tiene el documento {info_art['codigo']}?", info_art["num_articulos"], "numero")
# Buscar artículos con considerandos
docs_con_consid = [(d, i) for d, i in doc_info.items() if i["num_considerandos"] > 0]
random.shuffle(docs_con_consid)
for idx, template in enumerate([
    "¿Cuántos considerandos tiene el documento {}?",
    "¿Con cuántos considerandos cuenta la exposición de motivos de {}?",
    "Indica el número de considerandos del documento {}.",
    "¿Cuántos puntos tiene la parte considerativa de {}?",
    "Dame el número total de considerandos de {}.",
]):
    if idx < len(docs_con_consid):
        d, i = docs_con_consid[idx]
        add_q("estructura", template.format(i["codigo"]), i["num_considerandos"], "numero")
# Documentos con anexos
docs_con_anexo = buscar_en_contenido("ANEXO")
add_q("estructura", "¿Qué documentos contienen anexos?", docs_con_anexo, "lista_documentos")
add_q("estructura", "¿Cuántos documentos incluyen anexos?", len(docs_con_anexo), "numero")
# Documentos con tablas
docs_con_tabla = buscar_en_contenido("cuadro")
add_q("estructura", "¿Qué documentos contienen cuadros o tablas?", docs_con_tabla, "lista_documentos")
# Estructura de artículos por documento
arts_por_doc = sorted([(d, i["num_articulos"]) for d, i in doc_info.items() if i["num_articulos"] > 0],
                      key=lambda x: -x[1])
add_q("estructura", "¿Cuáles documentos tienen artículos y cuántos tienen cada uno?",
      [{"documento": d, "num_articulos": n} for d, n in arts_por_doc], "ranking")
# Páginas de documentos
add_q("estructura", "lista todos los documentos ordenados por número de páginas de mayor a menor.",
      [{"documento": d, "paginas": i["num_paginas"]} for d, i in sorted(doc_info.items(), key=lambda x: -x[1]["num_paginas"])], "ranking")
# Documentos con fórmulas / datos numéricos
docs_con_porcentaje = buscar_en_contenido("%")
add_q("estructura", "¿Cuáles documentos contienen datos porcentuales?", docs_con_porcentaje, "lista_documentos")
# Documentos con fechas de aplicación
docs_con_aplicacion = buscar_en_contenido("será aplicable a partir")
add_q("estructura", "¿Qué documentos especifican una fecha de aplicación?", docs_con_aplicacion, "lista_documentos")
# Documentos con disposiciones transitorias
docs_transitorio = buscar_en_contenido("disposiciones transitorias")
if not docs_transitorio:
    docs_transitorio = buscar_en_contenido("transitoria")
add_q("estructura", "¿Hay documentos con disposiciones transitorias?", docs_transitorio, "lista_documentos")
# Documentos vinculantes
docs_obligatorio = buscar_en_contenido("obligatorio en todos sus elementos")
add_q("estructura", "¿Qué documentos declaran ser obligatorios en todos sus elementos?", docs_obligatorio, "lista_documentos")
# Vista rápida de todos los documentos
all_docs_summary = [{"documento": d, "tipo": i["tipo"], "fecha": i["fecha"], "paginas": i["num_paginas"]}
                    for d, i in sorted(doc_info.items())]
add_q("estructura", "Dame una vista general de todos los documentos con su tipo, fecha y número de páginas.", all_docs_summary, "tabla")
# ═══════════════════════════════════════════════
# CAT 7: EXISTENCIA Y VERIFICACIÓN (20)
# ═══════════════════════════════════════════════
add_q("existencia", "¿Hay algún documento sobre pesca en el Atlántico?",
      {"existe": len(set(buscar_en_contenido("pesca") + []) & set(buscar_en_contenido("Atlántico"))) > 0,
       "documentos": sorted(set(buscar_en_contenido("pesca")) & set(buscar_en_contenido("Atlántico")))}, "booleano")
add_q("existencia", "¿Existe algún reglamento de ejecución en la base de datos?",
      {"existe": len([d for d in docs if "REGLAMENTO DE EJECUCIÓN" in docs[d]["contenido"][:1000]]) > 0,
       "documentos": [d for d in docs if "REGLAMENTO DE EJECUCIÓN" in docs[d]["contenido"][:1000]]}, "booleano")
add_q("existencia", "¿Hay documentos que traten sobre Ucrania?",
      {"existe": len(buscar_en_contenido("Ucrania")) > 0, "documentos": buscar_en_contenido("Ucrania")}, "booleano")
add_q("existencia", "¿Se menciona a Rusia en algún documento?",
      {"existe": len(buscar_en_contenido("Rusia")) > 0, "documentos": buscar_en_contenido("Rusia")}, "booleano")
add_q("existencia", "¿Hay algún documento sobre inteligencia artificial?",
      {"existe": len(buscar_en_contenido("inteligencia artificial")) > 0, "documentos": buscar_en_contenido("inteligencia artificial")}, "booleano")
add_q("existencia", "¿Existen documentos sobre cambio climático?",
      {"existe": len(buscar_en_contenido("cambio climático")) > 0, "documentos": buscar_en_contenido("cambio climático")}, "booleano")
add_q("existencia", "¿Hay documentos relativos a derechos humanos?",
      {"existe": len(buscar_en_contenido("derechos humanos")) > 0, "documentos": buscar_en_contenido("derechos humanos")}, "booleano")
add_q("existencia", "¿Se menciona a China en algún documento?",
      {"existe": len(buscar_en_contenido("China")) > 0, "documentos": buscar_en_contenido("China")}, "booleano")
add_q("existencia", "¿Hay documentos sobre política agrícola?",
      {"existe": len(buscar_en_contenido("agrícola")) > 0, "documentos": buscar_en_contenido("agrícola")}, "booleano")
add_q("existencia", "¿Existe algún documento que mencione el euro?",
      {"existe": len(buscar_en_contenido("euro")) > 0, "documentos": buscar_en_contenido("euro")}, "booleano")
add_q("existencia", "¿Se hace referencia a la OTAN en algún documento?",
      {"existe": len(buscar_en_contenido("OTAN")) > 0, "documentos": buscar_en_contenido("OTAN")}, "booleano")
add_q("existencia", "¿Hay documentos sobre protección de datos?",
      {"existe": len(buscar_en_contenido("protección de datos")) > 0, "documentos": buscar_en_contenido("protección de datos")}, "booleano")
add_q("existencia", "¿Existe algún documento sobre transporte?",
      {"existe": len(buscar_en_contenido("transporte")) > 0, "documentos": buscar_en_contenido("transporte")}, "booleano")
add_q("existencia", "¿Se menciona a Siria en alguno de los documentos?",
      {"existe": len(buscar_en_contenido("Siria")) > 0, "documentos": buscar_en_contenido("Siria")}, "booleano")
add_q("existencia", "¿Hay documentos que traten sobre energía?",
      {"existe": len(buscar_en_contenido("energía")) > 0, "documentos": buscar_en_contenido("energía")}, "booleano")
add_q("existencia", "¿Existe algún documento relativo al Espacio Económico Europeo (EEE)?",
      {"existe": len(buscar_en_contenido("EEE")) > 0, "documentos": buscar_en_contenido("EEE")}, "booleano")
add_q("existencia", "¿Se hace mención a Bielorrusia en algún documento?",
      {"existe": len(buscar_en_contenido("Bielorrusia")) > 0, "documentos": buscar_en_contenido("Bielorrusia")}, "booleano")
add_q("existencia", "¿Hay algún documento sobre aduanas o aranceles?",
      {"existe": len(set(buscar_en_contenido("aduana") + buscar_en_contenido("arancel"))) > 0,
       "documentos": sorted(set(buscar_en_contenido("aduana") + buscar_en_contenido("arancel")))}, "booleano")
add_q("existencia", "¿Existe algún documento sobre medicamentos?",
      {"existe": len(buscar_en_contenido("medicamento")) > 0, "documentos": buscar_en_contenido("medicamento")}, "booleano")
add_q("existencia", "¿Hay algún documento que mencione la denominación de origen protegida (DOP)?",
      {"existe": len(buscar_en_contenido("DOP")) > 0, "documentos": buscar_en_contenido("DOP")}, "booleano")
# ═══════════════════════════════════════════════
# CAT 8: LISTADO Y CATÁLOGO (15)
# ═══════════════════════════════════════════════
add_q("listado", "Dame la lista completa de todos los documentos disponibles.", sorted(docs.keys()), "lista_documentos")
add_q("listado", "¿Cuáles son todos los documentos de la base de datos?", sorted(docs.keys()), "lista_documentos")
add_q("listado", "Enumera todos los documentos que tenemos en la colección.", sorted(docs.keys()), "lista_documentos")
add_q("listado", "Necesito ver el catálogo completo de documentos de la UE.", sorted(docs.keys()), "lista_documentos")
add_q("listado", "Muéstrame una lista de todos los documentos del Diario Oficial disponibles.", sorted(docs.keys()), "lista_documentos")
# Por órgano
for org in sorted(idx_organo.keys()):
    add_q("listado", f"lista todos los documentos emitidos por {org}.", sorted(idx_organo[org]), "lista_documentos")
# Por tipo
for tipo in sorted(idx_tipo.keys()):
    add_q("listado", f"lista todos los documentos de tipo {tipo}.", sorted(idx_tipo[tipo]), "lista_documentos")
# Documentos por año
docs_2025 = sorted([d for d, i in doc_info.items() if "2025" in i["fecha"]])
docs_2026 = sorted([d for d, i in doc_info.items() if "2026" in i["fecha"]])
add_q("listado", "¿Cuáles documentos son del año 2025?", docs_2025, "lista_documentos")
add_q("listado", "¿Cuáles documentos corresponden al año 2026?", docs_2026, "lista_documentos")
# ═══════════════════════════════════════════════
# CAT 9: COMPARACIONES Y RELACIONES (30)
# ═══════════════════════════════════════════════
# Comparar longitud
d_max = max(doc_info.items(), key=lambda x: x[1]["num_paginas"])
d_min = min(doc_info.items(), key=lambda x: x[1]["num_paginas"])
add_q("relaciones", "¿Cuál es el documento más largo y cuál el más corto?",
      {"mas_largo": {"documento": d_max[0], "paginas": d_max[1]["num_paginas"]},
       "mas_corto": {"documento": d_min[0], "paginas": d_min[1]["num_paginas"]}}, "objeto")
add_q("relaciones", "¿Cuántas veces más largo es el documento más extenso respecto al más breve?",
      round(d_max[1]["num_paginas"] / d_min[1]["num_paginas"], 1), "numero")
# Documentos sobre temas comunes
pesca_docs = set(buscar_en_contenido("pesca"))
sanitarios_docs = set(buscar_en_contenido("sanitario"))
add_q("relaciones", "¿Hay documentos que traten simultáneamente de pesca y temas sanitarios?",
      sorted(pesca_docs & sanitarios_docs), "lista_documentos")
# Documentos con más referencias
top_refs = sorted(doc_info.items(), key=lambda x: -len(x[1]["refs"]))[:5]
add_q("relaciones", "¿Cuáles son los 5 documentos con más referencias a otros actos legislativos?",
      [{"documento": d, "num_referencias": len(i["refs"])} for d, i in top_refs], "ranking")
# Países mencionados
paises = ["España", "Francia", "Alemania", "Italia", "Portugal", "Grecia", "Marruecos", "Túnez", "Noruega", "Islandia"]
for pais in paises:
    docs_pais = buscar_en_contenido(pais)
    add_q("relaciones", f"¿En qué documentos se menciona {pais}?", docs_pais, "lista_documentos")
# Documentos que comparten órgano emisor
add_q("relaciones", "¿Qué documentos fueron emitidos conjuntamente por el Parlamento Europeo y el Consejo?",
      sorted(set(idx_organo.get("Parlamento Europeo", [])) & set(idx_organo.get("Consejo", []))), "lista_documentos")
# Agrupación temática
add_q("relaciones", "¿Qué documentos están relacionados con la salud o sanidad?",
      sorted(set(buscar_en_contenido("sanitario") + buscar_en_contenido("salud") + buscar_en_contenido("medicamento"))), "lista_documentos")
add_q("relaciones", "¿Qué documentos tratan sobre comercio internacional o relaciones exteriores?",
      sorted(set(buscar_en_contenido("comercio") + buscar_en_contenido("relaciones exteriores") + buscar_en_contenido("acuerdo comercial"))), "lista_documentos")
# Documentos con disposiciones finales
docs_disposiciones = buscar_en_contenido("entrará en vigor")
add_q("relaciones", "¿Qué documentos contienen disposiciones sobre entrada en vigor?", docs_disposiciones, "lista_documentos")
# Comparar documentos del mismo tipo
regs = idx_tipo.get("REGLAMENTO", [])
if len(regs) >= 2:
    r1, r2 = regs[0], regs[1]
    add_q("relaciones", f"Compara los documentos {doc_info[r1]['codigo']} y {doc_info[r2]['codigo']}: ¿qué tienen en común?",
          {"tipo_comun": "REGLAMENTO",
           "doc1": {"codigo": doc_info[r1]["codigo"], "fecha": doc_info[r1]["fecha"], "paginas": doc_info[r1]["num_paginas"]},
           "doc2": {"codigo": doc_info[r2]["codigo"], "fecha": doc_info[r2]["fecha"], "paginas": doc_info[r2]["num_paginas"]}}, "objeto")
# Documentos más recientes
docs_por_fecha = sorted(doc_info.items(), key=lambda x: x[1]["fecha"], reverse=True)
add_q("relaciones", "¿Cuáles son los documentos más recientes?",
      [{"documento": d, "fecha": i["fecha"]} for d, i in docs_por_fecha[:5]], "ranking")
# Documentos sobre seguridad
docs_seguridad = sorted(set(buscar_en_contenido("seguridad") + buscar_en_contenido("defensa")))
add_q("relaciones", "¿Qué documentos tratan temas de seguridad o defensa?", docs_seguridad, "lista_documentos")
# Documentos sobre medio ambiente
docs_ambiente = sorted(set(buscar_en_contenido("medio ambiente") + buscar_en_contenido("medioambiental") + buscar_en_contenido("ambiental")))
add_q("relaciones", "¿Hay documentos relacionados con el medio ambiente?", docs_ambiente, "lista_documentos")
# Documentos con más artículos
top_arts = sorted(doc_info.items(), key=lambda x: -x[1]["num_articulos"])[:5]
add_q("relaciones", "¿Cuáles son los 5 documentos con más artículos?",
      [{"documento": d, "num_articulos": i["num_articulos"]} for d, i in top_arts], "ranking")
# Documentos según mes
meses = Counter()
for d, i in doc_info.items():
    m = re.search(r'de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)', i["fecha"])
    if m:
        meses[m.group(1)] += 1
add_q("relaciones", "¿Cómo se distribuyen los documentos por mes de emisión?",
      [{"mes": m, "cantidad": c} for m, c in meses.most_common()], "ranking")
# ═══════════════════════════════════════════════
# CAT 10: CONTENIDO ESPECÍFICO / DETALLE (25)
# ═══════════════════════════════════════════════
# Buscar artículos específicos dentro de documentos
for d_id in list(doc_info.keys())[:8]:
    text = docs[d_id]["contenido"]
    info = doc_info[d_id]
    if info["num_articulos"] >= 2:
        # Extraer texto del Artículo 1
        m_art1 = re.search(r'Artículo\s+1\s*\n([\s\S]*?)(?:Artículo\s+2|\Z)', text)
        if m_art1:
            art1_text = m_art1.group(1).strip()[:500]
            art1_text = re.sub(r'\s+', ' ', art1_text)
            add_q("contenido_especifico",
                  f"¿Cuál es el contenido del Artículo 1 del documento {info['codigo']}?",
                  art1_text, "texto_largo")
            break
# Preguntas sobre contenido de páginas específicas
for d_id in list(doc_info.keys()):
    if doc_info[d_id]["num_paginas"] >= 3:
        pag2 = docs[d_id]["paginas"][1][:300] if len(docs[d_id]["paginas"]) > 1 else ""
        if pag2.strip():
            pag2_clean = re.sub(r'\s+', ' ', pag2).strip()
            add_q("contenido_especifico",
                  f"¿Qué información aparece en la página 2 del documento {doc_info[d_id]['codigo']}?",
                  pag2_clean, "texto_largo")
            break
# Fechas de entrada en vigor
docs_vigor = []
for d_id, doc in docs.items():
    m = re.search(r'entrará en vigor\s+(?:el\s+)?(.+?)(?:\.|$)', doc["contenido"])
    if m:
        docs_vigor.append({"documento": d_id, "entrada_en_vigor": m.group(1).strip()[:100]})
if docs_vigor:
    add_q("contenido_especifico", "¿Cuáles documentos especifican su fecha de entrada en vigor y cuándo es?",
          docs_vigor, "lista_detallada")
# Preguntas sobre ámbito de aplicación
docs_ambito = []
for d_id, doc in docs.items():
    m = re.search(r'(?:ámbito de aplicación|se aplica a|será aplicable)[\s:]*(.{50,300})', doc["contenido"], re.IGNORECASE)
    if m:
        docs_ambito.append(d_id)
add_q("contenido_especifico", "¿Qué documentos definen su ámbito de aplicación?", docs_ambito, "lista_documentos")
# Preguntas sobre definiciones
docs_definiciones = buscar_en_contenido("definiciones")
add_q("contenido_especifico", "¿Qué documentos contienen una sección de definiciones?", docs_definiciones, "lista_documentos")
# Preguntas sobre derogaciones
docs_deroga = buscar_en_contenido("queda derogad")
add_q("contenido_especifico", "¿Qué documentos contienen cláusulas de derogación?", docs_deroga, "lista_documentos")
# Documentos que modifican otros
docs_modifica = buscar_en_contenido("se modifica")
add_q("contenido_especifico", "¿Cuáles documentos modifican legislación preexistente?", docs_modifica, "lista_documentos")
# Documentos con disposiciones sobre comités
docs_comite = buscar_en_contenido("comité")
add_q("contenido_especifico", "¿En qué documentos se hace referencia a comités?", docs_comite, "lista_documentos")
# Destinatarios
docs_destinatarios = buscar_en_contenido("destinatarios")
if not docs_destinatarios:
    docs_destinatarios = buscar_en_contenido("Estados miembros son los destinatarios")
add_q("contenido_especifico", "¿Qué documentos mencionan a sus destinatarios?", docs_destinatarios, "lista_documentos")
# Bases jurídicas
docs_tratado = buscar_en_contenido("Tratado de Funcionamiento")
add_q("contenido_especifico", "¿Cuáles documentos se basan en el Tratado de Funcionamiento de la Unión Europea?",
      docs_tratado, "lista_documentos")
# Documentos sobre estados miembros específicos
docs_españa = buscar_en_contenido("España")
add_q("contenido_especifico", "¿En qué documentos se menciona a España?", docs_españa, "lista_documentos")
# Sobre especies
docs_especies = buscar_en_contenido("especies")
add_q("contenido_especifico", "¿Qué documentos hacen referencia a especies animales o vegetales?", docs_especies, "lista_documentos")
# Sobre cuotas
docs_cuotas = buscar_en_contenido("cuota")
add_q("contenido_especifico", "¿Qué documentos mencionan cuotas?", docs_cuotas, "lista_documentos")
# Sobre sanciones en detalle
docs_sancion_det = buscar_en_contenido("congelación de activos")
add_q("contenido_especifico", "¿Qué documentos mencionan la congelación de activos?", docs_sancion_det, "lista_documentos")
# Sobre plazos
docs_plazos = buscar_en_contenido("plazo")
add_q("contenido_especifico", "¿En cuáles documentos se establecen plazos?", docs_plazos, "lista_documentos")
# Sobre publicación en el Diario Oficial
docs_publicacion = buscar_en_contenido("publicación en el Diario Oficial")
add_q("contenido_especifico", "¿Qué documentos mencionan su publicación en el Diario Oficial?", docs_publicacion, "lista_documentos")
# Sobre consultas o dictámenes
docs_dictamen = buscar_en_contenido("dictamen")
add_q("contenido_especifico", "¿Qué documentos hacen referencia a dictámenes?", docs_dictamen, "lista_documentos")
# Sobre Estados miembros
docs_eemm = buscar_en_contenido("Estados miembros")
add_q("contenido_especifico", "¿Cuántos documentos hacen referencia a los Estados miembros?",
      len(docs_eemm), "numero")
# Sobre personas listadas (sanciones)
docs_personas = buscar_en_contenido("persona física")
add_q("contenido_especifico", "¿Qué documentos mencionan personas físicas?", docs_personas, "lista_documentos")
# Sobre montos o cantidades
docs_toneladas = buscar_en_contenido("tonelada")
add_q("contenido_especifico", "¿Qué documentos hacen referencia a toneladas?", docs_toneladas, "lista_documentos")
# Sobre cooperación
docs_cooperacion = buscar_en_contenido("cooperación")
add_q("contenido_especifico", "¿En qué documentos se menciona la cooperación?", docs_cooperacion, "lista_documentos")
# ═══════════════════════════════════════════════
# CAT 11: DOCUMENTOS_CRUZADOS (requiere Knowledge Graph)
# ═══════════════════════════════════════════════
# Estas preguntas REQUIEREN sintetizar información de 2+ documentos.
# Un RAG vectorial básico recupera chunks de forma independiente y falla
# cuando la respuesta solo se puede construir relacionando hechos de múltiples
# documentos. Un knowledge graph (GraphRAG) debería superar al RAG básico aquí.
_ref_to_docs = defaultdict(set)
for _d, _info in doc_info.items():
    for _ref in _info.get("refs", []):
        _ref_to_docs[_ref].add(_d)
_ref_ranking = sorted(_ref_to_docs.items(), key=lambda x: (-len(x[1]), x[0]))
if _ref_ranking and len(_ref_ranking[0][1]) >= 2:
    _top_ref, _top_docs = _ref_ranking[0]
    add_q("documentos_cruzados",
          f"lista TODOS los documentos del corpus que citan el reglamento {_top_ref}.",
          sorted(_top_docs), "lista_documentos")
if len(_ref_ranking) >= 2 and len(_ref_ranking[1][1]) >= 2:
    _ref2, _docs2 = _ref_ranking[1]
    add_q("documentos_cruzados",
          f"¿Cuántos documentos del corpus hacen referencia al reglamento {_ref2}?",
          len(_docs2), "numero")
add_q("documentos_cruzados",
      "¿Cuántos actos legislativos externos distintos se citan en todo el corpus?",
      len(_ref_to_docs), "numero")
_multi_cited = sorted(r for r, ds in _ref_to_docs.items() if len(ds) >= 2)
add_q("documentos_cruzados",
      "¿Qué reglamentos externos son citados por 2 o más documentos del corpus?",
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
          f"¿Qué actos legislativos son citados TANTO por el documento {doc_info[_d1]['codigo']} COMO por el documento {doc_info[_d2]['codigo']}?",
          _common, "lista_referencias")
if _pair_shared_refs:
    _d1, _d2, _common = _pair_shared_refs[0]
    add_q("documentos_cruzados",
          "¿Qué par de documentos del corpus comparte más referencias cruzadas? ¿Cuántas referencias comparten?",
          {"documento_1": doc_info[_d1]["codigo"], "documento_2": doc_info[_d2]["codigo"],
           "num_compartidas": len(_common), "refs_compartidas": _common}, "objeto")
_doc_codes = {info["codigo"]: d for d, info in doc_info.items() if info.get("codigo")}
_internal_refs = []
for _d, _info in doc_info.items():
    for _ref in _info.get("refs", []):
        if _ref in _doc_codes and _doc_codes[_ref] != _d:
            _internal_refs.append((_d, _doc_codes[_ref]))
if _internal_refs:
    _d1, _d2 = _internal_refs[0]
    add_q("documentos_cruzados",
          f"El documento {doc_info[_d1]['codigo']} cita otro documento que también está en nuestro corpus. Identifícalo y describe de qué trata.",
          {"citante": doc_info[_d1]["codigo"], "citado": doc_info[_d2]["codigo"],
           "titulo_citado": doc_info[_d2]["titulo"][:200]}, "objeto")
_no_refs = sorted(d for d, info in doc_info.items() if not info.get("refs"))
add_q("documentos_cruzados",
      "¿Qué documentos del corpus no citan ningún otro acto legislativo?",
      _no_refs, "lista_documentos")
_most_citing = sorted(doc_info.items(), key=lambda x: -len(x[1].get("refs", [])))[:3]
add_q("documentos_cruzados",
      "¿Cuáles son los 3 documentos que citan más reglamentos externos? Indica códigos y cantidades.",
      [{"documento": doc_info[_d]["codigo"], "num_referencias": len(_i.get("refs", []))} for _d, _i in _most_citing], "ranking")
_comision_docs = sorted(idx_organo.get("Comisión Europea", []))
if _comision_docs:
    add_q("documentos_cruzados",
          "De los documentos emitidos por la Comisión Europea, lista sus códigos y fechas (requiere correlacionar organismo y metadatos de múltiples documentos).",
          [{"documento": _d, "codigo": doc_info[_d]["codigo"], "fecha": doc_info[_d]["fecha"]}
           for _d in _comision_docs], "ranking")
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
print(f"\n→ Reducido de {len(preguntas)} a {len(_selected)} preguntas (objetivo: 80-100)")
preguntas = _selected
# ═══════════════════════════════════════════════
# VERIFICACIÓN Y EXPORTACIÓN
# ═══════════════════════════════════════════════
texts = [q["pregunta"] for q in preguntas]
dupes = [t for t in texts if texts.count(t) > 1]
if dupes:
    print(f"\nADVERTENCIA: {len(set(dupes))} preguntas duplicadas:")
    for d in set(dupes):
        print(f"  - {d}")
else:
    print("\nOK Todas las preguntas son únicas")
print(f"Total de preguntas generadas: {len(preguntas)}")
cat_counts = Counter(q["categoria"] for q in preguntas)
print("\nDistribución por categoría:")
for cat, cnt in sorted(cat_counts.items()):
    print(f"  {cat}: {cnt}")
gold_standard = {
    "gold_standard": {
        "caso_uso": "documentos_ue",
        "idioma": "es",
        "total_preguntas": len(preguntas),
        "total_documentos_analizados": len(docs),
        "fecha_generacion": "2026-04-17",
        "categorias": dict(sorted(cat_counts.items())),
        "descripcion": "Gold standard para evaluar un sistema RAG sobre documentos del Diario Oficial de la UE "
                       "en español (reglamentos, decisiones, correcciones). Contiene preguntas de identificación, "
                       "búsqueda por tipo, búsqueda por contenido, conteo, referencias cruzadas, estructura, "
                       "existencia, listado, relaciones y contenido específico. Incluye una categoría "
                       "'documentos_cruzados' con preguntas multi-hop (referencias compartidas, cadenas de "
                       "citación, agregaciones multi-documento) diseñadas para exponer las limitaciones "
                       "del RAG vectorial básico y resolverse con un knowledge graph. "
                       "Todas las respuestas computadas de los datos.",
        "preguntas": preguntas
    }
}
output_path = OUTPUT_DIR / "gold_standard_eu_es.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(gold_standard, f, ensure_ascii=False, indent=2)
print(f"\nOK Gold standard guardado en: {output_path}")
