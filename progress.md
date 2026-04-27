# Progress

## Completed

- [x] Milestone 1: Project skeleton
- [x] Milestone 2: Research planner
- [x] Milestone 3: Search providers
- [x] Milestone 4: Dedup & ranking
- [x] Milestone 5: PDF download
- [x] Milestone 6: PDF parsing
- [x] Milestone 7: Paper classification
- [x] Milestone 8: Paper reader
- [x] Milestone 9: Knowledge builder
- [x] Milestone 10: Final report
- [x] Milestone 11: Audit
- [x] Milestone 12: End-to-end CLI

## Current Notes

- Added a minimal Python package under `src/litagent`.
- Added `litagent init WORKSPACE` to create the PRD workspace directories and starter config/prompt files.
- Added `litagent plan "topic" --workspace WORKSPACE` with deterministic `research_plan.json` and `research_plan.md`.
- Added mockable search provider interfaces and mappings for arXiv, Semantic Scholar, and OpenAlex.
- Added deterministic offline mock results for `litagent search --mock` and `litagent run --mock`.
- Added DOI/arXiv/title deduplication, scoring, ranking, and `selected_papers.jsonl` generation.
- Added legal open PDF download handling with arXiv URL fallback, Unpaywall DOI lookup, mock PDF support, and download logs.
- Added MinerU-backed PDF parsing through `litagent parse WORKSPACE --mineru-mode auto`.
- Supported MinerU Agent lightweight URL/file parsing and MinerU precision URL/file parsing.
- MinerU precision mode reads `MINERU_API_TOKEN` from the environment or local `.env`; the token is intentionally not stored in tracked project files.
- Added local `.env` loading for `MINERU_API_TOKEN`; environment variables still take precedence.
- Configured `/app/.env` locally for MinerU precision mode. `.env` is ignored by `.gitignore` and should not be committed.
- Parsed Markdown is written to `library/markdown/{paper_id}.md`, metadata is updated under `library/metadata`, and attempts are logged to `logs/parsing.jsonl`.
- Reframed the project in `AGENTS.md` as Codex orchestrator + Python deterministic tool layer + MCP structured tools.
- Added `litagent status WORKSPACE --json` for agent-facing workspace inspection.
- Added a dependency-free stdio MCP server at `python -m litagent.mcp_server`.
- Registered the local Codex MCP server as `litagent` with cwd `/app`.
- Installed the local `litagent-researcher` Codex skill under `~/.codex/skills/litagent-researcher`.
- Added rule-based paper classification with explanation evidence.
- Added Markdown note generation, per-paper metadata JSON, knowledge files, final report, audit report, and runs log.
- Added full pipeline command: `litagent run "topic" --workspace ./demo --max-papers 30 --mock`.
- Added `--mineru-mode off|agent|precision|auto` to `litagent run`; default is `off` to keep mock/dev runs network-free.
- Added `pypdf` as a runtime dependency for local PDF text extraction.
- Improved classifier priority so implemented workbenches/systems classify as `system` and position/agenda papers classify as `position` before broad survey matching.
- Removed standalone `review` as a survey trigger so open-literature-review systems are not classified as surveys solely because they contain that word.
- Added focused real-mode plan terms for `多智能体文献综述自动化工具`, including LLM agents, automated literature review, paper reading agents, citation-aware synthesis, and Chinese equivalents.
- Added topic exclusion terms for generic robotics multi-agent, traffic control, swarm robotics, game theory-only, and reinforcement-learning-only results.
- Added exclusion scoring to reduce rank for papers matching plan exclusion terms.
- Added parse quality metrics to audit output: selected papers, downloaded PDFs, parsed Markdown files, parse success rate, and note source counts.
- Audit now fails when selected papers have downloaded PDFs but zero parsed Markdown files.
- Added `litagent inspect-workspace WORKSPACE --json` and MCP tool `litagent_inspect_workspace` for smoke-test vs real-review quality assessment, search/selection/parse/report/audit concerns, and recommended next action.
- Updated status output to separate current selected-paper parse failures from historical parse log failures.
- Switched the recommended small-run parsing path to local pypdf first; MinerU remains optional for OCR or complex layout extraction.
- Hardened pypdf extraction by replacing invalid Unicode surrogate characters before writing parsed Markdown.
- Improved classifier matching with word-boundary checks and title-first system detection so SurveyGen/LiRA-style generation frameworks classify as `system` instead of survey/dataset/benchmark due to incidental words in names or abstracts.
- Added tests for research plan schema, provider mappings, dedup/ranking, classifier behavior, MinerU API adapters, and end-to-end mock outputs.
- Added Docker Desktop support through `Dockerfile` and `docker-compose.yml`.
- Switched `Dockerfile` to `mcr.microsoft.com/devcontainers/python:1-3.11-bookworm` after Debian apt mirror returned 502 during build.
- Added VS Code Dev Container support through `.devcontainer/devcontainer.json`.
- Dev Container uses the Node.js 22 feature and installs `@openai/codex` so `codex resume` is available inside VS Code's container.
- Dev Container now uses a Docker volume as active `CODEX_HOME=/home/vscode/.codex` and mounts host `%USERPROFILE%\.codex` at `/mnt/host-codex`.
- Added `.devcontainer/sync_codex_from_host.py` and `.devcontainer/sync_codex_to_host.py` to share safe Codex auth/session files without directly reusing Windows SQLite/WAL files.
- Kept the existing `Dockerfile.codex` for optional Codex CLI container usage.
- Used standard-library `argparse` for the first CLI slice so Milestone 1 works before third-party dependencies are installed.
- Continued using the Python standard library for the MVP pipeline. MinerU HTTP calls use injectable transports so tests do not hit external services.
- Ambiguity decision: `litagent run` defaults to `--mineru-mode off` so ordinary tests and mock runs never call a rate-limited external API. Users can opt in with `--mineru-mode auto`, `agent`, or `precision`.
- Security decision: MinerU tokens are read from `MINERU_API_TOKEN` or local `.env`; never commit tokens to source, README, or progress files.
- Ran a stepwise MCP mock literature review in `./demo-agent-mock` for topic `多智能体文献综述自动化工具`, inspecting status, plan, raw results, selected papers, notes, knowledge files, final report, and audit output instead of using the all-in-one pipeline.
- Added search batch isolation: every search run now has a `search_run_id`, `search_created_at`,
  per-run `data/search_runs/{run_id}/raw_results.jsonl`, per-run metadata, and a latest-run pointer.
