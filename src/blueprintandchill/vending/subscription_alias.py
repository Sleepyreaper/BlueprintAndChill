from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AliasProvisioningError(RuntimeError):
 """Raised when Azure subscription alias provisioning fails."""


class AliasTimeoutError(TimeoutError):
 """Raised when Azure subscription alias polling times out."""


@dataclass(frozen=True)
class SubscriptionAliasRequest:
 alias_name: str
 display_name: str
 workload: str
 billing_scope: str


@dataclass(frozen=True)
class SubscriptionAliasResult:
 alias_name: str
 subscription_id: str | None
 provisioning_state: str
 raw_response: dict


class HttpClient(Protocol):
 def put(self, url: str, json: dict, headers: dict | None = None) -> dict:...
 def get(self, url: str, headers: dict | None = None) -> dict:...


class SubscriptionAliasService:
 """Wrapper for the Microsoft.Subscription alias API.

 Phase 1 note:
 This scaffold defines the exact API contract and idempotency semantics.
 Live Azure authentication/wiring may still be TODO depending on tenant setup.
 """

 API_VERSION = "2021-10-01"

 def __init__(self, http_client: HttpClient, arm_api_base: str) -> None:
 self._http = http_client
 self._arm_api_base = arm_api_base.rstrip("/")

 def create_or_get(self, request: SubscriptionAliasRequest) -> dict:
 if request.workload not in {"Production", "DevTest"}:
 raise ValueError("workload must be 'Production' or 'DevTest'")
 if not request.alias_name:
 raise ValueError("alias_name is required")
 if not request.billing_scope.startswith("/providers/Microsoft.Billing/"):
 raise ValueError("billing_scope must be an MCA invoice section scope")

 url = (
 f"{self._arm_api_base}/providers/Microsoft.Subscription/aliases/"
 f"{request.alias_name}?api-version={self.API_VERSION}"
 )
 body = {
 "properties": {
 "displayName": request.display_name,
 "workload": request.workload,
 "billingScope": request.billing_scope,
 }
 }
 return self._http.put(url, json=body)

 def get(self, alias_name: str) -> dict:
 if not alias_name:
 raise ValueError("alias_name is required")

 url = (
 f"{self._arm_api_base}/providers/Microsoft.Subscription/aliases/"
 f"{alias_name}?api-version={self.API_VERSION}"
 )
 return self._http.get(url)