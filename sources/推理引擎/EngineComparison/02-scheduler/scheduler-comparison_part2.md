## 02-scheduler 调度器对比：策略、chunked prefill 与抢占

接 `scheduler-comparison.md`（调度模型与批构建）。本节聚焦四组核心差异：调度策略、chunked prefill、抢占/淘汰、与 KV 缓存的衔接。事实基准：vLLM `scheduler.py`/`request_queue.py`、SGLang `schedule_policy.py`/`schedule_batch.py`。

### 一、调度策略对比

| 维度 | vLLM V1 | SGLang |
|---|---|---|
| 策略载体 | `Request.__lt__` 比较键 `(priority, arrival_time, request_id)` + `create_request_queue` 工厂 | `SchedulePolicy`（`schedule_policy.py:216`）+ 每轮 `calc_priority`（:237）原地重排 `waiting_queue` |
| 策略集 | **2 种**：`FCFS`（`FCFSRequestQueue`，deque）与 `PRIORITY`（`PriorityRequestQueue`，heapq） | **6+1 种**：`fcfs`、`lpm`、`dfs-weight`、`lof`、`random`、`routing-key` + `priority` 参数（`server_args.py:839-854`） |
| cache 感知 | 无独立 cache 策略；调度时逐请求 `get_computed_blocks` | `CacheAwarePolicy`（`lpm`/`dfs-weight`）先做 `tree_cache.match_prefix` 再排序；`CacheAgnosticPolicy`（`fcfs`/`lof`/`random`/`routing-key`）不感知 |
| 排序键示例 | 同 priority 按到达时间、再按 request_id（priority 值越小越先） | `fcfs`=到达时间；`lpm`=`-num_matched_prefix_tokens`；`dfs-weight`=radix 树上按子树请求数 DFS 序；`lof`=`-max_new_tokens`；`random`=洗牌；`routing-key`=running 批内 key 频率降序 |
| 降级/保护 | 无 | `tree_cache.disable` 时 cache-aware 自动降级 fcfs；`waiting_queue>128` 时 LPM 退回 fcfs（`_determine_active_policy` :290）；`priority_sign` 控制 priority 方向 |
| 默认值 | FCFS（priority 均为 0） | `fcfs` |
| 批内复用 | cached 请求走 `CachedRequestData` 增量 | `_compute_prefix_matches`（:321）批内前缀缓存：共享前缀请求临时降权，兄弟先跑把公共前缀写入 radix 树下轮批量命中 |

### 二、chunked prefill 对比

| 维度 | vLLM V1 | SGLang |
|---|---|---|
| 机制形态 | **无独立 chunk 概念**：`max_num_scheduled_tokens`/`long_prefill_token_threshold`（>0 时限制单段 prefill 长度，`scheduler.py:563`）作为 token 预算自然截断长 prefill，`is_prefill_chunk` 仅作标记 | **显式 chunk 机制**：`chunked_prefill_size` 参数 + `chunked_req` 状态 + `add_chunked_req` 续跑（`schedule_policy.py:1004`） |
| 默认 | 连续批处理默认开启式（预算内分多步） | `chunked_prefill_size` 默认 `None` → 按 GPU 内存自动设 2048/4096/8192/16384（`server_args.py:4867+`）；`-1` 表示整段单次 forward 不切分 |
| chunk 边界 | 预算（token_budget/input_budget）+ `long_prefill_token_threshold` | `chunked_prefill_size`，`truncation_align_size` 强制对齐；`enable_dynamic_chunking`（PP）用 `predict_next_chunk_size`（:3295） |
| 中途 KV | 无需特殊处理（自然分步，KV 随步分配） | chunk 未完成时 `stash_chunked_request`（:3100）缓存已算 chunk 的 KV，下一轮 `add_chunked_req` 继续 |
| 禁用条件 | — | `chunked_prefill_size≤0` 或 transformers 后端多模态模型自动禁用（`scheduler.py:1160-1179`）；DP>1 时按 `dp_size` 分摊 |
| 与 decode 交替 | 同批混跑 | `prefill_decode_interval`：prefill 后连续 N 轮只跑 decode；`is_mixed_chunk` 时可并入 decode 请求 |

### 三、抢占/淘汰对比

