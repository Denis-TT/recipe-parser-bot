import logging
from typing import Any, Dict, List, Optional

from supabase import Client, create_client

from app.shared.constants import MEAL_TYPE_ALIASES, SUPPORTED_MEAL_TYPES

logger = logging.getLogger(__name__)


class SupabaseRecipeRepository:
    def __init__(self, url: str, key: str) -> None:
        self._client: Client = create_client(url, key)

    def save_recipe(self, user_id: int, recipe_data: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(recipe_data)
        payload["meal_type"] = self._normalize_meal_type(payload.get("meal_type"))
        payload["user_id"] = user_id
        result = self._client.table("recipes").insert(payload).execute()
        if not result.data:
            logger.error("Supabase insert returned empty data for user_id=%s", user_id)
            raise RuntimeError("Failed to save recipe: Supabase returned no data.")
        return result.data[0]

    @staticmethod
    def _normalize_meal_type(value: Any) -> str:
        normalized = str(value or "").strip().lower()
        normalized = MEAL_TYPE_ALIASES.get(normalized, normalized or "other")
        if normalized not in SUPPORTED_MEAL_TYPES:
            return "other"
        return normalized

    def get_categories(self, user_id: int) -> List[Dict[str, Any]]:
        result = self._client.rpc("get_user_categories", {"p_user_id": user_id}).execute()
        return result.data or []

    def get_recipes_in_category(self, user_id: int, category: str) -> List[Dict[str, Any]]:
        result = (
            self._client.table("recipes")
            .select("id,title,meal_type,cook_time,total_time,nutrition_per_serving,created_at")
            .eq("user_id", user_id)
            .eq("meal_type", category)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []

    def get_recipe(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        result = self._client.table("recipes").select("*").eq("id", recipe_id).limit(1).execute()
        return result.data[0] if result.data else None

    def delete_recipe(self, recipe_id: str, user_id: int) -> bool:
        result = (
            self._client.table("recipes")
            .delete()
            .eq("id", recipe_id)
            .eq("user_id", user_id)
            .execute()
        )
        return bool(result.data)
