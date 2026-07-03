"""Sample shopping catalog data for the BlueprintAndChill demo web app.

This module is a pure data slice: typed Pydantic models plus a
hand-authored seed catalog. It intentionally has NO FastAPI routes and
NO orchestration wiring, so shopping pages can be built and rendered
before the subscription-vending submit flow is connected in a later
task.

Everything returned here is clearly DEMO / SAMPLE data aligned with
the README's hub-and-spoke Landing Zone architecture narrative:

  - Landing zone (hub) components: the shared connectivity/identity/
    management resources that live in the central hub subscription
    (hub virtual network, Azure Firewall, Azure Bastion, private DNS
    zones, centralized Log Analytics, and the CAF-aligned Azure
    Policy initiative baseline).
  - Spoke options: the per-subscription networking building blocks
    that get peered back to the hub when a new spoke subscription is
    vended (spoke VNet + hub peering, baseline NSGs, forced-tunnel
    route table to the hub firewall).
  - Workload/environment choices: mirrors the Workload enum already
    defined in blueprintandchill.models.vending (Production / DevTest)
    so the shopping selection can later be threaded straight into a
    ProvisioningRequest without translation.
  - Regions: the Azure regions Landmark's landing zones are expected
    to be deployed into, each carrying the short Azure region code
    used by ARM/Bicep deployments.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field

from blueprintandchill.models.vending import Workload


class CatalogCategory(StrEnum):
    """High-level grouping for a catalog item in the shopping UI."""

    LANDING_ZONE_COMPONENT = "LandingZoneComponent"
    SPOKE_OPTION = "SpokeOption"
    WORKLOAD_ENVIRONMENT = "WorkloadEnvironment"
    REGION = "Region"


class CatalogItem(BaseModel):
    """A single selectable item in the demo shopping catalog.

    This is intentionally decoupled from the vending domain models in
    blueprintandchill.models.vending -- a route/orchestration layer
    added in a later task is responsible for translating a set of
    selected CatalogItem ids into a real ProvisioningRequest.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(..., min_length=1)
    category: CatalogCategory
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    icon: str = Field(default="\U0001F4E6")  # package emoji fallback
    default_selected: bool = False
    requires_hub: bool = False
    tags: list[str] = Field(default_factory=list)
    workloads: list[Workload] = Field(
        default_factory=list,
        description=(
            "Workload environments this item is relevant/available for. "
            "Empty means the item applies to all workloads."
        ),
    )


class CatalogRegion(BaseModel):
    """A region option aligned with an Azure region code."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    azure_region: str = Field(..., min_length=1)
    geography: str = Field(..., min_length=1)
    is_default: bool = False


class Catalog(BaseModel):
    """The full demo shopping catalog rendered by the shopping page.

    Sections map directly onto the README architecture narrative:
    hub landing-zone components, spoke networking options, workload
    environment choices, and region-aligned deployment targets.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    landing_zone_components: list[CatalogItem]
    spoke_options: list[CatalogItem]
    workload_environments: list[CatalogItem]
    regions: list[CatalogRegion]
    is_sample_data: bool = True
    source_note: str = (
        "Demo/sample catalog data for BlueprintAndChill. Not sourced from "
        "live Azure billing or management group APIs -- see TODOs in "
        "orchestration modules for where live wiring will replace this."
    )


def _landing_zone_components() -> list[CatalogItem]:
    return [
        CatalogItem(
            id="lz-hub-vnet",
            category=CatalogCategory.LANDING_ZONE_COMPONENT,
            name="Hub Virtual Network",
            description=(
                "Central hub VNet for the region -- shared connectivity "
                "point that every spoke subscription peers back to."
            ),
            icon="\U0001F310",
            default_selected=True,
            requires_hub=True,
            tags=["networking", "caf-connectivity"],
        ),
        CatalogItem(
            id="lz-azure-firewall",
            category=CatalogCategory.LANDING_ZONE_COMPONENT,
            name="Azure Firewall",
            description=(
                "Centralized network security appliance in the hub, used "
                "for forced-tunneling egress from spoke VNets."
            ),
            icon="\U0001F525",
            default_selected=True,
            requires_hub=True,
            tags=["security", "networking"],
        ),
        CatalogItem(
            id="lz-azure-bastion",
            category=CatalogCategory.LANDING_ZONE_COMPONENT,
            name="Azure Bastion",
            description=(
                "Managed jump-box service in the hub for secure RDP/SSH "
                "to spoke workloads without public IPs."
            ),
            icon="\U0001F6E1\uFE0F",
            default_selected=False,
            requires_hub=True,
            tags=["security", "remote-access"],
        ),
        CatalogItem(
            id="lz-private-dns-zones",
            category=CatalogCategory.LANDING_ZONE_COMPONENT,
            name="Private DNS Zones",
            description=(
                "Shared private DNS zones for Private Link-enabled PaaS "
                "services, linked to both the hub and each spoke VNet."
            ),
            icon="\U0001F4C7",
            default_selected=True,
            requires_hub=True,
            tags=["dns", "networking"],
        ),
        CatalogItem(
            id="lz-log-analytics",
            category=CatalogCategory.LANDING_ZONE_COMPONENT,
            name="Centralized Log Analytics Workspace",
            description=(
                "Shared Log Analytics workspace for platform and spoke "
                "diagnostics, aligned with the CAF management baseline."
            ),
            icon="\U0001F4CA",
            default_selected=True,
            requires_hub=True,
            tags=["monitoring", "management"],
        ),
        CatalogItem(
            id="lz-policy-baseline",
            category=CatalogCategory.LANDING_ZONE_COMPONENT,
            name="Azure Policy Baseline Initiative",
            description=(
                "CAF-aligned Azure Policy initiative assigned at the "
                "management group level (tagging, allowed regions, "
                "diagnostic settings, security baselines)."
            ),
            icon="\U0001F4DC",
            default_selected=True,
            requires_hub=True,
            tags=["governance", "policy"],
        ),
    ]


