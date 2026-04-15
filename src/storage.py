import os
import json
import hashlib
import re
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

class RecipeStorage:
    """Класс для работы с сохраненными рецептами"""
    
    def __init__(self, storage_dir: str = "data/recipes"):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        
        # Категории блюд
        self.categories = {
            "breakfast": "🍳 Завтраки",
            "lunch": "🍲 Обеды", 
            "dinner": "🍽 Ужины",
            "dessert": "🍰 Десерты",
            "snack": "🥨 Перекусы",
            "salad": "🥗 Салаты",
            "soup": "🥣 Супы",
            "baking": "🧁 Выпечка",
            "drink": "🥤 Напитки",
            "other": "📦 Другое"
        }
        
        # Маппинг типов блюд из AI на категории
        self.meal_type_to_category = {
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
            "основное блюдо": "dinner"
        }
    
    def save_recipe(self, user_id: int, recipe: Dict[str, Any]) -> str:
        """Сохранение рецепта для пользователя"""
        user_dir = os.path.join(self.storage_dir, str(user_id))
        os.makedirs(user_dir, exist_ok=True)
        recipe_to_save = dict(recipe)
        
        # Определяем категорию
        meal_type = recipe_to_save.get('meal_type', 'other').lower()
        category = self.meal_type_to_category.get(meal_type, 'other')
        
        # Создаем подпапку категории
        category_dir = os.path.join(user_dir, category)
        os.makedirs(category_dir, exist_ok=True)
        
        # Добавляем метаданные сохранения
        recipe_to_save['saved_at'] = datetime.now().isoformat()
        recipe_to_save['user_id'] = user_id
        recipe_to_save['category'] = category
        recipe_to_save['recipe_uid'] = recipe_to_save.get('recipe_uid') or uuid.uuid4().hex[:10]
        
        # Создаем имя файла
        title = recipe_to_save.get('title', 'recipe')[:40]
        safe_title = self._safe_title_for_filename(title)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{safe_title}_{timestamp}.json"
        filepath = os.path.join(category_dir, filename)
        
        # Сохраняем
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(recipe_to_save, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def get_user_categories(self, user_id: int) -> List[Dict[str, Any]]:
        """Получение списка категорий пользователя с количеством рецептов"""
        user_dir = os.path.join(self.storage_dir, str(user_id))
        
        if not os.path.exists(user_dir):
            return []
        
        categories = []
        for cat_key, cat_name in self.categories.items():
            cat_dir = os.path.join(user_dir, cat_key)
            if os.path.exists(cat_dir):
                recipes = [f for f in os.listdir(cat_dir) if f.endswith('.json')]
                if recipes:
                    categories.append({
                        'key': cat_key,
                        'name': cat_name,
                        'count': len(recipes)
                    })
        
        return sorted(categories, key=lambda x: x['count'], reverse=True)
    
    def get_recipes_in_category(self, user_id: int, category: str) -> List[Dict[str, Any]]:
        """Получение списка рецептов в категории"""
        user_dir = os.path.join(self.storage_dir, str(user_id))
        cat_dir = os.path.join(user_dir, category)
        
        if not os.path.exists(cat_dir):
            return []
        
        recipes = []
        for filename in os.listdir(cat_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(cat_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        recipe = json.load(f)
                        recipes.append({
                            'title': recipe.get('title', 'Без названия'),
                            'saved_at': recipe.get('saved_at', ''),
                            'filename': filename,
                            'recipe_uid': recipe.get('recipe_uid', self._fallback_uid(filename)),
                            'calories': recipe.get('nutrition_per_serving', {}).get('calories', 0),
                            'cook_time': recipe.get('total_time', 0)
                        })
                except:
                    pass
        
        # Сортируем по дате сохранения (новые сверху)
        return sorted(recipes, key=lambda x: x['saved_at'], reverse=True)
    
    def get_recipe(self, user_id: int, category: str, filename: str) -> Optional[Dict[str, Any]]:
        """Получение полного рецепта"""
        safe_filename = os.path.basename(filename)
        filepath = os.path.join(self.storage_dir, str(user_id), category, safe_filename)
        
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        return None
    
    def delete_recipe(self, user_id: int, category: str, filename: str) -> bool:
        """Удаление рецепта"""
        safe_filename = os.path.basename(filename)
        filepath = os.path.join(self.storage_dir, str(user_id), category, safe_filename)
        
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        
        return False
    
    def get_category_name(self, category_key: str) -> str:
        """Получение названия категории"""
        return self.categories.get(category_key, category_key)

    def get_recipe_by_filename(self, user_id: int, filename: str) -> Optional[Dict[str, Any]]:
        """Поиск рецепта по имени файла во всех категориях"""
        user_dir = os.path.join(self.storage_dir, str(user_id))
        
        if not os.path.exists(user_dir):
            return None
        
        for category in os.listdir(user_dir):
            cat_dir = os.path.join(user_dir, category)
            if os.path.isdir(cat_dir):
                filepath = os.path.join(cat_dir, filename)
                if os.path.exists(filepath):
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            return json.load(f)
                    except:
                        pass
        
        return None

    def get_recipe_by_uid(self, user_id: int, category: str, recipe_uid: str) -> Optional[Dict[str, Any]]:
        """Поиск рецепта по короткому UID внутри категории."""
        for recipe in self.get_recipes_in_category(user_id, category):
            if recipe.get("recipe_uid") == recipe_uid:
                return self.get_recipe(user_id, category, recipe.get("filename", ""))
        return None

    def delete_recipe_by_uid(self, user_id: int, category: str, recipe_uid: str) -> bool:
        """Удаление рецепта по UID внутри категории."""
        for recipe in self.get_recipes_in_category(user_id, category):
            if recipe.get("recipe_uid") == recipe_uid:
                return self.delete_recipe(user_id, category, recipe.get("filename", ""))
        return False

    def _safe_title_for_filename(self, value: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9 _-]+", "", value)
        normalized = re.sub(r"\s+", "_", normalized).strip("_")
        return normalized[:30] or "recipe"

    def _fallback_uid(self, filename: str) -> str:
        return hashlib.sha1(filename.encode("utf-8")).hexdigest()[:10]
