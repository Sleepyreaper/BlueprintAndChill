"""Environment-driven configuration for BlueprintAndChill.

This module centralizes all runtime settings for the Landing Zone +
subscription-vending accelerator. Settings are read from environment
variables (optionally via a local .env file for developer machines)
using pydantic-settings. NOTHING here is hardcoded: no tenant IDs, no
subscription IDs, no secrets, no client secrets.

In production, values are expected to come from:
  - App Service / Azure Functions application settings, backed by
    Key Vault references (@Microsoft.KeyVault(...)), or
  - Managed Identity + Key Vault SDK calls performed by the caller
    before settings are constructed (out of scope for this module).

Mr. Scorpio's rule of thumb applies: managed identity over secrets,
private endpoints by default, tags on everything. This module does
not enforce those things directly (it's just config), but it gives
every downstream module the values it needs to enforce them.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AzureIdentitySettings(BaseSettings):
    """Settings related to Entra ID / tenant identity.

    TODO(tenant-onboarding): Landmark must supply their own tenant_id,
    hub_subscription_id, and management_group_root_id at onboarding
    time. These are read from environment variables and are never
    defaulted to a real value in source control.
    """

    model_config = SettingsConfigDict(
        env_prefix="BAC_AZURE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    tenant_id: Optional[str] = Field(
        default=None,
        description="Entra ID tenant GUID for Landmark. TODO: set via BAC_AZURE_TENANT_ID.",
    )
    environment: str = Field(
        default="AzureCloud",
        description="Azure cloud environment name (AzureCloud, AzureUSGovernment, etc.).",
    )
    hub_subscription_id: Optional[str] = Field(
        default=None,
        description=(
            "Subscription ID of the central Landing Zone hub. "
            "TODO: set via BAC_AZURE_HUB_SUBSCRIPTION_ID once the hub exists."
        ),
    )
    management_group_root_id: Optional[str] = Field(
        default=None,
        description=(
            "Root management group ID for the Landmark ALZ hierarchy "
            "(e.g. the 'landmark' MG under Tenant Root Group). "
            "TODO: set via BAC_AZURE_MANAGEMENT_GROUP_ROOT_ID."
        ),
    )
    default_location: str = Field(
        default="eastus2",
        description="Default Azure region for new spoke subscriptions and resources.",
    )


class BillingSettings(BaseSettings):
    """Settings related to Microsoft Customer Agreement (MCA) billing.

    These values scope where subscription-vending is allowed to create
    new subscriptions and which billing role gets granted to the
    automation service principal.
    """

    model_config = SettingsConfigDict(
        env_prefix="BAC_BILLING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    account_id: Optional[str] = Field(
        default=None,
        description="MCA Billing Account ID. TODO: set via BAC_BILLING_ACCOUNT_ID.",
    )
    profile_id: Optional[str] = Field(
        default=None,
        description="MCA Billing Profile ID. TODO: set via BAC_BILLING_PROFILE_ID.",
    )
    default_invoice_section_id: Optional[str] = Field(
        default=None,
        description=(
            "Default Invoice Section ID used when a subscription-vending "
            "request does not specify one explicitly. TODO: set via "
            "BAC_BILLING_DEFAULT_INVOICE_SECTION_ID, or supply per-request."
        ),
    )
    billing_role_definition_name: str = Field(
        default="Azure Subscription Creator",
        description=(
            "Built-in MCA billing role granted to the automation service "
            "principal so it can create subscriptions against the invoice "
            "section (billing scope)."
        ),
    )


class EventGridSettings(BaseSettings):
    """Settings for the invoice-section-created trigger path.

    TODO(events-task): This mirrors the shape expected by the Event Grid
    subscription created in a later task, so the trigger function and
    this config agree on names without a network call happening here.
    """

    model_config = SettingsConfigDict(
        env_prefix="BAC_EVENTGRID_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    topic_endpoint: Optional[str] = Field(
        default=None,
        description="Event Grid custom topic endpoint. TODO: set via BAC_EVENTGRID_TOPIC_ENDPOINT.",
    )
    topic_key_secret_name: Optional[str] = Field(
        default=None,
        description=(
            "Key Vault secret name holding the Event Grid topic key. "
            "Never store the key itself in settings or source control."
        ),
    )
    subscription_created_event_type: str = Field(
        default="Microsoft.Billing.InvoiceSectionCreated",
        description="Event type this accelerator reacts to for auto-vending.",
    )


class AppSettings(BaseSettings):
    """Top-level application settings for the demo shopping web app.

    Covers the Azure Web App (Python, Entra ID login) that lets Landmark
    'shop' for what gets deployed into the landing zone and each new
    spoke subscription.
    """

    model_config = SettingsConfigDict(
        env_prefix="BAC_APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    name: str = Field(
        default="blueprintandchill",
        description="Application name used for tagging and resource naming.",
    )
    environment: str = Field(
        default="dev",
        description="Deployment environment label: dev, staging, or prod.",
    )
    owner_tag: str = Field(
        default="landmark-platform-team",
        description="Value used for the 'owner' tag on provisioned resources.",
    )
    cost_center_tag: Optional[str] = Field(
        default=None,
        description="Value used for the 'costCenter' tag. TODO: set via BAC_APP_COST_CENTER_TAG.",
    )
    key_vault_uri: Optional[str] = Field(
        default=None,
        description="Key Vault URI used for secret references at runtime. TODO: set via BAC_APP_KEY_VAULT_URI.",
    )
    allow_live_azure_calls: bool = Field(
        default=False,
        description=(
            "Feature flag. When False, all Azure SDK client construction "
            "in later tasks must short-circuit into stub/mock behavior. "
            "Keeps this framework safe to import and test with zero "
            "network access."
        ),
    )


class Settings(BaseSettings):
    """Aggregate settings object combining every settings group.

    This is the single object the rest of the application should import
    and use: `from blueprintandchill.config import get_settings`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    identity: AzureIdentitySettings = Field(default_factory=AzureIdentitySettings)
    billing: BillingSettings = Field(default_factory=BillingSettings)
    events: EventGridSettings = Field(default_factory=EventGridSettings)
    app: AppSettings = Field(default_factory=AppSettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached, process-wide Settings instance.

    Cached via lru_cache so environment variables are read once per
    process. Tests that need fresh settings should call
    `get_settings.cache_clear()` before constructing a new instance.
    """
    return Settings()