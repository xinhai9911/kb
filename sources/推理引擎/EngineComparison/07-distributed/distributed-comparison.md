## 分布式并行：并行维度与初始化对比（vLLM vs SGLang）

本模块对比两大引擎的**并行组建模**与**分布式初始化**。事实基准：vLLM `vllm/distributed/parallel_state.py`（KB 08-distributed）与 SGLang `sglang/srt/distributed/parallel_state.py`（KB 15-distributed，文件头标注 "Adapted from vLLM v0.6.4.post1"）。通信对比见 [_part2](distributed-comparison_part2.md)，专家并行负载均衡见 [eplb-comparison.md](eplb-comparison.md)。

### 一、并行维度总览

| 维度 | vLLM | SGLang |
|---|---|---|
| 并行组数 | 9（world/inner_dp_world/TP/PCP/PP/DP/DCP/EP/EPLB） | 11（world/TP/PDMUX-TP/DCP/ATTN_CP/ATTN_CP_OVERLAP/ATTN_TP/MOE_DP/MOE_EP/MOE_TP/PP） |
| TP 张量并行 | `_TP`（总是，含 mq_broadcaster） | `_TP`（总是，含 mq_broadcaster） |
| PP 流水并行 | `_PP`（总是） | `_PP`（总是，禁用 CustomAllreduce） |
| DP 数据并行 | `_DP`（总是） | 无独立 DP 组：数据维度隐含在 TP/PP 布局与 `_MOE_DP`/`_ATTN_*` 派生中 |
| CP 上下文并行 | 概念维度：拆为 `_PCP`（prefill）+ `_DCP`（decode），无单一 CP 组 | `_ATTN_CP`（`attn_cp_size==tp_size` 时别名 `_TP`）；另有 `_DCP` |
| PCP | `_PCP`（prefill context parallel，可独立于 DCP） | 无 PCP 维度 |
| DCP | `_DCP`（decode context parallel，TP 组内按 dcp_size 切） | `_DCP`（`decode_context_parallel_size>1`） |
| EP 专家并行 | `_EP`（仅 MoE 模型；`use_all2all` 时传 use_all2all=True） | `_MOE_EP`（`moe_ep_size==tp_size` 且非 NPU 时别名 `_TP`；强制禁用 PyNccl/CustomAllreduce） |
| EPLB | `_EPLB` 独立通信组（MoE 且 `enable_eplb`） | 无 EPLB 通信组；独立 `srt/eplb/` 模块（在线重均衡） |
| MoE 专属组 | 无 MOE_DP/MOE_TP（复用 DP/TP） | `_MOE_DP`（`moe_dp_size==tp_size` 时别名 `_TP`）、`_MOE_TP`（禁 PyNccl/CAR） |
| DP-attention | 无（DP 即数据并行） | `_ATTN_TP`/`_ATTN_CP` 与 TP 解耦：`attn_tp_size = tp_size // attn_cp_size // attn_dp_size` |
| 弹性/特殊 | `_INNER_DP_WORLD`（DP>1 且 nnodes_within_dp>1）；Stateless EP 用 `StatelessGroupCoordinator` | `_PDMUX_PREFILL_TP_GROUP`（PD-Multiplexing 的 prefill TP 副本，`duplicate_tp_group`）；`_ATTN_CP_OVERLAP`（HIP 双流重叠） |

> 关键差异 ①：vLLM 固定 rank 拓扑 **ExternalDP × DP × PP × PCP × TP**，CP 维度拆成 PCP/DCP 两维以支持 prefill/decode 解耦（PD 分离）；SGLang 用 **attn_tp = tp/cp/dp、moe_tp = tp/ep/dp** 的派生关系把 attention 与 MoE 的通信组从 TP 组中独立出来（DP-attention），但**没有 PCP 维度**——上下文并行由 ATTN_CP/DCP 承担。

### 二、并行组建模（initialize_model_parallel）

布局示例（8 GPU，TP=2、PP=4）两者一致：4 个 TP 组 `[g0,g1][g2,g3][g4,g5][g6,g7]`；2 个 PP 组 `[g0,g2,g4,g6][g1,g3,g5,g7]`。TP 取连续 rank 块，PP 取跨块 stride。

| 组 | vLLM 全局变量 | SGLang 全局变量 |
|---|---|---|
| world | `_WORLD` / `get_world_group()` | `_WORLD` / `get_world_group()` |
| TP | `_TP` / `get_tp_group()` | `_TP` / `get_tp_group()` |
| PP | `_PP` / `get_pp_group()` | `_PP` / `get_pp_group()` |
| DP | `_DP` / `get_dp_group()` | —（无访问器） |
| DCP | `_DCP` / `get_dcp_group()` | `_DCP` / `get_dcp_group()` |
| PCP | `_PCP` / `get_pcp_group()` | — |
| EP | `_EP` / `get_ep_group()` | `_MOE_EP` / `get_moe_ep_group()` |
| EPLB | `_EPLB` / `get_eplb_group()` | — |
| ATTN_CP | — | `_ATTN_CP` / `get_attn_cp_group()` |
| ATTN_TP | — | `_ATTN_TP` / `get_attn_tp_group()` |
| MOE_DP | — | `_MOE_DP` / `get_moe_dp_group()` |
| MOE_TP | — | `_MOE_TP` / `get_moe_tp_group()` |

