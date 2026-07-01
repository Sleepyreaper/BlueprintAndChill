from __future__ import annotations

from pydantic import BaseModel, Field


class FeatureOption(BaseModel):
    key: str
    name: str
    description: str
    enabled_by_default: bool = False


class SubscriptionOption(BaseModel):
    landing_zone: str
    environments: list[str]
    regions: list[str]
    features: list[FeatureOption] = Field(default_factory=list)


class SubscriptionCatalogResponse(BaseModel):
    options: list[SubscriptionOption]
