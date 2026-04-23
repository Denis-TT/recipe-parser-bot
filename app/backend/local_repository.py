import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LocalRecipeRepository:
    """Simple JSON fallback repository for local development."""

    def __init__(self, base_path: str) -> None:
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _file_path(self, user_id: int) -> Path:
        return self._base_path / f"{user_id}.json"

    def _read(self, user_id: int) -> List[Dict[str, Any]]:
        path = self._file_path(user_id)
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, user_id: int, rows: List[Dict[str, Any]]) -> None:
        self._file_path(user_id).write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def save_recipe(self, user_id: int, recipe_data: Dict[str, Any]) -> Dict[str, Any]:
        rows = self._read(user_id)
        recipe = dict(recipe_data)
        recipe["id"] = recipe.get("id") or str(uuid.uuid4())
        recipe["user_id"] = user_id
        recipe["created_at"] = recipe.get("created_at") or datetime.utcnow().isoformat()
        rows.insert(0, recipe)
        self._write(user_id, rows)
        return recipe

    def get_categories(self, user_id: int) -> List[Dict[str, Any]]:
        rows = self._read(user_id)
        grouped: Dict[str, int] = {}
        for row in rows:
            key = row.get("meal_type", "other")
            grouped[key] = grouped.get(key, 0) + 1
        return [{"key": key, "count": count} for key, count in grouped.items()]

    def get_recipes_in_category(self, user_id: int, category: str) -> List[Dict[str, Any]]:
        rows = self._read(user_id)
        return [row for row in rows if row.get("meal_type", "other") == category]

    def get_recipe(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        for user_file in self._base_path.glob("*.json"):
            rows = json.loads(user_file.read_text(encoding="utf-8"))
            for row in rows:
                if row.get("id") == recipe_id:
                    return row
        return None

    def delete_recipe(self, recipe_id: str, user_id: int) -> bool:
        rows = self._read(user_id)
        filtered = [row for row in rows if row.get("id") != recipe_id]
        if len(filtered) == len(rows):
            return False
        self._write(user_id, filtered)
        return True
