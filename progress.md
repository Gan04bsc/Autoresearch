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
- Ran the small v2 real review in `./demo-real-v2` for `多智能体文献综述自动化工具` with search run
  `demo-real-v2-initial`.
- Real search returned 111 raw records and 94 deduplicated papers from arXiv/OpenAlex; Semantic
  Scholar was attempted but returned HTTP 429 because no API key was configured.
- Calibrated topic-sensitive ranking and review-selection after the run showed sparse high-value
  matches were being diluted by long include-term lists.
- Refined the plan terms for this workspace to include `multi-agent framework`, `citation graph`,
  `hierarchical citation graph`, `paper-reading agents`, `PaperGuide`, and `PaperCompass`, which
  brought PaperGuide into the selected set and removed broad high-citation review papers.
- Final `./demo-real-v2` selection has 8 likely relevant papers, 0 questionable papers, 0 likely
  off-topic papers, and covers survey generation, systematic-review automation, paper-reading
  agents, citation-aware synthesis, and evaluation/benchmarking.
- Download and local pypdf parse succeeded for 8/8 selected papers; notes used parsed Markdown for
  8/8 with 0 abstract fallback.
- Manually strengthened `./demo-real-v2/reports/final_report.md` using parsed Markdown evidence so
  it reads as a roadmap-style synthesis instead of only a deterministic template.
- `litagent inspect-workspace ./demo-real-v2 --json` labels the workspace `small_real_review`.
- Improved the deterministic reader so notes separate metadata/abstract content from parsed
  full-text evidence across problem, method, agent roles, pipeline stages, retrieval/search,
  citation/evidence handling, evaluation, datasets/benchmarks, findings, limitations, and relevance.
- Added `litagent build-evidence WORKSPACE --json` and MCP tool `litagent_build_evidence`.
  Evidence artifacts are written to `knowledge/evidence_table.md` and
  `knowledge/evidence_table.json`.
- Updated the pipeline to run `build-evidence` after `build-knowledge` and before report
  generation.
- Updated report generation to use paper notes, knowledge outputs, and the evidence table for
  explicit claim-to-paper support, synthesis themes, comparison tables, design implications,
  roadmap, and remaining evidence gaps.
- Audit and `inspect-workspace` now warn when the evidence table is missing, notes remain
  abstract-level despite parsed Markdown, reports have too few unique paper references, or generic
  claims appear without paper support.
- Ran the broader small real review in `./demo-real-v3` for `多智能体文献综述自动化工具` with search
  run `demo-real-v3-initial`.
- `./demo-real-v3` produced 382 raw results, selected 12 relevant papers, downloaded 12/12 legal
  open PDFs, parsed 12/12 PDFs with local pypdf, generated 12 notes from parsed Markdown, generated
  `knowledge/evidence_table.md` and `knowledge/evidence_table.json`, passed audit, and was labeled
  `small_real_review` by `inspect-workspace`.
- Semantic Scholar was attempted during `./demo-real-v3` but was effectively unavailable without
  `SEMANTIC_SCHOLAR_API_KEY`; the run remains arXiv/OpenAlex dominated and should not be treated as
  `source_diverse_real_review`.
- Completed a stage-convergence pass that defines the current phase as `small_real_review`
  prototype and the next phase as evidence-quality enhancement, Chinese research-grade synthesis,
  and source-diversity validation.
- Added project-level documentation for Codex / Agent vs. `litagent` responsibility boundaries,
  Chinese output policy, quality labels, regression checks, and the next-stage roadmap.
- Implemented the first evidence-quality enhancement slice: section-aware evidence extraction,
  snippet cleaning, `snippet_score`, `snippet_score_explanation`, and `quality_flags`.
- Updated `knowledge/evidence_table.json` and `knowledge/evidence_table.md` so evidence is grouped
  by theme and each snippet records section, score, confidence, quality flags, and uncertainty.
- Updated `litagent report` to produce a Chinese draft report by default and use high-score
  evidence snippets for paper-specific synthesis instead of writing low-score noise into the body.
- Updated `audit` and `inspect-workspace` to report evidence-quality signals such as unknown
  sections, low-score evidence ratio, noise sections, and themes without enough paper-specific
  support.
- Froze the `./demo-real-v3` evidence-quality regression baseline after commit `06207a4 Improve
  evidence quality scoring`: 12 selected papers, 12/12 local pypdf parse, 0 abstract fallback,
  93 evidence snippets, 85 high-quality snippets, 0% unknown-section ratio, about 1.1%
  noise-section ratio, about 2.2% low-score ratio, audit PASS, and inspect label
  `small_real_review`.
