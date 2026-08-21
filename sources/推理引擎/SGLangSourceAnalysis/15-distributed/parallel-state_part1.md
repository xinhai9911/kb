## 分布式并行状态（srt/distributed）· 分组与初始化

本文覆盖 `srt/distributed/`（28 文件）。文件头显式标注 "Adapted from vLLM v0.6.4.post1"，主架构源自 vLLM/Megatron-LM，但并行维度与通信加速器有大量 SGLang 特有扩展。EPLB 见 [eplb_part1.md](eplb_part1.md)。通信算子与 vLLM 对照见 [parallel-state_part2.md](parallel-state_part2.md)。

### 模块职责

| 文件 | 职责 |
|---|---|
| `__init__.py` | 转导出 communication_op / parallel_state / utils 全部符号 |
| `parallel_state.py`（120KB） | `GroupCoordinator`、9 类并行组建模、`init_distributed_environment`/`initialize_model_parallel`、自定义算子注册、destroy 生命周期 |
| `communication_op.py` | TP/ATTN-TP/MoE-TP/MoE-EP 组通信便捷封装（极薄，全部委托 `get_*_group()`） |
| `bootstrap.py` | worker 进程入口：解析 backend/dist_init_method、调 `_init_parallel_groups`、NCCL 预热、TP 内存均衡检查 |
| `utils.py` | `StatelessProcessGroup`、全局 TCPStore、`get_pp_indices`、张量切分工具 |
| `parallel_state_wrapper.py` | `ParallelState` frozen dataclass（tp/pp/attn_*/moe_* 各维 rank/size 快照） |
| `naive_distributed.py` | `NaiveDistributed`：基于文件系统 rendezvous 的分布式替代（pickle+文件交换），无 torch.distributed |
| `communication_tags.py` | `P2PTag` 枚举：`HIRADIX_PP_SYNC`/`GRAMMAR_PP_SYNC` 预留 P2P tag |
| `device_communicators/` | PyNccl、CustomAllReduce、PyMscclpp、TorchSymmMem、QuickAllReduce（ROCm）、shm_broadcast、HPU/NPU/XPU、mooncake_transfer_engine |

### 初始化流程

```
bootstrap.py: init_torch_distributed()
  ├─ _resolve_backend()           # 平台 get_torch_distributed_backend_str()：CUDA→"nccl"
  ├─ _resolve_dist_init_method()  # --dist-init-addr 或 host:dist_port 的 tcp://
  ├─ _set_all_reduce_flags()      # set_custom_all_reduce/set_mscclpp_all_reduce/set_torch_symm_mem_all_reduce
  ├─ _init_parallel_groups()      # rank = rank_offset + tp_size*pp_rank + tp_rank（ep_join 可偏移）
  │    ├─ init_distributed_environment(parallel_state.py:2236)  # torch.distributed.init_process_group + _WORLD
  │    └─ initialize_model_parallel(parallel_state.py:2328)     # 建 9 类并行组
  │         └─ initialize_dp_attention()
  └─ _prewarm_nccl() / _prewarm_tp_lm_head_all_to_all()   # 消解首次请求冷启动
```

- `init_distributed_environment`：`backend` 默认 "nccl"，mooncake 时构造 `MooncakeBackendOptions(active_ranks, recovered_rank)`；`local_rank==-1` 时从 `LOCAL_RANK` env 取；随后 `init_world_group()` 建 `_WORLD`（world 组禁用一切加速通信器）。
- `initialize_model_parallel` 参数：`tensor_model_parallel_size`、`expert_model_parallel_size`、`pipeline_model_parallel_size`、`attention_data_parallel_size`、`attention_context_model_parallel_size`、`moe_data_model_parallel_size`、`decode_context_parallel_size`。派生关系：`attn_tp_size = tp_size // attn_cp_size // attn_dp_size`，`moe_tp_size = tp_size // moe_ep_size // moe_dp_size`。
- 弹性 EP（`recovered_rank`/`rank_offset`/`max_world_size`）：joiner 组在全局 rank 空间构造，TP/PP 布局按 `tp_size*pp_size` 推算，PG 以 `max_world_size` 预分配容量。

### 并行组建模（initialize_model_parallel）

以 TP=2、PP=4、8 GPU 为例：4 个 TP 组 `[g0,g1] [g2,g3] [g4,g5] [g6,g7]`；2 个 PP 组 `[g0,g2,g4,g6] [g1,g3,g5,g7]`。TP 组取**连续 rank 块**，PP 组取**跨块 stride**。

