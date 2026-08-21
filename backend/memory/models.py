"""
记忆系统数据模型

定义 Agent 短期记忆和长期记忆统一的数据结构。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class MemoryItem:
    """统一记忆对象。

    memory_type 用于区分：
    - short_term: 当前任务上下文
    - long_term: 长期用户或企业经验
    """

    id: str
    user_id: str
    content: str
    memory_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    expire_at: Optional[datetime] = None
