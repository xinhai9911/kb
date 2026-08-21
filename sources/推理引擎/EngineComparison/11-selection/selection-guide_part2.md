## 11-selection 选型指南（二）：迁移速查与社区状态

承接 [selection-guide.md](selection-guide.md)（设计哲学/矩阵/场景）。本文给出 vLLM ↔ SGLang 迁移参数速查与社区状态。事实基准同前：vLLM V1、SGLang SRT commit `21c88f86`。

### 四、迁移速查：vLLM ↔ SGLang

#### 4.1 启动参数对照

| 语义 | vLLM | SGLang |
|---|---|---|
| 服务启动 | `vllm serve <model>` | `sglang serve <model>`（或 `python -m sglang.launch_server`） |
| 张量并行 | `--tensor-parallel-size` | `--tp-size`（alias `--tensor-parallel-size`） |
| 流水线并行 | `--pipeline-parallel-size` | `--pp-size` |
| 数据并行 | `--data-parallel-size` | `--dp-size` |
| 解码上下文并行 | `--decode-context-parallel-size` | `--dcp-size` |
| 预填充上下文并行 | `--prefill-context-parallel-size` | `--attn-cp-size` |
| 显存比例 | `--gpu-memory-utilization`（默认 0.92） | `--mem-fraction-static`（默认启发式自动计算） |
| 模型上下文长 | `--max-model-len`（支持 `1k`/`25.6k`/`-1` 自动 fit） | `--context-length` |
| 批大小上限 | `--max-num-seqs`（默认 128） | `--max-total-tokens` |
| KV 页大小 | `--block-size`（默认 16） | `--page-size`（默认 1，paged 分配时 >1） |
| 前缀缓存 | `--enable-prefix-caching`（默认开） | `--disable-radix-cache`（默认开，RadixAttention） |
| chunked prefill | `--enable-chunked-prefill` + `--max-num-batched-tokens`（2048） | `--chunked-prefill-size`（显存分级 2048~16384，`-1` 禁用） |
| 调度策略 | `--policy` fcfs/priority | `--schedule-policy` fcfs/lpm/dfs-weight/lof/random/routing-key（+priority） |
| 投机解码 | `--speculative-config`（method 字符串） | `--speculative-algorithm` + `--speculative-num-draft-tokens` |
| 量化 | `--quantization`（含在线 6 简写） | `--quantization`（+`nvfp4_online`；方法名映射见 08 模块） |
| grammar 后端 | `--structured-outputs-config`（xgrammar/guidance/outlines/lm-format-enforcer） | `--grammar-backend`（xgrammar/outlines/llguidance） |
| 确定性推理 | `--seed` | `--random-seed` + `--enable-deterministic-inference` |
| PD 分离 | `--kv-transfer-config` | `--disaggregation-mode` + `--disaggregation-transfer-backend` |
| 工具解析 | `--enable-auto-tool-choice` + `--tool-call-parser`（**必须显式**） | `--tool-call-parser auto`（自动探测） |
| LoRA | `--enable-lora` + `--lora-modules` | `--enable-lora` + `--lora-paths` |
| 鉴权 | 无内建 API key | `--api-key` / `--admin-api-key` |

#### 4.2 采样参数差异（跨引擎迁移易踩坑）

| 语义 | vLLM | SGLang | 注意 |
|---|---|---|---|
| 生成上限 | `max_tokens`（默认 16） | `max_new_tokens`（默认 128） | 默认值相差大 |
| `top_k` 禁用语义 | `0`/`-1` 表示禁用（默认 0） | `2**30` 表示全开（默认 `TOP_K_ALL`） | **数值含义相反，必须显式转换** |
| 停止条件 | `stop` / `stop_token_ids` | `stop` / `stop_token_ids` / **`stop_regex`** | 正则停止仅 SGLang |
| 结构化输出 | `structured_outputs` 六选一（含 json_object/choice） | json_schema/regex/ebnf/structural_tag 四选一互斥 | vLLM 多 json_object/choice |
| 词表约束 | `allowed_token_ids` / `bad_words` | 无（仅 `logit_bias`） | vLLM 独有 |
| 返回数 | `n` 支持 >1（上限 16384） | 固定 `n=1` | — |
| 确定性 | `seed` 每请求 Generator、后端无关 | `sampling_seed` 需开启确定性且 flashinfer 不支持 | 换后端注意 |

#### 4.3 离线 API 差异

| 项 | vLLM | SGLang |
|---|---|---|
| 离线入口 | `LLM(model, **kwargs)` → 内部 LLMEngine(V1) | `Engine(model_path=..., **kwargs)`（或直传 `server_args=`） |
| 生成返回 | `generate()` → `list[RequestOutput]`（强类型） | `generate()` → dict（`text`/`meta_info`/`output_ids`） |
| 流式 | 同步引擎不流式，走 `AsyncLLM` / `vllm serve` | 同步 `generate(stream=True)` |
| 嵌入/打分 | `encode(..., pooling_task=)` 必须显式任务 | `encode`/`score` 内置（`EngineScoreMixin`） |
| 权重热更新 | `start_weight_update` / `update_weights` / `finish_weight_update` | `update_weights_from_tensor/distributed/disk/ipc` |
| 会话 | 无内置 session | `open_session` / `close_session`（session_id） |

