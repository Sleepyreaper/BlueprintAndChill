from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from blueprintandchill.api.catalog import router as catalog_router
from blueprintandchill.api.health import router as health_router
from blueprintandchill.api.subscriptions import router as subscriptions_router
from blueprintandchill.config import get_settings
from blueprintandchill.web.routes import router as web_router


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.1.0",
        description="BlueprintAndChill subscription shopping demo app.",
    )

    app.include_router(health_router)
    app.include_router(catalog_router, prefix="/api/v1")
    app.include_router(subscriptions_router, prefix="/api/v1")
    app.include_router(web_router)

    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

    return app


app = create_app()
