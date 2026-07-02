"""Billing-scope subscription-creator role assignment slice.

Scope of this module (and only this module):
    - Grant a Microsoft Entra ID service principal the *billing-scope*
      "Azure subscription creator" role on a specific invoice section,
      via the Billing RP ``billingRoleAssignments`` PUT operation.

Explicitly OUT of scope here:
    - Creating the service principal itself (see
      ``blueprintandchill.vending.service_principals``).
    - Creating/aliasing the Azure subscription (a later module).
    - Any Azure RBAC (``Microsoft.Authorization/roleAssignments``)
      role assignment. This module NEVER touches Azure RBAC.

CRITICAL DISTINCTION - billing-scope roles vs Azure RBAC:
    The "Azure subscription creator" role assigned here lives entirely
    inside the Billing RP (``billingRoleAssignments`` /
    ``billingRoleDefinitions``), scoped to a billing account, billing
    profile, or invoice section. It is a *billing* permission that
    lets a principal create new subscriptions and associate them with
    an invoice section for billing purposes.

    It is completely separate from, and grants NO permissions within,
    Azure RBAC (``Microsoft.Authorization/roleAssignments``). It is
    NOT Owner. It is NOT Contributor. It does NOT grant access to any
    Azure resource, resource group, or management group. Any Azure
    RBAC access the newly-vended subscription's landing zone requires
    (e.g. management group Contributor for policy assignment) must be
    granted separately, deliberately, and is explicitly out of scope
    for this module.

Design notes:
    - The billing scope is taken *verbatim* from the caller-supplied
      ``InvoiceSectionEventPayload.billing_scope`` (see
      ``blueprintandchill.models.events``). This module never
      constructs, guesses, or reformats a billing scope string - it
      only appends the well-known ``/billingRoleAssignments/{guid}``
      and ``/billingRoleDefinitions/{guid}`` suffixes to whatever
      scope it is given.
    - The role definition GUID
      ``a0bcee42-bf30-4d1b-926a-48d21664ef71`` is the fixed, published
      Billing RP "Azure subscription creator" role definition ID. It
      is a module-level constant so it is never re-typed (and
      potentially mistyped) at call sites.
    - A fresh assignment GUID is generated per call via ``uuid.uuid4``
      so each invocation is a distinct, idempotent-by-GUID billing
      role assignment resource (the Billing RP PUT is keyed by this
      GUID in the path).
    - Live Billing RP access is behind the ``BillingRoleAssignmentClient``
      Protocol so ``assign_subscription_creator_role`` is independently
      unit-testable with an in-memory fake - no tenant/network access
      required. The production-facing ``LiveBillingRoleAssignmentClient``
      wires to ``blueprintandchill.azure.http_client.AzureManagementClient``
      but the actual PUT call is marked TODO pending final review of
      the Billing RP request/response contract against a live tenant.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from blueprintandchill.models.events import InvoiceSectionEventPayload

try:
    # Guarded import so this module still parses / is unit-testable in
    # environments where azure-identity/httpx (transitive deps of the
    # http_client module) are not yet installed, matching the pattern
    # established in t06/t07.
    from blueprintandchill.azure.http_client import (
        AzureManagementClient,
        AzureManagementResponse,
    )
except ImportError:  # pragma: no cover - exercised only when deps missing
    AzureManagementClient = Any  # type: ignore[assignment,misc]
    AzureManagementResponse = Any  # type: ignore[assignment,misc]


BILLING_ROLE_ASSIGNMENTS_API_VERSION = "2024-04-01"

SUBSCRIPTION_CREATOR_BILLING_ROLE_DEFINITION_GUID = "a0bcee42-bf30-4d1b-926a-48d21664ef71"

BILLING_ROLE_KIND = "BillingScope"
"""Marker constant distinguishing this assignment kind from Azure RBAC.