- Kept `data/raw_results.jsonl` as a compatibility view of the latest search run instead of a
  silent accumulator.
- Updated deduplication so Codex can choose `--search-scope latest`, `all`, or `selected`; the
  default is `latest` to avoid stale refinement results contaminating the current selection.
- Added topic-sensitive v2 ranking with include-keyword overlap, high-value phrase matches,
  negative-term penalties, modest recency/citation/open-PDF signals, and per-paper
  `score_explanation` metadata.
- Added `litagent review-selection WORKSPACE --json` and MCP tool `litagent_review_selection` for
  pre-download relevance review, source/year distributions, missing subtopics, and next-action
  guidance.
- Improved deterministic report generation toward the manually rewritten `demo-real-small` style:
  executive summary, method taxonomy, system comparison, pipeline patterns, multi-agent roles,
  evidence handling, evaluation methods, gaps, design implications, and roadmap.
- Refined `inspect-workspace` quality labels into `smoke_test_run`, `small_real_review`,
  `source_diverse_real_review`, and `production_quality_review`; source imbalance is now a warning
  rather than the sole reason to downgrade a successful small real run.
- Recommended next real run is a new `./demo-real-v2` workspace with Semantic Scholar API key if
  available, local pypdf parsing first, MinerU reserved for OCR/complex-layout/table-heavy PDFs,
  `review-selection` before download, and `inspect-workspace` after audit.

## Validation

