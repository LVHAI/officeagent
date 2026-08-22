from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from typing import Callable, Sequence

from app.rag.embedding import EmbeddingService
from app.rag.loader import DocumentLoader, LoadedDocument
from app.rag.milvus import MilvusRepository
from app.rag.models import DocumentChunk
from app.rag.parent_child import build_parent_child_from_markdown
from app.rag.splitter import policy_nodes, semantic_nodes

logger = logging.getLogger(__name__)
BATCH_SIZE = 32


def _chunks_for_document(
    document: LoadedDocument,
    semantic_embedder: Callable[[Sequence[str]], Sequence[Sequence[float]]] | None = None,
) -> list[DocumentChunk]:
    name = document.path.name
    if document.doc_type == "policy":
        return policy_nodes(document.content, name)
    if document.doc_type == "parent_child":
        parsed = build_parent_child_from_markdown(name, document.content)
        return [parsed.parent, *parsed.children]
    if document.doc_type == "semantic":
        return semantic_nodes(name and document.content or document.content, name, embedder=semantic_embedder)
    if document.doc_type == "faq":
        # FAQ 暂时沿用语义切分，保持 ingestion 可用；后续可替换为独立 FAQ parser。
        return semantic_nodes(document.content, name, embedder=semantic_embedder)
    raise ValueError(f"unsupported chunking strategy: {document.doc_type}")


async def ingest_corpus(
    corpus_root: str | Path = "data",
    *,
    collection: str = "officeagent_chunks",
    batch_size: int = BATCH_SIZE,
) -> dict[str, int]:
    """全量重建 data/ 对应的 Milvus collection。"""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    loader = DocumentLoader()
    documents = loader.load_corpus(corpus_root)
    if not documents:
        raise ValueError(f"no supported documents found under {Path(corpus_root).resolve()}")

    logger.info("rag.ingest.start root=%s documents=%d collection=%s", corpus_root, len(documents), collection)
    embedding_service = EmbeddingService()
    vector_store = MilvusRepository(collection=collection)

    all_chunks: list[DocumentChunk] = []
    for document in documents:
        logger.info("rag.ingest.parse document=%s strategy=%s", document.path, document.doc_type)
        chunks = _chunks_for_document(document)
        all_chunks.extend(chunks)
        logger.info("rag.ingest.parsed document=%s chunks=%d", document.path, len(chunks))

    if not all_chunks:
        raise ValueError("no chunks generated from corpus")

    # 先生成第一批向量以确定维度，再清空并重建 collection。
    first_batch = all_chunks[:batch_size]
    first_vectors = await embedding_service.embed_documents([chunk.content for chunk in first_batch])
    if not first_vectors or not first_vectors[0]:
        raise ValueError("embedding service returned empty vectors")
    dimension = len(first_vectors[0])
    if any(len(vector) != dimension for vector in first_vectors):
        raise ValueError("embedding service returned inconsistent vector dimensions")

    logger.info("rag.ingest.reset_collection collection=%s dimension=%d", collection, dimension)
    vector_store.reset_collection(dimension)

    vector_store.insert(first_batch, first_vectors)
    embedded = len(first_batch)
    stored = len(first_batch)

    for start in range(batch_size, len(all_chunks), batch_size):
        batch = all_chunks[start : start + batch_size]
        logger.info("rag.ingest.embedding batch_start=%d batch_size=%d", start, len(batch))
        vectors = await embedding_service.embed_documents([chunk.content for chunk in batch])
        if len(vectors) != len(batch) or any(len(vector) != dimension for vector in vectors):
            raise ValueError(f"embedding dimension/count mismatch at batch start {start}")
        vector_store.insert(batch, vectors)
        embedded += len(batch)
        stored += len(batch)

    logger.info(
        "rag.ingest.completed documents=%d chunks=%d embedded=%d stored=%d collection=%s",
        len(documents), len(all_chunks), embedded, stored, collection,
    )
    return {"documents": len(documents), "chunks": len(all_chunks), "embedded": embedded, "stored": stored}


def main() -> None:
    parser = argparse.ArgumentParser(description="将 data/ 全量解析、Embedding 并重建 Milvus collection")
    parser.add_argument("--root", default="data", help="RAG 数据目录，默认 data")
    parser.add_argument("--collection", default="officeagent_chunks", help="Milvus collection 名称")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Embedding/写入批大小")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    result = asyncio.run(ingest_corpus(args.root, collection=args.collection, batch_size=args.batch_size))
    print(
        "RAG ingestion completed: "
        f"documents={result['documents']} chunks={result['chunks']} "
        f"embedded={result['embedded']} stored={result['stored']} collection={args.collection}"
    )


if __name__ == "__main__":
    main()
