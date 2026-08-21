## PP 调度与策略扩展（scheduler_pp_mixin）

本文基于 `sglang/srt/managers/scheduler_pp_mixin.py`，说明 `SchedulerPPMixin` 的流水线并行调度循环、动态 chunk 预测，以及 PD 分离场景下的 PP 变体。PP 模式下 `dispatch_event_loop` 直接选 `event_loop_pp`（或 `event_loop_pp_disagg_prefill/decode`），每个 PP stage 各跑一份 Scheduler，经 P2P 通信链传递请求与中间激活。

### PP 调度循环（event_loop_pp, scheduler_pp_mixin.py:69）

docstring 给出统一调度顺序（每 stage 相同，由前一 stage 通知推进）：

```
Stage P:
recv i-th req 与 proxy → run i-th batch → 异步接收上一批输出 →
process 上一批结果（与当前批 GPU 前向并行）→ 异步发送本批 req/proxy/输出
```

实现要点：

| 特性 | 代码 |
|---|---|
| 微批矩阵 | `mbs`/`last_mbs`/`running_mbs` 各为 `pp_loop_size` 长度的列表（:567-572），`running_batch`/`last_batch` 每微批切换 |
| 循环深度 | `pp_loop_size = pp_size + pp_async_batch_depth`（`init_pp_loop_state` :561） |
| 通信模式 | 异步发送（`async_send=True`）+ 同步接收，避免失步同时降低通信开销（:74-75） |
| 输出缓冲 | `pp_async_batch_depth > 0` 时 `_pp_commit_send_output_work_and_preprocess_output_tensors` 预取下微批输出，`d2h_event.synchronize` 后处理结果（:126-155） |
| 中间激活 | 非末 rank 把 `pp_hidden_states_proxy_tensors` 发下一 stage（`_pp_send_dict_to_next_stage`），`_pp_recv_proxy_tensors` 接收 |
| 空闲判定 | 一轮内所有微批 `cur_batch` 为空才 `on_idle`（:173-175） |

`PPBatchMetadata`（:63）承载跨 stage 的批元数据；`_pp_launch_batch`（:1280）在对应 stage 上跑 `forward_batch_generation`。

### 动态 chunk 预测（ChunkSizePredictor, :1486）

`enable_dynamic_chunking`（`init_chunked_prefill`，`scheduler.py:1187`）仅 PP>1 生效，让每个 chunk 维持近似相同的执行时长以对齐流水线：

- `profile_and_init_predictor`（:585）只在 PP0 用 128 个递减 chunk 尺寸预热测延迟，广播到所有 rank。
- 拟合模型 `f(l) = a·l² + b·l + c`（`np.linalg.lstsq`），强制 `a > 0`（attention 二次复杂度）、`b ≥ 0`。
- `set_target_latency(base_chunk_size)`：目标 = `f(base) - f(0)`；`predict_next_chunk_size(history_len)`（:1574）求使 `f(history+x) - f(history) = target` 的 x，供 `_get_new_batch_prefill_raw` 的 `dynamic_size`（`scheduler.py:3295-3299`）覆盖静态 `chunked_prefill_size`。

### PD 分离的 PP 变体

| 变体 | 位置 | 差异 |
|---|---|---|
| `event_loop_pp_disagg_prefill` | :178 | prefill 引擎：bootstrap 队列（`_pp_pd_get_bootstrapped_ids` :825）接送请求，KV 传输完成前 `PrefillBootstrapQueue` 托管，`send_consensus_bootstrapped_ids/release_ids` 跨 rank 共识后放行 |
| `event_loop_pp_disagg_decode` | :364 | decode 引擎：`DecodePreallocQueue` 预分配 KV，`_pp_pd_get_prealloc_ids`/`_pp_pd_get_retract_ids`/`_pp_pd_get_decode_transferred_ids` 与 prefill 引擎同步"已传/可收/需回收"的请求 id |

`process_retract_queue`/`process_prealloc_queue`/`process_decode_transfer_queue`（:1437-1485）消费上述队列。PP 下 chunked 请求可跨微批存活（注释 :3272-3275 说明 `num_allocatable_reqs` 检查在 PP 下对 chunked_req 放宽，防止内存泄漏）。

### 与 vLLM V1 PP 对照

| 维度 | SGLang | vLLM V1 |
|---|---|---|
| PP 事件循环 | 每 stage 独立 `event_loop_pp`，async send + sync recv 驱动微批 | vLLM V1 调度集中单点，PP 主要体现为 runner 层 `next_decode_eligible_step` 步进约束 |
| 微批管理 | `mbs[pp_loop_size]` 环形矩阵 + `pp_async_batch_depth` 缓冲 | AsyncScheduler 用 `num_output_placeholders` 预占跨 PP 延迟的 token |
| 负载均衡 | 动态 chunk 尺寸（二次延迟模型拟合） | 无动态 chunk，依赖 `long_prefill_token_threshold` 限制 |
| 输出延迟释放 | `last_rank_comm_queue` + `launch_event` 围栏 | `last_sched_seq`/`processed_step_seq` 围栏释放块 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
