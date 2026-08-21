## 专家并行负载均衡（EPLB）对比（vLLM vs SGLang）

EPLB（Expert Parallel Load Balancing）在服务运行期按在线专家负载统计重排专家在 EP 组内的物理位置。事实基准：vLLM `vllm/distributed/eplb/`（eplb_utils.py / eplb_state.py / rebalance_execute.py / async_worker.py / policy/，KB 快照仅载 `eplb/eplb_communicator.py`，源码为本节权威）与 SGLang `sglang/srt/eplb/`（13 文件，KB 15-distributed eplb_part1/_part2）。两者算法均源自 DeepSeek EPLB。

### 一、定位与架构

| 维度 | vLLM | SGLang |
|---|---|---|
| 定位 | `parallel_state._EPLB` 独立通信组（MoE 且 `enable_eplb`）+ `distributed/eplb/` 模块 | 无通信组；独立 `srt/eplb/` 模块（EPLBManager 协程）+ `MOE_EP` 通信组 |
| 算法来源 | `policy/default.py`：`DefaultEplbPolicy` "adapted from DeepSeek EPLB" | `eplb_algorithms/deepseek.py` 文件头注明**直接复制** DeepSeek EPLB |
| 核心文件 | `eplb_state.py`（EplbState/EplbModelState，1356 行）、`rebalance_execute.py`（710 行）、`async_worker.py`、`policy/{abstract,default}.py` | `eplb_manager.py`、`expert_distribution.py`、`expert_location.py`、`expert_location_updater.py`、`expert_location_dispatch.py`、`lplb_solver.py`、`eplb_algorithms/` |
| 触发模型 | 滑动窗口负载 + 不平衡阈值，可选 **async 线程**（`eplb_config.use_async`） | 每 N 次 forward 触发（`eplb_rebalance_num_iterations`），协程 `on_forward_pass_end` 调 `next()` |
| 数据面 | `ExpertDistributionRecorder`（KB）之外：`EplbState.expert_load_window (window_size, layers, num_physical_experts)`，naive a2a 时负载乘 dp_size | `ExpertDistributionRecorder`：topk/DeepEP 分派计数，`stat`/`stat_approx`/`per_pass`/`per_token` 模式，利用率窗口 (10,100,1000) |

### 二、核心算法对照

| 原语 | vLLM `DefaultEplbPolicy` | SGLang `deepseek.py` |
|---|---|---|
| balanced_packing | 带权对象均衡装包（每包 n/m 个，贪心取当前最轻包） | 同（逐层向量化在 `deepseek_vec.py`） |
| replicate_experts | 逻辑专家复制到物理副本，最小化副本最大负载（贪心取 `weight/logcnt` 最大者） | 同 |
| rebalance_experts_hierarchical | 三级：① 组→节点（packing）② 节点内冗余复制 ③ 物理专家→GPU（packing）；`num_groups % num_nodes == 0` 时走分层否则全局版 | 同三原语三级分层；`compute_algorithm`：`num_groups % num_nodes == 0` → deepseek_hierarchical，否则 deepseek |
| 附加后处理 | `preserve_intragpu_slots`：GPU 数/槽位不变时保留原槽位，避免同 GPU 内专家搬动引起的无谓权重拷贝（旧映射传入 `rebalance_experts`） | 无等价后处理；依赖 `_find_nearest_expert` 坍缩物理候选 |
| 弹性感知 | 无 | `elasticity_aware.py` 接收 `active_ranks`，仅把专家放入活跃 rank（弹性 EP 强制此算法） |

### 三、重均衡执行对照

| 环节 | vLLM | SGLang |
|---|---|---|
| 负载统计 | `expert_load_window` 滑动窗口（各 EP rank 独立步进），`expert_load_window_imbalance_threshold` 超阈值触发重排；async 模式由后台线程执行 | `ExpertDistributionRecorder.dump` 把物理计数经 `physical_to_logical_map` 折叠为 `logical_count` 后 `dist.all_reduce(SUM)` 汇总；利用率 `(mean+1e-5)/(max+1e-5)`，超 `eplb_min_rebalancing_utilization_threshold`（默认 1.0）则跳过 |
| 重排求解 | `DefaultEplbPolicy.rebalance_experts(weight, num_replicas, num_groups, num_nodes, num_ranks, old_global_expert_indices)` → 新 phy2log | `init_by_eplb` 经 `rebalance_experts` 求解 phy2log/log2phy/logcnt；普通模式各 rank 独立算，弹性 scale 后 rank 0 算再 broadcast |
| 权重搬运 | `rebalance_execute.py`：计算 send/recv map → `move_to_buffer` 拷入缓冲 → 经 `EplbCommunicator` P2P 发送（`TransferMetadata`/`AsyncEplbLayerResult`），逐层异步 | `ExpertLocationUpdater.update`：比较新旧映射，P2P 张量传输（`torch.distributed.P2POp`），逐 chunk（`eplb_rebalance_layers_per_chunk`）更新 + 每块 `dist.barrier()`；canary 模式（`SGLANG_EXPERT_LOCATION_UPDATER_CANARY`）校验迁移正确性 |
| 故障恢复 | 无 | 弹性 EP 缺专家时经 `expert_backup_client.update_weights`（DRAM 备份）或 `update_weights_from_disk`（磁盘重载，`weight_name_filter` 局部恢复） |

### 四、分派算法对照

| 算法 | vLLM | SGLang |
|---|---|---|
| static | 预计算物理专家选择（KB 快照语义） | `logical_to_rank_dispatch_physical_map` 每 rank 确定性选择（`_fair_choices` 补选，seed=42） |
| dynamic | — | 运行期从候选副本动态挑选 |
| fake | — | router_logits 填 uniform(5,10)（仿真） |
| lp | 无 | `LPLBSolver` 线性规划：离线建 GPU 分配矩阵 B1/B2，在线每 rank 统计 token → all-reduce 全局一致 → 各 rank 独立解同 LP 得 `log2phy_prob`；仅 DeepSeek-v2 家族等 7 架构 |

### 五、总对比

| 维度 | vLLM | SGLang |
|---|---|---|
| 在线重均衡 | 有（滑动窗口 + 阈值 + async 线程） | 有（周期协程 + 分块更新 + 弹性感知） |
| 算法深度 | DeepSeek 三原语 + preserve_intragpu_slots | DeepSeek 三原语 + deepseek_vec + elasticity_aware + LPLB |
| 弹性 EP 协同 | 无内建（弹性 EP 为 Stateless 通信组，另文） | `srt/elastic_ep/` 状态机（scale/recover）+ DRAM 备份 + 磁盘重载 |
| 专家副本 | replicate 生成冗余物理专家 | 同；`logical_to_all_physical_map` 多副本 + rank_invariant 保证无 a2a 时选一致 |
| 运维 | `NCCL_MAX_CTAS=8` 规避与 DeepGEMM Mega MoE cooperative launch 死锁（`eplb_utils.override_envs_for_eplb`） | Prometheus 热力图 `eplb_gpu_physical_count`（`SGLANG_EPLB_HEATMAP_COLLECTION_INTERVAL`） |
| 结论 | "简单"是相对早期快照：源码现已有 DeepSeek 算法与 async 重均衡，但**仍无 LPLB、无 DeepEP 分派统计、无弹性 EP 在线重均衡与 DRAM 备份** | 完整实现 DeepSeek 生产级 EPLB 全链路（算法 + 统计 + 搬运 + 弹性 + LP 分派） |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
