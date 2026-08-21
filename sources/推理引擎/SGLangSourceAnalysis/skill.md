# SGLang 源码分析 Skill

基于 SGLang 源码（commit `21c88f8625f2e699543a1c34f41d6894ef342903`）的模块化深度分析索引，聚焦多进程 manager 架构、RadixAttention 前缀缓存、调度与模型执行链路。

## 全局配置

```yaml
# 被分析源码
source_repo: Q:\AI\sglang-main
source_commit: 21c88f8625f2e699543a1c34f41d6894ef342903
source_package: python/sglang/（3365 个 .py，核心在 srt/）
analysis_language: zh-CN
# 文档约定
heading_base_level: "##"
file_size_limit: 8KB
# 覆盖范围（Round 1-2）
module_count: 20
markdown_file_count: 62
```

## AI 使用流程

1. 先读本文件定位主题，按「功能/接口 → 文件路径」进入对应模块分析。
2. 模块内优先看 `-overview` / 总览文件建立架构图景，再读细分主题文件。
3. 涉及请求/响应类内容时，请求工具统一记作 `HTTP_CLIENT`，可配置值引用全局占位符 `{BASE_URL}`、`{TOKEN}`、`{TIMEOUT}`、`{PAGE_SIZE}`、`{MAX_PAGE_SIZE}`。
4. 排查问题先查 `faq.md` 的错误码/定位步骤，再回到对应模块源码路径核对。

## 全局约定

- 源码路径统一写为相对 `python/sglang/` 包的形式（如 `srt/managers/scheduler.py`）。
- 进程模型：`TokenizerManager`（主进程，宿主 HTTP 服务）→ `Scheduler`（子进程，调度）+ `TpModelWorker`（与 Scheduler 同进程，模型执行）→ `DetokenizerManager`（子进程，反分词）。进程间经 ZMQ 通信（`managers/communicator.py`）。
- 核心创新：`RadixAttention` 前缀树缓存（`srt/mem_cache/`），块级复用 + eviction，与调度深度融合。
- 配置唯一来源：`srt/server_args.py`（约 10073 行）`ServerArgs`；环境变量 `SGLANG_*`（`srt/environ.py`）。
- 请求端到端路径：HTTP → TokenizerManager → Scheduler → TpModelWorker → DetokenizerManager → 响应。
- 全局配置只在此处声明；模块文件出现可配置值一律引用占位符，不写死。
- 文档为源码事实的记录，不补写源码未明确给出的参数、枚举或行为；多来源冲突时优先具体/更新/更贴近主题的表述。
- 每个模块文件 < 8KB；超限按 `_part1`/`_part2` 拆分。

## 子文档索引（Round 1）

