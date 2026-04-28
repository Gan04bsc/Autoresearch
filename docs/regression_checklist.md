# 回归检查清单

每次修改 `litagent` 的研究流程模块后，都应按照本文档检查是否破坏当前小规模真实综述原型（small_real_review prototype）基线。

当前主要回归基线是 `./demo-real-v3`。除非明确需要真实网络检索，否则优先使用已有 workspace 进行非网络验证。

## search / ranking

检查项：

- 是否仍能隔离 search run。
- 每次搜索是否写入 `data/search_runs/{run_id}/raw_results.jsonl`。
- `data/raw_results.jsonl` 是否只是最新搜索批次的兼容视图。
- selected papers 是否仍包含 `score_explanation`。
- 排名是否避免让高引用但泛泛相关的论文压过高度相关论文。
- 负面关键词是否能压低 robotics、traffic、swarm、game theory、reinforcement learning、medical、education、industry-only 等偏题结果。

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
- 是否区分 metadata/abstract-derived content 和 parsed-full-text-derived evidence。
- 是否提取 problem、method、agent roles、pipeline stages、retrieval/search、citation/evidence handling、evaluation、datasets/benchmarks、key findings、limitations、relevance。
- 是否明确标记缺失或不确定信息。

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
- 是否尽量避免 References、Appendix、prompts、code、tables、layout artifacts 等噪声。

`demo-real-v3` 基线：

- evidence table 已生成。
- 主题包括 multi-agent architecture、survey/literature review generation、systematic review workflow、paper reading agents、citation-aware synthesis、evaluation and benchmarks、limitations and open problems、design implications for litagent。
- 已知弱点：仍存在 prompts、code、table 和 layout artifacts 噪声片段。

## report

检查项：

- 是否使用中文输出。
- 是否 evidence-backed。
- 是否包含 taxonomy、comparison、gaps、roadmap。
- 是否有论文级引用。
- 是否避免泛泛而谈。
- 是否明确说明证据空白和当前限制。

`demo-real-v3` 基线：

- final report 有 12 个唯一 paper_id 引用。
- report 使用 evidence table 生成证据支撑主题。
- 质量可接受为 small_real_review，但仍不是中文研究级报告。
- 已知弱点：deterministic report 仍像英文模板，部分 representative evidence 片段有噪声。

## audit / inspect

检查项：

- `audit PASS` 是否仍不足以代表成功。
- `inspect-workspace` label 是否合理。
- 是否能发现 shallow report、weak evidence、source imbalance、parse failure、abstract fallback。
- 是否报告 selected count、downloaded PDF count、parsed Markdown count、parse success rate 和 note source counts。

`demo-real-v3` 基线：

- Audit: PASS
- Inspect label: `small_real_review`
- downloaded PDFs: 12
- parsed Markdown: 12
- notes from parsed Markdown: 12
- abstract fallback: 0
- evidence table exists: true
- 由于 Semantic Scholar 不可用且 selected papers 被 arXiv 主导，不应升级为 `source_diverse_real_review`。

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
