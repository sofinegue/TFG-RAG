"""Utilidades comunes para exportar prompts a ficheros de texto"""
from __future__ import annotations
from pathlib import Path
class PromptExportBuilder:
    def __init__(self) -> None:
        self._sections: list[str] = []
    @staticmethod
    def separator(label: str) -> str:
        line = "=" * 80
        return f"\n\n{line}\n  {label}\n{line}\n\n"
    def add(self, content: str) -> None:
        self._sections.append(content)
    def add_section(self, label: str, *parts: str) -> None:
        self._sections.append(self.separator(label))
        self._sections.extend(parts)
    def render(self) -> str:
        return "\n".join(self._sections)
def write_prompt_export(output_file: str, output_text: str, success_label: str) -> None:
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output_text, encoding="utf-8")
    print(f"✅ Prompts {success_label} generados en {output_path} ({len(output_text)} caracteres)")
