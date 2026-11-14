from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.postgres import get_pool
from app.services.auth import get_firebase_app


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up so the first sign-in does not pay for DNS, TLS and SDK setup.
    try:
        await asyncio.to_thread(get_pool)
        await asyncio.to_thread(get_firebase_app)
    except Exception as error:
        logging.getLogger(__name__).warning("Startup warm-up failed: %s", type(error).__name__)
    try:
        yield
    finally:
        if get_pool.cache_info().currsize:
            get_pool().close()
        get_pool.cache_clear()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        return {"message": settings.app_name, "docs": "/docs"}

    return app


app = create_app()
