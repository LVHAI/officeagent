from pathlib import Path

import pytest

from app.agents.skills import Skill, SkillRegistry, load_skill_metadata


def test_skill_registry_only_authorizes_declared_tools():
    registry = SkillRegistry(
        [
            Skill("crm", "customer analysis", ("customer.query",), "crm"),
            Skill("sales", "sales analysis", ("sales.query",), "db"),
        ]
    )
    assert registry.canonical_names() == ("crm", "sales")
    assert registry.authorized_tool_names() == ("customer.query", "sales.query")


def test_skill_duplicate_and_unknown_are_rejected():
    registry = SkillRegistry([Skill("crm", "customer")])
    with pytest.raises(ValueError, match="Duplicate skill name"):
        registry.register(Skill("crm", "duplicate"))
    with pytest.raises(KeyError, match="Unknown skill"):
        registry.get("missing")


def test_skill_body_is_lazy_until_selected(tmp_path: Path):
    skill_file = tmp_path / "crm" / "SKILL.md"
    skill_file.parent.mkdir()
    skill_file.write_text(
        "---\nname: crm\ndescription: customer analysis\nmcp_server: crm\nmcp_tools:\n  - customer.query\n---\n\n# CRM\nDetailed instructions\n",
        encoding="utf-8",
    )
    registry = load_skill_metadata(tmp_path)
    skill = registry.get("crm")
    assert skill.description == "customer analysis"
    assert skill.tool_names == ("customer.query",)
    assert skill.load_instructions() == "# CRM\nDetailed instructions"
