from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

class PatternLibrary:
    """
    JSON-backed library under ./pattern_library.

    File schema (new):
    {
      "name": "...",
      "type": "multi",
      "devices": { "buzz":[...], "pulse":[...], "motion":[...] },
      "params":  { "buzz":{...}, "pulse":{...}, "motion":{...} },
      "data_merged": { "steps":[...] },              # merged timeline
      "data_by_type": { "buzz":{...}, "pulse":{...}, "motion":{...} },
      "created_at": "...",
      "version": 2
    }

    Backward compatibility: we also keep "data" (alias of data_merged).
    """
    def __init__(self, folder: str | Path = "pattern_library") -> None:
        self.root = Path(folder)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        safe = "".join(c for c in name if c.isalnum() or c in "-_ ")
        return self.root / f"{safe}.json"

    def save_item(
        self,
        name: str,
        ptype: str,
        devices: Any,
        params: Any,
        data_merged: Dict[str, Any],
        data_by_type: Dict[str, Any] | None = None,
    ) -> None:
        payload = dict(
            name=name,
            type=ptype,
            devices=devices,
            params=params,
            data=data_merged,            # alias for backward compatibility
            data_merged=data_merged,     # explicit merged timeline
            data_by_type=data_by_type or {},  # per-type timelines
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            version=2,
        )
        path = self._path(name)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def load_item(self, name: str) -> Optional[Dict[str, Any]]:
        path = self._path(name)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def delete_item(self, name: str) -> bool:
        path = self._path(name)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_items(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for p in sorted(self.root.glob("*.json")):
            try:
                with p.open("r", encoding="utf-8") as f:
                    j = json.load(f)
                out.append({
                    "name": j.get("name", p.stem),
                    "type": j.get("type", "?"),
                    "created_at": j.get("created_at", "?"),
                })
            except Exception:
                continue
        return out
