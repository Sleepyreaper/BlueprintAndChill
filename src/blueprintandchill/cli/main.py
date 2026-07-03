"""BlueprintAndChill CLI entrypoint for subscription-vending operations.

This module is the operational front door onto the vending core built in
blueprintandchill.vending.orchestrator. It is intentionally narrow: it
parses arguments, resolves configuration, constructs the collaborator
clients the orchestrator requires, calls provision_subscription, and
renders the result (or a clean error) to stdout/stderr with a process
exit code suitable for automation.

Explicitly out of scope for this module:
    - No FastAPI, no web framework of any kind. This is a pure CLI path
      so it can run in a shell, a CI job, or an Azure Function timer
      trigger without dragging in web dependencies.
    - No interactive secret prompts. Credentials and identity flow in
      only through the standard Azure SDK credential chain (e.g.
      DefaultAzureCredential) which is wired up where the real clients
      are constructed, never typed at a prompt.
    - No hardcoded environment values. Every environment-specific value
      (tenant, billing account, billing profile, invoice section,
      default location) comes from blueprintandchill.config.Settings,
      which itself reads from process environment variables.

Client construction below is deliberately stubbed. The real Azure SDK
clients (Microsoft Graph for service-principal creation, azure-mgmt-
billing for the billing-scope role assignment, azure-mgmt-subscription
for the alias PUT/poll) are a follow-on task; wiring them here would
require live Azure credentials at import time, which this framework
scaffold must not assume. Each stub raises a clear NotImplementedError
with a TODO pointing at the SDK client that belongs there, so running
the command against real infrastructure fails loudly and immediately
rather than silently no-opping.

Usage (once installed as a console script):

    blueprintandchill provision-subscription \\
        --alias landmark-spoke-001 \\
        --display-name "Landmark - Spoke 001" \\
        --workload Production \\
        --billing-scope /providers/Microsoft.Billing/billingAccounts/ACCT/billingProfiles/PROF/invoiceSections/SECT

Or directly during local development:

    python -m blueprintandchill.cli.main provision-subscription --help
"""

from __future__ import annotations

import dataclasses
import sys
from typing import Any, NoReturn

import typer

from blueprintandchill.config import Settings, load_settings
from blueprintandchill.vending.orchestrator import provision_subscription

app = typer.Typer(
    name="blueprintandchill",
    help=(
        "BlueprintAndChill subscription-vending CLI. "
        "Operational surface over the vending orchestrator for local "
        "testing and automation-triggered runs."
    ),
    no_args_is_help=True,
)


class _UnconfiguredGraphClient:
    """Placeholder Microsoft Graph client for service-principal creation.

    TODO: replace with a real msgraph / azure-identity backed client that
    implements whatever protocol blueprintandchill.vending.service_principals
    expects (create_service_principal and friends).
    """

    def __getattr__(self, name: str) -> NoReturn:
        raise NotImplementedError(
            "Graph client is not wired to live Azure infrastructure yet. "
            f"Attempted to call graph_client.{name}(...). "
            "TODO: construct a real Microsoft Graph client here."
        )


class _UnconfiguredBillingClient:
    """Placeholder Azure billing client for role assignment on the
    invoice-section billing scope.

    TODO: replace with a real azure-mgmt-billing backed client that
    implements whatever protocol blueprintandchill.vending.billing_roles
    expects (assign_subscription_creator_role and friends).
    """

    def __getattr__(self, name: str) -> NoReturn:
        raise NotImplementedError(
            "Billing client is not wired to live Azure infrastructure yet. "
            f"Attempted to call billing_client.{name}(...). "
            "TODO: construct a real azure-mgmt-billing client here."
        )


class _UnconfiguredSubscriptionClient:
    """Placeholder Azure subscription-alias client.

    TODO: replace with a real azure-mgmt-subscription backed client that
    implements whatever protocol blueprintandchill.vending.subscriptions
    expects (create_subscription and friends).
    """

    def __getattr__(self, name: str) -> NoReturn:
        raise NotImplementedError(
            "Subscription client is not wired to live Azure infrastructure "
            f"yet. Attempted to call subscription_client.{name}(...). "
            "TODO: construct a real azure-mgmt-subscription client here."
        )


def _build_graph_client(settings: Settings) -> _UnconfiguredGraphClient:
    """Construct the Graph client collaborator.

    Takes settings so a future real implementation can read tenant_id
    without changing this function's call site.
    """
    _ = settings
    return _UnconfiguredGraphClient()


def _build_billing_client(settings: Settings) -> _UnconfiguredBillingClient:
    """Construct the billing client collaborator."""
    _ = settings
    return _UnconfiguredBillingClient()


