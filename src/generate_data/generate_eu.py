import requests
from pathlib import Path
import time

BASE = "https://eur-lex.europa.eu"

OUTPUT_DIR = Path("data/eu")

LANGUAGES = {
    "en": "EN",
    "es": "ES",
    "fr": "FR",
    "pt": "PT",
    "it": "IT"
}

SECTIONS = {
    "legislation": {
        "pdf_base": "legislation",
        "classification": "in-force"
    },
    "legislation-preparation": {
        "pdf_base": "legislation-preparation",
        "classification": "pending"
    },
    "inter-agree": {
        "pdf_base": "inter-agree",
        "classification": "in-force"
    }
}

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def download_pdf(url, out_path):
    if out_path.exists():
        return False

    r = requests.get(url, headers=HEADERS, stream=True, timeout=30)
    if r.status_code == 200 and "application/pdf" in r.headers.get("Content-Type", ""):
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return True
    return False

def run():
    print("Descargando capitulos EUR-Lex (multilenguaje)")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for lang_code, lang_name in LANGUAGES.items():
        lang_dir = OUTPUT_DIR / lang_name.lower()
        lang_dir.mkdir(exist_ok=True)

        print(f"\nIdioma: {lang_name}")

        for section, info in SECTIONS.items():
            print(f"  {section}")

            for chapter in range(1, 21):
                chapter_str = f"{chapter:02d}"
                file_code = f"20{chapter_str}"
                file_name = f"{section}_{file_code}.pdf"

                pdf_url = (
                    f"{BASE}/browse/pdf/directories/{info['pdf_base']}.html"
                    f"?file=chapter%20{chapter_str}.pdf"
                    f"&classification={info['classification']}"
                )

                out_path = lang_dir / file_name

                ok = download_pdf(pdf_url, out_path)

                if ok:
                    print(f"    [OK] {file_name}")
                else:
                    print(f"    [WARNING] {file_name} no disponible")

                time.sleep(0.5)

    print("\nDESCARGA COMPLETADA")

if __name__ == "__main__":
    run()
