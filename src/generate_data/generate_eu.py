"""
pruebas.py  Scraping del Diario Oficial de la UE (serie L)
Descarga todos los PDFs publicados en enero y febrero de 2026
en el idioma configurado (por defecto ES)
URL de índice diario:
  https://eur-lex.europa.eu/oj/daily-view/L-series/default.html?ojDate=DDMMYYYY
URL de PDF por documento:
  https://eur-lex.europa.eu/legal-content/{LANG}/TXT/PDF/?uri=OJ:L_{YEAR}{NUM:05d}
"""
import os
import re
import time
import requests
import urllib.request
from pathlib import Path
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
BASE = "https://eur-lex.europa.eu"
TRANSIENT = {202, 429, 500, 502, 503, 504}
OUTPUT_DIR = Path("data/eu")
LANG =  ["ES", "EN", "FR", "IT", "PT"]
# Fechas a procesar
DATES = [
    # date(2025, 12, 1),
    date(2026, 1, 1),
    date(2026, 2, 1),
    # date(2026, 3, 1),
]
# Hilos concurrentes para descargas
DOWNLOAD_WORKERS = 5
# =====================================================================
# 1) SESION Y SELENIUM
# =====================================================================
def _detect_proxy() -> str | None:
    """Devuelve la URL del proxy HTTP del sistema (si existe)"""
    proxies = urllib.request.getproxies()
    return proxies.get("https") or proxies.get("http")
def make_session(lang: str = "ES") -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; SofiaRAGBot/1.0; +https://example.org)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": f"{lang.lower()},{lang.lower()}-en;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    proxy = _detect_proxy()
    if proxy:
        print(f"[PROXY] Usando proxy del sistema: {proxy}")
        s.proxies = {"http": proxy, "https": proxy}
    return s
def make_driver() -> webdriver.Edge:
    """Abre Edge con el proxy del sistema y tolerancia a errores SSL corporativos"""
    opts = Options()
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_argument("--ignore-certificate-errors")
    opts.add_argument("--ignore-ssl-errors")
    opts.add_argument("--allow-insecure-localhost")
    proxy = _detect_proxy()
    if proxy:
        # Eliminar el esquema para Selenium (espera host:puerto)
        proxy_host = proxy.replace("https://", "").replace("http://", "").rstrip("/")
        opts.add_argument(f"--proxy-server={proxy_host}")
        print(f"[PROXY] Edge usando proxy: {proxy_host}")
    return webdriver.Edge(options=opts)
def sync_cookies(driver: webdriver.Edge, session: requests.Session):
    """Copia las cookies del driver a la sesion de requests"""
    for c in driver.get_cookies():
        session.cookies.set(c["name"], c["value"])
# =====================================================================
# 2) DOWNLOAD CON RETRY / BACKOFF
# =====================================================================
def download_binary(session: requests.Session, url: str, out_path: str,
                    max_retries: int = 8, timeout: int = 60):
    backoff = 1.0
    last_err = None
    for attempt in range(max_retries):
        try:
            r = session.get(url, timeout=timeout, allow_redirects=True, stream=True)
        except requests.exceptions.ConnectionError as exc:
            last_err = exc
            print(f"  [RETRY {attempt+1}/{max_retries}] ConnectionError: {exc} — esperando {backoff:.1f}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
            continue
        if r.status_code == 200:
            ct = r.headers.get("Content-Type", "").lower()
            if "pdf" not in ct:
                raise RuntimeError(
                    f"Respuesta no es PDF (Content-Type: {ct}): {url}"
                )
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=16384):
                    if chunk:
                        f.write(chunk)
            return
        if r.status_code in TRANSIENT:
            ra = r.headers.get("Retry-After")
            sleep_s = float(ra) if (ra and ra.isdigit()) else backoff
            print(f"  [RETRY {attempt+1}/{max_retries}] HTTP {r.status_code} — esperando {sleep_s:.1f}s")
            time.sleep(sleep_s)
            backoff = min(backoff * 1.8, 30.0)
            continue
        # Error no transitorio
        time.sleep(backoff)
        backoff = min(backoff * 1.8, 30.0)
    raise RuntimeError(f"No se pudo descargar {url} tras {max_retries} intentos; último error: {last_err}")