- Passed: `PYTHONPATH=src python -m pytest tests -q -p no:cacheprovider`.
- Passed: `python -m py_compile src/litagent/__init__.py src/litagent/cli.py src/litagent/workspace.py tests/test_workspace_init.py`.
- Passed in Docker: `docker compose run --rm litagent sh -lc "pytest -q && ruff check ."`.
- Passed: `pytest -q` with 11 tests.
- Passed: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider` with 11 tests.
- Passed: `RUFF_CACHE_DIR=/tmp/litagent-ruff-cache ruff check .`.
- Passed: `python -m py_compile $(rg --files src/litagent -g '*.py')`.
- Passed: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider` with 14 tests after MinerU integration.
- Passed: `RUFF_CACHE_DIR=/tmp/litagent-ruff-cache ruff check .` after MinerU integration.
- Passed: `python -m py_compile $(rg --files src/litagent -g '*.py')` after MinerU integration.
- Passed: `litagent run "agentic literature review automation" --workspace .tmp/manual-mineru-... --max-papers 3 --mock`.
- Passed: local MinerU token configuration check without printing the token value.
- Passed: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider` with 17 tests after `.env` support.
- Passed: `RUFF_CACHE_DIR=/tmp/litagent-ruff-cache ruff check .` after `.env` support.
- Passed: `python -m py_compile $(rg --files src/litagent -g '*.py')` after `.env` support.
- Passed: direct MCP initialize and tools/list smoke test through `python -m litagent.mcp_server`.
- Passed: `codex mcp get litagent` after registration.
- Passed: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider` with 21 tests after MCP/skill integration.
- Passed: `RUFF_CACHE_DIR=/tmp/litagent-ruff-cache ruff check .` after MCP/skill integration.
- Passed: `python -m py_compile $(rg --files src/litagent -g '*.py')` after MCP/skill integration.
- Passed: MCP stepwise mock review for `./demo-agent-mock` selected 5 papers, downloaded 5 mock PDFs, generated 5 notes, built knowledge files, generated `reports/final_report.md`, and passed audit.
- Passed: `litagent download ./demo-agent-mock && litagent parse ./demo-agent-mock --mineru-mode off && litagent classify ./demo-agent-mock && litagent read ./demo-agent-mock && litagent build-knowledge ./demo-agent-mock && litagent report ./demo-agent-mock && litagent audit ./demo-agent-mock` after adding `pypdf`; local mock parsing produced 5/5 parsed Markdown files.
- Passed: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider` with 26 tests after parse quality, classifier, planner, and inspect-workspace updates.
- Passed: `RUFF_CACHE_DIR=/tmp/litagent-ruff-cache ruff check .` after parse quality, classifier, planner, and inspect-workspace updates.
- Passed: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider` with 29 tests after pypdf surrogate cleaning and classifier title-priority updates.
- Passed: `RUFF_CACHE_DIR=/tmp/litagent-ruff-cache ruff check .` after pypdf surrogate cleaning and classifier title-priority updates.
- Passed: `litagent parse ./demo-real-small --mineru-mode off` parsed 8/8 real PDFs using local pypdf.
- Passed: `litagent audit ./demo-real-small`; audit report shows 8 selected papers, 8 PDFs, 8 parsed Markdown files, and 100% parse success.
- Passed: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider` with 34 tests after v2 search-run, ranking, review-selection, report, and quality-label updates.
- Passed: `RUFF_CACHE_DIR=/tmp/litagent-ruff-cache ruff check .` after v2 updates.
- Passed: `litagent review-selection ./demo-real-small --json`; it found 8 likely relevant papers,
  0 questionable papers, 0 likely off-topic papers, and no missing subtopics.
- Passed: `litagent inspect-workspace ./demo-real-small --json`; it now labels the workspace
  `small_real_review` with 8/8 parsed Markdown, 0 abstract-fallback notes, and only a source
  imbalance search warning.

## Known Issues

- Local `pip install -e ".[dev]"` failed because this machine has SSL/temp-directory permission issues; Docker should isolate this.
- Docker Engine is running under the real Windows user; `docker ps` and `docker compose version` work.
- Docker Desktop UI logs show repeated Electron `/cloud/status/stream` Internal Server Error, but Engine/Compose are usable.
- Old Dev Container instances with `CODEX_HOME=/root/.codex` or a direct host bind at `/home/vscode/.codex` must be rebuilt.
- Sharing `.codex` into a container gives the container access to local Codex credentials/state; only use this with trusted Dockerfiles and trusted dependencies.
- Local `.ruff_cache` and `.pytest_cache` paths are not writable in this environment; use `RUFF_CACHE_DIR=/tmp/litagent-ruff-cache` and `pytest -p no:cacheprovider` when needed.
- Real API calls are implemented but not exercised by tests; tests use provider mapping units and deterministic mock mode.
- DOI PDF lookup through Unpaywall requires `UNPAYWALL_EMAIL` or `LITAGENT_CONTACT_EMAIL`.
- MinerU Agent lightweight API is IP rate-limited; failed or timed-out parses are logged and do not stop the pipeline.
- MinerU precision API requires `MINERU_API_TOKEN`; large/complex PDFs should use `--mineru-mode precision`.
- There is no LLM-backed reader yet; notes and reports are conservative deterministic summaries based on metadata, abstracts, and selected paper IDs.
- Historical `./demo-agent-mock` logs still contain the earlier 5 local parse skips from before `pypdf` was installed, but rerunning download/parse/read/report/audit produced 5/5 parsed Markdown files and notes from parsed Markdown.
- Semantic Scholar can return 429 rate limits without an API key, so the next real run should set a
  Semantic Scholar key when available and treat OpenAlex dominance as a warning to inspect.
- Local pypdf parsing works for text PDFs but is not sufficient for complex layout, OCR-heavy, or
  table-heavy papers; reserve MinerU for those cases.

## Next Task

Run a small v2 real review in `./demo-real-v2` with `max_papers=8`, real API search, Semantic
Scholar API key if available, pypdf local parsing first, `review-selection` before download, and
`inspect-workspace` after audit. Then improve the reader to use parsed Markdown sections more
deeply instead of abstract-heavy deterministic notes.

