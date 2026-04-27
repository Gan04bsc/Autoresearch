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
litagent search ./my-topic --mock
litagent dedup ./my-topic --max-papers 30
litagent download ./my-topic
litagent parse ./my-topic --mineru-mode auto
litagent classify ./my-topic
litagent read ./my-topic
litagent build-knowledge ./my-topic
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

## MinerU PDF Parsing

`litagent parse` writes parsed PDF Markdown to `library/markdown/{paper_id}.md`, updates
`library/metadata/{paper_id}.json`, and logs each attempt to `logs/parsing.jsonl`.
Local fallback parsing depends on `pypdf`, which is installed by `pip install -e ".[dev]"`.

Parser modes:

- `off`: no MinerU network call; use local text extraction if available, otherwise fallback later to abstracts.
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

`litagent audit WORKSPACE` checks required files, traceable report citations, and parse quality.
The audit report includes selected paper count, downloaded PDF count, parsed Markdown count, parse
success rate, and notes generated from parsed Markdown versus abstract fallback.

`litagent inspect-workspace WORKSPACE --json` is agent-facing quality guidance. It labels a
workspace as smoke-test quality or real-review quality, summarizes search and selection concerns,
reports parse/report/audit concerns, and recommends the next action.

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

Typical Codex prompt:

```text
Use $litagent-researcher to run a real literature review for "agentic literature review tools"
in ./demo-real. Inspect results before accepting the selected papers, use MinerU auto parsing,
audit the workspace, and improve the final report if needed.
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
