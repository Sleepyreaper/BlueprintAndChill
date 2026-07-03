"""Command-line interface for BlueprintAndChill's subscription-vending scaffold.

Glavin! This module gives Landmark's platform engineers a thin,
FastAPI-independent way to exercise the vending *service layer*
(`vending.py`) directly from a terminal, without standing up the web
app. It intentionally does NOT import anything from a future
`routers/` / FastAPI package -- this module must keep working even if
the web layer is torn out and rebuilt.

Two subcommands are exposed:

    provision
        Directly invokes `vending.provision_subscription()` with an
        alias / display name / workload / billing scope supplied on
        the command line. This is the "break glass, do it by hand"
        path an engineer uses while the real trigger is being wired
        up.

    simulate-invoice-trigger
        Builds a lightweight, in-process stand-in for a
        Microsoft.Billing "invoice section created" event payload
        (see `InvoiceSectionEvent` below) and feeds the fields it
        would carry into the same `provision_subscription()` call.
        This lets engineers rehearse the intended production trigger
        path (see TODO(event-integration) in vending.py) without a
        real Event Grid subscription or a real MCA invoice section.

Both commands print a single structured JSON document to stdout
(dataclasses, enums, and nested results are all made JSON-safe by
`_to_jsonable`) so this CLI is easy to script against or pipe into
`jq` while the scaffold grows.

Entry point wiring: `pyproject.toml` is expected to expose this via

    [project.scripts]
    blueprintandchill = "blueprintandchill.cli:main"

TODO(event-integration): once a real Azure Event Grid subscription on
Microsoft.Billing "invoice section created" events exists, its
handler should call `vending.provision_subscription()` the same way
`_run_simulate_invoice_trigger()` does here -- this command is meant
to be a faithful, side-effect-free rehearsal of that exact call
shape, not a parallel implementation.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import inspect
import json
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from .clients import ManagementApiError, PollingTimeoutError
from .vending import provision_subscription

_DEFAULT_WORKLOAD = "Production"
_WORKLOAD_CHOICES = ("Production", "DevTest")


@dataclass
class InvoiceSectionEvent:
    """Lightweight stand-in for a Microsoft.Billing invoice-section event.

    This is deliberately NOT a copy of the real Event Grid schema --
    it carries only the handful of fields `provision_subscription()`
    actually needs, so the simulation stays honest about what this
    scaffold does and does not model. Once real event wiring lands,
    the production handler should translate the true Event Grid
    payload into a call shaped like this one.
    """

    invoice_section_id: str
    billing_scope: str
    display_name: str
    workload: str = _DEFAULT_WORKLOAD
    alias: Optional[str] = None

    def resolved_alias(self) -> str:
        """Derive a subscription alias when the caller did not supply one."""
        if self.alias:
            return self.alias
        return f"landmark-{self.invoice_section_id.strip().lower()}"


def _to_jsonable(value: Any) -> Any:
    """Recursively convert dataclasses / enums / containers to JSON-safe values.

    In *proper* code, service-layer return types stay decoupled from
    any particular serialization format -- so the CLI, not the
    service layer, owns the job of flattening `vending.py` result
    objects (dataclasses, enums, nested results) into something
    `json.dumps` can render without a custom encoder at every call
    site.
    """
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field_name: _to_jsonable(field_value)
            for field_name, field_value in dataclasses.asdict(value).items()
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


async def _maybe_await(result: Any) -> Any:
    """Await `result` if the service layer returned a coroutine, else pass through.

    `vending.py` documents a polling loop for provisioningState, which
    strongly suggests these functions may become `async def` as the
    live Azure calls are wired in. This helper keeps the CLI correct
    either way without the CLI having to know which mode is in effect.
    """
    if inspect.isawaitable(result):
        return await result
    return result


async def _run_provision(args: argparse.Namespace) -> dict:
    """Handler for the `provision` subcommand."""
    result = provision_subscription(
        alias=args.alias,
        display_name=args.display_name,
        workload=args.workload,
        billing_scope=args.billing_scope,
    )
    result = await _maybe_await(result)
    return {
        "command": "provision",
        "request": {
            "alias": args.alias,
            "display_name": args.display_name,
            "workload": args.workload,
            "billing_scope": args.billing_scope,
        },
        "result": _to_jsonable(result),
    }


async def _run_simulate_invoice_trigger(args: argparse.Namespace) -> dict:
    """Handler for the `simulate-invoice-trigger` subcommand."""
    event = InvoiceSectionEvent(
        invoice_section_id=args.invoice_section_id,
        billing_scope=args.billing_scope,
        display_name=args.display_name,
        workload=args.workload,
        alias=args.alias,
    )
    alias = event.resolved_alias()

    print(
        "[simulate-invoice-trigger] simulated Microsoft.Billing "
        f"'invoice section created' event received for "
        f"invoice_section_id={event.invoice_section_id!r} "
        f"-> resolved_alias={alias!r}",
        file=sys.stderr,
    )

    result = provision_subscription(
        alias=alias,
        display_name=event.display_name,
        workload=event.workload,
        billing_scope=event.billing_scope,
    )
    result = await _maybe_await(result)
    return {
        "command": "simulate-invoice-trigger",
        "event": _to_jsonable(event),
        "resolved_alias": alias,
        "result": _to_jsonable(result),
    }


def _build_parser() -> argparse.ArgumentParser:
    """Assemble the argparse CLI tree for `blueprintandchill`."""
    parser = argparse.Ar