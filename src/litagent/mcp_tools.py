from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from litagent.audit import audit_workspace
from litagent.classifier import classify_papers
from litagent.dedup import dedup_and_rank
from litagent.downloader import download_pdfs
from litagent.evidence import build_evidence_table
from litagent.inspect import inspect_workspace
from litagent.knowledge import build_knowledge
from litagent.mineru import parse_selected_pdfs
from litagent.planner import write_research_plan
from litagent.reader import generate_notes
from litagent.report import generate_final_report
from litagent.review_selection import review_selection
from litagent.search import execute_search
from litagent.status import workspace_status


def text_schema(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


def int_schema(description: str, default: int | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "integer", "description": description}
    if default is not None:
        schema["default"] = default
    return schema


def bool_schema(description: str, default: bool = False) -> dict[str, Any]:
    return {"type": "boolean", "description": description, "default": default}


def tool_definitions() -> list[dict[str, Any]]:
    workspace = text_schema("Workspace directory path.")
    return [
        {
            "name": "litagent_plan",
            "description": "Create research_plan.json and research_plan.md for a topic.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "topic": text_schema("Natural-language research topic."),
                    "workspace": workspace,
                    "max_papers": int_schema("Selection count.", 30),
                    "max_results_per_source": int_schema("Results per source.", 50),
                },
                "required": ["topic", "workspace"],
            },
        },
        {
            "name": "litagent_search",
            "description": "Search academic APIs or deterministic mock providers.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "workspace": workspace,
                    "mock": bool_schema("Use deterministic offline mock results."),
                    "run_id": text_schema("Optional explicit search run id."),
                },
                "required": ["workspace"],
            },
        },
        {
            "name": "litagent_dedup",
            "description": "Deduplicate, score, rank, and select papers.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "workspace": workspace,
                    "max_papers": int_schema("Maximum selected papers."),
                    "search_scope": {
                        "type": "string",
                        "enum": ["latest", "all", "selected"],
                        "default": "latest",
                    },
                    "search_run_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Search run ids used when search_scope is selected.",
                    },
                },
                "required": ["workspace"],
            },
        },
        {
            "name": "litagent_review_selection",
            "description": "Review selected papers for relevance before download.",
            "inputSchema": {
                "type": "object",
                "properties": {"workspace": workspace},
                "required": ["workspace"],
            },
        },
        {
            "name": "litagent_download",
            "description": "Download legal open PDFs and log failures.",
            "inputSchema": {
                "type": "object",
                "properties": {"workspace": workspace},
                "required": ["workspace"],
            },
        },
        {
            "name": "litagent_parse",
            "description": "Parse selected PDFs to Markdown through MinerU or local fallback.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "workspace": workspace,
                    "mineru_mode": {
                        "type": "string",
                        "enum": ["off", "agent", "precision", "auto"],
                        "default": "auto",
                    },
                    "language": text_schema("MinerU OCR language."),
                    "page_range": text_schema("Optional page range."),
                    "timeout": int_schema("Polling timeout seconds.", 300),
                },
                "required": ["workspace"],
            },
        },
        {
            "name": "litagent_classify",
            "description": "Classify selected paper types.",
            "inputSchema": {
                "type": "object",
                "properties": {"workspace": workspace},
                "required": ["workspace"],
            },
        },
        {
            "name": "litagent_read",
            "description": (
                "Generate Chinese-oriented structured paper notes with section-aware evidence "
                "metadata when parsed Markdown is available."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"workspace": workspace},
                "required": ["workspace"],
            },
        },
        {
            "name": "litagent_build_knowledge",
            "description": "Generate base knowledge, topic map, glossary, and index.",
            "inputSchema": {
                "type": "object",
                "properties": {"workspace": workspace},
                "required": ["workspace"],
            },
        },
        {
            "name": "litagent_build_evidence",
            "description": (
                "Generate section-aware, scored evidence_table.md and evidence_table.json for "
                "agent inspection."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"workspace": workspace},
                "required": ["workspace"],
            },
        },
        {
            "name": "litagent_report",
            "description": (
                "Generate a Chinese draft report from notes, knowledge, and scored evidence."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"workspace": workspace},
                "required": ["workspace"],
            },
        },
        {
            "name": "litagent_audit",
            "description": (
                "Audit workspace completeness, traceability, parse quality, and evidence quality."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"workspace": workspace},
                "required": ["workspace"],
            },
        },
        {
            "name": "litagent_status",
            "description": "Return agent-facing workspace status, counts, previews, and failures.",
            "inputSchema": {
                "type": "object",
                "properties": {"workspace": workspace},
                "required": ["workspace"],
            },
        },
        {
            "name": "litagent_inspect_workspace",
            "description": (
                "Assess whether a workspace is smoke-test quality or real-review quality, "
                "including search, selection, parse, evidence, report, audit concerns, "
                "and next action."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"workspace": workspace},
                "required": ["workspace"],
            },
        },
    ]