- Documented that the remaining inspect warning is acceptable for the current baseline: the
  Chinese draft report may still contain generic claims that require Codex / Agent review for
  paper-specific support.
- Added `demo-real-v4` planning guidance without executing it. The next run should validate source
  diversity after `SEMANTIC_SCHOLAR_API_KEY` is configured, using fresh workspace
  `./demo-real-v4`, `max_papers=15`, search run isolation, `review-selection` before download,
  local pypdf first, section-aware evidence scoring, Chinese draft report generation, and Codex /
  Agent secondary synthesis.
- Added Semantic Scholar key configuration support for both the official `x-api-key` path and an
  explicitly configured compatible proxy path using `SEMANTIC_SCHOLAR_API_BASE_URL` plus
  `SEMANTIC_SCHOLAR_API_AUTH_MODE=authorization_bearer`.
- Configured local ignored `.env` with Semantic Scholar credentials for future v4 preparation;
  the real key is not tracked and must not be written to docs or source code.
- Documented v4 failure strategy: if Semantic Scholar still has no effective contribution, or if
  source diversity improves at the cost of relevance or evidence quality, the run must not be
  upgraded to `source_diverse_real_review`.
- Ran `./demo-real-v4` as the source-diversity validation attempt for
  `多智能体文献综述自动化工具` with search run `demo-real-v4-initial`.
- `./demo-real-v4` returned 321 raw results from arXiv/OpenAlex; Semantic Scholar was attempted
  through the configured key/proxy path but contributed 0 usable candidates because every query
  returned HTTP 403 Forbidden.
- After plan/ranking refinement, `review-selection` accepted 15 selected papers as likely relevant
  with 0 questionable and 0 likely off-topic papers; the remaining selection gap is direct
  `paper reading agent` coverage.
- `./demo-real-v4` downloaded 15/15 legal open PDFs, parsed 15/15 PDFs with local pypdf, generated
  15 notes from parsed Markdown, and used 0 abstract fallback notes.
- `./demo-real-v4` generated section-aware evidence artifacts with 84 snippets, 74 high-quality
  snippets, 0% unknown-section ratio, about 1.2% noise-section ratio, and about 3.6% low-score
  ratio.
- `./demo-real-v4` audit passed and `inspect-workspace` labeled the workspace
  `small_real_review`; it must not be upgraded to `source_diverse_real_review` because Semantic
  Scholar had no effective contribution and the selected set remains arXiv/OpenAlex dominated.
- Added `litagent provider-smoke semantic-scholar --json` as a safe minimal Semantic Scholar
  connectivity diagnostic. It requests at most three results, reports `status_code`, `auth_mode`,
  `base_url`, `endpoint`, `key_present`, `error_type`, and `likely_action`, and never prints the
  real API key.
- Improved Semantic Scholar search error logs so 401/403/429 failures include actionable provider
  diagnostics instead of only a raw HTTP error string.
- Documented that `demo-real-v4` should not be retried until the provider smoke test succeeds, and
  that a successful smoke test still does not by itself justify `source_diverse_real_review`.
- Local `litagent provider-smoke semantic-scholar --json` still returns HTTP 403 Forbidden with
  `key_present=true`, `auth_mode=authorization_bearer`, and the configured custom proxy base URL;
  this indicates the next step is checking the key/proxy permission or auth/path expectations
  outside the literature-review pipeline.
- Switched the local ignored `.env` from the failed proxy configuration to the official Semantic
  Scholar API configuration: `base_url=https://api.semanticscholar.org` and
  `auth_mode=x-api-key`. The real API key remains local-only and is not tracked.
- Re-ran `litagent provider-smoke semantic-scholar --json` against the official endpoint; it
  succeeded with HTTP 200, `key_present=true`, and one returned sample result, so Semantic Scholar
  provider connectivity is now ready for a controlled v4 retry.
- Re-ran `./demo-real-v4` with the official Semantic Scholar API and new search run
  `demo-real-v4-official-ss`; the run used `--search-scope latest` and did not mix the previous
  failed `demo-real-v4-initial` search results.
- The official v4 run returned 801 raw results: arXiv 19, OpenAlex 361, and Semantic Scholar 421.
  Semantic Scholar contributed effective candidates and entered the selected set.
- After ranking refinement to remove off-topic smart-city, financial-application, climate-scenario,
  and generic assisted-systematic-review items, final `review-selection` accepted 15 selected
  papers with 0 questionable, 0 likely off-topic, and no missing subtopics.
