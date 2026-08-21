"""
Tool Registry 单元测试。
验证注册、查询、删除以及异常场景。
"""

import pytest

from backend.tools.registry import (
    DuplicateToolError,
    ToolNotFoundError,
    ToolRegistry,
)
from backend.tools.schema import ToolSchema


def create_tool():
    return ToolSchema(
        name="crm_search",
        description="Search CRM customer data",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )


def test_register_tool():
    registry = ToolRegistry()
    registry.register(create_tool())

    assert registry.get("crm_search").name == "crm_search"


def test_duplicate_tool():
    registry = ToolRegistry()
    registry.register(create_tool())

    with pytest.raises(DuplicateToolError):
        registry.register(create_tool())


def test_remove_tool():
    registry = ToolRegistry()
    registry.register(create_tool())

    registry.remove("crm_search")

    with pytest.raises(ToolNotFoundError):
        registry.get("crm_search")
