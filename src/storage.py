import os
import json
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
        
        # Определяем категорию
        meal_type = recipe.get('meal_type', 'other').lower()
        category = self.meal_type_to_category.get(meal_type, 'other')
        
        # Создаем подпапку категории
        category_dir = os.path.join(user_dir, category)
        os.makedirs(category_dir, exist_ok=True)
        
        # Добавляем метаданные сохранения
        recipe['saved_at'] = datetime.now().isoformat()
        recipe['user_id'] = user_id
        recipe['category'] = category
        
        # Создаем имя файла
        title = recipe.get('title', 'recipe')[:30]
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_'))
        safe_title = safe_title.replace(' ', '_')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{safe_title}_{timestamp}.json"
        filepath = os.path.join(category_dir, filename)
        
        # Сохраняем
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(recipe, f, ensure_ascii=False, indent=2)
        
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
                            'calories': recipe.get('nutrition_per_serving', {}).get('calories', 0),
                            'cook_time': recipe.get('total_time', 0)
                        })
                except:
                    pass
        
        # Сортируем по дате сохранения (новые сверху)
        return sorted(recipes, key=lambda x: x['saved_at'], reverse=True)
    
    def get_recipe(self, user_id: int, category: str, filename: str) -> Optional[Dict[str, Any]]:
        """Получение полного рецепта"""
        filepath = os.path.join(self.storage_dir, str(user_id), category, filename)
        
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        return None
    
    def delete_recipe(self, user_id: int, category: str, filename: str) -> bool:
        """Удаление рецепта"""
        filepath = os.path.join(self.storage_dir, str(user_id), category, filename)
        
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        
        return False
    
    def get_category_name(self, category_key: str) -> str:
        """Получение названия категории"""
        return self.categories.get(category_key, category_key)
