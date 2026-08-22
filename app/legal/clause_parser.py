from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedClauseKey:
    law_name: str
    article: str
    article_number: int


_CLAUSE_KEY_RE = re.compile(
    r"^(?P<law_name>.+?)\s+第(?P<number>[0-9零〇一二三四五六七八九十百千万亿]+)条$"
)
_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_SMALL_UNITS = {"十": 10, "百": 100, "千": 1000}
_LARGE_UNITS = {"万": 10_000, "亿": 100_000_000}


def _chinese_number_to_int(value: str) -> int:
    if value.isdigit():
        return int(value)

    total = 0
    section = 0
    number = 0
    for char in value:
        if char in _DIGITS:
            number = _DIGITS[char]
            continue
        if char in _SMALL_UNITS:
            unit = _SMALL_UNITS[char]
            section += (number or 1) * unit
            number = 0
            continue
        if char in _LARGE_UNITS:
            unit = _LARGE_UNITS[char]
            section = (section + number) * unit
            total += section
            section = 0
            number = 0
            continue
        raise ValueError(f"invalid Chinese article number: {value!r}")

    return total + section + number


def parse_clause_key(key: str) -> ParsedClauseKey:
    """Parse legal clause keys such as ``中华人民共和国劳动法 第一百零一条``.

    Both Chinese and Arabic article numbers are accepted. The original article
    label is retained so downstream metadata can preserve the source text.
    """
    if not isinstance(key, str):
        raise ValueError(f"无效的政策条款 key: {key!r}，格式应为“法律名称 第X条”")

    match = _CLAUSE_KEY_RE.fullmatch(key.strip())
    if not match:
        raise ValueError(f"无效的政策条款 key: {key!r}，格式应为“法律名称 第X条”")

    law_name = match.group("law_name").strip()
    number_text = match.group("number")
    article_number = _chinese_number_to_int(number_text)
    if article_number <= 0:
        raise ValueError(f"无效的政策条款 key: {key!r}，格式应为“法律名称 第X条”")

    article = f"第{number_text}条"
    return ParsedClauseKey(
        law_name=law_name,
        article=article,
        article_number=article_number,
    )
