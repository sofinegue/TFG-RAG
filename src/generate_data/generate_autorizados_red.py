import os
import time
import requests
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURACIÓN ---
START_URL = "https://www.seg-social.es/wps/portal/wss/internet/InformacionUtil/5300/07c7073f-f356-499f-8d1f-2bac8d596c5f"
DOWNLOAD_FOLDER = "data/autorizados_red/raw_documents"
DELAY = 2  # segundos de espera para que cargue el contenido dinámico

# Tipos de documentos a descargar
DOC_EXTENSIONS = [".pdf", ".doc", ".docx", ".xls", ".xlsx"]

# --- FUNCIONES AUXILIARES ---
def is_document(url):
    return any(url.lower().endswith(ext) for ext in DOC_EXTENSIONS)

def save_document(url):
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    filename = os.path.join(DOWNLOAD_FOLDER, os.path.basename(url))
    try:
        r = requests.get(url)
        with open(filename, "wb") as f:
            f.write(r.content)
        print(f"✅ Descargado: {filename}")
    except Exception as e:
        print(f"❌ Error descargando {url}: {e}")

def get_domain(url):
    return urlparse(url).netloc

# --- CONFIGURAR SELENIUM ---
chrome_options = Options()
chrome_options.add_argument("--headless")  # Ejecutar en modo headless
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
service = Service()  # Asegúrate de que chromedriver esté en PATH
driver = webdriver.Chrome(service=service, options=chrome_options)

# --- CRAWLER RECURSIVO ---
visited = set()

def crawl(url, base_domain):
    if url in visited:
        return
    visited.add(url)
    print(f"\n🌐 Visitando: {url}")
    driver.get(url)
    time.sleep(DELAY)

    # --- EXPANDIR DESPLEGABLES ---
    try:
        # Buscar elementos tipo accordion o botones de expandir
        buttons = driver.find_elements(By.XPATH, "//button | //a[contains(@class,'accordion')]")
        for btn in buttons:
            try:
                driver.execute_script("arguments[0].scrollIntoView();", btn)
                btn.click()
                time.sleep(0.5)
            except:
                continue
    except:
        pass

    # --- EXTRAER DOCUMENTOS ---
    links = driver.find_elements(By.TAG_NAME, "a")
    for link in links:
        href = link.get_attribute("href")
        if href:
            href = urljoin(url, href)
            if is_document(href):
                save_document(href)

    # --- EXTRAER SUBPÁGINAS INTERNAS ---
    for link in links:
        href = link.get_attribute("href")
        if href:
            href = urljoin(url, href)
            if get_domain(href) == base_domain and href not in visited and not is_document(href):
                crawl(href, base_domain)

# --- INICIO DEL CRAWL ---
try:
    crawl(START_URL, get_domain(START_URL))
finally:
    driver.quit()
    print("\n🎉 Crawl completado!")
