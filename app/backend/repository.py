from typing import Any, Dict, List, Optional, Protocol


class RecipeRepository(Protocol):
    def save_recipe(self, user_id: int, recipe_data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def get_categories(self, user_id: int) -> List[Dict[str, Any]]:
        ...

    def get_recipes_in_category(self, user_id: int, category: str) -> List[Dict[str, Any]]:
        ...

    def get_recipe(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        ...

    def delete_recipe(self, recipe_id: str, user_id: int) -> bool:
        ...
