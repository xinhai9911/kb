## 进程间消息协议：communicator 与 io_struct

本文聚焦 `managers/communicator.py` 与 `managers/io_struct.py` 定义的 IPC 消息协议，以及各 Manager 收端的类型分派。ZMQ 链路拓扑（PUSH/PULL 单向环 + DEALER RPC、`PortArgs` 地址）见 [00-overview](../00-overview/architecture_part1.md)，此处不重复。

### 消息类型的载体：msgspec tag 联合

所有跨进程消息都是 `msgspec.Struct(tag=True)` 子类（`io_struct.py:79/90` 的 `BaseReq`/`BaseBatchReq`），收端用 `msgpack.Decoder(Union[全部类型])` 按 tag 解码。`io_struct.py` 共定义 **103** 个类/枚举，其中 **89** 种带 tag 的消息类型，按用途分四组：

| 组 | 类型数 | 代表类型 | 链路 |
|---|---|---|---|
| 生成请求（数据面下行） | 2 | `TokenizedGenerateReqInput` / `BatchTokenizedGenerateReqInput` | Tokenizer→Scheduler |
| Embedding 请求（数据面下行） | 2 | `TokenizedEmbeddingReqInput` / `BatchTokenizedEmbeddingReqInput` | Tokenizer→Scheduler |
| 输出（数据面上行） | 3 | `BatchTokenIDOutput` / `BatchStrOutput` / `BatchEmbeddingOutput` | Scheduler→Detokenizer→Tokenizer |
| 控制面（Request/Output 成对） | 82 | `AbortReq`、`FlushCacheReqInput/Output`、`PauseGenerationReqInput`、`UpdateWeightsFromTensorReqInput/Output`、`LoadLoRAAdapterReqInput`、`RpcReqInput/Output` 等 | Tokenizer↔Scheduler（FanOut） |

另有非 tagged 辅助结构：`PickleWrapper`、`SessionParams`、`ExpertWeightPointer`、`ParallelismInfo`、`ChecksumInfo`、`Function`、`Tool`，以及 HTTP 层 dataclass `GenerateReqInput`/`EmbeddingReqInput` 和枚举 `ProfileReqType`/`ExpertDistributionReqType`/`BlockReqType`。

### 控制面核心类型

| 消息 | 文件:行 | 关键字段 |
|---|---|---|
| `AbortReq` | io_struct.py:2005 | `abort_all`、`finished_reason`(FinishReasonDict)、`abort_message`；`rid=None` 时置 `""` |
| `FlushCacheReqInput/Output` | :1628/:1632 | 清空 radix cache 与 KV 池，`Output.success/message` |
| `PauseGenerationReqInput` / `ContinueGenerationReqInput` | :1700/:1722 | 暂停/恢复推理（权重更新、LoRA 换载期间） |
| `UpdateWeightFromDiskReqInput/Output` | :1743/:1768 | 磁盘权重热更新，`Output.success/message` |
| `UpdateWeightsFromTensorReqInput/Output` | :1798/:1821 | `serialized_named_tensors` 张量热更新（DP 校验：`dp_size==1` 或 dp_attention） |
| `ProfileReq/Output` | :2072/:2101 | `ProfileReqType.START/STOP_PROFILE`，`with_stack`/`record_shapes` |
| `RpcReqInput/Output` | :2203/:2209 | Scheduler 侧 `handle_rpc_request` 通用 RPC，走 `recv_from_rpc` 专线 |
| `OpenSessionReqInput/Output` | :2127/:2138 | 会话开启（流式/非流式 session） |

### FanOutCommunicator：一发多收控制原语

`FanOutCommunicator`（`communicator.py:13`）是 Tokenizer 侧向**所有 scheduler rank** 广播控制请求并等齐响应的抽象：

| 模式 | 语义 |
|---|---|
| `queueing`（默认） | 请求 FIFO 串行：`asyncio.Lock` 保序，并发调用者排队；`handle_recv` 攒满 `fan_out` 个响应后 `event.set()` |
| `watching` | 并发调用者共享同一个在途请求，各自等同一结果（幂等控制用） |

