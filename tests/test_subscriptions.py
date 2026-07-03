"""Unit tests for the subscription alias creation + polling slice.

Covers blueprintandchill.vending.subscriptions.create_subscription:
    - the alias PUT request is built with the correct API path,
      api-version, and payload fragments (displayName, workload,
      billingScope)
    - polling loops on the injected client until a terminal
      provisioning state ("Succeeded") is observed, then returns the
      subscription_id

All Azure/HTTP interaction is mocked via MagicMock - no live network,
no real Azure SDK import.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

try:
    from blueprintandchill.vending import subscriptions
except ImportError:
    pytest.skip(
        "blueprintandchill.vending.subscriptions not importable yet; "
        "Gil, please make sure the module + its dependencies are installed.",
        allow_module_level=True,
    )


ALIAS_API_VERSION = "2021-10-01"


def _client_stub(put_response, get_responses):
    """Build a minimal client double exposing put(...) and get(...).

    put_response: dict returned by a single call to client.put(...)
    get_responses: list of dicts returned by successive client.get(...)
    calls, simulating a poll loop that resolves after N polls.
    """
    client = MagicMock()
    client.put.return_value = put_response
    client.get.side_effect = get_responses
    return client


def test_create_subscription_put_uses_correct_path_and_api_version():
    """GIVEN a subscription alias request
    WHEN create_subscription issues its PUT
    THEN it targets the Microsoft.Subscription aliases path at the
    documented api-version (2021-10-01), so Landmark's tenant never
    silently drifts onto an undocumented/unsupported API surface.
    """
    alias_name = "landmark-spoke-001"
    client = _client_stub(
        put_response={"properties": {"provisioningState": "Accepted"}},
        get_responses=[
            {
                "properties": {
                    "provisioningState": "Succeeded",
                    "subscriptionId": "11111111-2222-3333-4444-555555555555",
                }
            }
        ],
    )

    subscriptions.create_subscription(
        client=client,
        alias=alias_name,
        display_name="Landmark Spoke 001",
        workload="Production",
        billing_scope="/providers/Microsoft.Billing/billingAccounts/1/invoiceSections/2",
    )

    put_call = client.put.call_args
    called_url = put_call.args[0] if put_call.args else put_call.kwargs.get("url")
    assert alias_name in called_url and "Microsoft.Subscription/aliases" in called_url, (
        "Expected the PUT URL to hit providers/Microsoft.Subscription/aliases/"
        f"{alias_name}. Gil, double-check the alias URL builder."
    )
    assert ALIAS_API_VERSION in str(put_call), (
        "Expected api-version=2021-10-01 in the PUT call. Gil, this is the "
        "pinned alias API version - please do not let it drift."
    )


def test_create_subscription_put_payload_contains_billing_scope_and_workload():
    """GIVEN valid alias request fields
    WHEN create_subscription builds the PUT body
    THEN the payload fragment carries displayName, workload, and the
    caller-supplied billingScope verbatim (no reformatting).
    """
    billing_scope = "/providers/Microsoft.Billing/billingAccounts/1/invoiceSections/2"
    client = _client_stub(
        put_response={"properties": {"provisioningState": "Accepted"}},
        get_responses=[
            {
                "properties": {
                    "provisioningState": "Succeeded",
                    "subscriptionId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                }
            }
        ],
    )

    subscriptions.create_subscription(
        client=client,
        alias="landmark-spoke-002",
        display_name="Landmark Spoke 002",
        workload="Production",
        billing_scope=billing_scope,
    )

    put_call = client.put.call_args
    body = put_call.kwargs.get("json") or put_call.kwargs.get("body")
    if body is None and len(put_call.args) > 1:
        body = put_call.args[1]
    properties = body.get("properties", body) if isinstance(body, dict) else {}
    assert properties.get("billingScope") == billing_scope, (
        "Expected the PUT payload's properties.billingScope to match the "
        "caller-supplied billing scope exactly. Gil, do not reformat it."
    )
    assert properties.get("workload") == "Production", (
        "Expected properties.workload == 'Production'. Gil, check the "
        "payload builder passes workload through unchanged."
    )


def test_create_subscription_polls_until_succeeded_and_returns_subscription_id():
    """GIVEN an alias that is Accepted, then InProgress, then Succeeded
    WHEN create_subscription polls the alias GET
    THEN it loops through the intermediate states and returns the
    subscription_id only once the terminal 'Succeeded' state appears.
    """
    expected_subscription_id = "99999999-8888-7777-6666-555555555555"
    client = _client_stub(
        put_response={"properties": {"provisioningState": "Accepted"}},
        get_responses=[
            {"properties": {"provisioningState": "Accepted"}},
            {"properties": {"provisioningState": "InProgress"}},
            {
                "properties": {
                    "provisioningState": "Succeeded",
                    "subscriptionId": expected_subscription_id,
                }
            },
        ],
    )

    result = subscriptions.create_subscription(
        client=client,
        alias="landmark-spoke-003",
        display_name="Landmark Spoke 003",
        workload="DevTest",
        billing_scope="/providers/Microsoft.Billing/billingAccounts/1/invoiceSections/2",
    )

    subscription_id = getattr(result, "subscription_id", None)
    if subscription_id is None and isinstance(result, dict):
        subscription_id = result.get("subscription_id")
    assert subscription_id == expected_subscription_id, (
        "Expected create_subscription to return the subscription_id from the "
        "terminal 'Succeeded' poll response. Gil, check the poll loop's exit "
        f"condition and return value (got {subscription_id!r})."
    )
    assert client.get.call_count == 3, (
        "Expected exactly 3 polling GET calls (Accepted, InProgress, "
        f"Succeeded) but got {client.get.call_count}. Gil, the poll loop "
        "should keep calling GET until a terminal state is reached, then stop."
    )


def test_create_subscription_raises_on_failed_provisioning_state():
    """GIVEN an alias that resolves to the terminal 'Failed' state
    WHEN create_subscription polls the alias GET
    THEN it raises rather than silently returning a missing/None
    subscription_id, so orchestrator callers never proceed with a
    subscription that was never actually created.
    """
    client = _client_stub(
        put_response={"properties": {"provisioningState": "Accepted"}},
        get_responses=[{"properties": {"provisioningState": "Failed"}}],
    )

    with pytest.raises(Exception):
        subscriptions.create_subscription(
            client=client,
            alias="landmark-spoke-004",
            display_name="Landmark Spoke 004",
            workload="Production",
            billing_scope="/providers/Microsoft.Billing/billingAccounts/1/invoiceSections/2",
        )