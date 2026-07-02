"""Invoice-section event trigger skeleton.

This module is the *event-adapter* boundary for the
subscription-vending workflow: it exists to show how a "new MCA
invoice section was created" event would be mapped into a call to
:func:`blueprintandchill.vending.orchestrator.provision_subscription`.

It is deliberately a FRAMEWORK SKELETON, not a finished integration:

    - There is no live Azure Event Grid, Azure Function, or Logic App
      subscription wired up here. Every place a real event source
      would plug in is marked with an explicit ``TODO`` comment.
    - The handler takes its collaborators (Azure SDK clients, the
      request-builder callback, the orchestrator function itself) as
      constructor / call arguments so it can be unit-tested with
      in-memory stubs today, and re-pointed at real infrastructure
      later with zero changes to the mapping logic.
    - Building a full :class:`~blueprintandchill.models.vending.ProvisioningRequest`
      from an :class:`~blueprintandchill.models.events.InvoiceSectionEventPayload`
      requires policy decisions this task does not own (naming
      conventions, default owner object id, default management group,
      tag baseline). Rather than guess at those, the mapping is an
      injectable ``ProvisioningRequestBuilder`` callback - the caller
      supplies the real mapping once those decisions are made.

Wiring this up for real, later, means (at minimum):

    TODO(event-source): stand up an Azure Event Grid *system topic*
        subscription on the Microsoft.Billing / MCA invoice-section
        resource (or a Logic App polling the Billing API on a
        schedule, if MCA invoice-section create events are not yet
        emitted natively to Event Grid in the target tenant) and
        register an Azure Function with an Event Grid trigger that
        calls :func:`parse_event_grid_envelope` then
        :func:`handle_invoice_section_event`.
    TODO(identity): the Azure Function's managed identity needs the
        Billing Account "Contributor" (or narrower, purpose-built)
        RBAC role in order for the downstream Graph / Billing /
        Subscription clients constructed at the real call site to
        authenticate as something other than a stub.
    TODO(idempotency): persist processed ``event_id`` values (e.g. in
        Cosmos DB) so a redelivered Event Grid event does not trigger
        a duplicate subscription-vending run.
    TODO(error-handling): route handler exceptions to a dead-letter
        destination (Event Grid dead-lettering to a Storage Queue, or
        an Azure Function retry policy) rather than swallowing them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from blueprintandchill.models.events import InvoiceSectionEventPayload
from blueprintandchill.models.vending import ProvisioningRequest
from blueprintandchill.vending.orchestrator import provision_subscription

# A caller-supplied mapping from the typed invoice-section event
# payload to a fully-formed ProvisioningRequest. This is injected
# rather than hard-coded here because the real mapping depends on
# naming conventions, default owner object id, default management
# group, and tag baseline decisions that belong to configuration, not
# to this event-adapter module.
#
# TODO(config): replace the placeholder builder in
#     `default_provisioning_request_builder` below with a real
#     implementation once those naming/ownership decisions are made,
#     and wire that implementation in at the real event-source call
#     site instead of relying on the placeholder.
ProvisioningRequestBuilder = Callable[[InvoiceSectionEventPayload], ProvisioningRequest]


class SupportsProvisionSubscription(Protocol):
    """Structural type for the orchestrator entrypoint this handler calls.

    Modeled as a Protocol (rather than importing a concrete signature)
    so unit tests can substitute any zero-argument-free callable that
    matches this shape without depending on the orchestrator's exact
    keyword-argument names.
    """

    def __call__(
        self,
        request: ProvisioningRequest,
        *,
        graph_client: Any,
        billing_client: Any,
        subscription_client: Any,
    ) -> Any:
        ...


def default_provisioning_request_builder(
    payload: InvoiceSectionEventPayload,
) -> ProvisioningRequest:
    """Placeholder mapping from an invoice-section event to a request.

    This is intentionally the simplest thing that could plausibly
    work, using only fields the event payload actually carries. It
    exists so the skeleton is exercisable end-to-end in tests without
    a caller having to supply a builder - it is NOT the real naming /
    ownership policy for Landmark.

    TODO(config): replace with the real Landmark naming convention,
        default owner object id resolution (likely: the requester's
        Entra ID object id looked up via ``payload.initiated_by``),
        default management group placement, and tag baseline before
        this is used against anything other than a stub client in
        tests.
    """
    tags: dict[str, str] = {
        "billingSection": payload.invoice_section_id,
        "correlationId": payload.correlation_id or payload.event_id,
    }
    return ProvisioningRequest(
        display_name=payload.invoice_section_name,
        billing_scope=payload.billing_scope,
        owner_object_id=payload.initiated_by or "TODO-resolve-owner-object-id",
        tags=tags,
    )


@dataclass
class InvoiceSectionEventHandler:
    """Isolated handler that maps an invoice-section event to provisioning.

    All collaborators are supplied at construction time so this class
    has zero live-Azure dependencies of its own - it can be
    instantiated in a unit test with fakes, or instantiated at a real
    Azure Function entrypoint with genuine SDK clients, without any
    change to this module.

    Attributes:
        graph_client: Passed through to
            :func:`~blueprintandchill.vending.orchestrator.provision_subscription`
            for service-principal creation.
        billing_client: Passed through for billing-role assignment.
        subscription_client: Passed through for subscription-alias
            creation.
        request_builder: Callback that maps a typed invoice-section
            event payload into a :class:`ProvisioningRequest`. Defaults
            to :func:`default_provisioning_request_builder`.
        provision_subscription_fn: The orchestrator entrypoint to
            invoke once the request is built. Defaults to the real
            :func:`blueprintandchill.vending.orchestrator.provision_subscription`,
            but is overridable so tests can inject a stub instead.
    """

    graph_client: Any
    billing_client: Any
    subscription_client: Any
    request_builder: ProvisioningRequestBuilder = default_provisioning_request_builder
    provision_subscription_fn: SupportsProvisionSubscription = provision_subscription

    def handle(self, payload: InvoiceSectionEventPayload) -> Any:
        """Map an invoice-section event payload to a provisioning run.

        Args:
            payload: The typed, already-validated invoice-section
                event payload (see
                ``blueprintandchill.models.events.InvoiceSectionEventPayload``).

        Returns:
            Whatever :func:`provision_subscription` returns for this
            handler's injected ``provision_subscription_fn`` (a typed
            provisioning result in the real orchestrator).
        """
        request = self.request_builder(payload)
        return self.provision_subscription_fn(
            request,
            graph_client=self.graph_client,
            billing_client=self.billing_client,
            subscription_client=self.subscription_client,
        )


def handle_invoice_section_event(
    payload: InvoiceSectionEventPayload,
    *,
    graph_client: Any,
    billing_client: Any,
    subscription_client: Any,
    request_builder: ProvisioningRequestBuilder = default_provisioning_request_builder,
    provision_subscription_fn: SupportsProvisionSubscription = provision_subscription,
) -> Any:
    """Functional convenience wrapper around :class:`InvoiceSectionEventHandler`.

    Provided so a future Azure Function entrypoint (or a test) can
    call a single function rather than constructing the handler class
    itself, while still injecting every collaborator explicitly.

    TODO(event-source): this is the function a real Azure Function
        trigger body should call, after constructing genuine
        ``graph_client`` / ``billing_client`` / ``subscription_client``
        instances from the Function's managed identity, e.g.:

            azure_function_entrypoint(event) calls
                payload = parse_event_grid_envelope(event.get_json())
                handle_invoice_section_event(
                    payload,
                    graph_client=real_graph_client,
                    billing_client=real_billing_client,
                    subscription_client=real_subscription_client,
                    request_builder=landmark_request_builder,
                )

        No such Azure Function is registered yet in this repository -
        that infrastructure (Function App, Event Grid subscription,
        managed identity + RBAC) is out of scope for this task and is
        tracked as a follow-up.
    """
    handler = InvoiceSectionEventHandler(
        graph_client=graph_client,
        billing_client=billing_client,
        subscription_client=subscription_client,
        request_builder=request_builder,
        provision_subscription_fn=provision_subscription_fn,
    )
    return handler.handle(payload)


def parse_event_grid_envelope(raw_event: dict[str, Any]) -> InvoiceSectionEventPayload:
    """Parse a raw Event Grid event dict into a typed payload.

    This is a thin, explicit adapter boundary: today it just validates
    a dict already shaped like ``InvoiceSectionEventPayload`` (e.g. as
    produced by a test fixture or a manually-posted event). It exists
    so the *real* Event Grid envelope-unwrapping logic has a single,
    obvious place to live once it is implemented.

    Args:
        raw_event: A mapping expected to either already match
            ``InvoiceSectionEventPayload``'s fields, or (once the TODO
            below is implemented) an actual Event Grid event envelope
            with a ``data`` key holding the MCA invoice-section
            payload.

    Returns:
        A validated :class:`InvoiceSectionEventPayload`.

    Raises:
        pydantic.ValidationError: if ``raw_event`` does not match the
            expected shape.

    TODO(event-source): once a real Event Grid subscription is wired
        up (see module docstring), replace this body with real
        envelope handling:
            1. Validate the Event Grid envelope's ``eventType`` is the
               expected MCA "invoice section created" event type
               (or the Azure Billing API polling equivalent) and
               reject/log anything else.
            2. Unwrap the envelope's ``data`` field (the actual
               invoice-section resource) rather than assuming
               ``raw_event`` is already flat.
            3. Map MCA billing API field names (which differ from this
               local model's field names) into
               ``InvoiceSectionEventPayload`` explicitly, rather than
               relying on the field names matching by coincidence.
    """
    return InvoiceSectionEventPayload.model_validate(raw_event)


__all__ = [
    "InvoiceSectionEventHandler",
    "ProvisioningRequestBuilder",
    "SupportsProvisionSubscription",
    "default_provisioning_request_builder",
    "handle_invoice_section_event",
    "parse_event_grid_envelope",
]