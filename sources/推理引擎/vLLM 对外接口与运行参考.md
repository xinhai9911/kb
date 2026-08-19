---
title: vLLM 对外接口与运行参考
tags: [llm, inference-engine, vllm, openai-api, serving, deployment, metrics, gpu-memory, reference]
created: 2026-08-19
updated: 2026-08-19
lifecycle: active
category: sources
base_confidence: 0.85
summary: >-
  vLLM 的对外服务面与运行细节参考：三类客户端（离线 LLM / AsyncLLMEngine / OpenAI Server）、
  OpenAI 兼容端点全景与流式/认证、管理端点（/metrics /health /profile）、部署形态与关键参数、
  以及 GPU 显存预算/ KV Cache 容量计算 / CUDA Graph 等运行期细节（调度内核见 vLLM 深度解析）。
---

# vLLM 对外接口与运行参考

> **一句话**：本笔记是 [[sources/推理引擎/vLLM-Deep-Dive|vLLM 深度解析]] 的对外接口与运行侧补充——架构/调度/PagedAttention 见那篇，这篇专注「怎么连、怎么配、怎么采显存指标」。
> 代码路径对应本地仓库 `Q:/AI/vllm/vllm`（当前为带 Rust 前端的较新版本）。

## 1. 三类对外形态

| 形态 | 入口 | 典型用途 |
|------|------|----------|
| **离线 Python 库** | `LLM`（`vllm/entrypoints/llm.py`） | 批处理、评测、脚本内生成 |
| **异步引擎** | `AsyncLLMEngine` / `AsyncEngineArgs` | 自建服务/嵌入 FastAPI 应用 |
| **OpenAI 兼容服务** | `vllm serve`（`vllm/entrypoints/openai/api_server.py`） | 生产 HTTP 服务 |

三者共享同一套 `VllmConfig → EngineCore(Scheduler+Executor) → Worker` 管线，只是入口封装不同。

### 1.1 离线 API

```python
from vllm import LLM, SamplingParams
llm = LLM(model="meta-llama/Llama-3-8B-Instruct",
          tensor_parallel_size=2, gpu_memory_utilization=0.9)
out = llm.generate(["说明量子计算"], SamplingParams(max_tokens=256, temperature=0.6))
print([o.outputs[0].text for o in out])

# 流式（离线也支持流式）
for o in llm.generate(["写诗"], SamplingParams(max_tokens=64, stream=True)):
    pass  # 逐 token 产出
```

### 1.2 异步引擎（嵌入自建 FastAPI）

```python
from vllm import AsyncLLMEngine, AsyncEngineArgs, SamplingParams
engine = AsyncLLMEngine.from_engine_args(AsyncEngineArgs(model="..."))
async for out in engine.generate(
        {"prompt": "...", "max_tokens": 32}, SamplingParams()):
    # 每步拿到增量输出
```

## 2. OpenAI 兼容端点全景

### 2.1 生成类

| 路径 | 说明 |
|------|------|
| `POST /v1/chat/completions` | 对话（`messages`/`model`/`max_tokens`；支持 `stream`、`logprobs`、tools） |
| `POST /v1/completions` | 文本补全（`prompt`） |
| `POST /v1/responses` | OpenAI **Responses API** 规约（较新版本支持） |
| `POST /generate` / `POST /generate/stream` | 原生生成（早期接口，`--enable-generate-routes`） |
| `POST /tokenize` `POST /detokenize` | 分词往返（`--enable-tokenize-routes`） |

### 2.2 向量 / 打分 / 路由类

| 路径 | 任务 | 服务模块 |
|------|------|----------|
| `POST /v1/embeddings` | Embedding | `pooling`（`register_pooling_api_routers`） |
| `POST /v1/score` | 打分 | `pooling` / scores |
| `POST /v1/rerank`、`/v1/rank` | 重排 | `pooling` / rerank |
| `POST /v1/classify`（随版本） | 分类 logits | `pooling` / classify |
| `POST /v1/audio/transcriptions` | 语音→文本 | `speech_to_text` 路由 |

