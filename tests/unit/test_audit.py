from app.core.audit import InMemoryAuditStore, make_audit_event


def test_audit_store_keeps_events_by_task():
    store = InMemoryAuditStore()
    store.append(make_audit_event("t1", "agent.completed", "supervisor", {"status": "ok"}))
    store.append(make_audit_event("t2", "agent.completed", "report", {"status": "ok"}))

    events = store.list("t1")

    assert len(events) == 1
    assert events[0].event_type == "agent.completed"
    assert events[0].actor == "supervisor"
