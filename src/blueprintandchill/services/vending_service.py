from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from blueprintandchill.auth.entra import EntraUser
from blueprintandchill.config import Settings, get_settings
from blueprintandchill.models.subscription_request import (
    OrchestrationPreview,
    SubscriptionRequestCreate,
    SubscriptionRequestRecord,
    SubscriptionRequestResponse,
)
from blueprintandchill.services.request_store import RequestStore


class VendingService:
    def __init__(self, request_store: RequestStore) -> None:
        self._request_store = request_store

    def list_requests(self) -> list[SubscriptionRequestRecord]:
        return self._request_store.list()

    def submit_request(
        self,
        payload: SubscriptionRequestCreate,
        submitted_by: EntraUser,
    ) -> SubscriptionRequestResponse:
        orchestration = self._build_orchestration_preview(payload)
        record = SubscriptionRequestRecord(
            submitted_by=submitted_by.email or submitted_by.subject,
            payload=payload,
            orchestration=orchestration,
        )
        self._request_store.save(record)
        return SubscriptionRequestResponse(request=record)

    def _build_orchestration_preview(
        self,
        payload: SubscriptionRequestCreate,
    ) -> OrchestrationPreview:
        subscription_alias = (
            f"lmk-{payload.business_area}-{payload.workload_name}-{payload.environment}-{payload.region}"
        )
        management_group = f"Landmark/LandingZones/{payload.business_area.title()}/Region-{payload.region.title()}"
        return OrchestrationPreview(
            target_management_group=management_group,
            proposed_subscription_alias=subscription_alias,
            target_hub_region=payload.region,
            policy_package="landing-zone-baseline",
            status="PENDING_IMPLEMENTATION",
            automation_hook="TODO: invoke Terraform/Bicep/ARM vending workflow after approval.",
        )


@lru_cache(maxsize=1)
def get_request_store(settings: Settings = Depends(get_settings)) -> RequestStore:
    return RequestStore(settings.request_data_dir)


@lru_cache(maxsize=1)
def get_vending_service(
    request_store: RequestStore = Depends(get_request_store),
) -> VendingService:
    return VendingService(request_store)
