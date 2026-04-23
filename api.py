from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from dotenv import load_dotenv

from app.backend.factory import build_repository
from app.shared.config import Settings

BASE_DIR = Path(__file__).parent
WEBAPP_DIR = BASE_DIR / "frontend" / "miniapp"
LEGACY_WEBAPP_DIR = BASE_DIR / "webapp"

load_dotenv()
settings = Settings.from_env()
repository = build_repository(settings)

app = FastAPI(title="Recipe Parser Mini App API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _resolve_webapp_dir() -> Path:
    required = ["index.html", "recipe-detail.html", "app.js", "styles.css"]
    if all((WEBAPP_DIR / file_name).exists() for file_name in required):
        return WEBAPP_DIR
    return LEGACY_WEBAPP_DIR


STATIC_DIR = _resolve_webapp_dir()


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/categories/{user_id}")
async def get_categories(user_id: int):
    return repository.get_categories(user_id)


@app.get("/api/recipes/{user_id}/{category}")
async def get_recipes(user_id: int, category: str):
    return repository.get_recipes_in_category(user_id, category)


@app.get("/api/recipe/{recipe_id}")
async def get_recipe(recipe_id: str):
    recipe = repository.get_recipe(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@app.get("/", include_in_schema=False)
async def webapp_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/recipe", include_in_schema=False)
async def webapp_recipe_detail():
    return FileResponse(STATIC_DIR / "recipe-detail.html")


app.mount("/webapp", StaticFiles(directory=STATIC_DIR), name="webapp")
