"""
Extrae el texto de los PDFs de la UE y los guarda como JSON.
Genera un archivo JSON por cada PDF con estructura:
  {
    "archivo": "nombre_archivo.pdf",
    "idioma": "es",
    "num_paginas": N,
    "contenido": "texto completo",
    "paginas": ["texto pag 1", "texto pag 2", ...]
  }
"""

import json
import logging
import pdfplumber
from pathlib import Path

# Silenciar el logging verbose de pdfminer que causa problemas
logging.getLogger("pdfminer").setLevel(logging.WARNING)

DATA_DIR = Path(__file__).parent.parent.parent
EU_DIR = DATA_DIR / "eu"

for lang_dir in sorted(EU_DIR.iterdir()):
    if not lang_dir.is_dir():
        continue
    idioma = lang_dir.name  # "es", "en", etc.
    
    # Crear carpeta json de salida dentro de eu/<idioma>/
    out_dir = lang_dir / "json"
    out_dir.mkdir(exist_ok=True)
    
    pdfs = sorted(lang_dir.glob("*.pdf"))
    print(f"\n{'='*60}")
    print(f"Idioma: {idioma} — {len(pdfs)} PDFs encontrados")
    print(f"{'='*60}")
    
    for pdf_path in pdfs:
        out_file = out_dir / (pdf_path.stem + ".json")
        if out_file.exists():
            print(f"  Saltando (ya existe): {pdf_path.name}")
            continue
        print(f"  Procesando: {pdf_path.name} ... ", end="", flush=True)
        try:
            with pdfplumber.open(pdf_path) as pdf:
                paginas = []
                for i, page in enumerate(pdf.pages):
                    try:
                        text = page.extract_text() or ""
                    except BaseException:
                        text = ""
                    paginas.append(text)
                    if (i + 1) % 100 == 0:
                        print(f"{i+1}/{len(pdf.pages)}...", end="", flush=True)
                
                contenido = "\n\n".join(paginas)
                
                doc = {
                    "archivo": pdf_path.name,
                    "idioma": idioma,
                    "num_paginas": len(paginas),
                    "contenido": contenido,
                    "paginas": paginas
                }
                
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(doc, f, ensure_ascii=False, indent=2)
                
                print(f"OK ({len(paginas)} págs, {len(contenido)} chars)")
        except Exception as e:
            print(f"ERROR: {e}")

print("\n✓ Extracción completada")
