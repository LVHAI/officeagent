from infra.mcp.mock_server import build_service_tools, validate_read_only_sql


def test_database_service_exposes_read_only_sql_tool():
    tools = build_service_tools("database")
    names = {tool.name for tool in tools}

    assert names == {"sql_query"}


def test_crm_service_does_not_expose_database_sql_tool():
    tools = build_service_tools("crm")
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
