from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class NetworkRequest(BaseModel):
    address_space: str | None = Field(
        default=None,
        description="Optional CIDR to request for the spoke VNet. Placeholder only.",
    )
    connect_to_hub: bool = True
    private_endpoints_required: bool = False


class SubscriptionRequestCreate(BaseModel):
    business_area: Literal["corp", "online", "sandbox"]
    workload_name: str = Field(min_length=3, max_length=50)
    environment: Literal["dev", "test", "prod"]
    region: Literal["eastus", "centralus"]
    owner_email: str
    features: list[str] = Field(default_factory=list)
    network: NetworkRequest = Field(default_factory=NetworkRequest)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("workload_name")
    @classmethod
    def validate_workload_name(cls, value: str) -> str:
        normalized = value.strip().lower().replace(" ", "-")
        if not normalized.replace("-", "").isalnum():
            raise ValueError("workload_name must be alphanumeric words separated by hyphens")
        return normalized


class OrchestrationPreview(BaseModel):
    target_management_group: str
    proposed_subscription_alias: str
    target_hub_region: str
    policy_package: str
    status: Literal["PENDING_IMPLEMENTATION"]
    automation_hook: str


class SubscriptionRequestRecord(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_by: str
    payload: SubscriptionRequestCreate
    orchestration: OrchestrationPreview


class SubscriptionRequestResponse(BaseModel):
    request: SubscriptionRequestRecord


class SubscriptionRequestListResponse(BaseModel):
    items: list[SubscriptionRequestRecord]
