"""
src.generate_data.runner
Runner para generación de datos sintéticos de prueba (CVs, EUs, Wikipedia)
Ejecuta cada módulo de generación y validación, con manejo de errores para facilitar debugging
Uso:
    python -m src.generate_data.runner
Este script ejecuta en orden:
    1. Generación de CVs sintéticos
    2. Generación de documentos legislativos EU
    3. Generación de artículos de Wikipedia
    4. Validación de todos los datos contra esquemas JSON
"""
import traceback
import src.generate_data.generate_cvs as generate_cvs
import src.generate_data.generate_eu as generate_eu
import src.generate_data.generate_wiki as generate_wiki
import src.generate_data.validate_data as validate
def main():
    print("Generating CV's...")
    try:
        generate_cvs.main()
    except Exception as e:
        print(f"\nError during CV's generation: {e}")
        traceback.print_exc()
    print("Generating EU documents...")
    try:
        generate_eu.main()
    except Exception as e:
        print(f"\nError during EU documents generation: {e}")
        traceback.print_exc()
    print("Generating Wikipedia data...")
    try:
        generate_wiki.main()
    except Exception as e:
        print(f"\nError during wikipedia documents generation: {e}")
        traceback.print_exc()
    print("Validating data...")
    try:
        validate.main()
    except Exception as e:
        print(f"\nError during validation: {e}")
        traceback.print_exc()
if __name__ == "__main__":
    main()