def _build_subscription_client(settings: Settings) -> _UnconfiguredSubscriptionClient:
    """Construct the subscription-alias client collaborator."""
    _ = settings
    return _UnconfiguredSubscriptionClient()


def _resolve_billing_scope(
    settings: Settings,
    billing_scope: str | None,
    invoice_section: str | None,
) -> str:
    """Resolve the effective billing scope to vend a subscription against.

    Precedence:
        1. An explicit --billing-scope, used verbatim.
        2. An explicit --invoice-section combined with the billing
           account/profile names already present in Settings.
        3. The invoice_section_name from Settings, combined with the
           billing account/profile names also present in Settings.

    Raises typer.BadParameter if none of the above yields a usable
    scope, so the failure surfaces before any client is called.
    """
    if billing_scope:
        return billing_scope

    section = invoice_section or settings.invoice_section_name
    if not section:
        raise typer.BadParameter(
            "No billing scope could be resolved. Provide --billing-scope, "
            "or --invoice-section together with BAC_BILLING_ACCOUNT and "
            "BAC_BILLING_PROFILE, or set BAC_INVOICE_SECTION."
        )
    if not settings.billing_account_name or not settings.billing_profile_name:
        raise typer.BadParameter(
            "Cannot build a billing scope from an invoice section without "
            "BAC_BILLING_ACCOUNT and BAC_BILLING_PROFILE set in the "
            "environment."
        )
    return (
        "/providers/Microsoft.Billing/billingAccounts/"
        f"{settings.billing_account_name}/billingProfiles/"
        f"{settings.billing_profile_name}/invoiceSections/{section}"
    )


def _render_result(result: Any) -> None:
    """Print a provisioning result in a human-readable, script-parseable form.

    Uses dataclasses.asdict when the result is a dataclass instance (the
    documented shape of ProvisionSubscriptionResult), falling back to a
    plain repr for anything else so this module never needs a hard
    import-time dependency on the exact result type's internals.
    """
    if dataclasses.is_dataclass(result) and not isinstance(result, type):
        payload = dataclasses.asdict(result)
        typer.echo("provision-subscription: success")
        for key, value in payload.items():
            typer.echo(f"  {key}: {value}")
        return
    typer.echo("provision-subscription: success")
    typer.echo(f"  result: {result!r}")


@app.command("provision-subscription")
def provision_subscription_command(
    alias: str = typer.Option(
        ...,
        "--alias",
        help="Unique alias name for the Microsoft.Subscription alias resource.",
    ),
    display_name: str = typer.Option(
        ...,
        "--display-name",
        help="Human-readable display name for the new subscription.",
    ),
    workload: str = typer.Option(
        ...,
        "--workload",
        help="Subscription workload type, e.g. Production or DevTest.",
    ),
    billing_scope: str = typer.Option(
        None,
        "--billing-scope",
        help=(
            "Full billing-scope resource ID "
            "(/providers/Microsoft.Billing/.../invoiceSections/<section>). "
            "If omitted, resolved from --invoice-section plus environment "
            "configuration."
        ),
    ),
    invoice_section: str = typer.Option(
        None,
        "--invoice-section",
        help=(
            "Invoice section name to combine with BAC_BILLING_ACCOUNT / "
            "BAC_BILLING_PROFILE when --billing-scope is not given."
        ),
    ),
) -> None:
    """Provision a new spoke subscription via the vending orchestrator.

    Resolves environment-driven Settings, resolves the effective billing
    scope, constructs the (currently stubbed) collaborator clients, and
    delegates the actual sequencing to
    blueprintandchill.vending.orchestrator.provision_subscription.

    Exits with status code 1 and a message on stderr if provisioning
    raises for any reason (unresolved billing scope, client not yet
    wired, orchestrator-level failure).
    """
    settings = load_settings()

    try:
        resolved_billing_scope = _resolve_billing_scope(
            settings, billing_scope, invoice_section
        )
    except typer.BadParameter as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    graph_client = _build_graph_client(settings)
    billing_client = _build_billing_client(settings)
    subscription_client = _build_subscription_client(settings)

    try:
        result = provision_subscription(
            alias=alias,
            display_name=display_name,
            workload=workload,
            billing_scope=resolved_billing_scope,
            graph_client=graph_client,
            billing_client=billing_client,
            subscription_client=subscription_client,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced deliberately to the operator
        typer.echo(f"error: provision-subscription failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    _render_result(result)


def main() -> None:
    """Console-script entrypoint. Wired from pyproject.toml [project.scripts]."""
    app()


if __name__ == "__main__":
    sys.exit(main() or 0)