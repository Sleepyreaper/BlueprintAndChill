"""Service principal creation slice of the subscription-vending workflow.

Scope of this module (and only this module):
    - Register a Microsoft Entra ID (Azure AD) application.
    - Create the associated service principal for that application.
    - Return a typed result carrying the identifiers the *next* step
      (billing role assignment, see the not-yet-built
      ``billing_roles`` module) needs to grant the SP the correct
      billing scope role.

Explicitly OUT of scope here:
    - Assigning any billing role to the created principal.
    - Creating/aliasing the Azure subscription itself.
    - Persisting credentials/secrets anywhere other than a Key Vault
      *reference name* (never the secret value).

Design notes:
    - No tenant ID, application name, or any other tenant-specific
      value is hardcoded. Everything tenant-specific is sourced from
      ``blueprintandchill.config.Settings`` (env-driven) or passed in
      explicitly by the caller via ``ServicePrincipalCreationRequest``.
    - Microsoft Graph is accessed through a small ``GraphClient``
      ``Protocol`` so ``create_service_principal`` can be exercised in
      unit tests with an in-memory stub - no real network/tenant
      access required. The default, production-facing implementation
      (``LiveMicrosoftGraphClient``) is provided but its actual Graph
      REST calls are marked ``TODO`` and raise ``NotImplementedError``
      until wired to a concrete Graph SDK/HTTP call and reviewed for
      the exact Graph API permissions (``Application.ReadWrite.All``,
      admin-consent flow, etc.) Landmark's tenant requires.
    - Credential/secret material is never returned inline. Only a
      *reference name* (e.g. a Key Vault secret name the caller is
      expected to populate out-of-band, or via a federated identity
      credential in a follow-on task) is carried on the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from blueprintandchill.config import Settings, load_settings

try:
    # azure-identity is an expected dependency of this package. The
    # import is guarded so this module still parses / is unit-testable
    # in environments where the dependency has not been installed yet
    # (e.g. a bare lint/docs pass), matching the pattern established
    # in blueprintandchill.azure.http_client.
    from azure.core.credentials import TokenCredential
    from azure.identity import DefaultAzureCredential
except ImportError:  # pragma: no cover - exercised only when SDK missing
    TokenCredential = Any  # type: ignore[assignment,misc]
    DefaultAzureCredential = None  # type: ignore[assignment,misc]


DEFAULT_GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
DEFAULT_GRAPH_SCOPE = "https://graph.microsoft.com/.default"


class ServicePrincipalCreationError(Exception):
    """Raised when application or service-principal creation fails."""

    def __init__(self, message: str, graph_response: Any = None) -> None:
        super().__init__(message)
        self.graph_response = graph_response


# --------------------------------------------------------------------------
# Typed request / result contracts
# --------------------------------------------------------------------------


class ServicePrincipalCreationRequest(BaseModel):
    """Input to :func:`create_service_principal`.

    ``display_name`` should encode enough context (e.g. customer +
    invoice-section correlation id) to be traceable back to the
    triggering event, but this module does not itself impose a naming
    scheme - that policy belongs to the orchestrator/caller.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    display_name: str = Field(..., min_length=1)
    tenant_id: str | None = Field(
        default=None,
        description=(
            "Tenant to create the app/SP in. If omitted, resolved from "
            "Settings.tenant_id (env-driven, never hardcoded)."
        ),
    )
    tags: list[str] = Field(default_factory=list)
    idempotency_key: str | None = Field(
        default=None,
        description="Correlation id (e.g. invoice section event id) for idempotent retries.",
    )


