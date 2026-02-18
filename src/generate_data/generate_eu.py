import requests
from pathlib import Path
import time
from selenium import webdriver
from selenium.webdriver.edge.options import Options

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

#     "User-Agent": (
#         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#         "AppleWebKit/537.36 (KHTML, like Gecko) "
#         "Chrome/120.0.0.0 Safari/537.36"
#     ),
#     "Accept": "application/pdf,*/*",
# }

# Return codes for download_pdf
DOWNLOAD_OK = "ok"
DOWNLOAD_CACHED = "cached"
DOWNLOAD_FAILED = "failed"


def refresh_waf_cookies(session):
    """Open Edge, solve the WAF challenge, and update the session cookies."""
    print("    [WAF] Refreshing cookies with Edge...")
    opts = Options()
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    driver = webdriver.Edge(options=opts)
    driver.get(BASE)
    # Wait until the WAF sets at least one cookie (up to 10s max)
    for _ in range(20):
        if driver.get_cookies():
            break
        time.sleep(0.5)
    cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
    driver.quit()
    session.cookies.update(cookies)
    print(f"    [WAF] Cookies refreshed: {list(cookies.keys())}")


def download_pdf(url, out_path, session):
    """Download a PDF from *url* to *out_path*.

    Uses a requests.Session that already carries the WAF cookies.
    If a 202 (WAF challenge) is received, automatically refreshes
    cookies and retries once.
    Returns DOWNLOAD_OK, DOWNLOAD_CACHED, or DOWNLOAD_FAILED.
    """
    if out_path.exists():
        return DOWNLOAD_CACHED

    for attempt in range(2):  # at most 1 retry after cookie refresh
        try:
            r = session.get(url, stream=True, timeout=60)
            content_type = r.headers.get("Content-Type", "")
            # print(f"      HTTP {r.status_code}, Content-Type: {content_type}")

            if 200 <= r.status_code < 300 and "application/pdf" in content_type:
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
                return DOWNLOAD_OK

            # 202 = WAF cookies expired → refresh and retry
            if r.status_code == 202 and attempt == 0:
                refresh_waf_cookies(session)
                continue

        except requests.RequestException as e:
            print(f"      [ERROR] Request failed: {e}")
            if attempt == 0:
                refresh_waf_cookies(session)
                continue

    return DOWNLOAD_FAILED


def main():
    print("Descargando capitulos EUR-Lex (multilenguaje)")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Create session and get initial WAF cookies ---
    session = requests.Session()
    session.headers.update(HEADERS)
    refresh_waf_cookies(session)

    for lang_code, lang_name in LANGUAGES.items():
        lang_dir = OUTPUT_DIR / lang_name.lower()
        lang_dir.mkdir(exist_ok=True)

        # If the language folder already contains the expected number of PDFs,
        # skip scraping to avoid re-downloading and WAF challenges.
        expected_per_lang = len(SECTIONS) * 20
        existing_pdfs = len(list(lang_dir.glob('*.pdf')))
        if existing_pdfs >= expected_per_lang:
            print(f"\nIdioma: {lang_name} - ya completo ({existing_pdfs}/{expected_per_lang}), se omite descarga")
            continue

        print(f"\nIdioma: {lang_name}")

        for section, info in SECTIONS.items():
            print(f"  Section: {section}")

            for chapter in range(1, 21):
                chapter_str = f"{chapter:02d}"
                file_code = f"20{chapter_str}"
                file_name = f"{section}_{file_code}.pdf"

                # Include locale so the correct language version is fetched
                pdf_url = (
                    f"{BASE}/browse/pdf/directories/{info['pdf_base']}.html"
                    f"?file=chapter%20{chapter_str}.pdf"
                    f"&classification={info['classification']}"
                    f"&locale={lang_code}"
                )

                out_path = lang_dir / file_name

                result = download_pdf(pdf_url, out_path, session)

                # if result == DOWNLOAD_OK:
                #     print(f"    [OK]      {file_name}")
                # elif result == DOWNLOAD_CACHED:
                #     print(f"    [CACHED]  {file_name}")
                # else:
                if result == DOWNLOAD_FAILED:
                    print(f"    [WARNING] {file_name} no disponible ({pdf_url})")

                time.sleep(0.5)

    print("\nDESCARGA COMPLETADA")

# if __name__ == "__main__":
#     main()
