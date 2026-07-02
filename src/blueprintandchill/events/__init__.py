"""Event-trigger skeletons for BlueprintAndChill.

This package holds *framework* adapters that translate an inbound
event (today: a "new MCA invoice section" notification) into a call
against the subscription-vending orchestrator
(:func:`blueprintandchill.vending.orchestrator.provision_subscription`).

Nothing in this package talks to a real Azure event source yet. Each
module documents, with explicit ``TODO`` markers, exactly where the
real Azure Function / Event Grid / Logic App wiring belongs so this
skeleton can be swapped into real infrastructure later without
touching the orchestration logic itself.
"""

from __future__ import annotations

from blueprintandchill.events.invoice_section_handler import (
    InvoiceSectionEventHandler,
    ProvisioningRequestBuilder,
    handle_invoice_section_event,
    parse_event_grid_envelope,
)

__all__ = [
    "InvoiceSectionEventHandler",
    "ProvisioningRequestBuilder",
    "handle_invoice_section_event",
    "parse_event_grid_envelope",
]