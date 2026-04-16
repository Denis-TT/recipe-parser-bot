"""
Модуль для локального хранения рецептов в формате JSON.
Организация по категориям блюд с индексным файлом для быстрого поиска.

Автор: Recipe Parser Bot
Версия: 2.0.0
"""

import os
import json
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
import logging
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class MealType(Enum):
    """Типы приемов пищи"""
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    DESSERT = "dessert"
    SNACK = "snack"
    SALAD = "salad"
    SOUP = "soup"
    BAKING = "baking"
    DRINK = "drink"
    OTHER = "other"

    @classmethod
    def get_emoji(cls, meal_type: str) -> str:
        """Возвращает эмодзи для типа блюда"""
        emoji_map = {
            "breakfast": "🍳",
            "lunch": "🍲",
            "dinner": "🍽️",
            "dessert": "🍰",
            "snack": "🥨",
            "salad": "🥗",
            "soup": "🥣",
            "baking": "🧁",
            "drink": "🥤",
            "other": "📦"
        }
        return emoji_map.get(meal_type, "🍴")

    @classmethod
    def get_folder_name(cls, meal_type: str) -> str:
        """Возвращает имя папки для типа блюда"""
        folder_map = {
            "breakfast": "breakfasts",
            "lunch": "lunches",
            "dinner": "dinners",
            "dessert": "desserts",
            "snack": "snacks",
            "salad": "salads",
            "soup": "soups",
            "baking": "baking",
            "drink": "drinks",
            "other": "other"
        }
        return folder_map.get(meal_type, "other")


class Difficulty(Enum):
    """Сложность приготовления"""
    EASY = "легко"
    MEDIUM = "средне"
    HARD = "сложно"


@dataclass
class Ingredient:
    """Ингредиент рецепта"""
    name: str
    amount: Union[float, str]
    unit: str
    notes: str = ""


@dataclass
class CookingStep:
    """Шаг приготовления"""
    step_number: int
    description: str
    time: Optional[Union[str, int]] = None


@dataclass
class NutritionInfo:
    """Информация о пищевой ценности"""
    calories: int = 0
    protein: int = 0
    fat: int = 0
    carbs: int = 0
    fiber: int = 0


@dataclass
class Recipe:
    """Полная структура рецепта"""
    title: str
    meal_type: str
    ingredients: List[Dict[str, Any]]
    steps: List[Dict[str, Any]]
    description: str = ""
    cuisine: str = "интернациональная"
    difficulty: str = "средне"
    prep_time: int = 0
    cook_time: int = 0
    total_time: int = 0
    servings: int = 4
    nutrition: Dict[str, int] = None
    nutrition_per_serving: Dict[str, int] = None
    total_nutrition: Dict[str, int] = None
    equipment: List[str] = None
    tips: List[str] = None
    storage: str = ""
    tags: List[str] = None
    is_vegetarian: bool = False
    is_vegan: bool = False
    is_gluten_free: bool = False
    is_lactose_free: bool = False
    source_url: str = ""
    processed_at: str = ""
    version: str = "2.0"
    
    def __post_init__(self):
        if self.nutrition is None:
            self.nutrition = {}
        if self.nutrition_per_serving is None:
            self.nutrition_per_serving = {}
        if self.total_nutrition is None:
            self.total_nutrition = {}
        if self.equipment is None:
            self.equipment = []
        if self.tips is None:
            self.tips = []
        if self.tags is None:
            self.tags = []
        if not self.processed_at:
            self.processed_at = datetime.now().isoformat()
        if not self.total_time:
            self.total_time = self.prep_time + self.cook_time


