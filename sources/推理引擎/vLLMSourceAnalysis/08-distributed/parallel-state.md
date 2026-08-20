## 分布式并行状态（vllm/distributed）

### 模块职责

`vllm/distributed/` 接管 PyTorch 分布式环境控制，核心文件：

| 文件 | 职责 |
|---|---|
| `__init__.py` | 仅转导出 `communication_op` / `parallel_state` / `utils` 全部符号 |
| `parallel_state.py` | `GroupCoordinator`、并行组建模、init/destroy 生命周期、`torch.ops.vllm.*` 自定义算子 |
| `communication_op.py` | TP 组通信便捷封装（all_reduce / all_gather / reduce_scatter / gather / broadcast_tensor_dict） |
| `utils.py` | 张量切分、PP 层划分（`get_pp_indices`）、`StatelessProcessGroup`、无状态 PG 初始化 |
| `stateless_coordinator.py` | `StatelessGroupCoordinator`：不污染默认 PG 的弹性 EP 通信组 |
| `kv_events.py` | KV 事件（`BlockStored`/`BlockRemoved`/`AllBlocksCleared`）与事件发布器 |

### 生命周期工作流

```
init_distributed_environment()   # 初始化分布式环境（default PG + world 组）
  └─ initialize_model_parallel() # 建立 TP/PCP/PP/DP/EP 等模型并行组
      └─ ... 业务使用各 group 的通信操作 ...
          └─ destroy_model_parallel()       # 销毁模型并行组
              └─ destroy_distributed_environment()  # 销毁环境
```

只用电环境、不用模型并行时，可跳过并行组 init/destroy 两步。另提供 `ensure_model_parallel_initialized()`：未初始化则初始化，已初始化则校验各并行组 size 一致。

### GroupCoordinator 核心类

PyTorch `ProcessGroup` 的包装，一个组绑定一种通信后端（NCCL/Gloo 等），统一管理 CPU 与设备通信。

| 属性 | 含义 |
|---|---|
| `rank` | 全局 rank |
| `ranks` | 组内成员的全部全局 rank |
| `world_size` | 组大小 |
| `local_rank` | 节点内本进程 rank（用于分配设备） |
| `rank_in_group` | 在组内的位次 |
| `device_group` | 设备通信 ProcessGroup（如 nccl） |
| `cpu_group` | CPU 通信 ProcessGroup（gloo） |
| `device_communicator` | 平台设备通信器（`use_device_communicator=True` 且 `world_size>1` 时创建） |
| `mq_broadcaster` | 共享内存广播器（`MessageQueue`，TP 组用） |

rank 三态示例（2 节点 4 进程）：

| 进程 | 节点 | rank | local_rank | rank_in_group |
|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 |
| 1 | 0 | 1 | 1 | 1 |
| 2 | 1 | 2 | 0 | 2 |
| 3 | 1 | 3 | 1 | 3 |

关键 API：`first_rank`/`last_rank`/`next_rank`/`prev_rank`、`barrier()`（强制用 cpu_group 而非 device_group，因 NCCL barrier 内部是偷偷建 GPU 张量的 broadcast，易污染当前设备）、`destroy()`、`graph_capture()`（CUDA graph 捕获上下文，含 custom allreduce 的 `capture()`）。

### 并行组建模（initialize_model_parallel）

rank 拓扑布局固定为 `ExternalDP x DP x PP x PCP x TP`。示例（8 GPU，TP=2、PP=4）：

- 4 个 TP 组：`[g0,g1] [g2,g3] [g4,g5] [g6,g7]`
- 2 个 PP 组：`[g0,g2,g4,g6] [g1,g3,g5,g7]`

| 组 | 全局变量 | 访问器 | 建立条件 |
|---|---|---|---|
| world | `_WORLD` | `get_world_group()` | `init_distributed_environment` |
| inner_dp_world | `_INNER_DP_WORLD` | `get_inner_dp_world_group()` | DP>1 且 nnodes_within_dp>1 |
| TP | `_TP` | `get_tp_group()` | 总是 |
| DCP | `_DCP` | `get_dcp_group()` | decode context parallel（默认 1） |
| PCP | `_PCP` | `get_pcp_group()` | prefill context parallel |
| PP | `_PP` | `get_pp_group()` | 总是 |
| DP | `_DP` | `get_dp_group()` | 总是 |
| EP | `_EP` | `get_ep_group()` | 仅 MoE 模型（`config.model_config.is_moe`） |
| EPLB | `_EPLB` | `get_eplb_group()` | MoE 且 `parallel_config.enable_eplb` |

