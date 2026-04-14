import json
import aiohttp
from typing import Dict, Any, Optional

class GitHubModelNormalizer:
    def __init__(self, github_token: str, model: str = "gpt-4o-mini"):
        self.github_token = github_token
        self.model = model
        self.api_url = "https://models.inference.ai.azure.com/chat/completions"
        
        self.system_prompt = """Ты профессиональный диетолог и шеф-повар. Извлеки из текста рецепт и рассчитай КБЖУ.

Верни ТОЛЬКО JSON в формате:
{
    "title": "Название блюда",
    "description": "Краткое описание",
    "cuisine": "Кухня мира",
    "meal_type": "завтрак/обед/ужин/десерт/перекус/закуска/напиток",
    "difficulty": "легко/средне/сложно",
    "prep_time": "Время подготовки в минутах (число)",
    "cook_time": "Время приготовления в минутах (число)",
    "total_time": "Общее время в минутах (число)",
    "servings": "Количество порций (число)",
    "ingredients": [
        {
            "name": "Название ингредиента",
            "amount": "Количество (число)",
            "unit": "Единица измерения (г, мл, шт, ст.л., ч.л.)",
            "notes": "Примечания"
        }
    ],
    "steps": [
        {
            "step_number": 1,
            "description": "Описание шага",
            "time": "Время шага в минутах (опционально)"
        }
    ],
    "nutrition": {
        "calories": "Калории на 100г (число)",
        "protein": "Белки на 100г в граммах (число)",
        "fat": "Жиры на 100г в граммах (число)",
        "carbs": "Углеводы на 100г в граммах (число)",
        "fiber": "Клетчатка на 100г в граммах (число)"
    },
    "nutrition_per_serving": {
        "calories": "Калории на порцию (число)",
        "protein": "Белки на порцию (число)",
        "fat": "Жиры на порцию (число)",
        "carbs": "Углеводы на порцию (число)"
    },
    "total_nutrition": {
        "calories": "Общие калории на всё блюдо (число)",
        "protein": "Общие белки (число)",
        "fat": "Общие жиры (число)",
        "carbs": "Общие углеводы (число)"
    },
    "equipment": ["Необходимое оборудование"],
    "tips": ["Советы по приготовлению"],
    "storage": "Как хранить",
    "tags": ["ключевые", "слова"],
    "is_vegetarian": true/false,
    "is_vegan": true/false,
    "is_gluten_free": true/false,
    "is_lactose_free": true/false
}

ВАЖНО:
1. meal_type определи по ингредиентам и контексту
2. nutrition рассчитай примерно, основываясь на ингредиентах
3. Если точных данных нет, сделай обоснованную оценку
4. Все числа в nutrition должны быть числами, не строками"""
    
    async def normalize(self, raw_text: str) -> Dict[str, Any]:
        if not raw_text:
            return self._get_empty_recipe()
        
        if len(raw_text) > 30000:
            raw_text = raw_text[:30000]
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.github_token}"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Проанализируй рецепт, определи тип блюда и рассчитай КБЖУ:\n\n{raw_text}"}
            ],
            "temperature": 0.3,
            "max_tokens": 3000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"❌ GitHub API error {response.status}: {error_text[:200]}")
                        return self._get_empty_recipe()
                    
                    data = await response.json()
                    content = data["choices"][0]["message"]["content"]
                    
                    # Извлекаем JSON
                    content = content.strip()
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    
                    result = json.loads(content.strip())
                    
                    # Валидация и установка значений по умолчанию
                    result = self._validate_recipe(result)
                    
                    print(f"✅ Рецепт нормализован: {result.get('title')} | Тип: {result.get('meal_type')} | Ккал: {result.get('nutrition', {}).get('calories')}")
                    
                    return result
                    
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return self._get_empty_recipe()
    
    def _validate_recipe(self, recipe: Dict) -> Dict:
        """Валидация и установка значений по умолчанию"""
        
        # Обязательные поля
        defaults = {
            "title": "Блюдо",
            "description": "",
            "cuisine": "интернациональная",
            "meal_type": "основное блюдо",
            "difficulty": "средне",
            "prep_time": 20,
            "cook_time": 30,
            "total_time": 50,
            "servings": 4,
            "ingredients": [],
            "steps": [],
            "nutrition": {
                "calories": 200,
                "protein": 10,
                "fat": 10,
                "carbs": 20,
                "fiber": 2
            },
            "nutrition_per_serving": {
                "calories": 400,
                "protein": 20,
                "fat": 20,
                "carbs": 40
            },
            "total_nutrition": {
                "calories": 1600,
                "protein": 80,
                "fat": 80,
                "carbs": 160
            },
            "equipment": [],
            "tips": [],
            "storage": "В холодильнике до 3 дней",
            "tags": [],
            "is_vegetarian": False,
            "is_vegan": False,
            "is_gluten_free": False,
            "is_lactose_free": False
        }
        
        # Рекурсивно устанавливаем значения по умолчанию
        for key, default_value in defaults.items():
            if key not in recipe or recipe[key] is None:
                recipe[key] = default_value
            elif isinstance(default_value, dict):
                for sub_key, sub_default in default_value.items():
                    if sub_key not in recipe[key] or recipe[key][sub_key] is None:
                        recipe[key][sub_key] = sub_default
        
        # Определяем meal_type если не указан
        if recipe["meal_type"] == "основное блюдо":
            title_lower = recipe["title"].lower()
            if any(word in title_lower for word in ["завтрак", "утро", "яич", "каша", "омлет", "тост"]):
                recipe["meal_type"] = "завтрак"
            elif any(word in title_lower for word in ["суп", "борщ", "щи", "солянка"]):
                recipe["meal_type"] = "обед"
            elif any(word in title_lower for word in ["десерт", "торт", "пирог", "слад", "шоколад"]):
                recipe["meal_type"] = "десерт"
            elif any(word in title_lower for word in ["салат", "закуска"]):
                recipe["meal_type"] = "закуска"
            elif any(word in title_lower for word in ["напиток", "сок", "коктейль", "чай", "кофе"]):
                recipe["meal_type"] = "напиток"
        
        return recipe
    
    def _get_empty_recipe(self) -> Dict[str, Any]:
        return self._validate_recipe({})
