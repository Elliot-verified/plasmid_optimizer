"""Vercel entry point. Sets sys.path so api.main and plasmid_optimizer resolve
without relying on the editable wheel (which can break in the function runtime)."""

import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from api.main import app  # noqa: F401
except Exception as e:
    err = f"{type(e).__name__}: {e}\n{traceback.format_exc()}\nsys.path={sys.path}"
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse

    app = FastAPI()

    @app.get("/{full_path:path}")
    @app.post("/{full_path:path}")
    async def _diag(full_path: str):
        return PlainTextResponse(err, status_code=500)
