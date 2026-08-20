## v1 内核资源管理：抢占、BlockPool、Encoder 缓存与批队列

本文说明 v1 内核的「资源紧张时的抢占回退」「KV 块池接口契约」「encoder 缓存调度协作」以及 `EngineCore` 的批队列（BatchQueue）与同步/事件机制。BlockPool 内部实现细节见 03 模块，本文侧重**组件契约与 step 链路的配合**。

### 抢占在 step 链路中的触发与协作

抢占发生在 `schedule()` 的 running 调度循环内（`vllm/v1/core/sched/scheduler.py`）：`kv_cache_manager.allocate_slots(...)` 返回 `None`（空闲块不足 `required_blocks`）即选受害者：

| 策略 | 受害者 | 回退动作 |
|---|---|---|
| `PRIORITY` | `max(running, key=(priority, arrival_time))`（priority 值最大者） | 若本步已调度：从 `scheduled_running_reqs` 移除、回退 `num_scheduled_tokens`/`token_budget`/`input_budget`、`req_to_new_blocks`、spec tokens、encoder compute budget |
| `FCFS` | `running.pop()`（队尾） | 无 |

`_preempt_request(request, timestamp, drop_stale_output)` 契约（请求须已移出 `running`）：

```
_free_request_blocks(request)          # KV 块归还块池
encoder_cache_manager.free(request)    # 释放 encoder 缓存引用
_inflight_prefills.discard(request)
status = PREEMPTED; num_computed_tokens = 0; spec_token_ids = []
num_preemptions += 1
waiting.prepend_request(request)       # 回 waiting 队首（FCFS 下最优先重调度）
reset_preempted_req_ids.add(request_id)  # 本步 reset_preempted_req_ids 上报
```

- `drop_stale_output`：async scheduling / KV connector 场景在途输出标记 `num_stale_output_tokens = num_in_flight_tokens`，步内逐步 drain，防止 token 乱序交付。
- 释放的块在 `free_blocks` 中分两类归还：无哈希块头插空闲队（LIFO 保 GPU 局部性），有哈希块尾插（LRU 淘汰序）。
- 重调度走 `WAITING → RUNNING`，`num_computed_tokens` 从 0 重新 prefill（前缀缓存命中可减少重算）。
- 极端情况：受害者即待调度请求本身（running 空且块仍不足）→ 无法调度，`break`。

### BlockPool 与 KVCacheManager 的接口契约（block_pool.py）

`BlockPool` 是 KV 块元数据池（`KVCacheBlock` 不持 GPU 张量），`KVCacheManager`/协调器共享单一实例：

| 方法 | 调用方/时机 | 契约 |
|---|---|---|
| `get_new_blocks(num_blocks)` | `allocate_slots` 三阶段末尾 | 空闲队头取块；`enable_caching` 时先 `_maybe_evict_cached_block`（清哈希、发 `BlockRemoved`），`ref_cnt=1`；不足抛 `ValueError` |
| `touch(blocks)` | 前缀命中（`find_longest_cache_hit` 后，coordinator 两阶段分配） | `ref_cnt 0→1` 时移出空闲队列，再 `ref_cnt += 1`（命中块被多请求共享） |
| `free_blocks(ordered_blocks)` | `_free_request_blocks` / `_drain_deferred_frees` | 按 eviction 优先级逆序归还，`ref_cnt-=1` |
| `cache_full_blocks` / `cache_partial_block` | 单类型管理器写满块后 | 登记链式前缀哈希（`BlockHashToBlockMap`）；`block_mask` 跳过 SWA/Mamba 稀疏组；partial 条目支持块内 `hash_block_size` 边界 |
| `evict_blocks(block_ids)` | KV connector 外部逐出请求 | 仅从前缀哈希表移除，不改池内占用 |
| `reset_prefix_cache()` | `scheduler.reset_prefix_cache` | 仅所有块空闲（除 null 块）时成功 |
| `take_events()` | `kv_cache_manager.take_events` → scheduler | 原子取走 `kv_event_queue`（`BlockStored`/`BlockRemoved`/`AllBlocksCleared`） |

- `null_block`（`block_id=0`，`is_null=True`）恒占位，不参与 ref 计数与缓存。
- `get_usage()`：`1 - free/(num_gpu_blocks-1)`，经 `kv_cache_manager.usage` 进 `SchedulerStats.kv_cache_usage`。
- 新块 ID 经 `take_new_block_ids` 交给 worker 事前清零（`new_block_ids_to_zero`，防 stale NaN 进注意力）。
- `defer_block_free`（async scheduling）：块释放经 `last_sched_seq`/`processed_step_seq` 围栏延迟到 `update_from_output` 中 `_drain_deferred_frees`，保证在途前向不会写已释放块。