- Final official v4 selected-paper source distribution was arXiv 10, OpenAlex 5, and Semantic
  Scholar 12 after dedup/source merging. Two selected papers were primary Semantic Scholar-only
  discoveries, and several arXiv/OpenAlex papers gained Semantic Scholar metadata/citation support.
- Official v4 downloaded 15/15 legal open PDFs, parsed 15/15 with local pypdf, generated 15 notes
  from parsed Markdown, and used 0 abstract fallback notes.
- Official v4 generated 93 evidence snippets, 80 high-quality snippets, 0% unknown-section ratio,
  about 1.1% noise-section ratio, and about 3.2% low-score ratio.
- Official v4 audit passed and `inspect-workspace` labeled the workspace
  `source_diverse_real_review`. The remaining warning is that the Chinese draft report still has
  2 candidate generic lines requiring Codex / Agent review before treating it as final research
  synthesis.
- Corrected the project direction from “automatic final literature-review writer” to a research
  literature workspace for literature discovery, classification, management, field mapping,
  technical-frontier tracking, evidence management, research-gap discovery, innovation clues, and
  Chinese research materials.
- Documented that `reports/final_report.md` is an optional display artifact, not the core endpoint.
- Added dual paper classification signals: `paper_role` and `reading_intent`.
- Added role-aware knowledge outputs from `build-knowledge`: `field_map.md`,
  `technical_frontier.md`, `method_matrix.md`, `benchmark_matrix.md`,
  `innovation_opportunities.md`, and `reading_plan.md`.
- Added `litagent export-wiki WORKSPACE --format autowiki --out OUT_DIR` and MCP tool
  `litagent_export_wiki` for an AutoWiki-compatible Markdown + JSON vault export. The exporter
  uses existing workspace artifacts only and does not call network, download, or parse.
- Added AutoWiki-compatible vault pages under `raw/<paper_id>/` and `kb/`, with Obsidian wikilinks,
  paper role routing, source metadata, evidence JSON, field map, technical frontier, method matrix,
  benchmark matrix, innovation opportunities, and reading plan.
- Improved the AutoWiki-compatible export after Obsidian usability review: vaults now include
  `START_HERE.md`, `kb/source-index.md`, `kb/evidence-index.md`, visible `kb/sources/<paper_id>.md`
  article quick-read pages, `kb/notes/note-<paper_id>.md` full notes, and
  `kb/evidence/evidence-<paper_id>.md` Markdown evidence pages. `raw/` is now clearly treated as an
  archive layer rather than the primary reading surface.
- Generated an improved non-hidden Obsidian vault at `workspace/wiki-vault-v4` from existing
  `./demo-real-v4` artifacts. This vault has visible maps, source summaries, full notes, and
  Markdown evidence pages, and should be opened from `START_HERE.md`.
- Updated `audit` and `inspect-workspace` to emit research-workspace quality signals for missing
  field maps, technical frontier pages, matrices, innovation opportunities, reading plans, role
  distributions, technical/system paper coverage, survey dominance, and background/application
  over-weight.

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
- Passed: `litagent review-selection ./demo-real-v2 --json`; it reported 8 likely relevant papers,
  0 questionable papers, 0 likely off-topic papers, and no missing subtopics.
- Passed: `litagent download ./demo-real-v2` downloaded 8/8 legal open PDFs.
- Passed: `litagent parse ./demo-real-v2 --mineru-mode off` parsed 8/8 PDFs with local pypdf.
- Passed: `litagent audit ./demo-real-v2` after manual report improvement.
- Passed: `litagent inspect-workspace ./demo-real-v2 --json`; it reports `small_real_review`,
  100% parse success, 8 notes from parsed Markdown, and 0 abstract fallback notes.
- Passed: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider` with 34 tests after
  relevance/review/inspect calibration.
- Passed: `RUFF_CACHE_DIR=/tmp/litagent-ruff-cache ruff check .` after relevance/review/inspect
  calibration.
- Passed: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider` with 39 tests after
  evidence-table, reader, report, audit, and inspect updates.
- Passed: `RUFF_CACHE_DIR=/tmp/litagent-ruff-cache ruff check .` after evidence-grounding
  updates.
- Passed: non-network validation on `./demo-real-v2`: `litagent read`, `litagent build-knowledge`,
  `litagent build-evidence --json`, `litagent report`, `litagent audit`, and
  `litagent inspect-workspace --json`. Inspect reports `small_real_review`, 8/8 parsed Markdown,
  8/8 notes with parsed full-text evidence, 0 abstract fallback notes, and no quality concerns.
