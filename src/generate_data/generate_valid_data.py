import traceback

import src.generate_data.generate_cvs as generate_cvs
import src.generate_data.generate_eu as generate_eu
import src.generate_data.generate_wikipedia as generate_wikipedia
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
        generate_wikipedia.main()
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
