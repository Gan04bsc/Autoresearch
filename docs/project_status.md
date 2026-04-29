# 项目阶段状态

## 项目愿景

`litagent` 面向“多智能体文献综述自动化工具”这一方向，目标是构建一个可追溯、可检查、可迭代的研究型文献工作台（research literature workspace）。

项目不应被定位为自动综述写作器。它的主要目标是帮助研究者做文献调研和管理：

1. 文献发现。
2. 文献分类。
3. 文献管理。
4. 领域地图构建。
5. 技术论文追踪。
6. 证据管理。
7. 研究空白发现。
8. 创新线索生成。
9. 中文调研材料生成。

`reports/final_report.md` 只是可选中文草稿或展示产物，不是项目核心终点。

项目必须避免重新滑向“综述生成系统”。综述论文的价值是建立领域地图，技术论文和系统论文的
价值是追踪前沿方法、架构和创新机会，benchmark/dataset 论文的价值是建立评估体系。全新领域
可以处理 50-70 篇高质量论文，但必须优先选择顶会、顶刊、高引用基础论文、权威技术报告、
主流 benchmark 和可复现系统，不能用低质量或弱相关论文凑数量。

项目采用清晰的职责分工：

- Codex / Agent 负责调度、检查、判断、质疑和中文综合。
- `litagent` 负责确定性工具执行，包括搜索、去重、下载、解析、初步分类、论文角色和阅读意图推断、初步阅读、知识构建、证据表（evidence table）构建、AutoWiki-compatible 导出、可选报告草稿、审计和质量信号输出。

核心原则是：`litagent` 不承担最终研究判断，Codex / Agent 必须检查中间产物并完成二次判断和中文综合。

## 当前能力

当前系统已经具备以下能力：

- 小规模真实综述（small real review）流程可以跑通。
- 搜索批次隔离（search run isolation）可用，搜索结果写入 `data/search_runs/{run_id}/`。
- 相关性敏感排序可用，并为论文生成 `score_explanation`。
- `review-selection` 可用，可以在下载前标记相关、可疑和偏题论文。
- 本地 `pypdf` 解析可用，适合普通文本 PDF。
- parsed Markdown notes 可用，笔记能区分元数据/摘要来源和全文解析来源。
- 证据表可用，输出 `knowledge/evidence_table.md` 和 `knowledge/evidence_table.json`。
- 证据表开始记录章节、`snippet_score`、质量说明和噪声标记，供 Agent 检查证据质量。
- `litagent report` 默认生成中文报告草稿，并优先使用高分证据片段。
- `build-knowledge` 生成研究工作台知识页，包括领域地图、技术前沿、方法矩阵、
  benchmark 矩阵、创新机会和阅读计划。
- `export-wiki` 可以把已有 workspace 产物导出为 AutoWiki-compatible vault，
  供 Obsidian 或 AutoWiki-skill 长期维护。
- `audit` 和 `inspect-workspace` 可用，可输出质量信号和阶段标签。
- `topic-run` 可用，能把一次主题调研流程编排为可恢复的后台任务雏形，并写入
  `run_state.json`、`run_log.jsonl`、`artifacts_manifest.json` 和 `errors.json`。

## 后台服务化路线

当前最重要的工程路线不是继续扩大论文数量，而是把 Autoresearch 变成稳定后台服务。

第一步是 `litagent topic-run`：

```bash
litagent topic-run "多模态模型" \
  --workspace ~/.autoresearch/topics/multimodal-models \
  --max-papers 50
```

它默认执行：

```text
plan -> search -> dedup -> review-selection -> download -> parse -> classify -> read
-> build-knowledge -> build-evidence -> export-wiki -> audit -> inspect-workspace
```

该命令的定位是稳定执行和记录状态，不是替代 Codex / Agent 的研究判断。它生成的状态文件将
成为后续 OpenClaw 手机端 `status`、失败重试、增量更新和通知的基础。

`topic-run` 当前输出：

- `run_state.json`：步骤状态、输入数量、输出数量、失败数量和时间戳。
- `run_log.jsonl`：事件流，用于后续 mobile status 和通知。
- `artifacts_manifest.json`：关键产物清单。
- `errors.json`：脱敏后的错误摘要。

后续后台化顺序应保持收敛：

1. 稳定 `topic-run` 和失败恢复。
2. 增加全局文献库（global library），区分全局唯一 paper 和 topic 视角。
3. 增加本地任务队列（job queue），只暴露白名单命令给 OpenClaw。
4. 再接 OpenClaw Research Skill、Obsidian 增量同步和音频摘要。

