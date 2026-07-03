"""Generic poll-until helper for Azure long-running operations (LROs).

Azure RPs (Billing, Subscription, etc.) commonly return 202 Accepted
with an Azure-AsyncOperation or Location header pointing at a status
resource. This module provides a transport-agnostic polling loop on
top of :class:`blueprintandchill.azure.http_client.AzureManagementClient`
that callers (e.g. subscription alias creation) can reuse without
duplicating backoff/timeout logic.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from blueprintandchill.azure.http_client import (
    AzureManagementClient,
    AzureManagementError,
    AzureManagementResponse,
)

DEFAULT_POLL_INTERVAL_SECONDS = 5.0
DEFAULT_POLL_TIMEOUT_SECONDS = 600.0
DEFAULT_MAX_POLL_INTERVAL_SECONDS = 30.0

TERMINAL_SUCCESS_STATES = frozenset({"Succeeded"})
TERMINAL_FAILURE_STATES = frozenset({"Failed", "Canceled"})


class PollingTimeoutError(Exception):
    """Raised when a long-running operation does not reach a terminal state in time."""

    def __init__(self, message: str, last_response: AzureManagementResponse | None = None) -> None:
        super().__init__(message)
        self.last_response = last_response


class PollingFailedError(Exception):
    """Raised when the long-running operation reaches a terminal failure state."""

    def __init__(self, message: str, response: AzureManagementResponse) -> None:
        super().__init__(message)
        self.response = response


@dataclass(frozen=True)
class PollingResult:
    """Final outcome of a poll-until loop."""

    response: AzureManagementResponse
    provisioning_state: str
    attempts: int
    elapsed_seconds: float


def _default_extract_state(response: AzureManagementResponse) -> str:
    """Best-effort extraction of provisioningState/status from an LRO body.

    Different RPs nest this differently:
        - top-level "status"
        - top-level "properties.provisioningState"
    This helper checks both common shapes; callers needing bespoke
    parsing should pass their own ``extract_state`` function to
    :func:`poll_until`.
    """
    body = response.json_body or {}
    status = body.get("status")
    if isinstance(status, str):
        return status
    properties = body.get("properties")
    if isinstance(properties, dict):
        provisioning_state = properties.get("provisioningState")
        if isinstance(provisioning_state, str):
            return provisioning_state
    return "Unknown"


def poll_until(
    client: AzureManagementClient,
    operation_url: str,
    extract_state: Callable[[AzureManagementResponse], str] | None = None,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    max_poll_interval_seconds: float = DEFAULT_MAX_POLL_INTERVAL_SECONDS,
    timeout_seconds: float = DEFAULT_POLL_TIMEOUT_SECONDS,
    clock: Callable[[], float] | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> PollingResult:
    """Poll an Azure LRO status URL until it reaches a terminal state.

    Generic across any vending action that returns an Azure-AsyncOperation
    or Location URL (subscription alias creation, billing role
    assignment propagation, etc.). This function owns only the polling
    semantics; it does not know what resource is being provisioned.

    Args:
        client: An already-authenticated AzureManagementClient.
        operation_url: Fully-qualified status URL (from the
            Azure-AsyncOperation or Location response header).
        extract_state: Optional function to pull the provisioning
            state string out of a response; defaults to checking the
            common "status" / "properties.provisioningState" shapes.
        poll_interval_seconds: Initial delay between polls.
        max_poll_interval_seconds: Cap for exponential backoff between polls.
        timeout_seconds: Overall wall-clock budget before giving up.
        clock: Injectable time source for tests (defaults to time.monotonic).
        sleep_fn: Injectable sleep function for tests (defaults to time.sleep).

    Returns:
        PollingResult once a terminal success state is observed.

    Raises:
        PollingFailedError: if the operation reaches a terminal failure state.
        PollingTimeoutError: if the timeout budget is exhausted first.
    """
    state_extractor = extract_state or _default_extract_state
    now = clock or time.monotonic
    sleep = sleep_fn or time.sleep

    start_time = now()
    attempt = 0
    current_interval = poll_interval_seconds
    last_response: AzureManagementResponse | None = None

    while True:
        attempt += 1
        try:
            response = client.get_absolute(operation_url)
        except AzureManagementError as exc:
            raise PollingTimeoutError(
                f"Polling request failed on attempt {attempt}: {exc}",
                last_response=last_response,
            ) from exc

        last_response = response
        provisioning_state = state_extractor(response)
        elapsed_seconds = now() - start_time

        if provisioning_state in TERMINAL_SUCCESS_STATES:
            return PollingResult(
                response=response,
                provisioning_state=provisioning_state,
                attempts=attempt,
                elapsed_seconds=elapsed_seconds,
            )

        if provisioning_state in TERMINAL_FAILURE_STATES:
            raise PollingFailedError(
                f"Operation reached terminal failure state '{provisioning_state}' "
                f"after {attempt} attempt(s)",
                response=response,
            )

        if elapsed_seconds >= timeout_seconds:
            raise PollingTimeoutError(
                f"Polling timed out after {elapsed_seconds:.1f}s / {attempt} attempt(s); "
                f"last observed state: '{provisioning_state}'",
                last_response=response,
            )

        retry_after = response.retry_after_seconds
        sleep_seconds = retry_after if retry_after is not None else current_interval
        sleep(sleep_seconds)
        current_interval = min(current_interval * 1.5, max_poll_interval_seconds)


def build_operation_url_from_response(response: AzureManagementResponse) -> str | None:
    """Extract the LRO polling URL from an initial 202-style response.

    Prefers Azure-AsyncOperation per ARM convention, falls back to
    Location. Returns None if neither header is present (e.g. the
    initial call already returned a terminal state synchronously).
    """
    return response.azure_async_operation_url or response.location_url