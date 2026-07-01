from __future__ import annotations

from fastapi import APIRouter, Depends, status

from blueprintandchill.auth.dependencies import get_current_user, require_role
from blueprintandchill.auth.entra import EntraUser
from blueprintandchill.models.subscription_request import (
    SubscriptionRequestCreate,
    SubscriptionRequestListResponse,
    SubscriptionRequestResponse,
)
from blueprintandchill.services.vending_service import VendingService, get_vending_service

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/requests", response_model=SubscriptionRequestListResponse)
def list_requests(
    _: EntraUser = Depends(require_role("requester")),
    vending_service: VendingService = Depends(get_vending_service),
) -> SubscriptionRequestListResponse:
    return SubscriptionRequestListResponse(items=vending_service.list_requests())


@router.post(
    "/requests",
    response_model=SubscriptionRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_request(
    payload: SubscriptionRequestCreate,
    user: EntraUser = Depends(get_current_user),
    vending_service: VendingService = Depends(get_vending_service),
) -> SubscriptionRequestResponse:
    return vending_service.submit_request(payload=payload, submitted_by=user)
