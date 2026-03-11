"""
src.document_ingestion.runner

Runner principal para el pipeline de ingesta de documentos.
Ejecuta secuencialmente los runners de cada colección:
  - CVs       → src.document_ingestion.cvs.runner_cvs
  - EU        → src.document_ingestion.eu.runner_eu
  - Wikipedia → src.document_ingestion.wiki.runner_wiki
"""

import traceback

import src.document_ingestion.cvs.runner_cvs as runner_cvs
import src.document_ingestion.eu.runner_eu as runner_eu
import src.document_ingestion.wiki.runner_wiki as runner_wiki


def main():
    print("Procesando CVs...")
    try:
        runner_cvs.main()
    except Exception as e:
        print(f"\nError durante el chunking de CVs: {e}")
        traceback.print_exc()

    print("Procesando documentos EU...")
    try:
        runner_eu.main()
    except Exception as e:
        print(f"\nError durante el chunking de documentos EU: {e}")
        traceback.print_exc()

    print("Procesando artículos de Wikipedia...")
    try:
        runner_wiki.main()
    except Exception as e:
        print(f"\nError durante el chunking de Wikipedia: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
