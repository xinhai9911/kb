# vLLM vs SGLang 跨引擎对比 Skill

基于两份源码分析知识库（`vLLMSourceAnalysis` 与 `SGLangSourceAnalysis`）的**综合层对比索引**，按 12 个维度逐项对照两引擎的架构决策与实现差异。

## 全局配置

```yaml
# 对比对象
left_engine: vLLM（vLLMSourceAnalysis，00-32 全模块）
right_engine: SGLang（SGLangSourceAnalysis，00-19 全模块）
# 综合来源
vllm_kb: sources/推理引擎/vLLMSourceAnalysis
sglang_kb: sources/推理引擎/SGLangSourceAnalysis
analysis_language: zh-CN
# 文档约定
heading_base_level: "##"
file_size_limit: 8KB
# 覆盖范围
module_count: 12
markdown_file_count: 27
```

## AI 使用流程

1. 先读本文件定位对比主题，按「对比维度 → 文件路径」进入对应模块。
2. 每个对比模块优先读 `-comparison` 首文件建立逐维度对照表，再读 `_part2`/专门文件（eplb、selection 等）深化。
3. 需要原始实现细节时回到两份 SourceAnalysis 知识库对应模块核对。
4. 选型结论看 `11-selection/`；排查单引擎问题仍以对应引擎知识库为准。

## 全局约定

- vLLM 侧路径写为相对 `vllm/vllm/` 的形式（如 `v1/engine/core.py`）；SGLang 侧写为相对 `python/sglang/` 的形式（如 `srt/managers/scheduler.py`）。
- 对比结论基于两份知识库与源码快照（vLLM 与 SGLang 源码均为 2026 年快照），不编造 benchmark 数字。
- 性能类表述一律为**机制性差异**（如前缀复用模型、调度策略），不做未经验证的吞吐/延迟量化对比。
- 每个模块文件 ≤8KB；超限按 `_part1`/`_part2` 拆分。
- 模块文件末尾统一返回链接至本文件与 `faq.md`。

## 子文档索引

| 对比维度 | 文件路径 |
|---|---|
| 进程模型与通信协议 | [00-architecture/architecture-comparison.md](00-architecture/architecture-comparison.md) |
| 请求端到端路径与两代演进 | [00-architecture/request-path-evolution.md](00-architecture/request-path-evolution.md) |
| 配置载体与参数装配 | [01-config/config-comparison.md](01-config/config-comparison.md) |
| 校验/哈希与关键参数对照 | [01-config/config-comparison_part2.md](01-config/config-comparison_part2.md) |
| 调度模型与批构建 | [02-scheduler/scheduler-comparison.md](02-scheduler/scheduler-comparison.md) |
| 调度策略/chunked prefill/抢占 | [02-scheduler/scheduler-comparison_part2.md](02-scheduler/scheduler-comparison_part2.md) |
| KV 块管理与前缀缓存 | [03-kvcache-prefix/kvcache-comparison.md](03-kvcache-prefix/kvcache-comparison.md) |
| 分层缓存/显存分配/命中率 | [03-kvcache-prefix/kvcache-comparison_part2.md](03-kvcache-prefix/kvcache-comparison_part2.md) |
| 注意力后端抽象与注册表 | [04-attention/attention-comparison.md](04-attention/attention-comparison.md) |
| 前缀缓存衔接/KV 布局/平台选择 | [04-attention/attention-comparison_part2.md](04-attention/attention-comparison_part2.md) |
| SamplingParams 与批量张量化 | [05-sampling/sampling-comparison.md](05-sampling/sampling-comparison.md) |
| 采样后端/logits 处理/惩罚器 | [05-sampling/sampling-comparison_part2.md](05-sampling/sampling-comparison_part2.md) |
| 投机解码架构集成与草稿后端 | [06-speculative/speculative-comparison.md](06-speculative/speculative-comparison.md) |
| EAGLE 实现差异与调度衔接 | [06-speculative/speculative-comparison_part2.md](06-speculative/speculative-comparison_part2.md) |
| 并行维度与初始化 | [07-distributed/distributed-comparison.md](07-distributed/distributed-comparison.md) |
| 通信架构 | [07-distributed/distributed-comparison_part2.md](07-distributed/distributed-comparison_part2.md) |
| 专家并行负载均衡（EPLB） | [07-distributed/eplb-comparison.md](07-distributed/eplb-comparison.md) |
| 量化抽象/方法/内核 | [08-quantization/quantization-comparison.md](08-quantization/quantization-comparison.md) |
| 量化加载/硬件后端/在线量化 | [08-quantization/quantization-comparison_part2.md](08-quantization/quantization-comparison_part2.md) |
| 多模态输入与生成 | [09-multimodal-tool/multimodal-comparison.md](09-multimodal-tool/multimodal-comparison.md) |
| 工具调用与约束解码 | [09-multimodal-tool/tool-structure-comparison.md](09-multimodal-tool/tool-structure-comparison.md) |
| Reasoning 与流式解析路线 | [09-multimodal-tool/tool-structure-comparison_part2.md](09-multimodal-tool/tool-structure-comparison_part2.md) |
| 离线/在线 API 与协议族 | [10-serving/serving-comparison_part1.md](10-serving/serving-comparison_part1.md) |
| 请求模型映射与工具参数 | [10-serving/serving-comparison_part2.md](10-serving/serving-comparison_part2.md) |
| 部署形态与监控可观测 | [10-serving/serving-observability.md](10-serving/serving-observability.md) |
| 设计哲学/优劣势矩阵/适用场景 | [11-selection/selection-guide.md](11-selection/selection-guide.md) |
| 迁移速查与社区状态 | [11-selection/selection-guide_part2.md](11-selection/selection-guide_part2.md) |