class RecipeStorage:
    """
    Класс для управления локальным хранилищем рецептов.
    
    Структура хранения:
    output/
    ├── index.json
    ├── recipes/
    │   ├── breakfasts/
    │   ├── lunches/
    │   ├── dinners/
    │   └── ...
    └── backups/
    """
    
    VERSION = "2.0.0"
    REQUIRED_FIELDS = ["title", "meal_type", "ingredients", "steps"]
    
    def __init__(self, base_path: str = "output"):
        """
        Инициализация хранилища рецептов.
        
        Args:
            base_path: Базовый путь для хранения данных
        """
        self.base_path = Path(base_path)
        self.recipes_path = self.base_path / "recipes"
        self.backups_path = self.base_path / "backups"
        self.index_file = self.base_path / "index.json"
        
        self._create_directory_structure()
        self._load_index()
        
        logger.info(f"Хранилище инициализировано: {self.base_path.absolute()}")
    
    def _create_directory_structure(self) -> None:
        """Создание структуры папок для хранения рецептов"""
        # Создаем базовые папки
        self.recipes_path.mkdir(parents=True, exist_ok=True)
        self.backups_path.mkdir(parents=True, exist_ok=True)
        
        # Создаем подпапки для каждого типа блюд
        for meal_type in MealType:
            folder_name = MealType.get_folder_name(meal_type.value)
            (self.recipes_path / folder_name).mkdir(exist_ok=True)
        
        logger.debug("Структура папок создана")
    
    def _load_index(self) -> None:
        """Загрузка индексного файла"""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    self.index = json.load(f)
                logger.debug(f"Индекс загружен: {len(self.index.get('recipes', []))} рецептов")
            except Exception as e:
                logger.error(f"Ошибка загрузки индекса: {e}")
                self._create_empty_index()
        else:
            self._create_empty_index()
            self._save_index()
    
    def _create_empty_index(self) -> None:
        """Создание пустого индексного файла"""
        self.index = {
            "version": self.VERSION,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "total_recipes": 0,
            "recipes": [],
            "statistics": {mt.value: 0 for mt in MealType}
        }
    
    def _save_index(self) -> None:
        """Сохранение индексного файла"""
        self.index["updated_at"] = datetime.now().isoformat()
        
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)
        
        logger.debug("Индекс сохранен")
    
    def _update_index_add(self, recipe_data: Dict[str, Any], file_path: str) -> None:
        """Обновление индекса при добавлении рецепта"""
        meal_type = recipe_data.get("meal_type", "other")
        
        index_entry = {
            "title": recipe_data.get("title", "Без названия"),
            "meal_type": meal_type,
            "file_path": str(file_path),
            "saved_at": recipe_data.get("processed_at", datetime.now().isoformat()),
            "cuisine": recipe_data.get("cuisine", ""),
            "difficulty": recipe_data.get("difficulty", ""),
            "total_time": recipe_data.get("total_time", 0),
            "servings": recipe_data.get("servings", 4),
            "calories": recipe_data.get("nutrition_per_serving", {}).get("calories", 0),
            "tags": recipe_data.get("tags", []),
            "is_vegetarian": recipe_data.get("is_vegetarian", False),
            "is_vegan": recipe_data.get("is_vegan", False),
            "is_gluten_free": recipe_data.get("is_gluten_free", False)
        }
        
        self.index["recipes"].append(index_entry)
        self.index["total_recipes"] = len(self.index["recipes"])
        
        # Обновляем статистику
        if meal_type in self.index["statistics"]:
            self.index["statistics"][meal_type] += 1
        else:
            self.index["statistics"]["other"] = self.index["statistics"].get("other", 0) + 1
        
        self._save_index()
        logger.info(f"Рецепт добавлен в индекс: {recipe_data.get('title')}")
    
    def _update_index_remove(self, file_path: str) -> None:
        """Обновление индекса при удалении рецепта"""
        path_str = str(file_path)
        
        for i, recipe in enumerate(self.index["recipes"]):
            if recipe["file_path"] == path_str:
                meal_type = recipe["meal_type"]
                
                # Уменьшаем счетчик в статистике
                if meal_type in self.index["statistics"]:
                    self.index["statistics"][meal_type] = max(0, self.index["statistics"][meal_type] - 1)
                
                # Удаляем из списка
                del self.index["recipes"][i]
                self.index["total_recipes"] = len(self.index["recipes"])
                
                self._save_index()
                logger.info(f"Рецепт удален из индекса: {recipe['title']}")
                return
        
        logger.warning(f"Рецепт не найден в индексе: {path_str}")
    
    @staticmethod
    def _slugify(text: str) -> str:
        """
        Преобразование строки в безопасное имя файла.
        Транслитерация, только латиница, цифры и подчеркивания.
        
        Args:
            text: Исходный текст
            
        Returns:
            Безопасное имя файла
        """
        # Транслитерация русских букв
        translit_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
            'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
            'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
            'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
            'Ф': 'F', 'Х': 'H', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch',
            'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
        }
        
        text = text.lower()
        for ru, en in translit_map.items():
            text = text.replace(ru, en)
        
        # Удаление диакритических знаков
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
        
        # Замена пробелов и спецсимволов на подчеркивания
        text = re.sub(r'[^a-zA-Z0-9]+', '_', text)
        
        # Удаление лишних подчеркиваний
        text = re.sub(r'_+', '_', text).strip('_')
        
        return text[:50] or "recipe"
    
    @staticmethod
    def _generate_filename(recipe: Dict[str, Any]) -> str:
        """
        Генерация имени файла по шаблону:
        {meal_type}_{slugified_title}_{timestamp}.json
        
        Args:
            recipe: Данные рецепта
            
        Returns:
            Имя файла
        """
        meal_type = recipe.get("meal_type", "other")
        title = recipe.get("title", "recipe")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        slug = RecipeStorage._slugify(title)
        
        return f"{meal_type}_{slug}_{timestamp}.json"
    
    @staticmethod
    def _validate_recipe(recipe: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Проверка обязательных полей рецепта.
        
        Args:
            recipe: Данные рецепта
            
        Returns:
            (валидность, сообщение об ошибке)
        """
        for field in RecipeStorage.REQUIRED_FIELDS:
            if field not in recipe or not recipe[field]:
                return False, f"Отсутствует обязательное поле: {field}"
        
        if not isinstance(recipe.get("ingredients"), list) or len(recipe["ingredients"]) == 0:
            return False, "Ингредиенты должны быть непустым списком"
        
        if not isinstance(recipe.get("steps"), list) or len(recipe["steps"]) == 0:
            return False, "Шаги приготовления должны быть непустым списком"
        
        return True, "OK"
    
    def _create_backup(self, file_path: Path) -> Optional[Path]:
        """
        Создание резервной копии перед перезаписью.
        
        Args:
            file_path: Путь к оригинальному файлу
            
        Returns:
            Путь к резервной копии или None
        """
        if not file_path.exists():
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_backup_{timestamp}.json"
        backup_path = self.backups_path / backup_name
        
        shutil.copy2(file_path, backup_path)
        logger.info(f"Создана резервная копия: {backup_path}")
        
        return backup_path
    
    def save_recipe(self, recipe_data: Dict[str, Any], create_backup: bool = False) -> str:
        """
        Сохранение рецепта в соответствующую подпапку.
        
        Args:
            recipe_data: Данные рецепта
            create_backup: Создавать ли резервную копию при перезаписи
            
        Returns:
            Путь к сохраненному файлу
            
        Raises:
            ValueError: Если рецепт не прошел валидацию
        """
        # Валидация
        is_valid, error_msg = self._validate_recipe(recipe_data)
        if not is_valid:
            raise ValueError(f"Некорректный рецепт: {error_msg}")
        
        # Добавляем метаданные если их нет
        if "processed_at" not in recipe_data:
            recipe_data["processed_at"] = datetime.now().isoformat()
        if "version" not in recipe_data:
            recipe_data["version"] = "2.0"
        
        # Определяем папку для сохранения
        meal_type = recipe_data.get("meal_type", "other")
        folder_name = MealType.get_folder_name(meal_type)
        target_dir = self.recipes_path / folder_name
        
        # Генерируем имя файла
        filename = self._generate_filename(recipe_data)
        file_path = target_dir / filename
        
        # Проверяем на дубликаты (по URL или названию)
        existing = self._find_duplicate(recipe_data)
        if existing:
            logger.warning(f"Найден дубликат рецепта: {existing}")
            if create_backup:
                self._create_backup(existing)
        
        # Сохраняем файл
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(recipe_data, f, ensure_ascii=False, indent=2)
        
        # Обновляем индекс
        self._update_index_add(recipe_data, file_path)
        
        logger.info(f"Рецепт сохранен: {file_path}")
        return str(file_path)
    
    def _find_duplicate(self, recipe_data: Dict[str, Any]) -> Optional[Path]:
        """
        Поиск дубликата рецепта по source_url или названию.
        
        Args:
            recipe_data: Данные рецепта
            
        Returns:
            Путь к существующему файлу или None
        """
        source_url = recipe_data.get("source_url")
        title = recipe_data.get("title")
        
        for entry in self.index.get("recipes", []):
            # Проверяем по URL (более надежно)
            if source_url:
                existing_path = Path(entry["file_path"])
                if existing_path.exists():
                    try:
                        with open(existing_path, 'r', encoding='utf-8') as f:
                            existing_recipe = json.load(f)
                            if existing_recipe.get("source_url") == source_url:
                                return existing_path
                    except:
                        pass
            
            # Проверяем по названию (менее надежно, но полезно)
            if title and entry["title"] == title:
                return Path(entry["file_path"])
        
        return None
    
    def load_recipe(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Загрузка рецепта из файла.
        
        Args:
            file_path: Путь к файлу рецепта
            
        Returns:
            Данные рецепта или None при ошибке
        """
        path = Path(file_path)
        
        if not path.exists():
            logger.error(f"Файл не найден: {file_path}")
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                recipe = json.load(f)
            logger.debug(f"Рецепт загружен: {path.name}")
            return recipe
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка загрузки файла: {e}")
            return None
    
    def get_recipes_by_meal_type(self, meal_type: str) -> List[Dict[str, Any]]:
        """
        Получение списка рецептов указанной категории.
        
        Args:
            meal_type: Тип блюда (breakfast, lunch, dinner, etc.)
            
        Returns:
            Список рецептов
        """
        folder_name = MealType.get_folder_name(meal_type)
        target_dir = self.recipes_path / folder_name
        
        recipes = []
        
        if not target_dir.exists():
            logger.warning(f"Папка не существует: {target_dir}")
            return recipes
        
        for file_path in target_dir.glob("*.json"):
            recipe = self.load_recipe(str(file_path))
            if recipe:
                recipes.append(recipe)
        
        logger.info(f"Загружено {len(recipes)} рецептов типа '{meal_type}'")
        return recipes
    
    def get_all_recipes(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Получение всех рецептов, сгруппированных по категориям.
        
        Returns:
            Словарь {категория: [список рецептов]}
        """
        all_recipes = {}
        
        for meal_type in MealType:
            recipes = self.get_recipes_by_meal_type(meal_type.value)
            if recipes:
                all_recipes[meal_type.value] = recipes
        
        total = sum(len(r) for r in all_recipes.values())
        logger.info(f"Загружено {total} рецептов из {len(all_recipes)} категорий")
        
        return all_recipes
    
    def search_recipes(self, query: str) -> List[Dict[str, Any]]:
        """
        Поиск рецептов по названию, описанию, тегам и ингредиентам.
        
        Args:
            query: Поисковый запрос
            
        Returns:
            Список найденных рецептов
        """
        query_lower = query.lower()
        results = []
        
        for entry in self.index.get("recipes", []):
            # Поиск по названию
            if query_lower in entry["title"].lower():
                recipe = self.load_recipe(entry["file_path"])
                if recipe:
                    results.append(recipe)
                continue
            
            # Поиск по тегам
            if any(query_lower in tag.lower() for tag in entry.get("tags", [])):
                recipe = self.load_recipe(entry["file_path"])
                if recipe:
                    results.append(recipe)
                continue
            
            # Поиск по кухне
            if query_lower in entry.get("cuisine", "").lower():
                recipe = self.load_recipe(entry["file_path"])
                if recipe:
                    results.append(recipe)
        
        logger.info(f"Поиск '{query}': найдено {len(results)} рецептов")
        return results
    
    def delete_recipe(self, file_path: str, create_backup: bool = True) -> bool:
        """
        Удаление рецепта.
        
        Args:
            file_path: Путь к файлу рецепта
            create_backup: Создать резервную копию перед удалением
            
        Returns:
            True если удаление успешно
        """
        path = Path(file_path)
        
        if not path.exists():
            logger.error(f"Файл не найден: {file_path}")
            return False
        
        try:
            if create_backup:
                self._create_backup(path)
            
            path.unlink()
            self._update_index_remove(file_path)
            
            logger.info(f"Рецепт удален: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления файла: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Получение статистики хранилища.
        
        Returns:
            Словарь со статистикой
        """
        stats = {
            "total_recipes": self.index.get("total_recipes", 0),
            "by_meal_type": self.index.get("statistics", {}),
            "storage_path": str(self.base_path.absolute()),
            "index_version": self.index.get("version", "unknown"),
            "created_at": self.index.get("created_at"),
            "updated_at": self.index.get("updated_at")
        }
        
        # Добавляем размер хранилища
        total_size = 0
        for file_path in self.recipes_path.rglob("*.json"):
            total_size += file_path.stat().st_size
        stats["total_size_mb"] = round(total_size / (1024 * 1024), 2)
        
        return stats
    
    def get_categories(self) -> List[Dict[str, Any]]:
        """
        Получение списка категорий с количеством рецептов.
        
        Returns:
            Список категорий для отображения в меню
        """
        categories = []
        stats = self.index.get("statistics", {})
        
        for meal_type, count in stats.items():
            if count > 0:
                categories.append({
                    "key": meal_type,
                    "name": MealType.get_folder_name(meal_type).capitalize(),
                    "emoji": MealType.get_emoji(meal_type),
                    "count": count
                })
        
        return sorted(categories, key=lambda x: x["count"], reverse=True)
    
    def get_recipes_list(self, meal_type: str) -> List[Dict[str, Any]]:
        """
        Получение списка рецептов для отображения в меню.
        
        Args:
            meal_type: Тип блюда
            
        Returns:
            Список с краткой информацией о рецептах
        """
        recipes = []
        
        for entry in self.index.get("recipes", []):
            if entry["meal_type"] == meal_type:
                recipes.append({
                    "title": entry["title"],
                    "file_path": entry["file_path"],
                    "saved_at": entry.get("saved_at", ""),
                    "calories": entry.get("calories", 0),
                    "total_time": entry.get("total_time", 0),
                    "difficulty": entry.get("difficulty", "средне")
                })
        
        return sorted(recipes, key=lambda x: x["saved_at"], reverse=True)


# ============ ТЕСТОВЫЙ ПРИМЕР ============

if __name__ == "__main__":
    # Настройка логирования для теста
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Создаем хранилище
    storage = RecipeStorage()
    
    # Пример рецепта
    sample_recipe = {
        "title": "Паста Карбонара",
        "description": "Классическая итальянская паста с яичным соусом и беконом",
        "cuisine": "итальянская",
        "meal_type": "dinner",
        "difficulty": "средне",
        "prep_time": 10,
        "cook_time": 20,
        "total_time": 30,
        "servings": 4,
        "ingredients": [
            {"name": "Спагетти", "amount": 400, "unit": "г", "notes": ""},
            {"name": "Бекон", "amount": 150, "unit": "г", "notes": "или панчетта"},
            {"name": "Яйца", "amount": 3, "unit": "шт", "notes": ""},
            {"name": "Пармезан", "amount": 100, "unit": "г", "notes": "тертый"}
        ],
        "steps": [
            {"step_number": 1, "description": "Сварить спагетти в подсоленной воде"},
            {"step_number": 2, "description": "Обжарить бекон до хрустящей корочки"}
        ],
        "nutrition_per_serving": {
            "calories": 550,
            "protein": 25,
            "fat": 22,
            "carbs": 65
        },
        "tips": ["Не солите сильно - бекон и пармезан уже соленые"],
        "storage": "В холодильнике до 2 дней",
        "tags": ["паста", "италия", "быстро"],
        "is_vegetarian": False,
        "source_url": "https://example.com/carbonara"
    }
    
    # Сохраняем рецепт
    filepath = storage.save_recipe(sample_recipe)
    print(f"\n✅ Рецепт сохранён: {filepath}")
    
    # Получаем ужины
    dinners = storage.get_recipes_by_meal_type("dinner")
    print(f"\n🍽️ Найдено ужинов: {len(dinners)}")
    
    # Статистика
    stats = storage.get_statistics()
    print(f"\n📊 Статистика:")
    print(f"   Всего рецептов: {stats['total_recipes']}")
    print(f"   По категориям: {stats['by_meal_type']}")
    print(f"   Размер: {stats['total_size_mb']} MB")
    
    # Категории для меню
    categories = storage.get_categories()
    print(f"\n📂 Категории для меню:")
    for cat in categories:
        print(f"   {cat['emoji']} {cat['name']}: {cat['count']} рецептов")
    
    print("\n✅ Тест завершен успешно!")