| 机制 | vLLM V1 | SGLang |
|---|---|---|
| 触发点 | `allocate_slots` 返回 `None`（空闲 KV 块不足，`scheduler.py` 抢占逻辑）；`reset_prefix_cache` 强制全量抢占 | ① prefill 准入时 batch 满 + priority 模式 → `preempt_to_schedule`（`schedule_policy.py:1437`）；② decode 前 `check_decode_mem` 失败 → `retract_decode`（`schedule_batch.py:2819`）；③ decode 内存检查先 `evict_from_tree_cache`（:2816）回收 radix 节点 |
| 受害者选择 | `PRIORITY`：`max(running, key=(priority, arrival_time))`（priority 值最大者）；`FCFS`：`running.pop()` 队尾 | `preempt_to_schedule`：running 中 `(priority*(-priority_sign), -wait_queue_entry_time)` 升序（低优先先被抢），且需 `priority_diff > priority_scheduling_preemption_threshold` 且被抢 token 总和 ≥ 需求缺口；`retract_decode`：按 priority 或 `(output_len, -input_len)`（:2883）从最不受保护者开始 |
| 抢占后状态 | `status=PREEMPTED`、`num_computed_tokens=0`、清空 spec tokens、`num_preemptions+=1`、放回 `waiting` 队首（`_preempt_request` :1336）；AsyncScheduler 下在途输出标记 stale | 释放资源后请求放回 `waiting_queue`（`is_retracted=True`）或进 `preempt_list` 重入队；仅剩 1 个仍放不下则 `FINISH_ABORT` |
| 重算策略 | **全量重算**：V1 无 swap-to-CPU，`num_computed_tokens=0` 从头跑（前缀缓存命中除外） | 无 CPU swap；被抢请求重新 `match_prefix`，radix 树中已缓存前缀仍可复用 |
| 抢占频率抑制 | `watermark` 预留空闲块比例；`PauseState.PAUSED_NEW/ALL` | `token_usage_low_watermark`、`MinFreeSlotsDelayer`（`min_free_slots_delay`）、`max_delay_passes` 封顶 |
| 补充 | — | `_abort_on_waiting_timeout`（`SGLANG_REQ_WAITING_TIMEOUT`）/`_abort_on_running_timeout` 超时中止 |

> 关键差异 ③：vLLM 抢占是**被动内存反应**——KV 块不足才抢占，回退到队首全量重算；SGLang 抢占是**三路组合**——优先级差驱动的主动腾位（`preempt_to_schedule`）+ decode 内存守卫（`retract_decode`）+ radix 节点优先回收（`evict_from_tree_cache`），且被抢请求能靠 radix 缓存免重算已共享前缀。

### 四、与 KV 缓存衔接点（详细见 03-kvcache）

| 衔接点 | vLLM V1 | SGLang |
|---|---|---|
| 前缀查询 | `get_computed_blocks`（上限 `num_tokens-1`，末 token 重算取 logits），`KVCacheManager` 本地命中 + KV connector 外部命中可异步加载 | `policy.calc_priority` → `tree_cache.match_prefix` 同步内嵌，回填 `prefix_indices`/`last_node`/`host_hit_length`；`init_load_back` 回载 host 命中 KV |
| 块分配 | `KVCacheManager.allocate_slots` 三阶段布局（comp/外部命中/new/lookahead），`watermark` 预留 | `req_to_token_pool`/`token_to_kv_pool_allocator`（`kv_cache_builder` 产出），`add_one_req` 内 `inc_lock_ref(last_node)` 锁节点防驱逐 |
| 共享锁 | ref_cnt + `FreeKVCacheBlockQueue` | `inc_lock_ref`/`dec_lock_ref` + radix 树引用计数 |
| 释放路径 | `finish_requests` 释放块；AsyncScheduler 延迟释放围栏 | decode OOM 先 `evict_from_tree_cache` 回收可驱逐节点；`maybe_cache_unfinished_req` 缓存未完成 chunk |
| 事件 | `BlockStored`/`BlockRemoved` 事件经 `kv_event_publisher` 发布 | radix 树由 `batch_result_processor` 按 token 插入/更新 |

### 五、速查表

| 对比项 | vLLM V1 | SGLang |
|---|---|---|
| 阶段模型 | 隐式连续（num_computed_tokens 追赶） | 显式 EXTEND/DECODE 两相 |
| 策略数 | 2（fcfs/priority） | 6+1（fcfs/lpm/dfs-weight/lof/random/routing-key+priority） |
| 默认策略 | fcfs | fcfs |
| cache 感知策略 | 无（调度时逐请求查询） | 有（lpm/dfs-weight 先排序后调度） |
| chunked prefill | 预算天然截断 | 显式 `chunked_prefill_size` + `chunked_req` 续跑 |
| 抢占 | 内存不足被动抢占、全量重算 | 优先级主动腾位 + decode 内存守卫 + radix 优先回收 |
| 前缀缓存 | `KVCacheManager`（可异步 connector） | `RadixCache`（调度时同步内嵌） |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
