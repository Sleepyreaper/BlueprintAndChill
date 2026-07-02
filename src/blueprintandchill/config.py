from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
 tenant_id: str
 billing_account_name: str
 billing_profile_name: str
 invoice_section_name: str
 default_location: str


def load_settings() -> Settings:
 return Settings(tenant_id=os.environ.get("BAC_TENANT_ID", ""), billing_account_name=os.environ.get("BAC_BILLING_ACCOUNT", ""), billing_profile_name=os.environ.get("BAC_BILLING_PROFILE", ""), invoice_section_name=os.environ.get("BAC_INVOICE_SECTION", ""), default_location=os.environ.get("BAC_DEFAULT_LOCATION", "eastus"))