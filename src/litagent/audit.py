from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from litagent.io import read_json, read_jsonl
from litagent.paper_roles import enrich_paper_role, role_counts
from litagent.schema import missing_paper_fields, normalize_paper

REQUIRED_REPORT_SECTIONS = [
    "执行摘要",
    "研究背景",
    "核心问题",
    "方法分类",
    "论文代表性列表",
    "证据支撑的主题综合",
    "综述类论文综合",
    "技术论文综合",
    "局限和研究空白",
    "对 litagent 的设计启发",
    "下一步路线图",
    "推荐阅读顺序",
    "参考文献",
]

GENERIC_UNSUPPORTED_PATTERNS = [
    "these papers",
    "selected papers",
    "the literature",
    "papers show",
    "systems show",
    "the field is",
    "这些论文",
    "所选论文",
    "文献表明",
    "研究表明",
    "该领域",
]

WORKSPACE_ARTIFACTS = [
    "knowledge/field_map.md",
    "knowledge/technical_frontier.md",
    "knowledge/method_matrix.md",
    "knowledge/benchmark_matrix.md",
    "knowledge/innovation_opportunities.md",
    "knowledge/reading_plan.md",
]


def nonempty_file(path: Path) -> bool:
    return path.exists() and path.is_file() and path.stat().st_size > 0


def parse_quality_metrics(workspace: Path, selected: list[dict[str, Any]]) -> dict[str, Any]:
    downloaded_pdf_count = 0
    parsed_markdown_count = 0
    notes_from_parsed_markdown = 0
    notes_from_pdf_text = 0
    notes_from_abstract_fallback = 0
    notes_with_unknown_source = 0

    for paper in selected:
        local_pdf_path = paper.get("local_pdf_path")
        if local_pdf_path and nonempty_file(workspace / str(local_pdf_path)):
            downloaded_pdf_count += 1

        parsed_markdown_path = paper.get("parsed_markdown_path")
        has_parsed_markdown = bool(
            parsed_markdown_path and nonempty_file(workspace / str(parsed_markdown_path))
        )
        if has_parsed_markdown:
            parsed_markdown_count += 1

        metadata = read_json(
            workspace / "library" / "metadata" / f"{paper['paper_id']}.json",
            default={},
        ) or {}
        text_source = str(metadata.get("text_source") or "")
        note_path = workspace / "library" / "notes" / f"{paper['paper_id']}.md"
        if not note_path.exists():
            continue
        if has_parsed_markdown and text_source and not text_source.startswith("abstract"):
            notes_from_parsed_markdown += 1
        elif text_source == "pdf":
            notes_from_pdf_text += 1
        elif text_source.startswith("abstract") or text_source == "":
            notes_from_abstract_fallback += 1
        else:
            notes_with_unknown_source += 1

    parse_success_rate = (
        parsed_markdown_count / downloaded_pdf_count if downloaded_pdf_count else 0.0
    )
    return {
        "selected_count": len(selected),
        "downloaded_pdf_count": downloaded_pdf_count,
        "parsed_markdown_count": parsed_markdown_count,
        "parse_success_rate": round(parse_success_rate, 4),
        "notes_from_parsed_markdown": notes_from_parsed_markdown,
        "notes_from_pdf_text": notes_from_pdf_text,
        "notes_from_abstract_fallback": notes_from_abstract_fallback,
        "notes_with_unknown_source": notes_with_unknown_source,
    }


def note_quality_metrics(workspace: Path, selected: list[dict[str, Any]]) -> dict[str, int]:
    notes_with_parsed_evidence = 0
    metadata_only_notes = 0
    missing_notes = 0
    for paper in selected:
        note_path = workspace / "library" / "notes" / f"{paper['paper_id']}.md"
        if not note_path.exists():
            missing_notes += 1
            continue
        text = note_path.read_text(encoding="utf-8")
        if "Source: parsed-full-text" in text:
            notes_with_parsed_evidence += 1
        elif "Metadata / Abstract-Derived Content" in text or "abstract fallback" in text:
            metadata_only_notes += 1
    return {
        "notes_with_parsed_full_text_evidence": notes_with_parsed_evidence,
        "metadata_only_notes": metadata_only_notes,
        "missing_notes": missing_notes,
    }


