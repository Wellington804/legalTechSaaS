from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.observability import init_sentry
from app.core.redis_cache import cache_manager


init_sentry()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Schema changes are an explicit deploy gate: `alembic upgrade head`.
    await cache_manager.connect()
    yield
    await cache_manager.disconnect()
    await engine.dispose()


docs_enabled = not settings.is_hardened_environment
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    lifespan=lifespan,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if docs_enabled else None,
    docs_url=f"{settings.API_V1_STR}/docs" if docs_enabled else None,
    redoc_url=None,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
async def readyz(response: Response) -> dict[str, str]:
    ready = True
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        ready = False

    try:
        if cache_manager.redis_client is None:
            ready = False
        else:
            await cache_manager.redis_client.ping()
    except Exception:
        ready = False

    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready"}
    return {"status": "ready"}


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"status": "online", "service": settings.PROJECT_NAME, "version": "1.0.0"}
