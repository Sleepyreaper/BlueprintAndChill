"""Invoice-section event handling for BlueprintAndChill.

This module is the FRONT DOOR of the subscription-vending automation
described in the platform spec: "as soon as a new MCA invoice section
is created, automatically provision a subscription linked to the
landing zone." It defines the typed event payload, the mapping from
that payload into the inputs `vending.provision_subscription()`
expects, and the Azure-Function-shaped entrypoint that a real trigger
will eventually call.

Nothing in this module makes a live network call. This is a
FRAMEWORK SKELETON: the orchestration shape and call boundaries are
real and testable in-process; the actual event-source wiring
(Event Grid subscription, Azure Function binding, or a polling
Logic App) is explicitly marked TODO below.

Why an invoice section is the trigger:

    In a Microsoft Customer Agreement (MCA), a "billing profile"
    contains one or more "invoice sections." Landmark's operating
    model is: one invoice section per business unit / cost center,
    and one Azure subscription per invoice section. The
    Microsoft.Billing resource provider emits (or can be polled for)
    invoice-section lifecycle changes, which makes "new invoice
    section" the natural, businessfacing signal to kick off
    "provision a subscription."

TODO(event-source-wiring): Bind this module's `on_new_invoice_section`
handler to one of the following real triggers (pick one during the
next implementation PR, not this scaffold):

    1. Event Grid system topic on the billing account, subscribed to
       the "Microsoft.Billing.InvoiceSectionCreated" (or equivalent)
       event type, delivering to an Azure Function with an Event Grid
       trigger binding. Preferred: lowest latency, no polling cost.
    2. A timer-triggered Azure Function that polls
       "GET /providers/Microsoft.Billing/billingAccounts/{id}/
       billingProfiles/{id}/invoiceSections" on a schedule and diffs
       against a persisted list of known invoice section IDs (e.g. in
       Cosmos DB or Table Storage). Fallback for tenants where the
       Event Grid event type is not yet available.
    3. A Logic App with a recurrence trigger calling the same
       diff-and-detect logic as (2), for teams that prefer low-code
       orchestration over Functions.

Whichever is chosen, the wiring code should do nothing but:
    (a) authenticate,
    (b) construct an `InvoiceSectionEvent`,
    (c) call `on_new_invoice_section(event)`,
    (d) translate the result into the trigger's expected return
        shape (HTTP response, Event Grid ack, etc).
All actual business logic stays in this module and in `vending.py`.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .vending import ManagementApiError, PollingTimeoutError, provision_subscription

logger = logging.getLogger(__name__)


class InvoiceSectionEventType(str, Enum):
    """The Microsoft.Billing event types this handler understands.

    TODO(event-source-wiring): confirm the exact event-type strings
    once Event Grid schema access is available for the Landmark MCA
    billing account; these are the documented CAF/ALZ-aligned names
    as of this scaffold and may need a point update.
    """

    INVOICE_SECTION_CREATED = "Microsoft.Billing.InvoiceSectionCreated"
    INVOICE_SECTION_UPDATED = "Microsoft.Billing.InvoiceSectionUpdated"


class ProvisionStatus(str, Enum):
    """Outcome status for an invoice-section-triggered provision run."""

    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    SKIPPED_DUPLICATE = "SkippedDuplicate"
    SKIPPED_UNSUPPORTED_EVENT = "SkippedUnsupportedEvent"


@dataclass(frozen=True)
class InvoiceSectionEvent:
    """Typed payload for an inbound invoice-section lifecycle event.

    This is the shape the real trigger (Event Grid, Function binding,
    or polling job) MUST populate before calling
    `on_new_invoice_section()`. Field names intentionally mirror the
    Microsoft.Billing invoice section resource so mapping from a real
    Event Grid CloudEvent payload is a thin, mechanical translation.

    Attributes:
        event_id: Unique identifier of the inbound event itself
            (Event Grid `id`, or a generated UUID for polling-sourced
            events). Used for idempotency / dedupe.
        event_type: Which lifecycle transition this event represents.
        billing_account_id: Fully-qualified MCA billing account
            resource ID, e.g.
            "/providers/Microsoft.Billing/billingAccounts/{account}".
        billing_profile_id: Fully-qualified billing profile resource
            ID under the billing account above.
        invoice_section_id: Fully-qualified invoice section resource
            ID. This becomes the billing scope for the least-privilege
            "Azure subscription creator" role assignment.
        invoice_section_display_name: Human-readable name, typically
            the business unit / cost center name. Used to derive the
            new subscription's display name.
        workload: Landing-zone workload classification for the new
            subscription (e.g. "corp" or "online"), per the ALZ
            management group taxonomy. Defaults to "corp" when the
            invoice section metadata does not specify one.
        requested_subscription_display_name: Optional override; if not
            supplied, a display name is derived from
            `invoice_section_display_name`.
        event_time: UTC timestamp the source event was raised.
        correlation_id: Propagated end-to-end for tracing across
            identity.py / clients.py / vending.py log lines.
        raw: The original, untouched event payload as received from
            the trigger, retained for audit / replay purposes.
    """

    event_id: str
    event_type: InvoiceSectionEventType
    billing_account_id: str
    billing_profile_id: str
    invoice_section_id: str
    invoice_section_display_name: str
    workload: str = "corp"
    requested_subscription_display_name: Optional[str] = None
    event_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProvisionRequest:
    """Inputs mapped from an InvoiceSectionEvent for provision_subscription().

    This intentionally mirrors the parameter shape of
    `vending.create_subscription()` / `vending.provision_subscription()`
    (alias, display_name, workload, billing_scope) plus the invoice
    section reference needed for the billing-role assignment step.
    """

    alias: str
    display_name: str
    workload: str
    billing_scope: str
    invoice_section: str
    correlation_id: str


@dataclass(frozen=True)
class ProvisionOutcome:
    """Result returned by on_new_invoice_section for the caller/trigger.

    Attributes:
        status: High-level outcome of the run.
        correlation_id: Same ID threaded through the whole call chain.
        subscription_id: The provisioned subscription GUID, if the run
            succeeded far enough to obtain one.
        message: Human-readable summary, safe to log or surface in an
            Event Grid dead-letter payload on failure.
    """

    status: ProvisionStatus
    correlation_id: str
    subscription_id: Optional[str] = None
    message: str = ""


# In-process idempotency guard for this scaffold. A production
# deployment MUST replace this with a durable store (Cosmos DB /
# Table Storage keyed on event_id) so retries and multi-instance
# Function execution do not double-provision. See TODO below.
_SEEN_EVENT_IDS: set[str] = set()


def _derive_display_name(event: InvoiceSectionEvent) -> str:
    """Build a subscription display name from an invoice-section event."""
    if event.requested_subscription_display_name:
        return event.requested_subscription_display_name
    return f"landmark-{event.invoice_section_display_name}".lower().replace(" ", "-")


def _derive_alias(event: InvoiceSectionEvent) -> str:
    """Build a stable, unique subscription alias name.

    Uses the invoice section's own ID as entropy so retried events for
    the same invoice section resolve to the same alias, making the
    downstream ARM alias PUT naturally idempotent.
    """
    short_id = event.invoice_section_id.rsplit("/", maxsplit=1)[-1]
    return f"landmark-sub-{short_id}"[:63]


def map_invoice_section_event_to_provision_request(
    event: InvoiceSectionEvent,
) -> ProvisionRequest:
    """Map a typed invoice-section event into provision_subscription inputs.

    This is the single seam between "what an Azure billing event looks
    like" and "what our subscription-vending service needs." Keeping
    this mapping in one small, pure function makes it trivial to unit
    test independent of any real trigger.
    """
    return ProvisionRequest(
        alias=_derive_alias(event),
        display_name=_derive_display_name(event),
        workload=event.workload,
        billing_scope=event.invoice_section_id,
        invoice_section=event.invoice_section_id,
        correlation_id=event.correlation_id,
    )


async def on_new_invoice_section(event: InvoiceSectionEvent) -> ProvisionOutcome:
    """Handle a new (or updated) invoice-section event end-to-end.

    This is the orchestration call boundary the spec asks for: given a
    typed invoice-section event, decide whether it warrants a new
    subscription, map it to `provision_subscription()` inputs, run the
    provisioning workflow, and return a structured outcome.

    This function is intentionally framework-agnostic (no Azure
    Functions decorator, no Event Grid SDK type) so it can be called:
        - directly, in-process, from unit tests,
        - from a local simulation harness (see
          `simulate_invoice_section_event` below),
        - from the real Azure Function entrypoint once wired
          (see `on_new_invoice_section_function_entrypoint`).

    Args:
        event: The typed invoice-section event to process.

    Returns:
        A ProvisionOutcome describing what happened.
    """
    if event.event_type not in (
        InvoiceSectionEventType.INVOICE_SECTION_CREATED,
    ):
        logger.info(
            "Ignoring unsupported invoice-section event type=%s correlation_id=%s",
            event.event_type,
            event.correlation_id,
        )
        return ProvisionOutcome(
            status=ProvisionStatus.SKIPPED_UNSUPPORTED_EVENT,
            correlation_id=event.correlation_id,
            message=f"Event type {event.event_type} does not trigger provisioning.",
        )

    # TODO(idempotency-store): Replace this in-memory set with a
    # durable, distributed check (Cosmos DB point-read on event_id, or
    # a Table Storage row) before this handler is bound to a real
    # trigger. In-memory dedupe only protects a single warm Function
    # instance and is unsafe across cold starts / scale-out.
    if event.event_id in _SEEN_EVENT_IDS:
        logger.warning(
            "Duplicate invoice-section event_id=%s correlation_id=%s -- skipping.",
            event.event_id,
            event.correlation_id,
        )
        return ProvisionOutcome(
            status=ProvisionStatus.SKIPPED_DUPLICATE,
            correlation_id=event.correlation_id,
            message="Event already processed; skipped to avoid double-provisioning.",
        )
    _SEEN_EVENT_IDS.add(event.event_id)

    request = map_invoice_section_event_to_provision_request(event)
    logger.info(
        "Provisioning subscription for invoice_section=%s alias=%s correlation_id=%s",
        request.invoice_section,
        request.alias,
        request.correlation_id,
    )

    try:
        result = await provision_subscription(
            alias=request.alias,
            display_name=request.display_name,
            workload=request.workload,
            billing_scope=request.billing_scope,
        )
    except (ManagementApiError, PollingTimeoutError) as exc:
        logger.error(
            "Provisioning failed for invoice_section=%s correlation_id=%s error=%s",
            request.invoice_section,
            request.correlation_id,
            exc,
        )
        return ProvisionOutcome(
            status=ProvisionStatus.FAILED,
            correlation_id=request.correlation_id,
            message=f"Provisioning failed: {exc}",
        )

    subscription_id = getattr(result, "subscription_id", None)
    logger.info(
        "Provisioning succeeded subscription_id=%s correlation_id=%s",
        subscription_id,
        request.correlation_id,
    )
    return ProvisionOutcome(
        status=ProvisionStatus.SUCCEEDED,
        correlation_id=request.correlation_id,
        subscription_id=subscription_id,
        message="Subscription provisioned and linked to the landing zone.",
    )


def build_event_from_raw_payload(payload: dict[str, Any]) -> InvoiceSectionEvent:
    """Translate a raw event payload dict into a typed InvoiceSectionEvent.

    TODO(event-source-wiring): Once the real trigger is chosen, replace
    the generic dict-shaped `payload` parameter with the actual
    Event Grid CloudEvent (or Azure Function binding object) type, and
    update the field lookups below to match its real schema. The
    lookups here assume a Microsoft.Billing-style event envelope with
    a nested "data" object; this is a reasonable, documented starting
    shape but is NOT guaranteed to be byte-for-byte final until tested
    against a live Event Grid subscription.
    """
    data = payload.get("data", {})
    return InvoiceSectionEvent(
        event_id=str(payload.get("id", uuid.uuid4())),
        event_type=InvoiceSectionEventType(
            payload.get("eventType", InvoiceSectionEventType.INVOICE_SECTION_CREATED.value)
        ),
        billing_account_id=data.get("billingAccountId", ""),
        billing_profile_id=data.get("billingProfileId", ""),
        invoice_section_id=data.get("invoiceSectionId", ""),
        invoice_section_display_name=data.get("invoiceSectionDisplayName", ""),
        workload=data.get("workload", "corp"),
        requested_subscription_display_name=data.get("subscriptionDisplayName"),
        raw=payload,
    )


def on_new_invoice_section_function_entrypoint(azure_event: dict[str, Any]) -> dict[str, Any]:
    """Azure-Function-shaped synchronous entrypoint for a real trigger.

    This is the function signature an Azure Functions Event Grid
    trigger (or a thin Logic App -> Function bridge) would bind to.
    It stays synchronous on the outside because Azure Functions'
    Python worker supports both sync and async defs, and keeping this
    wrapper sync makes local invocation from non-async callers (e.g. a
    quick manual test in a REPL) trivial.

    TODO(event-source-wiring): Register this function in
    `function_app.py` (not created in this scaffold PR) with an
    `@app.event_grid_trigger(arg_name="azure_event", ...)` decorator
    once the Event Grid system topic subscription described in the
    module docstring exists. Nothing else in this function needs to
    change when that wiring lands.

    Args:
        azure_event: The raw event payload as delivered by the trigger
            binding. Expected to be JSON-deserializable into the shape
            `build_event_from_raw_payload()` understands.

    Returns:
        A small JSON-serializable dict summarizing the outcome, useful
        for HTTP-triggered manual invocation during local testing.
    """
    event = build_event_from_raw_payload(azure_event)
    outcome = asyncio.run(on_new_invoice_section(event))
    return {
        "status": outcome.status.value,
        "correlationId": outcome.correlation_id,
        "subscriptionId": outcome.subscription_id,
        "message": outcome.message,
    }


def simulate_invoice_section_event(
    invoice_section_display_name: str,
    billing_account_id: str = "/providers/Microsoft.Billing/billingAccounts/00000000",
    billing_profile_id: str = "/providers/Microsoft.Billing/billingAccounts/00000000/billingProfiles/00000000",
    invoice_section_id: Optional[str] = None,
    workload: str = "corp",
) -> InvoiceSectionEvent:
    """Build a synthetic InvoiceSectionEvent for local testing/simulation.

    Not a stub for production use -- this is a deliberate test helper
    so contributors and CI can exercise `on_new_invoice_section()`
    end-to-end without any real Azure Billing event source wired up
    yet, per the "callable in-process for tests or local simulation"
    acceptance criterion for this task.
    """
    if invoice_section_id is None:
        slug = invoice_section_display_name.lower().replace(" ", "-")
        invoice_section_id = f"{billing_profile_id}/invoiceSections/{slug}"
    return InvoiceSectionEvent(
        event_id=str(uuid.uuid4()),
        event_type=InvoiceSectionEventType.INVOICE_SECTION_CREATED,
        billing_account_id=billing_account_id,
        billing_profile_id=billing_profile_id,
        invoice_section_id=invoice_section_id,
        invoice_section_display_name=invoice_section_display_name,
        workload=workload,
    )