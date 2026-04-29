# AGENTS.md

你正在维护 `litagent`，一个由 Codex 调度的研究型文献工作台
（research literature workspace）。

开始任何开发或研究工作前，先阅读 `prd.md`、`progress.md` 和
`docs/project_status.md`。当前方向不是自动综述写作器，也不是生产级系统综述工具，
而是面向研究者的文献调研、管理、证据组织和技术前沿追踪工具。

核心目标包括：

- 文献发现。
- 文献分类。
- 文献管理。
- 领域地图构建。
- 技术论文追踪。
- 证据管理。
- 研究空白发现。
- 创新线索生成。
- 中文调研材料生成。

`reports/final_report.md` 只是可选中文草稿或展示产物，不是项目核心终点。

重要边界：`litagent` 不是“综述生成系统”。综述论文只是帮助研究者快速建立领域地图；
技术论文、系统论文和 benchmark/dataset 论文才是追踪前沿技术、发现方法创新和设计评估体系的
主要材料。对全新领域，候选集合可以是 50-70 篇，但必须优先选择高质量来源，例如顶会、
顶刊、高引用基础论文、主流技术报告、权威 benchmark 和可复现系统；不要用低质量泛论文凑数。

## 架构和职责边界

### Codex / Agent 的职责

Codex / Agent 是调度、判断、检查和中文综合层。它必须：

- 调度 `litagent` 的 CLI 或 MCP 工具执行研究流程。
- 检查 `research_plan.json`、原始结果、候选论文、解析日志、阅读笔记、证据表
  （evidence table）、报告和审计结果等中间产物。
- 判断是否继续下一步，必要时局部重跑 `search`、`dedup`、`review-selection`、
  `parse` 或 `report`。
- 判断 `selected_papers.jsonl` 是否与研究主题相关。
- 判断证据表是否可用，是否记录 `section`、`snippet_score`、
  `snippet_score_explanation` 和 `quality_flags`，是否存在噪声片段、证据不足或主题支撑过弱。
- 判断工作台知识页是否可用，包括 `field_map`、`technical_frontier`、`method_matrix`、
  `benchmark_matrix`、`innovation_opportunities` 和 `reading_plan`。
- 判断 `reports/final_report.md` 是否只是可选草稿，是否浅薄、模板化、缺少论文级支撑或
  不适合作为真实研究输出。
- 基于 `library/notes`、`library/markdown`、`knowledge/evidence_table.*`、工作台知识页
  和元数据进行中文综合。
- 不接受 `audit PASS` 作为唯一成功标准。

### litagent 的职责

`litagent` 是确定性工具层。它负责：

- 搜索开放学术来源。
- 隔离搜索批次并保留 `search_run_id`。
- 去重、排序和生成 `score_explanation`。
- 下载合法开放获取 PDF。
- 使用本地 `pypdf` 或必要时 MinerU 解析 PDF。
- 初步分类论文类型。
- 推断论文角色（paper_role）和阅读意图（reading_intent）。
- 生成初步阅读笔记。
- 构建知识文件。
- 构建带章节和质量评分的证据表。
- 生成研究工作台知识页。
- 导出 AutoWiki-compatible vault。
- 通过 `topic-run` 记录可恢复的一键流程状态。
- 可选生成报告草稿。
- 输出 `audit` 和 `inspect-workspace` 质量信号。

`litagent` 不应被视为最终研究判断者。它的 `classify`、`read`、
`build-knowledge`、`build-evidence`、`export-wiki` 和 `report` 输出都只是草稿
（draft）、结构化证据（structured evidence）或机器生成的中间产物
（machine-generated intermediate artifacts），不是最终学术判断
（final scholarly judgment）。

## 中文输出规范

- Agent 面向用户的输出默认使用中文。
- 最终报告默认使用中文。
- 研究笔记默认使用中文，必要英文术语保留原文。
- 论文标题可以保留英文原文。
- 重要英文术语第一次出现时使用“中文解释（English original）”格式。
- 命令、文件名、MCP tool 名、API 名和代码标识符保持英文。
- 不要把中间报告写成英文模板。
- 如果输入论文内容是英文，阅读和综合结果仍应转写成中文。

详细规范见 `docs/chinese_output_policy.md`。

## 标准 Agent 工作流

1. 理解用户主题、workspace、论文数量和是否允许真实网络检索。
2. 先运行或调用 `litagent status WORKSPACE --json` 或
   `litagent inspect-workspace WORKSPACE --json`。