当前已经进入第二步的 MVP：`litagent sync-library` 可以把已有 workspace 产物同步到
SQLite `library.db`。

全局库当前表结构：

- `papers`：全局唯一论文。
- `topics`：研究主题。
- `topic_papers`：论文在某个 topic 下的角色、阅读意图、相关性和选择理由。
- `runs`：一次调研运行的状态、workspace、搜索批次和质量标签。
- `evidence_spans`：挂到 paper 和 topic 的证据片段。

命令：

```bash
litagent sync-library WORKSPACE --library-db ~/.autoresearch/library.db --topic-slug TOPIC
litagent library-status --library-db ~/.autoresearch/library.db --json
```

当前实现仍是同步层，不会改变 workspace 主流程，也不会自动替代 `selected_papers.jsonl`、
`library/notes` 或 `knowledge/evidence_table.*`。下一步 job queue 应复用这些状态和库表，
而不是让 OpenClaw 直接执行任意 shell。

当前已经进入第三步的 MVP：`litagent job` 提供本地 SQLite 任务队列。

命令：

```bash
litagent job create --topic "多模态模型" --workspace ~/.autoresearch/topics/multimodal-models
litagent job status JOB_ID --json
litagent job list --json
litagent job cancel JOB_ID --json
litagent job logs JOB_ID --json
litagent job run-next --json
```

`jobs.db` 当前只支持白名单 `topic-run` job。`job run-next` 以前台方式运行最早的 queued
job；如果创建任务时传入 `--sync-library`，成功后会同步到 `library.db`。这一步为 OpenClaw
提供安全接口，但还不是完整后台 daemon。后续可以在此基础上加 worker、进度通知和手机端
消息映射。

## 论文角色和阅读意图

当前采用双层分类。

`paper_role`：

- `survey_or_review`
- `technical_method`
- `system_paper`
- `benchmark_or_dataset`
- `position_or_perspective`
- `application_case`
- `background_foundation`

`reading_intent`：

- `build_field_map`
- `extract_method`
- `track_frontier`
- `compare_systems`
- `identify_benchmarks`
- `find_research_gap`
- `implementation_reference`

使用原则：

- 综述论文主要用于 `knowledge/field_map.md`，帮助建立领域地图。
- 技术论文和系统论文主要用于 `knowledge/technical_frontier.md` 和
  `knowledge/method_matrix.md`，帮助追踪前沿技术、比较系统设计、发现创新点。
- Benchmark / dataset 论文主要用于 `knowledge/benchmark_matrix.md`，帮助建立评估体系。
- Position/background 论文只能作为背景，不应主导技术路线判断。
- Application case 如果偏离“文献调研和管理工具”主题，应在 review-selection 和人工复核中降权。

## 研究工作台知识产物

`build-knowledge` 的核心输出现在包括：

- `knowledge/field_map.md`：领域划分、核心术语、代表方向，主要由综述和背景论文支持。
- `knowledge/technical_frontier.md`：最新系统、方法、架构、agent 设计和可复用模块。
- `knowledge/method_matrix.md`：横向比较系统/方法。
- `knowledge/benchmark_matrix.md`：汇总 benchmark/dataset 论文和评估资源。
- `knowledge/innovation_opportunities.md`：从技术论文和 benchmark 论文提炼创新线索。
- `knowledge/reading_plan.md`：推荐阅读顺序，区分“先读综述建地图”和“再读技术论文追踪前沿”。

`final_report.md` 不再是默认终点。未来 `report` 可支持以下模式，当前先作为路线图记录：

- `report --mode field-map`
- `report --mode technical-brief`
- `report --mode literature-review`
- `report --mode research-roadmap`
- `report --mode reading-guide`

## 当前基线

当前重要 workspace 基线如下：

- `./demo-agent-mock`：确定性 mock 流程基线，用于验证端到端流程。
- `./demo-real-small`：早期小规模真实检索基线，验证真实下载、pypdf 解析和审计。
- `./demo-real-v2`：8 篇真实相关论文基线，验证 evidence table 前后的报告改进方向。
- `./demo-real-v3`：证据质量回归基线，12 篇真实相关论文，完成下载、解析、阅读、证据表、报告、审计和 inspect。
- `./demo-real-v4`：来源多样性验证基线，官方 Semantic Scholar API 连通后完成 15 篇真实论文 run，达到 `source_diverse_real_review`，但仍不代表生产级研究工作台。

## demo-real-v3 证明了什么

`./demo-real-v3` 证明了：

