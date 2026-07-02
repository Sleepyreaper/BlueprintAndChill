from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class InvoiceSectionEventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(..., min_length=1)
    event_type: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    billing_account_id: str = Field(..., min_length=1)
    billing_profile_id: str = Field(..., min_length=1)
    invoice_section_id: str = Field(..., min_length=1)
    invoice_section_name: str = Field(..., min_length=1)
    billing_scope: str = Field(..., min_length=1)
    customer_name: str | None = None
    initiated_by: str | None = None
    correlation_id: str | None = None


__all__ = ["InvoiceSectionEventPayload"]