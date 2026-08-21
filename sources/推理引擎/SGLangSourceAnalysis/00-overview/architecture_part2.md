## SGLang 整体架构总览：RadixCache、请求路径与对比（_part2）

承接 [_part1](architecture_part1.md)（版本、进程模型、四大 Manager、ZMQ IPC）。

### RadixAttention 前缀缓存

核心为 `mem_cache/radix_cache.py::RadixCache`（:303，实现 `mem_cache/base_prefix_cache.py::BasePrefixCache`）。Scheduler 在 `scheduler.py:558` 持有 `self.tree_cache`，与 KV 池联动：`req_to_token_pool`（请求 token→KV block 映射）与 `token_to_kv_pool_allocator`（KV page 分配/释放）。

| 机制 | 实现 | 说明 |
|---|---|---|
| 前缀树 | `TreeNode`（:238），子节点按首个逻辑单元分桶（`child_key`） | 节点 key 为 `RadixKey`（token_ids + `extra_key` 命名空间 + `cache_salt` + EAGLE bigram 视图），value 为对应 KV cache 索引张量 |
| 前缀匹配 | `match_prefix`（:377） | 沿树查找最长公共前缀，返回拼接后的 `device_indices`（可直接复用为 prefill 输入）；命中段内时分裂节点暴露精确边界（结构性优化，不复制数据） |
| 块复用插入 | `insert`（:437）/ `cache_unfinished_req`（:516）/ `cache_finished_req`（:459） | 只为「超出公共前缀」的新 token 分配 KV page，`prefix_len` 之前的块计入复用 |
| 引用保护 | `inc_lock_ref`/`dec_lock_ref`（:623/:638） | 正在运行的请求对其前缀路径节点加锁，从可驱逐区移入受保护区，防止运行中被逐出 |
| Eviction | `evict`（:593） | 只驱逐 `evictable_leaves` 中的叶子节点，按 `eviction_strategy.get_priority`（策略由 `--eviction-policy` 决定）建堆逐个弹出、释放 KV 段并上溯父节点；命中率、驱逐指标计入 collector |

「RadixAttention」即把注意力计算中的 KV cache 映射为这棵前缀树：`match_prefix` 得到共享前缀的物理块，模型仅对「新增后缀」做 prefill 注意力，从而让相似前缀请求（多轮对话、few-shot 共用提示、共享 system prompt）显著降低 TTFT 与重复计算。

### 请求端到端路径

1. **HTTP 入口**：`POST /generate`（`http_server.py:894`）→ `TokenizerManager.generate_request`（`tokenizer_manager.py:765`），流式走 `StreamingResponse` 并挂 `create_abort_task`。
2. **Tokenize 与下行**：`normalize_batch_and_arguments` → `_tokenize_one_request`（:995，含 mm_processor 预处理）→ 组装 `TokenizedGenerateReqInput` → `wrap_shm_features`/`wrap_pickle_fields` → `_dispatch_to_scheduler`（:569）PUSH。
3. **调度与执行**：Scheduler rank0 从 `recv_from_tokenizer` PULL（`ipc_channels.py:38`）→ `process_input_requests`（:1901）→ 对每个新请求 `match_prefix` 复用前缀、分配新块 → `get_next_batch_to_run`（:3064）→ `run_batch` → `model_worker.forward_batch_generation`（:3832，即 `TpModelWorker`）→ 采样出 `next_token_ids`。
4. **反分词**：Scheduler 经 `output_streamer` 把 `BatchTokenIDOutput` PUSH 到 Detokenizer（`ipc_channels.py:63`）→ `_decode_batch_token_id_output`（:291）按 `DecodeStatus` 做增量解码（含 UTF-8 截断恢复、stop 串裁剪）→ `BatchStrOutput` PUSH 回 Tokenizer。
5. **回包**：Tokenizer 的 `handle_loop`（:2199）PULL 到包 → `_handle_batch_output`（:2214）填 `meta_info`（finish_reason/prompt_tokens/cached_tokens 等）→ 置 `state.event` → `_wait_one_response`（:1733）yield 给 HTTP（流式按 `stream_interval` 分块，非流式取末块）。

`skip_tokenizer_init` 模式下 Scheduler 把 `BatchTokenIDOutput` 直接发给 Tokenizer（`ipc_channels.py:55`），跳过 Detokenizer。

### 与 vLLM V1 EngineCore 的粗粒度对比

| 维度 | vLLM V1 | SGLang SRT |
|---|---|---|
| 进程模型 | 前端 + 单个 EngineCore 后台进程（DP 时另起 DPCoordinator） | 主进程（HTTP+TokenizerManager）+ 每 TP rank 一个 Scheduler 进程（内嵌模型执行）+ 1 个 Detokenizer 进程 |
| 调度/执行 | EngineCore 内 `Scheduler` 与 `ModelExecutor` 分离 | `Scheduler` 与 `TpModelWorker` 同进程，无独立执行进程 |
| 反分词 | 前端进程 `OutputProcessor` 内完成 | 独立 `DetokenizerManager` 子进程 |
| IPC | ZMQ DEALER/ROUTER + msgspec msgpack | ZMQ PUSH/PULL 单向环 + DEALER RPC，msgspec msgpack（默认） |
| 前缀缓存 | BlockManager + hash-based `PrefixCachingBlockAllocator`（hashed block） | 显式 radix 树 `RadixCache`：节点分裂、叶子驱逐、lock_ref 保护 |
| 控制流 | EngineCore `run_busy_loop` 轮询输入队列 | Scheduler `event_loop_normal`/`event_loop_overlap` 同步轮询 ZMQ |
| 流式 | `EngineCoreOutputs` 批量容器回传 | `BatchStrOutput` 按 stream_interval 批量回传 |

共同点：两者都把「前端（HTTP/输入处理）」与「GPU 推理内核」解耦、都用 ZMQ+二进制序列化、都支持 DP/TP/PP 并行与 CUDA graph。

### sglang.lang 前端语言（简要）

`sglang/lang/` 提供「结构化生成」DSL：`@sgl.function` 装饰普通 Python 函数，函数体内用 `sgl.gen(...)`/`sgl.select(...)`/`sgl.role(...)`/`sgl.image(...)` 等原语描述生成过程（`lang/api.py`）。程序被编译为 IR（`lang/ir.py`：`SglFunction`/`SglGen`/`SglSelect`/`SglExpr` 树），由 `lang/interpreter.py` 的 `run_program` 执行，产出批量 prompt 交给 backend（`Runtime` HTTP endpoint 或进程内 `Engine`，`api.py:35`）。它对上层的意义：一套程序即可驱动 SRT 服务端，其请求最终仍走上文「HTTP → TokenizerManager → Scheduler → …」路径，多轮上下文共享则依赖 RadixCache 前缀复用。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
