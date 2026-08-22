from __future__ import annotations

import json
from typing import Any

from fastapi.encoders import jsonable_encoder


def dumps_json(value: Any) -> str:
    """Serialize Agent/tool results into JSON-safe data before storing in JSONB."""
    return json.dumps(jsonable_encoder(value))