def unsupported_generic_claims(report_text: str) -> list[str]:
    unsupported: list[str] = []
    for line in report_text.splitlines():
        clean = line.strip()
        if not clean or clean.startswith(("#", "|", "- [p-", "## References")):
            continue
        lower = clean.lower()
        if "[p-" in lower:
            continue
        if any(pattern in lower for pattern in GENERIC_UNSUPPORTED_PATTERNS):
            unsupported.append(clean[:180])
    return unsupported


def report_reference_metrics(report_text: str) -> dict[str, int]:
    refs = re.findall(r"\[p-[a-f0-9]{12}\]", report_text)
    return {
        "paper_reference_count": len(refs),
        "unique_paper_reference_count": len(set(refs)),
        "unsupported_generic_claim_count": len(unsupported_generic_claims(report_text)),
    }


def evidence_quality_metrics(workspace: Path) -> dict[str, Any]:
    evidence_path = workspace / "knowledge" / "evidence_table.json"
    evidence_md = workspace / "knowledge" / "evidence_table.md"
    if not evidence_path.exists() or not evidence_md.exists():
        return {
            "exists": False,
            "total_snippets": 0,
            "high_quality_snippets": 0,
            "low_score_snippets": 0,
            "unknown_section_snippets": 0,
            "noise_section_snippets": 0,
            "low_score_ratio": 0.0,
            "unknown_section_ratio": 0.0,
            "noise_section_ratio": 0.0,
            "themes_without_paper_specific_support": [],
            "section_counts": {},
        }

    evidence = read_json(evidence_path, default={}) or {}
    rows = evidence.get("themes") or []
    if not isinstance(rows, list):
        rows = []

    section_counts: Counter[str] = Counter()
    total = 0
    high_quality = 0
    low_score = 0
    unknown_section = 0
    noise_section = 0
    themes_without_support: list[str] = []
    noise_sections = {"References", "Bibliography", "Appendix", "Prompt", "Code", "Tables"}

    for row in rows:
        snippets = row.get("evidence_snippets_or_sections") or []
        has_support = False
        for item in snippets:
            total += 1
            section = str(item.get("section") or "Unknown")
            section_counts[section] += 1
            score = float(item.get("snippet_score") or 0.0)
            flags = set(str(flag) for flag in item.get("quality_flags") or [])
            if score >= 0.45 and item.get("paper_id"):
                has_support = True
            if score >= 0.65:
                high_quality += 1
            if score < 0.35:
                low_score += 1
            if section == "Unknown" or "unknown_section" in flags:
                unknown_section += 1
            if section in noise_sections or "noise_section" in flags:
                noise_section += 1
        if not has_support:
            themes_without_support.append(str(row.get("theme") or "unknown"))

    denominator = max(1, total)
    return {
        "exists": True,
        "total_snippets": total,
        "high_quality_snippets": high_quality,
        "low_score_snippets": low_score,
        "unknown_section_snippets": unknown_section,
        "noise_section_snippets": noise_section,
        "low_score_ratio": round(low_score / denominator, 4),
        "unknown_section_ratio": round(unknown_section / denominator, 4),
        "noise_section_ratio": round(noise_section / denominator, 4),
        "themes_without_paper_specific_support": themes_without_support,
        "section_counts": dict(sorted(section_counts.items())),
    }


