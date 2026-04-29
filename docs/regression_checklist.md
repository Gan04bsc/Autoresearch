# 回归检查清单

每次修改 `litagent` 的研究流程模块后，都应按照本文档检查是否破坏当前研究型文献工作台（research literature workspace）基线。

当前主要回归基线是 `./demo-real-v3`。除非明确需要真实网络检索，否则优先使用已有 workspace 进行非网络验证。
`./demo-real-v4` 是来源多样性基线，不应在普通功能改动中反复重跑。

## project direction

检查项：

- 项目是否仍被定位为文献调研和管理工具，而不是自动综述写作器。
- `final_report.md` 是否仍被视为可选展示产物，而不是默认终点。
- 文献发现、分类、管理、领域地图、技术前沿、证据管理、研究空白和创新线索是否仍是核心输出。
- AutoWiki-compatible export 是否只是知识组织层，不接管 search/download/parse。
- 是否仍明确区分综述建图、技术论文追前沿、benchmark/dataset 建评估，而不是把项目重新做成
  综述生成系统。
- 新领域扩大到 50-70 篇时，是否有质量门禁，优先顶会、顶刊、高引用基础论文、权威技术报告、
  主流 benchmark 和可复现系统。
- `topic-run` 是否仍被定位为后台流程编排和状态记录，而不是把 `final_report.md`
  重新变成唯一终点。

## topic-run / backend readiness

修改 CLI 编排、OpenClaw 接入、状态记录或 workspace 产物时，检查：

- `litagent topic-run TOPIC --workspace WORKSPACE` 是否仍能串联
  `plan -> search -> dedup -> review-selection -> download -> parse -> classify -> read ->
  build-knowledge -> build-evidence -> export-wiki -> audit -> inspect-workspace`。
- 是否写入 `run_state.json`。
- 是否写入 `run_log.jsonl`。
- 是否写入 `artifacts_manifest.json`。
- 是否写入 `errors.json`。
- 每个 step 是否记录 `status`、`input_count`、`output_count`、`failed_count`、
  `started_at` 和 `finished_at`。
- 默认是否跳过已经成功的步骤，支持失败后重新运行。
- `--force` 是否能重跑全部步骤。
- `--from-step` 是否能从指定步骤向后重跑。
- 错误摘要是否脱敏，不泄露 API key、Bearer token 或 `.env` 内容。
- 默认 parse 是否仍为本地 pypdf first，不把 MinerU 变成默认路径。
- `review-selection` 发现 likely off-topic 时，是否在下载前阻止或明确要求人工复核。
- `export-wiki` 是否只使用 workspace 已有产物，不调用网络、不重新下载、不重新解析。

最小非网络回归命令：

```bash
litagent topic-run "agentic literature review automation" \
  --workspace .tmp/topic-run-smoke \
  --max-papers 5 \
  --mock
```

## global library

修改全局文献库、topic workspace、OpenClaw 准备层或同步逻辑时，检查：

- `litagent sync-library WORKSPACE --library-db PATH --json` 是否只读取已有 workspace 产物。
- 是否不调用网络、不下载 PDF、不重新解析 PDF。
- 是否创建或迁移 SQLite schema。
- `papers` 是否保存全局唯一 paper，而不是按 topic 重复造 paper。
- `topics` 是否保存 topic 视角。
- `topic_papers` 是否保存 `paper_role`、`reading_intent`、相关性分数和选择理由。
- `runs` 是否保存 workspace、run 状态、search run id、selected count 和 quality label。
- `evidence_spans` 是否保存 paper_id、topic_id、section、snippet、score 和 quality flags。
- 重复运行 sync 是否幂等，不重复插入同一个 topic-paper 或 evidence span。
- `library-status` 是否能显示 papers、topics、topic_papers、runs 和 evidence_spans 数量。
- 同步输出、错误日志和数据库内容是否不包含 API key、Bearer token 或 `.env` 内容。

