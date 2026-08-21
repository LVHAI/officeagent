"""
Source Trace 来源追踪模块

用于记录 Agent 输出依据的数据来源。
支持文档、工具调用、Web 数据等来源类型。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict


@dataclass
class SourceTrace:
    """统一来源信息结构。"""

    source_type: str
    source_id: str
    metadata: Dict = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )


class SourceTraceManager:
    """管理 Agent 执行过程中的来源记录。"""

    def __init__(self):
        self.sources = []

    def add(self, trace: SourceTrace):
        self.sources.append(trace)

    def list_sources(self):
        return self.sources
