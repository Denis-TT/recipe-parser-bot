import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    github_token: str
    supabase_url: str
    supabase_key: str
    webapp_url: str
    api_host: str
    api_port: int
    log_level: str
    local_storage_path: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_key=os.getenv("SUPABASE_KEY", ""),
            webapp_url=os.getenv("WEBAPP_URL", "http://localhost:8000"),
            api_host=os.getenv("API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("API_PORT", "8000")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            local_storage_path=os.getenv("LOCAL_STORAGE_PATH", "data/local_recipes"),
        )
