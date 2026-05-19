"""
CvsHistory — gestión del historial de consultas de CVs
Estructura del JSON:
{
  "entries": [
    {
      "id": "uuid",
      "timestamp": "ISO-8601",
      "question": "pregunta del usuario",
      "results": [
        {
          "reliability": 0.9,
          "data": ["Nombre Apellido", ...],
          "reasoning": "explicación"
        },
        ..
      ]
    }
  ]
}
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
class CvsHistory:
    """Lee y escribe el historial de consultas de CVs en un JSON local"""
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps({"entries": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------
    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"entries": []}
    def _save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def add_entry(
        self,
        query: str,
        groups: dict[str, dict],
        language: str = "es",
    ) -> str:
        """
        Añade una entrada al historial y devuelve su ID
        Convierte el dict de grupos al formato plano:
        {
          "question": "...",
          "results": [
            {"reliability": 0.9, "data": [...], "reasoning": "..."},
            ..
          ]
        }
        """
        data = self._load()
        entry_id = str(uuid.uuid4())
        # Convertir groups dict → results array con reliability numérico
        results = []
        for gname in ("grupo1", "grupo2", "grupo3", "grupo4", "grupo5"):
            g = groups.get(gname)
            if not g:
                continue
            raw_data = g.get("data", "ninguno")
            # Normalizar data a lista
            if isinstance(raw_data, list):
                data_list = raw_data
            elif isinstance(raw_data, str) and raw_data.lower() != "ninguno":
                data_list = [name.strip() for name in raw_data.split("|") if name.strip()]
            else:
                data_list = []
            results.append({
                "reliability": g.get("reliability_score", 0.0),
                "data":        data_list,
                "reasoning":   g.get("reasoning", ""),
            })
        entry = {
            "id":        entry_id,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "question":  query,
            "language":  language,
            "results":   results,
        }
        data["entries"].append(entry)
        self._save(data)
        return entry_id
    def get_entries(self, last_n: Optional[int] = None) -> list[dict]:
        """Devuelve todas las entradas (o las últimas n)"""
        entries = self._load().get("entries", [])
        if last_n is not None:
            return entries[-last_n:]
        return entries
    def get_entry(self, entry_id: str) -> Optional[dict]:
        """Devuelve una entrada por ID, o None si no existe"""
        for entry in self._load().get("entries", []):
            if entry.get("id") == entry_id:
                return entry
        return None