3. 创建或检查 `research_plan.json`。
4. 检查检索词是否过宽、过窄、偏离主题、缺少排除项或缺少中文/英文同义表达。
5. 搜索时使用明确的 `search_run_id`。每次搜索必须可追踪到
   `data/search_runs/{run_id}/`。
6. 检查 `data/raw_results.jsonl` 和来源分布，再决定是否去重。
7. 默认对最新搜索批次去重：`litagent dedup WORKSPACE --search-scope latest`。
8. 检查 `data/selected_papers.jsonl`，重点看相关性、分数解释、开放 PDF 和来源。
9. 下载前必须运行 `litagent review-selection WORKSPACE --json`。
10. 只有在候选论文相关性可接受时才下载。
11. 只下载合法开放获取 PDF，不绕过付费墙。
12. 普通文本 PDF 优先使用本地 `pypdf`。MinerU 只用于 OCR、复杂版面或表格密集论文。
13. 检查下载数、解析 Markdown 数、解析成功率和 abstract fallback 数。
14. 运行 `classify -> read -> build-knowledge -> build-evidence`。
15. 检查证据表是否按主题组织，是否有论文级支撑，是否有 `section`、
    `snippet_score`、质量说明和明显噪声标记。
16. 检查 `knowledge/field_map.md`、`knowledge/technical_frontier.md`、
    `knowledge/method_matrix.md`、`knowledge/benchmark_matrix.md`、
    `knowledge/innovation_opportunities.md` 和 `knowledge/reading_plan.md`。
17. 如需长期知识库管理，运行
    `litagent export-wiki WORKSPACE --format autowiki --out OUT_DIR`。
18. 如需 AutoWiki/Obsidian 知识库，不要只接受 `export-wiki` 的模板式结果。Codex / Agent
    必须使用 `autowiki` skill 检查 source、note 和 evidence，并二次编译主题页、source
    深度分析、Relations、Critical Analysis、阅读路径和创新路线。
19. 如需展示型中文草稿，再运行 `report`。报告不是默认终点。
20. 运行 `audit`。
21. 运行 `inspect-workspace`。
22. 如果 `audit PASS` 但工作台知识页缺失、证据表弱、解析失败、来源失衡、候选论文偏题
    或报告浅薄，必须继续修正。

## 一键 Topic Run 规则

`litagent topic-run` 是后台服务化和后续 OpenClaw 接入的基础命令。它用于稳定执行流程和记录
状态，不替代 Codex / Agent 的研究判断。

默认流程：

```text
plan -> search -> dedup -> review-selection -> download -> parse -> classify -> read
-> build-knowledge -> build-evidence -> export-wiki -> audit -> inspect-workspace
```

运行后必须检查：

- `run_state.json`
- `run_log.jsonl`
- `artifacts_manifest.json`
- `errors.json`
- `logs/review_selection.json`
- `logs/inspect_workspace.json`

默认行为：

- 已成功步骤会被跳过，支持失败后恢复。
- `--force` 用于重跑全部步骤。
- `--from-step` 用于从某一步向后重跑。
- 默认 `--mineru-mode off`，也就是本地 `pypdf` first。
- 默认导出到 `WORKSPACE/wiki-vault`，也可用 `--wiki-out` 指定 Obsidian vault。
- `review-selection` 发现 likely off-topic 时不应盲目继续下载，除非用户明确允许。

后续 OpenClaw 不应直接自由执行 shell，而应只调用 `topic-run`、`status`、`inspect-workspace`、
`export-wiki`、未来 `job status` 等白名单命令。

## 论文角色和阅读意图

`paper_role` 用来描述论文在知识库中的功能：

- `survey_or_review`：用于构建领域地图。
- `technical_method`：用于抽取方法和追踪前沿。
- `system_paper`：用于比较系统、抽取架构和寻找实现参考。
- `benchmark_or_dataset`：用于评估体系建设。
- `position_or_perspective`：用于背景和研究空白，不主导技术路线。
- `application_case`：只在与主题直接相关时作为实现参考；偏题时降权。
- `background_foundation`：用于背景知识，不主导技术路线。

`reading_intent` 用来描述为什么读这篇论文：

- `build_field_map`
- `extract_method`
- `track_frontier`
- `compare_systems`
- `identify_benchmarks`
- `find_research_gap`
- `implementation_reference`

