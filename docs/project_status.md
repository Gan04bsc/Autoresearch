# 项目阶段状态

## 项目愿景

`litagent` 面向“多智能体文献综述自动化工具”这一方向，目标是构建一个可追溯、可检查、可迭代的文献研究工作台。

项目采用清晰的职责分工：

- Codex / Agent 负责调度、检查、判断、质疑和中文综合。
- `litagent` 负责确定性工具执行，包括搜索、去重、下载、解析、初步分类、初步阅读、知识构建、证据表（evidence table）构建、报告草稿、审计和质量信号输出。

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
- `audit` 和 `inspect-workspace` 可用，可输出质量信号和阶段标签。

## 当前基线

当前重要 workspace 基线如下：

- `./demo-agent-mock`：确定性 mock 流程基线，用于验证端到端流程。
- `./demo-real-small`：早期小规模真实检索基线，验证真实下载、pypdf 解析和审计。
- `./demo-real-v2`：8 篇真实相关论文基线，验证 evidence table 前后的报告改进方向。
- `./demo-real-v3`：当前最佳基线，12 篇真实相关论文，完成下载、解析、阅读、证据表、报告、审计和 inspect。

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

当前阶段是小规模真实综述原型（small_real_review prototype）。

这个阶段的含义是：

- 能用真实检索完成 8 到 15 篇相关论文的小规模综述流程。
- 能下载和解析开放获取 PDF。
- 能生成 parsed Markdown notes。
- 能生成证据表和报告草稿。
- 能通过 audit 和 inspect 给出质量信号。
- 但仍需要 Codex / Agent 做最终判断和中文研究级综合。

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
- final report 有论文级引用。
- `review-selection` 没有严重 off-topic。
- `audit` 通过。

限制：

- 来源多样性可能不足。
- 证据片段可能有噪声。
- 报告深度可能仍接近草稿。
- 证据表不能只检查“是否存在”，还要检查 `section`、`snippet_score`、
  `snippet_score_explanation` 和 `quality_flags`。
- 仍需要 Codex / Agent 人工判断和中文综合。

### 来源多样真实综述（source_diverse_real_review）

这是下一阶段需要验证的质量等级。

最低要求：

- 至少两个或更多真实数据源有效参与。
- selected papers 不被单一来源垄断。
- `review-selection` 干净。
- 证据表质量较高。
- final report 有明确的论文级支撑（paper-specific support）。
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

下一阶段目标是：证据质量增强 + 中文研究级综合 + 来源多样性验证。

当前正在推进第一段：证据质量增强。该阶段不扩大论文规模，不启动
`./demo-real-v4`，不把 MinerU 改成默认解析路径。

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

### 优先级 3：中文研究级报告生成

目标：

- `litagent report` 可以生成中文报告草稿。
- Codex / Agent 基于证据表做二次中文综合。
- `final_report.md` 不再像英文模板。
- 报告包含：
  - 执行摘要。
  - 方法分类。
  - 系统对比。
  - 证据支撑的主题综合。
  - 研究空白。
  - 对 `litagent` 的设计启发。
  - 下一步路线图。

### 优先级 4：配置 Semantic Scholar API key 后的来源多样性验证

目标：

- 新 workspace：`./demo-real-v4`。
- `max_papers=15`。
- 配置 `SEMANTIC_SCHOLAR_API_KEY`。
- 验证是否可以达到 `source_diverse_real_review`。

## demo-real-v4 规划和验收标准

`./demo-real-v4` 暂时只用于验证来源多样性（source diversity），不是为了扩大规模。
在未配置 `SEMANTIC_SCHOLAR_API_KEY` 前，不应启动该 run。

建议运行条件：

- 配置 `SEMANTIC_SCHOLAR_API_KEY`；如使用兼容代理，还需配置
  `SEMANTIC_SCHOLAR_API_BASE_URL` 和 `SEMANTIC_SCHOLAR_API_AUTH_MODE=authorization_bearer`。
- 使用 fresh workspace：`./demo-real-v4`。
- `max_papers=15`。
- 使用真实检索，不使用 mock。
- 使用 search run isolation。
- 下载前运行 `review-selection`。
- 解析优先使用本地 `pypdf`。
- MinerU 只用于复杂版面、OCR 或表格密集 PDF。
- 使用带章节和质量评分的 `build-evidence`。
- `report` 默认生成中文草稿。
- Codex / Agent 对证据表和报告做二次综合。
- `inspect-workspace` 目标标签为 `source_diverse_real_review`；如果达不到，必须说明原因。

`demo-real-v4` 只有在满足以下条件时，才可以被认为比 `demo-real-v3` 前进：

- Semantic Scholar 实际贡献有效候选结果。
- selected papers 不再几乎全来自 arXiv/OpenAlex。
- `review-selection` clean，没有严重 questionable 或 off-topic。
- parse success 合理。
- abstract fallback 很低或为 0。
- evidence table 质量不低于 `demo-real-v3` 太多，尤其是 unknown section、
  noise section 和 low-score ratio 不能异常升高。
- `final_report.md` 是中文 evidence-backed report，并包含 paper_id 支撑。
- `inspect-workspace` 至少保持 `small_real_review`；如果来源多样性足够，则可升级为
  `source_diverse_real_review`。

失败策略：

- 如果 Semantic Scholar 仍然返回 429 或有效候选很少，`demo-real-v4` 最多仍应标记为
  `small_real_review`，并说明 Semantic Scholar 未能有效贡献来源多样性。
- 如果 selected papers 仍几乎全来自 arXiv/OpenAlex，不能升级到
  `source_diverse_real_review`。
- 如果来源多样性改善但论文相关性、`review-selection` 结果或 evidence quality 明显下降，
  也不能升级质量标签。
- 来源多样性不能以牺牲主题相关性、合法开放获取下载、解析质量或证据质量为代价。

## 暂时不要做

- 不要扩大到 30 或 50 篇论文。
- 不要急着接很多外部 MCP。
- 不要把 MinerU 作为默认解析路径。
- 不要把 deterministic report 当作最终研究报告。
- 不要继续无规划地“跑一轮发现问题加一个功能”。