Any consumer of ``BillingRoleAssignmentMetadata.role_kind`` can assert
on this value to guarantee, at runtime, that no Azure RBAC role has
been silently substituted for the intended billing-scope role.
"""


class BillingRoleAssignmentPrincipalType:
    """Allowed principal types for a billing role assignment.

    Kept as simple string constants (rather than an enum) so callers
    can pass either value without an extra import in the common case.
    """

    SERVICE_PRINCIPAL = "ServicePrincipal"
    USER = "User"


class BillingRoleAssignmentMetadata(BaseModel):
    """Typed result of a billing-scope role assignment call.

    This is intentionally distinct from
    ``blueprintandchill.models.vending.BillingRoleAssignmentResult`` so
    this module can be developed, tested, and reasoned about fully in
    isolation, as required by this task. A future orchestrator task
    may choose to map between the two.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    assignment_id: str = Field(..., min_length=1)
    principal_id: str = Field(..., min_length=1)
    principal_type: str = Field(default=BillingRoleAssignmentPrincipalType.SERVICE_PRINCIPAL)
    billing_scope: str = Field(..., min_length=1)
    role_definition_id: str = Field(..., min_length=1)
    role_kind: str = Field(default=BILLING_ROLE_KIND)
    request_path: str = Field(..., min_length=1)
    api_version: str = Field(default=BILLING_ROLE_ASSIGNMENTS_API_VERSION)
    status_code: int | None = None
    provisioning_state: str | None = None
    is_azure_rbac: bool = Field(default=False)


class BillingRoleAssignmentClient(Protocol):
    """Transport boundary this module depends on, not concretely.

    Implementations are responsible ONLY for issuing the raw PUT
    request against the Billing RP and returning a structured
    response. They must NOT reinterpret, widen, or substitute the
    scope/role/body handed to them.
    """

    def put_role_assignment(
        self,
        request_path: str,
        api_version: str,
        body: dict[str, Any],
    ) -> AzureManagementResponse:
        """Issue the billingRoleAssignments PUT and return the response."""
        ...


@dataclass
class LiveBillingRoleAssignmentClient:
    """Production-facing client wiring to the shared ARM HTTP client.

    TODO(gil): Wire this to a real ``AzureManagementClient.request()``
    call once the Billing RP request/response contract (headers,
    async-operation polling behavior for this specific PUT, and error
    body shape) has been validated against a live Landmark tenant.
    Until then this raises ``NotImplementedError`` so no accidental
    live call is ever made from an incomplete implementation.
    """

    management_client: AzureManagementClient

    def put_role_assignment(
        self,
        request_path: str,
        api_version: str,
        body: dict[str, Any],
    ) -> AzureManagementResponse:
        # TODO(gil): replace with a real call, e.g.:
        #   return self.management_client.request(
        #       method="PUT",
        #       path=request_path,
        #       api_version=api_version,
        #       json_body=body,
        #   )
        raise NotImplementedError(
            "LiveBillingRoleAssignmentClient.put_role_assignment is a stub. "
            "Wire to AzureManagementClient once the Billing RP contract "
            "has been validated against a live tenant."
        )


def _build_role_definition_id(billing_scope: str) -> str:
    """Construct the fixed 'Azure subscription creator' role definition id.

    Always ``{scope}/billingRoleDefinitions/{well_known_guid}``. Never
    accepts or invents an alternate role definition GUID - this
    function has exactly one job.
    """
    return f"{billing_scope}/billingRoleDefinitions/{SUBSCRIPTION_CREATOR_BILLING_ROLE_DEFINITION_GUID}"


def _build_request_path(billing_scope: str, assignment_guid: str) -> str:
    """Construct the billingRoleAssignments PUT path for a new assignment."""
    return f"{billing_scope}/billingRoleAssignments/{assignment_guid}"


def _build_request_body(principal_id: str, principal_type: str, role_definition_id: str) -> dict[str, Any]:
    """Construct the exact PUT request body for a billing role assignment."""
    return {
        "properties": {
            "principalId": principal_id,
            "principalTenantId": None,
            "principalType": principal_type,
            "roleDefinitionId": role_definition_id,
        }
    }