def _spoke_options() -> list[CatalogItem]:
    return [
        CatalogItem(
            id="spoke-vnet-peering",
            category=CatalogCategory.SPOKE_OPTION,
            name="Spoke VNet with Hub Peering",
            description=(
                "New spoke virtual network, automatically peered to the "
                "regional hub VNet on subscription vend."
            ),
            icon="\U0001F517",
            default_selected=True,
            tags=["networking"],
        ),
        CatalogItem(
            id="spoke-baseline-nsgs",
            category=CatalogCategory.SPOKE_OPTION,
            name="Baseline Network Security Groups",
            description=(
                "Deny-by-default NSGs applied to every subnet created in "
                "the spoke, following the CAF security baseline."
            ),
            icon="\U0001F6A7",
            default_selected=True,
            tags=["security", "networking"],
        ),
        CatalogItem(
            id="spoke-forced-tunnel-route",
            category=CatalogCategory.SPOKE_OPTION,
            name="Forced-Tunnel Route Table",
            description=(
                "Route table sending all spoke egress through the hub "
                "Azure Firewall instead of directly to the internet."
            ),
            icon="\U0001F6E3\uFE0F",
            default_selected=True,
            tags=["security", "networking"],
        ),
        CatalogItem(
            id="spoke-key-vault",
            category=CatalogCategory.SPOKE_OPTION,
            name="Spoke Key Vault",
            description=(
                "Per-subscription Key Vault for workload secrets, with "
                "Private Link into the spoke VNet."
            ),
            icon="\U0001F510",
            default_selected=False,
            tags=["security", "secrets"],
        ),
        CatalogItem(
            id="spoke-diagnostic-settings",
            category=CatalogCategory.SPOKE_OPTION,
            name="Diagnostic Settings to Hub Workspace",
            description=(
                "Automatically wires resource diagnostic logs in the "
                "spoke to the centralized hub Log Analytics workspace."
            ),
            icon="\U0001F4C9",
            default_selected=True,
            tags=["monitoring"],
        ),
    ]


def _workload_environments() -> list[CatalogItem]:
    return [
        CatalogItem(
            id="workload-production",
            category=CatalogCategory.WORKLOAD_ENVIRONMENT,
            name="Production",
            description=(
                "Production workload environment -- stricter policy "
                "baseline, forced-tunnel egress required, no exceptions."
            ),
            icon="\U0001F7E2",
            default_selected=True,
            tags=["environment"],
            workloads=[Workload.PRODUCTION],
        ),
        CatalogItem(
            id="workload-devtest",
            category=CatalogCategory.WORKLOAD_ENVIRONMENT,
            name="Development / Test",
            description=(
                "DevTest workload environment -- relaxed cost controls, "
                "same baseline security policies still apply."
            ),
            icon="\U0001F7E1",
            default_selected=False,
            tags=["environment"],
            workloads=[Workload.DEVELOPMENT],
        ),
    ]


def _regions() -> list[CatalogRegion]:
    return [
        CatalogRegion(
            id="eastus2",
            display_name="East US 2",
            azure_region="eastus2",
            geography="United States",
            is_default=True,
        ),
        CatalogRegion(
            id="westeurope",
            display_name="West Europe",
            azure_region="westeurope",
            geography="Europe",
            is_default=False,
        ),
        CatalogRegion(
            id="southcentralus",
            display_name="South Central US",
            azure_region="southcentralus",
            geography="United States",
            is_default=False,
        ),
    ]


@lru_cache(maxsize=1)
def get_demo_catalog() -> Catalog:
    """Return the (cached) demo shopping catalog.

    This is sample/seed data only. A later orchestration-wiring task
    is responsible for reading selected catalog item ids from a
    submitted form and translating them into the real
    blueprintandchill.models.vending request models -- this module
    does not perform that translation and has no route handlers.
    """
    return Catalog(
        landing_zone_components=_landing_zone_components(),
        spoke_options=_spoke_options(),
        workload_environments=_workload_environments(),
        regions=_regions(),
    )


__all__ = [
    "Catalog",
    "CatalogCategory",
    "CatalogItem",
    "CatalogRegion",
    "get_demo_catalog",
]