| 组 | 全局变量 | 访问器 | 建立条件/别名 |
|---|---|---|---|
| world | `_WORLD` | `get_world_group()` | `init_distributed_environment` |
| TP | `_TP` | `get_tp_group()` | 总是（启用 mq_broadcaster 共享内存广播） |
| PDMUX-TP | `_PDMUX_PREFILL_TP_GROUP` | `get_tp_group()`（pdmux 时） | `duplicate_tp_group`（PD-Multiplexing prefill 副本） |
| DCP | `_DCP` | `get_dcp_group()` | `decode_context_parallel_size>1`，TP 组内按 dcp_size 切 |
| ATTN_CP | `_ATTN_CP` | `get_attn_cp_group()` | `attn_cp_size==tp_size` 时别名 `_TP` |
| ATTN_CP_OVERLAP | `_ATTN_CP_OVERLAP` | `get_attn_cp_overlap_group()` | HIP 双流重叠（RCCL 单通信器双流会死锁），须与 `_ATTN_CP` 同 rank 集合 |
| ATTN_TP | `_ATTN_TP` | `get_attn_tp_group()` | `attn_tp_size==tp_size` 时别名 `_TP` |
| MOE_DP | `_MOE_DP` | `get_moe_dp_group()` | `attn_cp_size>moe_dp_size`→别名 `_ATTN_CP`；`moe_dp_size==tp_size`→别名 `_TP` |
| MOE_EP | `_MOE_EP` | `get_moe_ep_group()` | `moe_ep_size==tp_size` 且非 NPU 时别名 `_TP`；强制 `use_pynccl=False, use_custom_allreduce=False` |
| MOE_TP | `_MOE_TP` | `get_moe_tp_group()` | `moe_tp_size==tp_size` 时别名 `_TP`；同样禁 PyNccl/CAR |
| PP | `_PP` | `get_pp_group()` | 总是；`use_custom_allreduce=False` |

- 别名关系在 `destroy_model_parallel` 中特别处理：先销毁 `_MOE_DP` 再销毁 `_ATTN_CP`（避免重复 destroy 别名组）。
- `patch_tensor_parallel_group`：speculative decode 的 draft worker 临时替换 `_TP`。
- `_tag_groups_for_flashinfer_allreduce_only`：为 ATTN_TP 与 MOE_EP/MOE_TP 打 `_fi_workspace_hint`，使 `all_reduce` 可分发到 FlashInfer 融合 workspace（仅两个 workspace：attention 与 MoE）。
- 仅用分布式环境而不需要模型并行时，可跳过 `initialize_model_parallel`/`destroy_model_parallel` 两步（docstring 明示）。

### GroupCoordinator 核心类（parallel_state.py:237）

PyTorch `ProcessGroup` 包装。每个组由 `init_model_parallel_group`（`:1881`）建**两个**新 PG：`device_group`（backend=torch_distributed_backend，如 nccl）+ `cpu_group`（backend="gloo"，控制面）。mooncake backend 时各建 `backend="mooncake"`/`"mooncake-cpu"` 并带 `active_ranks` mask 与 `MooncakeBackendOptions`。

| 属性/通信器 | 含义 |
|---|---|
| `rank/ranks/world_size/rank_in_group/local_rank` | 全局 rank / 组内成员 / 组大小 / 组内位次 / 本节点内 rank |
| `device_group/cpu_group` | 设备通信 PG（nccl）/ CPU 协调 PG（gloo） |
| `pynccl_comm` | `PyNcclCommunicator`（world_size>1 且 `use_pynccl`） |
| `ca_comm` / `qr_comm` | `CustomAllreduce`（`dispatch_custom_allreduce` 分发，ROCm 下 aiter）/ ROCm `QuickAllReduce`（gfx942+，基于 quickreduce） |
| `pymscclpp_comm` / `torch_symm_mem_comm` | MSCL 集合通信 / 对称内存通信器 |
| `hpu/xpu/npu_communicator` | 对应平台专用通信器（`init_model_parallel_group` 一律传 `True`） |
| `mq_broadcaster` | `MessageQueue.create_from_process_group(cpu_group, 1<<22, 6)` 共享内存广播（仅 TP 组） |
| `unique_name` | `_get_unique_name(name)` 生成 `tp:0` 式唯一名，注册进 `_groups` weakref 表供自定义算子查表 |
| `active_ranks` | 弹性 EP 的活跃 rank mask（int32 张量，device/cpu 各一份） |

`graph_capture`（`:585`）模式矩阵：quick/custom allreduce 在 eager 与 graph 均启用；PyNccl/PyMscclpp/TorchSymmMem 仅 graph 启用；`torch.distributed` 原语仅 eager。PyMscclpp 需预注册张量，仅 graph 模式启用。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
