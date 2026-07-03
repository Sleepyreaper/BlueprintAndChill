"""Subscription-vending orchestration service for BlueprintAndChill.

This module is the top of the automation stack for Landmark's
subscription-vending accelerator. It COMPOSES the identity layer
(`identity.py`) and the ARM/Billing API client layer (`clients.py`)
into the exact public functions the platform spec calls for:

    create_service_principal()
    assign_subscription_creator_role(principal_id, invoice_section)
    create_subscription(alias, display_name, workload, billing_scope)
    provision_subscription(...)

Everything here is a PURE service-layer API: no FastAPI import, no
HTTP framework dependency, nothing that assumes it is running inside a
web request. A future API layer (routers/*.py) is expected to call
these functions and translate results into HTTP responses.

Live network calls to Microsoft Graph and Azure Resource Manager are
still stub-safe in this PR (see identity.py / clients.py docstrings for
the exact TODO boundaries). What IS fully real here:

  - The orchestration control flow (idempotency check, role
    assignment, alias PUT, provisioningState polling loop).
  - The typed request/response contracts.
  - The least-privilege role assignment shape (billing-scope
    roleDefinitionId using the built-in "Azure subscription creator"
    role GUID, scoped to a single invoice section -- never a whole
    billing account).

TODO(event-integration): Wire `provision_subscription()` as the
handler for a real trigger -- an Azure Event Grid subscription on
Microsoft.Billing "invoice section created" events (or a polling
Azure Function on a timer if that event type is unavailable in the
tenant) is the intended production trigger. That event-source wiring
is out of scope for this scaffold task.

TODO(tenant-integration): Replace `NotImplementedTokenProvider` /
stub Graph calls with real `DefaultAzureCredential` + Microsoft Graph
SDK / azure-mgmt-subscription calls once a Landmark tenant and
bootstrap credential are available.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .clients import (
    ARM_API_VERSION_BILLING_ROLE_ASSIGNMENT,
    ARM_API_VERSION_SUBSCRIPTION_ALIAS,
    BillingRoleAssignmentRequest,
    BillingRoleAssignmentResult,
    ManagementApiError,
    NotImplementedTokenProvider,
    PollingTimeoutError,
    SubscriptionAliasRequest,
    SubscriptionAliasResult,
)
from .identity import (
    AppRegistrationRequest,
    IdentityProvisioningError,
    ServicePrincipalResult,
    create_service_principal as _identity_create_service_principal,
)
from .models import InvoiceSectionIdentifier, WorkloadType

logger = logging.getLogger(__name__)

__all__ = [
    "SUBSCRIPTION_CREATOR_BILLING_ROLE_DEFINITION_GUID",
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "DEFAULT_POLL_TIMEOUT_SECONDS",
    "ProvisioningState",
    "VendingError",
    "RoleAssignmentResult",
    "ProvisionSubscriptionRequest",
    "ProvisionSubscriptionResult",
    "create_service_principal",
    "assign_subscription_creator_role",
    "create_subscription",
    "provision_subscription",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Microsoft built-in "Azure subscription creator" billing role definition
# GUID. This is the least-privilege role that can create a subscription
# against a specific invoice section without granting broader billing
# account access.
#
# Docs: https://learn.microsoft.com/azure/cost-management-billing/manage/grant-access-to-create-subscription
#
# TODO(verify-guid): Confirm this GUID against the live tenant's
# GET {billingAccountScope}/billingRoleDefinitions response before this
# accelerator goes to production -- built-in role GUIDs are stable per
# Microsoft's documentation but should always be re-verified per tenant
# type (MCA vs EA) during onboarding.
SUBSCRIPTION_CREATOR_BILLING_ROLE_DEFINITION_GUID = (
    "a0bcee42-bf30-4d1b-926a-48d21664ef71"
)

DEFAULT_POLL_INTERVAL_SECONDS: float = 5.0
DEFAULT_POLL_TIMEOUT_SECONDS: float = 600.0


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class VendingError(Exception):
    """Raised when subscription-vending orchestration fails.

    Wraps and normalizes errors from the identity layer and the ARM/
    Billing client layer so callers (API routers, background jobs) see
    a single stable exception type for the whole vending pipeline.
    """


# ---------------------------------------------------------------------------
# Enums / typed results
# ---------------------------------------------------------------------------

class ProvisioningState(str, Enum):
    """Normalized subscription-alias provisioningState values.

    Mirrors the values returned by the Microsoft.Subscription/aliases
    resource. `ACCEPTED` covers the transient "in progress" states the
    ARM API may report while polling (e.g. "Accepted", "Pending").
    """

    ACCEPTED = "Accepted"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"


@dataclass(frozen=True)
class RoleAssignmentResult:
    """Typed result of a billing-scope role assignment.

    Attributes:
        role_assignment_name: The GUID name of the created
            billingRoleAssignment resource.
        principal_id: The service principal object id granted access.
        role_definition_id: Full ARM resource id of the billing role
            definition that was assigned.
        invoice_section: The invoice section identifier the role was
            scoped to.
    """

    role_assignment_name: str
    principal_id: str
    role_definition_id: str
    invoice_section: InvoiceSectionIdentifier


@dataclass(frozen=True)
class ProvisionSubscriptionRequest:
    """Input contract for the full end-to-end vending workflow.

    Attributes:
        alias: Idempotency key for the subscription alias resource.
            Re-running provision_subscription() with the same alias
            MUST NOT create a second subscription.
        display_name: Human-readable subscription display name shown
            in the Azure portal.
        workload: Production vs. DevTest workload classification,
            which determines subscription offer type eligibility.
        billing_scope: Full ARM billing scope (invoice section) the
            new subscription is billed against.
        invoice_section: Structured identifier of the same invoice
            section, used for the billing role assignment call.
        management_group_id: Landing-zone management group the new
            subscription should be moved under once created.
    """

    alias: str
    display_name: str
    workload: WorkloadType
    billing_scope: str
    invoice_section: InvoiceSectionIdentifier
    management_group_id: Optional[str] = None


@dataclass(frozen=True)
class ProvisionSubscriptionResult:
    """Output contract for the full end-to-end vending workflow."""

    alias: str
    subscription_id: Optional[str]
    provisioning_state: ProvisioningState
    service_principal: ServicePrincipalResult
    role_assignment: RoleAssignmentResult
    management_group_id: Optional[str] = None


# ---------------------------------------------------------------------------
# create_service_principal()
# ---------------------------------------------------------------------------

def create_service_principal(
    display_name: str = "blueprintandchill-vending-automation",
) -> ServicePrincipalResult:
    """Provision the automation identity used by subscription vending.

    Thin, typed pass-through to identity.create_service_principal(),
    kept as its own public function per the vending service contract
    so callers only ever need to import from `vending`, not reach into
    `identity` directly.

    Args:
        display_name: Display name for the Entra ID app registration
            and its service principal.

    Returns:
        A ServicePrincipalResult with the app (client) id and the
        service principal object id (the id used for RBAC/billing
        role assignments).

    Raises:
        VendingError: If identity provisioning fails.
    """
    logger.info(
        "vending.create_service_principal: requesting app registration "
        "display_name=%s",
        display_name,
    )
    try:
        request = AppRegistrationRequest(display_name=display_name)
        return _identity_create_service_principal(request)
    except IdentityProvisioningError as exc:
        raise VendingError(
            "create_service_principal failed: " + str(exc)
        ) from exc


# ---------------------------------------------------------------------------
# assign_subscription_creator_role()
# ---------------------------------------------------------------------------

def assign_subscription_creator_role(
    principal_id: str,
    invoice_section: InvoiceSectionIdentifier,
) -> RoleAssignmentResult:
    """Grant a service principal the built-in "subscription creator" role.

    Scoped to a single invoice section (least privilege) rather than
    the whole billing account or billing profile. This is the minimum
    permission required for the automation identity to later call
    create_subscription() successfully against that invoice section.

    Args:
        principal_id: Object id of the service principal (NOT the
            application/client id) to grant the role to.
        invoice_section: The MCA invoice section to scope the grant
            to.

    Returns:
        A RoleAssignmentResult describing the created assignment.

    Raises:
        VendingError: If principal_id is blank or the underlying
            billing-role-assignment call fails.
    """
    if not principal_id or not principal_id.strip():
        raise VendingError(
            "assign_subscription_creator_role requires a non-blank "
            "principal_id"
        )

    invoice_section_scope = (
        "/providers/Microsoft.Billing/billingAccounts/"
        f"{invoice_section.billing_account_id}/billingProfiles/"
        f"{invoice_section.billing_profile_id}/invoiceSections/"
        f"{invoice_section.invoice_section_id}"
    )
    role_definition_id = (
        "/providers/Microsoft.Billing/billingAccounts/"
        f"{invoice_section.billing_account_id}/billingRoleDefinitions/"
        f"{SUBSCRIPTION_CREATOR_BILLING_ROLE_DEFINITION_GUID}"
    )
    role_assignment_name = str(uuid.uuid4())

    request = BillingRoleAssignmentRequest(
        invoice_section_scope=invoice_section_scope,
        role_assignment_name=role_assignment_name,
        role_definition_id=role_definition_id,
        principal_id=principal_id,
    )

    logger.info(
        "vending.assign_subscription_creator_role: scope=%s "
        "role_assignment_name=%s principal_id=%s",
        invoice_section_scope,
        role_assignment_name,
        principal_id,
    )

    # TODO(live-call): Construct a real BillingRoleAssignmentClient
    # here (token_provider=DefaultAzureCredential-backed provider,
    # transport=httpx.AsyncClient) and issue the PUT call described in
    # clients.py's module docstring:
    #
    #     PUT {invoice_section_scope}/providers/Microsoft.Billing/
    #         billingRoleAssignments/{role_assignment_name}
    #     ?api-version={ARM_API_VERSION_BILLING_ROLE_ASSIGNMENT}
    #
    # For this scaffold we synth