## PD 分离（srt/disaggregation）· KV 传输、状态机与调度衔接

接 [disaggregation.md](disaggregation.md)。本文件聚焦一次请求从 prefill 到 decode 的 KV 传输全链路、与 scheduler/radix cache 的衔接，以及与 vLLM KV connector 的对照。

### 传输时序（握手 → 传输 → 提交）

```
decode 收到 /generate（req.bootstrap_host/bootstap_room 由上游 router 注入）
  ├─ DecodePreallocQueue.add (decode.py:531)
  │    ├─ _create_receiver_and_enqueue (decode.py:604)   # 按后端建 KVReceiver
  │    └─ _resolve_prefill_dp_rank (decode.py:584)       # 快路径：查 prefill_info_table
  ├─ receiver.init(prefill_dp_rank) (common/conn.py:1349)
  │    ├─ 若 bootstrap_addr 不在 prefill_info_table → 标记 Failed（prefill 宕机检测）
  │    └─ _setup_bootstrap_infos (common/conn.py:1407)
  │         ├─ GET http://bootstrap/route?dp&cp&tp&pp 抓目标端点
  │         └─ 每个 (dp,cp,tp,pp) key 仅注册一次 KVArgs（connection_pool 缓存）
  │    status: Bootstrapping → WaitingForInput
  ├─ pop_preallocated (decode.py:991)   # token 预算 → _pre_alloc 预留 KV 槽位
  │    └─ send_metadata：把 kv_indices/aux_index 通知 prefill（scatter 目标定位）
  └─ DecodeTransferQueue.poll → Success → _commit_transfer_to_req (decode.py:1908)
       → req 进入 running_batch 开始 decode

prefill 侧（SchedulerDisaggregationPrefillMixin）
  ├─ event_loop_normal_disagg_prefill (prefill.py:569)
  ├─ check_bootstrap (prefill.py:1045) / create_sender (prefill.py:299)
  ├─ send_kv_chunk (prefill.py:1139)  # 按 page_size 对齐分块发送
  └─ 末 chunk：disagg_metadata_buffers.set_buf(req)（首 token 元数据随 KV 传输）
```

### 状态收敛：poll_and_all_reduce

KV 数据不用集合通信，但**传输状态用 gloo `all_reduce(MIN)` 收敛**，保证 TP/CP 各 rank 同步提交（utils.py:205）：

```
poll_and_all_reduce(pollers, gloo_group, ...)
  ├─ _poll_with_failure_injection        # SGLANG_TEST_DISAGG_FAILURE_PROB 随机注入失败（测试）
  ├─ _apply_metadata_gate                # Success→Transferring：decode 侧 metadata 未落地前不放行
  └─ dist.all_reduce(MIN) on attn_tp_cpu_group
poll_and_all_reduce_attn_cp_tp_group      # 先 TP 后 CP 两级收敛（utils.py:227）
poll_and_all_reduce_with_staging          # staging 感知轮询：推进 scatter、超时转 Failed（utils.py:247）
```

`update_status`（common/conn.py:327）状态单调递进（失败可覆盖）；`bootstrap_room` 复用由 `ReqToMetadataIdxAllocator`（utils.py:290）管理，Failed 不会污染复用槽位。

### 元数据面：MetadataBuffers

prefill 把首输出 token 的全部采样元数据写入固定大小张量块（utils.py:313），随末 chunk 传输，decode 提交后取回：

| 缓冲 | 维度 | 用途 |
|---|---|---|
| `output_ids` / `cached_tokens` | (size,16) int32 | 首 token id；cached 计数槽 0-3，多模态 token 数槽 4/5/6（image/audio/video） |
| `output_token_logprobs_val/idx` | (size,16) | logprob 值/索引 |
| `output_top_logprobs_val/idx` | (size,max_top_logprobs_num) | topk logprob（默认上限 128） |
| `output_token_sampling_mask_*` | 可选 | sampling mask（需 `SGLANG_DISAGGREGATION_SAMPLING_MASK_MAX_TOKENS>0`） |
| `output_topk_p/index` | (size,16) | speculative decode topk |
| `output_hidden_states` | (size,hidden_size) | spec 草稿 hidden states |
| `output_dsa_topk_indices` | 可选 | DSA seed 元数据（`get_dsa_seed_metadata_dim`，utils.py:69） |
| `bootstrap_room` | (size,8) | decode 侧校验字段（防 metadata 错位） |

NPU/自定义内存池/CUDA mem pool 时缓冲可置于对应设备；RDMA 最小 64B 已由填充满足（utils.py:351 注释）。

### prefill 侧 chunk 发送

