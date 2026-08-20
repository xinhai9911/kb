# FAQ：vLLM 源码分析常见问题

## 错误码 / 错误信息

本知识库为源码分析，不定义业务错误码。源码中明确出现的异常/错误信息按模块记录：

| 位置 | 错误信息 | 触发条件 |
|---|---|---|
| `vllm/tool_parsers/abstract_tool_parser.py` | `KeyError("Tool parser '{name}' not found.")` | `get_tool_parser(name)` 两表（就绪/惰性）均未命中 |
| `vllm/tool_parsers/abstract_tool_parser.py` | `TypeError` | 惰性加载的类不是 `ToolParser` 子类 |
| `vllm/tool_parsers/structural_tag_registry.py` | `ValueError: Unknown format type` | structural tag 模型 key 不在 xgrammar 与 vLLM 内置集合内 |
| `vllm/platforms/interface.py` | `ValueError`（`check_if_supports_dtype`） | bf16 而计算能力 < 8.0，建议 `--dtype=half` |
| `vllm/platforms/interface.py` | `RuntimeError`（`device_id_to_physical_device_id`） | 越界访问 `_assigned_physical_gpu_ids` |
| `vllm/platforms/interface.py` | `RuntimeError` | 树外/内置平台插件同时激活 ≥2 个（`resolve_current_platform_cls_qualname`） |
| `vllm/platforms/rocm.py` | `ValueError` | `HIP_VISIBLE_DEVICES` 与 `CUDA_VISIBLE_DEVICES` 冲突 |
| `vllm/inputs/registry.py`（若存在） | `ValueError` | 输入类型无法解析/未注册 |

## 通用 HTTP 状态定位

本分析对象为本地推理引擎，**无 HTTP 业务错误码**。HTTP 语义仅存在于 `09-entrypoints/openai-server.md` 描述的 OpenAI 兼容服务层：错误以标准 HTTP 状态 + OpenAI 风格 `error` 结构返回（如 400 参数错误、404 模型不存在、500 内部错误）。以下为定位步骤而非错误码定义：

1. 先确认请求是否到达引擎：服务层校验失败多为 4xx（参数/鉴权）。
2. 引擎内核异常（调度、KV、采样、执行）统一经 `EngineCore` 回传 `EngineCoreOutput` 的 `events`/`finish_reason`，前端转 500 或流式 `finish_reason=error`。
3. 排查时以 `finish_reason` 与 `RequestStatus`（02-engine-core）为准，再回溯对应模块。

## 常见问题

### 引擎为什么分成 v1 与 v0？
`vllm/v1/engine/core.py` 的 EngineCore 是现行执行内核；`vllm/engine/` 下仅保留 v0 兼容层。差异对照见 `02-engine-core/engine-overview.md`。

### 请求如何从入口到达 GPU？
入口（`09-entrypoints`）→ `InputProcessor` 生成 `EngineCoreRequest`（`02-engine-core/processors.md`）→ `EngineCore.step` 调度/执行（`02-engine-core/engine-overview.md`、`03-scheduler-kvcache`）→ `v1/worker` 的 ModelRunner 执行 forward（`15-v1-worker/model-runner.md`）→ 采样 → 输出回前端。

### 量化方法如何选择？
由 `QuantizationMethods` 注册表 + `get_quant_class` 三段式选择（配置名/短名/在线解析），方法总表见 `12-quantization/quant-methods.md`。

### LoRA 如何注入模型？
`LoRAResolver` 解析请求 → `lora_model_runner_mixin` 把权重按层打包 → 层内 `apply_lora` 用 Punica kernel 计算。见 `13-lora-adapters/`。

### 为什么工具调用解析不出来？
常见原因：`skip_special_tokens` 未关闭导致 `<tool_call>` 标记被跳过。各解析器 `adjust_request` 处理见 `18-tool-parsers/tool-parsers-overview_part3.md`。

### 模型如何被引擎选中？
`ModelConfig` 经 `ModelRegistry` 子进程探测 `_ModelInfo`，`resolve_model_cls` 按 architecture → 模型类四步选中链决定加载哪个实现。见 `19-model-definitions/model-registry.md`。

### v0 引擎还能用吗？
当前 `vllm/engine/llm_engine.py`/`async_llm_engine.py` 只是 v1 的**纯别名 shim**（无 deprecated 标记），对象即 v1 的 `LLMEngine`/`AsyncLLM`；`EngineArgs` 两代共用。见 `24-v0-engine-legacy/`。

### CustomAllReduce 何时生效？
`use_custom_allreduce` 由平台决定（CUDA 默认 True、ROCm 仅 MI300、CPU/XPU False）。内核为两阶段层次化 allreduce，见 `25-distributed-internals/custom-allreduce.md`。

### OpenAI 请求如何转成引擎参数？
Chat/Completion/Embedding/Responses 四类请求分别经 `to_sampling_params`/`to_pooling_params` 映射，serving 层错误经 `exceptions.py` 转 HTTP 状态码。见 `26-entrypoints-protocols/`。

### 插件机制能扩展什么？
`load_plugins_by_group` 按 entry-point 组加载树外插件，扩展点包括平台（14）、端点（Endpoint）、IO 处理器、LoRA resolver 等；Endpoint 插件需显式 opt-in。见 `28-plugins-observability/plugin-mechanism.md`。

### 渲染器与多模态输入的关系？
`RendererBase` 把用户输入内容渲染为模型输入（音频/视频/embedding/原生模板），与 07/11 的输入管线衔接；`assets/` 提供默认媒体资源。见 `27-renderers/`。

### vLLM IR 是什么？
`vllm/ir/` 是编译层中间表示 + 算子多实现分发底座（provider：native/vllm_c/oink/aiter），经 `VllmIRLoweringPass` 落地，是 17-compilation pass 流程的载体。见 `31-kernel-infrastructure/vllm-ir_part1.md`。

### CUDA graph 何时生效？
`OptimizationLevel` O2/O3 启用 full/piecewise CUDA graph；`CUDAGraphMode` 捕获与 replay 见 `17-compilation/cuda-graph.md`，级别映射见 `17-compilation/compilation-overview_part1.md`。

## 顺序排错流程

1. 确认入口/服务层参数（`09-entrypoints`）。
2. 确认请求状态机与终结原因（`02-engine-core`）。
3. 确认调度与 KV 分配是否正常（`03-scheduler-kvcache`）。
4. 确认注意力后端与平台选择（`04-attention`、`14-platforms`）。
5. 确认模型执行与采样（`15-v1-worker`、`05-sampling`）。
6. 涉及量化/LoRA/工具/结构化输出时，分别进入 `12/13/16/18` 模块核对契约与注册。
7. 性能/图捕获问题查 `17-compilation`。

> 返回：[skill.md](skill.md)
