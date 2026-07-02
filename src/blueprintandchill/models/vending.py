from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Workload(StrEnum):
    PRODUCTION = "Production"
    DEVELOPMENT = "DevTest"


class ProvisioningState(StrEnum):
    ACCEPTED = "Accepted"
    IN_PROGRESS = "InProgress"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    CANCELED = "Canceled"


class ServicePrincipalMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    app_id: str = Field(..., min_length=1)
    object_id: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    tenant_id: str | None = None
    client_secret_name: str | None = None


class BillingRoleAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    principal_object_id: str = Field(..., min_length=1)
    billing_scope: str = Field(..., min_length=1)
    role_definition_id: str | None = None
    role_name: str | None = None
    principal_type: str = "ServicePrincipal"
    idempotency_key: str | None = None


class BillingRoleAssignmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    principal_object_id: str = Field(..., min_length=1)
    billing_scope: str = Field(..., min_length=1)
    assignment_id: str | None = None
    role_definition_id: str | None = None
    role_name: str | None = None
    created: bool = True
    status: str = "Succeeded"
    message: str | None = None


class SubscriptionAliasRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    alias_name: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    billing_scope: str = Field(..., min_length=1)
    workload: Workload
    owner_object_id: str = Field(..., min_length=1)
    management_group_id: str | None = None
    subscription_idempotency_key: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class SubscriptionAliasResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    alias_name: str = Field(..., min_length=1)
    billing_scope: str = Field(..., min_length=1)
    subscription_id: str | None = None
    provisioning_state: ProvisioningState
    accepted: bool = True
    idempotency_key: str | None = None
    operation_id: str | None = None
    message: str | None = None


class ProvisioningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    display_name: str = Field(..., min_length=1)
    alias_name: str = Field(..., min_length=1)
    billing_scope: str = Field(..., min_length=1)
    workload: Workload
    owner_object_id: str = Field(..., min_length=1)
    management_group_id: str | None = None
    subscription_idempotency_key: str | None = None
    billing_role_definition_id: str | None = None
    billing_role_name: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProvisioningResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    alias_name: str = Field(..., min_length=1)
    billing_scope: str = Field(..., min_length=1)
    workload: Workload
    provisioning_state: ProvisioningState
    service_principal: ServicePrincipalMetadata | None = None
    billing_role_assignment: BillingRoleAssignmentResult | None = None
    alias_result: SubscriptionAliasResult | None = None
    subscription_id: str | None = None
    idempotency_key: str | None = None
    message: str | None = None


__all__ = [
    "BillingRoleAssignmentRequest",
    "BillingRoleAssignmentResult",
    "ProvisioningRequest",
    "ProvisioningResult",
    "ProvisioningState",
    "ServicePrincipalMetadata",
    "SubscriptionAliasRequest",
    "SubscriptionAliasResult",
    "Workload",
]