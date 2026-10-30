import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings, production_problems
from .db import pool
from .routes import billing, metrics, vapi, whatsapp

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if problems := production_problems(settings):
        # Fail closed: refusing to start beats serving unauthenticated webhooks.
        raise RuntimeError("Unsafe production config: " + "; ".join(problems))
    pool.open(wait=True)
    yield
    pool.close()


docs = {} if not settings.is_production else {"docs_url": None, "redoc_url": None, "openapi_url": None}
app = FastAPI(title="AI Voice Operator", lifespan=lifespan, **docs)
app.add_middleware(CORSMiddleware, allow_origins=[get_settings().web_origin], allow_methods=["GET", "POST"], allow_headers=["*"])

for r in (vapi.router, whatsapp.router, metrics.router, billing.router):
    app.include_router(r)


@app.get("/health")
def health():
    return {"ok": True}
