# AGENTS.md

You are building `litagent`, a Codex-orchestrated literature research workbench.

Read `prd.md` and `progress.md` first. Implement the product incrementally.

## Role Split

- Codex is the orchestrator and reasoning layer.
- The Python CLI is the deterministic tool layer.
- The MCP server exposes structured litagent tools to Codex.
- Skills / AGENTS.md define how Codex should perform literature research.
- Do not hide core research judgment inside opaque Python heuristics when Codex should inspect,
  revise, and iterate.

## Standard Agent Workflow

1. Understand the user topic and workspace.
2. Create or inspect `research_plan.json`.
3. Run or call search tools. Each search run should be traceable by `search_run_id` under
   `data/search_runs/{run_id}/`; `data/raw_results.jsonl` is only the latest compatibility view.
4. Inspect result quality before accepting Top N.
5. Revise search terms if results are too broad, too narrow, stale, duplicated, or low quality.
6. Deduplicate and select papers with an explicit search scope: latest run, all runs, or selected
   runs. Default to latest unless there is a clear reason to merge multiple refinement rounds.
7. Run `litagent review-selection WORKSPACE --json` before download and inspect likely relevant,
   questionable, and likely off-topic papers.
8. Download only legal open PDFs.
9. Parse PDFs with local pypdf first for ordinary text PDFs; use MinerU only when OCR,
   complex layout extraction, or pypdf quality is insufficient.
10. Inspect parsing and download failures.
11. Read notes and parsed Markdown.
12. Build knowledge files.
13. Build evidence artifacts with `litagent build-evidence WORKSPACE --json`.
14. Draft or revise the final report from paper notes, knowledge files, and the evidence table.
15. Run audit.
16. Run `litagent inspect-workspace WORKSPACE --json` when available to judge whether the
    workspace is only smoke-test quality or ready for real-review use.
17. Fix issues before final response.

## Rules

- Work only inside this repository unless the user explicitly asks for local Codex skill or MCP
  configuration.
- Use small, testable milestones.
- Do not bypass paywalls or scrape copyrighted PDFs illegally.
- Do not use browser automation or Google Scholar scraping.
- Prefer public academic APIs: arXiv, Semantic Scholar, OpenAlex, Crossref, Unpaywall.
- All external API integrations must be mockable in tests.
- Every milestone must include tests.
- Run tests before marking a task complete.
- Update `progress.md` after each iteration.
- Do not delete user files.
- If requirements are ambiguous, make a reasonable decision and document it in `progress.md`.
- Audit passing is not enough by itself. If parsing failed, notes used abstract fallback, selected
  papers look weak, the evidence table is missing, or the report reads like a shallow metadata
  summary without paper-specific support, Codex must flag that and improve the workspace before
  treating the output as a real literature review.

## Development Commands

- Install: `pip install -e ".[dev]"`
- Test: `pytest`
- Lint: `ruff check .`
- MCP server: `litagent-mcp`
- Inspect: `litagent inspect-workspace WORKSPACE --json`
- Selection review: `litagent review-selection WORKSPACE --json`
- Evidence table: `litagent build-evidence WORKSPACE --json`
- Dedup latest search run: `litagent dedup WORKSPACE --search-scope latest --max-papers N`

## Definition of Done

- Tests pass.
- CLI or MCP command is documented.
- Output files match the PRD schema.
- Errors are logged without crashing the whole pipeline.
- Agent-facing status/audit/inspection output is sufficient for Codex to decide the next step.
- Parse quality is visible: selected paper count, downloaded PDF count, parsed Markdown count,
  parse success rate, and note source counts are reported.
- Search refinements are traceable and do not silently mix stale raw results into the latest
  selection.
- Real-review reports use the preferred synthesis path:
  `read -> build-knowledge -> build-evidence -> report -> audit -> inspect-workspace`.