> 当前仓库把任务路由整合到 `vllm/entrypoints/serve/`（统一 API router）+ `generation`/`pooling`/`speech_to_text` 各子模块，`SupportedTask` 枚举（`generate/embedding/score/rerank/rank/classify/speech-to-text…`，随版本演化）决定开放的端点集合；**具体可用路由以 `vllm serve <model> --help` 与 `/v1/models` 为准**。

### 2.3 模型与适配

- `GET /v1/models`：列出 `--served-model-name` 注册的模型。
- 服务多模型别名：`--served-model-name a b`（一份权重多个名字）；`--model-alias` 映射。
- LoRA：`--lora-modules {name=path}` 启动即挂载，`/v1/loas`（部分版本）热加载；请求体 `"lora": "name"` 选用。
- `--chat-template` / `--hf-overrides`：换对话模板/覆盖模型类。

### 2.4 管理 / 可观测

| 端点 | 用途 |
|------|------|
| `GET /health` | 存活探针（K8s liveness 用） |
| `GET /metrics` | **Prometheus 抓取**（内存使用、批处理、延迟分位数） |
| `POST /start_profile` / `POST /stop_profile` | `--profiler-config` 开启 torch profiler 的起停（见 [[Clippings/vLLM 性能分析 - vLLM - vLLM 文档|vLLM 性能分析]]） |
| `GET /ping`、`/version`、`/get_mm_limits` | 存活语/版本/多模态上限 |

### 2.5 流式与认证

```bash
# Stream（SSE 增量帧 + 末尾 usage）
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $VLLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"m","messages":[{"role":"user","content":"你好"}],
       "stream":true,"max_tokens":32,"stream_options":{"include_usage":true}}'
```
- 认证：`--api-key`（未设则默认不鉴权，生产务必设）+ `Authorization: Bearer <key>`；`--host`/`--port` 绑定。
- 采样参数：`temperature / top_p / top_k / min_p / frequency_penalty / presence_penalty / repetition_penalty / stop / max_tokens / n / best_of / logprobs / echo / ignore_eos / seed / stop_token_ids`。
- 工具调用：`tools` + `tool_choice` 由 `ToolParser` 把模型输出解析成结构化调用；推理内容（reasoning_content）由 `ReasoningParser` 处理（`--enable-reasoning`）。
- 结构化输出：`guided_json / guided_regex / guided_choice / guided_grammar`（`vllm/v1/structured_output/`，后端 xgrammar/outlines/lm_format_enforcer），OpenAI 风格 `response_format: {type: json_schema}` 亦可。

### 2.6 离线批处理（Batch）

- `vllm run_batch`（`vllm/entrypoints/openai/run_batch.py`）：读 `requests.jsonl` 批量提交（不占长连接）。
- OpenAI 风格异步批任务端点（较新版本提供 `POST /v1/batch` + 结果拉取）。

### 2.7 多模态请求管线

- **请求体**：`/v1/chat/completions` 的 `messages[].content` 支持数组形式，`image_url`/`audio_url` 等模态段可与文本混排（`"type":"image_url","image_url":{"url":"<data:base64 或 http>"}`）。
- **启动参数**：`--limit-mm-per-prompt`（如 `{"image":"2","audio":"1"}` 限制每请求各模态数量）、`--image-token-id`（图 token 占位 id）、`--mm-processor-kwargs`（processor 细节）。
- **处理管线**：请求进入后由 `InputProcessor` 走 `vllm/multimodal/`（vLLM 把处理器/编码器/输入规范化统一管理），图像经 vision encoder 编成 hidden token 并入序列；`--processor-overrides`/中间层可配置。
- **encoder KV 缓存**：多模态 encoder 的前向输出也可被缓存（`vllm/v1/core/encoder_cache_manager.py`，`--enable-encoder-cache` 相关）——**同一张图在多轮/多请求间复用，省掉重复 encode**，对齐 SGLang 的"图 token 前缀复用"语义。
- **任务**：`--task generate`；多模态模型加载用 `AutoModelForImageTextToText` / 等效入口。

### 2.8 LoRA 动态服务

