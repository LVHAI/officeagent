from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from app.core.json_utils import dumps_json


def test_dumps_json_serializes_datetime_and_nested_agent_values():
    payload = {
        "created_at": datetime(2026, 8, 22, 12, 30, tzinfo=timezone.utc),
        "amount": Decimal("12.50"),
        "task_id": UUID("12345678-1234-5678-1234-567812345678"),
        "items": [{"updated_at": datetime(2026, 8, 22, tzinfo=timezone.utc)}],
    }

    result = dumps_json(payload)

    assert '"created_at": "2026-08-22T12:30:00+00:00"' in result
    assert '"amount": 12.5' in result
    assert '"task_id": "12345678-1234-5678-1234-567812345678"' in result
    assert '"updated_at": "2026-08-22T00:00:00+00:00"' in result