- 可以处理 12 篇真实相关论文。
- 可以完成真实搜索、去重、下载、本地 pypdf 解析、分类、阅读、知识构建、证据表、报告、审计和 inspect。
- 下载成功率为 12/12。
- pypdf 解析成功率为 12/12。
- 笔记来自 parsed Markdown 的数量为 12。
- 抽象回退（abstract fallback）数量为 0。
- 证据表已经生成。
- 证据表当前包含 93 条 evidence snippets，其中 85 条为高质量片段，unknown section
  比例为 0%，noise section 比例约 1.1%。
- `audit` 结果为 PASS。
- `inspect-workspace` 标签为 `small_real_review`。

## demo-real-v3 没有证明什么

`./demo-real-v3` 没有证明：

- 没有证明来源多样性（source diversity）已经达到 `source_diverse_real_review`。
- 没有证明生产级综述（production quality review）能力。
- 没有证明复杂 PDF、OCR 密集 PDF 或表格密集论文可以稳定处理。
- 没有证明 deterministic report 足够接近人工研究综述。
- 没有证明 Semantic Scholar 可稳定使用，因为当前缺少 `SEMANTIC_SCHOLAR_API_KEY`。
- 没有证明 evidence extraction 已经足够干净，因为仍会抓到 references、headers、captions、prompts、code、tables 和 layout artifacts 等噪声。

## 当前冻结基线：demo-real-v3 after evidence quality scoring

本节冻结 commit `06207a4 Improve evidence quality scoring` 之后的 `./demo-real-v3`
证据质量基线。以后修改 `reader`、`evidence`、`report`、`audit` 或
`inspect-workspace` 时，应优先对照该基线。

基线记录：

- Workspace: `./demo-real-v3`
- Commit: `06207a4 Improve evidence quality scoring`
- Selected papers: 12
- Parse success: 12/12，使用本地 `pypdf`
- Abstract fallback: 0
- Evidence snippets: 93
- High-quality evidence snippets: 85
- Unknown section ratio: 0%
- Noise section ratio: about 1.1%
- Low-score ratio: about 2.2%
- Audit result: PASS
- Inspect label: `small_real_review`
- Remaining warning: final report 仍可能有泛化表述，需要 Codex / Agent 复核
  paper-specific support。

该基线证明了：

- 小规模真实综述流程可以在 12 篇真实论文上稳定完成。
- 本地 `pypdf` 对当前普通文本 PDF 集合可稳定生成 parsed Markdown。
- 证据表不再只是“存在”，而是包含 `section`、`snippet_score`、
  `snippet_score_explanation` 和 `quality_flags`。
- `audit` 和 `inspect-workspace` 能输出证据质量信号，而不只检查文件完整性。
- `litagent report` 可以生成中文报告草稿，并使用高质量 evidence 和 paper_id 支撑。

该基线没有证明：

- 没有证明来源多样性（source diversity）达到 `source_diverse_real_review`。
- 没有证明 Semantic Scholar 在配置 API key 后可以稳定贡献候选结果。
- 没有证明复杂 PDF、OCR 或表格密集论文可以稳定解析。
- 没有证明 deterministic report 已达到最终中文研究综述质量。
- 没有消除人工复核需求；`audit PASS` 仍不等于最终研究质量达标。

## 当前阶段定义

当前阶段正在从小规模真实综述原型（small_real_review prototype）转向研究型文献工作台原型。
`./demo-real-v4` 已证明在官方 Semantic Scholar API 可用时可以达到来源多样真实验证，但
项目核心仍是文献调研、管理、证据组织和技术前沿追踪，而不是自动综述写作。

这个阶段的含义是：

- 能用真实检索完成 8 到 15 篇相关论文的小规模综述流程。
- 能下载和解析开放获取 PDF。
- 能生成 parsed Markdown notes。
- 能生成证据表、研究工作台知识页和可选报告草稿。
- 能通过 audit 和 inspect 给出质量信号。
- 但仍需要 Codex / Agent 做最终判断、知识组织和中文研究级综合。

## 质量等级定义

### 冒烟测试（smoke_test_run）

只验证流程是否跑通，可以使用 mock 数据。它不代表真实综述质量，也不应用来判断研究结论。

典型条件：

- 使用 mock 搜索。
- 论文数量很少。
- 不要求真实下载或高质量解析。
- 报告可以是流程产物，不应作为真实研究报告。

### 小规模真实综述（small_real_review）

使用真实检索，通常有 8 到 15 篇相关论文。

最低要求：

- 使用真实 API 检索。
- selected papers 与主题相关。
- 下载和解析成功率合理。
- notes 主要来自 parsed Markdown。
- 证据表存在。
- evidence table、工作台知识页或可选 final report 有论文级引用。
- `review-selection` 没有严重 off-topic。
- `audit` 通过。

限制：

