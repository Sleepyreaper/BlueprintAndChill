"""End-to-end subscription-vending orchestration.

This module is the *composition root* for the BlueprintAndChill
subscription-vending workflow. It contains no web, CLI, or transport
concerns of its own - it exists purely to sequence the three
independently-testable slices already implemented elsewhere in this
package, in the order the CAF / ALZ subscription-vending pattern
requires:

    1. ``blueprintandchill.vending.service_principals.create_service_principal``
       - register the Entra ID application + service principal that
         will own the new subscription's billing-scope permission.
    2. ``blueprintandchill.vending.billing_roles.assign_subscription_creator_role``
       - grant that service principal the billing-scope "Azure
         subscription creator" role on the triggering invoice
         section.
    3. ``blueprintandchill.vending.subscriptions.create_subscription``
       - PUT the Microsoft.Subscription alias (using the
         now-permissioned service principal's billing scope) and poll
         it through to a terminal provisioning state.

Explicitly OUT of scope here (same boundary the three slice modules
already establish, just enforced one level up):
    - Any HTTP/CLI/web framework glue. Callers (a future FastAPI
      route, a future Azure Function event-grid trigger, a future
      CLI command) import ``provision_subscription`` and call it -
      this module never imports ``fastapi``, ``click``, or similar.
    - Spoke subscription onboarding into the ALZ landing zone
      (management group move, hub-spoke VNet peering, Azure Policy
      assignment, budget/tag baseline). Those steps come *after* a
      subscription exists and are marked with ``TODO`` below rather
      than guessed at - they depend on landing-zone design decisions
      (management group hierarchy, hub VNet address space) that are
      out of scope for this task.

Design notes - why this shape:
    - ``provision_subscription`` takes its three collaborator clients
      (``graph_client``, ``billing_client``, ``subscription_client``)
      as required keyword arguments with no default construction of
      live Azure clients anywhere in this module. That is what makes
      the orchestrator "side-effect-light outside delegated modules":
      every network-capable object is supplied by the caller, so a
      unit test can pass three in-memory stubs and exercise the full
      sequencing/aggregation logic with zero real HTTP calls.
    - Each step's typed ``*Request`` is built from the single
      ``ProvisionSubscriptionRequest`` the caller supplies - the
      orchestrator does not invent, default, or reformat any
      tenant-specific value (billing scope, workload, display name);
      it only routes data between the already-defined slice
      contracts.
    - Failures are wrapped in ``VendingOrchestrationError`` so a
      caller (and its logs/telemetry) can tell exactly which of the
      three steps failed and inspect whatever partial results were
      produced before the failure, without losing the original
      exception (``raise ... from exc``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from blueprintandchill.models.events import InvoiceSectionEventPayload
from blueprintandchill.vending.billing_roles import (
    BillingClient,
    BillingRoleAssignmentRequest,
    BillingRoleAssignmentResult,
    assign_subscription_creator_role,
)
from blueprintandchill.vending.service_principals import (
    GraphClient,
    ServicePrincipalCreationRequest,
    ServicePrincipalCreationResult,
    create_service_principal,
)
from blueprintandchill.vending.subscriptions import (
    SubscriptionClient,
    SubscriptionCreationRequest,
    SubscriptionCreationResult,
    create_subscription,
)

__all__ = [
    "ProvisionSubscriptionRequest",
    "ProvisionSubscriptionResult",
    "VendingOrchestrationError",
    "provision_subscription",
]


@dataclass(frozen=True, slots=True)
class ProvisionSubscriptionRequest:
    """Aggregated, caller-supplied input for a full vending run.

    Carries exactly the tenant-specific values the three delegated
    slices need. Nothing here is defaulted or guessed by the
    orchestrator - every field must be supplied by the caller (e.g.
    the future event-grid handler reacting to a new MCA invoice
    section).

    Attributes:
        service_principal_display_name: Display name for the Entra ID
            application/service principal to register for this
            subscription. Passed straight through to
            ``ServicePrincipalCreationRequest``.
        subscription_display_name: Display name for the new Azure
            subscription itself (shown in the Azure portal / EA-MCA
            billing views). Passed straight through to
            ``SubscriptionCreationRequest``.
        subscription_alias: The Microsoft.Subscription alias resource
            name to PUT/poll. Must be unique per vending run; reused
            aliases replay idempotently (see
            ``blueprintandchill.vending.subscriptions`` docstring).
        workload: Either ``"Production"`` or ``"DevTest"``, forwarded
            verbatim to the subscription alias request body.
        invoice_section_event: The triggering MCA invoice-section
            event payload. Its ``billing_scope`` is the single source
            of truth for both the billing-role assignment scope and
            the subscription alias's ``billingScope`` - it is read
            once here and threaded through both downstream requests
            so they can never disagree.
    """

    service_principal_display_name: str
    subscription_display_name: str
    subscription_alias: str
    workload: str
    invoice_section_event: InvoiceSectionEventPayload


@dataclass(frozen=True, slots=True)
class ProvisionSubscriptionResult:
    """Aggregated, typed output of a full vending run.

    Bundles the three slice results as-produced, plus a
    ``landing_zone_attachment_pending`` flag that is always ``True``
    from this module today - flipping it to ``False`` is the explicit
    marker of the not-yet-implemented spoke-onboarding step (see the
    ``TODO`` block in ``provision_subscription``).

    Attributes:
        service_principal: Result of step 1
            (``create_service_principal``).
        billing_role_assignment: Result of step 2
            (``assign_subscription_creator_role``).
        subscription: Result of step 3 (``create_subscription``).
        landing_zone_attachment_pending: ``True`` until a future task
            implements spoke management-group placement, hub VNet
            peering, and baseline Azure Policy assignment for the
            subscription this result describes.
    """

    service_principal: ServicePrincipalCreationResult
    billing_role_assignment: BillingRoleAssignmentResult
    subscription: SubscriptionCreationResult
    landing_zone_attachment_pending: bool = field(default=True)


class VendingOrchestrationError(RuntimeError):
    """Raised when a step of ``provision_subscription`` fails.

    Preserves which named step failed and whichever partial results
    were already produced before the failure, so a caller can log or
    retry with full context rather than just seeing a bare exception
    from deep inside one of the delegated modules.

    Attributes:
        step: Name of the step that raised (``"create_service_principal"``,
            ``"assign_subscription_creator_role"``, or
            ``"create_subscription"``).
        service_principal: The step-1 result, if it completed before
            the failure; ``None`` otherwise.
        billing_role_assignment: The step-2 result, if it completed
            before the failure; ``None`` otherwise.
    """

    def __init__(
        self,
        step: str,
        *,
        service_principal: Optional[ServicePrincipalCreationResult] = None,
        billing_role_assignment: Optional[BillingRoleAssignmentResult] = None,
    ) -> None:
        super().__init__(
            f"subscription-vending orchestration failed at step {step!r}"
        )
        self.step = step
        self.service_principal = service_principal
        self.billing_role_assignment = billing_role_assignment


def provision_subscription(
    request: ProvisionSubscriptionRequest,
    *,
    graph_client: GraphClient,
    billing_client: BillingClient,
    subscription_client: SubscriptionClient,
) -> ProvisionSubscriptionResult:
    """Run the full subscription-vending sequence and return its result.

    Executes, strictly in order:

        1. ``create_service_principal`` - via ``graph_client``.
        2. ``assign_subscription_creator_role`` - via ``billing_client``,
           using the service principal's object id from step 1 and the
           billing scope from ``request.invoice_section_event``.
        3. ``create_subscription`` - via ``subscription_client``, using
           the same billing scope plus ``request.subscription_alias``,
           ``request.subscription_display_name``, and
           ``request.workload``.

    This function performs no I/O of its own: every network-capable
    collaborator is injected by the caller, which is what makes it
    exercisable in a unit test with three in-memory stubs and no real
    Azure/Graph/Billing endpoint in sight.

    Args:
        request: The aggregated, typed vending request (see
            ``ProvisionSubscriptionRequest``).
        graph_client: Concrete or stub implementation of the
            ``GraphClient`` protocol, injected for step 1.
        billing_client: Concrete or stub implementation of the
            ``BillingClient`` protocol, injected for step 2.
        subscription_client: Concrete or stub implementation of the
            ``SubscriptionClient`` protocol, injected for step 3.

    Returns:
        A ``ProvisionSubscriptionResult`` aggregating all three step
        results, with ``landing_zone_attachment_pending`` set to
        ``True`` (see the TODO block below).

    Raises:
        VendingOrchestrationError: If any step fails. The error
            reports which named step failed and carries whichever of
            the earlier steps' results already completed, with the
            original exception attached via ``raise ... from exc``.
    """
    service_principal_result: Optional[ServicePrincipalCreationResult] = None
    billing_role_result: Optional[BillingRoleAssignmentResult] = None

    try:
        service_principal_request = ServicePrincipalCreationRequest(
            display_name=request.service_principal_display_name,
        )
        service_principal_result = create_service_principal(
            service_principal_request,
            graph_client,
        )
    except Exception as exc:  # noqa: BLE001 - re-raised with step context
        raise VendingOrchestrationError(
            "create_service_principal",
        ) from exc

    try:
        billing_role_request = BillingRoleAssignmentRequest(
            billing_scope=request.invoice_section_event.billing_scope,
            principal_object_id=service_principal_result.service_principal_object_id,
        )
        billing_role_result = assign_subscription_creator_role(
            billing_role_request,
            billing_client,
        )
    except Exception as exc:  # noqa: BLE001 - re-raised with step context
        raise VendingOrchestrationError(
            "assign_subscription_creator_role",
            service_principal=service_principal_result,
        ) from exc

    try:
        subscription_request = SubscriptionCreationRequest(
            alias=request.subscription_alias,
            display_name=request.subscription_display_name,
            workload=request.workload,
            billing_scope=request.invoice_section_event.billing_scope,
        )
        subscription_result = create_subscription(
            subscription_request,
            subscription_client,
        )
    except Exception as exc:  # noqa: BLE001 - re-raised with step context
        raise VendingOrchestrationError(
            "create_subscription",
            service_principal=service_principal_result,
            billing_role_assignment=billing_role_result,
        ) from exc

    # TODO(landing-zone-attach): Once this orchestrator returns a live
    # subscription_id, the following spoke-onboarding steps still need
    # to run before the subscription is a fully-fledged ALZ spoke.
    # None of these are implemented yet - they depend on landing-zone
    # design decisions (management group hierarchy names, hub VNet
    # address space/peering policy, baseline Azure Policy set) that
    # are out of scope for this task:
    #   1. Move the new subscription into its target ALZ management
    #      group (e.g. "landing-zones/corp" or "landing-zones/online")
    #      via Microsoft.Management/managementGroups/subscriptions PUT.
    #   2. Deploy the spoke VNet + create a VNet peering (or Virtual
    #      WAN hub connection) back to the regional hub.
    #   3. Confirm inherited Azure Policy assignments from the target
    #      management group have applied (policy compliance scan) and
    #      layer on any spoke-specific policy assignments.
    #   4. Apply the baseline tag/budget policy for the subscription
    #      per Landmark's cost-management requirements.
    #   5. Emit a completion event/notification for the demo web app's
    #      "shopping" experience to surface the new subscription and
    #      its selected landing-zone resources as ready.
    return ProvisionSubscriptionResult(
        service_principal=service_principal_result,
        billing_role_assignment=billing_role_result,
        subscription=subscription_result,
        landing_zone_attachment_pending=True,
    )