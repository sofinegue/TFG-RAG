"""Genera ``data/wikipedia/catalog.json`` con metadatos del corpus Wikipedia.

Estructura:
``{lang: {"articulos": [...], "stats": {...}, "categorias": {cat: [titulos...]}}}``

Cada artículo contiene: titulo, url, pageid, idioma, fecha_descarga,
num_palabras, num_secciones, secciones, categorias (limpias) y
num_categorias.

Uso:
    python -m test.scripts.build_wiki_catalog
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WIKI_DIR = REPO_ROOT / "data" / "wikipedia"
OUT_PATH = WIKI_DIR / "catalog.json"

LANGS = ["en", "es"]

# Prefijos de categorías administrativas/internas a descartar.
# IMPORTANTE: usar EXACTAMENTE los mismos prefijos que el gold standard
# (test/gold_standard/generar_gold_standard_wikipedia_*.py) para que los
# conteos derivados coincidan con las respuestas esperadas.
_BLACKLIST_PREFIXES = (
    "Wikipedia:", "Articles ", "All ", "Short description", "Commons",
    "CS1 ", "Webarchive", "Use ", "Pages ", "Accuracy",
)


def _clean_categories(cats: List[str]) -> List[str]:
    out: List[str] = []
    for c in cats or []:
        c = c.replace("Category:", "").replace("Categoría:", "").strip()
        if not c:
            continue
        if any(c.startswith(p) for p in _BLACKLIST_PREFIXES):
            continue
        out.append(c)
    return out


_SEC_RE = re.compile(r"^={2,3}\s*(.+?)\s*={2,3}", re.MULTILINE)


def _extract_sections(text: str) -> List[str]:
    return [s.strip() for s in _SEC_RE.findall(text or "")]


def _build_entry(art: Dict) -> Dict:
    contenido = art.get("contenido", "") or ""
    secs = _extract_sections(contenido)
    cats = _clean_categories(art.get("categorias", []))
    return {
        "titulo": art.get("titulo", ""),
        "url": art.get("url", ""),
        "pageid": art.get("pageid"),
        "idioma": art.get("idioma", ""),
        "fecha_descarga": art.get("fecha_descarga", ""),
        "num_palabras": len(contenido.split()),
        "num_categorias": len(cats),
        "num_secciones": len(secs),
        "secciones": secs,
        "categorias": cats,
    }


def _build_lang(lang: str) -> Dict | None:
    json_dir = WIKI_DIR / lang / "json"
    if not json_dir.is_dir():
        return None

    articulos: List[Dict] = []
    for fp in sorted(json_dir.glob("*.json")):
        try:
            art = json.loads(fp.read_text(encoding="utf-8"))
            articulos.append(_build_entry(art))
        except Exception as exc:
            print(f"[warn] {fp.name}: {type(exc).__name__}: {exc}")

    # Inverso: categoría → títulos
    idx_categoria: Dict[str, List[str]] = defaultdict(list)
    for e in articulos:
        for c in e["categorias"]:
            idx_categoria[c].append(e["titulo"])
    idx_categoria = {k: sorted(v) for k, v in sorted(idx_categoria.items())}

    # Aggregates
    if articulos:
        longest = max(articulos, key=lambda e: e["num_palabras"])
        shortest = min(articulos, key=lambda e: e["num_palabras"])
        most_secs = max(articulos, key=lambda e: e["num_secciones"])
        most_cats = max(articulos, key=lambda e: e["num_categorias"])
        avg_palabras = round(sum(e["num_palabras"] for e in articulos) / len(articulos), 1)
        avg_secs = round(sum(e["num_secciones"] for e in articulos) / len(articulos), 1)
        avg_cats = round(sum(e["num_categorias"] for e in articulos) / len(articulos), 1)
        total_palabras = sum(e["num_palabras"] for e in articulos)
        top5_cats = Counter({c: len(t) for c, t in idx_categoria.items()}).most_common(5)
    else:
        longest = shortest = most_secs = most_cats = None
        avg_palabras = avg_secs = avg_cats = total_palabras = 0
        top5_cats = []

    stats = {
        "total_articulos": len(articulos),
        "total_categorias_unicas": len(idx_categoria),
        "total_palabras": total_palabras,
        "promedio_palabras_por_articulo": avg_palabras,
        "promedio_secciones_por_articulo": avg_secs,
        "promedio_categorias_por_articulo": avg_cats,
        "articulo_mas_largo": longest and {"titulo": longest["titulo"], "palabras": longest["num_palabras"]},
        "articulo_mas_corto": shortest and {"titulo": shortest["titulo"], "palabras": shortest["num_palabras"]},
        "articulo_mas_secciones": most_secs and {"titulo": most_secs["titulo"], "secciones": most_secs["num_secciones"]},
        "articulo_mas_categorias": most_cats and {"titulo": most_cats["titulo"], "categorias": most_cats["num_categorias"]},
        "top5_categorias_con_mas_articulos": [{"categoria": c, "num_articulos": n} for c, n in top5_cats],
    }

    return {
        "articulos": articulos,
        "categorias": idx_categoria,
        "stats": stats,
    }


def main() -> None:
    catalog: Dict[str, Dict] = {}
    for lang in LANGS:
        info = _build_lang(lang)
        if info is None:
            print(f"[skip] {WIKI_DIR / lang} no existe")
            continue
        catalog[lang] = info
        print(f"  {lang}: {info['stats']['total_articulos']} artículos, "
              f"{info['stats']['total_categorias_unicas']} categorías únicas")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nCatálogo escrito en {OUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
