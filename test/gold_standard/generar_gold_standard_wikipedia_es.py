"""
Script para generar el Gold Standard del caso de uso de Wikipedia en español.
Genera 80-100 preguntas únicas con respuestas extraídas directamente de los artículos.

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
# 1. CARGAR TODOS LOS ARTÍCULOS
# ─────────────────────────────────────────────
WIKI_DIR = Path(__file__).parent.parent.parent / "data" / "wikipedia" / "es" / "json"
OUTPUT_DIR = Path(__file__).parent.parent / "data"

articulos = {}
for f in sorted(WIKI_DIR.glob("*.json")):
    with open(f, encoding="utf-8") as fh:
        art = json.load(fh)
        articulos[art["titulo"]] = art

print(f"Cargados {len(articulos)} artículos")

# ─────────────────────────────────────────────
# 2. CONSTRUIR ÍNDICES
# ─────────────────────────────────────────────
# Categorías (limpias, sin prefijo "Categoría:")
idx_categoria = defaultdict(list)  # categoria -> [titulo, ...]
for titulo, art in articulos.items():
    for cat in art.get("categorias", []):
        cat_clean = cat.replace("Categoría:", "").strip()
        # Ignorar categorías internas de Wikipedia
        if not cat_clean.startswith("Wikipedia:"):
            idx_categoria[cat_clean].append(titulo)

# Secciones de cada artículo
def get_secciones(contenido):
    """Extrae los títulos de sección (== Titulo ==)."""
    return re.findall(r'^={2,3}\s*(.+?)\s*={2,3}', contenido, re.MULTILINE)

# Extraer primera frase (definición)
def get_primera_frase(contenido):
    """Extrae la primera frase del contenido (hasta el primer punto seguido de espacio o salto)."""
    # Limpiar referencias tipo ​ y similares
    clean = re.sub(r'[\u200b\u200c\u200d\u200e\u200f]', '', contenido)
    match = re.match(r'^(.+?\.)\s', clean)
    if match:
        return match.group(1).strip()
    return clean[:200].strip()

# Contar palabras
def contar_palabras(contenido):
    return len(contenido.split())

# Buscar artículos que contengan un keyword
def buscar_en_contenido(keyword):
    result = []
    for titulo, art in articulos.items():
        if keyword.lower() in art["contenido"].lower():
            result.append(titulo)
    return result

# Buscar artículos por categoría
def buscar_por_categoria(cat_keyword):
    result = []
    for cat, titulos in idx_categoria.items():
        if cat_keyword.lower() in cat.lower():
            result.extend(titulos)
    return sorted(set(result))

# Estadísticas
palabras_por_articulo = {t: contar_palabras(a["contenido"]) for t, a in articulos.items()}
secciones_por_articulo = {t: get_secciones(a["contenido"]) for t, a in articulos.items()}
n_secciones = {t: len(s) for t, s in secciones_por_articulo.items()}
n_categorias = {t: len([c for c in a.get("categorias", []) if not c.replace("Categoría:", "").startswith("Wikipedia:")]) for t, a in articulos.items()}

titulos = list(articulos.keys())
random.shuffle(titulos)
t_iter = iter(titulos)

def next_art():
    t = next(t_iter)
    return t, articulos[t]

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


# ═══════════════════════════════════════════════
# CAT 1: DEFINICIÓN / CONTENIDO DE UN ARTÍCULO (30)
# "¿Qué es X?" / "¿De qué trata el artículo X?"
# ═══════════════════════════════════════════════

t, a = next_art()
add_q("definicion", f"¿Qué es {t}?", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"Define el concepto de {t}.", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"¿De qué trata el artículo sobre {t}?", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"Explica brevemente qué es {t}.", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"Dame una descripción de {t}.", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"¿Cómo se define {t} según la información disponible?", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"Necesito saber qué es {t}. ¿Puedes explicármelo?", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"Resume en una frase el tema de {t}.", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"¿Qué concepto designa el término {t}?", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"¿En qué consiste {t}?", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"Proporciona la definición de {t}.", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"¿A qué se refiere el concepto de {t}?", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"Cuéntame sobre {t}. ¿Qué es exactamente?", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"¿Cuál es el significado de {t}?", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"Si busco {t}, ¿qué información encuentro?", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"¿Podrías decirme qué es {t} de forma concisa?", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"Describe el concepto recogido bajo el nombre de {t}.", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"Quiero entender qué es {t}. Resúmelo.", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"¿Qué información hay disponible sobre {t}?", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"Explícame el tema de {t} en pocas palabras.", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"¿Qué entendemos por {t}?", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"Háblame sobre {t}.", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"Me interesa saber qué es {t}. Dame una introducción.", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"¿Qué puedes contarme acerca de {t}?", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"¿Cómo definirías {t} a partir de los datos?", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"¿Qué se sabe sobre {t}?", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"¿Tienes información sobre {t}? Resúmela.", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"Haz un breve resumen de lo que es {t}.", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"Me gustaría que me aclararas qué es {t}.", get_primera_frase(a["contenido"]))
t, a = next_art()
add_q("definicion", f"¿En qué contexto aparece y qué significa {t}?", get_primera_frase(a["contenido"]))

# ═══════════════════════════════════════════════
# CAT 2: SECCIONES DE UN ARTÍCULO (20)
# ═══════════════════════════════════════════════

# Seleccionar artículos con secciones
arts_con_secciones = [(t, a) for t, a in articulos.items() if len(get_secciones(a["contenido"])) >= 2]
random.shuffle(arts_con_secciones)
sec_iter = iter(arts_con_secciones)

def next_art_sec():
    return next(sec_iter)

t, a = next_art_sec()
add_q("secciones", f"¿Qué secciones tiene el artículo sobre {t}?", get_secciones(a["contenido"]), "lista_secciones")
t, a = next_art_sec()
add_q("secciones", f"Lista los apartados del artículo de {t}.", get_secciones(a["contenido"]), "lista_secciones")
t, a = next_art_sec()
add_q("secciones", f"¿Cuáles son los temas que se tratan en el artículo de {t}?", get_secciones(a["contenido"]), "lista_secciones")
t, a = next_art_sec()
add_q("secciones", f"¿En qué partes se divide el contenido de {t}?", get_secciones(a["contenido"]), "lista_secciones")
t, a = next_art_sec()
add_q("secciones", f"Dame la estructura del artículo sobre {t}.", get_secciones(a["contenido"]), "lista_secciones")
t, a = next_art_sec()
add_q("secciones", f"¿Qué subtemas aborda el artículo de {t}?", get_secciones(a["contenido"]), "lista_secciones")
t, a = next_art_sec()
add_q("secciones", f"Indica los encabezados del artículo sobre {t}.", get_secciones(a["contenido"]), "lista_secciones")
t, a = next_art_sec()
add_q("secciones", f"¿De qué habla cada parte del artículo de {t}?", get_secciones(a["contenido"]), "lista_secciones")
t, a = next_art_sec()
add_q("secciones", f"Muéstrame el índice del artículo sobre {t}.", get_secciones(a["contenido"]), "lista_secciones")
t, a = next_art_sec()
add_q("secciones", f"¿Qué aspectos cubre el artículo de {t}?", get_secciones(a["contenido"]), "lista_secciones")
t, a = next_art_sec()
add_q("secciones", f"Enumera las secciones que componen el artículo de {t}.", get_secciones(a["contenido"]), "lista_secciones")
t, a = next_art_sec()
add_q("secciones", f"¿Cuántas secciones tiene {t} y cuáles son?", get_secciones(a["contenido"]), "lista_secciones")
t, a = next_art_sec()
add_q("secciones", f"Desglosa la estructura temática de {t}.", get_secciones(a["contenido"]), "lista_secciones")
t, a = next_art_sec()
add_q("secciones", f"¿Qué puntos se desarrollan en el artículo de {t}?", get_secciones(a["contenido"]), "lista_secciones")
t, a = next_art_sec()
add_q("secciones", f"Dame los títulos de cada sección de {t}.", get_secciones(a["contenido"]), "lista_secciones")
t, a = next_art_sec()
add_q("secciones", f"¿Qué tabla de contenidos tiene el artículo de {t}?", get_secciones(a["contenido"]), "lista_secciones")
t, a = next_art_sec()
add_q("secciones", f"Revisa el artículo de {t} y dime sus secciones principales.", get_secciones(a["contenido"]), "lista_secciones")
t, a = next_art_sec()
add_q("secciones", f"¿En cuántas partes está organizado el artículo de {t}?", get_secciones(a["contenido"]), "lista_secciones")
t, a = next_art_sec()
add_q("secciones", f"¿Cómo está estructurado el contenido de {t}?", get_secciones(a["contenido"]), "lista_secciones")
t, a = next_art_sec()
add_q("secciones", f"Detalla la organización del artículo sobre {t}.", get_secciones(a["contenido"]), "lista_secciones")

# ═══════════════════════════════════════════════
# CAT 3: CATEGORÍAS DE UN ARTÍCULO (15)
# ═══════════════════════════════════════════════
t, a = next_art()
cats = [c.replace("Categoría:", "").strip() for c in a.get("categorias", []) if not c.replace("Categoría:", "").strip().startswith("Wikipedia:")]
add_q("categorias_articulo", f"¿A qué categorías pertenece el artículo de {t}?", cats, "lista_categorias")
t, a = next_art()
cats = [c.replace("Categoría:", "").strip() for c in a.get("categorias", []) if not c.replace("Categoría:", "").strip().startswith("Wikipedia:")]
add_q("categorias_articulo", f"Dime las categorías del artículo sobre {t}.", cats, "lista_categorias")
t, a = next_art()
cats = [c.replace("Categoría:", "").strip() for c in a.get("categorias", []) if not c.replace("Categoría:", "").strip().startswith("Wikipedia:")]
add_q("categorias_articulo", f"¿Bajo qué clasificación temática está {t}?", cats, "lista_categorias")
t, a = next_art()
cats = [c.replace("Categoría:", "").strip() for c in a.get("categorias", []) if not c.replace("Categoría:", "").strip().startswith("Wikipedia:")]
add_q("categorias_articulo", f"¿En qué categorías se encuadra el artículo de {t}?", cats, "lista_categorias")
t, a = next_art()
cats = [c.replace("Categoría:", "").strip() for c in a.get("categorias", []) if not c.replace("Categoría:", "").strip().startswith("Wikipedia:")]
add_q("categorias_articulo", f"Lista las etiquetas de clasificación del artículo {t}.", cats, "lista_categorias")
t, a = next_art()
cats = [c.replace("Categoría:", "").strip() for c in a.get("categorias", []) if not c.replace("Categoría:", "").strip().startswith("Wikipedia:")]
add_q("categorias_articulo", f"¿Qué temas abarca el artículo de {t} según sus categorías?", cats, "lista_categorias")
t, a = next_art()
cats = [c.replace("Categoría:", "").strip() for c in a.get("categorias", []) if not c.replace("Categoría:", "").strip().startswith("Wikipedia:")]
add_q("categorias_articulo", f"Consulta las categorías asignadas a {t}.", cats, "lista_categorias")
t, a = next_art()
cats = [c.replace("Categoría:", "").strip() for c in a.get("categorias", []) if not c.replace("Categoría:", "").strip().startswith("Wikipedia:")]
add_q("categorias_articulo", f"¿Cómo está clasificado el artículo sobre {t}?", cats, "lista_categorias")
t, a = next_art()
cats = [c.replace("Categoría:", "").strip() for c in a.get("categorias", []) if not c.replace("Categoría:", "").strip().startswith("Wikipedia:")]
add_q("categorias_articulo", f"Indica las categorías temáticas de {t}.", cats, "lista_categorias")
t, a = next_art()
cats = [c.replace("Categoría:", "").strip() for c in a.get("categorias", []) if not c.replace("Categoría:", "").strip().startswith("Wikipedia:")]
add_q("categorias_articulo", f"¿Dentro de qué áreas se ubica {t}?", cats, "lista_categorias")
t, a = next_art()
cats = [c.replace("Categoría:", "").strip() for c in a.get("categorias", []) if not c.replace("Categoría:", "").strip().startswith("Wikipedia:")]
add_q("categorias_articulo", f"Extrae las categorías del artículo {t}.", cats, "lista_categorias")
t, a = next_art()
cats = [c.replace("Categoría:", "").strip() for c in a.get("categorias", []) if not c.replace("Categoría:", "").strip().startswith("Wikipedia:")]
add_q("categorias_articulo", f"¿Qué etiquetas clasificatorias tiene {t}?", cats, "lista_categorias")
t, a = next_art()
cats = [c.replace("Categoría:", "").strip() for c in a.get("categorias", []) if not c.replace("Categoría:", "").strip().startswith("Wikipedia:")]
add_q("categorias_articulo", f"¿Con qué materias se relaciona el artículo {t}?", cats, "lista_categorias")
t, a = next_art()
cats = [c.replace("Categoría:", "").strip() for c in a.get("categorias", []) if not c.replace("Categoría:", "").strip().startswith("Wikipedia:")]
add_q("categorias_articulo", f"Muéstrame la clasificación temática de {t}.", cats, "lista_categorias")
t, a = next_art()
cats = [c.replace("Categoría:", "").strip() for c in a.get("categorias", []) if not c.replace("Categoría:", "").strip().startswith("Wikipedia:")]
add_q("categorias_articulo", f"¿A qué campos del conocimiento pertenece {t}?", cats, "lista_categorias")

# ═══════════════════════════════════════════════
# CAT 4: BÚSQUEDA POR CATEGORÍA (20)
# ═══════════════════════════════════════════════
cat_keys = [c for c, arts in idx_categoria.items() if 2 <= len(arts) <= 50]
random.shuffle(cat_keys)
cat_iter = iter(cat_keys)

def next_cat():
    return next(cat_iter)

c = next_cat(); add_q("busqueda_por_categoria", f"¿Qué artículos pertenecen a la categoría {c}?", idx_categoria[c], "lista_articulos")
c = next_cat(); add_q("busqueda_por_categoria", f"Lista todos los artículos clasificados bajo {c}.", idx_categoria[c], "lista_articulos")
c = next_cat(); add_q("busqueda_por_categoria", f"¿Cuáles son los artículos de la categoría {c}?", idx_categoria[c], "lista_articulos")
c = next_cat(); add_q("busqueda_por_categoria", f"Dame los artículos que están en la categoría {c}.", idx_categoria[c], "lista_articulos")
c = next_cat(); add_q("busqueda_por_categoria", f"¿Qué temas están bajo la clasificación de {c}?", idx_categoria[c], "lista_articulos")
c = next_cat(); add_q("busqueda_por_categoria", f"Busca artículos en la categoría {c}.", idx_categoria[c], "lista_articulos")
c = next_cat(); add_q("busqueda_por_categoria", f"¿Cuántos y cuáles artículos hay bajo {c}?", idx_categoria[c], "lista_articulos")
c = next_cat(); add_q("busqueda_por_categoria", f"Muéstrame todos los artículos de {c}.", idx_categoria[c], "lista_articulos")
c = next_cat(); add_q("busqueda_por_categoria", f"¿Qué contenidos están categorizados como {c}?", idx_categoria[c], "lista_articulos")
c = next_cat(); add_q("busqueda_por_categoria", f"Encuentra los artículos pertenecientes a {c}.", idx_categoria[c], "lista_articulos")
c = next_cat(); add_q("busqueda_por_categoria", f"Enumera los artículos que se clasifican dentro de {c}.", idx_categoria[c], "lista_articulos")
c = next_cat(); add_q("busqueda_por_categoria", f"¿Puedes listar los artículos etiquetados como {c}?", idx_categoria[c], "lista_articulos")
c = next_cat(); add_q("busqueda_por_categoria", f"¿Qué artículos se relacionan con la categoría {c}?", idx_categoria[c], "lista_articulos")
c = next_cat(); add_q("busqueda_por_categoria", f"Identifica los artículos que pertenecen a {c}.", idx_categoria[c], "lista_articulos")
c = next_cat(); add_q("busqueda_por_categoria", f"Filtra los artículos por la categoría {c}.", idx_categoria[c], "lista_articulos")
c = next_cat(); add_q("busqueda_por_categoria", f"¿Dentro de {c}, qué artículos tenemos disponibles?", idx_categoria[c], "lista_articulos")
c = next_cat(); add_q("busqueda_por_categoria", f"Revisa la categoría {c} y dime qué artículos contiene.", idx_categoria[c], "lista_articulos")
c = next_cat(); add_q("busqueda_por_categoria", f"¿Qué artículos comparten la categoría {c}?", idx_categoria[c], "lista_articulos")
c = next_cat(); add_q("busqueda_por_categoria", f"Dame un inventario de los artículos en {c}.", idx_categoria[c], "lista_articulos")
c = next_cat(); add_q("busqueda_por_categoria", f"Selecciona de la base de datos los artículos de la categoría {c}.", idx_categoria[c], "lista_articulos")

# ═══════════════════════════════════════════════
# CAT 5: BÚSQUEDA POR CONTENIDO / KEYWORD (25)
# ═══════════════════════════════════════════════
kw_searches = [
    ("García Márquez", "¿Qué artículos mencionan a García Márquez?"),
    ("Borges", "¿En qué artículos aparece Borges?"),
    ("surrealismo", "¿Qué artículos tratan o mencionan el surrealismo?"),
    ("novela", "¿Cuáles artículos hacen referencia a la novela como género?"),
    ("poesía", "Lista los artículos que contengan la palabra poesía."),
    ("Latinoamérica", "¿Qué artículos mencionan Latinoamérica o América Latina?"),
    ("siglo XX", "¿En cuáles artículos se hace referencia al siglo XX?"),
    ("romanticismo", "Busca artículos que hablen sobre el romanticismo."),
    ("vanguardia", "¿Qué artículos tratan sobre vanguardias o movimientos vanguardistas?"),
    ("metáfora", "¿En qué artículos se menciona la metáfora?"),
    ("narrativa", "¿Cuáles artículos abordan el tema de la narrativa?"),
    ("Aristóteles", "¿Qué artículos hacen referencia a Aristóteles?"),
    ("verso", "Identifica los artículos que contengan información sobre el verso."),
    ("cuento", "¿En cuáles artículos se menciona el cuento como género literario?"),
    ("realismo", "Dame los artículos que traten sobre el realismo."),
    ("feminismo", "¿Qué artículos contienen la palabra feminismo o femenina?"),
    ("teatro", "Muéstrame artículos que hablen sobre teatro."),
    ("rima", "¿Qué artículos abordan el concepto de rima?"),
    ("ficción", "Busca artículos que mencionen la ficción."),
    ("España", "¿En qué artículos se menciona España?"),
    ("escritor", "¿Cuáles artículos hacen referencia a la figura del escritor?"),
    ("oral", "Lista los artículos que traten la literatura o tradición oral."),
    ("premio Nobel", "¿Qué artículos mencionan el premio Nobel?"),
    ("Cervantes", "¿En qué artículos aparece mencionado Cervantes?"),
    ("ensayo", "¿Cuáles artículos contienen información sobre el ensayo como género?"),
]

for kw, pregunta in kw_searches:
    # Para keywords con "|" usamos búsquedas múltiples
    if "o " in pregunta and kw in ["Latinoamérica", "feminismo"]:
        if kw == "Latinoamérica":
            r = sorted(set(buscar_en_contenido("Latinoamérica") + buscar_en_contenido("América Latina")))
        elif kw == "feminismo":
            r = sorted(set(buscar_en_contenido("feminismo") + buscar_en_contenido("femenina")))
    else:
        r = buscar_en_contenido(kw)
    add_q("busqueda_por_contenido", pregunta, r, "lista_articulos")

# ═══════════════════════════════════════════════
# CAT 6: METADATOS (15)
# ═══════════════════════════════════════════════
t, a = next_art()
add_q("metadatos", f"¿Cuál es la URL del artículo sobre {t}?", a["url"], "texto")
t, a = next_art()
add_q("metadatos", f"¿Qué identificador de página tiene el artículo de {t}?", a["pageid"], "numero")
t, a = next_art()
add_q("metadatos", f"¿En qué idioma está el artículo de {t}?", a["idioma"], "texto")
t, a = next_art()
add_q("metadatos", f"¿Cuándo se descargó el artículo sobre {t}?", a["fecha_descarga"], "texto")
t, a = next_art()
add_q("metadatos", f"Dame la URL del artículo {t}.", a["url"], "texto")
t, a = next_art()
add_q("metadatos", f"¿Cuál es el page ID del artículo de {t}?", a["pageid"], "numero")
t, a = next_art()
add_q("metadatos", f"¿De qué fecha es la descarga del artículo {t}?", a["fecha_descarga"], "texto")
t, a = next_art()
add_q("metadatos", f"Indícame el enlace al artículo original de {t}.", a["url"], "texto")
t, a = next_art()
add_q("metadatos", f"¿Cuántas categorías tiene asignadas el artículo {t}?", len(a.get("categorias", [])), "numero")
t, a = next_art()
add_q("metadatos", f"¿Cuántas palabras tiene aproximadamente el artículo de {t}?", palabras_por_articulo[t], "numero")
t, a = next_art()
add_q("metadatos", f"¿Cuántas secciones contiene el artículo sobre {t}?", n_secciones.get(t, 0), "numero")
t, a = next_art()
add_q("metadatos", f"Dame los metadatos del artículo {t}: URL y page ID.", {"url": a["url"], "pageid": a["pageid"]}, "objeto")
t, a = next_art()
add_q("metadatos", f"¿Cuál es el título exacto del artículo con page ID {a['pageid']}?", t, "texto")
t, a = next_art()
add_q("metadatos", f"Proporciona la fecha de descarga y el idioma del artículo sobre {t}.", {"fecha_descarga": a["fecha_descarga"], "idioma": a["idioma"]}, "objeto")
t, a = next_art()
add_q("metadatos", f"¿Cuántas categorías no internas tiene el artículo de {t}?", n_categorias.get(t, 0), "numero")

# ═══════════════════════════════════════════════
# CAT 7: CONTEO Y ESTADÍSTICAS (20)
# ═══════════════════════════════════════════════
add_q("conteo", "¿Cuántos artículos hay en total en la base de datos?", len(articulos), "numero")
add_q("conteo", "¿Cuántas categorías distintas existen entre todos los artículos?", len(idx_categoria), "numero")

art_mas_largo = max(palabras_por_articulo.items(), key=lambda x: x[1])
add_q("conteo", "¿Cuál es el artículo más largo (más palabras)?", {"articulo": art_mas_largo[0], "palabras": art_mas_largo[1]}, "objeto")

art_mas_corto = min(palabras_por_articulo.items(), key=lambda x: x[1])
add_q("conteo", "¿Cuál es el artículo más corto (menos palabras)?", {"articulo": art_mas_corto[0], "palabras": art_mas_corto[1]}, "objeto")

avg_palabras = round(sum(palabras_por_articulo.values()) / len(palabras_por_articulo), 1)
add_q("conteo", "¿Cuál es la media de palabras por artículo?", avg_palabras, "numero")

art_mas_secciones = max(n_secciones.items(), key=lambda x: x[1])
add_q("conteo", "¿Qué artículo tiene más secciones?", {"articulo": art_mas_secciones[0], "secciones": art_mas_secciones[1]}, "objeto")

art_mas_cats = max(n_categorias.items(), key=lambda x: x[1])
add_q("conteo", "¿Cuál es el artículo con más categorías asignadas?", {"articulo": art_mas_cats[0], "categorias": art_mas_cats[1]}, "objeto")

add_q("conteo", "¿Cuántos artículos tienen más de 1000 palabras?",
      len([t for t, w in palabras_por_articulo.items() if w > 1000]), "numero")

add_q("conteo", "¿Cuántos artículos tienen menos de 500 palabras?",
      len([t for t, w in palabras_por_articulo.items() if w < 500]), "numero")

top5_cats = Counter({c: len(arts) for c, arts in idx_categoria.items()}).most_common(5)
add_q("conteo", "¿Cuáles son las 5 categorías con más artículos?",
      [{"categoria": c, "num_articulos": n} for c, n in top5_cats], "ranking")

add_q("conteo", "¿Cuántos artículos mencionan la palabra 'poesía' en su contenido?",
      len(buscar_en_contenido("poesía")), "numero")

add_q("conteo", "¿Cuántos artículos mencionan 'novela'?",
      len(buscar_en_contenido("novela")), "numero")

add_q("conteo", "¿Cuántos artículos mencionan 'siglo XIX'?",
      len(buscar_en_contenido("siglo XIX")), "numero")

avg_secciones = round(sum(n_secciones.values()) / len(n_secciones), 1)
add_q("conteo", "¿Cuál es el promedio de secciones por artículo?", avg_secciones, "numero")

add_q("conteo", "¿Cuántos artículos no tienen ninguna sección?",
      len([t for t, n in n_secciones.items() if n == 0]), "numero")

avg_cats = round(sum(n_categorias.values()) / len(n_categorias), 1)
add_q("conteo", "¿Cuál es la media de categorías por artículo?", avg_cats, "numero")

total_palabras = sum(palabras_por_articulo.values())
add_q("conteo", "¿Cuántas palabras hay en total sumando todos los artículos?", total_palabras, "numero")

add_q("conteo", "¿Cuántos artículos mencionan 'vanguardia'?",
      len(buscar_en_contenido("vanguardia")), "numero")

add_q("conteo", "¿Cuántos artículos contienen la palabra 'realismo'?",
      len(buscar_en_contenido("realismo")), "numero")

add_q("conteo", "¿Cuántos artículos tratan sobre movimientos literarios (mencionan 'movimiento literario')?",
      len(buscar_en_contenido("movimiento literario")), "numero")

# ═══════════════════════════════════════════════
# CAT 8: EXISTENCIA (15)
# ═══════════════════════════════════════════════
add_q("existencia", "¿Hay algún artículo sobre realismo mágico?",
      {"existe": "Realismo mágico" in articulos, "titulo": "Realismo mágico" if "Realismo mágico" in articulos else None}, "booleano")

add_q("existencia", "¿Existe un artículo dedicado al Boom latinoamericano?",
      {"existe": "Boom latinoamericano" in articulos, "titulo": "Boom latinoamericano" if "Boom latinoamericano" in articulos else None}, "booleano")

add_q("existencia", "¿Tenemos un artículo sobre poesía?",
      {"existe": "Poesía" in articulos or "Poesía." in articulos, "titulo": "Poesía" if "Poesía" in articulos else None}, "booleano")

add_q("existencia", "¿Hay algún artículo que trate sobre naturalismo?",
      {"existe": any("naturalismo" in t.lower() for t in articulos), "articulos": [t for t in articulos if "naturalismo" in t.lower()]}, "booleano")

add_q("existencia", "¿Existe un artículo sobre el ultraísmo?",
      {"existe": "Ultraísmo" in articulos, "titulo": "Ultraísmo" if "Ultraísmo" in articulos else None}, "booleano")

add_q("existencia", "¿Se menciona a Shakespeare en alguno de los artículos?",
      {"existe": len(buscar_en_contenido("Shakespeare")) > 0, "articulos": buscar_en_contenido("Shakespeare")}, "booleano")

add_q("existencia", "¿Hay artículos que mencionen a Pablo Neruda?",
      {"existe": len(buscar_en_contenido("Neruda")) > 0, "articulos": buscar_en_contenido("Neruda")}, "booleano")

add_q("existencia", "¿Existe algún artículo sobre la poesía visual?",
      {"existe": "Poesía visual" in articulos, "titulo": "Poesía visual" if "Poesía visual" in articulos else None}, "booleano")

add_q("existencia", "¿Hay artículos que contengan la palabra 'Quijote'?",
      {"existe": len(buscar_en_contenido("Quijote")) > 0, "articulos": buscar_en_contenido("Quijote")}, "booleano")

add_q("existencia", "¿Se hace referencia a Freud en algún artículo?",
      {"existe": len(buscar_en_contenido("Freud")) > 0, "articulos": buscar_en_contenido("Freud")}, "booleano")

add_q("existencia", "¿Hay algún artículo sobre el creacionismo poético?",
      {"existe": any("creacionismo" in t.lower() for t in articulos), "articulos": [t for t in articulos if "creacionismo" in t.lower()]}, "booleano")

add_q("existencia", "¿Tenemos artículos que mencionen el surrealismo?",
      {"existe": len(buscar_en_contenido("surrealismo")) > 0, "articulos": buscar_en_contenido("surrealismo")}, "booleano")

add_q("existencia", "¿Hay algún artículo sobre el modernismo literario?",
      {"existe": any("modernismo" in t.lower() or "modernista" in t.lower() for t in articulos),
       "articulos": [t for t in articulos if "modernismo" in t.lower() or "modernista" in t.lower()]}, "booleano")

add_q("existencia", "¿Existe información sobre la generación del 99?",
      {"existe": any("generación del 99" in t.lower() for t in articulos),
       "articulos": [t for t in articulos if "generación del 99" in t.lower()]}, "booleano")

add_q("existencia", "¿Se mencionan los haikus en algún artículo de la base de datos?",
      {"existe": len(buscar_en_contenido("haiku")) > 0, "articulos": buscar_en_contenido("haiku")}, "booleano")

# ═══════════════════════════════════════════════
# CAT 9: LISTADO COMPLETO DE ARTÍCULOS (10)
# ═══════════════════════════════════════════════
add_q("listado", "Dame la lista completa de todos los artículos disponibles.", sorted(articulos.keys()), "lista_articulos")
add_q("listado", "¿Cuáles son todos los títulos de artículos de la base de datos?", sorted(articulos.keys()), "lista_articulos")
add_q("listado", "Enumera todos los artículos que tenemos.", sorted(articulos.keys()), "lista_articulos")
add_q("listado", "Necesito ver el catálogo completo de artículos. ¿Cuáles hay?", sorted(articulos.keys()), "lista_articulos")
add_q("listado", "Muéstrame una lista de todos los artículos disponibles en español.", sorted(articulos.keys()), "lista_articulos")

# Artículos que empiezan por una letra
arts_P = sorted([t for t in articulos if t.startswith("P")])
add_q("listado", "¿Qué artículos empiezan por la letra P?", arts_P, "lista_articulos")

arts_L = sorted([t for t in articulos if t.startswith("L")])
add_q("listado", "Lista los artículos cuyo título empieza por L.", arts_L, "lista_articulos")

arts_E = sorted([t for t in articulos if t.startswith("E")])
add_q("listado", "¿Cuáles artículos comienzan con la letra E?", arts_E, "lista_articulos")

arts_R = sorted([t for t in articulos if t.startswith("R")])
add_q("listado", "Busca artículos cuyo nombre empiece por R.", arts_R, "lista_articulos")

arts_M = sorted([t for t in articulos if t.startswith("M")])
add_q("listado", "¿Qué artículos tenemos que empiecen por M?", arts_M, "lista_articulos")

# ═══════════════════════════════════════════════
# CAT 10: COMPARACIONES Y RELACIONES (30)
# ═══════════════════════════════════════════════

# Artículos que comparten categoría
cat_pairs = [(c, arts) for c, arts in idx_categoria.items() if 2 <= len(arts) <= 10]
random.shuffle(cat_pairs)
cp_iter = iter(cat_pairs)

c, arts = next(cp_iter)
add_q("relaciones", f"¿Qué artículos comparten la categoría '{c}'?", arts, "lista_articulos")
c, arts = next(cp_iter)
add_q("relaciones", f"Dame los artículos que tienen en común la categoría {c}.", arts, "lista_articulos")
c, arts = next(cp_iter)
add_q("relaciones", f"¿Cuáles artículos están relacionados por pertenecer a {c}?", arts, "lista_articulos")
c, arts = next(cp_iter)
add_q("relaciones", f"Identifica los artículos que coinciden en la categoría {c}.", arts, "lista_articulos")
c, arts = next(cp_iter)
add_q("relaciones", f"¿Qué temas están vinculados a través de la categoría {c}?", arts, "lista_articulos")

# Artículos que mencionan otro artículo
mention_pairs = []
titulos_sorted = sorted(articulos.keys())
for t1 in titulos_sorted:
    for t2 in titulos_sorted:
        if t1 != t2 and t2.lower() in articulos[t1]["contenido"].lower() and len(t2) > 5:
            mention_pairs.append((t1, t2))
random.shuffle(mention_pairs)

if len(mention_pairs) >= 10:
    mp_iter = iter(mention_pairs[:30])
    t1, t2 = next(mp_iter)
    add_q("relaciones", f"¿El artículo de {t1} menciona a {t2}?", True, "booleano_simple")
    t1, t2 = next(mp_iter)
    add_q("relaciones", f"¿Se hace referencia a {t2} dentro del artículo de {t1}?", True, "booleano_simple")
    t1, t2 = next(mp_iter)
    add_q("relaciones", f"¿Existe alguna conexión entre los artículos de {t1} y {t2}?", True, "booleano_simple")
    t1, t2 = next(mp_iter)
    add_q("relaciones", f"¿Aparece mencionado {t2} en el contenido de {t1}?", True, "booleano_simple")
    t1, t2 = next(mp_iter)
    add_q("relaciones", f"¿Hay alguna relación entre {t1} y {t2} según los artículos?", True, "booleano_simple")

# Artículos más largos y más cortos
top5_largos = sorted(palabras_por_articulo.items(), key=lambda x: -x[1])[:5]
add_q("relaciones", "¿Cuáles son los 5 artículos más extensos?",
      [{"articulo": t, "palabras": w} for t, w in top5_largos], "ranking")

top5_cortos = sorted(palabras_por_articulo.items(), key=lambda x: x[1])[:5]
add_q("relaciones", "¿Cuáles son los 5 artículos más breves?",
      [{"articulo": t, "palabras": w} for t, w in top5_cortos], "ranking")

# Artículos sobre movimientos literarios
movimientos = buscar_en_contenido("movimiento literario")
add_q("relaciones", "¿Qué artículos tratan sobre movimientos literarios?", movimientos, "lista_articulos")

# Artículos sobre poesía
poesia_arts = buscar_por_categoria("Poesía")
if poesia_arts:
    add_q("relaciones", "¿Qué artículos están clasificados en categorías relacionadas con poesía?", poesia_arts, "lista_articulos")

# Artículos sobre literatura del siglo XX  
lit_xx = buscar_por_categoria("siglo XX")
if lit_xx:
    add_q("relaciones", "¿Qué artículos pertenecen a categorías del siglo XX?", lit_xx, "lista_articulos")

# Artículos sobre géneros literarios
generos = buscar_en_contenido("género literario")
add_q("relaciones", "¿Qué artículos hacen referencia a géneros literarios?", generos, "lista_articulos")

# Top categorías compartidas
cats_compartidas = [(c, len(arts)) for c, arts in idx_categoria.items() if len(arts) >= 3]
cats_compartidas.sort(key=lambda x: -x[1])
add_q("relaciones", "¿Cuáles son las categorías que agrupan a más artículos?",
      [{"categoria": c, "num_articulos": n} for c, n in cats_compartidas[:10]], "ranking")

# Artículos sin secciones
sin_secciones = [t for t, n in n_secciones.items() if n == 0]
add_q("relaciones", "¿Qué artículos no tienen secciones internas?", sorted(sin_secciones), "lista_articulos")

# Artículos con más secciones
top5_secciones = sorted(n_secciones.items(), key=lambda x: -x[1])[:5]
add_q("relaciones", "¿Cuáles son los 5 artículos con más secciones?",
      [{"articulo": t, "secciones": n} for t, n in top5_secciones], "ranking")

# Artículos sobre narrativa
narrativa = buscar_en_contenido("narrativa")
add_q("relaciones", "¿Cuáles artículos abordan la narrativa?", narrativa, "lista_articulos")

# Artículos que mencionan algún país concreto
arts_mexico = buscar_en_contenido("México")
add_q("relaciones", "¿Qué artículos mencionan México?", arts_mexico, "lista_articulos")

arts_argentina = buscar_en_contenido("Argentina")
add_q("relaciones", "¿En qué artículos se menciona Argentina?", arts_argentina, "lista_articulos")

arts_colombia = buscar_en_contenido("Colombia")
add_q("relaciones", "¿Cuáles artículos hacen referencia a Colombia?", arts_colombia, "lista_articulos")

arts_chile = buscar_en_contenido("Chile")
add_q("relaciones", "¿En qué artículos se habla de Chile?", arts_chile, "lista_articulos")

arts_cuba = buscar_en_contenido("Cuba")
add_q("relaciones", "¿Qué artículos mencionan Cuba?", arts_cuba, "lista_articulos")

arts_francia = buscar_en_contenido("Francia")
add_q("relaciones", "Lista los artículos que hagan referencia a Francia.", arts_francia, "lista_articulos")

# Top artículos por número de categorías
top5_cats_art = sorted(n_categorias.items(), key=lambda x: -x[1])[:5]
add_q("relaciones", "¿Cuáles son los 5 artículos con más categorías asignadas?",
      [{"articulo": t, "categorias": n} for t, n in top5_cats_art], "ranking")

# Artículos sobre siglo XIX
arts_xix = buscar_en_contenido("siglo XIX")
add_q("relaciones", "¿Qué artículos hacen referencia al siglo XIX?", arts_xix, "lista_articulos")

# Artículos sobre literatura española
arts_lit_esp = buscar_en_contenido("literatura española")
add_q("relaciones", "¿Qué artículos mencionan la literatura española?", arts_lit_esp, "lista_articulos")

# Artículos sobre América
arts_america = buscar_en_contenido("América")
add_q("relaciones", "¿En cuáles artículos se menciona América?", arts_america, "lista_articulos")


# ═══════════════════════════════════════════════
# CAT 11: DOCUMENTOS_CRUZADOS (requiere Knowledge Graph)
# ═══════════════════════════════════════════════
# Estas preguntas están diseñadas DELIBERADAMENTE para fallar con un RAG básico
# que recupera chunks de forma independiente. REQUIEREN sintetizar información
# de 2+ artículos distintos (razonamiento multi-hop, entidades compartidas,
# referencias bidireccionales y cadenas de menciones). Un knowledge graph
# (GraphRAG) debería superar claramente al RAG básico en estas preguntas.

# --- Detectar entidades (nombres propios) mencionadas en múltiples artículos ---
_proper_re = re.compile(
    r"\b((?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+(?:de|del|de\s+la|von|van|der|du|la|le|d['’]))?\s+){1,3}[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)\b"
)
_entity_articulos = defaultdict(set)
_blacklist = {
    "Estados Unidos", "Unión Europea", "Edad Media", "Nueva York",
    "Guerra Mundial", "Gran Bretaña", "Reino Unido", "América Latina",
    "América del Norte", "América del Sur", "Imperio Romano",
    "Espíritu Santo", "Tercer Mundo", "Real Academia",
}
for _t, _a in articulos.items():
    _seen_here = set()
    for _m in _proper_re.finditer(_a["contenido"]):
        _name = _m.group(1).strip()
        if _name in _blacklist or _name in articulos:
            continue
        if any(_name.startswith(p) for p in ("El ", "La ", "Los ", "Las ", "Esta ", "Este ", "Estos ", "Estas ", "Otros ", "Otras ")):
            continue
        if len(_name) < 6:
            continue
        _seen_here.add(_name)
    for _name in _seen_here:
        _entity_articulos[_name].add(_t)

_entidades_multi = sorted(
    ((n, ts) for n, ts in _entity_articulos.items() if len(ts) >= 3),
    key=lambda x: (-len(x[1]), x[0]),
)

# Q1-Q3: lista de artículos que mencionan una entidad compartida
for _idx, _slot in enumerate(_entidades_multi[:3]):
    _name, _arts = _slot
    if _idx == 0:
        add_q("documentos_cruzados",
              f"Lista todos los artículos del corpus que mencionan a {_name}.",
              sorted(_arts), "lista_articulos")
    elif _idx == 1:
        add_q("documentos_cruzados",
              f"¿Qué artículos hacen referencia a {_name}? Proporciona la lista completa, no solo un ejemplo.",
              sorted(_arts), "lista_articulos")
    else:
        add_q("documentos_cruzados",
              f"¿Cuántos artículos distintos mencionan a {_name} y cuáles son?",
              {"conteo": len(_arts), "articulos": sorted(_arts)}, "objeto")

# Q4: conteo agregado sobre una entidad compartida (RAG básico no puede agregar)
if len(_entidades_multi) >= 4:
    _name, _arts = _entidades_multi[3]
    add_q("documentos_cruzados",
          f"¿En cuántos artículos en total se menciona a {_name}?",
          len(_arts), "numero")

# --- Referencias bidireccionales: A menciona a B Y B menciona a A ---
_outgoing = defaultdict(set)
for _a, _b in mention_pairs:
    _outgoing[_a].add(_b)

_bidir = sorted({tuple(sorted([_a, _b])) for _a, _b in mention_pairs if _a in _outgoing[_b]})

# Q5-Q6: relación mutua entre dos artículos (RAG básico suele recuperar solo uno)
for _idx, _pair in enumerate(_bidir[:2]):
    _a, _b = _pair
    if _idx == 0:
        add_q("documentos_cruzados",
              f"Describe la relación mutua entre los artículos sobre {_a} y {_b}: explica cómo cada uno hace referencia al otro.",
              {"referencia_mutua": True, "articulos": [_a, _b]}, "objeto")
    else:
        add_q("documentos_cruzados",
              f"¿Están conectados bidireccionalmente los artículos sobre {_a} y {_b}? Si es así, justifica indicando que cada uno cita al otro.",
              {"referencia_mutua": True, "articulos": [_a, _b]}, "objeto")

# Q7: conteo total de pares con referencia mutua (requiere recorrer TODOS los pares)
add_q("documentos_cruzados",
      "¿Cuántos pares de artículos en el corpus se referencian mutuamente?",
      len(_bidir), "numero")

# --- Cadenas de 3 saltos: A → B → C donde A no menciona directamente a C ---
_chains = []
for _a, _bs in _outgoing.items():
    for _b in _bs:
        for _c in _outgoing.get(_b, ()):
            if _c != _a and _c not in _outgoing.get(_a, set()):
                _chains.append((_a, _b, _c))
_chains = sorted(set(_chains))

# Q8-Q9: razonamiento multi-hop (3 artículos requeridos)
for _idx, _chain in enumerate(_chains[:2]):
    _a, _b, _c = _chain
    if _idx == 0:
        add_q("documentos_cruzados",
              f"Encuentra un artículo que conecte {_a} con {_c}: identifica un artículo intermedio mencionado por {_a} que a su vez haga referencia a {_c}.",
              {"intermedio": _b, "cadena": [_a, _b, _c]}, "objeto")
    else:
        add_q("documentos_cruzados",
              f"¿A través de qué artículo intermedio está {_a} indirectamente conectado con {_c}?",
              {"intermedio": _b, "cadena": [_a, _b, _c],
               "explicacion": f"{_a} menciona a {_b}, y {_b} menciona a {_c}"}, "objeto")

# --- Pares fuertemente relacionados: artículos que comparten 2+ categorías ---
_pair_shared = defaultdict(list)
for _cat, _arts in idx_categoria.items():
    if 2 <= len(_arts) <= 8:
        for _i, _x in enumerate(_arts):
            for _y in _arts[_i + 1:]:
                _pair_shared[tuple(sorted([_x, _y]))].append(_cat)
_strong_pairs = sorted(((p, cs) for p, cs in _pair_shared.items() if len(cs) >= 2),
                       key=lambda x: (-len(x[1]), x[0]))

# Q10-Q11: TODAS las categorías compartidas entre dos artículos (RAG básico se deja algunas)
for _idx, _slot in enumerate(_strong_pairs[:2]):
    (_x, _y), _cats = _slot
    if _idx == 0:
        add_q("documentos_cruzados",
              f"Lista TODAS las categorías que comparten los artículos {_x} y {_y}.",
              sorted(_cats), "lista_categorias")
    else:
        add_q("documentos_cruzados",
              f"¿Qué etiquetas de clasificación comparten los artículos {_x} y {_y}? Proporciona todas las categorías comunes.",
              sorted(_cats), "lista_categorias")

# Q12: entidad puente entre dos artículos concretos
_bridge_candidates = sorted(((n, list(ts)) for n, ts in _entity_articulos.items() if len(ts) == 2),
                            key=lambda x: x[0])
if _bridge_candidates:
    _name_b, _arts_b = _bridge_candidates[0]
    _arts_b_sorted = sorted(_arts_b)
    add_q("documentos_cruzados",
          f"¿Qué nombre propio se menciona TANTO en el artículo '{_arts_b_sorted[0]}' COMO en el artículo '{_arts_b_sorted[1]}'?",
          _name_b, "texto")


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
        # Mantener TODAS las preguntas cruzadas: es el conjunto de evaluación del KG.
        _filtered[cat] = qs
    else:
        _filtered[cat] = _remove_similar(qs, "pregunta")

_total_f = sum(len(v) for k, v in _filtered.items() if k != "documentos_cruzados") or 1
_selected = []
for cat, qs in sorted(_filtered.items()):
    if cat == "documentos_cruzados":
        _selected.extend(qs)  # mantener todas las preguntas KG
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
if len(texts) != len(set(texts)):
    dupes = set([t for t in texts if texts.count(t) > 1])
    print(f"ADVERTENCIA: {len(dupes)} preguntas duplicadas:")
    for d in dupes:
        print(f"  - {d}")
else:
    print("✓ Todas las preguntas son únicas")

print(f"Total de preguntas generadas: {len(preguntas)}")

cat_counts = Counter(q["categoria"] for q in preguntas)
print("\nDistribución por categoría:")
for cat, cnt in sorted(cat_counts.items()):
    print(f"  {cat}: {cnt}")

gold_standard = {
    "gold_standard": {
        "caso_uso": "wikipedia",
        "idioma": "es",
        "total_preguntas": len(preguntas),
        "total_articulos_analizados": len(articulos),
        "fecha_generacion": "2026-04-17",
        "categorias": dict(sorted(cat_counts.items())),
        "descripcion": "Gold standard para evaluar un sistema RAG sobre artículos de Wikipedia en español "
                       "(temática: literatura y movimientos literarios). Contiene preguntas de definición, "
                       "secciones, categorías, búsqueda por contenido, metadatos, conteo, existencia, "
                       "listados y relaciones entre artículos. Incluye una categoría 'documentos_cruzados' "
                       "con preguntas multi-hop (entidades compartidas, referencias bidireccionales y cadenas) "
                       "diseñadas para exponer las limitaciones del RAG vectorial básico y resolverse con un "
                       "knowledge graph. Todas las respuestas computadas de los datos.",
        "preguntas": preguntas
    }
}

output_path = OUTPUT_DIR / "gold_standard_wikipedia_es.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(gold_standard, f, ensure_ascii=False, indent=2)

print(f"\n✓ Gold standard guardado en: {output_path}")
