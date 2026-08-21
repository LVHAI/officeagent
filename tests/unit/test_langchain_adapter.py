from app.tools.langchain_adapter import _args_model


def test_args_model_converts_json_schema() -> None:
    model = _args_model(
        "Args",
        {
            "type": "object",
            "properties": {"region": {"type": "string"}, "limit": {"type": "integer"}},
            "required": ["region"],
        },
    )

    value = model(region="East China", limit=10)
    assert value.region == "East China"
    assert value.limit == 10
