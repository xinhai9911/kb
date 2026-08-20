## Device Communicator 内核与平台衔接 _part1：基类与 CUDA 组合

`vllm/distributed/device_communicators/` 是数据面通信内核：基类接口、CUDA/CPU/XPU 各后端实现、PyNccl 裸 NCCL 封装与对称内存分配器。08-distributed 已列全通信器清单与调度链概览，本文深入**接口契约、内部组合、初始化流程与 platform(14) 衔接**（分两部分）。

### DeviceCommunicatorBase：接口契约与 rank 语义

`base_device_communicator.py` 是所有设备通信器基类。构造参数：`cpu_group`（gloo 控制面 PG）、`device`、`device_group`（设备 PG）、`unique_name`、`global_ranks`/`global_world_size`、`use_all2all`。

**stateless vs 有状态 PG**：通过 `_world.pg_map.get(cpu_group, None) is None` 判别。无状态组（弹性 EP 场景）不能用 `dist.get_rank`，改取 `cpu_group.rank()` + 显式传入的 `global_ranks`；有状态组则用 `dist.get_process_group_ranks`/`dist.get_group_rank`。

**EP all2all 判定**：`is_ep_communicator = unique_name.split(":")[0] == "ep"`，`use_all2all = is_ep_communicator and use_all2all`；`all2all_backend` 从 `get_current_vllm_config_or_none().parallel_config.all2all_backend` 读取。

**方法矩阵**（默认全部走 `torch.distributed` + `device_group`）：

| 方法 | 语义 |
|---|---|
| `all_reduce` | in-place，返回输入 |
| `all_gather` | concat 风格（`all_gather_into_tensor` + movedim/reshape），兼容 torch.compile |
| `reduce_scatter` | `movedim(0, dim).contiguous()` 后 `reduce_scatter_tensor` |
| `gather`/`send`/`recv`/`broadcast` | `dst`/`src` 均为**组内本地 rank**，内部转全局 rank |
| `batch_isend_irecv` | 默认 `NotImplementedError`，CUDA 由 PyNccl 实现 |
| `dispatch`/`combine`/`dispatch_router_logits` | 默认 no-op，EP 组由 all2all manager 接管 |
| `checkpoint_prepare`/`checkpoint_restore` | 默认 no-op；CUDA 只对 FlashInfer workspace 生效 |

### CudaCommunicator：组合与调度

`cuda_communicator.py` 的 `all_reduce` 逐级门控链（从 08 的概览落到**实例化条件**）：

| 后端 | 实例化条件（均在 TP 组，`"tp" in unique_name`） |
|---|---|
| `pynccl_comm` | `world_size > 1`；`VLLM_DISABLE_PYNCCL` 或缺 NCCL 库时 `disabled=True` |
| `symm_mem_comm` | `VLLM_ALLREDUCE_USE_SYMM_MEM` 且 `is_cuda()` |
| `fi_ar_comm` | `VLLM_ALLREDUCE_USE_FLASHINFER` 且 `world_size > 1` |
| `aiter_ar_comm` | `use_custom_allreduce and rocm_aiter_ops.is_custom_all_reduce_enabled()` |
| `ca_comm` | `use_custom_allreduce` 且 `aiter_ar_comm is None` 且 `world_size > 1` |
| `qr_comm` | `use_custom_allreduce` 且 `is_rocm()`（MI300 系列） |

- `use_custom_allreduce = _ENABLE_CUSTOM_ALL_REDUCE`（`set_custom_all_reduce` 全局开关）。
- 非 TP 组强制关闭全部加速后端。
- `all_reduce` 运行顺序：`NCCL_SYMM_MEM → QUICK_REDUCE → FLASHINFER → AITER_CUSTOM → CUSTOM → SYMM_MEM → PYNCCL → dist 兜底`；日志 `_log_all_reduce_backend_selection` 打印本组实际启用子集。
- **NCCL 对称内存（NVLS）路径**：`should_nccl_symm_mem_allreduce` 按 `NCCL_SYMM_MEM_ALL_REDUCE_CONFIG`（`all_reduce_utils.py`）裁决：`min_world_size=4`；8 卡 16KB-128KB、4 卡 16KB-512KB 区间 custom_AR 更优（H100/GB200 实测：小张量 1.21-1.48x、大张量 1.10-6.14x 快），区间外走 symm mem；`world_size>8` 恒走 symm mem；`VLLM_BATCH_INVARIANT` 禁用。
- **AG/RS 对称内存**：`should_nccl_symm_mem_ag_rs()` 仅要求 symm mem 启用；`_get_symm_scratch` 按 `(role, shape, dtype)` 缓存预注册 scratch（每次新建 symm 张量需付约 0.5ms window 注册扫描）；非均匀 size 的 RSv/AGv 不用 symm（`ncclCommWindowRegister` 是集体操作，非对称池分配会死锁）。
- all2all manager 工厂按 `all2all_backend` 分发到 `all2all.py` 的 9 种实现。

### PyNcclCommunicator：裸 NCCL 初始化流程

`pynccl.py` 绕开 torch.distributed 直接调 NCCL（CUDA graph 捕获期 torch.distributed 含非法 cuda API，见 `pynccl_wrapper.py` 头部注释）：

1. `NCCLLibrary(library_path)`：ctypes 绑定 `libnccl`（`VLLM_NCCL_SO_PATH` 可切换版本），导出 `ncclUniqueId`（128 字节）、`ncclCommProperties_t`、类型/归约枚举与全部 `nccl*` 函数。
2. rank 0 `ncclGetUniqueId` 生成 unique id → 经 gloo `dist.broadcast(tensor, src=ranks[0])` 分发（Stateless 组走 `group.broadcast_obj`）。
3. `torch.accelerator.device_index(device.index)` 上下文内 `ncclCommInitRank(world_size, unique_id, rank)` 建通信器，随后一次 1 元素 allreduce 预热 + `stream.synchronize()`。
4. 全部算子断言 `in_tensor.device == self.device`（跨设备触发 illegal memory access）。
5. `destroy()`：`ncclCommAbort` 在 daemon 线程 + 5s 超时执行，避免与 CUDA graph 释放自死锁。
6. `all_gatherv`/`reduce_scatterv` 用 `ncclGroupStart/End` 包裹 `ncclBroadcast`/`ncclReduce` 循环；`register_comm_window(_raw)` 对接 NCCL symmetric memory window。

### pynccl_allocator：NCCL 对称内存池

- 用 `load_inline` 编译 `nccl_alloc_plug`/`nccl_free_plug`（内部 `ncclMemAlloc`/`ncclMemFree`），包装为 `CUDAPluggableAllocator` + `torch.cuda.MemPool`；缺 NCCL 头文件则 `_nccl_allocator_failed_to_compile=True` 静默禁用。
- `nccl_symm_mem_context`：进入时 `use_mem_pool(get_nccl_mem_pool())`；graph 捕获期暂停 graph 内存池（`_cuda_endAllocateToPool`）并断言 `graph_pool_id` 已设；退出时对每个新增 segment `register_comm_window_raw`（按 unique id 去重）。要求 NCCL ≥ 2.27.3、torch ≥ 2.8.0a0。
- 据此注册 `all_reduce_symmetric_with_copy` 自定义算子（含 fake 实现供编译/图捕获）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
