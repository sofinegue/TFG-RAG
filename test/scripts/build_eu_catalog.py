"""Genera ``data/eu/catalog.json`` con metadatos del corpus EU por idioma.

Estructura:
``{lang: [{filename, type, subtype, title, num_pages, num_articles, act_year, act_number, issuer}, ...]}``

Uso:
    python -m test.scripts.build_eu_catalog
"""
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EU_DIR = REPO_ROOT / "data" / "eu"
OUT_PATH = EU_DIR / "catalog.json"

LANGS = ["en", "es", "fr", "it", "pt"]

# Patrones de tipo (mayúsculas y minúsculas, multilenguaje).
TYPE_PATTERNS = [
    ("REGULATION", r"\b(REGULATION|REGLAMENTO|R[ÈE]GLEMENT|REGOLAMENTO|REGULAMENTO)\b"),
    ("DECISION",   r"\b(DECISION|DECISI[ÓO]N|D[ÉE]CISION|DECISIONE|DECIS[ÃA]O)\b"),
    ("DIRECTIVE",  r"\b(DIRECTIVE|DIRECTIVA|DIRETTIVA)\b"),
    ("RECOMMENDATION", r"\b(RECOMMENDATION|RECOMENDACI[ÓO]N|RECOMMANDATION|RACCOMANDAZIONE|RECOMENDA[CÇ][ÃA]O)\b"),
]

# Subtipos (Implementing, Delegated, CFSP/PESC).
SUBTYPE_PATTERNS = [
    ("Implementing", r"(IMPLEMENTING|EJECUCI[ÓO]N|EXECUCI[ÓO]N|EX[EÉ]CUTION|ESECUZIONE|EXECU[CÇ][ÃA]O)"),
    ("Delegated",    r"(DELEGATED|DELEGADO|D[ÉE]L[ÉE]GU[ÉE]|DELEGATO)"),
    ("CFSP",         r"\((CFSP|PESC)\)"),
]

# Issuer (Commission / Council / Parliament).
ISSUER_PATTERNS = [
    ("Commission",  r"(COMMISSION|COMISI[ÓO]N|COMMISSIONE|COMISS[ÃA]O)"),
    ("Council",     r"(COUNCIL|CONSEJO|CONSEIL|CONSIGLIO|CONSELHO)"),
    ("Parliament",  r"(PARLIAMENT|PARLAMENTO|PARLEMENT)"),
    ("EU-Morocco",  r"(EU-?MOROCCO|UE-?MARRUECOS|UE-?MAROC|UE-?MAROCCO|UE-?MARROCOS)"),
]

# Act number p.ej. "2025/2621" o "2026/264".
ACT_NUMBER_RE = re.compile(r"\b(20\d{2})\s*/\s*(\d{2,5})\b")
# "of <day> <month> <year>" multilenguaje. Usado para extraer la fecha de
# adopción del acto (la fecha que aparece justo debajo del título).
ADOPTION_DATE_RE = re.compile(
    r"\b(?:of|de|du|del)\s+\d{1,2}\s+[A-Za-zÀ-ÿñç]+\s+(20\d{2})\b",
    re.I,
)
DATE_YEAR_RE = re.compile(r"\b(20\d{2})\b")
ARTICLE_RES = {
    "en": re.compile(r"(?im)^\s*Article\s+(\d+)"),
    "es": re.compile(r"(?im)^\s*Art[íi]culo\s+(\d+)"),
    "fr": re.compile(r"(?im)^\s*Article\s+(\d+)"),
    "it": re.compile(r"(?im)^\s*Articolo\s+(\d+)"),
    "pt": re.compile(r"(?im)^\s*Artigo\s+(\d+)"),
}


def _detect(patterns, text: str) -> str:
    for label, pat in patterns:
        if re.search(pat, text, re.I):
            return label
    return ""