def assign_subscription_creator_role(
    principal_id: str,
    invoice_section: InvoiceSectionEventPayload,
    *,
    principal_type: str = BillingRoleAssignmentPrincipalType.SERVICE_PRINCIPAL,
    client: BillingRoleAssignmentClient | None = None,
) -> BillingRoleAssignmentMetadata:
    """Assign the billing-scope 'Azure subscription creator' role.

    Grants ``principal_id`` the least-privilege billing-scope role
    needed to create subscriptions against ``invoice_section``. This
    is NOT an Azure RBAC Owner or Contributor assignment, and it never
    touches ``Microsoft.Authorization/roleAssignments`` - it operates
    exclusively against the Billing RP's ``billingRoleAssignments``
    resource, scoped to the invoice section's exact billing scope.

    Arguments:
        principal_id: object id of the service principal (or user, if
            ``principal_type`` is overridden) to grant the role to.
        invoice_section: the event payload describing the invoice
            section that was just created. Its ``billing_scope``
            field is used verbatim as the assignment scope - this
            function never derives or reconstructs a billing scope
            string on its own.
        principal_type: billing RP principal type string. Defaults to
            ``ServicePrincipal`` because subscription vending grants
            this role to the automation's service principal, not a
            human user.
        client: injectable transport implementing
            ``BillingRoleAssignmentClient``. Defaults to
            ``LiveBillingRoleAssignmentClient``-shaped behavior being
            required by the caller; pass an in-memory fake in tests to
            avoid any network/tenant dependency.

    Returns:
        Typed ``BillingRoleAssignmentMetadata`` describing the
        assignment that was requested (and, once ``client`` is a real
        implementation, its resulting status).

    Raises:
        ValueError: if ``principal_id`` or the invoice section's
            billing scope is empty.
        NotImplementedError: if no ``client`` is supplied and the
            default live client's stub is invoked.
    """
    if not principal_id or not principal_id.strip():
        raise ValueError("principal_id must be a non-empty string.")

    billing_scope = invoice_section.billing_scope
    if not billing_scope or not billing_scope.strip():
        raise ValueError("invoice_section.billing_scope must be a non-empty string.")

    assignment_guid = str(uuid.uuid4())
    role_definition_id = _build_role_definition_id(billing_scope)
    request_path = _build_request_path(billing_scope, assignment_guid)
    request_body = _build_request_body(principal_id, principal_type, role_definition_id)

    if client is None:
        raise NotImplementedError(
            "assign_subscription_creator_role requires an injected "
            "BillingRoleAssignmentClient in this framework/scaffold PR. "
            "Pass a LiveBillingRoleAssignmentClient (once wired) for "
            "real calls, or a fake implementation for tests."
        )

    response = client.put_role_assignment(
        request_path=request_path,
        api_version=BILLING_ROLE_ASSIGNMENTS_API_VERSION,
        body=request_body,
    )

    status_code = getattr(response, "status_code", None)
    provisioning_state: str | None = None
    json_body = getattr(response, "json_body", None)
    if isinstance(json_body, dict):
        properties = json_body.get("properties")
        if isinstance(properties, dict):
            candidate_state = properties.get("provisioningState")
            if isinstance(candidate_state, str):
                provisioning_state = candidate_state

    return BillingRoleAssignmentMetadata(
        assignment_id=assignment_guid,
        principal_id=principal_id,
        principal_type=principal_type,
        billing_scope=billing_scope,
        role_definition_id=role_definition_id,
        role_kind=BILLING_ROLE_KIND,
        request_path=request_path,
        api_version=BILLING_ROLE_ASSIGNMENTS_API_VERSION,
        status_code=status_code,
        provisioning_state=provisioning_state,
        is_azure_rbac=False,
    )


__all__ = [
    "BILLING_ROLE_ASSIGNMENTS_API_VERSION",
    "SUBSCRIPTION_CREATOR_BILLING_ROLE_DEFINITION_GUID",
    "BILLING_ROLE_KIND",
    "BillingRoleAssignmentPrincipalType",
    "BillingRoleAssignmentMetadata",
    "BillingRoleAssignmentClient",
    "LiveBillingRoleAssignmentClient",
    "assign_subscription_creator_role",
]