from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from blueprintandchill.auth.dependencies import get_auth_service, get_current_user
from blueprintandchill.auth.entra import EntraAuthService, EntraUser
from blueprintandchill.config import get_settings
from blueprintandchill.services.catalog_service import CatalogService, get_catalog_service

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.template_dir))
router = APIRouter(tags=["web"])


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    auth_service: EntraAuthService = Depends(get_auth_service),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "app_name": settings.app_name,
            "login_url": auth_service.get_login_url(),
            "entra_configured": auth_service.configured,
        },
    )


@router.get("/shop", response_class=HTMLResponse)
def subscription_shop(
    request: Request,
    user: EntraUser = Depends(get_current_user),
    catalog_service: CatalogService = Depends(get_catalog_service),
) -> HTMLResponse:
    catalog = catalog_service.get_subscription_catalog()
    return templates.TemplateResponse(
        request,
        "subscription_shop.html",
        {"app_name": settings.app_name, "user": user, "catalog": catalog},
    )