- vLLM 别名少：仅 ATTN/CP 无；SGLang 别名多，`destroy_model_parallel` 需先销毁 `_MOE_DP` 再销毁 `_ATTN_CP` 避免重复 destroy 别名组。
- SGLang `_tag_groups_for_flashinfer_allreduce_only` 为 ATTN_TP/MOE_EP/MOE_TP 打 `_fi_workspace_hint`，把 all_reduce 分发进 FlashInfer 融合 workspace（attention/MoE 各一）。

### 三、初始化流程对比

| 环节 | vLLM | SGLang |
|---|---|---|
| 入口 | `init_distributed_environment()` → `initialize_model_parallel()` →（业务）→ `destroy_model_parallel()` → `destroy_distributed_environment()` | `bootstrap.py::init_torch_distributed()` → `_init_parallel_groups()` → `init_distributed_environment()` → `initialize_model_parallel()` → `_prewarm_nccl()`/`_prewarm_tp_lm_head_all_to_all()` |
| 谱系 | Megatron-LM 风格（GroupCoordinator 包装 PG） | 显式改编自 vLLM v0.6.4.post1，再上溯 Megatron-LM |
| 组构建 | 每组两个新 PG：`new_group(ranks, backend=nccl)` + `new_group(ranks, backend="gloo")`；可选 `VLLM_DISTRIBUTED_USE_SPLIT_GROUP=1` 从双后端默认 PG 切分（`torch.distributed.split_group`） | 同两组 PG；另支持 `mooncake` backend（`active_ranks` mask + `MooncakeBackendOptions`）；NPU 走 HCCL `pg_options` |
| rank 布局 | 固定 ExternalDP×DP×PP×PCP×TP；DP>1 时按 `data_parallel_rank * world_size + rank` 偏移全局 rank | `rank = rank_offset + tp_size*pp_rank + tp_rank`（`ep_join` 可偏移）；弹性 EP joiner 组在全局 rank 空间构造、PG 以 `max_world_size` 预分配 |
| world 组 | `init_distributed_environment` 建 `_WORLD` | `init_world_group()` 建 `_WORLD`（world 组禁用一切加速通信器） |
| 后端回退 | 请求后端不可用（如 nccl）时警告并回退 gloo | 同 |
| PP 层划分 | `utils.get_pp_indices`，`VLLM_PP_LAYER_PARTITION` 可覆盖，余数从末尾倒数第 2 分区加 | 同款，`SGLANG_PP_LAYER_PARTITION` 覆盖 |
| 弹性 EP | `_init_stateless_group()` 建 `StatelessGroupCoordinator`，限 `nnodes_within_dp==1` | `srt/elastic_ep/`：状态机 + `ep_join_mode`（recover/scale）+ TCPStore scale cohort |
| 设备分配 | `local_rank` 绑定 | 同；bootstrap 另做 NCCL 预热与 TP 内存均衡检查 |

> 关键差异 ②：两引擎初始化骨架同源（都源自 Megatron：GroupCoordinator + device_group/cpu_group 双 PG），但 SGLang 在 vLLM 之上加了**弹性 EP（mooncake/rank_offset/max_world_size）**与 **PD-Multiplexing prefill 副本**；vLLM 则引入 **split_group 双后端默认 PG 切分**与 **Stateless EP 通信组**。

### 四、GroupCoordinator 核心对照

| 属性 | vLLM | SGLang |
|---|---|---|
| 角色 | PyTorch ProcessGroup 包装 | 同（`init_model_parallel_group` 建两组 PG） |
| rank 三态 | `rank`/`local_rank`/`rank_in_group` | 同 |
| device_group | 设备通信 PG（nccl） | 同 |
| cpu_group | gloo 控制面（barrier/对象广播/unique id 分发） | 同 |
| device_communicator | `current_platform.get_device_communicator_cls()` 构造，CudaCommunicator 组合 PyNccl+CustomAllreduce | 直接挂 `pynccl_comm`/`ca_comm`/`qr_comm`/`pymscclpp_comm`/`torch_symm_mem_comm` 等属性 |
| mq_broadcaster | `MessageQueue` 共享内存广播（仅 TP 组） | 同（`MessageQueue.create_from_process_group(cpu_group, 1<<22, 6)`） |
| unique_name | `_get_unique_name(group_name)` 供自定义算子查表 | 同（注册进 `_groups` weakref 表） |
| graph_capture | CUDA graph 捕获上下文（含 custom allreduce capture） | 模式矩阵：quick/custom AR eager+graph 均开；PyNccl/PyMscclpp/TorchSymmMem 仅 graph |
| 弹性 rank 表 | — | `active_ranks`（int32 mask，device/cpu 各一份） |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
