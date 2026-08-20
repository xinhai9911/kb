## 通信算子封装与 backend 选择（vllm/distributed 内核层）

本文聚焦 `vllm/distributed/` 中通信算子的**薄封装层**、`group` 参数语义，以及 backend（cuda/cpu/nccl）的**两层选择机制**（PG 层 + 通信器调度层）。分组与 GroupCoordinator 的完整模型见 08-distributed。

### communication_op.py：TP 组算子门面

`vllm/distributed/communication_op.py` 仅约 40 行，是 `GroupCoordinator` 的极薄包装，全部委托给 `get_tp_group()`：

| 函数 | 委托 | 说明 |
|---|---|---|
| `tensor_model_parallel_all_reduce(input_)` | `get_tp_group().all_reduce(input_)` | TP 组全归约 |
| `tensor_model_parallel_all_gather(input_, dim=-1)` | `get_tp_group().all_gather(input_, dim)` | 默认沿最后维 concat |
| `tensor_model_parallel_reduce_scatter(input_, dim=-1)` | `get_tp_group().reduce_scatter(input_, dim)` | 默认沿最后维切分 |
| `tensor_model_parallel_gather(input_, dst=0, dim=-1)` | `get_tp_group().gather(input_, dst, dim)` | 非全 rank；`dst` 为组内本地 rank，返回仅 dst |
| `broadcast_tensor_dict(tensor_dict, src=0)` | `get_tp_group().broadcast_tensor_dict(...)` | 未初始化时原样返回 |

关键点：该文件**不包含任何 backend 决策**，真正的算子实现在 `GroupCoordinator`（`parallel_state.py`）及其持有的 `device_communicator` 中；`get_tp_group()` 是懒加载单例（`_TP` 全局变量，初始化于 `initialize_model_parallel`）。

### GroupCoordinator 的 group 参数语义

每个并行组由 `GroupCoordinator`（`parallel_state.py:409`）持有三个层次的"通道"：

| 属性 | 创建方式 | 角色 |
|---|---|---|
| `cpu_group` | `torch.distributed.new_group(ranks, backend="gloo")` | 控制面：对象广播、barrier、NCCL unique id 分发、`in_the_same_node_as` 探测 |
| `device_group` | `torch.distributed.new_group(ranks, backend=torch_distributed_backend)` | 数据面 PG，backend 由平台决定（CUDA/ROCm 为 nccl，CPU 为 gloo）；`DeviceCommunicatorBase` 默认实现直接 `dist.all_reduce(..., group=self.device_group)` |
| `device_communicator` | `resolve_obj_by_qualname(current_platform.get_device_communicator_cls())(cpu_group=..., device=..., device_group=..., unique_name=...)` | 加速层，见 [device-communicators_part1.md](device-communicators_part1.md) |

- `unique_name`（`_get_unique_name(group_name)`）作为组标识传入通信器，用于判定是否 TP 组（决定是否启用 custom allreduce）以及 CPU SHM 组名生成。
- 新增 `VLLM_DISTRIBUTED_USE_SPLIT_GROUP=1` 时走 `split_group` 新路径：默认 PG 用 `backend="cpu:gloo,cuda:nccl"` 双后端 + 绑定 `device_id`，子组由父通信器切分（要求外部 launcher 也以该方式初始化，见 `_validate_default_pg_for_split_group`）。
- `init_distributed_environment`（`parallel_state.py:1586`）：DP>1 时按 `data_parallel_rank` 偏移 rank/world_size 并改用独立 master IP/端口；默认 `backend="nccl"`，由调用方（executor）传入平台指定 backend。

### backend 两层选择机制

**第一层：PG backend（进程组层面）**

| 平台 | 默认 init backend | device_group backend | 说明 |
|---|---|---|---|
| CUDA (`platforms/cuda.py`) | `cpu:gloo,cuda:nccl` | nccl | `get_device_communicator_cls()` → `CudaCommunicator` |
| ROCm (`platforms/rocm.py`) | 同上 | nccl | 类名仍是 `CudaCommunicator` |
| CPU (`platforms/cpu.py`) | `gloo` | gloo | `CpuCommunicator` |
| XPU (`platforms/xpu.py`) | `cpu:gloo,xpu:xccl`（外部） | xccl | `XpuCommunicator` |
| 无加速器 | `gloo` | gloo | 走 `_init_process_group_for_split_group` 的 else 分支 |

**第二层：通信器内调度（张量层面）** —— `CudaCommunicator.all_reduce` 的运行时门控链，详见 [custom-allreduce.md](custom-allreduce.md) / [device-communicators_part1.md](device-communicators_part1.md)。要点：每个候选后端通过 `should_*` 谓词按 **world size、dtype、字节大小（16 对齐）、弱连续、节点内/fully_connected** 逐调用裁决，返回 `None` 即落到下一级；最终兜底为 `torch.distributed.all_reduce(group=self.device_group)`（nccl）。

### 关键行为与坑

- `CudaCommunicator.all_reduce` 的 PyNccl 分支若返回 `None`（如测试环境），显式回退 `input_.clone(); dist.all_reduce(...)`；注释说明正式运行时 TP 组必有 custom allreduce 或 pynccl。
- `all_gather` 使用 concat 风格（`all_gather_into_tensor`）而非 stack 风格，因后者与 `torch.compile` 不兼容（`pytorch/pytorch#138795`）。
- `reduce_scatter` 前必须 `movedim(0, dim).contiguous()`（注释称 `reduce_scatter_tensor` 存在非连续 bug）。
- `send`/`recv` 的 `dst`/`src` 均为**组内本地 rank**，实现内转为全局 rank 再调 `dist.send/recv`。
- `broadcast` 在 `world_size==1` 时短路直接返回。
- fp8 类型（`float8_e5m2`/`float8_e4m3fn`/`float8_e4m3fnuz`/`float8_e5m2fnuz`）经 PyNccl `send`/`recv` 时按 `uint8` 传递（`pynccl.py`）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
