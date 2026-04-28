# AGENTS.md

你正在维护 `litagent`，一个由 Codex 调度的文献研究工作台。

开始任何开发或研究工作前，先阅读 `prd.md`、`progress.md` 和
`docs/project_status.md`。当前阶段是小规模真实综述原型
（small_real_review prototype），不是生产级系统综述工具。

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
- 判断 `reports/final_report.md` 是否浅薄、模板化、缺少论文级支撑或不适合作为真实综述。
- 基于 `library/notes`、`library/markdown`、`knowledge/evidence_table.*` 和元数据进行中文综合。
- 不接受 `audit PASS` 作为唯一成功标准。

### litagent 的职责

`litagent` 是确定性工具层。它负责：

- 搜索开放学术来源。
- 隔离搜索批次并保留 `search_run_id`。
- 去重、排序和生成 `score_explanation`。
- 下载合法开放获取 PDF。
- 使用本地 `pypdf` 或必要时 MinerU 解析 PDF。
- 初步分类论文类型。
- 生成初步阅读笔记。
- 构建知识文件。
- 构建带章节和质量评分的证据表。
- 生成报告草稿。
- 输出 `audit` 和 `inspect-workspace` 质量信号。

`litagent` 不应被视为最终研究判断者。它的 `classify`、`read`、
`build-knowledge`、`build-evidence` 和 `report` 输出都只是草稿
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
14. 运行 `classify -> read -> build-knowledge -> build-evidence -> report`。
15. 检查证据表是否按主题组织，是否有论文级支撑，是否有 `section`、
    `snippet_score`、质量说明和明显噪声标记。
16. 检查报告是否中文、是否优先使用高质量证据、是否有论文级引用、是否避免泛泛而谈。
17. 运行 `audit`。
18. 运行 `inspect-workspace`。
19. 如果 `audit PASS` 但报告浅薄、证据表弱、解析失败、来源失衡或候选论文偏题，必须继续修正。

## 质量等级

`inspect-workspace` 当前使用以下质量标签：

- 冒烟测试（smoke_test_run）：只验证流程，可以使用 mock，不代表真实综述质量。
- 小规模真实综述（small_real_review）：使用真实检索，有 8 到 15 篇相关论文，下载和解析成功率合理，笔记主要来自 parsed Markdown，证据表存在，报告有论文级引用，但来源多样性、证据质量或报告深度仍有限。
- 来源多样真实综述（source_diverse_real_review）：至少两个或更多真实数据源有效参与，selected papers 不被单一来源垄断，`review-selection` 干净，证据表质量较高，报告有明确论文级支撑。
- 生产级综述（production_quality_review）：更大规模，有明确纳入/排除标准、可复查检索策略、高质量全文解析、结构化证据链、可靠中文研究级综合，并经过人工审阅或严格质量门禁。当前项目尚未达到。

详细阶段定义见 `docs/project_status.md`。

## 暂时不要做

- 不要无规划地“跑一轮发现问题加一个功能”。
- 不要把 deterministic report 当作最终研究报告。
- 不要只因为 evidence table 存在就接受报告；必须检查证据质量。
- 不要把 MinerU 作为默认解析路径。
- 不要在没有 `SEMANTIC_SCHOLAR_API_KEY` 的情况下反复扩大真实检索。
- 不要扩大到 30 或 50 篇论文。
- 不要急着接很多外部 MCP。

## 开发命令

- Install: `pip install -e ".[dev]"`
- Test: `pytest`
- Lint: `ruff check .`
- MCP server: `litagent-mcp`
- Inspect: `litagent inspect-workspace WORKSPACE --json`
- Selection review: `litagent review-selection WORKSPACE --json`
- Evidence table: `litagent build-evidence WORKSPACE --json`
- Dedup latest search run: `litagent dedup WORKSPACE --search-scope latest --max-papers N`

## 完成标准

- 测试通过。
- `ruff check .` 通过。
- CLI 或 MCP 命令有文档说明。
- 输出文件符合 PRD schema。
- 错误被记录，主流程不应无说明崩溃。
- Agent 能通过 status、audit、inspect 和中间文件决定下一步。
- 真实综述必须使用：
  `read -> build-knowledge -> build-evidence -> report -> audit -> inspect-workspace`。
- `progress.md` 必须更新。
- 每次完成一次项目更新后提交版本。
