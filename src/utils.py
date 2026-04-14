import re
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

def format_recipe_for_telegram(recipe: Dict[str, Any]) -> str:
    """Форматирование рецепта для Telegram с КБЖУ"""
    if not recipe:
        return "❌ Не удалось обработать рецепт"
    
    # Заголовок с эмодзи по типу блюда
    meal_emojis = {
        "завтрак": "🍳",
        "обед": "🍲",
        "ужин": "🍽",
        "десерт": "🍰",
        "закуска": "🥗",
        "напиток": "🥤",
        "перекус": "🥨"
    }
    
    meal_type = recipe.get('meal_type', 'основное блюдо')
    emoji = meal_emojis.get(meal_type.lower(), "🍴")
    
    title = recipe.get('title', 'Без названия')
    text = f"{emoji} *{title}*\n\n"
    
    # Основная информация
    info_parts = []
    if recipe.get('cuisine'):
        info_parts.append(f"🍽 {recipe['cuisine']}")
    info_parts.append(f"📋 {meal_type}")
    if recipe.get('difficulty'):
        info_parts.append(f"📊 {recipe['difficulty']}")
    
    text += " | ".join(info_parts) + "\n\n"
    
    # Диетические метки
    diet_labels = []
    if recipe.get('is_vegetarian'):
        diet_labels.append("🥬 Вегетарианское")
    if recipe.get('is_vegan'):
        diet_labels.append("🌱 Веганское")
    if recipe.get('is_gluten_free'):
        diet_labels.append("🌾 Без глютена")
    if recipe.get('is_lactose_free'):
        diet_labels.append("🥛 Без лактозы")
    
    if diet_labels:
        text += " | ".join(diet_labels) + "\n\n"
    
    # Время и порции
    time_parts = []
    if recipe.get('prep_time'):
        time_parts.append(f"✂️ Подготовка: {recipe['prep_time']} мин")
    if recipe.get('cook_time'):
        time_parts.append(f"🔥 Готовка: {recipe['cook_time']} мин")
    if recipe.get('total_time'):
        time_parts.append(f"⏱ Всего: {recipe['total_time']} мин")
    
    if time_parts:
        text += "*⏰ Время:*\n" + "\n".join(time_parts) + "\n\n"
    
    if recipe.get('servings'):
        text += f"👥 *Порций:* {recipe['servings']}\n\n"
    
    # КБЖУ на порцию
    nutrition = recipe.get('nutrition_per_serving', {})
    if nutrition and nutrition.get('calories'):
        text += "*📊 КБЖУ на порцию:*\n"
        text += f"🔥 Калории: {nutrition.get('calories', 0)} ккал\n"
        text += f"💪 Белки: {nutrition.get('protein', 0)} г\n"
        text += f"🧈 Жиры: {nutrition.get('fat', 0)} г\n"
        text += f"🍚 Углеводы: {nutrition.get('carbs', 0)} г\n\n"
    
    # КБЖУ на 100г
    nutrition_100 = recipe.get('nutrition', {})
    if nutrition_100 and nutrition_100.get('calories'):
        text += "*📊 КБЖУ на 100г:*\n"
        text += f"🔥 {nutrition_100.get('calories', 0)} ккал | "
        text += f"💪 {nutrition_100.get('protein', 0)} г | "
        text += f"🧈 {nutrition_100.get('fat', 0)} г | "
        text += f"🍚 {nutrition_100.get('carbs', 0)} г\n\n"
    
    # Ингредиенты
    ingredients = recipe.get('ingredients', [])
    if ingredients:
        text += "*🛒 Ингредиенты:*\n"
        for ing in ingredients[:20]:
            if isinstance(ing, dict):
                parts = []
                if ing.get('amount'):
                    parts.append(str(ing['amount']))
                if ing.get('unit'):
                    parts.append(ing['unit'])
                if ing.get('name'):
                    parts.append(ing['name'])
                if parts:
                    ing_text = ' '.join(parts)
                    if ing.get('notes'):
                        ing_text += f" ({ing['notes']})"
                    text += f"• {ing_text}\n"
            elif isinstance(ing, str):
                text += f"• {ing}\n"
        
        if len(ingredients) > 20:
            text += f"• ... и еще {len(ingredients) - 20}\n"
        text += "\n"
    
    # Шаги
    steps = recipe.get('steps', [])
    if steps:
        text += "*📝 Приготовление:*\n"
        for step in steps[:8]:
            if isinstance(step, dict):
                num = step.get('step_number', '•')
                desc = step.get('description', '')
                step_text = f"{num}. {desc}"
                if step.get('time'):
                    step_text += f" ⏱ {step['time']} мин"
                text += step_text + "\n"
            elif isinstance(step, str):
                text += f"• {step}\n"
        
        if len(steps) > 8:
            text += f"... и еще {len(steps) - 8} шагов\n"
        text += "\n"
    
    # Советы и хранение
    tips = recipe.get('tips', [])
    if tips:
        text += "*💡 Советы:*\n"
        for tip in tips[:3]:
            text += f"• {tip}\n"
    
    if recipe.get('storage'):
        text += f"\n*📦 Хранение:* {recipe['storage']}\n"
    
    # Теги
    tags = recipe.get('tags', [])
    if tags:
        text += "\n"
        for tag in tags[:5]:
            text += f"#{tag.replace(' ', '_')} "
    
    # Обрезаем для Telegram
    if len(text) > 4000:
        text = text[:4000] + "...\n\n(полная версия в JSON файле)"
    
    return text

def save_recipe_to_file(recipe: Dict[str, Any], output_dir: str = "output") -> str:
    """Сохранение рецепта в JSON файл локально"""
    os.makedirs(output_dir, exist_ok=True)
    
    recipe['processed_at'] = datetime.now().isoformat()
    recipe['version'] = '2.0'
    
    # Создаем подпапки по типу блюда
    meal_type = recipe.get('meal_type', 'other')
    meal_dir = os.path.join(output_dir, meal_type)
    os.makedirs(meal_dir, exist_ok=True)
    
    title = recipe.get('title', 'recipe')
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_title = safe_title[:40].replace(' ', '_')
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{meal_dir}/{safe_title}_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(recipe, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Рецепт сохранен: {filename}")
    return filename

def validate_url(url: str) -> bool:
    """Проверка валидности URL"""
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return bool(url_pattern.match(url))
