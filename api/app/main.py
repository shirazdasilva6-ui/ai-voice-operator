import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings, production_problems
from .db import conn, pool
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
    """Liveness: the process is up. Says nothing about dependencies."""
    return {"ok": True}


@app.get("/ready")
def ready():
    """Readiness: the database answers. Point uptime monitors and load balancers here, not at /health."""
    try:
        with conn() as c:
            c.execute("select 1")
    except Exception:
        logging.getLogger(__name__).exception("readiness check: database unreachable")
        return JSONResponse({"ok": False, "database": "unreachable"}, status_code=503)
    return {"ok": True, "database": "ok"}
