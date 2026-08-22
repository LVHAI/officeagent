import pytest

from app.legal.clause_parser import parse_clause_key


@pytest.mark.parametrize(
    ("key", "law_name", "article_number", "article"),
    [
        ("中华人民共和国劳动合同法 第一条", "中华人民共和国劳动合同法", 1, "第一条"),
        ("中华人民共和国劳动合同法 第十条", "中华人民共和国劳动合同法", 10, "第十条"),
        ("中华人民共和国劳动法 第九十九条", "中华人民共和国劳动法", 99, "第九十九条"),
        ("中华人民共和国劳动法 第一百零一条", "中华人民共和国劳动法", 101, "第一百零一条"),
        ("中华人民共和国劳动法 第一百零七条", "中华人民共和国劳动法", 107, "第一百零七条"),
        ("中华人民共和国劳动法 第101条", "中华人民共和国劳动法", 101, "第101条"),
    ],
)
def test_parse_supported_clause_keys(key, law_name, article_number, article):
    result = parse_clause_key(key)

    assert result.law_name == law_name
    assert result.article_number == article_number
    assert result.article == article


def test_parse_rejects_key_without_article_suffix():
    with pytest.raises(ValueError, match="无效的政策条款 key"):
        parse_clause_key("中华人民共和国劳动法")


def test_parse_rejects_empty_key():
    with pytest.raises(ValueError, match="无效的政策条款 key"):
        parse_clause_key("")