最小非网络回归命令：

```bash
litagent sync-library .tmp/topic-run-smoke \
  --library-db .tmp/autoresearch-library.db \
  --topic-slug topic-run-smoke \
  --json
litagent library-status --library-db .tmp/autoresearch-library.db --json
```

## job queue / OpenClaw readiness

修改任务队列、OpenClaw 接入、后台执行或 CLI 编排时，检查：

- `litagent job create` 是否只创建 queued job，不立即执行真实检索。
- `litagent job status JOB_ID --json` 是否能返回 job 状态、topic、workspace 和 payload。
- `litagent job list --json` 是否能列出最近任务。
- `litagent job cancel JOB_ID --json` 是否能取消 queued job。
- `litagent job logs JOB_ID --json` 是否能返回 job events 和 `run_log.jsonl`。
- `litagent job run-next --json` 是否只运行最早的 queued job。
- job payload 是否只包含白名单 `topic-run` 参数。
- job queue 是否不允许任意 shell command。
- `--sync-library` 是否只在 topic-run 成功后同步 `library.db`。
- job 错误是否脱敏，不泄露 API key、Bearer token 或 `.env` 内容。
- OpenClaw 设计是否仍是入口和通知层，而不是研究判断层或任意 shell 执行器。

最小非网络回归命令：

```bash
litagent job create \
  --jobs-db .tmp/jobs.db \
  --topic "agentic literature review automation" \
  --workspace .tmp/job-topic \
  --max-papers 5 \
  --mock \
  --json
litagent job run-next --jobs-db .tmp/jobs.db --json
litagent job list --jobs-db .tmp/jobs.db --json
```

## search / ranking

检查项：

- 是否仍能隔离 search run。
- 每次搜索是否写入 `data/search_runs/{run_id}/raw_results.jsonl`。
- `data/raw_results.jsonl` 是否只是最新搜索批次的兼容视图。
- selected papers 是否仍包含 `score_explanation`。
- 排名是否避免让高引用但泛泛相关的论文压过高度相关论文。
- 负面关键词是否能压低 robotics、traffic、swarm、game theory、reinforcement learning、medical、education、industry-only 等偏题结果。
- 重新运行来源多样性验证前，是否先通过
  `litagent provider-smoke semantic-scholar --json`。
- Semantic Scholar 失败日志是否包含 `status_code`、`auth_mode`、`base_url`、`endpoint`、
  `key_present` 和 `likely_action`，且不包含真实 API key。

`demo-real-v3` 基线：

- `search_run_id`: `demo-real-v3-initial`
- raw results: 382
- raw source distribution: arXiv 80, OpenAlex 301, Semantic Scholar 1
- Semantic Scholar 因缺少 `SEMANTIC_SCHOLAR_API_KEY` 基本不可用。

## dedup

检查项：

- 默认是否使用 latest search run。
- 是否不会静默混入旧搜索结果。
- `--search-scope latest`、`all`、`selected` 是否语义清楚。
- 去重后是否保留 DOI、arXiv ID、标题、来源和分数解释等关键信息。

`demo-real-v3` 基线：

- deduplicated papers: 337
- selected papers: 12
- 最终选择来自最新搜索批次。

## review-selection

检查项：

- 是否能输出 likely relevant、questionable、likely off-topic。
- 是否能输出每篇论文的原因。
- 是否能输出 source distribution 和 year distribution。
- 是否能提示缺失子主题。
- 下载前是否必须运行。
- application_case 或明显偏题应用论文是否被降权或标记为 questionable/off-topic。

`demo-real-v3` 基线：

- 初次选择曾出现一个 broader roadmap 类 questionable paper。
- 调整 plan 并重跑 dedup 后，最终 `review-selection` 为 12 relevant、0 questionable、0 off-topic。

## parser

检查项：