- TP 组启用消息队列广播器（mq_broadcaster）；EP 组在 `parallel_config.use_all2all` 时传 `use_all2all=True`（EPLB 独立分组以隔离 MoE 通信防死锁）。
- 弹性 EP（`enable_elastic_ep`）时 DP/EP/EPLB 走 `_init_stateless_group()` 建 `StatelessGroupCoordinator`，并限制 `nnodes_within_dp == 1`（多节点 TP/PP 不支持）。

### 设备后端与 split_group

- 默认：每个并行组建两个新 PG —— `new_group(ranks, backend=device 后端, nccl)` + `new_group(ranks, backend="gloo")`。
- 可选 `VLLM_DISTRIBUTED_USE_SPLIT_GROUP=1`：用 `torch.distributed.split_group` 从绑定 `device_id` 的默认 PG 切分 device/cpu 子组，要求默认 PG 为 `"cpu:gloo,cuda:nccl"` 双后端 + `device_id`（外部启动器如 torchrun 需校验此约束）。
- 后端退避：请求后端不可用（如 nccl）时警告并回退 gloo。
- DP 扩展：`init_distributed_environment` 在 `nnodes>1 || data_parallel_size>1` 时按 `data_parallel_rank * world_size + rank` 偏移全局 rank。

### 通信操作汇总

设备组（device_group）上的集合通信统一走 `device_communicator`：

| 方法 | 说明 |
|---|---|
| `all_reduce` / `_all_reduce_out_place` | 均改出 OP（out-of-place），`world_size==1` 直接返回输入 |
| `all_gather(input, dim)` | 任意 dim，concat 语义（兼容 torch.compile） |
| `reduce_scatter(input, dim)` | 仅均匀切分；`world_size==1` 短路 |
| `all_gatherv` / `reduce_scatterv` | 变长尺寸版 |
| `gather(input, dst, dim)` | dst 为组内本地 rank |
| `send` / `recv` | P2P 张量传输（经 device_communicator） |
| `broadcast(input, src)` | 经 device_group |
| `broadcast_object` / `broadcast_object_list` | 对象广播（有 mq_broadcaster 则走共享内存） |
| `broadcast_tensor_dict` | 元数据走 cpu_group、张量走 device_group 的混合广播 |
| `send_tensor_dict` / `isend_tensor_dict` / `recv_tensor_dict` / `irecv_tensor_dict` | 张量字典 P2P，支持 `all_gather_group` 优化（TP 组内按切片重建全量） |
| `send_object` / `recv_object` | pickle 序列化对象经 cpu_group 发送 |
| `barrier` | 经 cpu_group |
| `dispatch_router_logits` / `dispatch` / `combine` | MoE 专家路由（转发给 all2all manager） |

自定义算子（`all_reduce`/`all_gather`/`reduce_scatter`/`patched_fused_scaled_matmul_reduce_scatter`）注册于 `torch.ops.vllm.*`，因 Dynamo 无法传递对象，以 `group_name` 字符串作为参数查表分发；每个算子提供 fake 实现供 meta 设备使用。`GroupCoordinator.all_reduce` 在 `use_custom_op_call`（TPU 或平台开启）时走自定义算子路径。

### utils.py 附带能力

- `get_pp_indices(num_hidden_layers, pp_rank, pp_size)`：PP 层区间切分，可用 `VLLM_PP_LAYER_PARTITION` 手动覆盖；未整除时余数从末尾倒数第 2 个开始加。
- `StatelessProcessGroup`：基于 TCPStore 的元数据交换对象，send/recv/broadcast/all_reduce/barrier 均不触碰默认 PG。
- `stateless_init_torch_distributed_process_group`：无状态 PG 创建，gloo 走 `init_gloo_process_group`，其余走平台 `stateless_init_device_torch_dist_pg`。
- `in_the_same_node_as(pg, src)`：通过共享内存段探测同节点性（NCCL 组不可用），`_node_count()` 据其统计节点数。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)