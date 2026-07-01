from blueprintandchill.vending.subscription_alias import (
 SubscriptionAliasRequest,
 SubscriptionAliasService,
)


class FakeHttpClient:
 def __init__(self) -> None:
 self.last_put_url = None
 self.last_put_body = None

 def put(self, url: str, json: dict, headers: dict | None = None) -> dict:
 self.last_put_url = url
 self.last_put_body = json
 return {"properties": {"provisioningState": "Accepted"}}

 def get(self, url: str, headers: dict | None = None) -> dict:
 return {"properties": {"provisioningState": "Succeeded", "subscriptionId": "sub-123"}}


def test_create_or_get_uses_exact_alias_api_contract() -> None:
 client = FakeHttpClient()
 service = SubscriptionAliasService(client, "https://management.azure.com")

 request = SubscriptionAliasRequest(
 alias_name="landmark-eastus-prod",
 display_name="Landmark East US Production",
 workload="Production",
 billing_scope="/providers/Microsoft.Billing/billingAccounts/ba/billingProfiles/bp/invoiceSections/is",
 )

 service.create_or_get(request)

 assert client.last_put_url == (
 "https://management.azure.com/providers/Microsoft.Subscription/aliases/"
 "landmark-eastus-prod?api-version=2021-10-01"
 )
 assert client.last_put_body == {
 "properties": {
 "displayName": "Landmark East US Production",
 "workload": "Production",
 "billingScope": "/providers/Microsoft.Billing/billingAccounts/ba/billingProfiles/bp/invoiceSections/is",
 }
 }