def as_workspace(arguments: dict[str, Any]) -> Path:
    workspace = arguments.get("workspace")
    if not workspace:
        msg = "workspace is required"
        raise ValueError(msg)
    return Path(str(workspace))


def call_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    arguments = arguments or {}
    workspace = as_workspace(arguments) if name != "litagent_plan" else Path(arguments["workspace"])

    if name == "litagent_plan":
        plan = write_research_plan(
            workspace,
            str(arguments["topic"]),
            max_results_per_source=int(arguments.get("max_results_per_source") or 50),
            selection_count=int(arguments.get("max_papers") or 30),
        )
        return {"ok": True, "topic": plan["topic"], "workspace": str(workspace)}
    if name == "litagent_search":
        rows = execute_search(
            workspace,
            mock=bool(arguments.get("mock", False)),
            run_id=arguments.get("run_id"),
        )
        run_id = rows[0].get("search_run_id") if rows else arguments.get("run_id")
        return {
            "ok": True,
            "raw_results": len(rows),
            "search_run_id": run_id,
            "workspace": str(workspace),
        }
    if name == "litagent_dedup":
        selected = dedup_and_rank(
            workspace,
            selection_count=arguments.get("max_papers"),
            search_scope=str(arguments.get("search_scope") or "latest"),
            search_run_ids=arguments.get("search_run_ids"),
        )
        return {"ok": True, "selected": len(selected), "workspace": str(workspace)}
    if name == "litagent_review_selection":
        return {"ok": True, **review_selection(workspace)}
    if name == "litagent_download":
        rows = download_pdfs(workspace)
        successes = sum(1 for row in rows if row.get("download_status") == "success")
        return {"ok": True, "pdf_successes": successes, "papers": len(rows)}
    if name == "litagent_parse":
        rows = parse_selected_pdfs(
            workspace,
            mode=str(arguments.get("mineru_mode") or "auto"),
            language=str(arguments.get("language") or "ch"),
            page_range=arguments.get("page_range"),
            timeout=int(arguments.get("timeout") or 300),
        )
        successes = sum(1 for row in rows if row.get("parse_status") == "success")
        return {"ok": True, "parse_successes": successes, "papers": len(rows)}
    if name == "litagent_classify":
        rows = classify_papers(workspace)
        return {"ok": True, "classified": len(rows)}
    if name == "litagent_read":
        rows = generate_notes(workspace)
        return {"ok": True, "notes": len(rows)}
    if name == "litagent_build_knowledge":
        rows = build_knowledge(workspace)
        return {"ok": True, "papers": len(rows)}
    if name == "litagent_build_evidence":
        result = build_evidence_table(workspace)
        return {"ok": True, **result}
    if name == "litagent_report":
        report = generate_final_report(workspace)
        return {"ok": True, "report_chars": len(report)}
    if name == "litagent_audit":
        result = audit_workspace(workspace)
        return {"ok": True, **result}
    if name == "litagent_status":
        return {"ok": True, **workspace_status(workspace)}
    if name == "litagent_inspect_workspace":
        return {"ok": True, **inspect_workspace(workspace)}

    msg = f"Unknown litagent MCP tool: {name}"
    raise ValueError(msg)


def call_tool_json(name: str, arguments: dict[str, Any] | None = None) -> str:
    return json.dumps(call_tool(name, arguments), ensure_ascii=False, indent=2, sort_keys=True)
