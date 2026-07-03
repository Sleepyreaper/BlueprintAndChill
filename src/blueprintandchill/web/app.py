"""FastAPI application factory for the BlueprintAndChill demo web app.

This module wires together the app shell: route registration, Jinja2
template configuration, and the Entra ID auth router scaffold. It does
NOT implement shopping pages or orchestration submission -- those are
built in later tasks. This is the reusable framework only.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from blueprintandchill.web.auth import router as auth_router

logger = logging.getLogger("blueprintandchill.web")

WEB_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_ROOT / "templates"
STATIC_DIR = WEB_ROOT / "static"


def get_templates() -> Jinja2Templates:
    """Build the shared Jinja2Templates instance.

    Centralized here so every route module (this one and future
    shopping/orchestration route modules) uses the same template
    environment and search path.
    """
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    return templates


def register_routes(app: FastAPI, templates: Jinja2Templates) -> None:
    """Register base framework routes onto the given app instance."""

    @app.get("/", response_class=HTMLResponse, name="index")
    async def index(request: Request) -> HTMLResponse:
        """Landing page shell.

        Later tasks will replace this body with the actual shopping
        catalog. For now it just proves templating and auth context
        are wired correctly.
        """
        context = {
            "request": request,
            "page_title": "BlueprintAndChill",
            "user": request.session.get("user") if hasattr(request, "session") else None,
        }
        return templates.TemplateResponse("base.html", context)

    @app.get("/healthz", name="healthz")
    async def healthz() -> dict[str, str]:
        """Liveness/readiness probe for App Service / Container Apps health checks."""
        return {"status": "ok"}


def create_app() -> FastAPI:
    """Application factory.

    Returns a fully configured FastAPI instance with:
      - static files mounted (if the static directory exists)
      - Jinja2 templating configured
      - base framework routes registered
      - the Entra ID auth router included

    TODO(auth): SessionMiddleware with a real secret (Key Vault-backed)
    must be added before enabling session-based login state in
    production. Left out here deliberately -- no secrets in this repo.
    """
    app = FastAPI(
        title="BlueprintAndChill",
        description="Azure Landing Zone + subscription-vending demo shopping app.",
        version="0.1.0",
    )

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    else:
        logger.info("Static directory %s does not exist yet; skipping mount.", STATIC_DIR)

    templates = get_templates()
    register_routes(app, templates)
    app.include_router(auth_router)

    return app


# Module-level ASGI app for `uvicorn blueprintandchill.web.app:app` style invocation.
app = create_app()