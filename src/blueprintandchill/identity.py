"""Entra ID app registration + service principal provisioning scaffold.

This module defines the CONTRACT for provisioning the automation
identity Landmark's subscription-vending workflow needs: an Entra ID
app registration and its corresponding service principal.

Live Microsoft Graph calls are intentionally STUBBED in this PR. The
functions below return typed, deterministic placeholder data so the
rest of the vending pipeline (billing role assignment, subscription
alias creation) can be built, tested, and wired together end-to-end
before a real tenant credential exists.

Expected production flow (documented here, implemented later):

    1. create_app_registration()
       Calls Microsoft Graph `POST /applications` using a
       caller-supplied credential (azure-identity DefaultAzureCredential
       or a bootstrap admin credential passed in explicitly). Never a
       hardcoded client secret. Returns the new application's appId
       (client ID) and object id.

    2. create_service_principal_for_app()
       Calls Microsoft Graph `POST /servicePrincipals` with the appId
       from step 1. Captures the service principal's object id — this
       is the value later used for Azure RBAC / billing role
       assignments, NOT the application (client) id.

    3. create_service_principal()
       Orchestrates steps 1-2, assembles a single typed
       ServicePrincipalResult, and documents outstanding TODOs
       (billing role grant, secret storage in Key Vault, etc.) so
       downstream automation and reviewers know exactly what is still
       a placeholder.

Mr. Scorpio's rule of thumb applies: managed identity over secrets,
no plaintext credentials in logs or source control, everything
env-driven. This module performs no network I/O and requires no
FastAPI import.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class IdentityProvisioningError(Exception):
    """Raised when app registration or service principal provisioning fails.

    In stub mode this is only raised for obviously invalid input
    (e.g. a blank display name). Once live Graph calls are wired up,
    this should also wrap Graph SDK exceptions (auth failures, throttling,
    duplicate display names, etc.) so callers see one stable error type.
    """


class ServicePrincipalKind(str, Enum):
    """Coarse classification of what a provisioned service principal is for."""

    AUTOMATION = "automation"
    WORKLOAD = "workload"


class AppRegistrationRequest(BaseModel):
    """Input contract for provisioning an app registration + service principal.

    TODO(graph-integration): sign_in_audience and any required API
    permissions (e.g. Billing.ReadWrite.Enrollment or the MCA billing
    scope equivalent) must be finalized with Landmark's tenant admin
    before live calls are enabled.
    """

    display_name: str = Field(
        ...,
        description="Human-readable name for the app registration, e.g. 'bac-vending-automation-prod'.",
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional free-text description of what this identity is used for.",
    )
    kind: ServicePrincipalKind = Field(
        default=ServicePrincipalKind.AUTOMATION,
        description="Classification of this service principal's purpose.",
    )
    sign_in_audience: str = Field(
        default="AzureADMyOrg",
        description="Graph signInAudience value. TODO: confirm single-tenant vs multi-tenant with Landmark.",
    )
    requested_by: Optional[str] = Field(
        default=None,
        description="Identifier of the human or workflow that requested this provisioning, for audit purposes.",
    )


class ServicePrincipalResult(BaseModel):
    """Typed result of a (possibly stubbed) service principal provisioning call.

    This is the contract downstream modules (billing role assignment,
    subscription alias vending) are built against, regardless of
    whether the underlying Graph calls are live or stubbed.
    """

    application_id: str = Field(
        ...,
        description="The app registration's application (client) ID, also called appId.",
    )
    service_principal_object_id: str = Field(
        ...,
        description="The service principal's object ID. Used for Azure RBAC / billing role assignments.",
    )
    application_object_id: Optional[str] = Field(
        default=None,
        description="The app registration's own object ID (distinct from application_id/appId).",
    )
    display_name: str = Field(
        ...,
        description="Display name assigned to the app registration and service principal.",
    )
    tenant_id: Optional[str] = Field(
        default=None,
        description="Entra ID tenant GUID this identity was created in, if known at call time.",
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp this result was produced.",
    )
    is_stub: bool = Field(
        default=True,
        description="True while this result was produced by the stubbed provisioning path, not live Graph calls.",
    )
    notes: List[str] = Field(
        default_factory=list,
        description="Human-readable notes about how this result was produced.",
    )
    todo: List[str] = Field(
        default_factory=list,
        description="Outstanding TODOs required before this result can be considered production-live.",
    )


def _utc_now() -> datetime:
    """Return the current UTC timestamp, tz-aware."""
    return datetime.now(timezone.utc)


def _stub_guid(seed: str) -> str:
    """Produce a deterministic, GUID-shaped placeholder string.

    This is NOT a real GUID generator and NOT cryptographically
    meaningful. It exists so stub-mode calls are stable and
    reproducible in tests (same seed always yields the same fake
    identifier), and so nobody mistakes the output for a live tenant
    resource.
    """
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return "-".join(
        [
            digest[0:8],
            digest[8:12],
            digest[12:16],
            digest[16:20],
            digest[20:32],
        ]
    )


def create_app_registration(request: AppRegistrationRequest) -> Dict[str, str]:
    """Create an Entra ID app registration.

    STUB in this PR. Returns a dict shaped like the subset of a Graph
    `application` resource this module cares about: appId and id
    (the application object id).

    TODO(graph-integration): replace this body with a real call, e.g.:

        from msgraph import GraphServiceClient
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
        client = GraphServiceClient(credentials=credential)
        app = await client.applications.post(body=application_request_body)
        return {"appId": app.app_id, "id": app.id}

    The credential above must come from managed identity or a
    bootstrap admin flow — never a hardcoded client secret.
    """
    tenant_id = os.environ.get("BAC_AZURE_TENANT_ID")
    if not tenant_id:
        logger.warning(
            "BAC_AZURE_TENANT_ID is not set; create_app_registration is running "
            "in stub mode with no tenant context."
        )

    app_id = _stub_guid(f"app:{request.display_name}")
    object_id = _stub_guid(f"appobj:{request.display_name}")

    logger.info(
        "create_app_registration (stub) produced appId=%s for display_name=%s",
        app_id,
        request.display_name,
    )

    return {"appId": app_id, "id": object_id}


def create_service_principal_for_app(app_id: str, app_display_name: str) -> Dict[str, str]:
    """Create a service principal for an existing app registration.

    STUB in this PR. Returns a dict shaped like the subset of a Graph
    `servicePrincipal` resource this module cares about: id (the
    service principal object id, used for RBAC), appId, and
    displayName.

    TODO(graph-integration): replace this body with a real call, e.g.:

        sp_body = ServicePrincipal(app_id=app_id)
        sp = await client.service_principals.post(body=sp_body)
        return {"id": sp.id, "appId": sp.app_id, "displayName": sp.display_name}
    """
    sp_object_id = _stub_guid(f"sp:{app_id}")

    logger.info(
        "create_service_principal_for_app (stub) produced sp object id=%s for appId=%s",
        sp_object_id,
        app_id,
    )

    return {"id": sp_object_id, "appId": app_id, "displayName": app_display_name}


def create_service_principal(request: AppRegistrationRequest) -> ServicePrincipalResult:
    """Orchestrate app registration + service principal creation.

    This is the single entry point downstream vending code should
    call. It documents the expected end-to-end flow and, in this PR,
    performs that flow entirely in stub mode:

        1. Validate the request (non-empty display_name).
        2. create_app_registration(request) -> appId, application object id
        3. create_service_principal_for_app(appId, display_name) -> SP object id
        4. Assemble and return a typed ServicePrincipalResult with
           clear notes/todo entries describing what remains to be
           wired up for a live tenant.

    Raises:
        IdentityProvisioningError: if the request is invalid (e.g. a
            blank display_name). Once live Graph calls are enabled,
            Graph SDK exceptions should also be caught and re-raised
            as IdentityProvisioningError here.
    """
    if not request.display_name or not request.display_name.strip():
        raise IdentityProvisioningError(
            "display_name is required to create a service principal."
        )

    tenant_id = os.environ.get("BAC_AZURE_TENANT_ID")

    notes: List[str] = ["Running in STUB mode: no live Microsoft Graph calls were made."]
    todos: List[str] = [
        "TODO(graph-integration): call Microsoft Graph POST /applications via the "
        "msgraph SDK using a caller-supplied credential (DefaultAzureCredential or a "
        "bootstrap admin credential) -- never an embedded client secret.",
        "TODO(graph-integration): call Microsoft Graph POST /servicePrincipals with the "
        "appId from the application step, then capture the resulting object id -- that "
        "id (not the appId) is what gets used in Azure RBAC / billing role assignments.",
        "TODO(billing-role): the service_principal_object_id returned here must be "
        "granted the least-privilege billing role (e.g. an Azure subscription creator "
        "role) at the MCA invoice section scope by a dedicated billing-role module.",
        "TODO(secret-management): if this service principal ever needs a client secret "
        "or certificate credential, store it in Key Vault immediately upon creation and "
        "reference it via managed identity elsewhere -- never log or persist it in plaintext.",
    ]

    if not tenant_id:
        notes.append(
            "BAC_AZURE_TENANT_ID is not set; tenant_id on the result will be None "
            "until tenant onboarding completes."
        )

    app_registration = create_app_registration(request)
    application_id = app_registration["appId"]
    application_object_id = app_registration["id"]

    service_principal = create_service_principal_for_app(application_id, request.display_name)
    sp_object_id = service_principal["id"]

    result = ServicePrincipalResult(
        application_id=application_id,
        service_principal_object_id=sp_object_id,
        application_object_id=application_object_id,
        display_name=request.display_name,
        tenant_id=tenant_id,
        created_at=_utc_now(),
        is_stub=True,
        notes=notes,
        todo=todos,
    )

    logger.info(
        "create_service_principal (stub) completed for display_name=%s appId=%s spObjectId=%s",
        request.display_name,
        application_id,
        sp_object_id,
    )

    return result


__all__ = [
    "IdentityProvisioningError",
    "ServicePrincipalKind",
    "AppRegistrationRequest",
    "ServicePrincipalResult",
    "create_app_registration",
    "create_service_principal_for_app",
    "create_service_principal",
]