from app.api import analysis
from app.core.task_store import InMemoryTaskStore


def test_analysis_can_inject_task_store():
    store = InMemoryTaskStore()
    analysis.configure_task_store(store)
    assert analysis._task_store is store
