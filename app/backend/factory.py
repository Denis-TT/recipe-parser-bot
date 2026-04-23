import logging

from app.backend.local_repository import LocalRecipeRepository
from app.backend.repository import RecipeRepository
from app.backend.supabase_repository import SupabaseRecipeRepository
from app.shared.config import Settings

logger = logging.getLogger(__name__)


def build_repository(settings: Settings) -> RecipeRepository:
    if settings.supabase_url and settings.supabase_key:
        try:
            logger.info("Using Supabase repository")
            return SupabaseRecipeRepository(settings.supabase_url, settings.supabase_key)
        except Exception as error:
            logger.warning("Supabase unavailable, fallback to local storage: %s", error)
    logger.info("Using local JSON repository")
    return LocalRecipeRepository(settings.local_storage_path)
