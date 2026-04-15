import json
import aiohttp
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class GitHubModelNormalizer:
    def __init__(self, github_token: str, model: str = "gpt-4o-mini"):
        self.github_token = github_token
        self.model = model
        self.api_url = "https://models.inference.ai.azure.com/chat/completions"
        
        self.system_prompt = """Ты профессиональный диетолог и шеф-повар. Проанализируй текст и извлеки рецепт.

Верни ТОЛЬКО JSON в таком формате:
{
    "title": "Название блюда",
    "description": "Краткое описание",
    "cuisine": "Кухня мира",
    "meal_type": "завтрак/обед/ужин/десерт/закуска/напиток",
    "difficulty": "легко/средне/сложно",
    "prep_time": 20,
    "cook_time": 30,
    "total_time": 50,
    "servings": 4,
    "ingredients": [
        {"name": "название", "amount": 1, "unit": "г/мл/шт", "notes": ""}
    ],
    "steps": [
        {"step_number": 1, "description": "описание шага"}
    ],
    "nutrition_per_serving": {
        "calories": 0,
        "protein": 0,
        "fat": 0,
        "carbs": 0
    },
    "nutrition": {
        "calories": 0,
        "protein": 0,
        "fat": 0,
        "carbs": 0
    },
    "tips": [],
    "storage": "Как хранить",
    "is_vegetarian": false,
    "is_vegan": false,
    "is_gluten_free": false
}

ВАЖНО: 
- nutrition_per_serving - КБЖУ на ОДНУ порцию
- nutrition - КБЖУ на 100 грамм готового блюда
- ВСЕ числа должны быть рассчитаны на основе ингредиентов
- НЕ ИСПОЛЬЗУЙ шаблонные значения
- Проверь, что КБЖУ на 100г МЕНЬШЕ чем на порцию (если порция больше 100г)
- Если порция 300г, то КБЖУ на 100г = КБЖУ на порцию / 3"""
    
    async def normalize(self, raw_text: str) -> Dict[str, Any]:
        if not raw_text:
            logger.error("Пустой текст для нормализации")
            return self._get_error_recipe("Пустой текст")
        
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
                {"role": "user", "content": f"Проанализируй этот рецепт и верни JSON с реальными данными:\n\n{raw_text}"}
            ],
            "temperature": 0.3,
            "max_tokens": 2500
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
                        logger.error(f"GitHub API error {response.status}")
                        return self._get_error_recipe(f"API Error {response.status}")
                    
                    data = await response.json()
                    content = data["choices"][0]["message"]["content"]
                    
                    # Очищаем от markdown
                    content = content.strip()
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()
                    
                    result = json.loads(content)
                    
                    # Проверяем и исправляем КБЖУ на 100г если оно неправильное
                    serving = result.get('servings', 1)
                    nutrition_per_serving = result.get('nutrition_per_serving', {})
                    nutrition_100 = result.get('nutrition', {})
                    
                    # Если КБЖУ на 100г больше чем на порцию - это ошибка
                    if nutrition_100.get('calories', 0) > nutrition_per_serving.get('calories', 0):
                        logger.warning("⚠️ КБЖУ на 100г больше чем на порцию - исправляю")
                        # Примерный вес порции (возьмем 300г как среднее)
                        portion_weight = 300
                        for key in ['calories', 'protein', 'fat', 'carbs']:
                            if key in nutrition_per_serving:
                                nutrition_100[key] = round(nutrition_per_serving[key] * 100 / portion_weight)
                        result['nutrition'] = nutrition_100
                    
                    logger.info(f"✅ Рецепт обработан: {result.get('title')}")
                    return result
                    
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            return self._get_error_recipe(str(e)[:100])
    
    def _get_error_recipe(self, error: str) -> Dict[str, Any]:
        return {
            "title": f"Ошибка обработки",
            "description": f"Не удалось обработать: {error}",
            "cuisine": "",
            "meal_type": "основное блюдо",
            "difficulty": "",
            "prep_time": 0,
            "cook_time": 0,
            "total_time": 0,
            "servings": 1,
            "ingredients": [],
            "steps": [],
            "nutrition_per_serving": {"calories": 0, "protein": 0, "fat": 0, "carbs": 0},
            "nutrition": {"calories": 0, "protein": 0, "fat": 0, "carbs": 0},
            "tips": ["Попробуйте другую ссылку"],
            "storage": "",
            "is_vegetarian": False,
            "is_vegan": False,
            "is_gluten_free": False,
            "error": error
        }
