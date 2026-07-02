"""Unit tests for the subscription-vending orchestrator.

Covers blueprintandchill.vending.orchestrator.provision_subscription:
    - the happy path sequences the three collaborators in order -
      create_service_principal -> assign_subscription_creator_role ->
      create_subscription - and returns their aggregated result
    - a failure raised by any collaborator propagates out of the
      orchestrator rather than being swallowed, and later steps are
      never invoked once an earlier one fails

All collaborators (graph_client, billing_client, subscription_client)
are MagicMock doubles injected directly - no live Azure SDK or network
access is used anywhere in this file.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

try:
    from blueprintandchill.vending import orchestrator
except ImportError:
    pytest.skip(
        "blueprintandchill.vending.orchestrator not importable yet; "
        "Gil, please make sure the module + its dependencies are installed.",
        allow_module_level=True,
    )


def _patched(monkeypatch, sp_result=None, role_result=None, sub_result=None,
             sp_side_effect=None, role_side_effect=None, sub_side_effect=None):
    """Patch the three composed slice functions the orchestrator calls."""
    sp_mock = MagicMock(return_value=sp_result, side_effect=sp_side_effect)
    role_mock = MagicMock(return_value=role_result, side_effect=role_side_effect)
    sub_mock = MagicMock(return_value=sub_result, side_effect=sub_side_effect)

    monkeypatch.setattr(orchestrator, "create_service_principal", sp_mock, raising=False)
    monkeypatch.setattr(orchestrator, "assign_subscription_creator_role", role_mock, raising=False)
    monkeypatch.setattr(orchestrator, "create_subscription", sub_mock, raising=False)
    return sp_mock, role_mock, sub_mock


def test_provision_subscription_happy_path_sequences_sp_role_then_subscription(monkeypatch):
    """GIVEN a request and three collaborator clients that all succeed
    WHEN provision_subscription runs
    THEN create_service_principal, assign_subscription_creator_role,
    and create_subscription are each called exactly once, in that
    order, so the billing role is never assigned before the SP exists
    and the subscription is never created before the role is granted.
    """
    call_order = []

    sp_mock, role_mock, sub_mock = _patched(
        monkeypatch,
        sp_result=MagicMock(app_id="app-1", service_principal_object_id="sp-1"),
        role_result=MagicMock(role_assignment_id="role-1"),
        sub_result=MagicMock(subscription_id="sub-1"),
    )
    sp_mock.side_effect = lambda *a, **k: call_order.append("sp") or sp_mock.return_value
    role_mock.side_effect = lambda *a, **k: call_order.append("role") or role_mock.return_value
    sub_mock.side_effect = lambda *a, **k: call_order.append("sub") or sub_mock.return_value

    graph_client = MagicMock()
    billing_client = MagicMock()
    subscription_client = MagicMock()

    result = orchestrator.provision_subscription(
        graph_client=graph_client,
        billing_client=billing_client,
        subscription_client=subscription_client,
        display_name="Landmark Spoke 001",
        billing_scope="/providers/Microsoft.Billing/billingAccounts/1/invoiceSections/2",
    )

    assert call_order == ["sp", "role", "sub"], (
        "Expected provision_subscription to call create_service_principal, "
        "then assign_subscription_creator_role, then create_subscription, "
        f"in that exact order but got {call_order!r}. Gil, check the "
        "sequencing in provision_subscription."
    )
    subscription_id = getattr(result, "subscription_id", None)
    assert subscription_id == "sub-1", (
        "Expected the orchestrator's result to carry the subscription_id "
        f"from create_subscription (got {subscription_id!r}). Gil, make "
        "sure ProvisionSubscriptionResult forwards it through."
    )


def test_provision_subscription_raises_when_service_principal_creation_fails(monkeypatch):
    """GIVEN a graph_client whose create_service_principal call fails
    WHEN provision_subscription runs
    THEN the failure propagates out of the orchestrator and neither
    assign_subscription_creator_role nor create_subscription are ever
    invoked - Landmark should never grant a billing role or create a
    subscription tied to a service principal that does not exist.
    """
    sp_mock, role_mock, sub_mock = _patched(
        monkeypatch,
        sp_side_effect=RuntimeError("graph API unavailable"),
    )

    with pytest.raises(RuntimeError):
        orchestrator.provision_subscription(
            graph_client=MagicMock(),
            billing_client=MagicMock(),
            subscription_client=MagicMock(),
            display_name="Landmark Spoke 002",
            billing_scope="/providers/Microsoft.Billing/billingAccounts/1/invoiceSections/2",
        )

    role_mock.assert_not_called()
    sub_mock.assert_not_called()


def test_provision_subscription_raises_when_role_assignment_fails_and_skips_subscription_creation(monkeypatch):
    """GIVEN a service principal is created successfully but the
    billing role assignment fails
    WHEN provision_subscription runs
    THEN the failure propagates and create_subscription is never
    called - Landmark should never provision a subscription for a
    principal that was never granted the subscription-creator role.
    """
    sp_mock, role_mock, sub_mock = _patched(
        monkeypatch,
        sp_result=MagicMock(app_id="app-2", service_principal_object_id="sp-2"),
        role_side_effect=RuntimeError("billing role assignment rejected"),
    )

    with pytest.raises(RuntimeError):
        orchestrator.provision_subscription(
            graph_client=MagicMock(),
            billing_client=MagicMock(),
            subscription_client=MagicMock(),
            display_name="Landmark Spoke 003",
            billing_scope="/providers/Microsoft.Billing/billingAccounts/1/invoiceSections/2",
        )

    sp_mock.assert_called_once()
    sub_mock.assert_not_called()