"""Low-level Azure management-plane API clients for subscription vending.

This module builds EXACT REST requests against the Azure Resource
Manager (ARM) control plane for the two calls Landmark's automation
needs:

  1. Subscription alias creation/polling
     PUT/GET providers/Microsoft.Subscription/aliases/{aliasName}
     api-version=2021-10-01
     Docs: https://learn.microsoft.com/rest/api/subscription/alias

  2. Billing role assignment on an MCA invoice section scope
     PUT {invoiceSectionScope}/providers/Microsoft.Billing/billingRoleAssignments/{billingRoleAssignmentName}
     api-version=2024-04-01
     Docs: https://learn.microsoft.com/rest/api/billing/2024-04-01/billing-role-assignments

Design goals (Mr. Scorpio's rules apply):
  - Request construction (URLs, query strings, JSON bodies) is fully,
    deterministically implemented. No placeholders in the shapes that
    get sent over the wire.
  - Auth (token acquisition) and the actual HTTP transport are
    injectable via small Protocols, so every client here is
    trivially mockable in unit tests -- no real network call is
    required to test that a request was built correctly.
  - NOTHING here hardcodes a tenant ID, subscription ID, or secret.
    Every identifier is a parameter supplied by the caller (which, in
    later tasks, comes from config.py / models.py / Key Vault).

TODO(auth-wiring): Replace `NotImplementedTokenProvider` with a real
implementation backed by azure-identity's `DefaultAzureCredential` (or
`ManagedIdentityCredential` in production) once this accelerator is
wired up inside an App Service / Azure Function with a system- or
user-assigned managed identity. That wiring is intentionally out of
scope for this scaffold task.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Awaitable, Callable, Dict, Optional, Protocol

import httpx
from pydantic import BaseModel, Field

from .models import InvoiceSectionIdentifier, WorkloadType

logger = logging.getLogger(__name__)

__all__ = [
    "ARM_API_VERSION_SUBSCRIPTION_ALIAS",
    "ARM_API_VERSION_BILLING_ROLE_ASSIGNMENT",
    "ARM_ENDPOINTS",
    "ManagementApiError",
    "PollingTimeoutError",
    "TokenProvider",
    "NotImplementedTokenProvider",
    "StaticTokenProvider",
    "ManagementApiTransport",
    "SubscriptionAliasRequest",
    "SubscriptionAliasResult",
    "SubscriptionAliasClient",
    "BillingRoleAssignmentRequest",
    "BillingRoleAssignmentResult",
    "BillingRoleAssignmentClient",
]

# ---------------------------------------------------------------------------
# Constants: API versions and ARM endpoints per cloud environment.
# ---------------------------------------------------------------------------

ARM_API_VERSION_SUBSCRIPTION_ALIAS = "2021-10-01"
ARM_API_VERSION_BILLING_ROLE_ASSIGNMENT = "2024-04-01"

# Maps AzureIdentitySettings.environment values (config.py) to ARM base
# URLs. TODO(sovereign-clouds): confirm exact endpoints if Landmark ever
# operates in a sovereign cloud; AzureCloud is the only one exercised
# by this scaffold today.
ARM_ENDPOINTS: Dict[str, str] = {
    "AzureCloud": "https://management.azure.com",
    "AzureUSGovernment": "https://management.usgovcloudapi.net",
    "AzureChinaCloud": "https://management.chinacloudapi.cn",
}

_TERMINAL_PROVISIONING_STATES = {"Succeeded", "Failed", "Canceled"}


class ManagementApiError(RuntimeError):
    """Raised when ARM returns a non-2xx response we can't recover from."""

    def __init__(self, message: str, *, status_code: int, response_body: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class PollingTimeoutError(TimeoutError):
    """Raised when a long-running ARM operation doesn't reach a terminal
    provisioning state within the configured timeout."""


# ---------------------------------------------------------------------------
# Auth abstraction -- fully mockable, real acquisition is a TODO.
# ---------------------------------------------------------------------------


class TokenProvider(Protocol):
    """Anything that can hand back a bearer token for a given ARM scope."""

    async def get_token(self, scope: str) -> str:
        ...


class NotImplementedTokenProvider:
    """Default token provider for the scaffold.

    TODO(auth-wiring): swap this for a real azure-identity-backed
    provider (DefaultAzureCredential / ManagedIdentityCredential)
    before any live call is made. Left as an explicit failure rather
    than a silent stub so nobody accidentally ships a no-op auth path.
    """

    async def get_token(self, scope: str) -> str:
        raise NotImplementedError(
            "TODO(auth-wiring): wire a real TokenProvider (e.g. "
            "azure.identity.aio.DefaultAzureCredential) before making "
            f"live ARM calls. Requested scope: {scope!r}"
        )


class StaticTokenProvider:
    """Test/dev-only token provider that returns a fixed string.

    Never use this in production; it exists purely so unit tests can
    inject a deterministic 'Bearer <token>' without any real auth flow.
    """

    def __init__(self, token: str) -> None:
        self._token = token

    async def get_token(self, scope: str) -> str:
        return self._token


# ---------------------------------------------------------------------------
# Transport abstraction -- wraps httpx, easy to mock/replace in tests.
# ---------------------------------------------------------------------------


class ManagementApiTransport:
    """Thin wrapper around an httpx.AsyncClient plus a TokenProvider.

    Kept deliberately small: build the Authorization header, send the
    request, and return the raw httpx.Response. All URL/body building
    lives in the client classes below so it can be unit tested without
    ever constructing a transport.
    """

    def __init__(
        self,
        token_provider: TokenProvider,
        *,
        http_client: Optional[httpx.AsyncClient] = None,
        arm_resource_scope: str = "https://management.azure.com/.default",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._token_provider = token_provider
        self._arm_resource_scope = arm_resource_scope
        # Caller may inject their own httpx.AsyncClient (e.g. a
        # httpx.MockTransport-backed client) for fully offline tests.
        self._http_client = http_client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_http_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self._http_client.aclose()

    async def _authorized_headers(self) -> Dict[str, str]:
        # TODO(auth-wiring): once NotImplementedTokenProvider is
        # replaced, this will produce a real bearer token per call.
        token = await self._token_provider.get_token(self._arm_resource_scope)
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def put(self, url: str, *, json_body: Dict[str, Any]) -> httpx.Response:
        headers = await self._authorized_headers()
        logger.debug("PUT %s", url)
        response = await self._http_client.put(url, headers=headers, json=json_body)
        _raise_for_status(response)
        return response

    async def get(self, url: str) -> httpx.Response:
        headers = await self._authorized_headers()
        logger.debug("GET %s", url)
        response = await self._http_client.get(url, headers=headers)
        _raise_for_status(response)
        return response


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code >= 400:
        raise ManagementApiError(
            f"ARM request failed with status {response.status_code} for "
            f"{response.request.method} {response.request.url}",
            status_code=response.status_code,
            response_body=response.text,
        )


def _arm_base_url(environment: str = "AzureCloud") -> str:
    try:
        return ARM_ENDPOINTS[environment]
    except KeyError as exc:
        raise ValueError(
            f"Unknown Azure cloud environment {environment!r}; known values: "
            f"{sorted(ARM_ENDPOINTS)}"
        ) from exc


# ---------------------------------------------------------------------------
# Subscription alias: request/response models + client.
# ---------------------------------------------------------------------------


class SubscriptionAliasRequest(BaseModel):
    """Body for PUT providers/Microsoft.Subscription/aliases/{aliasName}.

    Mirrors the `PutAliasRequestProperties` shape from the 2021-10-01
    Subscription alias API. No field here defaults to a real tenant,
    subscription, or management group -- every identifier must be
    supplied explicitly by the caller.
    """