def audit_workspace(workspace: Path) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []

    required_files = [
        "research_plan.json",
        "research_plan.md",
        "data/raw_results.jsonl",
        "data/papers.jsonl",
        "data/selected_papers.jsonl",
        "knowledge/base_knowledge.md",
        "knowledge/topic_map.md",
        "knowledge/index.md",
        "logs/downloads.jsonl",
    ]
    for relative_path in required_files:
        if not (workspace / relative_path).exists():
            issues.append(f"Missing required file: {relative_path}")

    plan = read_json(workspace / "research_plan.json", default={}) or {}
    for field in (
        "topic",
        "goal",
        "core_questions",
        "include_keywords",
        "exclude_keywords",
        "search_queries",
        "date_range",
        "max_results_per_source",
        "selection_count",
        "ranking_policy",
    ):
        if field not in plan:
            issues.append(f"research_plan.json missing field: {field}")

    selected = [
        enrich_paper_role(normalize_paper(paper))
        for paper in read_jsonl(workspace / "data" / "selected_papers.jsonl")
    ]
    if not selected:
        issues.append("No selected papers found.")

    for paper in selected:
        missing = missing_paper_fields(paper)
        if missing:
            issues.append(
                f"{paper.get('paper_id', 'unknown')} missing paper schema fields: {missing}"
            )
        note_path = workspace / "library" / "notes" / f"{paper['paper_id']}.md"
        metadata_path = workspace / "library" / "metadata" / f"{paper['paper_id']}.json"
        if not note_path.exists():
            issues.append(
                f"Missing note for {paper['paper_id']}: {note_path.relative_to(workspace)}"
            )
        if not metadata_path.exists():
            issues.append(
                f"Missing metadata for {paper['paper_id']}: {metadata_path.relative_to(workspace)}"
            )
        if paper.get("download_status") in {"failed", "skipped"}:
            warnings.append(
                f"{paper['paper_id']} PDF download {paper.get('download_status')}: "
                f"{paper.get('download_error') or 'no reason recorded'}"
            )

    parse_quality = parse_quality_metrics(workspace, selected)
    note_quality = note_quality_metrics(workspace, selected)
    downloaded_pdf_count = parse_quality["downloaded_pdf_count"]
    parsed_markdown_count = parse_quality["parsed_markdown_count"]
    notes_from_abstract_fallback = parse_quality["notes_from_abstract_fallback"]

    if downloaded_pdf_count and parsed_markdown_count == 0:
        issues.append(
            "No parsed Markdown files were produced for downloaded selected PDFs; "
            "real-review quality is not acceptable."
        )
    elif downloaded_pdf_count and parsed_markdown_count < downloaded_pdf_count:
        warnings.append(
            f"Parsed Markdown coverage is incomplete: "
            f"{parsed_markdown_count}/{downloaded_pdf_count} downloaded PDFs."
        )

    if notes_from_abstract_fallback:
        warnings.append(
            f"{notes_from_abstract_fallback} notes were generated from abstract fallback; "
            "inspect before using the report as a real review."
        )

    if parsed_markdown_count and note_quality["notes_with_parsed_full_text_evidence"] < max(
        1, parsed_markdown_count // 2
    ):
        warnings.append(
            "Notes appear mostly metadata/abstract-level despite parsed Markdown existing: "
            f"{note_quality['notes_with_parsed_full_text_evidence']}/{parsed_markdown_count} "
            "notes include parsed-full-text evidence."
        )

    report_path = workspace / "reports" / "final_report.md"
    report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    if report_path.exists():
        for section in REQUIRED_REPORT_SECTIONS:
            if f"## {section}" not in report_text:
                issues.append(f"final_report.md missing section: {section}")

        if selected and not re.search(r"\[p-[a-f0-9]{12}\]", report_text):
            issues.append("final_report.md does not include traceable paper_id citations.")
    else:
        warnings.append(
            "final_report.md is missing. This is acceptable only when the workspace is being used "
            "as a literature management workbench with field maps, matrices, "
            "and evidence artifacts."
        )

    missing_workspace_artifacts = [
        relative_path
        for relative_path in WORKSPACE_ARTIFACTS
        if not (workspace / relative_path).exists()
    ]
    if missing_workspace_artifacts:
        warnings.append(
            "Research workspace artifacts are incomplete: "
            + ", ".join(missing_workspace_artifacts)
        )

    counts_by_role = role_counts(selected)
    technical_count = counts_by_role.get("technical_method", 0) + counts_by_role.get(
        "system_paper", 0
    )
    if selected and technical_count < max(1, len(selected) // 3):
        warnings.append(
            "Technical/system paper count may be insufficient for technical frontier tracking: "
            f"{technical_count}/{len(selected)}."
        )

    evidence_json = workspace / "knowledge" / "evidence_table.json"
    evidence_md = workspace / "knowledge" / "evidence_table.md"
    evidence_quality = evidence_quality_metrics(workspace)
    if not evidence_json.exists() or not evidence_md.exists():
        warnings.append(
            "Evidence table is missing; run `litagent build-evidence WORKSPACE --json`."
        )
    elif evidence_quality["total_snippets"] == 0 and selected:
        issues.append("Evidence table exists but contains no usable evidence snippets.")
    else:
        if evidence_quality["unknown_section_ratio"] > 0.4:
            warnings.append(
                "Evidence table has a high unknown-section ratio: "
                f"{evidence_quality['unknown_section_ratio']:.0%}."
            )
        if evidence_quality["noise_section_ratio"] > 0.25:
            warnings.append(
                "Evidence table contains many snippets from low-priority/noise sections: "
                f"{evidence_quality['noise_section_ratio']:.0%}."
            )
        if evidence_quality["low_score_ratio"] > 0.5:
            warnings.append(
                "Evidence table has a high low-score snippet ratio: "
                f"{evidence_quality['low_score_ratio']:.0%}."
            )
        unsupported_themes = evidence_quality["themes_without_paper_specific_support"]
        if len(unsupported_themes) > 2:
            warnings.append(
                "Several evidence themes lack enough paper-specific support: "
                + ", ".join(unsupported_themes[:5])
            )
        if evidence_quality["high_quality_snippets"] and "score=" not in report_text:
            warnings.append(
                "Final report does not appear to expose evidence scores from the evidence table."
            )

    report_metrics = report_reference_metrics(report_text)
    if (
        report_path.exists()
        and selected
        and report_metrics["unique_paper_reference_count"] < min(len(selected), 5)
    ):
        warnings.append(
            "Final report has too few unique paper-specific references: "
            f"{report_metrics['unique_paper_reference_count']}/{len(selected)}."
        )
    if report_metrics["unsupported_generic_claim_count"]:
        warnings.append(
            "Final report contains generic claims without nearby paper support: "
            f"{report_metrics['unsupported_generic_claim_count']} candidate lines."
        )

    result = {
        "passed": not issues,
        "issues": issues,
        "warnings": warnings,
        "selected_count": len(selected),
        "parse_quality": parse_quality,
        "note_quality": note_quality,
        "report_quality": report_metrics,
        "evidence_quality": evidence_quality,
        "research_workspace_quality": {
            "paper_role_counts": counts_by_role,
            "technical_or_system_count": technical_count,
            "missing_workspace_artifacts": missing_workspace_artifacts,
        },
    }
    write_audit_report(workspace, result)
    return result


def write_audit_report(workspace: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Audit Report",
        "",
        f"Status: {'PASS' if result['passed'] else 'FAIL'}",
        f"Selected papers: {result.get('selected_count', 0)}",
        f"Downloaded PDFs: {result.get('parse_quality', {}).get('downloaded_pdf_count', 0)}",
        f"Parsed Markdown files: {result.get('parse_quality', {}).get('parsed_markdown_count', 0)}",
        f"Parse success rate: {result.get('parse_quality', {}).get('parse_success_rate', 0.0):.0%}",
        (
            "Notes from parsed Markdown: "
            f"{result.get('parse_quality', {}).get('notes_from_parsed_markdown', 0)}"
        ),
        (
            "Notes from abstract fallback: "
            f"{result.get('parse_quality', {}).get('notes_from_abstract_fallback', 0)}"
        ),
        (
            "Notes with parsed full-text evidence: "
            f"{result.get('note_quality', {}).get('notes_with_parsed_full_text_evidence', 0)}"
        ),
        (
            "Unique paper references in report: "
            f"{result.get('report_quality', {}).get('unique_paper_reference_count', 0)}"
        ),
        (
            "Evidence snippets: "
            f"{result.get('evidence_quality', {}).get('total_snippets', 0)}"
        ),
        (
            "High-quality evidence snippets: "
            f"{result.get('evidence_quality', {}).get('high_quality_snippets', 0)}"
        ),
        (
            "Unknown-section evidence ratio: "
            f"{result.get('evidence_quality', {}).get('unknown_section_ratio', 0.0):.0%}"
        ),
        (
            "Low-score evidence ratio: "
            f"{result.get('evidence_quality', {}).get('low_score_ratio', 0.0):.0%}"
        ),
        (
            "Paper role counts: "
            f"{result.get('research_workspace_quality', {}).get('paper_role_counts', {})}"
        ),
        (
            "Missing research workspace artifacts: "
            f"{result.get('research_workspace_quality', {}).get('missing_workspace_artifacts', [])}"
        ),
        "",
        "## Issues",
        "",
    ]
    issues = result.get("issues") or []
    lines.extend(f"- {issue}" for issue in issues)
    if not issues:
        lines.append("- None")

    lines.extend(["", "## Warnings", ""])
    warnings = result.get("warnings") or []
    lines.extend(f"- {warning}" for warning in warnings)
    if not warnings:
        lines.append("- None")
    lines.append("")

    path = workspace / "logs" / "audit_report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
