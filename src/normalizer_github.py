import json
import logging
from typing import Any, Dict

import aiohttp

from localization import Localization

logger = logging.getLogger(__name__)


class GitHubModelNormalizer:
    def __init__(self, github_token: str, model: str = "gpt-4o-mini"):
        self.github_token = github_token
        self.model = model
        self.api_url = "https://models.inference.ai.azure.com/chat/completions"

        self.system_prompt = """You are a professional chef and nutritionist. Extract the recipe from the webpage text below.

Return ONLY a valid JSON object with this exact structure:
{
    "title": "Recipe name in Russian",
    "description": "Brief description in Russian (2-3 sentences)",
    "cuisine": "italian/russian/japanese/french/chinese/georgian/etc",
    "meal_type": "breakfast/lunch/dinner/dessert/snack/salad/soup/baking/drink/other",
    "difficulty": "easy/medium/hard",
    "prep_time": 15,
    "cook_time": 30,
    "total_time": 45,
    "servings": 4,
    "ingredients": [
        {"name": "ingredient name in Russian", "amount": 200, "unit": "g/ml/pcs/tbsp/tsp", "notes": ""}
    ],
    "steps": [
        {"step_number": 1, "description": "Step description in Russian"}
    ],
    "nutrition_per_serving": {"calories": 350, "protein": 20, "fat": 15, "carbs": 40},
    "nutrition": {"calories": 150, "protein": 8, "fat": 5, "carbs": 15},
    "tips": ["Cooking tips in Russian"],
    "storage": "Storage instructions in Russian",
    "tags": ["tag1", "tag2"],
    "is_vegetarian": false,
    "is_vegan": false,
    "is_gluten_free": false,
    "is_lactose_free": false
}

IMPORTANT RULES:
1. ALL text fields (title, description, ingredients, steps, tips) MUST be in Russian.
2. meal_type MUST be one of: breakfast, lunch, dinner, dessert, snack, salad, soup, baking, drink, other
3. difficulty MUST be one of: easy, medium, hard
4. cuisine MUST be in English (italian, russian, japanese, etc.)
5. Calculate realistic nutrition based on ingredients.
6. If information is missing - make an educated guess based on similar recipes.
7. DO NOT use placeholder values like "Untitled" or 0 for times.
8. Return ONLY the JSON object, no other text."""

    async def normalize(self, raw_text: str) -> Dict[str, Any]:
        if not raw_text:
            logger.error("❌ Пустой текст для нормализации")
            return self._get_error_recipe("Пустой текст")

        logger.info("📄 Входящий текст: %s символов", len(raw_text))
        logger.debug("📄 Первые 200 символов: %s", raw_text[:200])

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
                {"role": "user", "content": f"Extract recipe from this text:\n\n{raw_text}"}
            ],
            "temperature": 0.3,
            "max_tokens": 2500,
            "response_format": {"type": "json_object"}
        }

        try:
            logger.info("🤖 Отправка запроса к GitHub Models API...")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url, headers=headers, json=payload, timeout=60
                ) as response:

                    logger.info("📡 Статус ответа API: %s", response.status)

                    if response.status != 200:
                        error_text = await response.text()
                        logger.error("❌ API error %s: %s", response.status, error_text[:300])
                        return self._get_error_recipe(f"API Error {response.status}")

                    data = await response.json()

                    if "choices" not in data or not data["choices"]:
                        logger.error("❌ Нет choices в ответе: %s", str(data)[:300])
                        return self._get_error_recipe("Пустой ответ от AI")

                    content = data["choices"][0]["message"]["content"]
                    logger.info("📝 Получен ответ длиной %s символов", len(content))
                    logger.debug("📝 Сырой ответ: %s", content[:500])

                    content = content.strip()
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()

                    result = json.loads(content)

                    title = result.get("title", "")
                    if not title or title.lower() in ["untitled", "recipe", "без названия"]:
                        logger.warning("⚠️ AI вернул пустое название: '%s'", title)
                        title = self._extract_title_from_text(raw_text)
                        if title:
                            result["title"] = title
                            logger.info("📝 Название извлечено из текста: %s", title)

                    if result.get("total_time", 0) == 0:
                        prep = result.get("prep_time", 0)
                        cook = result.get("cook_time", 0)
                        if prep > 0 or cook > 0:
                            result["total_time"] = prep + cook
                            logger.info("⏱ total_time исправлен: %s", result["total_time"])

                    ingredients = result.get("ingredients", [])
                    if not ingredients or len(ingredients) == 0:
                        logger.warning("⚠️ AI не вернул ингредиенты")

                    steps = result.get("steps", [])
                    if not steps or len(steps) == 0:
                        logger.warning("⚠️ AI не вернул шаги приготовления")

                    result = Localization.normalize_recipe(result)

                    logger.info(
                        "✅ Рецепт нормализован: title='%s', meal_type=%s, time=%smin",
                        result.get("title"),
                        result.get("meal_type"),
                        result.get("total_time"),
                    )

                    return result

        except json.JSONDecodeError as e:
            logger.error("❌ Ошибка парсинга JSON: %s", e)
            logger.error("❌ Контент: %s", content[:500] if "content" in locals() else "N/A")
            return self._get_error_recipe("Ошибка парсинга JSON")

        except Exception as e:
            logger.error("❌ Неизвестная ошибка: %s", e, exc_info=True)
            return self._get_error_recipe(str(e)[:100])

    def _extract_title_from_text(self, text: str) -> str:
        """Извлечение названия рецепта из текста страницы"""
        lines = text.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line or len(line) < 3:
                continue
            if any(word in line.lower() for word in [
                "ингредиент", "приготовлен", "способ", "рецепт", "кухня",
                "ingredient", "instruction", "method", "recipe", "cuisine",
                "меню", "поиск", "вход", "menu", "search", "login"
            ]):
                continue
            if len(line) > 5 and len(line) < 100:
                return line[:100]

        return text.strip()[:50] if text.strip() else "Рецепт"

    def _get_error_recipe(self, error: str) -> Dict[str, Any]:
        """Создает рецепт-заглушку с информацией об ошибке"""
        logger.error("❌ Создана заглушка из-за ошибки: %s", error)
        return {
            "title": "Ошибка обработки рецепта",
            "description": f"Не удалось обработать рецепт. Причина: {error}. Попробуйте другую ссылку.",
            "cuisine": "other",
            "meal_type": "other",
            "difficulty": "medium",
            "prep_time": 0,
            "cook_time": 0,
            "total_time": 0,
            "servings": 1,
            "ingredients": [],
            "steps": [],
            "nutrition_per_serving": {"calories": 0, "protein": 0, "fat": 0, "carbs": 0},
            "nutrition": {"calories": 0, "protein": 0, "fat": 0, "carbs": 0},
            "tips": ["Попробуйте отправить другую ссылку на рецепт"],
            "storage": "",
            "tags": [],
            "is_vegetarian": False,
            "is_vegan": False,
            "is_gluten_free": False,
            "is_lactose_free": False,
            "error": error
        }