# =====================================================================
# 3) SCRAPING DEL INDICE DIARIO
# =====================================================================
def oj_daily_url(d: date) -> str:
    """URL del indice diario en formato ojDate=DDMMYYYY"""
    return (
        f"{BASE}/oj/daily-view/L-series/default.html"
        f"?ojDate={d.strftime('%d%m%Y')}"
    )
def extract_oj_uris(html: str) -> list:
    """
    Extrae todos los URIs OJ:L_* unicos del HTML del indice diario
    Detecta patrones como: uri=OJ:L_202600477
    """
    return sorted(set(re.findall(r"(OJ:L_\d+)", html)))
def fetch_daily_page(driver: webdriver.Edge, session: requests.Session,
                     d: date, timeout: float = 10.0) -> str:
    """
    Carga la pagina del indice diario con Selenium y espera a que
    aparezca contenido real (links OJ o mensaje de no publicaciones)
    en vez de dormir un tiempo fijo
    """
    url = oj_daily_url(d)
    driver.get(url)
    try:
        # Espera hasta que aparezca al menos un enlace OJ:L o el bloque de contenido
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "a[href*='OJ:L_'], .ojDailyViewContent, #documentView")
            )
        )
    except Exception:
        pass  # Si expira, usamos lo que hay
    sync_cookies(driver, session)
    return driver.page_source
# =====================================================================
# 4) DESCARGA DE PDFs
# =====================================================================
def pdf_url(oj_uri: str, lang: str) -> str:
    return f"{BASE}/legal-content/{lang.upper()}/TXT/PDF/?uri={oj_uri}"
def download_oj_pdf(session: requests.Session, oj_uri: str,
                    lang: str, out_dir: Path):
    safe = oj_uri.replace(":", "_")
    out_path = out_dir / f"{safe}_{lang.upper()}.pdf"
    if out_path.exists() and out_path.stat().st_size > 0:
        return f"SKIP {out_path.name}"
    url = pdf_url(oj_uri, lang)
    try:
        download_binary(session, url, str(out_path))
        return f"OK   {out_path.name}"
    except RuntimeError as e:
        return f"ERR  {oj_uri}: {e}"
# =====================================================================
# 5) MAIN — dos fases: scraping (Selenium) + descarga (paralelo)
# =====================================================================
def main():
    for lang in LANG:
        session = make_session(lang)
        driver = make_driver()
        print("[INIT] Cargando EUR-Lex para obtener cookies WAF...")
        driver.get(BASE)
        # Espera a que cargue la portada antes de continuar
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        sync_cookies(driver, session)
        print("[INIT] Cookies obtenidas.\n")
        # ------------------------------------------------------------------
        # FASE 1: Scraping secuencial con Selenium — recoge todos los URIs
        # ------------------------------------------------------------------
        print("[FASE 1] Scraping de índices diarios...\n")
        work_items = []  # lista de (session, uri, lang, out_dir)
        for d in DATES:
            out_dir = OUTPUT_DIR / lang.lower()
            out_dir.mkdir(parents=True, exist_ok=True)
            print(f"  [DATE] {d}  ", end="", flush=True)
            html = fetch_daily_page(driver, session, d)
            uris = extract_oj_uris(html)
            if not uris:
                print("sin publicaciones")
            else:
                print(f"{len(uris)} doc(s)")
                for uri in uris:
                    work_items.append((session, uri, lang, out_dir))
        driver.quit()
        # ------------------------------------------------------------------
        # FASE 2: Descargas en paralelo
        # ------------------------------------------------------------------
        total = len(work_items)
        print(f"\n[FASE 2] Descargando {total} PDFs con {DOWNLOAD_WORKERS} hilos...\n")
        done = 0
        with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
            futures = {
                pool.submit(download_oj_pdf, sess, uri, lg, d): uri
                for sess, uri, lg, d in work_items
            }
            for fut in as_completed(futures):
                done += 1
                try:
                    result = fut.result()
                except Exception as exc:
                    result = f"ERR  {futures[fut]}: {exc}"
                print(f"  [{done}/{total}] {result}")
        print(f"\n[DONE] {total} documentos procesados.")
# if __name__ == "__main__":
#     main()
