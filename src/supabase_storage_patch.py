# Исправленный метод get_categories
def get_categories(self, user_id: int) -> List[Dict[str, Any]]:
    """Получение категорий с количеством рецептов"""
    try:
        # Пробуем через RPC
        result = self.client.rpc('get_user_categories', {'p_user_id': user_id}).execute()
        if result.data:
            return result.data
    except Exception as e:
        logger.warning(f"RPC не сработал: {e}")
    
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
