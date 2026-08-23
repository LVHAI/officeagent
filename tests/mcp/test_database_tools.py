import logging

import pytest
from infra.mcp import mock_server
from infra.mcp.mock_server import build_service_tools, validate_read_only_sql
from mcp.server.fastmcp import FastMCP


def test_database_service_exposes_read_only_sql_tool():
    server = FastMCP("database-test")
    tools = build_service_tools("database", server)
    names = {tool.name for tool in tools}

    assert names == {"sql_query"}


def test_crm_service_does_not_expose_database_sql_tool():
    server = FastMCP("crm-test")
    tools = build_service_tools("crm", server)
    names = {tool.name for tool in tools}

    assert "sql_query" not in names
    assert "customer_query" in names


def test_sql_query_rejects_write_statements():
    validate_read_only_sql("SELECT * FROM customers")

    for statement in (
        "INSERT INTO customers VALUES (1)",
        "UPDATE customers SET name = 'x'",
        "DELETE FROM customers",
        "DROP TABLE customers",
        "ALTER TABLE customers ADD COLUMN x text",
    ):
        try:
            validate_read_only_sql(statement)
        except ValueError:
            continue
        raise AssertionError(f"write SQL was accepted: {statement}")


@pytest.mark.asyncio
async def test_sql_query_logs_executed_sql(monkeypatch, caplog):
    class FakeCursor:
        description = []

        def execute(self, sql, params=None):
            self.last_sql = sql
            self.last_params = params

        def fetchmany(self, _limit):
            return []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(mock_server, "_database_connection", lambda: FakeConnection())

    with caplog.at_level(logging.INFO, logger="app.sql"):
        result = await mock_server._sql_query("SELECT * FROM customers LIMIT 10")

    assert result["row_count"] == 0
    assert "sql.execute.start" in caplog.text
    assert "sql.execute.completed" in caplog.text
    assert "SELECT * FROM customers LIMIT 10" in caplog.text
    assert "row_count=0" in caplog.text


@pytest.mark.asyncio
async def test_sql_query_logs_failed_sql(monkeypatch, caplog):
    class FakeCursor:
        description = []

        def execute(self, sql, params=None):
            if sql.startswith("SELECT"):
                raise RuntimeError("database unavailable")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(mock_server, "_database_connection", lambda: FakeConnection())

    with caplog.at_level(logging.ERROR, logger="app.sql"):
        with pytest.raises(RuntimeError, match="database unavailable"):
            await mock_server._sql_query("SELECT * FROM customers")

    assert "sql.execute.failed" in caplog.text
    assert "SELECT * FROM customers" in caplog.text
    assert "database unavailable" in caplog.text
