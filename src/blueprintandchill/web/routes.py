"""Shopping cart routes for the BlueprintAndChill demo web app.

Self-contained router: GET /catalog, POST /order (JSON), and
GET /order/{order_id}/result (HTML receipt page). This module does
NOT import the app factory in app.py -- it builds its own small
Jinja2Templates instance so it can be dropped into create_app()
independently, per the "self-contained" requirement for this task.

TODO(vending): POST /order currently calls a local stub instead of
blueprintandchill.vending.orchestrator.provision_subscription because
that function requires real graph_client / billing_client /
subscription_client collaborators (Entra ID app registration, MCA
billing account, and Azure subscription API credentials) that are not
yet wired up in this framework PR. Swap _stub_provision_subscription
for the real orchestrator call once those clients exist.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["shopping"])

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

_SAMPLE_CATALOG = [
    {"id": "lz-hub-network", "name": "Hub Virtual Network", "category": "LandingZoneComponent", "price": "included"},
    {"id": "lz-firewall", "name": "Azure Firewall", "category": "LandingZoneComponent", "price": "included"},
    {"id": "spoke-vnet", "name": "Spoke Virtual Network + Peering", "category": "SpokeOption", "price": "included"},
    {"id": "spoke-nsg-baseline", "name": "Baseline NSGs", "category": "SpokeOption", "price": "included"},
    {"id": "workload-devtest", "name": "DevTest Workload", "category": "WorkloadEnvironment", "price": "included"},
    {"id": "workload-production", "name": "Production Workload", "category": "WorkloadEnvironment", "price": "included"},
]

_REQUIRED_ORDER_FIELDS = ("subscription_name", "workload", "region")


def _stub_provision_subscription(order: dict) -> dict:
    """Stand-in for blueprintandchill.vending.orchestrator.provision_subscription.

    TODO(vending): replace this body with a real call to
    provision_subscription(graph_client=..., billing_client=...,
    subscription_client=..., request=...) once live Azure clients are
    available (Entra ID app registration + MCA billing account +
    subscription API credentials). For now it returns a deterministic
    fake result so the end-to-end submit-to-receipt flow is
    demonstrable as a working skeleton.
    """
    return {
        "order_id": str(uuid.uuid4()),
        "subscription_name": order["subscription_name"],
        "workload": order["workload"],
        "region": order["region"],
        "status": "simulated",
    }


@router.get("/catalog")
async def get_catalog() -> list[dict]:
    """Return the hardcoded sample shopping catalog."""
    return _SAMPLE_CATALOG


@router.post("/order")
async def submit_order(request: Request) -> dict:
    """Accept a raw dict order body, validate required fields, and
    hand it to the (stubbed) vending orchestrator.
    """
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="order body must be a JSON object")

    missing = [field for field in _REQUIRED_ORDER_FIELDS if not body.get(field)]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing required fields: {missing}")

    result = _stub_provision_subscription(body)
    return {"status": "accepted", "order": body, "result": result}


@router.get("/order/{order_id}/result", response_class=HTMLResponse)
async def order_result(request: Request, order_id: str) -> HTMLResponse:
    """Render a receipt page for a previously submitted order.

    TODO(vending): once orders are persisted (Cosmos DB or similar),
    look up the real ProvisionSubscriptionResult by order_id instead
    of rendering this placeholder context.
    """
    context = {
        "request": request,
        "page_title": "Order Result",
        "order_id": order_id,
        "status": "simulated",
    }
    return _templates.TemplateResponse("result.html", context)