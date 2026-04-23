"""
Модуль для хранения рецептов в Supabase.
Профессиональное облачное хранилище с API.

Автор: Recipe Parser Bot
Версия: 3.0.0
"""

import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from supabase import create_client, Client
from localization import Localization

logger = logging.getLogger(__name__)


class SupabaseRecipeStorage:
    """
    Хранилище рецептов в Supabase.
    
    Особенности:
    - Облачное хранение (доступ отовсюду)
    - Автоматические бэкапы
    - Полнотекстовый поиск
    - Row Level Security
    """
    
    def __init__(self):
        """Инициализация подключения к Supabase"""
        self.url = os.environ.get("SUPABASE_URL")
        self.key = os.environ.get("SUPABASE_KEY")
        
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL и SUPABASE_KEY должны быть установлены")
        
        self.client: Client = create_client(self.url, self.key)
        logger.info("✅ Подключение к Supabase установлено")
    
    def save_recipe(self, user_id: int, recipe_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Сохранение рецепта в Supabase.
        
        Args:
            user_id: ID пользователя Telegram
            recipe_data: Данные рецепта
            
        Returns:
            Сохраненный рецепт с ID
        """
        recipe_data = Localization.normalize_recipe(recipe_data)

        # Подготовка данных
        db_recipe = {
            "user_id": user_id,
            "title": recipe_data.get("title", "Без названия"),
            "description": recipe_data.get("description", ""),
            "cuisine": recipe_data.get("cuisine", "other"),
            "meal_type": recipe_data.get("meal_type", "other"),
            "difficulty": recipe_data.get("difficulty", "medium"),
            "prep_time": recipe_data.get("prep_time", 0),
            "cook_time": recipe_data.get("cook_time", 0),
            "total_time": recipe_data.get("total_time", 0),
            "servings": recipe_data.get("servings", 4),
            "ingredients": recipe_data.get("ingredients", []),
            "steps": recipe_data.get("steps", []),
            "nutrition": recipe_data.get("nutrition", {}),
            "nutrition_per_serving": recipe_data.get("nutrition_per_serving", {}),
            "total_nutrition": recipe_data.get("total_nutrition", {}),
            "equipment": recipe_data.get("equipment", []),
            "tips": recipe_data.get("tips", []),
            "storage": recipe_data.get("storage", ""),
            "tags": recipe_data.get("tags", []),
            "is_vegetarian": recipe_data.get("is_vegetarian", False),
            "is_vegan": recipe_data.get("is_vegan", False),
            "is_gluten_free": recipe_data.get("is_gluten_free", False),
            "is_lactose_free": recipe_data.get("is_lactose_free", False),
            "source_url": recipe_data.get("source_url", ""),
        }
        
        try:
            result = self.client.table("recipes").insert(db_recipe).execute()
            
            if result.data:
                logger.info(
                    "✅ Рецепт сохранен в Supabase: %s | meal_type=%s",
                    db_recipe["title"],
                    db_recipe["meal_type"],
                )
                return result.data[0]
            else:
                raise Exception("Нет данных в ответе")
                
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения в Supabase: {e}")
            raise
    
    def get_user_recipes(
        self, 
        user_id: int, 
        meal_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Получение рецептов пользователя.
        
        Args:
            user_id: ID пользователя
            meal_type: Фильтр по типу блюда
            limit: Лимит записей
            
        Returns:
            Список рецептов
        """
        try:
            query = self.client.table("recipes").select("*").eq("user_id", user_id)
            
            if meal_type:
                query = query.eq("meal_type", meal_type)
            
            result = query.order("created_at", desc=True).limit(limit).execute()
            
            logger.info(f"📖 Загружено {len(result.data)} рецептов для user {user_id}")
            return result.data
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки рецептов: {e}")
            return []

    def get_recipes_in_category(self, user_id: int, category: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Получение рецептов пользователя по категории meal_type.

        Args:
            user_id: ID пользователя Telegram
            category: Категория (meal_type)
            limit: Максимальное число рецептов

        Returns:
            Список рецептов в категории
        """
        normalized_category = self._normalize_category_key(category)
        recipes = self.get_user_recipes(user_id, meal_type=normalized_category, limit=limit)
        if not recipes:
            russian_category = self._category_key_to_ru(normalized_category)
            if russian_category != normalized_category:
                recipes = self.get_user_recipes(user_id, meal_type=russian_category, limit=limit)
        logger.info(
            "📚 get_recipes_in_category: user_id=%s, category=%s, found=%s",
            user_id,
            normalized_category,
            len(recipes),
        )
        return recipes
    
    def get_recipe(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        """
        Получение одного рецепта по ID.
        
        Args:
            recipe_id: UUID рецепта
            
        Returns:
            Рецепт или None
        """
        try:
            result = self.client.table("recipes").select("*").eq("id", recipe_id).execute()
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки рецепта {recipe_id}: {e}")
            return None
    
    def delete_recipe(self, recipe_id: str, user_id: int) -> bool:
        """
        Удаление рецепта.
        
        Args:
            recipe_id: UUID рецепта
            user_id: ID пользователя (для проверки прав)
            
        Returns:
            True если удалено
        """
        try:
            result = self.client.table("recipes").delete()\
                .eq("id", recipe_id)\
                .eq("user_id", user_id)\
                .execute()
            
            if result.data:
                logger.info(f"🗑️ Рецепт {recipe_id} удален")
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка удаления рецепта: {e}")
            return False
    
    def get_categories(self, user_id: int) -> List[Dict[str, Any]]:
        """Получение категорий с количеством рецептов"""
        recipes = self.get_user_recipes(user_id, limit=1000)
        categories = {}

        for recipe in recipes:
            meal_type = Localization.normalize_meal_type(recipe.get("meal_type", "other"))
            if meal_type not in categories:
                categories[meal_type] = {
                    "key": meal_type,
                    "name": self._category_name(meal_type),
                    "emoji": self._category_emoji(meal_type),
                    "count": 0
                }
            categories[meal_type]["count"] += 1

        logger.info("📂 Категории: %s", list(categories.keys()))
        return sorted(categories.values(), key=lambda x: x["count"], reverse=True)

    @staticmethod
    def _category_name(meal_type: str) -> str:
        names = {
            "breakfast": "Завтраки",
            "lunch": "Обеды",
            "dinner": "Ужины",
            "dessert": "Десерты",
            "snack": "Перекусы",
            "salad": "Салаты",
            "soup": "Супы",
            "baking": "Выпечка",
            "drink": "Напитки",
            "other": "Другое",
        }
        return names.get(meal_type, meal_type.capitalize())

    @staticmethod
    def _normalize_category_key(meal_type: Optional[str]) -> str:
        aliases = {
            "завтрак": "breakfast",
            "обед": "lunch",
            "ужин": "dinner",
            "десерт": "dessert",
            "перекус": "snack",
            "закуска": "snack",
            "салат": "salad",
            "суп": "soup",
            "выпечка": "baking",
            "напиток": "drink",
            "другое": "other",
            "основное блюдо": "dinner",
        }
        normalized = (meal_type or "").strip().lower()
        return aliases.get(normalized, normalized or "other")

    @staticmethod
    def _category_key_to_ru(category_key: str) -> str:
        names = {
            "breakfast": "завтрак",
            "lunch": "обед",
            "dinner": "ужин",
            "dessert": "десерт",
            "snack": "перекус",
            "salad": "салат",
            "soup": "суп",
            "baking": "выпечка",
            "drink": "напиток",
            "other": "другое",
        }
        return names.get(category_key, category_key)

    @staticmethod
    def _category_emoji(category_key: str) -> str:
        emoji_map = {
            "breakfast": "🍳",
            "lunch": "🍲",
            "dinner": "🍽️",
            "dessert": "🍰",
            "snack": "🥨",
            "salad": "🥗",
            "soup": "🥣",
            "baking": "🧁",
            "drink": "🥤",
            "other": "📦",
        }
        return emoji_map.get(category_key, "🍴")
    def search_recipes(self, user_id: int, query: str) -> List[Dict[str, Any]]:
        """
        Поиск рецептов.
        
        Args:
            user_id: ID пользователя
            query: Поисковый запрос
            
        Returns:
            Найденные рецепты
        """
        try:
            # Полнотекстовый поиск
            result = self.client.table("recipes").select("*")\
                .eq("user_id", user_id)\
                .text_search("title", query)\
                .execute()
            
            if result.data:
                logger.info(f"🔍 Найдено {len(result.data)} рецептов по запросу '{query}'")
                return result.data
            
            # Fallback: поиск по ILIKE
            result = self.client.table("recipes").select("*")\
                .eq("user_id", user_id)\
                .ilike("title", f"%{query}%")\
                .execute()
            
            return result.data
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска: {e}")
            return []
    
    def get_statistics(self, user_id: int) -> Dict[str, Any]:
        """
        Получение статистики пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Статистика
        """
        try:
            recipes = self.get_user_recipes(user_id, limit=1000)
            
            stats = {
                "total_recipes": len(recipes),
                "by_meal_type": {},
                "avg_calories": 0,
                "avg_time": 0,
                "vegetarian": 0,
                "vegan": 0,
                "gluten_free": 0
            }
            
            total_calories = 0
            total_time = 0
            
            for recipe in recipes:
                meal_type = recipe.get("meal_type", "other")
                stats["by_meal_type"][meal_type] = stats["by_meal_type"].get(meal_type, 0) + 1
                
                if recipe.get("is_vegetarian"):
                    stats["vegetarian"] += 1
                if recipe.get("is_vegan"):
                    stats["vegan"] += 1
                if recipe.get("is_gluten_free"):
                    stats["gluten_free"] += 1
                
                nutrition = recipe.get("nutrition_per_serving", {})
                total_calories += nutrition.get("calories", 0)
                total_time += recipe.get("total_time", 0)
            
            if recipes:
                stats["avg_calories"] = round(total_calories / len(recipes))
                stats["avg_time"] = round(total_time / len(recipes))
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка статистики: {e}")
            return {}


# Создание RPC функции в Supabase (выполнить в SQL Editor)
SQL_CREATE_CATEGORIES_FUNCTION = """
CREATE OR REPLACE FUNCTION get_user_categories(p_user_id BIGINT)
RETURNS TABLE (
    key TEXT,
    name TEXT,
    emoji TEXT,
    count BIGINT
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT 
        r.meal_type as key,
        INITCAP(r.meal_type) as name,
        CASE r.meal_type
            WHEN 'breakfast' THEN '🍳'
            WHEN 'lunch' THEN '🍲'
            WHEN 'dinner' THEN '🍽️'
            WHEN 'dessert' THEN '🍰'
            WHEN 'snack' THEN '🥨'
            WHEN 'salad' THEN '🥗'
            WHEN 'soup' THEN '🥣'
            WHEN 'baking' THEN '🧁'
            WHEN 'drink' THEN '🥤'
            ELSE '📦'
        END as emoji,
        COUNT(*) as count
    FROM recipes r
    WHERE r.user_id = p_user_id
    GROUP BY r.meal_type
    ORDER BY count DESC;
END;
$$;
"""