- 来源多样性可能不足。
- 证据片段可能有噪声。
- 工作台知识页可能仍需要人工整理；可选报告深度可能仍接近草稿。
- 证据表不能只检查“是否存在”，还要检查 `section`、`snippet_score`、
  `snippet_score_explanation` 和 `quality_flags`。
- 仍需要 Codex / Agent 人工判断和中文综合。

### 新领域文献工作台（field_literature_workspace）

用于陌生领域的系统性调研，不以写综述为终点。

最低要求：

- 论文规模通常为 50-70 篇，但必须通过质量筛选。
- 综述论文足够支撑 `field_map`，但不能主导全部结论。
- 技术论文和系统论文足够支撑 `technical_frontier`、`method_matrix` 和创新机会。
- Benchmark / dataset 论文足够支撑 `benchmark_matrix` 和评估路线。
- selected papers 优先来自顶会、顶刊、高引用基础论文、权威技术报告、主流 benchmark 或可复现系统。
- 偏应用、低相关、低质量或只做单一任务的论文应被标记为 questionable/off-topic 或降权。
- AutoWiki/Obsidian vault 应能让用户看到地图、论文速读、技术前沿、证据和创新线索。

### 来源多样真实验证（source_diverse_real_review）

这是下一阶段需要验证的质量等级。

最低要求：

- 至少两个或更多真实数据源有效参与。
- selected papers 不被单一来源垄断。
- `review-selection` 干净。
- 证据表质量较高。
- 证据表、工作台知识页和可选 final report 有明确的论文级支撑（paper-specific support）。
- 来源失衡不再是主要风险。

### 生产级综述（production_quality_review）

当前项目尚未达到。

生产级综述需要：

- 更大规模但受控的论文集合。
- 明确的纳入/排除标准。
- 可复查的检索策略。
- 高质量全文解析。
- 结构化证据链。
- 可靠的中文研究级综合。
- 人工审阅或严格质量门禁。
- 对引用可靠性、检索覆盖、证据质量和报告质量有明确评估。

## 下一阶段定义

下一阶段目标是：研究工作台质量增强 + AutoWiki-compatible 知识组织 + 来源多样性稳定回归。

当前已经完成章节感知证据抽取和来源多样性验证的第一轮。下一步不要继续围绕
`final_report.md` 优化，而应围绕文献管理、工作台知识页、AutoWiki/Obsidian 组织和
创新线索管理改进。

### 优先级 1：章节感知证据抽取（section-aware evidence extraction）

目标：

- 识别 Introduction、Method、Evaluation、Limitation、Conclusion 等章节。
- 降低 References、Appendix、prompt、code、table 和 layout artifacts 的权重。
- 让 evidence snippet 更干净、更可读、更适合支撑报告。

### 优先级 2：证据质量评分（evidence quality scoring）

目标：

- 每条 evidence snippet 记录 section。
- 每条 evidence snippet 有 `snippet_score`。
- 每条 evidence snippet 有 `snippet_score_explanation`。
- `audit` 和 `inspect-workspace` 能提示 evidence quality 问题。

### 优先级 3：中文研究级工作台材料生成

目标：

- `field_map`、`technical_frontier`、`method_matrix`、`benchmark_matrix`、
  `innovation_opportunities` 和 `reading_plan` 默认中文。
- Codex / Agent 基于证据表和工作台知识页做二次中文综合。
- `final_report.md` 只是可选展示草稿。
- 工作台材料包含：
  - 领域地图。
  - 技术前沿。
  - 系统/方法矩阵。
  - benchmark / dataset 矩阵。
  - 研究空白。
  - 创新线索。
  - 推荐阅读路径。

### 优先级 4：AutoWiki-compatible 知识库组织

目标：

- 使用 `litagent export-wiki WORKSPACE --format autowiki --out OUT_DIR` 导出现有 workspace。
- 不让 AutoWiki-skill 接管 search/download/parse。
- 让 AutoWiki 或 Obsidian 负责长期知识库组织、链接和复用。
- 保留 `litagent` 作为检索、筛选、解析和证据抽取层。
- 明确 `export-wiki` 只是 artifact 打包层，不等于 AutoWiki 级别的知识编译。
- Codex / Agent 必须使用 `autowiki` skill 对 source、note 和 evidence 做二次组织，形成
  里程碑主题、source 深度分析、Relations、Critical Analysis、阅读路径和创新路线。

当前 `./demo-real-v4` 的推荐 AutoWiki 风格 vault 是 `/app/workspace/autowiki-v4`，
入口为 `START_HERE.md`。旧的 `/app/workspace/wiki-vault-v4` 是模板式导出验证，不应作为
主要阅读界面。

