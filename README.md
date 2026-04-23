# Recipe Parser Bot

Production-oriented Telegram recipe bot with parser, mini app and Supabase/local storage fallback.

## Architecture

```
app/
  bot/         # Telegram bot orchestration and handlers
  parser/      # HTML parsing and LLM normalization
  backend/     # Repository layer (Supabase + local fallback)
  shared/      # Config, constants, utils, logging
api.py         # FastAPI for Mini App endpoints
run.py         # Bot entrypoint
webapp/        # Legacy static mini app frontend
frontend/      # New frontend root (migration target)
```

## Run locally

1. Create `.env` from `.env.example`
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Start bot:
   - `python run.py`
4. Start API:
   - `uvicorn api:app --reload`

## Docker

1. Create `.env` from `.env.example`
2. Build and run:
   - `docker compose up --build`
3. API will be available at:
   - `http://localhost:8000`
