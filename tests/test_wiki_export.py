from pathlib import Path
from uuid import uuid4

from litagent.cli import main
from litagent.io import read_json, write_json, write_jsonl
from litagent.wiki_export import export_wiki


def workspace_path(name: str) -> Path:
    path = Path(".tmp") / "tests" / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_export_workspace(workspace: Path) -> None:
    papers = [
        {
            "paper_id": "p-survey000001",
            "title": "A Survey of Literature Review Automation",
            "authors": ["A"],
            "year": 2024,
            "abstract": "This survey builds a taxonomy for automated literature review tools.",
            "source": ["openalex"],
            "paper_type": "survey",
            "relevance_score": 0.8,
        },
        {
            "paper_id": "p-system000001",
            "title": "AgentReview: A Multi-Agent Literature Review Workbench",
            "authors": ["B"],
            "year": 2025,
            "abstract": (
                "We propose a multi-agent workbench with planner, reader, writer, "
                "and critic agents for citation-aware synthesis."
            ),
            "source": ["semantic_scholar"],
            "paper_type": "system",
            "relevance_score": 0.9,
        },
        {
            "paper_id": "p-bench0000001",
            "title": "ReviewBench: A Benchmark for Survey Generation",
            "authors": ["C"],
            "year": 2025,
            "abstract": "A benchmark dataset and metrics for evaluating survey generation.",
            "source": ["arxiv"],
            "paper_type": "benchmark",
            "relevance_score": 0.7,
        },
    ]
    write_jsonl(workspace / "data" / "selected_papers.jsonl", papers)
    for paper in papers:
        note = workspace / "library" / "notes" / f"{paper['paper_id']}.md"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(
            f"# {paper['title']}\n\nSource: parsed-full-text\n\n中文阅读笔记。",
            encoding="utf-8",
        )
    write_json(
        workspace / "knowledge" / "evidence_table.json",
        {
            "workspace": str(workspace),
            "selected_count": 3,
            "themes": [
                {
                    "theme": "citation-aware synthesis",
                    "claim": "系统需要显式管理引用和证据。",
                    "supporting_papers": ["p-system000001"],
                    "evidence_snippets_or_sections": [
                        {
                            "paper_id": "p-system000001",
                            "paper_title": (
                                "AgentReview: A Multi-Agent Literature Review Workbench"
                            ),
                            "snippet": (
                                "The workbench performs citation-aware synthesis with "
                                "planner and critic agents."
                            ),
                            "section": "Method",
                            "snippet_score": 0.86,
                            "snippet_score_explanation": "加分：Method 章节、agent_roles；扣分：无",
                            "quality_flags": [],
                            "confidence": "high",
                        }
                    ],
                    "confidence": "high",
                    "gaps_or_uncertainties": [],
                }
            ],
        },
    )
    (workspace / "knowledge" / "evidence_table.md").write_text("# 证据表\n", encoding="utf-8")


def test_export_wiki_creates_autowiki_vault_without_network(monkeypatch) -> None:
    workspace = workspace_path("wiki-export")
    out_dir = workspace_path("wiki-vault")
    write_export_workspace(workspace)
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "s2k-test-secret")

    result = export_wiki(workspace, out_dir)

    assert result["paper_count"] == 3
    assert (out_dir / "raw" / "p-system000001" / "source.md").is_file()
    assert (out_dir / "raw" / "p-system000001" / "metadata.json").is_file()
    assert (out_dir / "raw" / "p-system000001" / "evidence.json").is_file()
    assert (out_dir / "kb" / "index.md").is_file()
    assert (out_dir / "kb" / "field-map.md").is_file()
    assert (out_dir / "kb" / "technical-frontier.md").is_file()
    assert (out_dir / "kb" / "matrices" / "method-matrix.md").is_file()
    assert (out_dir / "kb" / "matrices" / "benchmark-matrix.md").is_file()

    source = (out_dir / "raw" / "p-system000001" / "source.md").read_text(encoding="utf-8")
    index = (out_dir / "kb" / "index.md").read_text(encoding="utf-8")
    method_matrix = (out_dir / "kb" / "matrices" / "method-matrix.md").read_text(
        encoding="utf-8"
    )
    metadata = read_json(out_dir / "raw" / "p-system000001" / "metadata.json")

    assert "p-system000001" in source
    assert "[[citation-aware-synthesis]]" in source
    assert "[[field-map]]" in index
    assert "p-system000001" in method_matrix
    assert metadata["paper_role"] == "system_paper"
    assert "track_frontier" in metadata["reading_intent"]

    all_text = "\n".join(
        path.read_text(encoding="utf-8") for path in out_dir.rglob("*") if path.is_file()
    )
    assert "s2k-test-secret" not in all_text
    assert "SEMANTIC_SCHOLAR_API_KEY" not in all_text
    assert ".env" not in all_text


def test_export_wiki_cli_command_exists() -> None:
    workspace = workspace_path("wiki-export-cli")
    out_dir = workspace_path("wiki-vault-cli")
    write_export_workspace(workspace)

    exit_code = main(["export-wiki", str(workspace), "--format", "autowiki", "--out", str(out_dir)])

    assert exit_code == 0
    assert (out_dir / "export_manifest.json").is_file()
    assert (out_dir / "kb" / "index.md").is_file()
