from app.core.task_store import InMemoryTaskStore, TaskRecord


def test_task_store_round_trip():
    store = InMemoryTaskStore()
    record = TaskRecord(task_id="t1", status="running")
    store.save(record)
    assert store.get("t1") == record


def test_task_store_unknown_task_returns_none():
    store = InMemoryTaskStore()
    assert store.get("missing") is None
