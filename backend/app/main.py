from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.middleware import TenantMiddleware
from app.core.database import engine, Base
import app.models
from app.api.v1.router import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Multi-Tenancy Middleware
app.add_middleware(TenantMiddleware)

# Include API Routers
app.include_router(api_router, prefix=settings.API_V1_STR)

from app.core.redis_cache import cache_manager
from app.core.db_optimizations import apply_db_optimizations

@app.on_event("startup")
async def startup_event():
    # Initialize DB Tables asynchronously
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Apply Database Indexes & Optimizations
    await apply_db_optimizations(engine)
    # Initialize Redis L2 Cache Connection
    await cache_manager.connect()

@app.on_event("shutdown")
async def shutdown_event():
    await cache_manager.disconnect()

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "docs": f"{settings.API_V1_STR}/docs"
    }
