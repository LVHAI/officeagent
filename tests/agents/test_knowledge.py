import json

import pytest

from app.agents.knowledge import create_knowledge_pipeline, knowledge_search
from app.agents.rag import KnowledgeChunk


def test_knowledge_pipeline_returns_citation_aware_context():
    pipeline = create_knowledge_pipeline(
        [
            KnowledgeChunk("c1", "退款政策为七天", "policy.pdf", page=4, section="退款"),
            KnowledgeChunk("c2", "发货政策为三天", "shipping.pdf", page=2, section="发货"),
        ]
    )

    result = pipeline.search("退款 政策")

    assert result.chunks
    assert "[c1] policy.pdf p.4 / 退款" in result.context
    assert "退款政策为七天" in result.context


@pytest.mark.asyncio
async def test_knowledge_search_uses_rag_pipeline_without_mcp(monkeypatch):
    class FakeResult:
        def __init__(self):
            self.chunk = type(
                "Chunk",
                (),
                {
                    "id": "c1",
                    "content": "水煮鱼需要先将鱼片腌制，再下锅煮熟。",
                    "metadata": {"document": "水煮鱼.md"},
                    "source": type(
                        "Source",
                        (),
                        {
                            "document": "水煮鱼.md",
                            "page": None,
                            "section": "做法",
                            "article": None,
                            "chunk_id": "c1",
                        },
                    )(),
                },
            )()
            self.score = 0.91
            self.route = "vector"

    class FakePipeline:
        async def retrieve_async(self, query, *, limit):
            assert query == "水煮鱼怎么做"
            assert limit == 5
            return [FakeResult()]

        @staticmethod
        def build_context(results):
            return "[1] 水煮鱼.md | 做法 | chunk=c1\n水煮鱼需要先将鱼片腌制，再下锅煮熟。"

    import app.agents.knowledge as knowledge_module

    knowledge_module._runtime_retrieval_pipeline.cache_clear()
    monkeypatch.setattr(knowledge_module, "_runtime_retrieval_pipeline", lambda: FakePipeline())

    result = json.loads(await knowledge_search.ainvoke({"query": "水煮鱼怎么做", "limit": 5}))

    assert result["results"] == 1
    assert "水煮鱼需要先将鱼片腌制" in result["context"]
    assert result["sources"][0]["document"] == "水煮鱼.md"
    assert result["sources"][0]["route"] == "vector"
