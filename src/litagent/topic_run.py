from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from litagent.audit import audit_workspace
from litagent.classifier import classify_papers
from litagent.dedup import dedup_and_rank
from litagent.downloader import download_pdfs
from litagent.evidence import build_evidence_table
from litagent.inspect import inspect_workspace
from litagent.io import append_jsonl, read_json, read_jsonl, write_json
from litagent.knowledge import build_knowledge
from litagent.mineru import parse_selected_pdfs
from litagent.planner import write_research_plan
from litagent.reader import generate_notes
from litagent.review_selection import review_selection
from litagent.search import execute_search
from litagent.wiki_export import export_wiki
from litagent.workspace import create_workspace

TOPIC_RUN_STEPS = [
    "plan",
    "search",
    "dedup",
    "review-selection",
    "download",
    "parse",
    "classify",
    "read",
    "build-knowledge",
    "build-evidence",
    "export-wiki",
    "audit",
    "inspect-workspace",
]

SEARCH_ERROR_PATH = Path("logs/search_errors.jsonl")
DOWNLOAD_LOG_PATH = Path("logs/downloads.jsonl")
PARSE_LOG_PATH = Path("logs/parsing.jsonl")


class TopicRunError(RuntimeError):
    """Raised when a topic run fails at a recoverable step."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def safe_error_text(value: object) -> str:
    text = str(value)
    text = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer [redacted-key]", text)
    text = re.sub(r"\b(?:sk|s2k)-[A-Za-z0-9._\-]{8,}", "[redacted-key]", text)
    text = re.sub(r"(?i)(api[_-]?key=)[A-Za-z0-9._\-]+", r"\1[redacted-key]", text)
    return text


def count_jsonl(path: Path) -> int:
    return len(read_jsonl(path))


def relative_artifact_path(workspace: Path, path: Path) -> str:
    try:
        return str(path.relative_to(workspace))
    except ValueError:
        return str(path)


def artifact_entry(workspace: Path, path: Path, *, step: str) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "step": step,
        "path": relative_artifact_path(workspace, path),
        "exists": path.exists(),
        "kind": "directory" if path.is_dir() else "file",
    }
    if path.exists() and path.is_file():
        entry["size_bytes"] = path.stat().st_size
    elif path.exists() and path.is_dir():
        entry["file_count"] = sum(1 for item in path.rglob("*") if item.is_file())
    else:
        entry["size_bytes"] = 0
    return entry


class TopicRun:
    def __init__(
        self,
        *,
        topic: str,
        workspace: Path,
        max_papers: int,
        max_results_per_source: int,
        mock: bool,
        mineru_mode: str,
        mineru_timeout: int,
        search_run_id: str | None,
        search_scope: str,
        wiki_out: Path | None,
        resume: bool,
        force: bool,
        from_step: str | None,
        allow_selection_concerns: bool,
    ) -> None:
        self.topic = topic
        self.workspace = workspace
        self.max_papers = max_papers
        self.max_results_per_source = max_results_per_source
        self.mock = mock
        self.mineru_mode = mineru_mode
        self.mineru_timeout = mineru_timeout
        self.search_run_id = search_run_id
        self.search_scope = search_scope
        self.wiki_out = wiki_out or workspace / "wiki-vault"
        self.resume = resume
        self.force = force
        self.from_step = from_step
        self.allow_selection_concerns = allow_selection_concerns
        self.state_path = workspace / "run_state.json"
        self.log_path = workspace / "run_log.jsonl"
        self.manifest_path = workspace / "artifacts_manifest.json"
        self.errors_path = workspace / "errors.json"
        self._rerun_from_step = from_step is None

    def load_state(self) -> dict[str, Any]:
        state = read_json(self.state_path, default={}) or {}
        if not state:
            state = {
                "topic": self.topic,
                "workspace": str(self.workspace),
                "status": "created",
                "step_order": TOPIC_RUN_STEPS,
                "steps": {},
                "created_at": utc_now(),
            }
        state.update(
            {
                "topic": self.topic,
                "workspace": str(self.workspace),
                "max_papers": self.max_papers,
                "max_results_per_source": self.max_results_per_source,
                "mock": self.mock,
                "mineru_mode": self.mineru_mode,
                "search_run_id": self.search_run_id,
                "search_scope": self.search_scope,
                "wiki_out": str(self.wiki_out),
            }
        )
        return state

    def write_state(self, state: dict[str, Any]) -> None:
        state["updated_at"] = utc_now()
        write_json(self.state_path, state)

    def log_event(self, event: str, **payload: Any) -> None:
        append_jsonl(
            self.log_path,
            {
                "event": event,
                "at": utc_now(),
                **payload,
            },
        )

    def read_errors(self) -> dict[str, Any]:
        return read_json(self.errors_path, default={"errors": []}) or {"errors": []}

    def append_error(self, step: str, error: object) -> None:
        payload = self.read_errors()
        errors = payload.setdefault("errors", [])
        errors.append({"step": step, "at": utc_now(), "error": safe_error_text(error)})
        write_json(self.errors_path, payload)

    def should_skip(self, state: dict[str, Any], step: str) -> bool:
        if self.force or not self.resume:
            return False
        if self.from_step == step:
            self._rerun_from_step = True
            return False
        if self.from_step is not None and self._rerun_from_step:
            return False
        previous = (state.get("steps") or {}).get(step) or {}
        return previous.get("status") == "succeeded"

    def write_manifest(self) -> dict[str, Any]:
        artifacts: list[dict[str, Any]] = []
        add = artifacts.append
        artifact_specs = [
            ("plan", self.workspace / "research_plan.json"),
            ("plan", self.workspace / "research_plan.md"),
            ("search", self.workspace / "data/raw_results.jsonl"),
            ("search", self.workspace / "data/search_runs/latest.json"),
            ("dedup", self.workspace / "data/papers.jsonl"),
            ("dedup", self.workspace / "data/selected_papers.jsonl"),
            ("review-selection", self.workspace / "logs/review_selection.json"),
            ("download", self.workspace / "library/pdfs"),
            ("download", self.workspace / "logs/downloads.jsonl"),
            ("parse", self.workspace / "library/markdown"),
            ("parse", self.workspace / "logs/parsing.jsonl"),
            ("read", self.workspace / "library/notes"),
            ("read", self.workspace / "library/metadata"),
            ("build-knowledge", self.workspace / "knowledge/base_knowledge.md"),
            ("build-knowledge", self.workspace / "knowledge/field_map.md"),
            ("build-knowledge", self.workspace / "knowledge/technical_frontier.md"),
            ("build-knowledge", self.workspace / "knowledge/method_matrix.md"),
            ("build-knowledge", self.workspace / "knowledge/benchmark_matrix.md"),
            ("build-knowledge", self.workspace / "knowledge/innovation_opportunities.md"),
            ("build-knowledge", self.workspace / "knowledge/reading_plan.md"),
            ("build-evidence", self.workspace / "knowledge/evidence_table.md"),
            ("build-evidence", self.workspace / "knowledge/evidence_table.json"),
            ("export-wiki", self.wiki_out / "START_HERE.md"),
            ("export-wiki", self.wiki_out / "kb/index.md"),
            ("export-wiki", self.wiki_out / "kb/source-index.md"),
            ("audit", self.workspace / "logs/audit_report.md"),
            ("inspect-workspace", self.workspace / "logs/inspect_workspace.json"),
            ("topic-run", self.state_path),
            ("topic-run", self.log_path),
            ("topic-run", self.errors_path),
            ("topic-run", self.manifest_path),
        ]
        for step, path in artifact_specs:
            add(artifact_entry(self.workspace, path, step=step))
        manifest = {
            "workspace": str(self.workspace),
            "topic": self.topic,
            "generated_at": utc_now(),
            "artifacts": artifacts,
            "missing": [item["path"] for item in artifacts if not item["exists"]],
        }
        write_json(self.manifest_path, manifest)
        return manifest

    def run_step(
        self,
        state: dict[str, Any],
        step: str,
        action: Callable[[], dict[str, Any]],
    ) -> dict[str, Any] | None:
        if self.should_skip(state, step):
            self.log_event("step_skipped", step=step, reason="previously_succeeded")
            return None

        steps = state.setdefault("steps", {})
        started_at = utc_now()
        steps[step] = {"step": step, "status": "running", "started_at": started_at}
        state["status"] = "running"
        state["current_step"] = step
        self.write_state(state)
        self.log_event("step_started", step=step)

        try:
            metrics = action()
        except Exception as exc:
            finished_at = utc_now()
            error_text = safe_error_text(exc)
            steps[step] = {
                "step": step,
                "status": "failed",
                "started_at": started_at,
                "finished_at": finished_at,
                "error": error_text,
            }
            state["status"] = "failed"
            state["failed_step"] = step
            state["finished_at"] = finished_at
            self.append_error(step, exc)
            self.write_state(state)
            self.write_manifest()
            self.log_event("step_failed", step=step, error=error_text)
            raise

        finished_at = utc_now()
        record = {
            "step": step,
            "status": "succeeded",
            "started_at": started_at,
            "finished_at": finished_at,
            "input_count": int(metrics.get("input_count", 0)),
            "output_count": int(metrics.get("output_count", 0)),
            "failed_count": int(metrics.get("failed_count", 0)),
        }
        if metrics.get("details") is not None:
            record["details"] = metrics["details"]
        steps[step] = record
        self.write_state(state)
        self.write_manifest()
        self.log_event("step_succeeded", **record)
        return record

    def step_plan(self) -> dict[str, Any]:
        plan = write_research_plan(
            self.workspace,
            self.topic,
            max_results_per_source=self.max_results_per_source,
            selection_count=self.max_papers,
        )
        return {
            "input_count": 1,
            "output_count": 2,
            "failed_count": 0,
            "details": {
                "topic": plan.get("topic"),
                "selection_count": plan.get("selection_count"),
            },
        }

    def step_search(self) -> dict[str, Any]:
        before_errors = count_jsonl(self.workspace / SEARCH_ERROR_PATH)
        rows = execute_search(self.workspace, mock=self.mock, run_id=self.search_run_id)
        after_errors = count_jsonl(self.workspace / SEARCH_ERROR_PATH)
        run_id = rows[0].get("search_run_id") if rows else self.search_run_id
        return {
            "input_count": sum(
                len(queries)
                for queries in (
                    read_json(self.workspace / "research_plan.json", default={}) or {}
                )
                .get("search_queries", {})
                .values()
            ),
            "output_count": len(rows),
            "failed_count": max(0, after_errors - before_errors),
            "details": {"search_run_id": run_id, "mock": self.mock},
        }

    def step_dedup(self) -> dict[str, Any]:
        raw_count = count_jsonl(self.workspace / "data/raw_results.jsonl")
        selected = dedup_and_rank(
            self.workspace,
            selection_count=self.max_papers,
            search_scope=self.search_scope,
        )
        return {
            "input_count": raw_count,
            "output_count": len(selected),
            "failed_count": 0,
            "details": {"search_scope": self.search_scope},
        }

    def step_review_selection(self) -> dict[str, Any]:
        selected_count = count_jsonl(self.workspace / "data/selected_papers.jsonl")
        result = review_selection(self.workspace)
        write_json(self.workspace / "logs" / "review_selection.json", result)
        failed_count = len(result.get("likely_off_topic") or [])
        questionable_count = len(result.get("questionable") or [])
        if failed_count and not self.allow_selection_concerns:
            msg = (
                "review-selection found likely off-topic papers; inspect "
                "logs/review_selection.json before download or rerun with "
                "--allow-selection-concerns."
            )
            raise TopicRunError(msg)
        return {
            "input_count": selected_count,
            "output_count": len(result.get("likely_relevant") or []),
            "failed_count": failed_count,
            "details": {
                "questionable_count": questionable_count,
                "likely_off_topic_count": failed_count,
                "recommended_next_action": result.get("recommended_next_action"),
            },
        }

    def step_download(self) -> dict[str, Any]:
        selected_count = count_jsonl(self.workspace / "data/selected_papers.jsonl")
        rows = download_pdfs(self.workspace)
        successes = sum(1 for row in rows if row.get("download_status") == "success")
        return {
            "input_count": selected_count,
            "output_count": successes,
            "failed_count": max(0, len(rows) - successes),
        }

    def step_parse(self) -> dict[str, Any]:
        rows = parse_selected_pdfs(
            self.workspace,
            mode=self.mineru_mode,
            timeout=self.mineru_timeout,
        )
        successes = sum(1 for row in rows if row.get("parse_status") == "success")
        return {
            "input_count": len(rows),
            "output_count": successes,
            "failed_count": max(0, len(rows) - successes),
            "details": {"mineru_mode": self.mineru_mode},
        }

    def step_classify(self) -> dict[str, Any]:
        rows = classify_papers(self.workspace)
        return {"input_count": len(rows), "output_count": len(rows), "failed_count": 0}

    def step_read(self) -> dict[str, Any]:
        selected_count = count_jsonl(self.workspace / "data/selected_papers.jsonl")
        rows = generate_notes(self.workspace)
        return {"input_count": selected_count, "output_count": len(rows), "failed_count": 0}

    def step_build_knowledge(self) -> dict[str, Any]:
        selected_count = count_jsonl(self.workspace / "data/selected_papers.jsonl")
        rows = build_knowledge(self.workspace)
        return {"input_count": selected_count, "output_count": len(rows), "failed_count": 0}

    def step_build_evidence(self) -> dict[str, Any]:
        selected_count = count_jsonl(self.workspace / "data/selected_papers.jsonl")
        result = build_evidence_table(self.workspace)
        total_snippets = sum(
            len(theme.get("evidence_snippets_or_sections") or [])
            for theme in result.get("themes", [])
        )
        return {
            "input_count": selected_count,
            "output_count": total_snippets,
            "failed_count": 0,
            "details": {"theme_count": len(result.get("themes", []))},
        }

    def step_export_wiki(self) -> dict[str, Any]:
        selected_count = count_jsonl(self.workspace / "data/selected_papers.jsonl")
        result = export_wiki(self.workspace, self.wiki_out, export_format="autowiki")
        return {
            "input_count": selected_count,
            "output_count": int(result.get("paper_count") or 0),
            "failed_count": 0,
            "details": {"out": str(self.wiki_out)},
        }

    def step_audit(self) -> dict[str, Any]:
        selected_count = count_jsonl(self.workspace / "data/selected_papers.jsonl")
        result = audit_workspace(self.workspace)
        return {
            "input_count": selected_count,
            "output_count": 1 if result.get("passed") else 0,
            "failed_count": 0 if result.get("passed") else 1,
            "details": {"passed": bool(result.get("passed")), "warnings": result.get("warnings")},
        }

    def step_inspect(self) -> dict[str, Any]:
        selected_count = count_jsonl(self.workspace / "data/selected_papers.jsonl")
        result = inspect_workspace(self.workspace)
        write_json(self.workspace / "logs" / "inspect_workspace.json", result)
        return {
            "input_count": selected_count,
            "output_count": 1,
            "failed_count": 0,
            "details": {
                "quality_label": result.get("quality_label"),
                "recommended_next_action": result.get("recommended_next_action"),
            },
        }

    def run(self) -> dict[str, Any]:
        create_workspace(self.workspace)
        state = self.load_state()
        if state.get("status") != "running":
            state["started_at"] = state.get("started_at") or utc_now()
        state["status"] = "running"
        self.write_state(state)
        if not self.errors_path.exists():
            write_json(self.errors_path, {"errors": []})
        self.log_event(
            "topic_run_started",
            topic=self.topic,
            workspace=str(self.workspace),
            mock=self.mock,
            max_papers=self.max_papers,
        )

        actions: dict[str, Callable[[], dict[str, Any]]] = {
            "plan": self.step_plan,
            "search": self.step_search,
            "dedup": self.step_dedup,
            "review-selection": self.step_review_selection,
            "download": self.step_download,
            "parse": self.step_parse,
            "classify": self.step_classify,
            "read": self.step_read,
            "build-knowledge": self.step_build_knowledge,
            "build-evidence": self.step_build_evidence,
            "export-wiki": self.step_export_wiki,
            "audit": self.step_audit,
            "inspect-workspace": self.step_inspect,
        }
        for step in TOPIC_RUN_STEPS:
            self.run_step(state, step, actions[step])

        state["status"] = "succeeded"
        state["finished_at"] = utc_now()
        state.pop("current_step", None)
        state.pop("failed_step", None)
        self.write_state(state)
        manifest = self.write_manifest()
        self.log_event("topic_run_succeeded", artifact_count=len(manifest["artifacts"]))
        return {
            "state": state,
            "manifest": manifest,
            "errors": self.read_errors(),
        }


def run_topic(
    topic: str,
    workspace: Path,
    *,
    max_papers: int = 30,
    max_results_per_source: int = 50,
    mock: bool = False,
    mineru_mode: str = "off",
    mineru_timeout: int = 300,
    search_run_id: str | None = None,
    search_scope: str = "latest",
    wiki_out: Path | None = None,
    resume: bool = True,
    force: bool = False,
    from_step: str | None = None,
    allow_selection_concerns: bool = False,
) -> dict[str, Any]:
    if from_step and from_step not in TOPIC_RUN_STEPS:
        msg = f"Unknown topic-run step: {from_step}"
        raise ValueError(msg)
    runner = TopicRun(
        topic=topic,
        workspace=workspace,
        max_papers=max_papers,
        max_results_per_source=max_results_per_source,
        mock=mock,
        mineru_mode=mineru_mode,
        mineru_timeout=mineru_timeout,
        search_run_id=search_run_id,
        search_scope=search_scope,
        wiki_out=wiki_out,
        resume=resume,
        force=force,
        from_step=from_step,
        allow_selection_concerns=allow_selection_concerns,
    )
    return runner.run()
