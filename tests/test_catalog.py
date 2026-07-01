from fastapi.testclient import TestClient

from blueprintandchill.main import app


def test_catalog_returns_options() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/catalog/subscription-options")

    assert response.status_code == 200
    payload = response.json()
    assert "options" in payload
    assert len(payload["options"]) >= 3
