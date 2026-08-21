## 专家并行负载均衡（srt/eplb）· 重均衡流程与 LPLB

映射数据结构与算法见 [eplb_part1.md](eplb_part1.md)。本文覆盖 `EPLBManager` 重均衡流程、权重搬运、LPLBSolver、弹性 EP 与 vLLM 对照。

### 重均衡流程（eplb_manager.py）

`EPLBManager` 是一个**协程生成器**（`on_forward_pass_end` 每次前向调用 `next()`）：

```
_entrypoint(): for _ in range(eplb_rebalance_num_iterations): yield
                yield from self.rebalance()
```

`rebalance()` 步骤：
1. 弹性 EP 状态下校验 `has_scaled` 与 `scale_phase`（`pending_ep_size` 非空或扩缩容进行中不重均衡）。
2. `dump_record(output_mode="object")` 取 `logical_count` 与 `average_utilization_rate_over_window`。
3. `_check_rebalance_needed`：平均利用率 > `eplb_min_rebalancing_utilization_threshold`（默认 1.0）则跳过。
4. `_compute_expert_location_metadata`：普通模式各 rank 独立 `init_by_eplb`；弹性 scale 后由 rank 0 计算（`use_flat_topology=True`，避免进程本地拓扑影响展开世界）再 `dist.broadcast(physical_to_logical_map, src=0)`。
5. `_compute_update_layer_ids_chunks`：按 `eplb_rebalance_layers_per_chunk` 分块逐层更新（每块间 yield 一次让出），避免一次搬运阻塞服务。
6. `update_expert_location_with_recovery`（`eplb_manager.py:302`）：调 `ExpertLocationUpdater.update` P2P 搬权重；若弹性 EP 下缺专家（rank 故障），经 `expert_backup_client.update_weights`（DRAM 备份）或 `update_weights_from_disk`（磁盘重载，`weight_name_filter` 可只载缺失专家）；`ep_dispatch_algorithm=="lp"` 时重初始化 LPLB solver。
7. 更新全局 metadata 后记日志（`format_expert_location_layout` / `format_expert_location_layout_diff` 可对比搬迁量）。

`disable_rebalance(reason)` / `enable_rebalance()` 可动态开关，重置生成器。分块更新与弹性 scale 下每块后 `dist.barrier()` 保证无搬迁 rank 也先装上该块再恢复 NIXL。

### 权重搬运（expert_location_updater.py）

`update` 比较旧/新 `physical_to_logical_map`，把需要迁出的专家权重经 **P2P 张量传输**（`torch.distributed.P2POp`）发给新归属 rank，返回因 rank 故障缺失的逻辑专家集合。可选 canary 模式（`SGLANG_EXPERT_LOCATION_UPDATER_CANARY`）用 canary 张量校验迁移正确性（先传旧映射的 canary 再对比）。每层权重经 `routed_experts_weights_of_layer` 字典索引，逐 chunk 更新并 `empty_cache()`。

### 分派算法（expert_location_dispatch.py + lplb_solver.py）

`ExpertLocationDispatchInfo`（`expert_location_dispatch.py:25`）为每层提供分派表，`ep_dispatch_algorithm ∈ {static, dynamic, fake, lp}`：

| 算法 | 行为 |
|---|---|
| static | 用 `logical_to_rank_dispatch_physical_map` 预计算每 rank 的确定性选择 |
| dynamic | 运行期从候选副本动态挑选 |
| fake | `transform_select_experts_inputs` 把 router_logits 填成 uniform(5,10)（仿真用） |
| lp | `LPLBSolver` 线性规划求解 |

**LPLBSolver**（`lplb_solver.py:78`）：`--ep-dispatch-algorithm lp` 时启用。**离线构造**：由 phy2log/log2phy 区分单副本（`log_single`/`phy_single`）与冗余副本（`log_replicated`/`phy_replicated`），构建 GPU 分配矩阵 B1/B2（假设每 rank 持有连续 `num_phy//num_gpus` 块）。**在线求解**：每个 EP rank 统计本地 token 数 → **all-reduce 得全局一致计数** → 各 rank 独立解同一 LP 得 `log2phy_prob`（无需 broadcast）。仅 DeepSeek-v2 家族等 7 种架构支持（`_LPLB_SUPPORTED_MODEL_ARCHS`）——空 topk rank 也必须参与 solver all-reduce，否则 DP-attention 下死锁。

### 弹性 EP（srt/elastic_ep/，简要）

`ElasticEPStateManager` 单例维护 `active_ranks` 掩码（capacity=`max_ep_size`）与缩放状态机：`request_scale`→`begin_scale`→`mark_joining`→`mark_configuring_data_plane`→`mark_syncing_new_world`→`commit_scale`/`fail_scale`。`ep_join_mode`：`recover`（故障后重入既有槽位，`recovered_rank=True`，PG 用 `max_world_size` 预留）/ `scale`（`ep_join_rank_offset` 偏移后作为新 rank 加入，要求 `--node-rank 1`）。scale 组经 `register_scale_cohort`/`get_scale_cohort_target`（TCPStore）协调目标规模。backup 特性把专家权重驻留 DRAM，`expert_backup_client.update_weights` 按 `weight_name_filter` 局部恢复，避免全量重载。

### 与 vLLM 对照

| 维度 | vLLM | SGLang |
|---|---|---|
| EPLB 定位 | `_EPLB` 独立通信组（parallel_state 内），专家静态放置 | 独立 `srt/eplb/` 模块，**在线周期重均衡**（每 N 次 forward，`--enable-eplb`） |
| 负载来源 | 无在线统计（静态配置） | `ExpertDistributionRecorder` 实时统计 topk/DeepEP 分派计数，`dist.reduce`/`all_reduce` 汇总 |
| 算法 | 无（专家固定，冗余专家静态分派） | DeepSeek EPLB（packing+replicate）分层算法 + `elasticity_aware`（弹性感知）+ `deepseek_vec`（向量化）+ LPLB（线性规划分派） |
| 权重搬迁 | 不搬（启动时一次性放置） | `ExpertLocationUpdater` 运行期 P2P 搬运，支持分块/DRAM 备份/故障恢复 |
| 弹性扩展 | 无 | `elastic_ep/` 支持 scale-up/recover，nixl/mooncake 数据面 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
