from app.api import analysis
from app.core.task_store import InMemoryTaskStore


def test_analysis_can_inject_task_store():
    store = InMemoryTaskStore()
    analysis.configure_task_store(store)
    assert analysis._task_store is store


def test_initialize_task_store_calls_setup_when_available(monkeypatch):
    class SetupStore:
        def __init__(self):
            self.setup_called = False

        def setup(self):
            self.setup_called = True

    store = SetupStore()
    monkeypatch.setattr(analysis, "_task_store", store)

    analysis.initialize_task_store()

    assert store.setup_called is True