- `TokenizerControlMixin.init_communicators`（`tokenizer_control_mixin.py:154`）按 `_COMMUNICATOR_SPECS`（:94，**26 条**声明式规格 `(名称前缀, 响应类型, [模式])`）为每类控制操作建 `self.{name}_communicator`，并注册 `resp_type → communicator.handle_recv` 到 `_result_dispatcher`。
- 发送侧统一调 `self._dispatch_to_scheduler(obj)`（PUSH 到 `scheduler_input_ipc_name`）；响应经 `recv_from_detokenizer` 回环，`handle_loop` 内 `_result_dispatcher` 按 tag 分派到对应 communicator。
- 典型用法：`flush_cache` 只取 `results[0]`；`update_weights_from_*` 用 `FanOutCommunicator.merge_results`（`all_success` + `" | ".join(messages)`）聚合全部 rank；DP>1 时用 `set_fan_out` 调整期望响应数（:168）。
- 权重/LoRA 更新持有 `model_update_lock`/`is_pause_cond` 保证与新请求互斥（见 [tokenizer-manager.md](tokenizer-manager.md)）。

### 收端分派：TypeBasedDispatcher

三个 Manager 各自注册 `类型 → 处理器` 映射，收到消息按 msgspec 类型分派：

| Manager | 注册处 | 覆盖面 |
|---|---|---|
| Scheduler | `scheduler.py:1556` | **约 40 种**：数据面 `handle_generate_request`/`handle_embedding_request`/`handle_batch_generate_request`/`handle_batch_embedding_request`，控制面 `abort_request`/`flush_wrapper`/`weight_updater.*`/`pause_generation`/`load_lora_adapter` 等 |
| TokenizerManager | `tokenizer_manager.py:743` + `_COMMUNICATOR_SPECS` | `AbortReq`→`_handle_abort_req`、`OpenSessionReqOutput`、`UpdateWeightFromDiskReqOutput`、`FreezeGCReq`、`HealthCheckOutput`(忽略)、`ActiveRanksOutput`、`ElasticScaleUpdateReq` + 26 类 FanOut 响应 |
| DetokenizerManager | `detokenizer_manager.py:157` | `BatchEmbeddingOutput`→直通、`BatchTokenIDOutput`→增量解码、`FreezeGCReq`/`ConfigureLoggingReq` |

Scheduler 收端前置 `SchedulerRequestReceiver.recv_requests`（`scheduler_components/request_receiver.py:49`）：仅 `pp_rank==0 && attn_tp_rank==0 && attn_cp_rank==0` 从 ZMQ 拉取（`zmq.NOBLOCK` 循环，`max_recv_per_poll` 限制单轮条数），随后经 NCCL/gloo `broadcast_pyobj` 广播到同 TP/PP 各 rank；DP-attention 下 `_split_work_and_control_reqs` 把数据面与控制面分开走不同广播组。`unwrap_pickle_fields`/`unwrap_shm_features` 在广播完成后才解包，保证广播只传句柄元数据。

### DetokenizerManager 的增量解码状态

`DetokenizerManager`（`detokenizer_manager.py:92`）`event_loop`（:167）收 `BatchTokenIDOutput` → `_decode_batch_token_id_output`（:291）→ 回 `BatchStrOutput`。核心是 `DecodeStatus`（:64）维护的 `decode_status: dict`（容量 `SGLANG_DETOKENIZER_MAX_STATES`，默认 1<<16）：

```python
# 增量窗口（surr_ids = decode_ids[:surr_offset], read_ids = decode_ids[surr_offset:read_offset]）
# 只对新区间解码拼接，控制反分词 O(n²) 开销；UTF-8 边界截断由 surr 冗余区兜底
```

- `_clamp_decode_ids`（:213）：多模态占位符/radix pad 哈希的超界 id 钳到 0，防 tiktoken `OverflowError`。
- `_grouped_batch_decode`（:227）：fast tokenizer 按 `(skip_special_tokens, spaces_between_special_tokens)` 分组批量 `batch_decode`。
- `trim_matched_stop`（:177）：按 `finished_reason.matched` 裁剪 stop 串/token（`no_stop_trim=True` 时保留）。
- Embedding 输出直通（:209），不经解码；`skip_tokenizer_init` 时 Detokenizer 不持 tokenizer，scheduler 直接向 Tokenizer 发 `BatchTokenIDOutput`。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