def _build_entry(lang: str, json_path: Path) -> Dict:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    contenido = data.get("contenido", "") or ""
    head = contenido[:3000]

    archivo = data.get("archivo", json_path.stem)
    filename = Path(archivo).stem  # e.g. OJ_L_202502621_EN

    # Título: primera línea con tipo
    title = ""
    long_title = ""
    head_lines = [ln.strip() for ln in head.splitlines()]
    for idx, line_stripped in enumerate(head_lines):
        if not line_stripped:
            continue
        if re.search(r"(REGULATION|REGLAMENTO|R[ÈE]GLEMENT|REGOLAMENTO|REGULAMENTO|"
                     r"DECISION|DECISI[ÓO]N|D[ÉE]CISION|DECISIONE|DECIS[ÃA]O|"
                     r"DIRECTIVE|DIRECTIVA|DIRETTIVA)", line_stripped, re.I):
            title = line_stripped[:160]
            # Construir long_title concatenando líneas siguientes hasta un punto
            # final o ~600 caracteres (cubre títulos descriptivos largos:
            # "REGULATION (EU) X/Y of <date> on <subject>...").
            buf = [title]
            char_count = len(title)
            for nxt in head_lines[idx + 1: idx + 25]:
                if not nxt:
                    if char_count > 80:
                        break
                    continue
                buf.append(nxt)
                char_count += len(nxt) + 1
                if char_count >= 500 or nxt.endswith("."):
                    break
                # Cortar si la línea siguiente parece un nuevo bloque (tabla,
                # encabezado de capítulo, etc.).
                if re.match(r"(?i)^\s*(TITLE|T[IÍ]TULO|TITRE|TITOLO|"
                            r"CHAPTER|CAP[IÍ]TULO|CHAPITRE|CAPITOLO|"
                            r"WHEREAS|VISTO|CONSIDERANDO|"
                            r"THE EUROPEAN|LE PARLEMENT|EL PARLAMENTO|"
                            r"O PARLAMENTO|IL PARLAMENTO|"
                            r"HAVING REGARD|VU|VISTO|TENDO EM CONTA)",
                            nxt):
                    break
            long_title = " ".join(buf)[:600]
            break
    if not title:
        for line in head_lines:
            if line:
                title = line[:160]
                long_title = title
                break

    type_ = _detect(TYPE_PATTERNS, title) or _detect(TYPE_PATTERNS, head)
    subtype = _detect(SUBTYPE_PATTERNS, title) or _detect(SUBTYPE_PATTERNS, head[:500])
    issuer = _detect(ISSUER_PATTERNS, title) or _detect(ISSUER_PATTERNS, head[:500])

    # act_number "2026/264", act_year (año del acto)
    act_number = ""
    act_year = ""
    m = ACT_NUMBER_RE.search(title)
    if m:
        act_year = m.group(1)
        act_number = f"{m.group(1)}/{m.group(2)}"

    # Fecha "of <day> <month> <year>" → año real de adopción
    # (usado para preguntas "documents from 2025" cuando el filename es 2026 pero la fecha es 2025).
    adoption_year = ""
    title_idx = head.find(title) if title else 0
    after_title = head[title_idx:title_idx + 800]
    m_adopt = ADOPTION_DATE_RE.search(after_title)
    if m_adopt:
        adoption_year = m_adopt.group(1)
    else:
        # Fallback al primer año mencionado tras el título
        years = DATE_YEAR_RE.findall(after_title[len(title):])
        if years:
            adoption_year = years[0]

    pattern = ARTICLE_RES.get(lang) or ARTICLE_RES["en"]
    arts = set(pattern.findall(contenido))
    num_articles = len(arts)

    return {
        "filename":       filename,
        "type":           type_ or "UNKNOWN",
        "subtype":        subtype,
        "title":          title,
        "long_title":     long_title,
        "num_pages":      data.get("num_paginas", 0),
        "num_articles":   num_articles,
        "act_number":     act_number,
        "act_year":       act_year,           # año del número (ej. 2025/2621 → 2025)
        "adoption_year":  adoption_year,      # año de adopción (fecha texto)
        "issuer":         issuer,
    }


def main() -> None:
    catalog: Dict[str, List[Dict]] = {}
    for lang in LANGS:
        json_dir = EU_DIR / lang / "json"
        if not json_dir.is_dir():
            print(f"[skip] {json_dir} no existe")
            continue
        files = sorted(json_dir.glob("*.json"))
        entries = []
        for fp in files:
            try:
                entries.append(_build_entry(lang, fp))
            except Exception as exc:
                print(f"[warn] {fp.name}: {type(exc).__name__}: {exc}")
        catalog[lang] = entries
        print(f"  {lang}: {len(entries)} docs")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nCatálogo escrito en {OUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
