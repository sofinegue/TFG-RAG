"""
CvsHistory — gestión del historial de consultas de CVs.

Estructura del JSON:
{
  "entries": [
    {
      "id": "uuid",
      "timestamp": "ISO-8601",
      "query": "pregunta del usuario",
      "groups": {
        "grupo1": {   // fiabilidad >= 0.90
          "reliability": "≥90%",
          "data": ["Nombre Apellido", ...],
          "reasoning": "Extraído directamente por score ≥ 0.90"
        },
        "grupo2": {
          "reliability": "70-90%",
          "data": "respuesta del mini-LLM",
          "reasoning": "Generado con mini-LLM sobre N chunks"
        },
        ...
      }
    }
  ]
}
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


class CvsHistory:
    """Lee y escribe el historial de consultas de CVs en un JSON local."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps({"entries": []}, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------
    def _load(self) -> Dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"entries": []}

    def _save(self, data: Dict) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def add_entry(
        self,
        query: str,
        groups: Dict[str, Dict],
    ) -> str:
        """
        Añade una entrada al historial y devuelve su ID.

        ``groups`` tiene la forma:
        {
          "grupo1": {"reliability": "...", "data": [...], "reasoning": "..."},
          "grupo2": {"reliability": "...", "data": "...", "reasoning": "..."},
          ...
        }
        """
        data = self._load()
        entry_id = str(uuid.uuid4())
        entry = {
            "id":        entry_id,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "query":     query,
            "groups":    groups,
        }
        data["entries"].append(entry)
        self._save(data)
        return entry_id

    def get_entries(self, last_n: Optional[int] = None) -> List[Dict]:
        """Devuelve todas las entradas (o las últimas n)."""
        entries = self._load().get("entries", [])
        if last_n is not None:
            return entries[-last_n:]
        return entries

    def get_entry(self, entry_id: str) -> Optional[Dict]:
        """Devuelve una entrada por ID, o None si no existe."""
        for entry in self._load().get("entries", []):
            if entry.get("id") == entry_id:
                return entry
        return None
