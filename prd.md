# PRD：Agentic Literature Research Workbench（文献调研与知识体系构建 Agent）

## 1. 产品概述

### 1.1 产品定位

本产品([github.com](https://github.com/snarktank/ralph?utm_source=chatgpt.com))术战略分析等场景的“Agentic 文献调研与知识管理工作台”。用户只需要输入一句自然语言主题描述，例如：

> 我想快速了解多智能体文献综述自动化工具的发展现状、核心方法、代表论文、开源系统和未来创新方向。

系统应自动完成：主题理解、检索式扩展、多源论文搜索、元数据去重、开放获取 PDF 下载、本地文献库管理、论文分类、综述论文与技术论文差异化解读、基础知识体系生成、问题-方法-结论-创新方向抽取、知识库落盘与可追溯引用。

### 1.2 产品目标

MVP 阶段目标：

1. 用户输入一个研究主题，系统自动生成检索计划。
2. 系统从 arXiv、Semantic Scholar、OpenAlex、Crossref/Unpaywall 等来源检索论文元数据。
3. 系统自动筛选、去重、排序论文，并下载可合法获取的开放 PDF。
4. 系统将论文整理成本地项目知识库，包括 metadata、PDF、markdown 笔记、综述报告、主题地图。
5. 系统区分“综述论文”和“技术类论文”，使用两套不同提示词生成结构化解读。
6. 系统生成一份“快速入门该领域”的基础知识框架和研究路线图。
7. 系统输出后续可研究/创新方向，并保留证据引用。
8. 系统可被 Ralph 按 PRD 自动迭代构建、测试和验收。

### 1.3 非目标

MVP 不做以下事情：

1. 不绕过付费墙，不下载非法 PDF。
2. 不承诺生成可直接发表的系统综述论文。
3. 不替代 Zotero 的完整文献管理能力。
4. 不做复杂多人协作、权限系统、Web 账号体系。
5. 不做商业数据库接入，例如 Web of Science、Scopus，除非用户后续配置合法 API。
6. 不依赖浏览器自动化抓取 Google Scholar，避免违反服务条款和反爬限制。

------

## 2. 目标用户与使用场景

### 2.1 目标用户

1. 研究生、博士生、科研人员：需要快速进入一个新方向。
2. AI/软件工程师：需要理解某类技术路线、开源实现和论文脉络。
3. 产品经理/创业者：需要判断某个技术领域是否有产品机会。
4. 投资/战略分析人员：需要把学术技术趋势转化为结构化判断。
5. 独立研究者：需要长期维护自己的领域知识库。

### 2.2 核心用户故事

#### US-001：输入主题并启动调研

作为用户，我希望输入一句自然语言主题，让系统自动拆解研究范围、关键词、同义词、相关子领域和排除项。

验收标准：

- 输入主题后，系统生成 `research_plan.md`。
- 计划中包含：核心问题、关键词、英文检索式、中文解释、预期子主题、排除范围、检索来源、排序策略。
- 用户可以手动编辑该计划后继续执行。

#### US-002：自动检索论文

作为用户，我希望系统从多个开放学术来源搜索相关论文。

验收标准：

- 系统至少支持 arXiv、Semantic Scholar、OpenAlex 三个来源。
- 每篇论文保存 title、authors、year、venue、abstract、doi、arxiv_id、semantic_scholar_id、openalex_id、citation_count、reference_count、url、pdf_url、source。
- 检索结果写入 `data/raw_results.jsonl`。
- 归并后的结果写入 `data/papers.jsonl`。

#### US-003：论文去重与排序

作为用户，我希望系统去除重复论文，并按相关度和影响力排序。

验收标准：

- DOI 相同的论文合并。
- arXiv ID 相同的论文合并。
- 标题高度相似的论文合并。
- 每篇论文生成 `relevance_score`、`importance_score`、`recency_score`、`final_score`。
- Top N 论文写入 `data/selected_papers.jsonl`。

#### US-004：合法下载开放 PDF

作为用户，我希望系统自动下载可以合法获取的 PDF。

验收标准：

- arXiv 论文可下载 PDF。
- DOI 论文优先通过 Unpaywall 查找开放获取 PDF。
- 下载失败时记录原因，不中断主流程。
- PDF 保存到 `library/pdfs/{paper_id}.pdf`。
- 下载日志保存到 `logs/downloads.jsonl`。

#### US-005：论文类型分类

作为用户，我希望系统自动判断论文是综述论文、技术论文、benchmark/dataset 论文、position/opinion 论文或工具系统论文。

验收标准：

- 每篇论文生成 `paper_type`。
- 至少支持：`survey`、`technical`、`benchmark`、`dataset`、`system`、`position`、`unknown`。
- 分类结果保存在每篇论文 metadata 中。
- 分类依据应可解释，例如 title/abstract 中的 evidence。

#### US-006：综述论文解读

作为用户，我希望系统用专门提示词解读综述论文，帮助我快速理解领域边界、分类体系、代表工作和趋势。

验收标准：

- 对每篇 survey 生成 `library/notes/{paper_id}.md`。
- 输出结构包括：
  - 论文基本信息
  - 研究领域与问题范围
  - 综述组织框架
  - 领域基础概念
  - 代表方法/路线分类
  - 关键论文列表
  - 争议点与未解决问题
  - 对初学者的阅读价值
  - 可继续追踪的引用和关键词

#### US-007：技术论文解读

作为用户，我希望系统用专门提示词解读技术类论文，抓住问题、场景、方法、核心思想、实验结论和创新空间。

验收标准：

- 对每篇 technical/system/benchmark/dataset 论文生成 `library/notes/{paper_id}.md`。
- 输出结构包括：
  - 论文基本信息
  - 面临的问题/应用情景
  - 为什么已有方法不足
  - 核心方法与关键创新
  - 系统架构/算法流程
  - 数据集与实验设置
  - 主要结论
  - 局限性
  - 可以继续研究/改进的方向
  - 对该领域知识体系的贡献

#### US-008：领域基础知识体系生成

作为用户，我希望系统生成“快速了解这个领域”的基础知识体系。

验收标准：

- 输出 `knowledge/base_knowledge.md`。
- 内容包括：
  - 领域一句话定义
  - 为什么这个领域重要
  - 关键术语表
  - 前置知识
  - 核心问题列表
  - 主流技术路线
  - 代表论文阅读顺序
  - 初学者 1 天 / 1 周 / 1 个月学习路线

#### US-009：领域主题地图与知识库框架

作为用户，我希望系统自动生成领域主题树和知识库目录。

验收标准：

- 输出 `knowledge/topic_map.md`。
- 输出 `knowledge/index.md`。
- 主题地图至少包含 3 层：领域 -> 子方向 -> 代表问题/方法/论文。
- 每个主题节点关联相关论文。
- Markdown 文件可被 Obsidian 直接打开。

#### US-010：最终调研报告生成

作为用户，我希望系统生成一份可以快速阅读的领域调研报告。

验收标准：

- 输出 `reports/final_report.md`。
- 报告包括：
  - Executive Summary
  - 领域背景
  - 核心问题
  - 技术路线分类
  - 代表论文表格
  - 综述论文结论综合
  - 技术论文结论综合
  - 目前未解决问题
  - 未来研究/创新方向
  - 推荐阅读顺序
  - 附录：检索式、数据源、失败下载列表

#### US-011：可追溯引用

作为用户，我希望所有总结尽量能追溯到论文。

验收标准：

- 每条关键结论后标注 paper_id 或文献短引用。
- `reports/final_report.md` 中包含参考文献列表。
- 每篇 notes 文件包含原始 metadata。

#### US-012：增量更新

作为用户，我希望后续输入同一主题时，系统只新增处理新论文。

验收标准：

- 系统读取已有 `data/papers.jsonl`。
- 重复论文不重复下载和分析。
- 新论文补充进 knowledge/topic_map 和 final_report。
- 生成 `logs/update_report.md`。

------

## 3. 功能模块设计

### 3.1 Research Planner Agent

输入：用户主题描述。

输出：`research_plan.md` 和结构化 `research_plan.json`。

职责：

1. 识别研究目标。
2. 生成关键词、同义词、相关概念。
3. 生成多组检索式。
4. 规划检索来源。
5. 定义筛选标准。
6. 定义论文分类标准。

### 3.2 Search Agent

输入：`research_plan.json`。

输出：`data/raw_results.jsonl`。

职责：

1. 调用 arXiv API。
2. 调用 Semantic Scholar Graph API。
3. 调用 OpenAlex Works API。
4. 可选调用 Crossref。
5. 统一 metadata schema。
6. 保存原始结果。

### 3.3 Dedup & Ranking Agent

输入：`data/raw_results.jsonl`。

输出：`data/papers.jsonl`、`data/selected_papers.jsonl`。

职责：

1. DOI/arXiv ID/标题相似度去重。
2. 计算相关度。
3. 结合引用数、年份、venue、是否有 PDF 等因素排序。
4. 选择 Top N。

### 3.4 Download Agent

输入：`data/selected_papers.jsonl`。

输出：PDF 文件与下载日志。

职责：

1. arXiv PDF 下载。
2. Unpaywall 查询开放获取版本。
3. 记录失败原因。
4. 校验 PDF 文件是否有效。

### 3.5 Metadata & Library Manager

职责：

1. 维护本地目录。
2. 生成 BibTeX/CSL JSON。
3. 为每篇论文分配稳定 ID。
4. 支持 Zotero 导出/导入兼容格式。

建议目录结构：

```text
research-workspace/
  config/
    sources.yaml
    prompts/
      planner.md
      survey_reader.md
      technical_reader.md
      synthesis.md
  data/
    raw_results.jsonl
    papers.jsonl
    selected_papers.jsonl
  library/
    pdfs/
    notes/
    metadata/
  knowledge/
    index.md
    base_knowledge.md
    topic_map.md
    glossary.md
  reports/
    final_report.md
  logs/
    downloads.jsonl
    runs.jsonl
    update_report.md
```

### 3.6 Paper Classifier Agent

职责：

1. 根据 title、abstract、venue、sections 判断论文类型。
2. 为下游选择提示词。

分类标签：

- survey
- technical
- benchmark
- dataset
- system
- position
- unknown

### 3.7 Paper Reader Agent

职责：

1. 解析 PDF 文本。
2. 根据论文类型选择提示词。
3. 生成单篇论文 Markdown 解读。
4. 提取关键 claims、limitations、future work。

### 3.8 Knowledge Builder Agent

职责：

1. 汇总所有 notes。
2. 生成基础知识体系。
3. 生成主题地图。
4. 生成术语表。
5. 生成阅读路线。

### 3.9 Synthesis Agent

职责：

1. 对多篇论文进行横向对比。
2. 识别主要技术路线。
3. 归纳未解决问题。
4. 提出可研究/创新方向。
5. 生成最终调研报告。

### 3.10 QA / Audit Agent

职责：

1. 检查下载文件是否存在。
2. 检查 notes 是否完整。
3. 检查 final_report 是否包含引用。
4. 检查是否有明显 hallucination 风险。
5. 检查所有验收标准是否满足。

------

## 4. 数据模型

### 4.1 Paper Schema

```json
{
  "paper_id": "string",
  "title": "string",
  "authors": ["string"],
  "year": 2025,
  "venue": "string",
  "abstract": "string",
  "doi": "string|null",
  "arxiv_id": "string|null",
  "semantic_scholar_id": "string|null",
  "openalex_id": "string|null",
  "citation_count": 0,
  "reference_count": 0,
  "url": "string|null",
  "pdf_url": "string|null",
  "local_pdf_path": "string|null",
  "source": ["arxiv", "semantic_scholar", "openalex"],
  "paper_type": "survey|technical|benchmark|dataset|system|position|unknown",
  "relevance_score": 0.0,
  "importance_score": 0.0,
  "recency_score": 0.0,
  "final_score": 0.0,
  "download_status": "success|failed|skipped",
  "download_error": "string|null"
}
```

### 4.2 Research Plan Schema

```json
{
  "topic": "string",
  "goal": "string",
  "core_questions": ["string"],
  "include_keywords": ["string"],
  "exclude_keywords": ["string"],
  "search_queries": {
    "arxiv": ["string"],
    "semantic_scholar": ["string"],
    "openalex": ["string"]
  },
  "date_range": {
    "from": 2018,
    "to": 2026
  },
  "max_results_per_source": 50,
  "selection_count": 30,
  "ranking_policy": "string"
}
```

------

## 5. 两套核心提示词

### 5.1 综述论文解读 Prompt

```text
你是一个严谨的科研文献综述助手。请阅读以下综述论文内容和 metadata，目标不是简单摘要，而是帮助用户快速理解该领域的知识结构。

请输出 Markdown，必须包含：

1. 基本信息
- 标题
- 作者
- 年份
- 论文类型：survey
- 适合读者

2. 这篇综述覆盖的领域边界
- 它研究什么问题？
- 它不研究什么问题？
- 它试图解决读者的什么困惑？

3. 领域基础知识
- 初学者需要先知道哪些概念？
- 请给出术语表。

4. 综述组织框架
- 作者如何分类这个领域？
- 每个类别的核心思想是什么？
- 这些类别之间是什么关系？

5. 代表工作
- 列出作者反复提到或明显重要的代表论文/方法。
- 对每个代表工作说明其作用。

6. 领域演化脉络
- 早期方法是什么？
- 后续如何改进？
- 当前主流方向是什么？

7. 争议点与开放问题
- 该领域还有哪些没有解决的问题？
- 哪些问题存在不同路线？

8. 对我的价值
- 如果我要快速进入这个领域，这篇综述应该怎么读？
- 哪些章节最重要？
- 读完后应该继续看哪些类型论文？

9. 可追踪引用
- 列出文中出现的关键论文、关键词和可能的后续检索式。

要求：
- 不要编造论文中没有的信息。
- 如果信息不足，请明确写“原文信息不足”。
- 每个关键结论尽量关联原文证据或章节。
```

### 5.2 技术类论文解读 Prompt

```text
你是一个严谨的技术论文分析助手。请阅读以下论文内容和 metadata，目标是帮助用户快速理解这篇论文面对的问题、解决思路、核心创新、实验结论和后续研究方向。

请输出 Markdown，必须包含：

1. 基本信息
- 标题
- 作者
- 年份
- 论文类型：technical/system/benchmark/dataset
- 一句话贡献

2. 问题/情景
- 这篇论文面对的具体问题是什么？
- 该问题出现在哪些应用场景中？
- 为什么这个问题重要？

3. 现有方法的不足
- 作者认为之前的方法有什么缺陷？
- 是性能、成本、泛化、数据、评估还是部署问题？

4. 核心思想
- 这篇论文最核心的 idea 是什么？
- 请用非专业读者也能理解的方式解释。

5. 方法/系统设计
- 方法由哪些模块组成？
- 输入输出是什么？
- 关键算法流程是什么？
- 如果是系统论文，请描述系统架构。

6. 实验与证据
- 使用了哪些数据集？
- 和哪些 baseline 比较？
- 主要指标是什么？
- 最重要的实验结论是什么？

7. 结论
- 作者最终证明了什么？
- 哪些结论是强证据支持的？
- 哪些只是推测？

8. 局限性
- 作者承认了哪些局限？
- 你从论文中还能看出哪些潜在局限？请标明这是你的推断。

9. 后续研究/创新方向
- 可以从哪些方向继续改进？
- 可以迁移到哪些新场景？
- 有哪些值得做成产品/系统的机会？

10. 对知识体系的贡献
- 这篇论文应该放到哪个主题节点下？
- 它与哪些已有路线互补、冲突或延伸？

要求：
- 不要编造实验数字。
- 原文没有的信息必须标注“原文未说明”。
- 明确区分作者结论和你的推断。
```

------

## 6. 技术架构建议

### 6.1 推荐技术栈

MVP 推荐：

- 语言：Python 3.11+
- CLI：Typer 或 Click
- 配置：YAML + Pydantic
- 数据存储：JSONL + SQLite
- PDF 解析：PyMuPDF / pypdf / GROBID 可选
- 向量检索：LanceDB / Chroma / FAISS，MVP 可延后
- LLM 调用：OpenAI-compatible SDK，支持本地模型或云模型
- 工作流：LangGraph 可选；MVP 可先用显式 pipeline
- Markdown 知识库：Obsidian-compatible Markdown
- 测试：pytest
- 代码质量：ruff + mypy 可选

### 6.2 为什么 MVP 不建议一开始就做复杂多 Agent 框架

Ralph 已经负责“工程实现的 agent loop”。产品内部的文献 agent 工作流建议先做成可测试的确定性 pipeline：

```text
plan -> search -> dedup -> rank -> download -> classify -> read -> build knowledge -> synthesize -> audit
```

等 MVP 稳定后，再把每一步替换成真正的 planner/router/multi-agent。

### 6.3 API 来源

- arXiv：用于 arXiv 论文检索和 PDF 下载。
- Semantic Scholar Graph API：用于论文搜索、引用、参考文献、推荐论文。
- OpenAlex：用于大规模学术作品元数据检索。
- Unpaywall：用于通过 DOI 查找开放获取版本。

------

## 7. Ralph 实现计划

### 7.1 Ralph 使用方式定位

Ralph 不直接帮你“跑文献调研”；它帮你“根据 PRD 自动搭建这个文献调研系统”。因此你应该把 Ralph 当成 autonomous coding orchestrator。

### 7.2 仓库初始化

建议创建仓库：

```text
literature-agent/
  README.md
  AGENTS.md
  prd.md
  progress.md
  pyproject.toml
  src/litagent/
  tests/
  examples/
```

### 7.3 AGENTS.md 建议内容

```text
# AGENTS.md

You are building a Python CLI application called litagent.

Principles:
- Implement the PRD incrementally.
- Prefer deterministic, testable pipeline steps over opaque agent behavior.
- Never bypass paywalls or download copyrighted PDFs illegally.
- All external API calls must be wrapped behind interfaces and mockable in tests.
- Every feature must include tests.
- All outputs must be written to the workspace directory.
- Preserve user data and avoid deleting files unless explicitly requested.

Commands:
- Install: pip install -e .[dev]
- Test: pytest
- Lint: ruff check .

Definition of done:
- Tests pass.
- CLI command documented.
- Output files match PRD schema.
- Errors are logged without crashing the whole pipeline.
```

### 7.4 Ralph 可执行任务拆分

把 PRD 拆成 Ralph 易完成的小故事：

#### Milestone 1：项目骨架

- 创建 Python 包结构。
- 创建 CLI 命令 `litagent init`。
- 创建 workspace 目录结构。
- 添加 pytest 和 ruff。

验收：

- `litagent init ./demo` 生成所有目录。
- `pytest` 通过。

#### Milestone 2：Research Planner

- 实现 `litagent plan "topic"`。
- 输出 `research_plan.json` 和 `research_plan.md`。
- LLM 不可用时用 fallback template。

验收：

- 输入主题后生成结构化检索计划。
- schema 校验通过。

#### Milestone 3：Search Providers

- 实现 provider interface。
- 实现 arXiv provider。
- 实现 Semantic Scholar provider。
- 实现 OpenAlex provider。
- 所有 provider 支持 mock tests。

验收：

- `litagent search ./workspace` 写入 `data/raw_results.jsonl`。
- 单元测试不依赖真实网络。

#### Milestone 4：Dedup & Ranking

- 实现论文 schema。
- 实现 DOI/arXiv/title 去重。
- 实现排序函数。

验收：

- 测试覆盖重复 DOI、重复 arXiv、近似标题。
- 输出 `papers.jsonl` 和 `selected_papers.jsonl`。

#### Milestone 5：PDF Download

- 实现 arXiv PDF 下载。
- 实现 Unpaywall OA 查询。
- 实现下载失败日志。

验收：

- 可下载 PDF 保存到 `library/pdfs`。
- 失败不终止流程。

#### Milestone 6：PDF Parsing

- 实现 PDF 文本抽取。
- 长文本按 section/chunk 保存。
- 解析失败可降级到 abstract-only。

验收：

- 给定样例 PDF 可抽取文本。
- 输出 `library/metadata/{paper_id}.json`。

#### Milestone 7：Paper Classification

- 实现规则分类器。
- 可选 LLM 分类器。
- 输出 paper_type。

验收：

- survey/benchmark/technical 样例测试通过。

#### Milestone 8：Paper Reader

- 加入两套 prompts。
- 根据 paper_type 调用不同 reader。
- 输出 `library/notes/{paper_id}.md`。

验收：

- survey 论文使用 survey prompt。
- technical 论文使用 technical prompt。
- notes 包含必需章节。

#### Milestone 9：Knowledge Builder

- 汇总 notes。
- 生成 base_knowledge、glossary、topic_map、index。

验收：

- 输出文件存在。
- 每个主题节点至少关联一篇论文。

#### Milestone 10：Final Report

- 生成最终调研报告。
- 生成推荐阅读顺序。
- 生成未来方向。

验收：

- `reports/final_report.md` 包含 PRD 要求章节。
- 关键结论带 paper_id 引用。

#### Milestone 11：Audit

- 实现 `litagent audit ./workspace`。
- 检查 schema、文件完整性、引用、下载状态。

验收：

- audit 生成 `logs/audit_report.md`。
- 缺失项清晰列出。

#### Milestone 12：End-to-end CLI

- 实现 `litagent run "topic" --workspace ./demo --max-papers 30`。
- 串起全流程。

验收：

- 一条命令完成 plan/search/dedup/download/read/synthesis/audit。
- 任一步失败都有日志，流程尽量继续。

------

## 8. Ralph Prompt 模板

建议给 Ralph 的首轮任务：

```text
You are working in the literature-agent repository.

Your job is to implement the PRD in prd.md using small, verifiable increments.

Rules:
1. Read prd.md, AGENTS.md, and progress.md first.
2. Pick the highest-priority incomplete milestone.
3. Implement only one milestone or one coherent slice at a time.
4. Add or update tests.
5. Run tests and lint.
6. Update progress.md with what was completed, what failed, and next recommended task.
7. Do not claim completion unless tests pass.
8. Do not implement paywall bypassing or scraping that violates terms.

Start with Milestone 1 unless it is already complete.
```

### 8.1 progress.md 模板

```text
# Progress

## Completed

- [ ] Milestone 1: Project skeleton
- [ ] Milestone 2: Research planner
- [ ] Milestone 3: Search providers
- [ ] Milestone 4: Dedup & ranking
- [ ] Milestone 5: PDF download
- [ ] Milestone 6: PDF parsing
- [ ] Milestone 7: Paper classification
- [ ] Milestone 8: Paper reader
- [ ] Milestone 9: Knowledge builder
- [ ] Milestone 10: Final report
- [ ] Milestone 11: Audit
- [ ] Milestone 12: End-to-end CLI

## Current Notes

## Known Issues

## Next Task
```

------

## 9. CLI 设计

```bash
litagent init ./my-topic
litagent plan "agentic literature review tools" --workspace ./my-topic
litagent search ./my-topic
litagent dedup ./my-topic
litagent download ./my-topic
litagent classify ./my-topic
litagent read ./my-topic
litagent build-knowledge ./my-topic
litagent report ./my-topic
litagent audit ./my-topic
litagent run "agentic literature review tools" --workspace ./my-topic --max-papers 30
```

------

## 10. 验收测试示例

### 10.1 单元测试

- test_workspace_init.py
- test_research_plan_schema.py
- test_arxiv_provider_mapping.py
- test_semantic_scholar_provider_mapping.py
- test_openalex_provider_mapping.py
- test_dedup.py
- test_ranking.py
- test_download_logging.py
- test_paper_classifier.py
- test_note_required_sections.py
- test_report_required_sections.py
- test_audit.py

### 10.2 集成测试

使用 mock providers：

```bash
litagent run "test topic" --workspace ./tmp/demo --mock
```

验收：

- 所有核心输出文件存在。
- `final_report.md` 包含至少 5 篇 mock 论文引用。
- audit 通过。

------

## 11. 风险与约束

### 11.1 法律与版权风险

- 只能下载开放获取 PDF。
- 不能绕过出版社访问控制。
- 付费文献只保存 metadata 和链接。

### 11.2 质量风险

- LLM 可能幻觉。
- PDF 解析可能漏掉公式、表格、图。
- 自动分类可能错误。

缓解措施：

- 把“作者结论”和“模型推断”分开。
- 关键结论必须带 paper_id。
- audit 检查引用缺失。
- 保留原文 PDF 与 metadata。

### 11.3 工程风险

- API rate limit。
- 不同来源 metadata 不一致。
- PDF 下载失败。

缓解措施：

- provider 层统一异常处理。
- 加缓存。
- 下载失败不影响整体流程。
- 所有 API key 放在环境变量。

------

## 12. MVP 成功指标

1. 输入一个主题，30 分钟内完成 20-30 篇论文的检索、筛选、下载和 notes 生成。
2. 自动生成的 `base_knowledge.md` 能让用户在 10 分钟内了解领域框架。
3. 自动生成的 `final_report.md` 至少包含 5 个子方向、10 篇代表论文、5 个未来研究方向。
4. 90% 以上输出结论可追溯到 paper_id。
5. 用户可以在 Obsidian 中直接打开知识库。
6. Ralph 可以根据 progress.md 持续迭代实现功能。

------

## 13. 后续增强方向

1. Zotero 集成：导入/导出 Zotero collection。
2. Obsidian 插件：直接在 Obsidian 内触发调研。
3. 引用网络：基于 references/citations 进行 forward/backward snowballing。
4. 向量问答：对本地 PDF 和 notes 做 RAG。
5. 图谱可视化：主题、论文、方法、作者关系图。
6. 多轮调研：用户基于报告继续追问，系统增量补充。
7. 人工审核 UI：让用户接受/拒绝论文和主题分类。
8. Benchmark 模式：对比不同论文方法和实验结果。
9. AutoWiki 集成：把最终知识库编译成更强的 Obsidian Wiki。

------

## 14. 推荐第一版实现范围

第一版不要做太大，建议只做：

1. CLI。
2. arXiv + Semantic Scholar + OpenAlex 搜索。
3. Unpaywall 开放 PDF 下载。
4. JSONL/Markdown 本地知识库。
5. 两套 prompts。
6. final_report。
7. audit。
8. mock 测