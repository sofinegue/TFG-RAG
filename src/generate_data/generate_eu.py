"""
src.generate_data.generate_eu

Módulo para descargar capítulos de legislación europea (EUR-Lex) en PDF, multilenguaje.
"""
import os
import re
import time
import unicodedata
from datetime import datetime
from urllib.parse import urlencode

from anyio import Path
import requests
from bs4 import BeautifulSoup

BASE = "https://eur-lex.europa.eu"

def normalize_lang(lang: str) -> str:
    """EUR-Lex usa códigos tipo EN, ES, FR... en mayúsculas."""
    return (lang or "EN").strip().upper()

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def fetch_html(url: str, max_retries=3, timeout=30):
    for attempt in range(1, max_retries+1):
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200 and resp.text:
            return resp.text
        time.sleep(1.5 * attempt)
    raise RuntimeError(f"Error {resp.status_code} al obtener: {url}")

def guess_display_lang_from_txt_url(txt_url: str) -> str:
    # El patrón clásico es /legal-content/EN/TXT/...
    m = re.search(r"/legal-content/([A-Z]{2})/TXT/", txt_url)
    return m.group(1) if m else "EN"

def extract_consolidated_dates(txt_html: str):
    """
    Extrae la lista de fechas (YYYY-MM-DD) del panel 'Hide/Show consolidated versions'.
    La página actual de EUR-Lex coloca esas fechas en un <nav> lateral con enlaces.
    """
    soup = BeautifulSoup(txt_html, "html.parser")

    # Buscar el bloque lateral por el título aproximado “consolidated versions”
    # Hay variaciones según idioma; buscamos por anclas y patrones de fecha en los href.
    date_links = []

    # 1) Buscar enlaces que contengan .../TXT-YYYYMMDD en la 'uri' query
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        # Nos interesan los que apunten a TXT con sufijo -YYYYMMDD
        if "CELEX:" in href and "/TXT" in href and "-20" in href:
            # Extraer la parte -YYYYMMDD
            m = re.search(r"-([12][0-9]{7})$", href)
            if m:
                yyyymmdd = m.group(1)
                # Validar fecha
                try:
                    dt = datetime.strptime(yyyymmdd, "%Y%m%d")
                    date_links.append((dt.date(), href))
                except ValueError:
                    pass

    # Quitar duplicados y ordenar
    by_date = {}
    for dt, href in date_links:
        by_date[dt] = href
    return [ (d, by_date[d]) for d in sorted(by_date.keys()) ]

def to_pdf_url(celex_consolidated: str, lang: str, date_yyyymmdd: str):
    """
    Construye la URL PDF consolidada de la forma:
    https://eur-lex.europa.eu/legal-content/{LANG}/TXT/PDF/?uri=CELEX:{CELEX_CONSOLIDATED}/TXT-{YYYYMMDD}
    """
    lang = normalize_lang(lang)
    query = {
        "uri": f"CELEX:{celex_consolidated}/TXT-{date_yyyymmdd}"
    }
    return f"{BASE}/legal-content/{lang}/TXT/PDF/?{urlencode(query)}"

def to_txt_page_url(celex_consolidated: str, lang: str, date_yyyymmdd: str):
    """
    Devuelve la URL de la página HTML (no PDF) para inspección si hace falta:
    https://eur-lex.europa.eu/legal-content/{LANG}/TXT/?uri=CELEX:{CELEX_CONSOLIDATED}/TXT-{YYYYMMDD}
    """
    lang = normalize_lang(lang)
    query = {
        "uri": f"CELEX:{celex_consolidated}/TXT-{date_yyyymmdd}"
    }
    return f"{BASE}/legal-content/{lang}/TXT/?{urlencode(query)}"

def to_txt_root_url(celex_base: str, lang: str):
    """
    URL 'raíz' (HTML) desde la cual parsearemos las “consolidated versions”.
    Suele ser la no-consolidada (p. ej. CELEX:12016M/TXT) o directamente la consolidada actual sin fecha.
    """
    lang = normalize_lang(lang)
    query = { "uri": f"CELEX:{celex_base}/TXT" }
    return f"{BASE}/legal-content/{lang}/TXT/?{urlencode(query)}"

