"""Reusable Azure Resource Manager HTTP client wrapper.

This module provides a small, testable wrapper around calling Azure
management-plane REST APIs (ARM, Billing RP, Subscription RP, etc.).

Design goals:
    - No hardcoded secrets. Credentials come from azure-identity and
      are resolved lazily via env-driven configuration (see
      ``blueprintandchill.config``).
    - Callers supply the resource path and api-version; this wrapper
      only owns transport concerns: auth header injection, timeout,
      retry boundaries, and structured response parsing.
    - Not tied to any specific vending action (subscription alias,
      billing role assignment, etc.) - those live in higher-level
      modules that use this client.

TODO(gil): Wire in the real azure-identity credential chain once the
service principal / managed identity strategy for the vending
automation function is finalized (see spec section on SP creation).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

try:
    # azure-identity is an expected dependency of this package; import
    # is guarded so this module still parses / is testable in
    # environments where the dependency has not been installed yet
    # (e.g. a bare docs/lint pass).
    from azure.core.credentials import AccessToken, TokenCredential
    from azure.identity import DefaultAzureCredential
except ImportError:  # pragma: no cover - exercised only when SDK missing
    AccessToken = Any  # type: ignore[assignment,misc]
    TokenCredential = Any  # type: ignore[assignment,misc]
    DefaultAzureCredential = None  # type: ignore[assignment,misc]


DEFAULT_ARM_BASE_URL = "https://management.azure.com"
DEFAULT_ARM_SCOPE = "https://management.azure.com/.default"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 1.5
RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})


class AzureManagementError(Exception):
    """Raised when an Azure management-plane call fails after retries."""

    def __init__(self, message: str, status_code: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


@dataclass(frozen=True)
class AzureManagementResponse:
    """Structured, normalized response from an ARM-style call."""

    status_code: int
    headers: dict[str, str]
    json_body: dict[str, Any] | None
    text_body: str

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def azure_async_operation_url(self) -> str | None:
        """Header ARM uses to point at a long-running-operation status."""
        return self.headers.get("azure-asyncoperation") or self.headers.get(
            "Azure-AsyncOperation"
        )

    @property
    def location_url(self) -> str | None:
        """Alternate LRO polling header some RPs use instead of AAO."""
        return self.headers.get("location") or self.headers.get("Location")

    @property
    def retry_after_seconds(self) -> float | None:
        raw = self.headers.get("retry-after") or self.headers.get("Retry-After")
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            return None


@dataclass
class AzureManagementClientConfig:
    """Configuration for :class:`AzureManagementClient`.

    All values are safe to construct from environment-driven settings;
    nothing here is a secret. The credential itself is resolved via
    azure-identity, never via a literal key/secret in this config.
    """

    base_url: str = DEFAULT_ARM_BASE_URL
    scope: str = DEFAULT_ARM_SCOPE
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS
    default_api_version: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)


class AzureManagementClient:
    """Thin, testable wrapper for calling Azure management-plane APIs.

    Owns transport concerns only: auth token acquisition, timeout,
    retry boundaries on transient failures, and structured response
    parsing. It intentionally knows nothing about subscription
    vending, billing roles, or invoice sections - those are built on
    top of this client.

    Usage (indented, not fenced, to avoid nested code blocks):

        config = AzureManagementClientConfig(default_api_version="2021-10-01")
        client = AzureManagementClient(config=config)
        response = client.put(
            path="/providers/Microsoft.Billing/...",
            json_body={"properties": {...}},
        )
        if response.is_success:
            ...
    """

    def __init__(
        self,
        config: AzureManagementClientConfig | None = None,
        credential: "TokenCredential | None" = None,
        transport: httpx.Client | None = None,
    ) -> None:
        self._config = config or AzureManagementClientConfig()
        self._credential = credential or self._build_default_credential()
        self._owns_transport = transport is None
        self._transport = transport or httpx.Client(
            base_url=self._config.base_url,
            timeout=self._config.timeout_seconds,
        )

    def _build_default_credential(self) -> "TokenCredential | None":
        """Resolve the default azure-identity credential chain.

        TODO(gil): Replace DefaultAzureCredential with an explicit
        chain (workload identity in AKS/Container Apps, then managed
        identity, then env-based service principal) once the vending
        automation's hosting model is locked in. For now this defers
        entirely to azure-identity's environment-driven resolution -
        no secrets are read or stored in this module.
        """
        if DefaultAzureCredential is None:  # pragma: no cover - SDK not installed
            return None
        return DefaultAzureCredential()

    def close(self) -> None:
        if self._owns_transport:
            self._transport.close()

    def __enter__(self) -> "AzureManagementClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _get_bearer_token(self) -> str:
        if self._credential is None:
            # TODO(gil): This branch only fires when azure-identity is
            # unavailable (e.g. local lint/test env). Real deployments
            # must always have a resolvable credential.
            raise AzureManagementError(
                "No Azure credential available; azure-identity is not installed "
                "or DefaultAzureCredential failed to initialize."
            )
        token: AccessToken = self._credential.get_token(self._config.scope)
        return token.token

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._get_bearer_token()}",
            "Content-Type": "application/json",
        }
        headers.update(self._config.extra_headers)
        return headers

    def _build_url(self, path: str, api_version: str | None) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        version = api_version or self._config.default_api_version
        if version is None:
            return normalized_path
        separator = "&" if "?" in normalized_path else "?"
        return f"{normalized_path}{separator}api-version={version}"

    def _parse_response(self, response: httpx.Response) -> AzureManagementResponse:
        json_body: dict[str, Any] | None
        try:
            parsed = response.json()
            json_body = parsed if isinstance(parsed, dict) else {"value": parsed}
        except ValueError:
            json_body = None
        return AzureManagementResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            json_body=json_body,
            text_body=response.text,
        )

    def _request_with_retries(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any] | None,
    ) -> AzureManagementResponse:
        last_error: Exception | None = None
        for attempt in range(1, self._config.max_retries + 1):
            try:
                raw_response = self._transport.request(
                    method,
                    url,
                    headers=headers,
                    json=json_body,
                )
            except httpx.TransportError as exc:
                last_error = exc
                if attempt < self._config.max_retries:
                    time.sleep(self._config.retry_backoff_seconds * attempt)
                    continue
                raise AzureManagementError(
                    f"Transport error calling {method} {url} after "
                    f"{attempt} attempt(s): {exc}"
                ) from exc

            if raw_response.status_code in RETRYABLE_STATUS_CODES and attempt < self._config.max_retries:
                time.sleep(self._config.retry_backoff_seconds * attempt)
                continue

            return self._parse_response(raw_response)

        # Defensive: loop always returns or raises above.
        raise AzureManagementError(
            f"Exhausted retries calling {method} {url}: {last_error}"
        )

    def get(
        self,
        path: str,
        api_version: str | None = None,
        query_params: dict[str, str] | None = None,
    ) -> AzureManagementResponse:
        """Perform an authenticated GET against the management plane."""
        url = self._build_url(path, api_version)
        if query_params:
            separator = "&" if "?" in url else "?"
            query_string = "&".join(f"{key}={value}" for key, value in query_params.items())
            url = f"{url}{separator}{query_string}"
        headers = self._build_headers()
        return self._request_with_retries("GET", url, headers, json_body=None)

    def put(
        self,
        path: str,
        json_body: dict[str, Any],
        api_version: str | None = None,
    ) -> AzureManagementResponse:
        """Perform an authenticated PUT against the management plane."""
        url = self._build_url(path, api_version)
        headers = self._build_headers()
        return self._request_with_retries("PUT", url, headers, json_body=json_body)

    def get_absolute(self, absolute_url: str) -> AzureManagementResponse:
        """GET a fully-qualified URL, such as an Azure-AsyncOperation header value.

        Used by the polling helper in ``blueprintandchill.azure.polling``
        which receives full LRO status URLs, not relative paths.
        """
        headers = self._build_headers()
        return self._request_with_retries("GET", absolute_url, headers, json_body=None)