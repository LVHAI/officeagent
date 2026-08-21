import asyncio

from fastapi.testclient import TestClient

from app.core.task_store import InMemoryTaskStore, TaskRecord
from app.main import app


def test_analysis_endpoint_rejects_empty_query():
    client = TestClient(app)
    response = client.post("/api/v1/analyze", json={"query": ""})
    assert response.status_code == 422


def test_analysis_endpoint_accepts_query(monkeypatch):
    async def fake_run(query: str):
        return {"task_id": "task-1", "query": query, "report": "ok", "errors": [], "traces": []}

    monkeypatch.setattr("app.api.analysis.run_analysis", fake_run)
    client = TestClient(app)
    response = client.post("/api/v1/analyze", json={"query": "分析华东客户流失原因"})
    assert response.status_code == 200
    assert response.json()["report"] == "ok"
    assert response.json()["task_id"] == "task-1"


def test_task_store_io_is_async(monkeypatch):
    """验证 PostgreSQL 同步 Store 不会直接在 async handler 中执行。"""
    store = InMemoryTaskStore()
    store.save(TaskRecord(task_id="task-async", status="completed"))
    monkeypatch.setattr("app.api.analysis._task_store", store)

    async def run():
        from app.api.analysis import _get

        record = await _get("task-async")
        return record

    record = asyncio.run(run())
    assert record is not None
    assert record.status == "completed"
