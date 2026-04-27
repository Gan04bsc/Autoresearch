# Autoresearch

Agentic Literature Research Workbench CLI.

## Local development

```bash
pip install -e ".[dev]"
litagent init ./demo
litagent run "agentic literature review tools" --workspace ./demo --max-papers 10 --mock
pytest
ruff check .
```

If this container cannot write `/app/.ruff_cache`, run lint with
`RUFF_CACHE_DIR=/tmp/litagent-ruff-cache ruff check .`.

## CLI

```bash
litagent init ./my-topic
litagent plan "agentic literature review tools" --workspace ./my-topic
litagent search ./my-topic --mock --run-id first-pass
litagent dedup ./my-topic --max-papers 30 --search-scope latest
litagent review-selection ./my-topic --json
litagent download ./my-topic
litagent parse ./my-topic --mineru-mode auto
litagent classify ./my-topic
litagent read ./my-topic
litagent build-knowledge ./my-topic
litagent build-evidence ./my-topic --json
litagent report ./my-topic
litagent audit ./my-topic
litagent status ./my-topic --json
litagent inspect-workspace ./my-topic --json
litagent run "agentic literature review tools" --workspace ./my-topic --max-papers 30 --mock
litagent run "agentic literature review tools" --workspace ./my-topic --max-papers 30 --mineru-mode auto
```

Use `--mock` for deterministic offline tests. Without `--mock`, search calls the arXiv,
Semantic Scholar, and OpenAlex providers. DOI PDF resolution uses Unpaywall and requires
`UNPAYWALL_EMAIL` or `LITAGENT_CONTACT_EMAIL`; failed downloads are logged and do not stop
the rest of the pipeline.

## Search Runs, Ranking, and Selection Review

Search is isolated by run. Each run writes:

- `data/search_runs/{run_id}/raw_results.jsonl`
- `data/search_runs/{run_id}/metadata.json`
- `data/search_runs/latest.json`

`data/raw_results.jsonl` remains a compatibility view of the latest run. Deduplication defaults to
the latest search run so refinement rounds do not silently accumulate stale results:

```bash
litagent dedup ./my-topic --max-papers 8 --search-scope latest
litagent dedup ./my-topic --max-papers 8 --search-scope all
litagent dedup ./my-topic --max-papers 8 --search-scope selected --search-run-id first-pass
```

The v2 ranking mode combines topic keyword overlap, high-value phrase matches, negative terms,
recency, citation count, and open-PDF availability. Each selected paper stores an explainable
`score_explanation` in `data/selected_papers.jsonl`.

Before download, run:

```bash
litagent review-selection ./my-topic --json
```

This reports likely relevant papers, questionable papers, likely off-topic papers, source/year
distributions, missing subtopics, and the recommended next action.

## Evidence-Grounded Notes and Reports

After parsing PDFs, the preferred synthesis path is:

```bash
litagent read ./my-topic
litagent build-knowledge ./my-topic
litagent build-evidence ./my-topic --json
litagent report ./my-topic
litagent audit ./my-topic
litagent inspect-workspace ./my-topic --json
```

`litagent read` now separates metadata/abstract-derived content from parsed-full-text-derived
evidence. Notes attempt to extract problem, method, agent roles, pipeline stages, retrieval
strategy, citation/evidence handling, evaluation setup, datasets or benchmarks, findings,
limitations, and relevance to multi-agent literature review automation.

`litagent build-evidence WORKSPACE --json` creates:

- `knowledge/evidence_table.md`
- `knowledge/evidence_table.json`

The evidence table maps synthesis themes to supporting papers, snippets or sections, confidence,
and gaps. `litagent report` uses this table to make claim-to-paper support explicit. Audit and
inspection warn when the evidence table is missing, notes remain abstract-level despite parsed
Markdown, or the report has too few paper-specific references.

## MinerU PDF Parsing

`litagent parse` writes parsed PDF Markdown to `library/markdown/{paper_id}.md`, updates
`library/metadata/{paper_id}.json`, and logs each attempt to `logs/parsing.jsonl`.
Local fallback parsing depends on `pypdf`, which is installed by `pip install -e ".[dev]"`.

Parser modes:

- `off`: no MinerU network call; use local pypdf text extraction if available, otherwise fallback later to abstracts. This is the recommended first pass for small real runs with text PDFs.
- `agent`: use MinerU Agent lightweight API, no token required.
- `precision`: use MinerU precision API and requires `MINERU_API_TOKEN`.
- `auto`: use `precision` when `MINERU_API_TOKEN` is set, otherwise use `agent`.

Set your token in the environment, never in source files:

```bash
export MINERU_API_TOKEN="..."
litagent parse ./my-topic --mineru-mode auto --language ch --page-range 1-20
```

The CLI also reads `MINERU_API_TOKEN` from a local `.env` file in this repo. `.env` is
ignored by `.gitignore`.

## Audit and Workspace Inspection

`litagent audit WORKSPACE` checks required files, traceable report citations, parse quality, and
evidence-grounding signals. The audit report includes selected paper count, downloaded PDF count,
parsed Markdown count, parse success rate, notes generated from parsed Markdown versus abstract
fallback, notes with parsed full-text evidence, and report reference counts.

`litagent inspect-workspace WORKSPACE --json` is agent-facing quality guidance. It labels a
workspace as `smoke_test_run`, `small_real_review`, `source_diverse_real_review`, or
`production_quality_review`; summarizes search and selection concerns; reports
parse/report/audit concerns; and recommends the next action. Source imbalance is a warning, not by
itself a reason to downgrade an otherwise successful small real review to smoke-test quality.
Missing evidence tables, shallow notes, and generic unsupported report claims are treated as
quality concerns.

## Codex-Orchestrated Mode

This project now treats Codex as the research orchestrator and `litagent` as the tool layer.

Local pieces:

- `AGENTS.md`: project-level agent workflow and safety rules.
- `litagent-researcher` skill: installed under `~/.codex/skills/litagent-researcher`.
- `litagent` MCP server: registered in Codex as `litagent`.

Check the MCP registration:

```bash
codex mcp get litagent
```

The MCP server can also be launched directly:

```bash
python -m litagent.mcp_server
```

Recommended next broader real run:

```text
Use $litagent-researcher to run a broader real-mode literature review for
`多智能体文献综述自动化工具` in a fresh workspace after `SEMANTIC_SCHOLAR_API_KEY` is configured.
Use real API search, no mock mode, legal open-access PDFs only, local pypdf parsing first, and
MinerU only for OCR/complex-layout/table-heavy PDFs. Start with status/inspect, create and inspect
a focused plan, search with a clear run_id, inspect raw results, dedup latest search run only, run
review-selection before download, refine if needed, then download, parse, classify, read,
build-knowledge, build-evidence, report, audit, and inspect-workspace. Do not accept the run unless
selection quality, parse quality, evidence table, audit, inspect label, and report quality are all
acceptable.
```

## VS Code Reopen in Container

1. Open this folder in VS Code: `D:\study\Autoresearch`.
2. Install/open the Dev Containers extension if VS Code asks for it.
3. Press `Ctrl+Shift+P` and run `Dev Containers: Reopen in Container`.
4. VS Code builds `.devcontainer/devcontainer.json` using `Dockerfile`.
5. Run inside the container terminal:

```bash
litagent init /workspace/demo
pytest
ruff check .
```

The dev container bind-mounts the repo to `/app`, workspace outputs to `/workspace`, and uses a Docker volume at `/home/vscode/.codex` as the active Codex home.
Your local `%USERPROFILE%\.codex` is mounted at `/mnt/host-codex`; `.devcontainer/sync_codex_from_host.py` copies safe auth/config/session files into the container Codex home without reusing Windows SQLite/WAL files directly.
It also installs Node.js 22 and `@openai/codex` during Dev Container creation.

If Docker Desktop's window does not open but `docker ps` works, VS Code Dev Containers can still work because they only need the Docker Engine.

If `codex` reports permission denied for `/root/.codex`, run `Dev Containers: Rebuild Container` so VS Code recreates the container with the corrected mount.
To pull latest host sessions again, run `python .devcontainer/sync_codex_from_host.py`.
To copy container session JSONL files back to the host, run `python .devcontainer/sync_codex_to_host.py`.

## Docker Desktop without VS Code

```bash
docker compose build
docker compose run --rm litagent litagent init /workspace/demo
docker compose run --rm litagent pytest
docker compose run --rm litagent ruff check .
```

Use `docker compose run --rm litagent bash` to enter the container.
