from app.rag.splitter import semantic_chunks, semantic_nodes, split_sentences


def test_split_sentences_supports_markdown_and_chinese_punctuation():
    text = "# 标题\n\n第一段。第二句！\n\n- 第三句。"
    assert split_sentences(text) == ["标题", "第一段。", "第二句！", "第三句。"]


def test_semantic_chunks_uses_embedding_similarity_boundary():
    units = ["苹果是水果。", "香蕉也是水果。", "数据库需要索引。"]
    vectors = {
        "苹果是水果。": [1.0, 0.0],
        "香蕉也是水果。": [0.99, 0.01],
        "数据库需要索引。": [0.0, 1.0],
    }

    result = semantic_chunks(units, threshold=0.8, embedder=lambda values: [vectors[v] for v in values])

    assert result == ["苹果是水果。 香蕉也是水果。", "数据库需要索引。"]


def test_semantic_chunks_falls_back_to_max_chars_without_embedder():
    units = ["第一段", "第二段", "第三段"]
    assert semantic_chunks(units, max_chars=7) == ["第一段", "第二段", "第三段"]


def test_semantic_nodes_sets_metadata():
    result = semantic_nodes("# 标题\n\n第一段。第二段。", "example.md", max_chars=100)
    assert result
    assert all(chunk.metadata["doc_type"] == "semantic" for chunk in result)
    assert all(chunk.metadata["document"] == "example.md" for chunk in result)
