import requests
import time
import json
from pathlib import Path
import socket
import urllib3

# Forzar IPv4 (evita fallos IPv6 en Windows)
urllib3.util.connection.HAS_IPV6 = False

# =========================
# CONFIGURACIÓN GENERAL
# =========================

LANGUAGES = ["en", "es"]
MAX_PAGES_PER_LANGUAGE = 1000  # tamaño medio
SLEEP_TIME = 0.5

BASE_DIR = Path("data/wikipedia")

HEADERS = {
    "User-Agent": "TFG-RAG-Wikipedia-Dataset/1.0 (Academic use)"
}

# Categorías CANÓNICAS por idioma
CATEGORIES = {
    "en": [
        "Category:Literature",
        "Category:Writers",
        "Category:Novels",
        "Category:Poetry",
        "Category:Literary movements"
    ],
    "es": [
        "Categoría:Literatura",
        "Categoría:Escritores",
        "Categoría:Novelas",
        "Categoría:Poesía",
        "Categoría:Movimientos literarios"
    ]
}

# =========================
# UTILIDADES API
# =========================

def wikipedia_api(lang, params):
    url = f"https://{lang}.wikipedia.org/w/api.php"
    params["format"] = "json"
    response = requests.get(url, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()

# =========================
# DESCUBRIR PÁGINAS
# =========================

def get_pages_from_category(lang, category, limit=500):
    pages = []
    cont = None

    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmnamespace": 0,
            "cmlimit": min(limit, 500)
        }
        if cont:
            params["cmcontinue"] = cont

        data = wikipedia_api(lang, params)
        members = data["query"]["categorymembers"]
        pages.extend(members)

        cont = data.get("continue", {}).get("cmcontinue")
        if not cont or len(pages) >= limit:
            break

        time.sleep(SLEEP_TIME)

    return pages[:limit]

# =========================
# DESCARGAR CONTENIDO
# =========================

def get_page_content(lang, pageid):
    params = {
        "action": "query",
        "pageids": pageid,
        "prop": "extracts|categories",
        "explaintext": True,
        "cllimit": 20
    }
    data = wikipedia_api(lang, params)
    page = next(iter(data["query"]["pages"].values()))

    if "extract" not in page or len(page["extract"]) < 500:
        return None

    categories = [
        c["title"] for c in page.get("categories", [])
        if not c["title"].lower().startswith("categoría:artículos")
    ]

    return {
        "titulo": page["title"],
        "idioma": lang,
        "pageid": pageid,
        "categorias": categories,
        "url": f"https://{lang}.wikipedia.org/wiki/{page['title'].replace(' ', '_')}",
        "contenido": page["extract"],
        "fecha_descarga": time.strftime('%Y-%m-%dT%H:%M:%SZ')
    }

# =========================
# GUARDAR ARCHIVOS
# =========================

def save_document(lang, doc):
    json_dir = BASE_DIR / lang / "json"
    txt_dir = BASE_DIR / lang / "txt"

    json_dir.mkdir(parents=True, exist_ok=True)
    txt_dir.mkdir(parents=True, exist_ok=True)

    safe_title = doc["titulo"].replace("/", "_")

    with open(json_dir / f"{safe_title}.json", "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    with open(txt_dir / f"{safe_title}.txt", "w", encoding="utf-8") as f:
        f.write(doc["contenido"])

# =========================
# PIPELINE PRINCIPAL
# =========================

def build_dataset():
    print("[*] Construyendo dataset Wikipedia Literatura (ES / EN)")
    print(f"[*] Máx. documentos por idioma: {MAX_PAGES_PER_LANGUAGE}\n")

    for lang in LANGUAGES:
        print(f"\n[*] Idioma: {lang.upper()}")
        collected = {}
        target = MAX_PAGES_PER_LANGUAGE

        for category in CATEGORIES[lang]:
            if len(collected) >= target:
                break

            print(f"[*] Categoría: {category}")
            pages = get_pages_from_category(
                lang,
                category,
                limit=target - len(collected)
            )

            for page in pages:
                if page["pageid"] in collected:
                    continue

                doc = get_page_content(lang, page["pageid"])
                if not doc:
                    continue

                save_document(lang, doc)
                collected[page["pageid"]] = doc["titulo"]

                print(f"[OK] {doc['titulo']}")
                time.sleep(SLEEP_TIME)

                if len(collected) >= target:
                    break

        print(f"[*] Total documentos guardados ({lang}): {len(collected)}")

    print("\n[*] Dataset completado correctamente.")

# =========================
# EJECUCIÓN
# =========================

if __name__ == "__main__":
    build_dataset()
