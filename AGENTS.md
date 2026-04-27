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
3. Run or call search tools.
4. Inspect result quality before accepting Top N.
5. Revise search terms if results are too broad, too narrow, stale, duplicated, or low quality.
6. Deduplicate and select papers.
7. Download only legal open PDFs.
8. Parse PDFs through MinerU or documented fallback.
9. Inspect parsing and download failures.
10. Read notes and parsed Markdown.
11. Build knowledge files.
12. Draft or revise the final report.
13. Run audit.
14. Run `litagent inspect-workspace WORKSPACE --json` when available to judge whether the
    workspace is only smoke-test quality or ready for real-review use.
15. Fix issues before final response.

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
  papers look weak, or the report reads like a shallow metadata summary, Codex must flag that and
  improve the workspace before treating the output as a real literature review.

## Development Commands

- Install: `pip install -e ".[dev]"`
- Test: `pytest`
- Lint: `ruff check .`
- MCP server: `litagent-mcp`
- Inspect: `litagent inspect-workspace WORKSPACE --json`

## Definition of Done

- Tests pass.
- CLI or MCP command is documented.
- Output files match the PRD schema.
- Errors are logged without crashing the whole pipeline.
- Agent-facing status/audit/inspection output is sufficient for Codex to decide the next step.
- Parse quality is visible: selected paper count, downloaded PDF count, parsed Markdown count,
  parse success rate, and note source counts are reported.
