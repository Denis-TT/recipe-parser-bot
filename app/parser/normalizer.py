import json
import logging
from typing import Any, Dict

import aiohttp

from app.shared.constants import MEAL_TYPE_ALIASES, SUPPORTED_MEAL_TYPES

logger = logging.getLogger(__name__)


class GitHubModelNormalizer:
    """Normalizes raw recipe text into structured JSON using GitHub Models API."""

    def __init__(self, github_token: str, model: str = "gpt-4o-mini") -> None:
        self._github_token = github_token
        self._model = model
        self._api_url = "https://models.inference.ai.azure.com/chat/completions"
        self._system_prompt = (
            "You are an expert chef and nutritionist. Extract structured recipe JSON only. "
            "meal_type must be one of: breakfast,lunch,dinner,dessert,snack,salad,soup,baking,drink,other."
        )

    async def normalize(self, raw_text: str) -> Dict[str, Any]:
        if not raw_text:
            return self._error_payload("Empty text")

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": raw_text[:30000]},
            ],
            "temperature": 0.2,
            "max_tokens": 2500,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._github_token}",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._api_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error("GitHub model API error: %s %s", response.status, error_text)
                        return self._error_payload(f"API error {response.status}")
                    data = await response.json()
        except Exception as error:
            logger.error("Model request failed: %s", error, exc_info=True)
            return self._error_payload(str(error)[:120])

        try:
            content = data["choices"][0]["message"]["content"].strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            recipe = json.loads(content.strip())
            recipe["meal_type"] = self._normalize_meal_type(recipe.get("meal_type"))
            return recipe
        except Exception as error:
            logger.error("Invalid model response payload: %s", error, exc_info=True)
            return self._error_payload("Invalid JSON response")

    def _normalize_meal_type(self, meal_type: Any) -> str:
        normalized = str(meal_type or "").strip().lower()
        normalized = MEAL_TYPE_ALIASES.get(normalized, normalized or "other")
        if normalized not in SUPPORTED_MEAL_TYPES:
            return "other"
        return normalized

    @staticmethod
    def _error_payload(error: str) -> Dict[str, Any]:
        return {
            "title": "Recipe parsing error",
            "description": f"Failed to normalize recipe: {error}",
            "meal_type": "other",
            "ingredients": [],
            "steps": [],
            "nutrition_per_serving": {"calories": 0, "protein": 0, "fat": 0, "carbs": 0},
            "nutrition": {"calories": 0, "protein": 0, "fat": 0, "carbs": 0},
            "tips": [],
        }
