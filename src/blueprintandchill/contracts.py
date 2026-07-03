from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class SubscriptionRequest:
    display_name: str
    billing_scope: str
    workload: str
    owner_object_id: str


@dataclass
class VendingResult:
    subscription_id: str
    alias: str
    status: str
    service_principal_app_id: str


class VendorBackend(Protocol):
    def create_service_principal(self, request: SubscriptionRequest) -> str:
        ...

    def assign_billing_role(self, sp_object_id: str, billing_scope: str) -> None:
        ...

    def create_subscription_alias(
        self, request: SubscriptionRequest
    ) -> VendingResult:
        ...