- Passed: `litagent review-selection ./demo-real-v3 --json` after plan refinement; it reported
  12 likely relevant papers, 0 questionable papers, 0 likely off-topic papers, and no missing
  subtopics.
- Passed: `litagent audit ./demo-real-v3`; audit reports 12 selected papers, 12 PDFs, 12 parsed
  Markdown files, 100% parse success, 12 notes from parsed Markdown, 0 abstract fallback notes, and
  12 unique paper references in the report.
- Passed: `litagent inspect-workspace ./demo-real-v3 --json`; it reports `small_real_review`,
  evidence table present, audit passed, 12/12 parsed Markdown, and no parse/report/audit concerns.
- Passed: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider` with 39 tests after
  the stage-convergence documentation update.
- Passed: `RUFF_CACHE_DIR=/tmp/litagent-ruff-cache ruff check .` after the stage-convergence
  documentation update.
- Passed: non-network validation on `./demo-real-v3` after evidence-quality updates:
  `litagent read`, `litagent build-knowledge`, `litagent build-evidence --json`,
  `litagent report`, `litagent audit`, and `litagent inspect-workspace --json`.
- `./demo-real-v3` still labels as `small_real_review`; inspect reports 12/12 parsed Markdown,
  12 notes from parsed Markdown, 0 abstract fallback, 93 evidence snippets, 85 high-quality
  snippets, 0% unknown-section ratio, about 1.1% noise-section ratio, and audit PASS.
- Passed: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider` with 42 tests after
  evidence-quality updates.
- Passed: `RUFF_CACHE_DIR=/tmp/litagent-ruff-cache ruff check .` after evidence-quality updates.
- Passed: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider` with 42 tests after
  freezing the `./demo-real-v3` evidence-quality baseline and documenting `./demo-real-v4`
  acceptance criteria.
- Passed: `RUFF_CACHE_DIR=/tmp/litagent-ruff-cache ruff check .` after the baseline-freeze
  documentation update.
- Passed: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider` with 45 tests after
  Semantic Scholar key/proxy configuration support and v4 preflight documentation.
- Passed: `RUFF_CACHE_DIR=/tmp/litagent-ruff-cache ruff check .` after Semantic Scholar
  configuration support.
- Passed: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider` with 52 tests after
  provider smoke diagnostics.
- Passed: `RUFF_CACHE_DIR=/tmp/litagent-ruff-cache ruff check .` after provider smoke diagnostics.
- Ran: `litagent provider-smoke semantic-scholar --json`; it safely reported HTTP 403 without
  printing the real API key.
- Ran: `litagent provider-smoke semantic-scholar --json` after switching to the official Semantic
  Scholar API configuration; it safely reported HTTP 200 without printing the real API key.
- Passed: `litagent inspect-workspace ./demo-real-v4 --json` after adding research-workspace
  quality signals; it still labels the workspace `source_diverse_real_review`.
- Passed: `litagent build-knowledge ./demo-real-v4` as a non-network refresh of the new field map,
  technical frontier, matrices, innovation opportunities, and reading plan artifacts.
- Passed: `litagent export-wiki ./demo-real-v4 --format autowiki --out .tmp/wiki-vault-v4 --json`;
  it exported 15 papers with role distribution `system_paper=8`, `survey_or_review=4`,
  `technical_method=1`, `benchmark_or_dataset=1`, and `position_or_perspective=1`.
- Passed: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider` with 56 tests after
  research-workspace repositioning and AutoWiki-compatible export.
- Passed: `RUFF_CACHE_DIR=/tmp/litagent-ruff-cache ruff check .` after research-workspace
  repositioning and AutoWiki-compatible export.
- Passed: `litagent export-wiki ./demo-real-v4 --format autowiki --out workspace/wiki-vault-v4 --json`
  after Obsidian usability fixes.
