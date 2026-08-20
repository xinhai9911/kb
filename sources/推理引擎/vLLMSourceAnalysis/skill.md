# vLLM 源码分析 Skill

基于 vLLM 源码（`v0.27.2rc0-203-g41f179b57a`）的模块化深度分析索引，覆盖引擎核心、调度、注意力、采样、模型执行、分布式、入口、量化、LoRA、平台、编译、工具调用与推理等主题。

## 全局配置

```yaml
# 被分析源码
source_repo: Q:\AI\vllm\vllm
source_version: v0.27.2rc0-203-g41f179b57a
source_package: vllm/（2246 个 .py）
analysis_language: zh-CN
# 文档约定
heading_base_level: "##"
file_size_limit: 8KB
placeholder_base_url: "{BASE_URL}"
placeholder_token: "{TOKEN}"
placeholder_timeout: "{TIMEOUT}"
# 覆盖范围
module_count: 32
markdown_file_count: 99
```

## AI 使用流程

1. 先读本文件定位主题，按「功能/接口 → 文件路径」进入对应模块分析。
2. 模块内优先看 `-overview` / 总览文件建立架构图景，再读细分主题文件。
3. 涉及请求/响应类内容时，请求工具统一记作 `HTTP_CLIENT`，可配置值引用全局占位符 `{BASE_URL}`、`{TOKEN}`、`{TIMEOUT}`、`{PAGE_SIZE}`、`{MAX_PAGE_SIZE}`。
4. 排查问题先查 `faq.md` 的错误码/定位步骤，再回到对应模块源码路径核对。
5. 使用后如需沉淀，将关键结论反向标注回源码路径，保持知识库与源码可追溯。

## 全局约定

- 知识库维护变更记录见 `CHANGELOG.md`；转换过程与统计见 `_pipeline_report.md`。
- 源码路径统一写为相对 `vllm/` 包的形式（如 `vllm/v1/engine/core.py`）。
- 引擎分代：`v1` 为现行架构（EngineCore 独立进程 + ZMQ/msgpack），`v0`（`vllm/engine/`）仅保留兼容层。
- 请求状态机：`RequestStatus` 定义于 `vllm/v1/request.py`；`FinishReason` 与对外 `RequestOutput.finish_reason` 字符串映射见 02-engine-core。
- 全局配置只在此处声明；模块文件出现可配置值一律引用占位符，不写死。
- 文档为源码事实的记录，不补写源码未明确给出的参数、枚举或行为；多来源冲突时优先具体/更新/更贴近主题的表述，无法裁决时并列标注来源差异。
- 每个模块文件 < 8KB；超限按 `_part1`/`_part2` 拆分。

## 子文档索引

