"""FastAPI application factory for the BlueprintAndChill demo web app.

This is the "shop for what gets deployed" front door: a Python FastAPI
app, intended to run on Azure App Service (Linux, Python) protected by
Entra ID login. This module wires settings + the auth router together
behind an application factory pattern (create_app()) so tests, local
dev, and the real ASGI server entrypoint can all build the same app
consistently.

No live Azure calls happen at import time or at create_app() time.
Everything Azure-specific (OIDC discovery, token exchange, calls into
the subscription-vending workflow) is either stubbed with TODOs in
auth.py, or will be added in later tasks as separate routers that get
included here without changing this factory's shape.
"""

from __future__ import annotations

from typing import Dict

from fastapi import FastAPI
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from blueprintandchill.auth import EntraIdSettings, build_auth_router


class WebAppSettings(BaseSettings):
    """Top-level web app settings, independent of vending config.

    Kept separate from blueprintandchill.config.AzureIdentitySettings
    on purpose: this settings model only concerns the demo web app
    (title, debug flag, CORS-ish basics later), not the Azure Landing
    Zone / subscription-vending domain.
    """

    model_config = SettingsConfigDict(
        env_prefix="BAC_WEBAPP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    title: str = Field(
        default="BlueprintAndChill",
        description="Display title for the demo web app.",
    )
    debug: bool = Field(
        default=False,
        description="Enable FastAPI debug mode. Should be False in production.",
    )


def create_app(
    webapp_settings: WebAppSettings | None = None,
    entra_settings: EntraIdSettings | None = None,
) -> FastAPI:
    """Build and return a configured FastAPI application instance.

    This is the single application factory used by:
      - local dev (uvicorn blueprintandchill.webapp:create_app --factory)
      - Azure App Service (via a startup command invoking the factory)
      - tests (import create_app, build a TestClient against it)

    Args:
        webapp_settings: optional pre-built WebAppSettings, mainly for
            tests; defaults to environment-driven settings.
        entra_settings: optional pre-built EntraIdSettings, mainly for
            tests; defaults to environment-driven settings.

    Returns:
        A fully wired FastAPI app with health and auth routers
        included. No live Azure/network calls are performed here.
    """
    settings = webapp_settings or WebAppSettings()
    auth_settings = entra_settings or EntraIdSettings()

    app = FastAPI(
        title=settings.title,
        debug=settings.debug,
        description=(
            "Landmark's demo shop-and-deploy front end for the "
            "BlueprintAndChill Azure Landing Zone accelerator."
        ),
    )

    @app.get("/healthz", tags=["ops"])
    async def healthz() -> Dict[str, str]:
        """Liveness endpoint. Performs no Azure calls, no auth check."""
        return {"status": "ok", "app": settings.title}

    @app.get("/readyz", tags=["ops"])
    async def readyz() -> Dict[str, object]:
        """Readiness endpoint reporting whether Entra ID is configured.

        Does not attempt any live OIDC discovery or token calls; it
        only reports whether the minimum settings are present, so
        operators can see configuration status without secrets ever
        appearing in the response.
        """
        entra_configured = bool(auth_settings.tenant_id and auth_settings.client_id)
        return {
            "status": "ok",
            "entra_configured": entra_configured,
        }

    app.include_router(build_auth_router(auth_settings))

    return app