- **加载**：`--lora-modules name=/path/to/adapter`（可多个，逗号分隔）；`--max-lora-rank`（默认 64）限制最大 rank。
- **选用**：请求体加 `"lora": "adapter_name"` 即对本次请求套用；未选 => base 模型。
- **热管理**：`/v1/loas`（部分版本）/ 配置中集管理接口可动态挂载-卸载适配器。
- **资源与调度**：每 LoRA 的适配权重占额外内存（`--max-cpu-loras` 可将未激活 LoRA 放 CPU）；多 LoRA 并发时按请求打散调度（LoRA 专用 KV 分块），并发与吞吐受 `--max-lora-rank`/适配器数量影响。
- **用途**：几十上百个不同风格/领域 adapter 共用一份 base 权重，性价比高于各存各的模型副本。

## 3. 部署形态与关键参数

### 3.1 常见形态

| 形态 | 方式 | 适用 |
|------|------|------|
| 单机直跑 | `vllm serve <model> --tensor-parallel-size N` | 开发/中小规模 |
| Docker | `vllm/vllm-openai:latest` | 标准生产 |
| Kubernetes | Helm chart / 状态集 + 服务 | 云原生弹性 |
| 云服务 | vLLM 官方 Serving stack / Replicate / Together 等 | 托管 |
| 多机 | `--nnodes N --dist-...`（Ray 或 mp executor） | 超大模型 TP/EP 跨机 |

### 3.2 常用启动参数（分组速记）

```
模型        : --model, --tokenizer, --trust-remote-code, --dtype(auto/float16/bfloat16),
              --max-model-len, --quantization(fp8/awq/gptq/…), --load-format
并行        : --tensor-parallel-size, --pipeline-parallel-size, --data-parallel-size,
              --expert-parallel-size, --distributed-executor-backend(ray|mp)
显存/缓存   : --gpu-memory-utilization, --kv-cache-dtype(fp8), --swap-space,
              --block-size, --enable-prefix-caching, --enable-chunked-prefill
调度/批     : --max-num-seqs, --max-num-batched-tokens, --max-num-seqs-per-prefill-dp,
              --schedule-conservativeness
加速        : --enforce-eager(关 CUDA Graph), --cuda-graph-max-bs, --enable-torch-compile
推测解码    : --speculative-config(模型/方法), --num-speculative-tokens
可观测      : --served-model-name, --api-key, --prometheus-multiproc-dir,
              --profiler-config, --log-requests
多模态      : --limit-mm-per-prompt, --image-token-id, --mm-processor-kwargs
```

> 参数随版本演进（尤其 `--cuda-graph-*`、`--enable-*` 路由开关家族）；**以 `vllm serve --help` 为准**。

### 3.3 Deployment 注意事项

- **`gpu_memory_utilization` 与显存竞争**：调 0.9→0.95 前先确认权重+KV+graph 装得下；多模型共卡用显存隔离不可靠，优先每卡一模型或用 MPS。
- **K8s 探针**：liveness=`/health`，readiness 可自定义；HTTPS 由入口网关终结。
- **监控**：`/metrics` 抓取到 Prometheus + Grafana 即可观测 TTFT / 吞吐 / KV 使用率 / 抢占。

## 4. 运行期内存与 GPU 细节（补充 Deep-Dive）

> 调度算法、PagedAttention、Prefix Caching、抢占机制见 [[sources/推理引擎/vLLM-Deep-Dive|深度解析]]。这里补「启动时怎么分显存」「KV Cache 容量怎么算」「CUDA Graph 怎么回事」。

### 4.1 启动时的显存预算流程

```
EngineCore.__init__ 触发 profile 流程：
1) 读 gpu_memory_utilization（默认0.9）× 单卡可用显存 = 目标可用内存
2) 顺序占位：模型权重（含量化）→ 激活预算 → 采样/输出 buffer
   → 剩余全部给 KV Cache（分页块池）
3) 计算 num_gpu_blocks（可容纳的物理块数）并按块对齐/上限约束
4) 若开启 CUDA Graph：从 KV 预算里分割出 graph 捕获用显存
   （graph 内张量地址固定，捕获大小 = 最大 batch × 序列长 × hidden）
5) 打印启动日志：已用权重 GB / 可用 KV 块数 / graph 大小
```

**KV Cache 容量公式（近似）**：
```
每 block 每层字节 = 2(Key+Value) × block_size × num_kv_heads × head_dim × dtype字节
总 = 每层字节 × num_layers × num_gpu_blocks
```
- 例：Llama-3-70B，`--kv-cache-dtype fp8` → KV 减半，同显存下 `num_gpu_blocks` 翻倍 → `max_num_seqs`/并发上升。
- `--block-size`（默认 16 token）越大 → 每请求边界浪费越小、但长尾碎片略增；`--enable-prefix-caching` 下块即复用单元。

