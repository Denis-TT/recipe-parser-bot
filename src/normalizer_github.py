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
- ВСЕ числа должны быть рассчитаны на основе ингредиентов
- НЕ ИСПОЛЬЗУЙ шаблонные значения
- Если не можешь определить - сделай ОБОСНОВАННУЮ оценку"""
    
    async def normalize(self, raw_text: str) -> Dict[str, Any]:
        if not raw_text:
            logger.error("Пустой текст для нормализации")
            return self._get_error_recipe("Пустой текст")
        
        # Ограничиваем длину
        if len(raw_text) > 30000:
            raw_text = raw_text[:30000]
            logger.info(f"Текст обрезан до 30000 символов")
        
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
            "max_tokens": 2000
        }
        
        try:
            logger.info(f"Отправка запроса к GitHub Models API...")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    
                    logger.info(f"Статус ответа: {response.status}")
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"GitHub API error {response.status}: {error_text[:300]}")
                        return self._get_error_recipe(f"API Error {response.status}")
                    
                    data = await response.json()
                    
                    if "choices" not in data or not data["choices"]:
                        logger.error(f"Нет choices в ответе: {data}")
                        return self._get_error_recipe("Нет ответа от модели")
                    
                    content = data["choices"][0]["message"]["content"]
                    logger.info(f"Получен ответ длиной {len(content)} символов")
                    
                    # Очищаем от markdown
                    content = content.strip()
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()
                    
                    try:
                        result = json.loads(content)
                        logger.info(f"✅ JSON успешно распарсен")
                        logger.info(f"Название: {result.get('title', 'Н/Д')}")
                        logger.info(f"Тип: {result.get('meal_type', 'Н/Д')}")
                        
                        # Проверяем, не дефолтные ли значения
                        nutrition = result.get('nutrition_per_serving', {})
                        if nutrition.get('calories') == 400 and nutrition.get('protein') == 20:
                            logger.warning("⚠️ Обнаружены дефолтные значения КБЖУ")
                        
                        return result
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decode error: {e}")
                        logger.error(f"Content: {content[:500]}")
                        return self._get_error_recipe("Ошибка парсинга JSON")
                        
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка подключения: {e}")
            return self._get_error_recipe("Ошибка подключения к API")
        except Exception as e:
            logger.error(f"Неизвестная ошибка: {e}")
            return self._get_error_recipe(str(e)[:100])
    
    def _get_error_recipe(self, error: str) -> Dict[str, Any]:
        """Создает рецепт с информацией об ошибке"""
        return {
            "title": f"Ошибка обработки",
            "description": f"Не удалось обработать рецепт: {error}",
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