阅读模板：

- 综述论文：关注领域划分、核心术语、代表系统、经典论文、引用网络、未解决问题和背景价值。
- 技术 / 系统论文：关注具体问题、方法架构、核心模块、agent 分工、输入输出、实验设计、
  创新点、可借鉴设计和实现风险。
- Benchmark / dataset 论文：关注评估能力、数据构造、指标、baseline、对 litagent 的适用性
  和评估盲点。

## 质量等级

`inspect-workspace` 当前使用以下质量标签：

- 冒烟测试（smoke_test_run）：只验证流程，可以使用 mock，不代表真实综述质量。
- 小规模真实综述（small_real_review）：使用真实检索，有 8 到 15 篇相关论文，下载和解析成功率合理，笔记主要来自 parsed Markdown，证据表存在，报告有论文级引用，但来源多样性、证据质量或报告深度仍有限。
- 来源多样真实综述（source_diverse_real_review）：至少两个或更多真实数据源有效参与，selected papers 不被单一来源垄断，`review-selection` 干净，证据表质量较高，报告有明确论文级支撑。
- 生产级综述（production_quality_review）：更大规模，有明确纳入/排除标准、可复查检索策略、高质量全文解析、结构化证据链、可靠中文研究级综合，并经过人工审阅或严格质量门禁。当前项目尚未达到。

详细阶段定义见 `docs/project_status.md`。

## 暂时不要做

- 不要无规划地“跑一轮发现问题加一个功能”。
- 不要把项目重新收窄成自动综述写作器。
- 不要把 deterministic report 当作最终研究报告。
- 不要把 `final_report.md` 当作唯一交付物或默认终点。
- 不要只因为 evidence table 存在就接受报告；必须检查证据质量。
- 不要把 MinerU 作为默认解析路径。
- 不要在没有 `SEMANTIC_SCHOLAR_API_KEY` 的情况下反复扩大真实检索。
- 不要在 `litagent provider-smoke semantic-scholar --json` 失败时重新运行
  `demo-real-v4`；先诊断 Semantic Scholar API key、代理 base URL、auth mode 和 endpoint。
- 不要因为配置了 Semantic Scholar 或兼容代理就自动升级到
  `source_diverse_real_review`；必须同时检查来源分布、论文相关性和证据质量。
- 不要在质量门禁不足时盲目扩大论文数量。新领域调研可以扩大到 50-70 篇，但必须按综述建图、
  技术追踪、benchmark 评估和质量来源分层筛选。
- 不要急着接很多外部 MCP。

## 开发命令

- Install: `pip install -e ".[dev]"`
- Test: `pytest`
- Lint: `ruff check .`
- MCP server: `litagent-mcp`
- Inspect: `litagent inspect-workspace WORKSPACE --json`
- Selection review: `litagent review-selection WORKSPACE --json`
- Evidence table: `litagent build-evidence WORKSPACE --json`
- Export wiki: `litagent export-wiki WORKSPACE --format autowiki --out OUT_DIR`
- Dedup latest search run: `litagent dedup WORKSPACE --search-scope latest --max-papers N`
- Provider smoke test: `litagent provider-smoke semantic-scholar --json`
- Topic run: `litagent topic-run "TOPIC" --workspace WORKSPACE --max-papers N`

## 完成标准

- 测试通过。
- `ruff check .` 通过。
- CLI 或 MCP 命令有文档说明。
- 输出文件符合 PRD schema。
- 错误被记录，主流程不应无说明崩溃。
- Agent 能通过 status、audit、inspect 和中间文件决定下一步。
- 真实文献工作台必须使用：
  `read -> build-knowledge -> build-evidence -> audit -> inspect-workspace`。
- 需要长期知识库时使用 `export-wiki`；需要展示草稿时再运行 `report`。
- Obsidian 打开导出 vault 时应从 `START_HERE.md` 开始；`kb/sources/` 是论文速读页，
  `kb/notes/` 是完整 notes，`kb/evidence/` 是 Markdown evidence。`raw/` 只是归档层。
- `litagent export-wiki` 只是 artifact 打包层；真正像 AutoWiki 的地图、Relations、
  source 深度分析和创新路线必须由 Codex / Agent 使用 `autowiki` skill 二次编译。
- `progress.md` 必须更新。
- 每次完成一次项目更新后提交版本。
