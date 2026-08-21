from app.core.task_store import TaskRecord, InMemoryTaskStore


def test_task_store_round_trip():
    store = InMemoryTaskStore()
    record = TaskRecord(task_id="t1", status="running")
    store.save(record)
    assert store.get("t1") == record