- downloaded PDF 数是否正确。
- parsed Markdown 数是否正确。
- abstract fallback 数是否正确。
- `pypdf` 对普通文本 PDF 是否正常。
- 失败是否写入 `logs/parsing.jsonl`。
- MinerU 是否仍只作为 OCR、复杂版面或表格密集论文的备用路径。

`demo-real-v3` 基线：

- selected papers: 12
- downloaded PDFs: 12
- parsed Markdown: 12
- parse success rate: 100%
- abstract fallback: 0
- parser: local `pypdf`

## reader

检查项：

- 是否使用 parsed Markdown。
- 是否保留或推断 `paper_role` 和 `reading_intent`。
- 是否区分 metadata/abstract-derived content 和 parsed-full-text-derived evidence。
- 是否提取 problem、method、agent roles、pipeline stages、retrieval/search、citation/evidence handling、evaluation、datasets/benchmarks、key findings、limitations、relevance。
- 是否明确标记缺失或不确定信息。

## paper_role / reading_intent

检查项：

- `paper_role` 是否覆盖 `survey_or_review`、`technical_method`、`system_paper`、
  `benchmark_or_dataset`、`position_or_perspective`、`application_case`、
  `background_foundation`。
- `reading_intent` 是否覆盖 `build_field_map`、`extract_method`、`track_frontier`、
  `compare_systems`、`identify_benchmarks`、`find_research_gap`、
  `implementation_reference`。
- 综述论文是否主要进入 field map。
- 技术论文和系统论文是否主要进入 method extraction / technical frontier。
- Benchmark/dataset 论文是否主要进入 evaluation matrix。
- Position/background 论文是否只作为背景，不主导技术路线。
- Survey papers 是否过多导致系统退回“写综述”路径。
- Technical/system papers 是否足够支撑技术追踪。
- 大规模新领域调研中，survey、technical/system、benchmark/dataset 的比例是否合理。
- 低质量、弱相关或单一应用论文是否被降权，而不是挤占高质量代表论文。

## research workspace outputs

检查项：

- `knowledge/field_map.md` 是否存在，且主要由 survey/background/position 论文支撑。
- `knowledge/technical_frontier.md` 是否存在，且主要由 technical/system 论文支撑。
- `knowledge/method_matrix.md` 是否存在，且包含 paper_id、系统/方法、任务、输入、输出、核心模块、agent 分工、证据处理、评估方式和局限。
- `knowledge/benchmark_matrix.md` 是否存在，且能汇总 benchmark/dataset 论文。
- `knowledge/innovation_opportunities.md` 是否来自技术论文、benchmark 论文和证据缺口，而不是泛泛建议。
- `knowledge/reading_plan.md` 是否区分“先读综述建地图”和“再读技术论文追踪前沿”。

`demo-real-v3` 基线：

- notes: 12
- notes from parsed Markdown: 12
- notes from abstract fallback: 0
- notes with parsed full-text evidence: 12

## build-evidence

检查项：

- `knowledge/evidence_table.md` 是否存在。
- `knowledge/evidence_table.json` 是否存在。
- 是否按 theme 分组。
- 每个 theme 是否有 paper-specific support。
- 是否记录 confidence 和 gaps_or_uncertainties。
- 每条证据是否包含 `section`、`snippet_score`、`snippet_score_explanation` 和
  `quality_flags`。
- 低质量证据是否被保留为弱证据或复核线索，而不是被误当作强支撑。
- 是否尽量避免 References、Appendix、prompts、code、tables、layout artifacts 等噪声。

## evidence quality regression baseline

当修改 `reader`、`build-evidence`、`report`、`audit` 或 `inspect-workspace` 时，必须
对照以下 evidence quality regression baseline。

字段检查：

- `knowledge/evidence_table.json` 中每条证据是否包含 `section`。
- 是否包含 `snippet_score`。
- 是否包含 `snippet_score_explanation`。
- 是否包含 `quality_flags`。
- `knowledge/evidence_table.md` 是否按 theme 分组并展示 section 和 score。

