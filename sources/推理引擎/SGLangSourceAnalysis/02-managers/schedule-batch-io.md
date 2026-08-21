## ScheduleBatch 与请求 IO 结构

本文说明调度器侧的数据结构（`schedule_batch.py`）与跨进程 IO 结构（`io_struct.py`）。核心数据流：HTTP 请求经 TokenizerManager tokenize 成 `TokenizedGenerateReqInput` → Scheduler 反序列化为 `Req` → 聚成 `ScheduleBatch` → `ForwardBatch` 送模型执行（见 `schedule_batch.py:36` 顶部 docstring）。

### Req：请求在调度器侧的状态

`Req`（`schedule_batch.py:803`）是 `Scheduler.handle_generate_request`（`scheduler.py:2396`）由 `TokenizedGenerateReqInput` 反解构造的对象，字段按功能分组：

| 字段（节选） | 说明 |
|---|---|
| `rid` / `origin_input_ids` / `origin_input_ids_unpadded` | 请求 id 与原始 token 序列（后者为图像 padding 前的版本） |
| `output_ids`（`array("q")`）/ `full_untruncated_fill_ids` / `extend_range` | 逐 decode 输出追加；`full_untruncated_fill_ids` 为 origin+output(+DLLM mask) 全量序列，长度契约不可变（:865-870） |
| `sampling_params` / `stream` / `eos_token_ids` / `priority` | 采样参数、是否流式、自定义 eos、优先级（`_set_or_validate_priority` :2791） |
| `req_pool_idx` / `mamba_pool_idx` | 在 `ReqToTokenPool` 中的槽位（:934），KV/请求内存管理核心索引 |
| `prefix_indices` / `last_node` / `host_hit_length` / `num_matched_prefix_tokens` | RadixCache 前缀匹配结果：共享前缀的 KV 索引、命中节点、device/host/storage 三级命中长度（:990-1016） |
| `kv_committed_len` / `cached_tokens` / `cached_tokens_device/host/storage` | 已提交 KV 长度与缓存命中分解（HiCache） |
| `surr_offset` / `read_offset` / `decoded_text` | 增量反分词窗口：只对 `read_ids = [surr_offset:read_offset]` 区间增量解码 |
| `logprob`（`ReqLogprob` :766）/ `return_logprob` / `logprob_start_len` | 输入/输出 token logprob 与 top-logprobs 累积容器 |
| `to_finish` / `finished_reason`（`BaseFinishReason` :223） | 终止标记；事件循环中途只写 `to_finish`，`finished_reason` 在批次结果处理时统一落盘（:960-963） |
| `stream` 相关 `send_token_offset` / `send_decode_id_offset` | 增量流式增量发送偏移 |
| `grammar` / `grammar_key` | 结构化输出语法对象与缓存键 |
| `session` / `session_id` / `cache_salt` | 会话连续性（`SessionController`）与 radix cache 命名空间隔离 |
| `disagg_*` / `routed_dp_rank` | PD 分离推理与 DP 路由字段 |

终止原因体系（`schedule_batch.py:223-289`）：`FINISH_MATCHED_TOKEN`/`FINISH_MATCHED_STR`/`FINISHED_MATCHED_REGEX`/`FINISH_LENGTH`/`FINISH_ABORT`，`to_json()` 输出 `{"type": "stop"|"length"|"abort", ...}` 对齐 OpenAI 语义。

### ScheduleBatch：一批请求的承载

`ScheduleBatch`（`schedule_batch.py:2005`）由 `Scheduler.get_new_batch_prefill`/`get_next_batch_to_run`（`scheduler.py:3064/3209`）从 `waiting_queue` 组装。类 docstring 明确其分工：**CPU 侧调度数据**，GPU 张量由 `ForwardBatch` 承载。字段：

| 类别 | 字段 | 说明 |
|---|---|---|
| 请求列表 | `reqs: List[Req]` | 本批请求；`ForwardBatch` 据此派生 `lora_ids`/`rids`/`grammars`/`positions` |
| 共享资源 | `req_to_token_pool` / `token_to_kv_pool_allocator` / `tree_cache` | 请求→KV 映射池、KV page 分配器、RadixCache（engine 生命周期内各批相同） |
| GPU 张量（→ForwardBatch） | `input_ids` / `req_pool_indices` / `seq_lens` / `out_cache_loc` / `orig_seq_lens` | shape 均 `[b]`；`out_cache_loc` 为本次前向 KV 写出位置；`input_ids` 缺省为全 1 假 id（embeds 输入时） |
| 前向模式 | `forward_mode` / `is_extend_in_batch` / `is_prefill_only` | `ForwardMode` 区分 extend/decode/spec 等，决定调度与 CUDA graph 分支 |
| 采样 | `sampling_info: SamplingBatchInfo` / `return_logprob` / `top_logprobs_nums` | 采样参数批量张量（自 `SamplingBatchInfo.prepare` 生成） |
| 投机 | `spec_algorithm` / `spec_info` | 投机解码算法与 draft 输入 |
| 分块 prefill | `chunked_req` / `contains_last_prefill_chunk` / `extend_num_tokens` | 长请求 chunked prefill 状态；`chunked_req` 移出批次、结果 `stash_chunked_request`（:2974） |
| 多模态 | `multimodal_inputs` / `encoder_lens` | 图片/音频/视频输入与 encoder-decoder 长度 |
| DP/PP | `inner_idle_batch` / `decoding_reqs` / `split_index` | DP-attention、decode 伴随 chunked-prefill、split prefill 专用 |
| 指标 | `fpm_start_time` / `dp_cooperation_info` / `launch_ts` | 前向/调度指标埋点 |

