from __future__ import annotations

from fastapi import APIRouter, Depends

from blueprintandchill.models.catalog import SubscriptionCatalogResponse
from blueprintandchill.services.catalog_service import CatalogService, get_catalog_service

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/subscription-options", response_model=SubscriptionCatalogResponse)
def list_subscription_options(
    catalog_service: CatalogService = Depends(get_catalog_service),
) -> SubscriptionCatalogResponse:
    return catalog_service.get_subscription_catalog()