质量指标检查：

- unknown section ratio 是否异常升高。
- noise section ratio 是否异常升高。
- low-score ratio 是否异常升高。
- final_report.md 是否仍为中文报告草稿。
- report 是否仍有 paper_id 支撑。
- `inspect-workspace` label 是否仍合理。
- `audit PASS` 是否没有被误解为最终研究质量达标。

冻结基线：`demo-real-v3` after evidence quality scoring：

- evidence table 已生成。
- 当前证据质量增强基线：`total_snippets=93`，`high_quality_snippets=85`，
  `unknown_section_ratio=0%`，`noise_section_ratio≈1.1%`，`low_score_ratio≈2.2%`。
- 主题包括 multi-agent architecture、survey/literature review generation、systematic review workflow、paper reading agents、citation-aware synthesis、evaluation and benchmarks、limitations and open problems、design implications for litagent。
- 已知弱点：仍可能出现 table、reference-adjacent 或上下文过短片段，但应被
  `section`、`snippet_score` 和 `quality_flags` 标记为弱证据或复核线索。

如果指标相对该基线明显变差，应先检查章节识别、snippet 清洗、score threshold 和
主题匹配逻辑，不应直接接受新的报告。

## report

检查项：

- report 是否仍被视为可选中文草稿，不是项目默认终点。
- 是否使用中文输出。
- 是否 evidence-backed。
- 是否优先使用高 `snippet_score` 的 evidence snippet。
- 是否包含 taxonomy、comparison、gaps、roadmap。
- 是否有论文级引用。
- 是否避免泛泛而谈。
- 是否明确说明证据空白和当前限制。

`demo-real-v3` 基线：

- final report 有 12 个唯一 paper_id 引用。
- report 使用 evidence table 生成证据支撑主题。
- `litagent report` 默认生成中文报告草稿，并在正文优先使用高分证据。
- 质量可接受为 small_real_review，但仍不是最终中文研究级报告。
- 已知弱点：仍可能出现泛化表述，需要 Codex / Agent 复核 paper-specific support。

## audit / inspect

检查项：

- `audit PASS` 是否仍不足以代表成功。
- `inspect-workspace` label 是否合理。
- 是否能发现 shallow report、weak evidence、source imbalance、parse failure、abstract fallback。
- 是否能提示 unknown section 比例过高、低分 evidence 比例过高、References/Appendix 等噪声片段过多。
- 是否报告 selected count、downloaded PDF count、parsed Markdown count、parse success rate 和 note source counts。
- 是否报告 paper_role / reading_intent 分布。
- 是否提示 field_map、technical_frontier、method_matrix、benchmark_matrix、innovation_opportunities 或 reading_plan 缺失。
- 是否提示 technical/system papers 不足、survey papers 过多或 background/position/application 权重过高。

`demo-real-v3` 基线：

- Audit: PASS
- Inspect label: `small_real_review`
- downloaded PDFs: 12
- parsed Markdown: 12
- notes from parsed Markdown: 12
- abstract fallback: 0
- evidence table exists: true
- 由于 Semantic Scholar 不可用且 selected papers 被 arXiv 主导，不应升级为 `source_diverse_real_review`。

## demo-real-v4 来源多样性验收

`demo-real-v4` 的目标是验证来源多样性（source diversity），不是扩大规模。只有满足
以下条件时，才可以认为它比 `demo-real-v3` 前进：

- 已配置 `SEMANTIC_SCHOLAR_API_KEY`。
- `litagent provider-smoke semantic-scholar --json` 已成功，且输出不泄露 API key。
- 使用 fresh workspace：`./demo-real-v4`。
- `max_papers=15`。
- Semantic Scholar 实际贡献有效候选结果。
- selected papers 不再几乎全来自 arXiv/OpenAlex。
- `review-selection` clean。
- parse success 合理。
- abstract fallback 很低或为 0。
- evidence table 质量不低于 `demo-real-v3` 太多。
- final_report.md 是中文 evidence-backed report。
- report 有 paper_id 支撑。
- `inspect-workspace` 至少保持 `small_real_review`；如果来源多样性足够，则可达到
  `source_diverse_real_review`。

