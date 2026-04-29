from __future__ import annotations

import argparse
import json
from pathlib import Path

from litagent.audit import audit_workspace
from litagent.classifier import classify_papers
from litagent.dedup import dedup_and_rank
from litagent.downloader import download_pdfs
from litagent.evidence import build_evidence_table
from litagent.inspect import inspect_workspace, inspect_workspace_markdown
from litagent.knowledge import build_knowledge
from litagent.mineru import parse_selected_pdfs
from litagent.pipeline import run_pipeline
from litagent.planner import write_research_plan
from litagent.provider_diagnostics import smoke_test_semantic_scholar
from litagent.reader import generate_notes
from litagent.report import generate_final_report
from litagent.review_selection import review_selection, review_selection_markdown
from litagent.search import execute_search
from litagent.status import workspace_status, workspace_status_markdown
from litagent.topic_run import TOPIC_RUN_STEPS, run_topic
from litagent.wiki_export import export_wiki
from litagent.workspace import create_workspace


def init_workspace(workspace: Path) -> int:
    created = create_workspace(workspace)
    print(f"Initialized workspace: {workspace}")
    print(f"Created/verified {len(created)} paths")
    return 0


def plan_research(args: argparse.Namespace) -> int:
    plan = write_research_plan(
        args.workspace,
        args.topic,
        max_results_per_source=args.max_results_per_source,
        selection_count=args.max_papers,
    )
    print(f"Wrote plan for: {plan['topic']}")
    print(args.workspace / "research_plan.json")
    print(args.workspace / "research_plan.md")
    return 0


def search_research(args: argparse.Namespace) -> int:
    rows = execute_search(args.workspace, mock=args.mock, run_id=args.run_id)
    run_id = rows[0].get("search_run_id") if rows else args.run_id
    print(f"Wrote {len(rows)} raw results")
    if run_id:
        print(f"Search run: {run_id}")
        print(args.workspace / "data" / "search_runs" / str(run_id) / "raw_results.jsonl")
    print(args.workspace / "data" / "raw_results.jsonl")
    return 0


def dedup_research(args: argparse.Namespace) -> int:
    selected = dedup_and_rank(
        args.workspace,
        selection_count=args.max_papers,
        search_scope=args.search_scope,
        search_run_ids=args.search_run_id,
    )
    print(f"Selected {len(selected)} papers")
    print(args.workspace / "data" / "papers.jsonl")
    print(args.workspace / "data" / "selected_papers.jsonl")
    return 0


def download_research(args: argparse.Namespace) -> int:
    rows = download_pdfs(args.workspace)
    successes = sum(1 for row in rows if row.get("download_status") == "success")
    print(f"Downloaded {successes}/{len(rows)} PDFs")
    print(args.workspace / "logs" / "downloads.jsonl")
    return 0


def classify_research(args: argparse.Namespace) -> int:
    rows = classify_papers(args.workspace)
    print(f"Classified {len(rows)} papers")
    print(args.workspace / "data" / "selected_papers.jsonl")
    return 0


def parse_research(args: argparse.Namespace) -> int:
    rows = parse_selected_pdfs(
        args.workspace,
        mode=args.mineru_mode,
        language=args.language,
        page_range=args.page_range,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
    )
    successes = sum(1 for row in rows if row.get("parse_status") == "success")
    print(f"Parsed {successes}/{len(rows)} PDFs")
    print(args.workspace / "library" / "markdown")
    print(args.workspace / "logs" / "parsing.jsonl")
    return 0


def read_research(args: argparse.Namespace) -> int:
    rows = generate_notes(args.workspace)
    print(f"Generated {len(rows)} notes")
    print(args.workspace / "library" / "notes")
    return 0


def build_knowledge_command(args: argparse.Namespace) -> int:
    rows = build_knowledge(args.workspace)
    print(f"Built knowledge files from {len(rows)} papers")
    print(args.workspace / "knowledge")
    return 0


def build_evidence_command(args: argparse.Namespace) -> int:
    result = build_evidence_table(args.workspace)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Built evidence table from {result['selected_count']} papers")
        print(args.workspace / "knowledge" / "evidence_table.md")
        print(args.workspace / "knowledge" / "evidence_table.json")
    return 0


