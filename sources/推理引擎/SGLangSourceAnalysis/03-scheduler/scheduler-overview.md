## Scheduler 调度器：事件循环与批构建（part 1）

本文基于 `sglang/srt/managers/scheduler.py`，说明 Scheduler 主类与调度主循环。SGLang 采用**单进程连续批处理**：一个 `Scheduler` 实例对应一个 TP/DP 并行组的首 rank，调度、KV 分配、前向驱动都在同一个循环内完成（与 vLLM 的 `EngineCore` + `Scheduler` 双层结构不同）。

### Scheduler 主类与 mixin

`Scheduler`（`scheduler.py:383`）继承多个 mixin，按功能切片：

| Mixin | 文件 | 职责 |
|---|---|---|
| `SchedulerPPMixin` | `scheduler_pp_mixin.py` | PP 事件循环、动态 chunk 预测（见 scheduler-pp-mixin.md） |
| `SchedulerDisaggregationPrefillMixin` / `DecodeMixin` | `disaggregation/prefill.py` / `decode.py` | PD 分离的 prefill/decode 引擎循环 |
| `SchedulerDllmMixin` | `dllm/mixin/scheduler.py` | 扩散 LLM 调度 |
| `SchedulerMlxOverlapMixin` | `scheduler.py:338` | MLX 设备 overlap |

`__init__`（:393）是纯编排器，按序调用 `init_*`：`init_model_config` → `init_model_worker` → `kv_cache_builder.build_kv_cache`（产出 `tree_cache`/`req_to_token_pool`/`token_to_kv_pool_allocator`）→ `init_running_status` → `init_chunked_prefill` → `init_schedule_policy` → `init_disaggregation` → `init_overlap` → `init_request_receiver` 等。关键状态：

```python
self.waiting_queue: List[Req] = []                    # 等待队列（策略排序后取前 N 个）
self.running_batch: ScheduleBatch = ScheduleBatch(reqs=[], batch_is_full=False)
self.last_batch: Optional[ScheduleBatch] = None       # 上一前向批（overlap 用）
self.chunked_req: Optional[Req] = None                # 进行中的 chunked prefill 请求
```

### 事件循环分发（dispatch_event_loop, scheduler.py:4997）

```python
def dispatch_event_loop(scheduler: Scheduler):
    if disaggregation_mode == NULL:
        scheduler.event_loop_pdmux()          # PD 复用
        scheduler.event_loop_pp()             # PP > 1
        scheduler.event_loop_overlap_mlx()    # MLX 用 mx.async_eval 重叠
        scheduler.event_loop_overlap()        # 默认：CPU 调度与 GPU 前向重叠
        scheduler.event_loop_normal()         # --disable-overlap-schedule
    elif mode == PREFILL:   event_loop_pp_disagg_prefill() / event_loop_overlap_disagg_prefill() / ...
    elif mode == DECODE:    event_loop_pp_disagg_decode() / event_loop_overlap_disagg_decode() / ...
```

`run_event_loop`（:1691）先创建独立 `schedule_stream`（与 `forward_stream` 去别名），在 `StreamContext` 下启动循环；WAR 屏障（`_apply_war_barrier` :1729）保证调度器下一写落在前向共享读之后。

### event_loop_normal（:1743）——非 overlap 基准循环

```python
while True:
    recv_reqs = self.request_receiver.recv_requests()   # 1) 收请求
    self.process_input_requests(recv_reqs)              # 2) 构造 Req 入 waiting_queue / abort
    plan = self.get_next_batch_to_run(running_batch, last_batch)  # 3) 决策本步批
    self.running_batch = plan.running_batch
    batch = plan.batch_to_run
    if batch:
        result = self.run_batch(batch)                  # 4) 前向（含采样）
        self.process_batch_result(batch, result)        # 5) 结果处理（更新 KV、判定结束、流式输出）
    else:
        self.on_idle()                                  # 空闲自检
    self.last_batch = batch
```

### event_loop_overlap（:1778）——双缓冲重叠

`result_queue` 暂存 `(batch.copy(), batch_result)`：`run_batch` 把前向发到 `forward_stream` 后立即返回（异步），`process_batch_result` 在下轮迭代 CPU 侧执行，与 GPU 前向并行：

```python
batch_result = self.run_batch(batch)
self._apply_war_barrier()                      # WAR：调度器下一写须等前向读完共享缓冲
self.result_queue.append((batch.copy(), batch_result))
...
pop_and_process()                              # popleft 处理上一步结果
if self.is_generation:
    self.launch_batch_sample_if_needed(batch_result, batch)   # 采样依赖上批结果（grammar）
```

`is_disable_overlap_for_batch`（:1852）：两个连续 prefill 批不重叠（`SGLANG_DISABLE_CONSECUTIVE_PREFILL_OVERLAP`）保 TTFT；spec + grammar 场景强制同步。

### get_next_batch_to_run（:3064）——每步决策入口

1. `process_pending_chunked_abort`（安全中止在途 chunk）、`_abort_on_waiting_timeout`（`SGLANG_REQ_WAITING_TIMEOUT`）、`_abort_on_running_timeout`。
2. **合并上一 prefill 批到 running_batch**：`chunked_req` 先 `stash_chunked_request`（缓存未完成 chunk 的 KV，:3100），再 `filter_batch` 剔除已结束请求、`merge_batch` 合并（:3136）。prefill-only 批直接 `filter_batch` 以免负载统计失真。
3. **选本步批**：
   - 有 `chunked_req`/prefill 待调度 → `get_new_batch_prefill` 产 prefill 批；`_should_defer_prefill`（:1200，`prefill_decode_interval` 计数）返回 True 时跳过 prefill；
   - 否则 decode：`update_running_batch(running_batch)` 产生 decode 批；`is_prefill_only` 批跳过 decode。
4. `dp_attn_adapter.maybe_prepare_mlp_sync_batch` 保证 DP 各 rank 前向模式一致；`_arm_prefill_decode_interval` 记录 prefill 后的 decode 间隔。
5. 返回 `NextBatchPlan(batch_to_run, running_batch)`（`schedule_batch.py:3423`）。

`chunked_req` 移出批合并（`chunked_req_to_exclude`，:3090）避免与 running 批重复；PP 下 `last_batch.chunked_req` 同样剔除（:3121）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
