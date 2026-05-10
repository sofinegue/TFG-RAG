"""Genera todos los ficheros de prompts extraibles en data/prompts.

Uso:
    python -m src.scripts.extract_all_prompts
"""

from src.scripts import (
    generate_cvs_prompts,
    generate_eu_prompts,
    generate_wiki_prompts,
)


GENERATORS = (
    ("CVs", generate_cvs_prompts.generate),
    ("EU", generate_eu_prompts.generate),
    ("Wikipedia", generate_wiki_prompts.generate),
)


def main() -> None:
    for label, generate in GENERATORS:
        print(f"Generando prompts de {label}...")
        generate()


if __name__ == "__main__":
    main()