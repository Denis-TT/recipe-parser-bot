"""
Адаптер хранилища. Автоматически выбирает Supabase если доступен,
иначе использует локальное хранилище.
"""

import os
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Пробуем импортировать Supabase
try:
    from supabase_storage import SupabaseRecipeStorage
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.warning("Supabase не установлен, используется локальное хранилище")

# Локальное хранилище как fallback
from recipe_storage import RecipeStorage as LocalRecipeStorage


class RecipeStorage:
    """
    Универсальное хранилище рецептов.
    Автоматически использует Supabase если доступны ключи.
    """
    
    def __init__(self):
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_KEY")
        
        if SUPABASE_AVAILABLE and supabase_url and supabase_key:
            try:
                self.backend = SupabaseRecipeStorage()
                self.backend_type = "supabase"
                logger.info("🚀 Используется Supabase (облачное хранилище)")
            except Exception as e:
                logger.error(f"Ошибка подключения к Supabase: {e}")
                self.backend = LocalRecipeStorage()
                self.backend_type = "local"
        else:
            self.backend = LocalRecipeStorage()
            self.backend_type = "local"
            logger.info("💾 Используется локальное хранилище")
    
    def save_recipe(self, user_id: int, recipe_data: Dict[str, Any]) -> Any:
        """Сохранение рецепта"""
        return self.backend.save_recipe(user_id, recipe_data)
    
    def get_user_categories(self, user_id: int) -> List[Dict[str, Any]]:
        """Получение категорий пользователя"""
        if self.backend_type == "supabase":
            return self.backend.get_categories(user_id)
        else:
            # Адаптация локального формата
            categories = self.backend.get_categories()
            return categories
    
    def get_recipes_in_category(self, user_id: int, category: str) -> List[Dict[str, Any]]:
        """Получение рецептов в категории"""
        if self.backend_type == "supabase":
            recipes = self.backend.get_user_recipes(user_id, category)
            # Адаптация формата
            return [
                {
                    "title": r.get("title"),
                    "recipe_uid": r.get("id"),
                    "calories": r.get("nutrition_per_serving", {}).get("calories", 0),
                    "cook_time": r.get("total_time", 0),
                    "filename": r.get("id")  # для совместимости
                }
                for r in recipes
            ]
        else:
            return self.backend.get_recipes_list(category)
    
    def get_recipe_by_uid(self, user_id: int, category: str, recipe_uid: str) -> Optional[Dict]:
        """Получение рецепта по UID"""
        if self.backend_type == "supabase":
            return self.backend.get_recipe(recipe_uid)
        else:
            return self.backend.load_recipe(recipe_uid)
    
    def delete_recipe_by_uid(self, user_id: int, category: str, recipe_uid: str) -> bool:
        """Удаление рецепта по UID"""
        if self.backend_type == "supabase":
            return self.backend.delete_recipe(recipe_uid, user_id)
        else:
            return self.backend.delete_recipe(recipe_uid)
    
    def get_category_name(self, category_key: str) -> str:
        """Получение названия категории"""
        names = {
            "breakfast": "Завтраки", "lunch": "Обеды", "dinner": "Ужины",
            "dessert": "Десерты", "snack": "Перекусы", "salad": "Салаты",
            "soup": "Супы", "baking": "Выпечка", "drink": "Напитки", "other": "Другое"
        }
        return names.get(category_key, category_key.capitalize())
    
    @property
    def meal_type_to_category(self):
        """Маппинг для совместимости"""
        return {
            "завтрак": "breakfast", "обед": "lunch", "ужин": "dinner",
            "десерт": "dessert", "перекус": "snack", "закуска": "snack",
            "салат": "salad", "суп": "soup", "выпечка": "baking",
            "напиток": "drink", "основное блюдо": "dinner"
        }
