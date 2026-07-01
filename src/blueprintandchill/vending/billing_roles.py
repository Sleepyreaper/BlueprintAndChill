from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4
from typing import Protocol


SUBSCRIPTION_CREATOR_ROLE_GUID = "a0bcee42-bf30-4d1b-926a-48d21664ef71"


@dataclass(frozen=True)
class InvoiceSectionRef:
 billing_account_id: str
 billing_profile_id: str
 invoice_section_id: str

 @property
 def scope(self) -> str:
 return (
 "/providers/Microsoft.Billing"
 f"/billingAccounts/{self.billing_account_id}"
 f"/billingProfiles/{self.billing_profile_id}"
 f"/invoiceSections/{self.invoice_section_id}"
 )


class HttpClient(Protocol):
 def put(self, url: str, json: dict, headers: dict | None = None) -> dict:...


class BillingRoleAssignmentService:
 API_VERSION = "2024-04-01"

 def __init__(self, http_client: HttpClient, arm_api_base: str) -> None:
 self._http = http_client
 self._arm_api_base = arm_api_base.rstrip("/")

 def assign_subscription_creator(
 self,
 principal_id: str,
 invoice_section: InvoiceSectionRef,
 assignment_guid: str | None = None,
 ) -> dict:
 if not principal_id:
 raise ValueError("principal_id is required")

 scope = invoice_section.scope
 role_definition_id = (
 f"{scope}/billingRoleDefinitions/{SUBSCRIPTION_CREATOR_ROLE_GUID}"
 )
 assignment_id = assignment_guid or str(uuid4())
 url = (
 f"{self._arm_api_base}{scope}/billingRoleAssignments/{assignment_id}"
 f"?api-version={self.API_VERSION}"
 )
 body = {
 "properties": {
 "principalId": principal_id,
 "roleDefinitionId": role_definition_id,
 }
 }
 return self._http.put(url, json=body)