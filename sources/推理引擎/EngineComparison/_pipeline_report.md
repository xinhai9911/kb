# 转换报告：vLLM vs SGLang 跨引擎对比

## 输入

- **输入类型**：综合（多源知识库，非原始源码文件）。
- **来源**：`sources/推理引擎/vLLMSourceAnalysis/`（00-32 全模块）与 `sources/推理引擎/SGLangSourceAnalysis/`（00-19 全模块）；必要时核实源码快照（`Q:\AI\vllm\`、`Q:\AI\sglang-main\`）。
- **空文件**：0
- **排除文件**：两份 SourceAnalysis 之外的其他引擎知识库；源码中的 `test/`、`docs/` 等非核心目录。

## 版本

- vLLM 源码快照（2026，v1 EngineCore 时代）
- SGLang commit `21c88f8625f2e699543a1c34f41d6894ef342903`

## 阶段状态

| 阶段 | 状态 | 摘要 |
|---|---|---|
| 一 分析 | 完成 | 盘点两份知识库可对比维度，规划 12 个对比模块 |
| 二 规划 | 完成 | 模块目录 `NN-english-slug` 连续编号 00-11 |
| 三 逻辑分片 | 完成 | 每个对比代理只读自身维度对应知识库文件 |
| 四 生成 | 完成 | 12 代理产出 27 个对比文件，遵循统一模板与页脚 |
| 五 审查 | 完成 | 六维检查：页脚齐全、大小合规、修复 1 处断链（serving-observability → serving-comparison） |
| 六 优化 | 完成 | 跨文件引用对齐（`_part1`/`_part2` 链接归一）；生成根文件后链接全有效 |
| 七 硬化 | 完成 | skill.md 索引与文件清单一致；全文件 ≤8KB；零断链 |

## 覆盖率

- **模块级覆盖率**：12/12（100%）
- 覆盖维度：00-architecture、01-config、02-scheduler、03-kvcache-prefix、04-attention、05-sampling、06-speculative、07-distributed、08-quantization、09-multimodal-tool、10-serving、11-selection

## 章节到目标文件映射（摘要）

| 对比维度 | 产出文件 |
|---|---|
| 00-architecture | architecture-comparison.md、request-path-evolution.md |
| 01-config | config-comparison.md、config-comparison_part2.md |
| 02-scheduler | scheduler-comparison.md、scheduler-comparison_part2.md |
| 03-kvcache-prefix | kvcache-comparison.md、kvcache-comparison_part2.md |
| 04-attention | attention-comparison.md、attention-comparison_part2.md |
| 05-sampling | sampling-comparison.md、sampling-comparison_part2.md |
| 06-speculative | speculative-comparison.md、speculative-comparison_part2.md |
| 07-distributed | distributed-comparison.md、distributed-comparison_part2.md、eplb-comparison.md |
| 08-quantization | quantization-comparison.md、quantization-comparison_part2.md |
| 09-multimodal-tool | multimodal-comparison.md、tool-structure-comparison.md、tool-structure-comparison_part2.md |
| 10-serving | serving-comparison_part1.md、serving-comparison_part2.md、serving-observability.md |
| 11-selection | selection-guide.md、selection-guide_part2.md |

## 最终统计

- 目录数：13（12 对比模块 + 根）
- Markdown 文件数：27（对比文件）+ 3（根文件）= **30**
- 总大小：约 210KB；全部对比文件 ≤8KB

## 遗留问题

- 性能类结论为机制性差异，不含未经验证的 benchmark 量化数字。
- 两份知识库源码快照日期不同（vLLM 与 SGLang 快照年份一致均为 2026），跨版本细节以各自知识库记录为准。
- 对比库不重复两引擎内部实现细节，深挖单引擎请回到对应 SourceAnalysis。
