from __future__ import annotations

from pathlib import Path

WORKSPACE_DIRS = [
    "config/prompts",
    "data",
    "library/pdfs",
    "library/markdown",
    "library/notes",
    "library/metadata",
    "knowledge",
    "reports",
    "logs",
]

PROMPT_FILES = {
    "planner.md": "# Planner Prompt\n\nGenerate a research plan from the user's topic.\n",
    "survey_reader.md": (
        "# Survey Reader Prompt\n\nExtract structured insights from survey papers.\n"
    ),
    "technical_reader.md": (
        "# Technical Reader Prompt\n\nExtract method, evidence, limits, and citations "
        "from technical papers.\n"
    ),
    "synthesis.md": "# Synthesis Prompt\n\nSynthesize notes into a traceable research report.\n",
}

SOURCES_YAML = """sources:
  arxiv:
    enabled: true
  semantic_scholar:
    enabled: true
  openalex:
    enabled: true
  unpaywall:
    enabled: true
"""

README_MD = (
    "# Litagent Workspace\n\n"
    "This workspace stores search results, PDFs, notes, knowledge maps, reports, and logs.\n"
)


def create_workspace(workspace: Path) -> list[Path]:
    """Create the PRD workspace skeleton without deleting existing files."""
    created_or_verified: list[Path] = []
    workspace.mkdir(parents=True, exist_ok=True)
    created_or_verified.append(workspace)

    for directory in WORKSPACE_DIRS:
        path = workspace / directory
        path.mkdir(parents=True, exist_ok=True)
        created_or_verified.append(path)

    files = {
        workspace / "config" / "sources.yaml": SOURCES_YAML,
        workspace / "README.md": README_MD,
    }
    files.update(
        {
            workspace / "config" / "prompts" / filename: content
            for filename, content in PROMPT_FILES.items()
        }
    )

    for path, content in files.items():
        if not path.exists():
            path.write_text(content, encoding="utf-8")
        created_or_verified.append(path)

    return created_or_verified