`ScheduleBatch.init_new`（:2192）聚合各请求的标志位：`return_logprob = any(req.return_logprob)`、`return_hidden_states_mode` 取批次最大（`CaptureHiddenMode` 偏序）。

### ScheduleBatch → ForwardBatch

```python
# scheduler.run_batch → model_worker.forward_batch_generation（scheduler.py:3695 → tp_worker.py:574）
forward_batch = ForwardBatch.init_new(batch)          # model_runner/forward_batch_info.py
# input_ids / req_pool_indices / seq_lens / out_cache_loc / sampling_info 等直接搬上 GPU
```

`ScheduleBatch` 亦用于事件循环间传递：`get_next_batch_to_run` 返回 `NextBatchPlan`（`schedule_batch.py:3423`，`msgspec.Struct`：`batch_to_run` + `running_batch`），overlap 模式下 `event_loop_overlap` 用 `result_queue` 暂存 `(batch.copy(), batch_result)` 让 CPU 结果处理与 GPU 前向重叠（`scheduler.py:1778`）。

### 跨进程 IO 结构（io_struct.py）

`io_struct.py` 顶部 docstring 声明其**只放 IPC struct 定义**。消息基类：

```python
class BaseReq(msgspec.Struct, tag=True, kw_only=True, array_like=True):     # :79
    rid: Optional[str] = None
    http_worker_ipc: Optional[str] = None

class BaseBatchReq(msgspec.Struct, tag=True, kw_only=True, array_like=True): # :90
    rids: Optional[List[str]] = None
    http_worker_ipcs: Optional[List[Optional[str]]] = None
```

| 结构 | 文件:行 | 说明 |
|---|---|---|
| `GenerateReqInput`（dataclass） | :160 | HTTP 层输入：`rid`/`session_id`/`text`/`input_ids`/`input_embeds`/`image_data`/`sampling_params`/`stream`/`parallel_sample_num` 等，`normalize_batch_and_arguments` 摊平批量 |
| `TokenizedGenerateReqInput` | :941 | 下行单请求：`input_text`/`input_ids`/`mm_inputs`(PickleWrapper)/`sampling_params`/`return_logprob`/`stream`/`session_params`/`lora_id`/`custom_logit_processor`/`bootstrap_host`/`routed_dp_rank`/`priority`/`time_stats`(PickleWrapper)；`wrap_pickle_fields`/`unwrap_pickle_fields`（:1044/:1049） |
| `BatchTokenizedGenerateReqInput` | :1055 | 批量容器：`batch: List[TokenizedGenerateReqInput]`，支持 `__len__`/`__getitem__`/`__iter__` |
| `TokenizedEmbeddingReqInput` / `BatchTokenizedEmbeddingReqInput` | :1305/:1343 | embedding 对应物 |
| `BatchTokenIDOutput` | :1404 | Scheduler→Detokenizer：`finished_reasons`/`decoded_texts`/`decode_ids`/`read_offsets`/`prompt_tokens`/`cached_tokens`/全部 logprob 平行数组/`output_hidden_states`/`routed_experts`/`retraction_counts`/`time_stats` |
| `BatchStrOutput` | :1504 | Detokenizer→Tokenizer：`output_strs` + `output_ids` + 与上面同构的 logprob/统计字段 |
| `BatchEmbeddingOutput` | :1592 | embedding 结果：`embeddings`（向量/topk 稀疏 dict） |
| `AbortReq` | :2005 | `abort_all`/`finished_reason`/`abort_message`；`rid` 为空时置 `""` |

`PickleWrapper`（:104）把多模态输入、`time_stats`、`customized_info` 等非 msgspec 类型 pickle 为 bytes 塞进 msgpack 帧；`SGLANG_USE_PICKLE_IPC` 模式下整链路走 pickle，`wrap_as_pickle` 为 no-op。多模态张量另有共享内存旁路（`wrap_shm_features`），ZMQ 只传 `ShmPointerMMData` 句柄。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