def report_research(args: argparse.Namespace) -> int:
    generate_final_report(args.workspace)
    print("Generated final report")
    print(args.workspace / "reports" / "final_report.md")
    return 0


def audit_research(args: argparse.Namespace) -> int:
    result = audit_workspace(args.workspace)
    print("Audit PASS" if result["passed"] else "Audit FAIL")
    print(args.workspace / "logs" / "audit_report.md")
    return 0 if result["passed"] else 1


def status_research(args: argparse.Namespace) -> int:
    if args.json:
        print(
            json.dumps(
                workspace_status(args.workspace),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(workspace_status_markdown(args.workspace))
    return 0


def inspect_workspace_command(args: argparse.Namespace) -> int:
    if args.json:
        print(
            json.dumps(
                inspect_workspace(args.workspace),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(inspect_workspace_markdown(args.workspace))
    return 0


def review_selection_command(args: argparse.Namespace) -> int:
    result = review_selection(args.workspace)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(review_selection_markdown(args.workspace))
    return 0


def provider_smoke_command(args: argparse.Namespace) -> int:
    provider_name = args.provider.replace("-", "_")
    if provider_name != "semantic_scholar":
        msg = f"Unsupported provider smoke test: {args.provider}"
        raise ValueError(msg)
    result = smoke_test_semantic_scholar(query=args.query, limit=args.limit)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Provider: {result['provider']}")
        print(f"Success: {result['success']}")
        print(f"Status code: {result['status_code']}")
        print(f"Error type: {result['error_type']}")
        print(f"Likely action: {result['likely_action']}")
    return 0


def export_wiki_command(args: argparse.Namespace) -> int:
    result = export_wiki(args.workspace, args.out, export_format=args.format)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Exported {result['paper_count']} papers to AutoWiki-compatible vault")
        print(args.out)
    return 0


def run_research(args: argparse.Namespace) -> int:
    result = run_pipeline(
        args.topic,
        args.workspace,
        max_papers=args.max_papers,
        max_results_per_source=args.max_results_per_source,
        mock=args.mock,
        mineru_mode=args.mineru_mode,
        mineru_timeout=args.mineru_timeout,
    )
    print(
        f"Run complete: raw_results={result['raw_results']} selected={result['selected']} "
        f"audit={'PASS' if result['audit']['passed'] else 'FAIL'}"
    )
    print(args.workspace / "reports" / "final_report.md")
    print(args.workspace / "logs" / "audit_report.md")
    return 0 if result["audit"]["passed"] else 1


def topic_run_command(args: argparse.Namespace) -> int:
    result = run_topic(
        args.topic,
        args.workspace,
        max_papers=args.max_papers,
        max_results_per_source=args.max_results_per_source,
        mock=args.mock,
        mineru_mode=args.mineru_mode,
        mineru_timeout=args.mineru_timeout,
        search_run_id=args.run_id,
        search_scope=args.search_scope,
        wiki_out=args.wiki_out,
        resume=not args.no_resume,
        force=args.force,
        from_step=args.from_step,
        allow_selection_concerns=args.allow_selection_concerns,
    )
    state = result["state"]
    inspect_step = (state.get("steps") or {}).get("inspect-workspace") or {}
    details = inspect_step.get("details") or {}
    print(f"Topic run {state['status']}: {args.topic}")
    print(args.workspace / "run_state.json")
    print(args.workspace / "artifacts_manifest.json")
    print(args.workspace / "run_log.jsonl")
    print(args.workspace / "errors.json")
    if details.get("quality_label"):
        print(f"Inspect label: {details['quality_label']}")
    print(f"Wiki vault: {state.get('wiki_out')}")
    return 0 if state["status"] == "succeeded" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agentic literature research workbench.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a litagent workspace directory tree.")
    init_parser.add_argument("workspace", type=Path)

    plan_parser = subparsers.add_parser(
        "plan", help="Generate research_plan.json and research_plan.md."
    )
    plan_parser.add_argument("topic")
    plan_parser.add_argument("--workspace", type=Path, required=True)
    plan_parser.add_argument("--max-results-per-source", type=int, default=50)
    plan_parser.add_argument("--max-papers", type=int, default=30)
    plan_parser.set_defaults(func=plan_research)

    search_parser = subparsers.add_parser("search", help="Search configured academic providers.")
    search_parser.add_argument("workspace", type=Path)
    search_parser.add_argument(
        "--mock", action="store_true", help="Use deterministic offline mock results."
    )
    search_parser.add_argument("--run-id", help="Optional explicit search run id.")
    search_parser.set_defaults(func=search_research)

    dedup_parser = subparsers.add_parser("dedup", help="Deduplicate, score, and select papers.")
    dedup_parser.add_argument("workspace", type=Path)
    dedup_parser.add_argument("--max-papers", type=int)
    dedup_parser.add_argument(
        "--search-scope",
        choices=["latest", "all", "selected"],
        default="latest",
        help="Which isolated search run results to deduplicate.",
    )
    dedup_parser.add_argument(
        "--search-run-id",
        action="append",
        help="Search run id to include when --search-scope selected.",
    )
    dedup_parser.set_defaults(func=dedup_research)

    download_parser = subparsers.add_parser("download", help="Download legal open-access PDFs.")
    download_parser.add_argument("workspace", type=Path)
    download_parser.set_defaults(func=download_research)

    parse_parser = subparsers.add_parser("parse", help="Parse downloaded PDFs into Markdown.")
    parse_parser.add_argument("workspace", type=Path)
    parse_parser.add_argument(
        "--mineru-mode",
        choices=["off", "agent", "precision", "auto"],
        default="auto",
        help="MinerU parser mode. auto uses precision when MINERU_API_TOKEN is set.",
    )
    parse_parser.add_argument("--language", default="ch")
    parse_parser.add_argument("--page-range")
    parse_parser.add_argument("--timeout", type=int, default=300)
    parse_parser.add_argument("--poll-interval", type=float, default=3)
    parse_parser.set_defaults(func=parse_research)

    classify_parser = subparsers.add_parser("classify", help="Classify selected paper types.")
    classify_parser.add_argument("workspace", type=Path)
    classify_parser.set_defaults(func=classify_research)

    read_parser = subparsers.add_parser("read", help="Generate structured Markdown notes.")
    read_parser.add_argument("workspace", type=Path)
    read_parser.set_defaults(func=read_research)

    knowledge_parser = subparsers.add_parser(
        "build-knowledge",
        help="Generate base knowledge, topic map, glossary, and index.",
    )
    knowledge_parser.add_argument("workspace", type=Path)
    knowledge_parser.set_defaults(func=build_knowledge_command)

    evidence_parser = subparsers.add_parser(
        "build-evidence",
        help="Generate evidence table artifacts from notes and parsed Markdown.",
    )
    evidence_parser.add_argument("workspace", type=Path)
    evidence_parser.add_argument("--json", action="store_true")
    evidence_parser.set_defaults(func=build_evidence_command)

    report_parser = subparsers.add_parser("report", help="Generate the final research report.")
    report_parser.add_argument("workspace", type=Path)
    report_parser.set_defaults(func=report_research)

    audit_parser = subparsers.add_parser(
        "audit", help="Audit workspace completeness and traceability."
    )
    audit_parser.add_argument("workspace", type=Path)
    audit_parser.set_defaults(func=audit_research)

    status_parser = subparsers.add_parser(
        "status", help="Show agent-facing workspace status and failures."
    )
    status_parser.add_argument("workspace", type=Path)
    status_parser.add_argument("--json", action="store_true")
    status_parser.set_defaults(func=status_research)

    inspect_parser = subparsers.add_parser(
        "inspect-workspace",
        help="Assess workspace quality and recommend the next agent action.",
    )
    inspect_parser.add_argument("workspace", type=Path)
    inspect_parser.add_argument("--json", action="store_true")
    inspect_parser.set_defaults(func=inspect_workspace_command)

    review_parser = subparsers.add_parser(
        "review-selection",
        help="Inspect selected papers before download and recommend next action.",
    )
    review_parser.add_argument("workspace", type=Path)
    review_parser.add_argument("--json", action="store_true")
    review_parser.set_defaults(func=review_selection_command)

    provider_smoke_parser = subparsers.add_parser(
        "provider-smoke",
        help="Run a minimal safe provider connectivity diagnostic.",
    )
    provider_smoke_parser.add_argument(
        "provider",
        choices=["semantic-scholar", "semantic_scholar"],
        help="Provider to diagnose.",
    )
    provider_smoke_parser.add_argument("--json", action="store_true")
    provider_smoke_parser.add_argument("--query", default="literature review automation")
    provider_smoke_parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Maximum results to request; capped at 3 for smoke tests.",
    )
    provider_smoke_parser.set_defaults(func=provider_smoke_command)

    export_wiki_parser = subparsers.add_parser(
        "export-wiki",
        help="Export existing workspace artifacts to an AutoWiki-compatible Markdown vault.",
    )
    export_wiki_parser.add_argument("workspace", type=Path)
    export_wiki_parser.add_argument(
        "--format",
        choices=["autowiki"],
        default="autowiki",
        help="Wiki export format.",
    )
    export_wiki_parser.add_argument("--out", type=Path, required=True)
    export_wiki_parser.add_argument("--json", action="store_true")
    export_wiki_parser.set_defaults(func=export_wiki_command)

    topic_run_parser = subparsers.add_parser(
        "topic-run",
        help="Run a resumable topic workflow with run_state, run_log, and manifest files.",
    )
    topic_run_parser.add_argument("topic")
    topic_run_parser.add_argument("--workspace", type=Path, required=True)
    topic_run_parser.add_argument("--max-papers", type=int, default=30)
    topic_run_parser.add_argument("--max-results-per-source", type=int, default=50)
    topic_run_parser.add_argument(
        "--mock",
        action="store_true",
        help="Use deterministic offline mock providers.",
    )
    topic_run_parser.add_argument(
        "--mineru-mode",
        choices=["off", "agent", "precision", "auto"],
        default="off",
        help="PDF parsing mode. Default keeps the first pass local with pypdf.",
    )
    topic_run_parser.add_argument("--mineru-timeout", type=int, default=300)
    topic_run_parser.add_argument("--run-id", help="Optional explicit search run id.")
    topic_run_parser.add_argument(
        "--search-scope",
        choices=["latest", "all", "selected"],
        default="latest",
        help="Which isolated search run results to deduplicate.",
    )
    topic_run_parser.add_argument(
        "--wiki-out",
        type=Path,
        help="AutoWiki-compatible vault output directory. Defaults to WORKSPACE/wiki-vault.",
    )
    topic_run_parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not skip previously succeeded steps in run_state.json.",
    )
    topic_run_parser.add_argument(
        "--force",
        action="store_true",
        help="Rerun every step even if run_state.json marks it succeeded.",
    )
    topic_run_parser.add_argument(
        "--from-step",
        choices=TOPIC_RUN_STEPS,
        help="Resume by rerunning this step and all downstream steps.",
    )
    topic_run_parser.add_argument(
        "--allow-selection-concerns",
        action="store_true",
        help="Continue even if review-selection flags likely off-topic papers.",
    )
    topic_run_parser.set_defaults(func=topic_run_command)

    run_parser = subparsers.add_parser("run", help="Run the full research pipeline.")
    run_parser.add_argument("topic")
    run_parser.add_argument("--workspace", type=Path, required=True)
    run_parser.add_argument("--max-papers", type=int, default=30)
    run_parser.add_argument("--max-results-per-source", type=int, default=50)
    run_parser.add_argument(
        "--mineru-mode",
        choices=["off", "agent", "precision", "auto"],
        default="off",
        help="PDF parsing mode during run. Use auto to enable MinerU.",
    )
    run_parser.add_argument("--mineru-timeout", type=int, default=300)
    run_parser.add_argument(
        "--mock", action="store_true", help="Use deterministic offline mock providers."
    )
    run_parser.set_defaults(func=run_research)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return init_workspace(args.workspace)
    if hasattr(args, "func"):
        return args.func(args)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
