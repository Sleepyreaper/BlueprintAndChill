from pathlib import Path

from blueprintandchill.auth.entra import EntraUser
from blueprintandchill.models.subscription_request import SubscriptionRequestCreate
from blueprintandchill.services.request_store import RequestStore
from blueprintandchill.services.vending_service import VendingService


def test_vending_service_persists_request(tmp_path: Path) -> None:
    store = RequestStore(tmp_path)
    service = VendingService(store)
    user = EntraUser(
        subject="demo-user",
        display_name="Demo User",
        email="demo@example.invalid",
        roles=["requester"],
        claims={},
    )

    payload = SubscriptionRequestCreate(
        business_area="corp",
        workload_name="payments-api",
        environment="dev",
        region="eastus",
        owner_email="owner@example.com",
        features=["hub_peering"],
    )

    response = service.submit_request(payload=payload, submitted_by=user)
    stored_items = service.list_requests()

    assert response.request.orchestration.status == "PENDING_IMPLEMENTATION"
    assert len(stored_items) == 1
    assert stored_items[0].payload.workload_name == "payments-api"
