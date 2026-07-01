from __future__ import annotations

from functools import lru_cache

from blueprintandchill.models.catalog import (
    FeatureOption,
    SubscriptionCatalogResponse,
    SubscriptionOption,
)


class CatalogService:
    def get_subscription_catalog(self) -> SubscriptionCatalogResponse:
        return SubscriptionCatalogResponse(
            options=[
                SubscriptionOption(
                    landing_zone="corp",
                    environments=["dev", "test", "prod"],
                    regions=["eastus", "centralus"],
                    features=[
                        FeatureOption(
                            key="hub_peering",
                            name="Hub connectivity",
                            description="Request peering to the regional connectivity hub.",
                            enabled_by_default=True,
                        ),
                        FeatureOption(
                            key="policy_baseline",
                            name="Policy baseline",
                            description="Apply the standard landing zone governance package.",
                            enabled_by_default=True,
                        ),
                    ],
                ),
                SubscriptionOption(
                    landing_zone="online",
                    environments=["dev", "test", "prod"],
                    regions=["eastus", "centralus"],
                    features=[
                        FeatureOption(
                            key="private_endpoints",
                            name="Private endpoints",
                            description="Flag workload for private connectivity review.",
                        ),
                        FeatureOption(
                            key="budget_guardrail",
                            name="Budget guardrail",
                            description="Attach budget policy/billing review in a later phase.",
                        ),
                    ],
                ),
                SubscriptionOption(
                    landing_zone="sandbox",
                    environments=["dev", "test"],
                    regions=["eastus", "centralus"],
                    features=[
                        FeatureOption(
                            key="sandbox_expiry",
                            name="Sandbox expiry policy",
                            description="Mark for future automated cleanup and expiry governance.",
                        )
                    ],
                ),
            ]
        )


@lru_cache(maxsize=1)
def get_catalog_service() -> CatalogService:
    return CatalogService()
