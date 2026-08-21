from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_reports_service_status():
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert body["service"] == "officeagent"
    assert "dependencies" in body