### EncoderCacheManager 与调度协作（encoder_cache_manager.py）

多模态请求的 encoder 输出缓存，按 `mm_hash` 键、以「encoder embedding 数」计容量（忽略中间 break/text token）：

| 方法 | 调度器调用点 | 契约 |
|---|---|---|
| `check_and_update_cache(request, input_id)` | `_try_schedule_encoder_inputs` 命中判定 | 命中则登记引用并返回 True；原零引用条目从 `freeable` 回收 |
| `can_allocate(request, input_id, encoder_compute_budget, num_embeds_to_schedule)` | 调度前容量探测 | 空间不足时从 `freeable` **FIFO 驱逐**零引用最旧条目（`freed` 记录），仍不足返回 False；不真正分配 |
| `allocate(request, input_id)` | `schedule()` 调度成功分支 | 记账 `num_free_slots -= num_embeds`；调用前提是 `can_allocate` 已通过 |
| `free(request)` | `_preempt_request` / `_free_encoder_inputs`（请求结束） | 逐 input 释放引用；引用集空则条目转 `freeable`（物理内存保留至驱逐） |
| `get_freed_mm_hashes()` | scheduler 构造 `SchedulerOutput.free_encoder_mm_hashes` | 返回并清空 `freed`（同一调度 pass 内被重新分配的不返回，保 worker 侧张量）；worker 依此释放 encoder 输出张量 |

- 预算由 `compute_mm_encoder_budget` 计算：`encoder_compute_budget = max(max_num_encoder_input_tokens, 单条 mm 最大 token)`；`encoder_cache_size` 同理。
- `EncoderDecoderCacheManager`：encoder-decoder 过渡实现，不缓存仅记账；`get_freed_mm_hashes` 以「上步 allocated 本步 to_free」的双缓冲在模型执行后释放。
- 自定义管理器经 `ec_manager_config.get_encoder_cache_manager_obj()` 注入（`create_manager(cache_size, vllm_config)` 工厂）；`get_manager_metadata` 挂入 `SchedulerOutput.ec_manager_metadata`。

### BatchQueue 与 step_with_batch_queue（engine/core.py）

`max_concurrent_batches > 1` 时启用，`self.batch_queue = deque(maxlen=size)`，元组 `(sample_future, scheduler_output, exec_future)`，让调度/前向/采样异步重叠（PP 消除 pipeline bubble）：

```
1. 队列未满 → 尝试 schedule 新批并 execute_model(non_block=True)
   - 无 pending_structured_output_tokens：立即 sample_tokens 入队（成对 Future）
   - 有 pending：存 deferred_scheduler_output，待上步输出到位再采样
   - 池化/无调度：future = exec_future
   - 队列未满且有工作 → 直接返回 None（不阻塞）
2. 队列已满/无新调度 → pop 队首 future.result()（阻塞至最先完成批）
3. update_from_output + _attach_iteration_details
4. deferred 批：take_draft_token_ids → update_draft_token_ids_in_output（过滤非法草稿）
   → get_grammar_bitmask → sample_tokens 入队
```

- `_process_aborts_queue()` 在 `update_from_output` 前批量处理 ABORT（幂等）。
- `post_step(model_executed)`：非 async 调度时 `take_draft_token_ids` → `scheduler.update_draft_token_ids`。

### 同步/事件机制

| 机制 | 位置 | 说明 |
|---|---|---|
| `EngineCoreEvent`（`QUEUED`/`SCHEDULED`/`PREEMPTED`） | `v1/request.py` | 随 `EngineCoreOutput.events` 下发（单调时间戳），前端算排队/调度/首 token 时延 |
| `reset_preempted_req_ids` | scheduler | 本步抢占集合，经 `SchedulerOutput.preempted_req_ids` 通知 worker 丢弃在途状态（v2 runner） |
| KV 事件队列 | block_pool → kv_cache_manager → `EventPublisherFactory` | `BlockStored`/`BlockRemoved`/`AllBlocksCleared` 供 KV connector / gateway 消费 |
| `sleep(level)` / `wake_up` | EngineCore | 0 仅停调度；1 卸载权重、丢 KV；2 释放全部 GPU 内存 |
| `shutdown_timeout` | EngineCore | 0=立即 abort，>0=drain 模式 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
