"""
Prompts específicos para el caso de uso Wiki / Wikipedia
"""
from __future__ import annotations
import json
from pathlib import Path
from src.config import config
# ---------------------------------------------------------------------------
# Catálogo del corpus Wikipedia (lista exhaustiva de artículos, generado
# offline por ``src/test/scripts/build_wiki_catalog.py``). Se carga una sola vez
# por proceso y se inyecta en el prompt para que el LLM pueda responder con
# precisión a preguntas de catálogo, conteo, listado, búsqueda por categoría,
# metadatos (URL, pageid, fecha de descarga) y secciones, incluso cuando los
# artículos concretos no han sido recuperados entre los chunks.
# ---------------------------------------------------------------------------
_CATALOG_PATH = Path(__file__).resolve().parents[3] / "data" / "wikipedia" / "catalog.json"
_CATALOG_CACHE: dict[str, dict] | None = None
def _load_catalog() -> dict[str, dict]:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return _CATALOG_CACHE
    try:
        _CATALOG_CACHE = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        _CATALOG_CACHE = {}
    return _CATALOG_CACHE
def _format_catalog(language: str) -> str:
    """Construye un bloque de texto compacto con el catálogo Wikipedia
    Devuelve cadena vacía si no hay catálogo para el idioma solicitado
    """
    catalog = _load_catalog()
    info = catalog.get(language) or catalog.get("en") or {}
    articulos: list[dict] = info.get("articulos") or []
    if not articulos:
        return ""
    stats: dict = info.get("stats") or {}
    cats_index: dict[str, list[str]] = info.get("categorias") or {}
    lines: list[str] = []
    # ── Estadísticas globales ────────────────────────────────────────
    lines.append("ESTADÍSTICAS GLOBALES DEL CORPUS:")
    lines.append(f"- total de artículos: {stats.get('total_articulos', 0)}")
    lines.append(f"- total de categorías únicas (no administrativas): {stats.get('total_categorias_unicas', 0)}")
    lines.append(f"- total de palabras (suma): {stats.get('total_palabras', 0)}")
    lines.append(f"- promedio de palabras por artículo: {stats.get('promedio_palabras_por_articulo', 0)}")
    lines.append(f"- promedio de secciones por artículo: {stats.get('promedio_secciones_por_articulo', 0)}")
    lines.append(f"- promedio de categorías por artículo: {stats.get('promedio_categorias_por_articulo', 0)}")
    larg = stats.get("articulo_mas_largo") or {}
    cort = stats.get("articulo_mas_corto") or {}
    msec = stats.get("articulo_mas_secciones") or {}
    mcat = stats.get("articulo_mas_categorias") or {}
    if larg: lines.append(f"- artículo más largo: \"{larg.get('titulo')}\" ({larg.get('palabras')} palabras)")
    if cort: lines.append(f"- artículo más corto: \"{cort.get('titulo')}\" ({cort.get('palabras')} palabras)")
    if msec: lines.append(f"- artículo con más secciones: \"{msec.get('titulo')}\" ({msec.get('secciones')} secciones)")
    if mcat: lines.append(f"- artículo con más categorías: \"{mcat.get('titulo')}\" ({mcat.get('categorias')} categorías)")
    top5 = stats.get("top5_categorias_con_mas_articulos") or []
    if top5:
        lines.append("- top5 categorías con más artículos: " + ", ".join(
            f"{e.get('categoria')}={e.get('num_articulos')}" for e in top5
        ))
    lines.append("")
    # ── Catálogo exhaustivo (uno por artículo) ───────────────────────
    lines.append("CATÁLOGO DE ARTÍCULOS (titulo | url | pageid | descargado | palabras | nº_secciones | nº_categorias):")
    for e in articulos:
        secs = e.get("secciones") or []
        cats = e.get("categorias") or []
        lines.append(
            "- \"{t}\" | {u} | pageid={p} | descargado={d} | palabras={w} | secs={ns} | cats={nc}".format(
                t=e.get("titulo", ""),
                u=e.get("url", ""),
                p=e.get("pageid"),
                d=e.get("fecha_descarga", ""),
                w=e.get("num_palabras", 0),
                ns=e.get("num_secciones", 0),
                nc=e.get("num_categorias", 0),
            )
        )
        if secs:
            lines.append("    secciones: [" + " ; ".join(secs) + "]")
        if cats:
            lines.append("    categorías: [" + " ; ".join(cats) + "]")
    lines.append("")
    # ── Índice inverso por categoría (cat → títulos) ─────────────────
    # Solo categorías con ≥2 artículos para no inflar el contexto con
    # categorías triviales de un solo artículo (que ya están en el catálogo).
    lines.append("ÍNDICE INVERSO POR CATEGORÍA (categoría → artículos que la tienen, solo categorías con ≥2 artículos):")
    for cat, titles in sorted(cats_index.items()):
        if len(titles) < 2:
            continue
        lines.append(f"- {cat}: [" + " ; ".join(titles) + "]")
    return "\n".join(lines)