| 功能/接口 | 文件路径 |
|---|---|
| 整体架构与引擎分层 | [00-overview/architecture.md](00-overview/architecture.md) |
| 配置体系 VllmConfig / CLI 装配 / 哈希 | [01-config/config-system.md](01-config/config-system.md) |
| ModelConfig 与模型配置 | [01-config/model-config.md](01-config/model-config.md) |
| 子配置（cache/parallel/scheduler/device/load 等） | [01-config/sub-configs_part1.md](01-config/sub-configs_part1.md) |
| ParallelConfig 并行配置 | [01-config/sub-configs_part2.md](01-config/sub-configs_part2.md) |
| 三大引擎关系与进程间契约 | [02-engine-core/engine-overview.md](02-engine-core/engine-overview.md) |
| 输入/输出处理（InputProcessor/OutputProcessor） | [02-engine-core/processors.md](02-engine-core/processors.md) |
| DP 协调与负载 | [02-engine-core/coordination.md](02-engine-core/coordination.md) |
| 调度器（Scheduler/调度流程） | [03-scheduler-kvcache/scheduler.md](03-scheduler-kvcache/scheduler.md) |
| KV cache 与块管理 | [03-scheduler-kvcache/kv-cache.md](03-scheduler-kvcache/kv-cache.md) |
| 注意力后端架构 | [04-attention/attention-architecture.md](04-attention/attention-architecture.md) |
| 注意力元数据与层接线 | [04-attention/attention-architecture_part2.md](04-attention/attention-architecture_part2.md) |
| 采样流程与实现 | [05-sampling/sampling-flow.md](05-sampling/sampling-flow.md) |
| SamplingParams | [05-sampling/sampling-params.md](05-sampling/sampling-params.md) |
| 投机解码（speculative decoding） | [05-sampling/spec-decoding.md](05-sampling/spec-decoding.md) |
| 模型执行层（layers-core） | [06-model-executor/layers-core.md](06-model-executor/layers-core.md) |
| 权重加载 Loader | [06-model-executor/loader.md](06-model-executor/loader.md) |
| 自定义算子入口 | [06-model-executor/custom-ops.md](06-model-executor/custom-ops.md) |
| 输入管线（registry/parse/prepare/渲染） | [07-inputs-sequence/inputs-pipeline_part1.md](07-inputs-sequence/inputs-pipeline_part1.md) |
| 输入管线（enc-dec 装配等） | [07-inputs-sequence/inputs-pipeline_part2.md](07-inputs-sequence/inputs-pipeline_part2.md) |
| 核心数据模型（Request/Sequence/BlockTable） | [07-inputs-sequence/sequence-model_part1.md](07-inputs-sequence/sequence-model_part1.md) |
| 核心数据模型（续） | [07-inputs-sequence/sequence-model_part2.md](07-inputs-sequence/sequence-model_part2.md) |
| 输出结构与 logits/池化处理 | [07-inputs-sequence/outputs-logits.md](07-inputs-sequence/outputs-logits.md) |
| 并行状态（TP/PP/CP/DP/EP） | [08-distributed/parallel-state.md](08-distributed/parallel-state.md) |
| 通信器（allreduce/communicators） | [08-distributed/communicators.md](08-distributed/communicators.md) |
| Worker/Executor 分布执行 | [08-distributed/worker-executor.md](08-distributed/worker-executor.md) |
| 离线 API（LLM 类） | [09-entrypoints/offline-api.md](09-entrypoints/offline-api.md) |
| OpenAI 兼容服务 | [09-entrypoints/openai-server.md](09-entrypoints/openai-server.md) |
| CLI 工具（serve/benchmark 等） | [09-entrypoints/cli-tools.md](09-entrypoints/cli-tools.md) |
| 内核（kernels/csrc 自定义算子） | [10-kernels/custom-ops.md](10-kernels/custom-ops.md) |
| 多模态注册表 | [11-multimodal-inputs/multimodal-registry.md](11-multimodal-inputs/multimodal-registry.md) |
| 多模态输入数据 | [11-multimodal-inputs/input-data.md](11-multimodal-inputs/input-data.md) |
| 工具调用与推理（多模态侧） | [11-multimodal-inputs/tool-reasoning.md](11-multimodal-inputs/tool-reasoning.md) |
| 量化体系总览（注册/选择） | [12-quantization/quantization-overview.md](12-quantization/quantization-overview.md) |
| 量化接口契约与衔接 | [12-quantization/quantization-overview_part2.md](12-quantization/quantization-overview_part2.md) |
| 量化方法总表与内核 | [12-quantization/quant-methods.md](12-quantization/quant-methods.md) |
| 量化在线简写与场景速查 | [12-quantization/quant-methods_part2.md](12-quantization/quant-methods_part2.md) |
| LoRA 请求与分发 | [13-lora-adapters/lora-overview.md](13-lora-adapters/lora-overview.md) |
| LoRA 权重/注入/缓存 | [13-lora-adapters/lora-modules.md](13-lora-adapters/lora-modules.md) |
| Platform 接口契约与平台解析 | [14-platforms/platforms-overview_part1.md](14-platforms/platforms-overview_part1.md) |
| 后端差异对比 | [14-platforms/platforms-overview_part2.md](14-platforms/platforms-overview_part2.md) |
| device_allocator 与 DeviceConfig 联动 | [14-platforms/platforms-overview_part3.md](14-platforms/platforms-overview_part3.md) |
| 静态属性契约与能力钩子（上） | [14-platforms/platforms-overview_part4.md](14-platforms/platforms-overview_part4.md) |
| 能力钩子（下）与兜底代理 | [14-platforms/platforms-overview_part5.md](14-platforms/platforms-overview_part5.md) |
| v1 Worker 执行侧 | [15-v1-worker/worker-overview.md](15-v1-worker/worker-overview.md) |
| GPUModelRunner 执行流程 | [15-v1-worker/model-runner.md](15-v1-worker/model-runner.md) |
| v1 投机解码（proposer/验收） | [15-v1-worker/spec-decode-v1.md](15-v1-worker/spec-decode-v1.md) |
| Reasoning Parser（思考/答案分离） | [16-structured-reasoning/reasoning.md](16-structured-reasoning/reasoning.md) |
| 结构化输出后端与采样衔接 | [16-structured-reasoning/structured-outputs.md](16-structured-reasoning/structured-outputs.md) |
| 编译级别与 pass 流水线 | [17-compilation/compilation-overview_part1.md](17-compilation/compilation-overview_part1.md) |
| PostGradPassManager 与融合 | [17-compilation/compilation-overview_part2.md](17-compilation/compilation-overview_part2.md) |
| CUDA graph 捕获与 replay | [17-compilation/cuda-graph.md](17-compilation/cuda-graph.md) |
| ToolParser 契约与注册 | [18-tool-parsers/tool-parsers-overview_part1.md](18-tool-parsers/tool-parsers-overview_part1.md) |
| ToolParser 按模型选择与流式实现 | [18-tool-parsers/tool-parsers-overview_part2.md](18-tool-parsers/tool-parsers-overview_part2.md) |
| ToolParser 请求改写与注册表 | [18-tool-parsers/tool-parsers-overview_part3.md](18-tool-parsers/tool-parsers-overview_part3.md) |
| 模型注册表与选中链 | [19-model-definitions/model-registry.md](19-model-definitions/model-registry.md) |
| 模型公共组件与能力接口 | [19-model-definitions/model-common-components.md](19-model-definitions/model-common-components.md) |
| 代表架构（LLaMA/Qwen/DeepSeek/MoE 等） | [19-model-definitions/representative-architectures.md](19-model-definitions/representative-architectures.md) |
| Executor 层次与分布执行（v0 侧为历史） | [20-model-executor-runner/executor-architecture.md](20-model-executor-runner/executor-architecture.md) |
| v0 ModelRunner 执行流程（历史，基于 a4528f0cac） | [20-model-executor-runner/v0-model-runner.md](20-model-executor-runner/v0-model-runner.md) |
| v0 采样循环（LLMEngine.step，历史） | [20-model-executor-runner/llm-generator.md](20-model-executor-runner/llm-generator.md) |
| 并行线性层与 Norm | [21-model-layers/linear-norm-layers.md](21-model-layers/linear-norm-layers.md) |
| Sampler/Pooling/词表嵌入 | [21-model-layers/sampler-pooling.md](21-model-layers/sampler-pooling.md) |
| RoPE/激活/融合层/FusedMoE | [21-model-layers/rotary-activation-fused.md](21-model-layers/rotary-activation-fused.md) |
| v1 logits 处理与采样链路 | [22-v1-core-internals/logits-sampling.md](22-v1-core-internals/logits-sampling.md) |
| v1 pooling/embed/tti | [22-v1-core-internals/pooling-embed-tti.md](22-v1-core-internals/pooling-embed-tti.md) |
| v1 抢占/块池/encoder 缓存 | [22-v1-core-internals/preemption-block-pool.md](22-v1-core-internals/preemption-block-pool.md) |
| HF config 映射与架构解析 | [23-transformers-utils/config-mapping.md](23-transformers-utils/config-mapping.md) |
| HF config 映射（续） | [23-transformers-utils/config-mapping_part2.md](23-transformers-utils/config-mapping_part2.md) |
| 分词器与反分词器 | [23-transformers-utils/tokenizer-detokenizer.md](23-transformers-utils/tokenizer-detokenizer.md) |
| HF 权重加载链路 | [23-transformers-utils/weight-loading.md](23-transformers-utils/weight-loading.md) |
| v0 引擎兼容层（EngineArgs/别名 shim） | [24-v0-engine-legacy/v0-engine-legacy.md](24-v0-engine-legacy/v0-engine-legacy.md) |
| EngineArgs 装配细节 | [24-v0-engine-legacy/v0-engine-legacy_part2.md](24-v0-engine-legacy/v0-engine-legacy_part2.md) |
| 通信算子与 PG 封装 | [25-distributed-internals/comm-ops.md](25-distributed-internals/comm-ops.md) |
| CustomAllReduce 内核 | [25-distributed-internals/custom-allreduce.md](25-distributed-internals/custom-allreduce.md) |
| 设备通信器（NVLS/PyNccl/SHM） | [25-distributed-internals/device-communicators_part1.md](25-distributed-internals/device-communicators_part1.md) |
| 设备通信器（续） | [25-distributed-internals/device-communicators_part2.md](25-distributed-internals/device-communicators_part2.md) |
| OpenAI 协议模型 | [26-entrypoints-protocols/openai-protocols.md](26-entrypoints-protocols/openai-protocols.md) |
| 请求→引擎参数映射 | [26-entrypoints-protocols/request-to-params.md](26-entrypoints-protocols/request-to-params.md) |
| Serving 分派与错误处理 | [26-entrypoints-protocols/serving-dispatch.md](26-entrypoints-protocols/serving-dispatch.md) |
| 渲染器契约与代表实现 | [27-renderers/renderers-overview.md](27-renderers/renderers-overview.md) |
| 在线渲染与媒体资源 | [27-renderers/renderers-online-and-assets.md](27-renderers/renderers-online-and-assets.md) |
| 插件机制（加载/扩展点） | [28-plugins-observability/plugin-mechanism.md](28-plugins-observability/plugin-mechanism.md) |
| 可观测性（OTel 追踪/日志） | [28-plugins-observability/observability.md](28-plugins-observability/observability.md) |
| 用量统计上报 | [28-plugins-observability/usage-reporting.md](28-plugins-observability/usage-reporting.md) |
| 逐层剖析（layerwise profiler） | [29-profiler-utils/layerwise-profiler.md](29-profiler-utils/layerwise-profiler.md) |
| 高频工具（registry/torch/import） | [29-profiler-utils/utils-essentials.md](29-profiler-utils/utils-essentials.md) |
| 基础设施工具（async/gc/mem/cache） | [29-profiler-utils/utils-infra.md](29-profiler-utils/utils-infra.md) |
| 模型家族分类表 | [30-model-families/model-family-taxonomy.md](30-model-families/model-family-taxonomy.md) |
| 模型共性复用模式 | [30-model-families/family-reuse-patterns.md](30-model-families/family-reuse-patterns.md) |
| 模型索引表（一）：Dense/MoE/MLA | [30-model-families/model-index_part1.md](30-model-families/model-index_part1.md) |
| 模型索引表（二）：SSM/Hybrid/Vision/Audio | [30-model-families/model-index_part2.md](30-model-families/model-index_part2.md) |
| 模型索引表（三）：OCR/Embedding/投机/MTMD | [30-model-families/model-index_part3.md](30-model-families/model-index_part3.md) |
| vLLM IR（编译层中间表示） | [31-kernel-infrastructure/vllm-ir_part1.md](31-kernel-infrastructure/vllm-ir_part1.md) |
| vLLM IR（续） | [31-kernel-infrastructure/vllm-ir_part2.md](31-kernel-infrastructure/vllm-ir_part2.md) |
| 内核基础设施（Triton/FlashAttn/CUTE） | [31-kernel-infrastructure/kernel-infra-utils_part1.md](31-kernel-infrastructure/kernel-infra-utils_part1.md) |
| 内核基础设施（续） | [31-kernel-infrastructure/kernel-infra-utils_part2.md](31-kernel-infrastructure/kernel-infra-utils_part2.md) |
| Ray 集成基础设施 | [32-ray-third-party/ray-integration.md](32-ray-third-party/ray-integration.md) |
| vendored 三方库（FLA/flashmla/pynvml） | [32-ray-third-party/third-party-vendored.md](32-ray-third-party/third-party-vendored.md) |

> 返回：本页即 Skill 入口 | [faq.md](faq.md)
