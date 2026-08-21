## 专家并行负载均衡（srt/eplb）· 映射与算法

本文覆盖 `srt/eplb/`（13 文件，含 `eplb_algorithms/`、`eplb_simulator/` 子包）。EPLB（Expert Parallel Load Balancing）在**服务运行期**按在线专家负载统计重排专家在 EP 组内的物理位置，与 `parallel_state` 的 MOE_EP 通信组配合。核心算法源自 DeepSeek [EPLB](https://github.com/deepseek-ai/EPLB)（`deepseek.py` 文件头注明直接复制）。重均衡流程与 LPLB 见 [eplb_part2.md](eplb_part2.md)。

### 模块职责

| 文件 | 职责 |
|---|---|
| `eplb_manager.py` | `EPLBManager`：重均衡调度器（协程入口），每 N 次 forward 触发一次 rebalance |
| `expert_distribution.py` | `ExpertDistributionRecorder`：统计各逻辑专家/物理槽被选中次数，产出利用率与 logical_count |
| `expert_location.py` | `ExpertLocationMetadata`：逻辑↔物理专家映射的权威数据结构与构造/广播/格式化 |
| `expert_location_updater.py` | `ExpertLocationUpdater`：rebalance 后 P2P 搬运专家权重到新位置 |
| `expert_location_dispatch.py` | `ExpertLocationDispatchInfo`：每层每 EP rank 的静态/动态/LP 分派表（冗余专家挑选） |
| `lplb_solver.py` | `LPLBSolver`：线性规划（LP）负载均衡分派，逐 batch 求解 log2phy 概率 |
| `eplb_algorithms/` | `deepseek.py`（balanced_packing + replicate_experts）、`deepseek_vec.py`（向量化版）、`elasticity_aware.py`（弹性 EP 感知） |
| `eplb_simulator/` | 离线仿真器（`reader.py` 读记录回放） |
| 关联 `srt/elastic_ep/` | 弹性 EP：`elastic_ep.py`（状态机）、`expert_backup_manager.py`/`expert_backup_client.py`（DRAM 备份权重） |

### ExpertLocationMetadata（expert_location.py:58）

EPLB 的核心数据结构，贯穿统计→求解→映射→搬运全流程：

| 字段 | 形状 | 含义 |
|---|---|---|
| `physical_to_logical_map` | (layers, num_physical_experts) | 每个物理槽对应的逻辑专家 id（GPU 上，另有 `_cpu` 副本） |
| `logical_to_all_physical_map` | (layers, num_logical_experts, X) | 每个逻辑专家的全部物理副本候选（-1 填充，X=max_copies） |
| `logical_to_all_physical_map_num_valid` | (layers, num_logical_experts) | 每个逻辑专家的有效副本数（>1 即存在冗余） |
| `logical_to_rank_dispatch_physical_map` | (layers, num_logical_experts) | `ep_dispatch_algorithm=="static"` 时本 EP rank 应选的物理专家 |
| `ep_size` | int | EP 组大小 |

派生关系：`num_physical_experts = num_logical_experts + ep_num_redundant_experts`；`num_local_physical_experts = num_physical_experts // ep_size`。弹性 EP 下经 `_compute_elastic_expert_layout`：`num_local = base // initial_ep_size`，物理数随 `effective_ep_size` 扩展（`--elastic-ep-initial-size` 定义不可变的 per-rank 存储布局）。

三种构造入口：

| 入口 | 用途 |
|---|---|
| `init_trivial` | 逻辑专家 i 对应物理专家 i（`--init-expert-location trivial`） |
| `init_by_mapping` | 直接给定 `physical_to_logical_map`（.pt/.json 加载或广播后重建） |
| `init_by_eplb` | 由 `logical_count` 统计量经 `eplb_algorithms.rebalance_experts` 求解新映射 |

`_compute_logical_to_all_physical_map`（`:543`）：由 physical→logical 反推每个逻辑专家的物理候选，再经 `_find_nearest_expert`（优先同 GPU > 同节点）把候选**坍缩为最近物理专家**（仅当 `moe_a2a_backend != "none"`，各 rank 独立选最近；无 a2a 时保留全候选列表，保证所有 EP rank 对同一 token 选同一物理专家，见 `ExpertLocationDispatchInfo.rank_invariant`）。`compute_logical_to_rank_dispatch_physical_map`（`:624`）为每个 EP rank 预计算静态分派，缺位用 `_fair_choices` 公平补选（seed=42）。`broadcast_global_expert_location_metadata` 从 rank 0 广播映射后各 rank 重建。

### 重均衡算法（eplb_algorithms/）

`__init__.py` 的 `compute_algorithm`：`--eplb-algorithm auto` 时，`num_groups % num_nodes == 0` 选 `deepseek_hierarchical`，否则 `deepseek`。弹性 EP 强制 `elasticity_aware`（server_args 校验）。

`deepseek.py` 三个原语：

| 原语 | 语义 |
|---|---|
| `balanced_packing` | 把 n 个带权对象均衡装入 m 个包，每包恰好 n/m 个对象且包总权重最均衡（贪心：按权重降序，每次放入当前最轻且未满的包） |
| `replicate_experts` | 把 num_log 个专家复制到 num_phy 个副本，最小化副本最大负载：逐副本贪心选择 `weight/logcnt` 最大者（给当前负载比最高的专家加分片） |
| `rebalance_experts_hierarchical` | 三级分层：① 组→节点（balanced_packing）；② 节点内冗余复制（replicate_experts）；③ 物理专家→GPU（balanced_packing） |

入口 `rebalance_experts`（`:171`）：`enable_hierarchical=False` 时退化为 `num_groups=1, num_nodes=1` 的全局版；最终输出 `phy2log`（新 physical_to_logical_map）、`log2phy`（logical_to_all_physical_map）、`logcnt`（副本数）。`deepseek_vec.py` 为逐层向量化（`tokens_per_expert` 逐层输入）；`elasticity_aware.py` 额外接收 `active_ranks`，仅把专家放入活跃 rank。

### 统计：ExpertDistributionRecorder（expert_distribution.py:78）

- 记录钩子：`on_select_experts`（topk_ids 按专家 `scatter_add_` 计数）、`on_deepep_dispatch_normal`/`on_deepep_dispatch_low_latency`（DeepEP 分派统计）。`expert_distribution_recorder_mode`：`stat`（循环缓冲，默认）/ `stat_approx`（DeepEP 近似）/ `per_pass` / `per_token`。
- 单次 forward 收集器把**本地物理计数**经 `_convert_local_to_global_physical_count` 展开为全局槽位；`_StatAccumulator.dump` 用 `physical_to_logical_map` 经 `scatter_add` 把物理计数折叠回 `logical_count`（(steps, layers, num_logical)），再 `dist.all_reduce(SUM)` 汇总全 EP 组。
- 利用率：`compute_gpu_physical_count`（einops 按 ep_size 折叠）→ `compute_utilization_rate = (mean+1e-5)/(max+1e-5)`；`_UtilizationRateAccumulatorMixin` 每 pass 末尾 `dist.reduce(dst=0, SUM)`，rank 0 维护 (10,100,1000) 三窗口历史（`_DequeCollection`）供重均衡阈值判断；可经 Prometheus 上报 `eplb_gpu_physical_count` 热力图（`SGLANG_EPLB_HEATMAP_COLLECTION_INTERVAL`）。
- 缓冲：`_CircularBuffer`（默认）或 `_InfiniteBuffer`（`buffer_size=-1`），`eplb_rebalance_num_iterations` 须 ≥ buffer_size 防陈旧数据。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