def download_pdf(url: str, out_path: str, max_retries=3, timeout=60):
    for attempt in range(1, max_retries+1):
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200 and r.content:
            with open(out_path, "wb") as f:
                f.write(r.content)
            return
        time.sleep(1.5 * attempt)
    raise RuntimeError(f"No se pudo descargar {url}; último status={r.status_code}")

def download_all_consolidated_pdfs(
    celex_base_for_panel: str,
    celex_consolidated_prefix: str,
    lang="EN",
    out_dir="../data/eu/"
):
    """
    - celex_base_for_panel: CELEX cuya página TXT tiene el panel lateral de “consolidated versions”.
        Ej: '12016M' (TEU base) o '12016E' (TFEU base).
    - celex_consolidated_prefix: prefijo CELEX para construir cada PDF consolidado por fecha.
        Ej: '02016M' (TEU consolidado) o '02016E' (TFEU consolidado).
    - lang: idioma del PDF ('EN','ES',...)
    - out_dir: carpeta de salida
    """
    lang = normalize_lang(lang)
    root_url = to_txt_root_url(celex_base_for_panel, lang)
    print(f"[INFO] Cargando página raíz para extraer fechas: {root_url}")
    html = fetch_html(root_url)
    consolidated = extract_consolidated_dates(html)

    if not consolidated:
        # Si no se encuentran enlaces con -YYYYMMDD, intentamos un idioma alternativo para parsear
        alt_lang = "EN" if lang != "EN" else "ES"
        alt_root = to_txt_root_url(celex_base_for_panel, alt_lang)
        print(f"[WARN] No encontré fechas en {lang}; pruebo {alt_lang}: {alt_root}")
        html = fetch_html(alt_root)
        consolidated = extract_consolidated_dates(html)

    if not consolidated:
        raise RuntimeError("No fue posible localizar el panel de fechas consolidadas.")

    print(f"[INFO] Fechas encontradas: {len(consolidated)}")
    # Crear carpeta
    subdir = os.path.join(out_dir, f"{celex_consolidated_prefix}_{lang}")
    ensure_dir(subdir)

    for dt, href in consolidated:
        yyyymmdd = dt.strftime("%Y%m%d")
        pdf_url = to_pdf_url(celex_consolidated_prefix, lang, yyyymmdd)
        filename = f"{celex_consolidated_prefix}_{yyyymmdd}_{lang}.pdf"
        out_path = os.path.join(subdir, filename)

        # Evitar redescargas
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            print(f"  [SKIP] {filename}")
            continue

        print(f"  [GET] {pdf_url}")
        try:
            download_pdf(pdf_url, out_path)
            time.sleep(0.5)  # cortesía
        except Exception as ex:
            print(f"  [ERR] {ex}")

    print(f"[DONE] PDFs guardados en: {subdir}")

def main():
    OUTPUT_DIR = Path("data/eu")

    for lang in ["EN", "ES", "FR", "IT", "PT"]:
        download_all_consolidated_pdfs(
            celex_base_for_panel="12016M",
            celex_consolidated_prefix="02016M",
            lang=lang,              # Cambia a "ES" si quieres PDFs en español
            out_dir=OUTPUT_DIR / lang.lower()
        )
        download_all_consolidated_pdfs(
                celex_base_for_panel="12016E",
                celex_consolidated_prefix="02016E",
                lang=lang,
                out_dir=OUTPUT_DIR / lang.lower()
        )

# if __name__ == "__main__":
#     OUTPUT_DIR = Path("data/eu")

#     for lang in ["EN", "ES", "FR", "IT", "PT"]:
#         download_all_consolidated_pdfs(
#             celex_base_for_panel="12016M",
#             celex_consolidated_prefix="02016M",
#             lang=lang,              # Cambia a "ES" si quieres PDFs en español
#             out_dir=os.path.join(OUTPUT_DIR, lang.lower())
#         )
#         download_all_consolidated_pdfs(
#                 celex_base_for_panel="12016E",
#                 celex_consolidated_prefix="02016E",
#                 lang=lang,
#                 out_dir=os.path.join(OUTPUT_DIR, lang.lower())
#         )