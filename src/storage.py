"""
Адаптер для совместимости с новым RecipeStorage.
Перенаправляет все вызовы на новый модуль recipe_storage.
"""

from recipe_storage import RecipeStorage, MealType

# Реэкспорт для обратной совместимости
__all__ = ['RecipeStorage', 'MealType']
