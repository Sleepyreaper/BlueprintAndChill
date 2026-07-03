"""Typed domain models for the subscription-vending workflow.

These models are FastAPI-independent, side-effect free, and safe to
import without any Azure SDK, network access, or environment
validation happening at import time. They describe the exact
workflow entities Landmark's automation needs:

  1. Invoice section identifiers/events (the MCA trigger)
  2. Service principal metadata for the automation identity
  3. Billing role assignment request/result payloads
  4. Subscription alias (vending) request/response
  5. A top-level provision workflow result tying it all together

Every model uses pydantic BaseModel for validation, serialization,
and easy reuse in FastAPI request/response schemas in later tasks.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ProvisioningState(str, Enum):
    """Lifecycle states shared across vending workflow entities."""

    NOT_STARTED = "NotStarted"
    PENDING = "Pending"
    IN_PROGRESS = "InProgress"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    ROLLED_BACK = "RolledBack"


class WorkloadType(str, Enum):
    """Coarse workload classification used to pick spoke defaults."""

    SANDBOX = "sandbox"
    DEV_TEST = "dev-test"
    PRODUCTION = "production"
    SHARED_SERVICES = "shared-services"


class InvoiceSectionIdentifier(BaseModel):
    """Reference to an MCA invoice section, the billing scope used to
    vend a new subscription.

    TODO(tenant-onboarding): billing_account_id and billing_profile_id
    are tenant-specific and must be supplied per-environment; they are
    intentionally left optional here so this model can be constructed
    in tests without real Landmark billing data.
    """

    billing_account_id: Optional[str] = Field(
        default=None,
        description="MCA Billing Account ID. TODO: tenant-specific, set at onboarding.",
    )
    billing_profile_id: Optional[str] = Field(
        default=None,
        description="MCA Billing Profile ID. TODO: tenant-specific, set at onboarding.",
    )
    invoice_section_id: str = Field(
        ...,
        description="MCA Invoice Section ID this event/request refers to.",
    )

    def billing_scope(self) -> str:
        """Build the ARM billing scope string for this invoice section.

        Returns a placeholder-safe scope string even if account/profile
        IDs are not yet populated, so callers can still assemble a
        request object during local testing.
        """
        account = self.billing_account_id or "{TODO-billing-account-id}"
        profile = self.billing_profile_id or "{TODO-billing-profile-id}"
        return (
            f"/providers/Microsoft.Billing/billingAccounts/{account}"
            f"/billingProfiles/{profile}"
            f"/invoiceSections/{self.invoice_section_id}"
        )


class InvoiceSectionEvent(BaseModel):
    """Payload shape for the 'invoice section created' trigger event.

    TODO(events-task): The live Event Grid handler in a later task will
    deserialize the raw Event Grid envelope into this model before
    kicking off the provisioning workflow. No network or Event Grid SDK
    calls happen here.
    """

    event_id: str = Field(..., description="Event Grid event ID.")
    event_type: str = Field(
        default="Microsoft.Billing.InvoiceSectionCreated",
        description="Event Grid event type string.",
    )
    event_time: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp the event was raised.",
    )
    invoice_section: InvoiceSectionIdentifier = Field(
        ...,
        description="The invoice section that was created, triggering vending.",
    )
    requested_by: Optional[str] = Field(
        default=None,
        description="Object ID or UPN of whoever created the invoice section, if known.",
    )
    raw_subject: Optional[str] = Field(
        default=None,
        description="Original Event Grid 'subject' field, kept for traceability.",
    )


class ServicePrincipalRequest(BaseModel):
    """Request to create the automation service principal used to vend
    and manage a new subscription.

    No network calls happen here; this is purely the typed request
    shape consumed by a later Azure SDK-backed implementation.
    """

    display_name: str = Field(
        ...,
        description="Display name for the service principal, e.g. 'sp-landmark-vend-dev'.",
    )
    workload: WorkloadType = Field(
        default=WorkloadType.SANDBOX,
        description="Workload classification driving naming and default role scope.",
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable purpose of this service principal.",
    )
    requested_by: Optional[str] = Field(
        default=None,
        description="Who or what triggered this request (user UPN or 'invoice-section-trigger').",
    )


class ServicePrincipalMetadata(BaseModel):
    """Resulting metadata for a created (or stubbed) service principal.

    TODO(core-clients-task): app_id/object_id/tenant_id are populated
    by the live Microsoft Graph / Azure SDK call in a later task. Here
    they default to None so this model can represent a not-yet-created
    principal during planning/dry-run.
    """

    display_name: str = Field(..., description="Display name of the service principal.")
    app_id: Optional[str] = Field(
        default=None,
        description="Application (client) ID. TODO: populated after live creation.",
    )
    object_id: Optional[str] = Field(
        default=None,
        description="Service principal object ID. TODO: populated after live creation.",
    )
    tenant_id: Optional[str] = Field(
        default=None,
        description="Tenant ID the service principal belongs to.",
    )
    provisioning_state: ProvisioningState = Field(
        default=ProvisioningState.NOT_STARTED,
        description="Current lifecycle state of the service principal creation.",
    )
    created_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp the service principal was created, if known.",
    )


class BillingRoleAssignmentRequest(BaseModel):
    """Request to grant a billing role to a principal on a billing scope.

    This is the payload used to give the automation service principal
    permission to create subscriptions against an invoice section.
    """

    principal_object_id: str = Field(
        ...,
        description="Object ID of the service principal (or user/group) receiving the role.",
    )
    billing_scope: str = Field(
        ...,
        description="ARM billing scope, e.g. invoice section resource ID from InvoiceSectionIdentifier.billing_scope().",
    )
    role_definition_name: str = Field(
        default="Azure Subscription Creator",
        description="Built-in MCA billing role name to assign.",
    )


class BillingRoleAssignmentResult(BaseModel):
    """Outcome of a billing role assignment attempt.

    TODO(core-clients-task): role_assignment_id is populated by the
    live azure-mgmt-billing call in a later task.
    """

    principal_object_id: str = Field(..., description="Object ID of the principal that was assigned the role.")
    billing_scope: str = Field(..., description="Billing scope the role was assigned on.")
    role_definition_name: str = Field(..., description="Role that was assigned.")
    role_assignment_id: Optional[str] = Field(
        default=None,
        description="Resulting role assignment resource ID. TODO: populated after live call.",
    )
    provisioning_state: ProvisioningState = Field(
        default=ProvisioningState.NOT_STARTED,
        description="Current lifecycle state of the role assignment.",
    )


class SubscriptionAliasRequest(BaseModel):
    """Request payload matching the Azure Subscription Alias API shape,
    used to vend (create) a new subscription linked to the landing zone.

    Mirrors the fields of Microsoft.Subscription/aliases so this model
    can later be passed almost directly to azure-mgmt-subscription.
    """

    alias: str = Field(
        ...,
        description="Unique alias name for the subscription creation request, e.g. 'landmark-dev-001'.",
    )
    display_name: str = Field(
        ...,
        description="Human-friendly subscription display name shown in the Azure portal.",
    )
    workload: WorkloadType = Field(
        default=WorkloadType.SANDBOX,
        description="Workload type; maps to Azure's 'Production' or 'DevTest' workload field.",
    )
    billing_scope: str = Field(
        ...,
        description="Invoice section billing scope to bill this subscription against.",
    )
    management_group_id: Optional[str] = Field(
        default=None,
        description=(
            "Target management group (spoke landing zone) this subscription "
            "should land under. TODO: tenant-specific, set at onboarding."
        ),
    )
    owner_object_ids: List[str] = Field(
        default_factory=list,
        description="Object IDs (users, groups, or service principals) granted Owner on creation.",
    )
    tags: Dict[str, str] = Field(
        default_factory=dict,
        description="Tags applied to the new subscription (environment, project, owner, costCenter).",
    )


class SubscriptionAliasResponse(BaseModel):
    """Result of a subscription alias (vending) request.

    TODO(core-clients-task): subscription_id and tenant_id are
    populated by the live azure-mgmt-subscription call in a later
    task. Defaults are None so this model can represent an in-flight
    or dry-run request.
    """

    alias: str = Field(..., description="Alias name the request was submitted under.")
    subscription_id: Optional[str] = Field(
        default=None,
        description="Resulting subscription GUID. TODO: populated after live call.",
    )
    tenant_id: Optional[str] = Field(
        default=None,
        description="Tenant the subscription was created in.",
    )
    management_group_id: Optional[str] = Field(
        default=None,
        description="Management group the subscription was placed under, if known.",
    )
    provisioning_state: ProvisioningState = Field(
        default=ProvisioningState.NOT_STARTED,
        description="Current lifecycle state of the subscription alias request.",
    )
    accepted_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp the request was accepted by Azure, if known.",
    )


class ProvisionWorkflowResult(BaseModel):
    """Top-level result tying together every step of the automated
    subscription-vending workflow triggered by an invoice section event.

    This is the single object a caller (Event Grid function, CLI, or
    the shopping web app) inspects to know what happened end-to-end.
    """

    workflow_id: str = Field(
        ...,
        description="Unique correlation ID for this end-to-end provisioning run.",
    )
    triggered_by: Optional[InvoiceSectionEvent] = Field(
        default=None,
        description="The invoice-section-created event that triggered this workflow, if applicable.",
    )
    service_principal: Optional[ServicePrincipalMetadata] = Field(
        default=None,
        description="Result of the service principal creation step.",
    )
    billing_role_assignment: Optional[BillingRoleAssignmentResult] = Field(
        default=None,
        description="Result of the billing role assignment step.",
    )
    subscription_alias: Optional[SubscriptionAliasResponse] = Field(
        default=None,
        description="Result of the subscription alias (vending) step.",
    )
    overall_state: ProvisioningState = Field(
        default=ProvisioningState.NOT_STARTED,
        description="Aggregate provisioning state across all workflow steps.",
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp the workflow began.",
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp the workflow finished (success or failure).",
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Human-readable error messages accumulated during the workflow, if any.",
    )

    def is_terminal(self) -> bool:
        """Return True if the workflow has reached a terminal state."""
        return