#### 4.4 服务端点差异（核心协议对齐）

| 端点族 | vLLM | SGLang |
|---|---|---|
| 对齐 | `/v1/chat/completions`、`/v1/completions`、`/v1/embeddings`、`/v1/models`、`/health`、`/metrics` | 同左 |
| 原生 | `/pooling`、`/score`、`/rerank`、`/tokenize`、`/detokenize` | `/generate`、`/encode`、`/classify`（v0 风格） |
| 扩展 | Anthropic、Cohere、SageMaker、gRPC、`/v1/responses` | Anthropic、**Ollama**、**Vertex**、WS `/v1/realtime`、`/v1/audio/transcriptions` |
| 负载视图 | `/load`（GPU 占用请求数） | `/v1/loads`（core/memory/spec/lora/disagg 分节） |
| 管理端点 | dev 模式（`VLLM_SERVER_DEV_MODE`）才开 `/sleep` `/wake_up` `/collective_rpc` | 常开 `/flush_cache` `/update_weights_from_*` `/open_session` `/hicache/*` |
| 指标前缀 | `vllm:*`（KV cache/前缀缓存/队列） | `sglang:*`（TTFT/e2e/spec 接受率），需 `--enable-metrics` |
| Tracing | `traceparent`/`tracestate` header 透传引擎 | OTLP 独立子系统（`--enable-trace`，可运行时调级别/模块） |

#### 4.5 迁移注意点

- 模型权重与 HF config 通用；量化方法名按 08 模块映射（`mxfp8`↔`fp8`、`experts_int8`↔`w8a8_int8`、`awq`/`gptq` 一致）。
- 前缀缓存默认均开启，vLLM 迁入 SGLang 无需额外参数；但命中粒度从"块"变为"token 段"，命中率行为不同。
- SGLang 换 flashinfer 注意力/采样后端时确定性 seed 不可用；vLLM 无此限制。
- SGLang 工具 parser 可 `auto` 探测；vLLM 必须显式 `--tool-call-parser`，且 `--enable-auto-tool-choice` 强制配套。
- SGLang 结构化输出参数直接进 sampling dict（`json_schema`/`structural_tag` 键），原生 `/generate` 直通；vLLM 走 `response_format`/`structured_outputs` 归一。

### 五、社区/迭代状态（KB 快照视角）

| 维度 | vLLM | SGLang |
|---|---|---|
| 分析源码版本 | `v0.27.2rc0-203-g41f179b57a` | commit `21c88f8625f2e699543a1c34f41d6894ef342903` |
| 知识库规模 | 32 模块 / 99 md（vLLMSourceAnalysis） | 20 模块 / 62 md（SGLangSourceAnalysis） |
| 架构代际 | V1 为现行（v0 仅兼容层别名），EngineCore 独立进程 + ZMQ/msgpack | 无 v0/v1 分裂，SRT 进程模型自诞生定型 |
| 活跃方向 | 统一 token 调度、batch_queue 多批重叠、编译体系（CUDA graph/torch.compile）、DP 协调、Rust 前端实验、弹性 EP、插件生态 | overlap 双 stream、EAGLE 生态（多层/树/自适应）、HiRadixCache 分层、多模态生成（SGLang Diffusion）、弹性 EP、NPU/MLX 多平台、LPLB |
| 社区/生产 | vllm-project，OpenAI 协议生态主导，K8s/gRPC/Ray 生产面成熟 | lmsys 主导，与 DeepSeek 系深度绑定，新特性（多模态生成/llguidance）落地快 |
| 迭代节奏 | 版本化发布 + rc 快照，稳定推进 | commit 快照，功能面扩展快 |

> 版本号与快照日期取自两份 skill.md 元信息（KB 约 2026-08-20，对比库 2026-08-21 产出），不构成对线上最新版本的断言。

### 六、一页决策表

| 关键问题 | 结论 |
|---|---|
| 前缀复用 / 多轮对话 / 共享前缀占主导？ | → SGLang |
| 需要图像/音频/视频生成？ | → SGLang（唯一） |
| 跑 DeepSeek 系 MoE + EPLB / DP-attention？ | → SGLang |
| 上 NPU / MLX / 多平台异构？ | → SGLang |
| 生产稳定 / OpenAI 生态 / 团队熟悉度优先？ | → vLLM |
| 需要 guidance / lm-format-enforcer / 工具 parser 生态？ | → vLLM |
| 需要后端无关的确定性采样复现？ | → vLLM |
| 常规 CUDA 单机 LLM、两者都可用？ | 核心协议已对齐，建议协议层抽象 + 按场景热切换验证 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
