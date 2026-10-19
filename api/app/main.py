import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import pool
from .routes import billing, metrics, vapi, whatsapp

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open(wait=True)
    yield
    pool.close()


app = FastAPI(title="AI Voice Operator", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[get_settings().web_origin], allow_methods=["GET", "POST"], allow_headers=["*"])

for r in (vapi.router, whatsapp.router, metrics.router, billing.router):
    app.include_router(r)


@app.get("/health")
def health():
    return {"ok": True}