`send_kv_chunk`（prefill.py:1139）把 `req.start_send_idx..end_idx` 的 token 翻译成 KV 页索引（`req_to_token_pool`），按 `page_size` 对齐截断；末 chunk 才附带 metadata 与状态负载。状态负载按 `StateType` 打包：

- `_mamba_payload`：Mamba 状态页索引（经 `translate_mamba_indices`）
- `_swa_payload`：滑窗 KV 页（`translate_loc_from_full_to_swa`）
- `_dsa_payload` / `_swa_ring_payload`：DSA / unified_kv SWA ring（DeepSeek-V4）
- `_c128_payload`：请求级 C128 在线状态

`maybe_send_cached_prefix_chunk`（prefill.py:1100）跳过 radix cache 已匹配前缀的重复传输；`process_disagg_prefill_inflight_queue`（prefill.py:830）管理在传队列与失败处理（`handle_inflight_transfer_failure` prefill.py:937）。

### decode 侧预分配与传输队列

- `DecodePreallocQueue`（decode.py:296）：`_match_prefix_and_lock`（decode.py:568）对 decode 端 radix cache 匹配前缀并 `inc_lock_ref` 防驱逐；`pop_preallocated`（decode.py:991）按可回收 token 预算（`_allocatable_token_budgets` decode.py:1467）预留 KV 槽位——**先预留、后传输**，使 RDMA 直写最终 GPU 位置，避免二次搬运。
- `DecodeTransferQueue`（decode.py:1864）：轮询 receiver，Success 后 `_commit_transfer_to_req`（decode.py:1908）把 KV 页索引绑定到 Req 并交给 scheduler 进入 running_batch；支持 DCP relayout 与 staging。
- `ScheduleBatchDisaggregationDecodeMixin`（decode_schedule_batch_mixin.py:21）：`prepare_for_prebuilt`/`process_prebuilt` 在预建 batch 中处理在传请求。

### 与 radix cache / HiCache 衔接

| 能力 | 机制 |
|---|---|
| decode 端前缀复用 | 默认 chunk cache（`disable_radix_cache=True`）；开启 `--disaggregation-decode-enable-radix-cache` 后前缀匹配复用已传 KV，减少冗余 RDMA |
| prefill 端 | 正常 radix cache，命中前缀不重算、不重传（`maybe_send_cached_prefix_chunk`） |
| HiCache offload | `DecodeKVCacheOffloadManager`（decode_kvcache_offload_manager.py:34）：decode 端把旧页按 stride offload 到 host pool/磁盘，通过 `kv_events.py` 的 ZMQ 发布（`ZmqEventPublisher`，kv_events.py:185，PUB+ROUTER replay）对外广播 block 增删 |
| 重算/重传 | prefill 心跳失败 → decode 经 HTTP 触发 prefill recompute（`submit_prefill_recompute`，common/conn.py:484）；retraction 时 `is_rebootstrap` 路径重建握手（decode.py:626） |

### 编码器分离（正交特性）

与 PD 分离独立的"encoder-only"模式（`--encoder-only`/`--language-only`，server_args.py:3201 起）：

- `encode_server.py:3850 launch_encoder` 启动独立视觉 encoder 服务；`EncoderScheduler`（encode_server.py:2752）与 `DPDispatcher`（encode_server.py:3168）管理视觉 token prefill。
- `encode_receiver.py:2628 create_mm_receiver` 在 language 侧按传输模式选择 `MMReceiverHTTP`/`MMReceiverGrpc`/RDMA 接收；`encode_grpc_server.py:74 SGLangEncoderServer` 提供 gRPC 协议。

### 与 vLLM disaggregation / KV connector 对照

| 维度 | SGLang（本目录） | vLLM |
|---|---|---|
| 抽象层 | `base/conn.py` 四基类 + `KVArgs` 几何描述 | `kv_transfer/kv_connector` 的 `KVConnectorBase`，由 `KVConnectorManager` 管理生命周期 |
| 后端选择 | `get_kv_class` 工厂（utils.py:630）按 `TransferBackend` 分派 | 按 `--kv-transfer-config` 分发 `MooncakeKVConnector`/`NIXLKVConnector`/`PyNcclKVConnector` 等 |
| 状态机 | `KVPoll` 内嵌请求级状态 + gloo MIN all_reduce 收敛 | connector 侧 `connector_state` 轮询，worker 侧同步 |
| 与调度器耦合 | 队列即调度组件（`DecodePreallocQueue`/`DecodeTransferQueue` 直接挂在 Scheduler 上） | 独立 connector 层，worker 在 step 前后调用 |
| 控制面 | prefill bootstrap HTTP 注册表（/route）+ 心跳 | 各有 bootstrap server / 路由发现机制 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