## demo-real-v4 来源多样性基线

`./demo-real-v4` 用于验证来源多样性（source diversity），不是为了扩大规模。
第一次代理路径失败后，项目切换到官方 Semantic Scholar API，并使用
`demo-real-v4-official-ss` 完成有效验证。

当前记录：

- Search run ID: `demo-real-v4-official-ss`
- Raw results: 801
- Raw source distribution: Semantic Scholar 421, OpenAlex 361, arXiv 19
- Selected papers: 15
- Selected source distribution after merge: Semantic Scholar 12, arXiv 10, OpenAlex 5
- Download: 15/15
- pypdf parse: 15/15
- Abstract fallback: 0
- Evidence snippets: 93
- High-quality snippets: 80
- Unknown section ratio: 0%
- Noise section ratio: about 1.1%
- Low-score ratio: about 3.2%
- Audit: PASS
- Inspect label: `source_diverse_real_review`

该基线证明 Semantic Scholar 在官方 API key 可用时可以实际贡献候选和 selected set。
它仍没有证明生产级研究工作台，也没有证明复杂 PDF/OCR/table-heavy 论文可稳定处理。

建议运行条件：

- 配置 `SEMANTIC_SCHOLAR_API_KEY`；如使用兼容代理，还需配置
  `SEMANTIC_SCHOLAR_API_BASE_URL` 和 `SEMANTIC_SCHOLAR_API_AUTH_MODE=authorization_bearer`。
- 先运行 `litagent provider-smoke semantic-scholar --json`，确认最小 Semantic Scholar
  请求可以成功返回结果。该命令只做 1 条小查询，不创建新的 v4 run，不下载论文，也不会
  输出真实 API key。
- 使用 fresh workspace：`./demo-real-v4`。
- `max_papers=15`。
- 使用真实检索，不使用 mock。
- 使用 search run isolation。
- 下载前运行 `review-selection`。
- 解析优先使用本地 `pypdf`。
- MinerU 只用于复杂版面、OCR 或表格密集 PDF。
- 使用带章节和质量评分的 `build-evidence`。
- `report` 只是可选中文草稿。
- Codex / Agent 对证据表、工作台知识页和可选报告做二次综合。
- `inspect-workspace` 目标标签为 `source_diverse_real_review`；如果达不到，必须说明原因。

`demo-real-v4` 只有在满足以下条件时，才可以被认为比 `demo-real-v3` 前进：

- Semantic Scholar 实际贡献有效候选结果。
- selected papers 不再几乎全来自 arXiv/OpenAlex。
- `review-selection` clean，没有严重 questionable 或 off-topic。
- parse success 合理。
- abstract fallback 很低或为 0。
- evidence table 质量不低于 `demo-real-v3` 太多，尤其是 unknown section、
  noise section 和 low-score ratio 不能异常升高。
- evidence table、工作台知识页和可选 `final_report.md` 是中文 evidence-backed material，
  并包含 paper_id 支撑。
- `inspect-workspace` 至少保持 `small_real_review`；如果来源多样性足够，则可升级为
  `source_diverse_real_review`。

失败策略：

- 历史上 `demo-real-v4-initial` 通过已配置 key/proxy 路径返回 HTTP 403 Forbidden，
  实际贡献候选为 0，因此该 run 只能保持 `small_real_review`。
- 如果 Semantic Scholar provider smoke test 仍然返回 401、403、429 或无法解析 JSON，
  不应重新运行 `demo-real-v4`，应先修复 API key、auth mode、base URL、endpoint path
  或代理权限问题。
- 如果 Semantic Scholar 仍然返回 429 或有效候选很少，`demo-real-v4` 最多仍应标记为
  `small_real_review`，并说明 Semantic Scholar 未能有效贡献来源多样性。
- 如果 selected papers 仍几乎全来自 arXiv/OpenAlex，不能升级到
  `source_diverse_real_review`。
- 如果来源多样性改善但论文相关性、`review-selection` 结果或 evidence quality 明显下降，
  也不能升级质量标签。
- 来源多样性不能以牺牲主题相关性、合法开放获取下载、解析质量或证据质量为代价。

## 暂时不要做

- 不要在质量门禁不足时盲目扩大论文数量。进入全新领域时可以扩大到 50-70 篇，但必须按综述、
  技术论文、系统论文和 benchmark/dataset 分层筛选，并优先高质量来源。
- 不要急着接很多外部 MCP。
- 不要把 MinerU 作为默认解析路径。
- 不要把 deterministic report 当作最终研究报告。
- 不要继续无规划地“跑一轮发现问题加一个功能”。
