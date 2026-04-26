"""Local entry point: keep so `uvicorn index:app` works for local dev.
Vercel deploys use api/index.py instead (see vercel.json rewrites)."""
from api.main import app  # noqa: F401