class WikiPrompts:
    """Prompts centrados en respuestas enciclopédicas basadas en artículos de Wikipedia."""
    # ------------------------------------------------------------------
    # Prompt principal de generación
    # ------------------------------------------------------------------
    @staticmethod
    def generation(query: str, context: list[dict], max_chars: int, language: str = "es") -> str:
        context_text = ""
        unique_docs: set = set()
        for i, chunk in enumerate(context, 1):
            title     = chunk.get("title", "Sin título")
            content   = chunk.get("content", "")
            doc_title = chunk.get("doc_title", "Unknown")
            content_preview = content[:800] + ("..." if len(content) > 800 else "")
            context_text += (
                f"\n[ARTÍCULO {i}]: {doc_title}\n"
                f"Sección: {title}\nContenido:\n{content_preview}\n---\n"
            )
            unique_docs.add(doc_title)
        num_docs = len(unique_docs)
        catalog_block = _format_catalog(language)
        catalog_section = (
            f"\n**CATÁLOGO COMPLETO DEL CORPUS WIKIPEDIA (autoritativo y exhaustivo):**\n"
            f"{catalog_block}\n"
            if catalog_block else ""
        )
        return f"""Eres un asistente enciclopédico que responde preguntas de conocimiento general
basándose en artículos de Wikipedia y en los metadatos exhaustivos del corpus.
{catalog_section}
**FRAGMENTOS RECUPERADOS – {num_docs} artículos únicos en este lote:**
{context_text}
**PREGUNTA:**
{query}
**INSTRUCCIONES:**
[1] FUENTES:
   - Para preguntas de **catálogo / conteo / listado / metadatos / categorías / secciones / existencia**
     (cuántos artículos hay, lista todos los X, qué artículos pertenecen a la categoría Y, qué categorías
     tiene el artículo Z, qué secciones contiene, URL/pageid/fecha de descarga, artículo más largo/corto,
     artículos cuyo título empieza por una letra, etc.), USA EL CATÁLOGO COMPLETO. Es exhaustivo:
     cubre TODOS los artículos del corpus, no solo los recuperados como fragmentos.
   - Para **contenido específico** del cuerpo del artículo (qué dice, definiciones, explicaciones,
     fechas dentro del texto, etc.), usa los FRAGMENTOS RECUPERADOS y cita literalmente cuando ayude.
   - Si la pregunta solicita una lista de artículos, devuelve EXACTAMENTE los títulos tal y como
     aparecen en el catálogo. No omitas ninguno y no añadas inventados.
   - Si la pregunta pide una URL, un pageid o una fecha de descarga, devuélvelos literalmente desde
     el catálogo (no son texto del artículo).
[2] EXHAUSTIVIDAD EN LISTADOS:
   - Cuando se pida "todos los artículos", "lista completa" o "qué artículos pertenecen a X",
     enumera TODOS los que aparecen en el catálogo / índice inverso, sin truncar.
   - Cuando se pida un conteo, da primero el número exacto y luego (si procede) el desglose.
[2b] PREGUNTAS ANALÍTICAS SOBRE EL CATÁLOGO (top-N, filtros, intersecciones, agregados):
   - Para preguntas como "los 5 artículos con MÁS/MENOS X", "artículos cuyo título cumple un patrón",
     "qué artículos NO tienen ninguna categoría", "qué pares de artículos comparten ≥N categorías",
     "qué categorías aparecen en ≥N artículos", "qué dos artículos comparten más categorías",
     "cuántos títulos empiezan por vocal", etc., RECORRE EL CATÁLOGO COMPLETO Y CALCULA TÚ MISMO:
       a) Itera sobre TODOS los artículos del CATÁLOGO DE ARTÍCULOS (no solo los fragmentos).
       b) Aplica el filtro/criterio exacto que pide la pregunta.
       c) Si pide intersecciones, compara categorías de pares (i,j) artículo a artículo.
       d) Si pide top-N, ordena por la métrica solicitada y devuelve EXACTAMENTE N (con desempates por título).
       e) Devuelve un conteo total cuando proceda y a continuación la lista exhaustiva.
   - Para "una sola palabra": el título no contiene espacios, ni paréntesis, ni guiones.
   - Para "paréntesis disambiguador": el título contiene "(".
   - Para "vocal mayúscula": la primera letra del título es A, E, I, O o U (mayúscula).
   - NUNCA respondas con un subconjunto incompleto cuando los datos están en el catálogo.
[3] FORMATO DE RESPUESTA (Markdown):
**Respuesta:** [respuesta directa y concisa; si piden un número o un listado, dalo primero]
**Detalle:** [explicación complementaria si aporta valor; opcional]
**Fuentes:**
- [Título del artículo Wikipedia o "catálogo del corpus"] – [sección u origen]
[4] PRECISIÓN:
   - Cuando un artículo esté en el catálogo pero no en los fragmentos, sigue contestando usando
     los metadatos del catálogo en vez de decir "no está en los fragmentos".
   - No inventes artículos, categorías, URLs ni pageids que no aparezcan en el catálogo.
[5] IDIOMA: Responde en {config.get_lang_name(language)}.
Máximo {max_chars} caracteres."""
    # ------------------------------------------------------------------
    # Prompt de RAG Fusion (adaptado al dominio enciclopédico)
    # ------------------------------------------------------------------
    @staticmethod
    def rag_fusion(query: str, k: int) -> str:
        return f"""Eres un experto en búsqueda de información enciclopédica y conocimiento general.
Pregunta original: "{query}"
Genera {k} versiones alternativas de esta pregunta para buscar en artículos de Wikipedia que:
- Usen términos alternativos o sinónimos del concepto principal
- Amplíen a conceptos relacionados, causas o consecuencias
- Rephraseén desde distintos ángulos (histórico, científico, geográfico, etc.)
- Varíen el nivel de abstracción (general ↔ específico)
Responde ÚNICAMENTE con las {k} preguntas reformuladas, una por línea, numeradas.
Ejemplo:
1. [reformulación con sinónimos o términos alternativos]
2. [reformulación desde otro ángulo temático]
..."""
