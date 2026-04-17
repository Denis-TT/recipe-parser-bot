import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from supabase import create_client

BASE_DIR = Path(__file__).parent
WEBAPP_DIR = BASE_DIR / "webapp"

app = FastAPI(title="Recipe Parser Mini App API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


@app.get("/api/categories/{user_id}")
async def get_categories(user_id: int):
    result = supabase.rpc("get_user_categories", {"p_user_id": user_id}).execute()
    return result.data or []


@app.get("/api/recipes/{user_id}/{category}")
async def get_recipes(user_id: int, category: str):
    result = (
        supabase.table("recipes")
        .select("id,title,meal_type,cook_time,total_time,nutrition_per_serving,created_at")
        .eq("user_id", user_id)
        .eq("meal_type", category)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


@app.get("/api/recipe/{recipe_id}")
async def get_recipe(recipe_id: str):
    result = supabase.table("recipes").select("*").eq("id", recipe_id).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return result.data[0]


@app.get("/", include_in_schema=False)
async def webapp_index():
    return FileResponse(WEBAPP_DIR / "index.html")


@app.get("/recipe", include_in_schema=False)
async def webapp_recipe_detail():
    return FileResponse(WEBAPP_DIR / "recipe-detail.html")


app.mount("/webapp", StaticFiles(directory=WEBAPP_DIR), name="webapp")
