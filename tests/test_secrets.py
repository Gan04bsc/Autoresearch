from pathlib import Path

from litagent.secrets import get_config_value, parse_env_file


def test_parse_env_file_supports_quotes_and_comments(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
# comment
MINERU_API_TOKEN="abc.def"
EMPTY=
OTHER='value'
""",
        encoding="utf-8",
    )

    values = parse_env_file(env_file)

    assert values["MINERU_API_TOKEN"] == "abc.def"
    assert values["OTHER"] == "value"
    assert values["EMPTY"] == ""


def test_get_config_value_prefers_environment(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("MINERU_API_TOKEN=file-token\n", encoding="utf-8")
    monkeypatch.setenv("MINERU_API_TOKEN", "env-token")

    assert get_config_value("MINERU_API_TOKEN", env_files=[env_file]) == "env-token"


def test_get_config_value_reads_env_file(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("MINERU_API_TOKEN=file-token\n", encoding="utf-8")
    monkeypatch.delenv("MINERU_API_TOKEN", raising=False)

    assert get_config_value("MINERU_API_TOKEN", env_files=[env_file]) == "file-token"

