"""
企业知识文档加载抽象层。

后续可以扩展 PDF、Word、HTML 等 Loader。
"""

from dataclasses import dataclass


@dataclass
class Document:
    content: str
    metadata: dict


class BaseDocumentLoader:
    """所有文档加载器统一接口。"""

    def load(self, path: str) -> Document:
        raise NotImplementedError


class TextDocumentLoader(BaseDocumentLoader):
    """简单文本文件加载器。"""

    def load(self, path: str) -> Document:
        with open(path, "r", encoding="utf-8") as file:
            content = file.read()

        return Document(
            content=content,
            metadata={"path": path},
        )
