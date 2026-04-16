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
        # Подготовка данных
        db_recipe = {
            "user_id": user_id,
            "title": recipe_data.get("title", "Без названия"),
            "description": recipe_data.get("description", ""),
            "cuisine": recipe_data.get("cuisine", "интернациональная"),
            "meal_type": recipe_data.get("meal_type", "other"),
            "difficulty": recipe_data.get("difficulty", "средне"),
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
                logger.info(f"✅ Рецепт сохранен в Supabase: {db_recipe['title']}")
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
        """
        Получение категорий с количеством рецептов.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список категорий для меню
        """
        try:
            # Используем RPC для агрегации
            result = self.client.rpc(
                'get_user_categories',
                {'p_user_id': user_id}
            ).execute()
            
            if result.data:
                return result.data
            
            # Fallback: группировка на клиенте
            recipes = self.get_user_recipes(user_id, limit=1000)
            
            categories = {}
            emoji_map = {
                "breakfast": "🍳", "lunch": "🍲", "dinner": "🍽️",
                "dessert": "🍰", "snack": "🥨", "salad": "🥗",
                "soup": "🥣", "baking": "🧁", "drink": "🥤", "other": "📦"
            }
            
            for recipe in recipes:
                meal_type = recipe.get("meal_type", "other")
                if meal_type not in categories:
                    categories[meal_type] = {
                        "key": meal_type,
                        "name": meal_type.capitalize(),
                        "emoji": emoji_map.get(meal_type, "🍴"),
                        "count": 0
                    }
                categories[meal_type]["count"] += 1
            
            return sorted(categories.values(), key=lambda x: x["count"], reverse=True)
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения категорий: {e}")
            return []
    
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