| 功能/接口 | 文件路径 |
|---|---|
| 整体架构：进程模型/四大 manager/RadixAttention 理念 | [00-overview/architecture_part1.md](00-overview/architecture_part1.md) |
| 请求路径与 vLLM 对照 | [00-overview/architecture_part2.md](00-overview/architecture_part2.md) |
| ServerArgs 配置体系（构造/解析管线） | [01-config/config-system.md](01-config/config-system.md) |
| 参数分组与关键默认值 | [01-config/server-args-groups.md](01-config/server-args-groups.md) |
| 环境变量与 configs | [01-config/env-constants-configs.md](01-config/env-constants-configs.md) |
| TokenizerManager 请求流 | [02-managers/tokenizer-manager.md](02-managers/tokenizer-manager.md) |
| Req/ScheduleBatch 数据结构 | [02-managers/schedule-batch-io.md](02-managers/schedule-batch-io.md) |
| 进程间通信（communicator） | [02-managers/communicator.md](02-managers/communicator.md) |
| Scheduler 主类与调度循环 | [03-scheduler/scheduler-overview.md](03-scheduler/scheduler-overview.md) |
| get_new_batch_prefill 决策 | [03-scheduler/scheduler-overview_part2.md](03-scheduler/scheduler-overview_part2.md) |
| 调度策略（fcfs/lpm 等） | [03-scheduler/schedule-policies.md](03-scheduler/schedule-policies.md) |
| PP 调度 | [03-scheduler/scheduler-pp-mixin.md](03-scheduler/scheduler-pp-mixin.md) |
| RadixCache 数据结构与命中/插入 | [04-radix-cache/radix-cache-overview.md](04-radix-cache/radix-cache-overview.md) |
| 淘汰策略与 chunking | [04-radix-cache/eviction-chunking.md](04-radix-cache/eviction-chunking.md) |
| HiRadixCache 分层缓存 | [04-radix-cache/hiradix-cache.md](04-radix-cache/hiradix-cache.md) |
| 内存池（token/KV/请求池） | [05-mem-cache/memory-pool.md](05-mem-cache/memory-pool.md) |
| 显存分配估算 | [05-mem-cache/allocation-sizing.md](05-mem-cache/allocation-sizing.md) |
| 特殊池（SWA/embedding/DSV4） | [05-mem-cache/special-pools.md](05-mem-cache/special-pools.md) |
| ModelRunner 与执行流程 | [06-model-executor/model-runner.md](06-model-executor/model-runner.md) |
| ForwardBatch 数据结构 | [06-model-executor/forward-batch-info.md](06-model-executor/forward-batch-info.md) |
| 权重加载链路 | [06-model-executor/weight-loading.md](06-model-executor/weight-loading.md) |
| RadixAttention 层实现 | [07-attention/radix-attention.md](07-attention/radix-attention.md) |
| Attention 后端抽象与注册 | [07-attention/attention-backends.md](07-attention/attention-backends.md) |
| KV 布局与后端差异 | [07-attention/kv-layout-and-backends.md](07-attention/kv-layout-and-backends.md) |
| SamplingParams 参数模型 | [08-sampling/sampling.md](08-sampling/sampling.md) |
| SamplingBatchInfo 批量张量化与参数流转 | [08-sampling/sampling_part2.md](08-sampling/sampling_part2.md) |
| 采样后端（logits/penalty/sampler） | [08-sampling/sampling-backend_part1.md](08-sampling/sampling-backend_part1.md) |
| 采样与 vLLM 对照 | [08-sampling/sampling-backend_part2.md](08-sampling/sampling-backend_part2.md) |
| HTTP 服务端点与协议族 | [09-entrypoints/http-server_part1.md](09-entrypoints/http-server_part1.md) |
| HTTP 服务（续） | [09-entrypoints/http-server_part2.md](09-entrypoints/http-server_part2.md) |
| Engine 离线接口 | [09-entrypoints/engine-api.md](09-entrypoints/engine-api.md) |
| gRPC 与工具端点 | [09-entrypoints/grpc-and-tools.md](09-entrypoints/grpc-and-tools.md) |
| 并行线性层与 Norm | [10-layers/linear-norm-layers.md](10-layers/linear-norm-layers.md) |
| MoE/激活/RoPE/嵌入 | [10-layers/moe-activation-rotary.md](10-layers/moe-activation-rotary.md) |
| 模型注册机制 | [11-models/model-registry.md](11-models/model-registry.md) |
| 代表架构实现 | [11-models/representative-models.md](11-models/representative-models.md) |
| 模型索引表（一） | [11-models/model-index_part1.md](11-models/model-index_part1.md) |
| 模型索引表（二） | [11-models/model-index_part2.md](11-models/model-index_part2.md) |
| 多模态输入处理 | [12-multimodal/multimodal-inputs.md](12-multimodal/multimodal-inputs.md) |
| 多模态调度与缓存 | [12-multimodal/multimodal-scheduling.md](12-multimodal/multimodal-scheduling.md) |
| 多模态生成管线 | [12-multimodal/multimodal-gen.md](12-multimodal/multimodal-gen.md) |
| 投机解码架构 | [13-speculative/speculative-overview.md](13-speculative/speculative-overview.md) |
| EAGLE 草稿头实现 | [13-speculative/eagle-drafters.md](13-speculative/eagle-drafters.md) |
| 草稿后端清单 | [13-speculative/draft-backends.md](13-speculative/draft-backends.md) |
| 工具调用（tools schema/解析） | [14-function-constrained/function-calling.md](14-function-constrained/function-calling.md) |
| 约束解码（grammar 后端） | [14-function-constrained/constrained-decoding.md](14-function-constrained/constrained-decoding.md) |
| 工具约束桥接 | [14-function-constrained/tool-constraint-bridge.md](14-function-constrained/tool-constraint-bridge.md) |
| 并行状态（TP/PP/EP/DP） | [15-distributed/parallel-state_part1.md](15-distributed/parallel-state_part1.md) |
| 通信算子与 vLLM 对照 | [15-distributed/parallel-state_part2.md](15-distributed/parallel-state_part2.md) |
| EPLB 专家负载均衡（一） | [15-distributed/eplb_part1.md](15-distributed/eplb_part1.md) |
| EPLB 专家负载均衡（二） | [15-distributed/eplb_part2.md](15-distributed/eplb_part2.md) |
| 硬件后端抽象 | [16-hardware-kernels/hardware-backends.md](16-hardware-kernels/hardware-backends.md) |
| 内核组织与分派 | [16-hardware-kernels/kernels-overview.md](16-hardware-kernels/kernels-overview.md) |
| 内核族与基建 | [16-hardware-kernels/kernels-overview_part2.md](16-hardware-kernels/kernels-overview_part2.md) |
| LoRA 请求/注册/缓存 | [17-lora/lora-overview.md](17-lora/lora-overview.md) |
| LoRA 权重加载与层注入 | [17-lora/lora-cache-injection.md](17-lora/lora-cache-injection.md) |
| PD 分离架构与 KV 传输 | [18-disaggregation/disaggregation.md](18-disaggregation/disaggregation.md) |
| PD 分离（续） | [18-disaggregation/disaggregation_part2.md](18-disaggregation/disaggregation_part2.md) |
| sglang.lang 前端语言 | [19-lang-observability/lang-frontend.md](19-lang-observability/lang-frontend.md) |
| 可观测性（metrics/trace） | [19-lang-observability/observability.md](19-lang-observability/observability.md) |
| 编译与 CUDA graph（一） | [19-lang-observability/compilation_part1.md](19-lang-observability/compilation_part1.md) |
| 编译与 CUDA graph（二） | [19-lang-observability/compilation_part2.md](19-lang-observability/compilation_part2.md) |

> 返回：本页即 Skill 入口 | [faq.md](faq.md)
