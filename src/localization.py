"""
Модуль локализации для Recipe Parser Bot.
Разделяет внутренние ключи (латиница) и отображение (русский/другие языки).
"""


class Localization:
    # Все возможные значения meal_type (только латиница!)
    VALID_MEAL_TYPES = [
        "breakfast", "lunch", "dinner", "dessert",
        "snack", "salad", "soup", "baking", "drink", "other"
    ]

    # Все возможные значения difficulty (только латиница!)
    VALID_DIFFICULTY = ["easy", "medium", "hard"]

    # Словари локализации
    TRANSLATIONS = {
        "ru": {
            # Категории блюд
            "meal_type_breakfast": "Завтраки",
            "meal_type_lunch": "Обеды",
            "meal_type_dinner": "Ужины",
            "meal_type_dessert": "Десерты",
            "meal_type_snack": "Перекусы",
            "meal_type_salad": "Салаты",
            "meal_type_soup": "Супы",
            "meal_type_baking": "Выпечка",
            "meal_type_drink": "Напитки",
            "meal_type_other": "Другое",

            # Сложность
            "difficulty_easy": "Легко",
            "difficulty_medium": "Средне",
            "difficulty_hard": "Сложно",

            # Кухни
            "cuisine_italian": "Итальянская",
            "cuisine_russian": "Русская",
            "cuisine_japanese": "Японская",
            "cuisine_french": "Французская",
            "cuisine_chinese": "Китайская",
            "cuisine_georgian": "Грузинская",
            "cuisine_korean": "Корейская",
            "cuisine_indian": "Индийская",
            "cuisine_thai": "Тайская",
            "cuisine_mexican": "Мексиканская",
            "cuisine_mediterranean": "Средиземноморская",
            "cuisine_american": "Американская",
            "cuisine_european": "Европейская",
            "cuisine_asian": "Азиатская",
            "cuisine_other": "Другая",

            # Общие фразы
            "ingredients": "Ингредиенты",
            "steps": "Приготовление",
            "tips": "Советы",
            "storage": "Хранение",
            "nutrition": "Пищевая ценность",
            "calories": "Калории",
            "protein": "Белки",
            "fat": "Жиры",
            "carbs": "Углеводы",
            "fiber": "Клетчатка",
            "servings": "Порций",
            "minutes": "мин",
            "hours": "ч",
        }
    }

    # Эмодзи для категорий
    MEAL_TYPE_EMOJIS = {
        "breakfast": "🍳",
        "lunch": "🍲",
        "dinner": "🍽️",
        "dessert": "🍰",
        "snack": "🥨",
        "salad": "🥗",
        "soup": "🥣",
        "baking": "🧁",
        "drink": "🥤",
        "other": "📦",
    }

    DIFFICULTY_EMOJIS = {
        "easy": "🟢",
        "medium": "🟡",
        "hard": "🔴",
    }

    def __init__(self, language: str = "ru"):
        self.language = language if language in self.TRANSLATIONS else "ru"

    def translate(self, key: str, category: str = "") -> str:
        """Перевод ключа с учетом категории"""
        full_key = f"{category}_{key}" if category else key
        return self.TRANSLATIONS.get(self.language, {}).get(full_key, str(key))

    def get_meal_type_name(self, meal_type: str) -> str:
        """Локализованное название категории (например: 'Обеды')"""
        return self.translate(meal_type, "meal_type")

    def get_meal_type_emoji(self, meal_type: str) -> str:
        """Эмодзи для категории"""
        return self.MEAL_TYPE_EMOJIS.get(meal_type, "🍴")

    def get_meal_type_display(self, meal_type: str) -> str:
        """Полное отображение: '🍲 Обеды'"""
        emoji = self.get_meal_type_emoji(meal_type)
        name = self.get_meal_type_name(meal_type)
        return f"{emoji} {name}"

    def get_difficulty_name(self, difficulty: str) -> str:
        """Локализованное название сложности"""
        return self.translate(difficulty, "difficulty")

    def get_difficulty_display(self, difficulty: str) -> str:
        """Сложность с эмодзи: '🟡 Средне'"""
        emoji = self.DIFFICULTY_EMOJIS.get(difficulty, "")
        name = self.get_difficulty_name(difficulty)
        return f"{emoji} {name}" if emoji else name

    def get_cuisine_name(self, cuisine: str) -> str:
        """Локализованное название кухни"""
        if not cuisine:
            return self.translate("other", "cuisine")
        normalized = self.normalize_cuisine(cuisine)
        return self.translate(normalized, "cuisine")

    @staticmethod
    def normalize_meal_type(value) -> str:
        """
        Нормализация meal_type ВСЕГДА в латиницу.
        Принимает любое значение (русское, английское, смешанное).
        Возвращает СТРОГО одно из VALID_MEAL_TYPES.
        """
        if not value:
            return "other"

        value = str(value).lower().strip()

        mapping = {
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
            "другое": "other",
            "основное блюдо": "dinner",
            "горячее": "dinner",
            "второе": "dinner",
            "первое": "soup",
            "десерты": "dessert",
            "напитки": "drink",
            "салаты": "salad",
            "супы": "soup",
            "закуски": "snack",
            "завтраки": "breakfast",
            "обеды": "lunch",
            "ужины": "dinner",
            "breakfast": "breakfast",
            "lunch": "lunch",
            "dinner": "dinner",
            "dessert": "dessert",
            "snack": "snack",
            "appetizer": "snack",
            "starter": "snack",
            "salad": "salad",
            "soup": "soup",
            "baking": "baking",
            "bake": "baking",
            "drink": "drink",
            "beverage": "drink",
            "other": "other",
            "main": "dinner",
            "main course": "dinner",
            "breakfasts": "breakfast",
            "lunches": "lunch",
            "dinners": "dinner",
            "desserts": "dessert",
            "snacks": "snack",
            "salads": "salad",
            "soups": "soup",
            "drinks": "drink",
        }

        return mapping.get(value, "other")

    @staticmethod
    def normalize_difficulty(value) -> str:
        """
        Нормализация сложности ВСЕГДА в латиницу.
        Возвращает: easy, medium, hard
        """
        if not value:
            return "medium"

        value = str(value).lower().strip()

        mapping = {
            "легко": "easy",
            "лёгко": "easy",
            "легкая": "easy",
            "легкое": "easy",
            "лёгкая": "easy",
            "просто": "easy",
            "простая": "easy",
            "простое": "easy",
            "easy": "easy",
            "beginner": "easy",
            "средне": "medium",
            "среднее": "medium",
            "средняя": "medium",
            "средний": "medium",
            "нормально": "medium",
            "medium": "medium",
            "normal": "medium",
            "intermediate": "medium",
            "сложно": "hard",
            "сложное": "hard",
            "сложная": "hard",
            "сложный": "hard",
            "тяжело": "hard",
            "трудно": "hard",
            "hard": "hard",
            "difficult": "hard",
            "advanced": "hard",
            "expert": "hard",
        }

        return mapping.get(value, "medium")

    @staticmethod
    def normalize_cuisine(value) -> str:
        """
        Нормализация кухни ВСЕГДА в латиницу.
        """
        if not value:
            return "other"

        value = str(value).lower().strip()

        mapping = {
            "итальянская": "italian",
            "италия": "italian",
            "русская": "russian",
            "российская": "russian",
            "руссия": "russian",
            "японская": "japanese",
            "япония": "japanese",
            "французская": "french",
            "франция": "french",
            "китайская": "chinese",
            "китай": "chinese",
            "грузинская": "georgian",
            "грузия": "georgian",
            "корейская": "korean",
            "корея": "korean",
            "индийская": "indian",
            "индия": "indian",
            "тайская": "thai",
            "таиланд": "thai",
            "мексиканская": "mexican",
            "мексика": "mexican",
            "средиземноморская": "mediterranean",
            "американская": "american",
            "сша": "american",
            "европейская": "european",
            "азиатская": "asian",
            "кавказская": "caucasian",
            "украинская": "ukrainian",
            "белорусская": "belarusian",
            "немецкая": "german",
            "германия": "german",
            "испанская": "spanish",
            "испания": "spanish",
            "турецкая": "turkish",
            "турция": "turkish",
            "греческая": "greek",
            "греция": "greek",
            "арабская": "arabic",
            "восточная": "eastern",
            "домашняя": "homemade",
            "другая": "other",
            "интернациональная": "international",
            "italian": "italian",
            "russian": "russian",
            "japanese": "japanese",
            "french": "french",
            "chinese": "chinese",
            "georgian": "georgian",
            "korean": "korean",
            "indian": "indian",
            "thai": "thai",
            "mexican": "mexican",
            "mediterranean": "mediterranean",
            "american": "american",
            "european": "european",
            "asian": "asian",
            "caucasian": "caucasian",
            "ukrainian": "ukrainian",
            "belarusian": "belarusian",
            "german": "german",
            "spanish": "spanish",
            "turkish": "turkish",
            "greek": "greek",
            "arabic": "arabic",
            "eastern": "eastern",
            "homemade": "homemade",
            "other": "other",
            "international": "international",
        }

        return mapping.get(value, value)

    @staticmethod
    def normalize_recipe(recipe: dict) -> dict:
        """
        Полная нормализация рецепта.
        Приводит все ключевые поля к латинице.
        """
        if not recipe:
            return recipe

        normalized = dict(recipe)

        if "meal_type" in normalized:
            normalized["meal_type"] = Localization.normalize_meal_type(normalized["meal_type"])

        if "difficulty" in normalized:
            normalized["difficulty"] = Localization.normalize_difficulty(normalized["difficulty"])

        if "cuisine" in normalized:
            normalized["cuisine"] = Localization.normalize_cuisine(normalized["cuisine"])

        if "tags" in normalized and isinstance(normalized["tags"], list):
            normalized["tags"] = [str(t).lower().strip() for t in normalized["tags"]]

        return normalized

    def format_recipe_for_display(self, recipe: dict) -> dict:
        """
        Форматирует рецепт для отображения пользователю.
        Добавляет локализованные названия рядом с ключами.
        """
        display = dict(recipe)

        if "meal_type" in display:
            display["meal_type_display"] = self.get_meal_type_display(display["meal_type"])

        if "difficulty" in display:
            display["difficulty_display"] = self.get_difficulty_display(display["difficulty"])

        if "cuisine" in display:
            display["cuisine_display"] = self.get_cuisine_name(display["cuisine"])

        return display

    def get_all_meal_types_for_display(self) -> list:
        """Список всех категорий для отображения в меню"""
        return [
            {
                "key": mt,
                "name": self.get_meal_type_name(mt),
                "emoji": self.get_meal_type_emoji(mt),
                "display": self.get_meal_type_display(mt),
            }
            for mt in self.VALID_MEAL_TYPES
        ]
