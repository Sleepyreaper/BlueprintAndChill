"""Subscription alias creation and provisioning polling.

This module owns exactly one slice of the BlueprintAndChill vending
workflow: turning an approved vending request into a real Azure
subscription using the Microsoft.Subscription **alias** resource.

Scope (per the CAF / ALZ subscription-vending pattern this project is
built on):
    - IN scope:  PUT the alias, poll the alias GET until the
      provisioning state resolves, and return the resulting
      subscriptionId.
    - OUT of scope (owned by other modules, not this one):
      service-principal creation, billing-role-assignment (Billing
      Account Contributor / Invoice Section Contributor / etc.), and
      landing-zone attach (management-group move, policy assignment).
      Those callers are expected to invoke ``create_subscription``
      here first, then wire the returned subscription_id into their
      own workflows.

API reference (exact, per spec - do not invent alternate paths):
    PUT  https://management.azure.com/providers/Microsoft.Subscription/aliases/{aliasName}?api-version=2021-10-01
    GET  https://management.azure.com/providers/Microsoft.Subscription/aliases/{aliasName}?api-version=2021-10-01

    Request body (PUT):
        {
          "properties": {
            "displayName": "<display_name>",
            "workload": "Production" | "DevTest",
            "billingScope": "<billing_scope>"
          }
        }

    Response body (GET, while polling):
        {
          "properties": {
            "provisioningState": "Accepted" | "InProgress" | "Succeeded" | "Failed",
            "subscriptionId": "<guid>"   # present once Succeeded
          }
        }

Idempotent alias semantics (documented + preserved by shape):
    The Microsoft.Subscription alias resource is named by the caller
    (``alias``), not generated server-side. Azure treats PUT against
    an existing alias name as an upsert against that same resource -
    it does NOT create a second subscription for a second PUT with
    the same alias name. This module leans into that behavior rather
    than re-implementing it:

        1. Before issuing a PUT, ``create_subscription`` first GETs
           the alias. If it already exists and has already reached
           ``Succeeded``, the existing ``subscriptionId`` is returned
           immediately with no PUT call at all - a true no-op replay.
        2. If the alias exists but is still ``Accepted``/``InProgress``
           (e.g. a prior caller crashed mid-poll, or a retry raced a
           still-in-flight create), this module skips straight to
           polling instead of re-issuing PUT, since Azure is already
           working the request and the shared alias name IS the
           idempotency key.
        3. If the alias exists but previously reached a terminal
           failure state, this module refuses to silently retry
           under the same alias name (Azure does not resurrect a
           failed alias into a fresh attempt) and raises loudly so
           the caller can choose a new alias name.
        4. Only when the alias does not exist yet (GET -> 404) does
           this module issue the PUT that actually creates it.

    Net effect: calling ``create_subscription`` twice with the same
    ``alias`` is always safe and converges on the same subscription.

TODO(gil): once the invoice-section-created event handler (separate
task) is wired up, it will call this module's ``create_subscription``
with a deterministic alias name derived from the invoice section id
so that redelivered events are naturally idempotent too.
"""

from __future__ import ann