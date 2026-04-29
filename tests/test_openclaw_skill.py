from pathlib import Path


def test_openclaw_autoresearch_skill_exists_and_limits_commands() -> None:
    skill = Path("openclaw/skills/autoresearch/SKILL.md")

    text = skill.read_text(encoding="utf-8")

    assert "name: autoresearch" in text
    assert "litagent job create" in text
    assert "litagent job run-next" in text
    assert "litagent job status" in text
    assert "不允许 OpenClaw 自由执行 shell" in text
    assert "`SKILL.md` 本身只是技能说明" in text
    assert "coding-agent" in text
    assert "litagent library-status --json" in text
    assert "QQ bot" in text


def test_openclaw_integration_doc_requires_host_verification() -> None:
    doc = Path("docs/openclaw_integration.md")

    text = doc.read_text(encoding="utf-8")

    assert "openclaw health" in text
    assert "openclaw config validate" in text
    assert "openclaw/skills/autoresearch/SKILL.md" in text
    assert "不能从容器内确认" in text
    assert "不要把 token" in text
    assert "Skill 已理解但无法执行命令时" in text
    assert "command bridge" in text