如果无法达到 `source_diverse_real_review`，必须在最终总结中说明具体原因，例如
Semantic Scholar 返回 401/403/429、有效候选不足、selected papers 仍由单一来源主导或
证据质量下降。
如果 Semantic Scholar 无有效贡献，则 v4 最多仍是 `small_real_review`。如果来源多样性改善
但 selected papers 相关性下降、`review-selection` 不干净或 evidence quality 明显弱于
`demo-real-v3`，也不能升级标签。来源多样性不能以牺牲相关性和证据质量为代价。

当前官方 API 基线：

- run_id: `demo-real-v4-official-ss`
- raw results: 801
- Semantic Scholar raw candidates: 421
- selected papers: 15
- selected source distribution after merge: Semantic Scholar 12, arXiv 10, OpenAlex 5
- download: 15/15
- pypdf parse: 15/15
- abstract fallback: 0
- evidence snippets: 93
- high-quality snippets: 80
- inspect label: `source_diverse_real_review`

## AutoWiki-compatible export

检查项：

- `litagent export-wiki WORKSPACE --format autowiki --out OUT_DIR` 是否存在。
- 命令是否不调用网络、不重新下载、不重新解析。
- 是否明确把 `export-wiki` 当作 artifact 打包层，而不是最终 AutoWiki 知识编译。
- Codex / Agent 是否使用 `autowiki` skill 二次编译主题页、source 深度分析页、Relations、
  Critical Analysis、阅读路径和创新路线。
- 是否生成 `raw/<paper_id>/source.md`、`metadata.json` 和 `evidence.json`。
- 是否生成 `START_HERE.md`、`kb/index.md`、`kb/source-index.md`、`kb/evidence-index.md`、
  `field-map.md`、`technical-frontier.md`、`reading-plan.md`、`innovation-opportunities.md`、
  `matrices/method-matrix.md` 和 `matrices/benchmark-matrix.md`。
- 是否生成 `kb/sources/<paper_id>.md`、`kb/notes/note-<paper_id>.md` 和
  `kb/evidence/evidence-<paper_id>.md`。
- Markdown 是否默认中文并保留必要英文术语、论文标题、命令名和代码标识符。
- 是否使用 Obsidian wikilinks，例如 `[[survey-generation]]` 和
  `[[citation-aware-synthesis]]`。
- 是否区分综述论文、技术论文、系统论文和 benchmark/dataset 论文。
- 是否不泄露 `.env`、API key、token 或 secret 字段。
- Obsidian 中是否能从 `START_HERE.md` 看到地图、论文速读、完整 notes 和 evidence。
- 不应只检查链接是否存在；还要抽查 topic/source 页面是否有真实综合，而不是 Python
  模板填充。

`./demo-real-v4` 当前推荐打开 `/app/workspace/autowiki-v4`，入口是 `START_HERE.md`。
`/app/workspace/wiki-vault-v4` 只作为模板式导出回归样例。

## 每次改动后的最低验证

必须运行：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider
RUFF_CACHE_DIR=/tmp/litagent-ruff-cache ruff check .
```

如改动涉及 reader、build-evidence、report、audit 或 inspect，建议在不启动真实网络检索的前提下使用已有 `./demo-real-v3` 运行：

```bash
litagent read ./demo-real-v3
litagent build-knowledge ./demo-real-v3
litagent build-evidence ./demo-real-v3 --json
litagent report ./demo-real-v3
litagent audit ./demo-real-v3
litagent inspect-workspace ./demo-real-v3 --json
```
