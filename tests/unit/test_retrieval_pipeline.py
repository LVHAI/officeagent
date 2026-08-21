from app.rag.models import DocumentChunk, Source
from app.rag.pipeline import RetrievalPipeline
from app.tools.skills import Skill, SkillRegistry


def test_retrieval_pipeline_preserves_source_context():
    chunks = [
        DocumentChunk(
            id="c1",
            content="华东客户流失率为 12%",
            source=Source(document="sales.pdf", page=3, section="客户分析", chunk_id="c1"),
        )
    ]
    pipeline = RetrievalPipeline(chunks)
    results = pipeline.retrieve("华东客户流失率")
    context = pipeline.build_context(results)
    assert "sales.pdf" in context
    assert "page=3" in context
    assert "华东客户流失率" in context


def test_retrieval_pipeline_applies_metadata_filter():
    chunks = [
        DocumentChunk(id="c1", content="华东客户流失率", metadata={"department": "sales"}),
        DocumentChunk(id="c2", content="华东客户流失率", metadata={"department": "finance"}),
    ]
    pipeline = RetrievalPipeline(chunks)

    results = pipeline.retrieve("华东客户流失率", metadata_filter={"department": "sales"})

    assert [result.chunk.id for result in results] == ["c1"]


def test_skill_registry_filters_discovered_tools():
    class FakeClient:
        async def list_tools(self):
            return [
                {"name": "customer_query", "description": "query", "input_schema": {}, "server": "crm"},
                {"name": "delete_customer", "description": "delete", "input_schema": {}, "server": "crm"},
            ]

    registry = SkillRegistry({"crm": FakeClient()})
    registry.register(Skill("customer_analysis", "客户分析", "crm", ("customer_query",)))

    import asyncio

    tools = asyncio.run(registry.discover_tools("customer_analysis"))
    assert [tool["name"] for tool in tools] == ["customer_query"]
