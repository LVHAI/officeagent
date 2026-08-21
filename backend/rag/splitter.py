"""
文档切片模块。

将长文档拆分为适合 Embedding 和 Retrieval 的 Chunk。
保留 metadata，保证后续 Source Trace 可追踪。
"""

from dataclasses import dataclass


@dataclass
class Chunk:
    content: str
    metadata: dict


class TextSplitter:
    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str):
        """按照字符长度切分文本。"""
        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size
            chunks.append(
                Chunk(
                    content=text[start:end],
                    metadata={"start": start, "end": end},
                )
            )

            # overlap 防止上下文边界信息丢失
            start = end - self.overlap

        return chunks
