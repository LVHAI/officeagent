from fastapi.testclient import TestClient

from app.main import app


def test_analysis_endpoint_rejects_empty_query():
    client = TestClient(app)
    response = client.post("/api/v1/analyze", json={"query": ""})
    assert response.status_code == 422


def test_analysis_endpoint_accepts_query(monkeypatch):
    async def fake_run(query: str):
        return {"query": query, "report": "ok", "errors": []}

    monkeypatch.setattr("app.api.analysis.run_analysis", fake_run)
    client = TestClient(app)
    response = client.post("/api/v1/analyze", json={"query": "分析华东客户流失原因"})
    assert response.status_code == 200
    assert response.json()["report"] == "ok"
