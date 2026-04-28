# Autoresearch

Agentic Literature Research Workbench CLI.

## 当前阶段

当前项目阶段是小规模真实综述原型（small_real_review prototype）。

`litagent` 已经可以完成小规模真实文献综述流程，但它不是最终研究判断者。项目采用以下职责边界：

- Codex / Agent 是调度、检查、判断、质疑和中文综合层。
- `litagent` 是确定性工具层，负责搜索、去重、下载、解析、初步分类、初步阅读、知识构建、证据表（evidence table）构建、报告草稿、审计和质量信号输出。
- `classify`、`read`、`build-knowledge`、`build-evidence` 和 `report` 输出都应视为草稿或结构化中间产物，不应直接视为最终学术判断。
- `audit PASS` 不是唯一成功标准。Codex / Agent 仍必须检查候选论文、解析质量、证据表、报告深度和来源多样性（source diversity）。

重要项目文档：

- `docs/project_status.md`：当前阶段、质量等级、基线和下一阶段路线图。
- `docs/chinese_output_policy.md`：中文输出规范。
- `docs/regression_checklist.md`：回归检查清单。

## 中文输出规范

从当前阶段开始，Agent 面向用户的输出默认使用中文。最终报告和研究笔记也应默认使用中文，论文标题、命令、文件名、MCP tool 名、API 名和代码标识符可以保留英文原文。重要英文术语第一次出现时使用“中文解释（English original）”格式。

当前确定性 `litagent report` 默认生成中文报告草稿，并优先使用高 `snippet_score` 证据片段。它仍然只是机器生成的中间产物；真实研究输出需要 Codex / Agent 基于 `library/notes`、`library/markdown` 和 `knowledge/evidence_table.*` 进行二次中文综合。

## 质量等级

`litagent inspect-workspace WORKSPACE --json` 当前使用以下质量标签：

- 冒烟测试（smoke_test_run）：只验证流程，可以使用 mock，不代表真实综述质量。
- 小规模真实综述（small_real_review）：使用真实检索，有 8 到 15 篇相关论文，下载和解析成功率合理，笔记主要来自 parsed Markdown，证据表存在，报告有论文级引用，但来源多样性、证据质量或报告深度仍有限。
- 来源多样真实综述（source_diverse_real_review）：至少两个或更多真实数据源有效参与，selected papers 不被单一来源垄断，`review-selection` 干净，证据表质量较高，报告有明确论文级支撑。
- 生产级综述（production_quality_review）：更大规模，有明确纳入/排除标准、可复查检索策略、高质量全文解析、结构化证据链、可靠中文研究级综合，并经过人工审阅或严格质量门禁。当前项目尚未达到。

当前最佳基线是 `./demo-real-v3`。它达到 `small_real_review`，但没有达到 `source_diverse_real_review` 或 `production_quality_review`。

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

## Semantic Scholar API 配置

`litagent` 使用 `SEMANTIC_SCHOLAR_API_KEY` 读取 Semantic Scholar API key。配置后，
Semantic Scholar provider 会在真实检索中使用该 key。不要把真实 key 写入代码、文档或
提交记录；可以使用 shell 环境变量或本地 `.env` 文件，`.env` 已被 `.gitignore` 忽略。

官方 Semantic Scholar API 默认使用：

```bash
export SEMANTIC_SCHOLAR_API_KEY="..."
```

如使用明确配置的兼容代理，可以额外设置：

```bash
export SEMANTIC_SCHOLAR_API_BASE_URL="https://your-compatible-proxy.example/s2"
export SEMANTIC_SCHOLAR_API_AUTH_MODE="authorization_bearer"
```

默认鉴权模式是 `x-api-key`。当 `SEMANTIC_SCHOLAR_API_AUTH_MODE=authorization_bearer`
时，provider 会发送 `Authorization: Bearer <SEMANTIC_SCHOLAR_API_KEY>`。如果没有
有效 key，Semantic Scholar 可能返回 HTTP 401、403 或 429；该错误会被记录到
`logs/search_errors.jsonl`，不会中断整个 pipeline。日志只记录 `key_present`、`auth_mode`、
`base_url`、`endpoint` 和诊断建议，不会写入真实 key。

重新运行来源多样性验证前，先做最小 provider 连通性检查：

```bash
litagent provider-smoke semantic-scholar --json
```

该命令只请求 1 条 `"literature review automation"` 结果，不创建 workspace、不运行完整
search、不下载论文。输出包含 `success`、`status_code`、`error_type`、`base_url`、
`auth_mode`、`key_present`、`endpoint`、`result_count` 和 `likely_action`。如果仍然返回
403，应先检查 API key 权限、鉴权 header 模式、代理 base URL、endpoint path 和代理是否
允许该路径。

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
and gaps. In the current evidence-quality phase, every evidence item should also include
`section`, `snippet_score`, `snippet_score_explanation`, and `quality_flags`. Codex / Agent must
inspect these fields before accepting the report.

`litagent report` now generates a Chinese draft report and prioritizes higher-score evidence
snippets for paper-specific claims. Low-score snippets remain in the evidence table for review,
but should not be treated as strong support. Audit and inspection warn when the evidence table is
missing, notes remain abstract-level despite parsed Markdown, report references are too weak, or
evidence quality is poor.

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
Missing evidence tables, shallow notes, generic unsupported report claims, high unknown-section
ratios, many low-score snippets, and noise-heavy evidence are treated as quality signals that
Codex / Agent must inspect. `audit PASS` remains insufficient by itself.

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
下一阶段先不要扩大真实检索规模。当前优先级是稳定 section-aware evidence extraction、
evidence quality scoring 和中文研究级报告草稿质量。

配置 SEMANTIC_SCHOLAR_API_KEY 后，再使用 fresh workspace ./demo-real-v4
做 max_papers=15 的 source-diverse validation。
```

`demo-real-v4` 前置检查：

- 确认 `SEMANTIC_SCHOLAR_API_KEY` 已配置；如使用兼容代理，还需确认
  `SEMANTIC_SCHOLAR_API_BASE_URL` 和 `SEMANTIC_SCHOLAR_API_AUTH_MODE`。
- 先运行 `litagent provider-smoke semantic-scholar --json`，并确认 Semantic Scholar
  provider 能返回成功结果；如果 smoke test 失败，不要重新运行 v4。
- 使用 fresh workspace：`./demo-real-v4`。
- `max_papers=15`，目标是来源多样性验证，不是扩大规模。
- 使用真实检索和 search run isolation，不使用 mock。
- 下载前运行 `review-selection`。
- 解析优先使用本地 `pypdf`。
- MinerU 只用于复杂版面、OCR 或表格密集 PDF。
- 运行带章节和质量评分的 `build-evidence`。
- `report` 默认中文，且必须是 evidence-backed report。
- Codex / Agent 必须复核 evidence quality、paper_id 支撑和泛化表述。

如果 Semantic Scholar 仍然 401、403、429 或有效候选很少，`demo-real-v4` 不应强行标记为
`source_diverse_real_review`。如果 selected papers 仍被 arXiv/OpenAlex 主导，或来源多样性
改善但相关性和证据质量明显下降，则最多仍应视为 `small_real_review`，并在总结中说明原因。

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