### 4.2 CUDA Graph 捕获要点

- prefill/decode 前向默认用 **CUDA Graph 捕获**（`--enforce-eager` 关闭）：把若干 kernel launch 固化为一个 graph 重放，省掉每步 CPU 调度开销。
- 捕获发生在启动 profile 阶段；**捕获期间要预留显存**，捕获失败常报 "CUDA error: out of memory"（尤其显存紧时 `--enforce-eager` 或降 `--cuda-graph-max-bs`）。
- V1 为常用 batch 尺寸捕获多档图，运行期把新 batch 填进已捕获图（复用槽位），避免每步 launch。
- `--enable-torch-compile` 可叠加 torch.compile 优化算子图（A 卡/新卡上收益可观）。

### 4.3 分布式运行期

| 并行 | 切片对象 | 通信 |
|------|----------|------|
| TP | 每层权重按 head/hidden 维度切分 | NCCL allreduce（同节点最快） |
| PP | 层间流水（micro-batch 填充） | 相邻 rank 张量收发 |
| EP | MoE expert 路由到卡 | all-to-all |
| DP | 请求分摊多副本 | 无（各自独立） |

- `--distributed-executor-backend ray`：多机/混布（依赖 Ray）；`mp`：单机多卡多进程（默认现代倾向）。
- 环境变量：`NCCL_*`（超时/条带宽）、`VLLM_WORKER_MULTIPROC_METHOD(spawn/fork)`、`VLLM_LOGGING_LEVEL` 等。
- **观测指标**（`/metrics`，名称形如）：`vllm:num_requests_running/waiting`、`request_success_total`、`generation_tokens_total`、`average_time_per_output_token_seconds`、`time_to_first_token_seconds`、`e2e_latency_seconds`、`num_preemptions_total`、`vllm:kv_cache_usage_percent`、`gpu_cache_usage_percent` / `cpu_cache_usage_percent`。这些直接对应调优项（并发、前缀缓存、抢占率）。

### 4.4 常见运行问题速查

| 症状 | 原因/处置 |
|------|-----------|
| 启动 CUDA OOM | graph 捕获或权重放不下 → 降 `--gpu-memory-utilization`、`--enforce-eager`、`--cuda-graph-max-bs`、升 `--kv-cache-dtype fp8` |
| 长上下文 prefill 慢 | chunked prefill 未充分切、或 launch 数多 → 调 `--chunked-prefill-size`、`--max-num-batched-tokens` |
| 并发上不去 `num_requests_waiting` 高 | KV 块不足 → 降 max_model_len / 开 fp8 KV / 放开 `--max-num-seqs` |
| 前缀缓存收益不明显 | 前缀命中率低 → 确认 `--enable-prefix-caching`、请求共享 prompt 长 |
| 抢占频繁 | swap-space 足够才在 V0 有效，V1 基本重算 → 提 `--max-num-seqs` 预算或减并发 |

## 5. 参考与延伸

- 本文接口/路由信息依据本地仓库 `Q:/AI/vllm/vllm` 与 vLLM 稳定公开文档整理；**具体端点与参数以所用版本 `--help` 为准**（本环境无法访问外网核对最新版）。

## 📚 相关笔记

- [[sources/推理引擎/vLLM-Deep-Dive|vLLM 深度解析]] — 架构/调度/PagedAttention/前缀缓存内核（本文的调度侧底稿）
- [[sources/推理引擎/vLLM 源码 导读|vLLM 源码导读]] — 本地仓库模块地图
- [[sources/推理引擎/PagedAttention|PagedAttention]] — 分页 KV 与块表
- [[sources/推理引擎/vllm|vLLM 实体页]] — 概览
- [[sources/推理引擎/推理 引擎 监控]] — 监控/指标深度
- [[sources/推理引擎/推理 引擎 调优]] — 调优手段
- [[Clippings/vLLM 性能分析 - vLLM - vLLM 文档|vLLM 性能分析（profiling）]] — `--profiler-config` 用法