# FAQ：SGLang 源码分析常见问题

## 错误码 / 错误信息

本知识库为源码分析，不定义业务错误码。源码中明确出现的异常/错误信息按模块记录：

| 位置 | 错误信息 | 触发条件 |
|---|---|---|
| `srt/server_args.py` | `ValueError`/`RuntimeError` | CLI 参数冲突或非法组合（如并行度与模型不匹配） |
| `srt/environ.py` | `ValueError` | 未知/弃用的 `SGLANG_*` 环境变量 |
| `srt/managers/communicator.py` | 消息类型校验失败 | 进程间消息 tag 与注册不符 |
| `srt/mem_cache/` | 内存分配失败 | 显存预算（mem_fraction_static）不足以容纳请求池 |

## 通用 HTTP 状态定位

HTTP 语义位于 `09-entrypoints/http-server_part1.md` 描述的 `/generate` 与 OpenAI 兼容 `/v1/*` 端点：错误以标准 HTTP 状态 + 消息返回。以下为定位步骤而非错误码定义：

1. 4xx 多为请求参数/鉴权问题（`/v1/*` 协议族校验）。
2. 5xx 多为引擎侧异常，回溯 Scheduler/TPWorker 日志。
3. 流式请求中断查 `finish_reason` 与 DetokenizerManager 增量解码。

## 常见问题

### SGLang 与 vLLM 的架构核心差异？
SGLang 用多进程 manager 模型（TokenizerManager 前端 + Scheduler/TPWorker 同进程 + DetokenizerManager），核心创新是 RadixAttention 前缀树缓存；vLLM V1 用独立 EngineCore 进程 + ZMQ。对照见 `00-overview/architecture_part2.md`。

### RadixCache 如何工作？
前缀树节点按 token 块组织，`match_prefix` 命中复用 KV，`insert` 写入新块，eviction 按策略回收。见 `04-radix-cache/`。

### 请求如何从 HTTP 到 GPU？
HTTP → `TokenizerManager`（`02-managers/tokenizer-manager.md`）→ `Scheduler` 调度（`03-scheduler/`）→ `TpModelWorker` 执行（`06-model-executor/model-runner.md`）→ `DetokenizerManager` 输出。

### 显存如何分配？
`mem_fraction_static` 预算 + `_compute_cell_size` 每 token 字节成本，估算请求池/KV 池大小。见 `05-mem-cache/allocation-sizing.md`。

### 注意力后端如何选择？
`ATTENTION_BACKENDS` 注册表 + 默认选择逻辑，支持 FlashInfer/FA3/FA4/Triton/FlashMLA 等 20+ 后端。见 `07-attention/attention-backends.md`。

### 投机解码如何组织？
spec worker 替换 model_worker，draft/verify/draft_extend 三阶段；EAGLE-1/2/3 树形草稿 + 多步验收。见 `13-speculative/`。

### 工具调用与约束解码？
tools schema 经 `get_structure_constraint` → `to_sampling_params`，`FunctionCallParser` 33 个 detector 解析；grammar 后端 xgrammar（默认）/outlines/llguidance。见 `14-function-constrained/`。

### sglang.lang 是什么？
声明式/指令式双执行态的 DSL（`@function`、gen/select 原语），编译后经 backend 翻译为 HTTP/OpenAI 请求。见 `19-lang-observability/lang-frontend.md`。

### PD 分离如何传输 KV？
prefill/decode 分离实例经 conn 抽象（mooncake/nixl/mori 等后端）传输 KV。见 `18-disaggregation/`。

## 顺序排错流程

1. 确认请求是否到达 TokenizerManager（`09-entrypoints`、`02-managers`）。
2. 确认调度与内存准入（`03-scheduler`、`05-mem-cache`）。
3. 确认 radix 命中/淘汰是否异常（`04-radix-cache`）。
4. 确认模型执行与采样（`06-model-executor`、`07-attention`、`08-sampling`）。

> 返回：[skill.md](skill.md)
