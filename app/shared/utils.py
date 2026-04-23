import re
from typing import Any, Dict


def validate_url(url: str) -> bool:
    pattern = re.compile(
        r"^https?://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
        r"localhost|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return bool(pattern.match(url))


def format_recipe_for_telegram(recipe: Dict[str, Any]) -> str:
    if not recipe:
        return "❌ Recipe parsing failed."

    title = recipe.get("title", "Untitled recipe")
    meal_type = recipe.get("meal_type", "other")
    cuisine = recipe.get("cuisine", "international")
    difficulty = recipe.get("difficulty", "medium")
    total_time = recipe.get("total_time", 0)
    servings = recipe.get("servings", 1)
    nutrition = recipe.get("nutrition_per_serving", {}) or {}

    lines = [
        f"🍴 *{title}*",
        "",
        f"🍽 {cuisine} | 📋 {meal_type} | 📊 {difficulty}",
        f"⏱ {total_time} min | 👥 {servings}",
    ]

    if nutrition.get("calories"):
        lines.extend(
            [
                "",
                "*📊 Nutrition per serving:*",
                f"🔥 {nutrition.get('calories', 0)} kcal",
                f"💪 {nutrition.get('protein', 0)} g protein",
                f"🧈 {nutrition.get('fat', 0)} g fat",
                f"🍚 {nutrition.get('carbs', 0)} g carbs",
            ]
        )

    ingredients = recipe.get("ingredients", [])
    if ingredients:
        lines.extend(["", "*🛒 Ingredients:*"])
        for ingredient in ingredients:
            if isinstance(ingredient, dict):
                name = ingredient.get("name", "").strip()
                amount = str(ingredient.get("amount", "")).strip()
                unit = str(ingredient.get("unit", "")).strip()
                lines.append(f"• {' '.join(part for part in [amount, unit, name] if part)}")
            else:
                lines.append(f"• {ingredient}")

    steps = recipe.get("steps", [])
    if steps:
        lines.extend(["", "*📝 Steps:*"])
        for index, step in enumerate(steps, start=1):
            if isinstance(step, dict):
                text = step.get("description", "")
            else:
                text = str(step)
            lines.append(f"{index}. {text}")

    return "\n".join(lines)[:3900]