class ServicePrincipalCreationResult(BaseModel):
    """Typed output consumed by the downstream billing-role-assignment step.

    ``service_principal_object_id`` (aka the SP's ``objectId``/
    ``principalId``) is the identifier billing role assignment needs
    for the ``principal_object_id`` field of
    ``blueprintandchill.models.vending.BillingRoleAssignmentRequest``.
    ``app_id``/``client_id`` are the same underlying Entra app
    (client) id, both exposed for caller convenience since downstream
    Azure APIs are inconsistent about which name they expect.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    app_id: str = Field(..., min_length=1, description="Entra application (client) id.")
    client_id: str = Field(..., min_length=1, description="Alias of app_id; kept explicit for callers.")
    application_object_id: str = Field(..., min_length=1, description="Object id of the app registration itself.")
    service_principal_object_id: str = Field(
        ..., min_length=1, description="Object id of the service principal; used as the principal id downstream."
    )
    display_name: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    client_secret_name: str | None = Field(
        default=None,
        description=(
            "Name of the Key Vault secret reference holding the SP credential, if a "
            "client-secret credential (rather than a federated identity credential) was "
            "provisioned. Never contains the secret value itself."
        ),
    )
    created: bool = True
    message: str | None = None


# --------------------------------------------------------------------------
# Microsoft Graph client boundary (dependency-injected)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ApplicationRegistration:
    """Minimal shape returned from creating an Entra application object."""

    app_id: str
    object_id: str
    display_name: str


@dataclass(frozen=True)
class ServicePrincipalObject:
    """Minimal shape returned from creating a service principal for an app."""

    object_id: str
    app_id: str
    display_name: str


class GraphClient(Protocol):
    """Boundary between this module and Microsoft Graph.

    Kept intentionally small (two verbs) so tests can supply an
    in-memory stub without pulling in any Graph SDK or network stack.
    """

    def create_application(self, display_name: str, tags: list[str]) -> ApplicationRegistration:
        """Register a new Entra ID application and return its identifiers."""
        ...

    def create_service_principal_for_app(self, app_id: str) -> ServicePrincipalObject:
        """Create the service principal object for a previously-registered app."""
        ...


class LiveMicrosoftGraphClient:
    """Production-facing Graph client using the configured auth path.

    Auth path: resolves a token credential via ``azure-identity``'s
    ``DefaultAzureCredential`` (same credential-chain philosophy as
    ``blueprintandchill.azure.http_client``), scoped to
    ``https://graph.microsoft.com/.default``. No tenant id, client id,
    or secret is hardcoded anywhere in this class - the credential
    chain and ``tenant_id`` are both externally configured.

    The actual Graph REST calls (``POST /applications``,
    ``POST /servicePrincipals``) are deliberately left as ``TODO`` /
    ``NotImplementedError`` until:
        1. The exact Graph app permissions and admin-consent flow for
           Landmark's tenant are finalized (Hank + Troy sign-off).
        2. A decision is made between an httpx-based raw call (like
           ``blueprintandchill.azure.http_client.AzureManagementClient``)
           vs. the ``msgraph-sdk`` package.
    Until then, callers should inject a stub ``GraphClient`` (see
    ``create_service_principal``'s ``graph_client`` parameter) for
    testing, and this class exists to make the production wiring point
    explicit and discoverable.
    """

    def __init__(
        self,
        tenant_id: str,
        credential: "TokenCredential | None" = None,
        graph_base_url: str = DEFAULT_GRAPH_BASE_URL,
    ) -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required to construct LiveMicrosoftGraphClient")
        self._tenant_id = tenant_id
        self._graph_base_url = graph_base_url
        self._credential = credential or self._default_credential()

    @staticmethod
    def _default_credential() -> "TokenCredential | None":
        if DefaultAzureCredential is None:  # pragma: no cover - SDK not installed
            return None
        # TODO(gil): confirm whether the vending automation should use
        # DefaultAzureCredential (managed identity in prod, dev creds
        # locally) or a dedicated user-assigned managed identity scoped
        # tighter than the default chain. Mr. Scorpio prefers managed
        # identity over any static credential wherever possible.
        return DefaultAzureCredential()

    def create_application(self, display_name: str, tags: list[str]) -> ApplicationRegistration:
        # TODO(gil): LIVE GRAPH CALL NOT YET WIRED.
        # Real implementation should:
        #   1. Acquire a token via self._credential.get_token(DEFAULT_GRAPH_SCOPE)
        #   2. POST {self._graph_base_url}/applications with body
        #      {"displayName": display_name, "tags": tags}
        #   3. Parse the response for "appId" and "id" (object id)
        #   4. Raise ServicePrincipalCreationError on non-2xx with the
        #      response body attached for diagnostics.
        raise NotImplementedError(
            "LiveMicrosoftGraphClient.create_application is a stub. "
            "Wire the POST /applications Microsoft Graph call before using in production."
        )

    def create_service_principal_for_app(self, app_id: str) -> ServicePrincipalObject:
        # TODO(gil): LIVE GRAPH CALL NOT YET WIRED.
        # Real implementation should:
        #   1. Acquire a token via self._credential.get_token(DEFAULT_GRAPH_SCOPE)
        #   2. POST {self._graph_base_url}/servicePrincipals with body
        #      {"appId": app_id}
        #   3. Parse the response for "id" (SP object id) and "appId"
        #   4. Raise ServicePrincipalCreationError on non-2xx with the
        #      response body attached for diagnostics.
        raise NotImplementedError(
            "LiveMicrosoftGraphClient.create_service_principal_for_app is a stub. "
            "Wire the POST /servicePrincipals Microsoft Graph call before using in production."
        )


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------


def create_service_principal(
    request: ServicePrincipalCreationRequest,
    graph_client: GraphClient | None = None,
    settings: Settings | None = None,
) -> ServicePrincipalCreationResult:
    """Create an Entra application + service principal for the vending workflow.

    This is the ONLY entry point of this module. It:
        1. Resolves the tenant id from ``request.tenant_id`` or, if
           omitted, from env-driven ``Settings`` (never hardcoded).
        2. Registers the application via the injected ``GraphClient``.
        3. Creates the service principal for that application.
        4. Returns a fully-typed ``ServicePrincipalCreationResult``
           carrying the identifiers the billing-role-assignment step
           needs next.

    Dependency injection:
        ``graph_client`` defaults to a ``LiveMicrosoftGraphClient``
        built from resolved settings, but any object satisfying the
        ``GraphClient`` protocol can be injected - which is how this
        function is unit-tested without network/tenant access:

            class _FakeGraphClient:
                def create_application(self, display_name, tags):
                    return ApplicationRegistration(
                        app_id="00000000-0000-0000-0000-000000000001",
                        object_id="00000000-0000-0000-0000-000000000002",
                        display_name=display_name,
                    )

                def create_service_principal_for_app(self, app_id):
                    return ServicePrincipalObject(
                        object_id="00000000-0000-0000-0000-000000000003",
                        app_id=app_id,
                        display_name="stub-sp",
                    )

            result = create_service_principal(
                ServicePrincipalCreationRequest(display_name="landmark-spoke-001"),
                graph_client=_FakeGraphClient(),
                settings=Settings(
                    tenant_id="00000000-0000-0000-0000-0000000000ff",
                    billing_account_name="",
                    billing_profile_name="",
                    invoice_section_name="",
                    default_location="eastus",
                ),
            )

    Raises:
        ValueError: if no tenant id can be resolved from the request
            or settings.
        ServicePrincipalCreationError: if the underlying Graph client
            raises during application or service-principal creation.
    """
    resolved_settings = settings or load_settings()
    tenant_id = request.tenant_id or resolved_settings.tenant_id
    if not tenant_id:
        raise ValueError(
            "No tenant_id available: pass ServicePrincipalCreationRequest.tenant_id "
            "or set BAC_TENANT_ID in the environment."
        )

    client = graph_client or LiveMicrosoftGraphClient(tenant_id=tenant_id)

    try:
        application = client.create_application(
            display_name=request.display_name,
            tags=list(request.tags),
        )
    except NotImplementedError:
        # Re-raise as-is so callers/tests get a clear, actionable signal
        # that the live Graph path isn't wired yet, rather than a
        # generic ServicePrincipalCreationError swallowing that detail.
        raise
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise ServicePrincipalCreationError(
            f"Failed to create application '{request.display_name}': {exc}"
        ) from exc

    try:
        service_principal = client.create_service_principal_for_app(application.app_id)
    except NotImplementedError:
        raise
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise ServicePrincipalCreationError(
            f"Failed to create service principal for app '{application.app_id}': {exc}"
        ) from exc

    # TODO(gil): Once federated identity credential support is added
    # (preferred over client secrets per Mr. Scorpio's "managed
    # identity / no static secrets" standard), populate
    # client_secret_name only when a client-secret fallback credential
    # was actually provisioned; otherwise leave it None.
    return ServicePrincipalCreationResult(
        app_id=application.app_id,
        client_id=application.app_id,
        application_object_id=application.object_id,
        service_principal_object_id=service_principal.object_id,
        display_name=service_principal.display_name,
        tenant_id=tenant_id,
        client_secret_name=None,
        created=True,
        message=None,
    )


__all__ = [
    "ApplicationRegistration",
    "ServicePrincipalObject",
    "GraphClient",
    "LiveMicrosoftGraphClient",
    "ServicePrincipalCreationError",
    "ServicePrincipalCreationRequest",
    "ServicePrincipalCreationResult",
    "create_service_principal",
]