- Passed: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider` with 56 tests after
  Obsidian-friendly vault export fixes.
- Passed: `RUFF_CACHE_DIR=/tmp/litagent-ruff-cache ruff check .` after Obsidian-friendly vault
  export fixes.
- Synced `/app/AutoWiki-skill/skills/autowiki/` into the Codex `autowiki` skill directory and
  recompiled `./demo-real-v4` into an AutoWiki-style vault at `/app/workspace/autowiki-v4`.
- The new vault is not the deterministic `export-wiki` template output. It uses Codex/AutoWiki
  synthesis to create milestone topics, source analysis pages, Relations, Critical Analysis,
  evidence pages, notes, and an innovation roadmap.
- Added an Obsidian entry point for the new vault: `/app/workspace/autowiki-v4/START_HERE.md`.
- Added a notice in the older `/app/workspace/wiki-vault-v4` template export telling readers to
  use `/app/workspace/autowiki-v4` for the AutoWiki-style knowledge map.
- Re-clarified that `litagent` is a literature reading and management workbench, not a survey
  generation system. Survey papers build field maps, technical/system papers track frontier
  methods and innovation opportunities, and benchmark/dataset papers support evaluation design.
- Updated the project rules so new-field literature workspaces may use 50-70 high-quality papers
  when justified, with preference for top venues/journals, highly cited foundations, authoritative
  technical reports, major benchmarks, and reproducible systems.
- Ran a new-field MLLM literature workspace in `./demo-mllm-workspace` for
  `多模态大模型文献阅读与技术前沿`, using real API search and a curated high-quality 67-paper
  selection rather than forcing a 15-paper cap.
- The MLLM run produced 3536 raw results across arXiv, OpenAlex, and Semantic Scholar; selected
  papers cover 2 survey papers, 55 technical/system papers, and 10 benchmark papers after
  role-aware reclassification.
- Download and local pypdf parsing succeeded for 67/67 selected papers, notes used parsed Markdown
  for 67/67, and abstract fallback remained 0.
- Fixed reader performance for 50-70 paper workspaces by reusing sectioned Markdown units per
  paper and avoiding expensive snippet scoring before keyword matches.
- Fixed a catastrophic regex slow path in evidence snippet cleaning for PDF layout artifacts such
  as dense numeric table/figure strings.
- Corrected classifier behavior so `vision` no longer makes visual-language model papers
  `position`, technical papers are not demoted to benchmark/dataset only because the abstract
  mentions a benchmark, and rerunning `classify` overwrites stale `paper_role` values.
- Updated evidence table generation to derive themes from `research_plan.json` coverage targets,
  filter evidence by paper role, and skip strict theme snippets with weak theme matches.
- `./demo-mllm-workspace` evidence table now has 69 snippets, 65 high-quality snippets,
  0% unknown-section ratio, 0% noise-section ratio, and 0% low-score ratio.
- `litagent inspect-workspace ./demo-mllm-workspace --json` now labels the run
  `source_diverse_real_review`; the remaining report warning is acceptable because
  `final_report.md` is only an optional display artifact.
- Exported an AutoWiki-compatible Obsidian vault to `workspace/mllm-autowiki` and then rewrote
  the key pages with Codex synthesis: `START_HERE.md`, `field-map.md`,
  `technical-frontier.md`, `method-matrix.md`, `benchmark-matrix.md`,
  `innovation-opportunities.md`, `reading-plan.md`, and `index.md`.
- Verified the generated MLLM vault has 355 Markdown files and 0 missing Obsidian wikilinks.
- Added `litagent topic-run` as the first backend-service milestone for Autoresearch. It
  orchestrates `plan -> search -> dedup -> review-selection -> download -> parse -> classify ->
  read -> build-knowledge -> build-evidence -> export-wiki -> audit -> inspect-workspace`
  without making `final_report.md` the core endpoint.
- `topic-run` writes root-level execution artifacts: `run_state.json`, `run_log.jsonl`,
  `artifacts_manifest.json`, and `errors.json`. Each step records status, input count, output
  count, failed count, and timestamps so later OpenClaw/mobile status can read deterministic
  progress instead of scraping console output.
- `topic-run` supports failure recovery by skipping previously succeeded steps by default,
  `--force` to rerun all steps, and `--from-step` to rerun a step plus downstream steps.
- `topic-run` defaults to local pypdf parsing through `--mineru-mode off`; MinerU remains an
  explicit opt-in for OCR-heavy, table-heavy, or complex-layout PDFs.
- Added the first global library MVP with `litagent sync-library` and `litagent library-status`.
  The SQLite `library.db` separates global `papers` from topic-specific `topic_papers`, stores
  `topics`, `runs`, and `evidence_spans`, and keeps evidence attached to both paper and topic.
- Added MCP tools `litagent_sync_library` and `litagent_library_status` so Codex can sync an
  inspected workspace into the long-term library without running network, download, or parse.
- Added the first local job queue MVP with `litagent job create/status/list/cancel/logs/run-next`.
  Jobs are stored in SQLite `jobs.db`, only run whitelisted `topic-run` payloads, and can sync
  successful workspaces into `library.db` via `--sync-library`.
- Added MCP tools for local jobs: `litagent_job_create`, `litagent_job_status`,
  `litagent_job_list`, `litagent_job_cancel`, `litagent_job_logs`, and
  `litagent_job_run_next`.
- Added the first OpenClaw-compatible Autoresearch skill draft at
  `openclaw/skills/autoresearch/SKILL.md`. It maps `/research ...` style mobile/QQ bot
  requests to safe `litagent job` commands only, and explicitly forbids arbitrary shell.
- Added `docs/openclaw_integration.md` to document host-side OpenClaw/QQ bot verification.
  The current `/app` container cannot directly confirm the user's host OpenClaw/QQ bot instance,
  so setup must be verified on the host with `openclaw health`, `openclaw config validate`,
  and skill/channel checks.
- Documented the second OpenClaw integration failure mode: `SKILL.md` can teach the agent how to
  handle `/research ...`, but it does not by itself expose `litagent` as an executable tool.
  OpenClaw needs either a safe command bridge/native command mapping or a tightly scoped
  `coding-agent` fallback that runs only whitelisted commands such as
  `litagent library-status --json`.
- Diagnosed the host OpenClaw `/research library` integration after `tools.catalog` showed
  `exec`/`process`, gateway approvals were installed, and `litagent library-status --json`
  succeeded locally while approval `Last Used` stayed `unknown`. This means the QQ agent turn did
  not actually issue an `exec` tool call.
- Hardened `openclaw/skills/autoresearch/SKILL.md` so `/research library` is a command entrypoint:
  when `exec` is available it must run `litagent library-status --json` before replying, and it is
  forbidden to send placeholder text such as “我先帮你查” without command results.
- Mirrored the `/research library` exec requirement into the skill frontmatter `description`,
  because OpenClaw session snapshots include the skill description before the model decides
  whether to read the full `SKILL.md` file.
- Updated `docs/openclaw_integration.md` with the “skill understood but only placeholder reply”
  failure mode and the exact verification signal: approvals `Last Used` should change and logs
  should contain `exec` / `litagent` records after a successful run.

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
- There is no LLM-backed reader yet. Notes and reports now use parsed-Markdown evidence with
  section and score signals, but extraction is still deterministic and can miss subtle context.
- `./demo-real-v3` remains the regression baseline for checking whether section-aware scoring
  reduces references, headers, captions, prompts, code, tables, and layout artifacts.
- Current deterministic `litagent report` is now a Chinese draft report, but it is still not final
  scholarly judgment. Final user-facing research synthesis should be reviewed and strengthened by
  Codex / Agent.
- Historical `./demo-agent-mock` logs still contain the earlier 5 local parse skips from before `pypdf` was installed, but rerunning download/parse/read/report/audit produced 5/5 parsed Markdown files and notes from parsed Markdown.
- Semantic Scholar returned 429 during `./demo-real-v2` without an API key, so the next real run
  should set `SEMANTIC_SCHOLAR_API_KEY` when available and treat OpenAlex dominance as a warning
  to inspect.
- Local pypdf parsing works for text PDFs but is not sufficient for complex layout, OCR-heavy, or
  table-heavy papers; reserve MinerU for those cases.

## Next Task

Do not expand to larger real reviews yet. Next work should focus on backend reliability and
research workspace quality:

1. Verify the host OpenClaw/QQ bot configuration outside the `/app` container and append
   `openclaw/skills` to the actual host skill path.
2. Add a safe OpenClaw command bridge/native command mapping for `/research library`,
   `/research list`, `/research status <job_id>`, and `/research run-next`, or explicitly use a
   constrained `coding-agent` fallback for one command at a time.
3. Stabilize `topic-run`、`sync-library` and `job` as local backend primitives before giving
   OpenClaw real tasks.
4. Use `./demo-real-v3` as the evidence-quality regression baseline.
5. Use `./demo-real-v4` as the source-diversity regression baseline.
6. Validate the new AutoWiki-compatible export on existing workspaces before connecting it to a
   real Obsidian/AutoWiki maintenance workflow.
7. Treat `litagent export-wiki` as artifact packaging only; use Codex/AutoWiki skill for actual
   milestone/topic/source synthesis.
8. Improve field maps, method matrices, benchmark matrices, and innovation opportunities before
   further optimizing `final_report.md`.
9. Keep AutoWiki-skill as the wiki organization layer; do not let it replace litagent search,
   download, parse, or evidence extraction.

