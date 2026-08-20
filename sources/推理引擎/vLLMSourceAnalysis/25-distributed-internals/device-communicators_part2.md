## Device Communicator 内核与平台衔接 _part2：CPU/XPU、platform 与无状态初始化

接 part1。本文覆盖 CPU/XPU 通信器实现、与 platform(14) 的衔接机制、`utils.py` 无状态初始化辅助与 P2P 探测内核。

### CpuCommunicator 与 CPU SHM

`cpu_communicator.py`：TP/PP 组且全 rank 共享同一 SHM 组名（`VLLM_DIST_IDENT` + unique_name + ranks 组成，经 `_all_group_ranks_share_shm_group_name` 用 `all_gather_object` 校验一致）时，`dist_module` 换为 `_CPUSHMDistributed`：

- 初始化：`torch.ops._C.init_shm_manager(group_name, world_size, rank, thread_num)`（线程数取各 rank `ReduceOp.MIN` 归约），随后 join + 两次 barrier。
- 算子映射：`shm_allreduce`/`shm_gather`/`shm_all_gather`/`shm_send_tensor_list`/`shm_recv_tensor_list`。
- `supports_tensor_dict=True` 时 `send/recv_tensor_dict` 走 SHM 快路径（pickle 元信息 + 张量列表），供 `broadcast_tensor_dict` 加速；否则抛 NotImplementedError。
- all2all 仅支持 `naive`/`allgather_reducescatter`，其他 backend 告警后回落 `AgRsAll2AllManager`。

### XpuCommunicator

`xpu_communicator.py`：无自定义 allreduce（`ca_comm=None`），all_reduce/reduce_scatter 直接走 `device_group`（xccl）；`gather` 用 all_gather 替代（与 Ray 集群不兼容）；all2all 非 AgRs 后端一律告警回落；`broadcast` 走 `dist.broadcast`。

### 与 platform(14) 的衔接

衔接点在 `GroupCoordinator.__init__`（`parallel_state.py:503`）：

```python
device_comm_cls = resolve_obj_by_qualname(current_platform.get_device_communicator_cls())
self.device_communicator = device_comm_cls(cpu_group=self.cpu_group, device=self.device,
                                           device_group=self.device_group,
                                           unique_name=self.unique_name, use_all2all=use_all2all)
```

| 平台 | `get_device_communicator_cls()` 返回 |
|---|---|
| `platforms/cuda.py:559` | `CudaCommunicator` |
| `platforms/rocm.py:962` | `CudaCommunicator`（ROCm 复用） |
| `platforms/cpu.py:435` | `CpuCommunicator` |
| `platforms/xpu.py:467` | `XpuCommunicator` |

platform 同时提供内核所需设备能力查询：`is_fully_connected`（NVLink 全连接判定）、`get_device_capability().as_version_str()`（SM 版本号，驱动大小阈值表）、`logical/visible/physical_device_id` 三态映射、`fp8_dtype()`（pynccl dtype 映射）、`stateless_init_device_torch_dist_pg`（无状态 PG 的 device 后端初始化）。device backend 选择见 comm-ops.md 的两层机制表。

### utils.py：无状态初始化辅助

- `StatelessProcessGroup`：不污染全局状态的元数据组（弹性 EP 场景），基于 TCPStore 提供 `send_obj`/`recv_obj`/`broadcast_obj`/`broadcast`/`send`/`recv`/`all_reduce`（对象级）；多阶段 `barrier`（uuid 标识，rank0 等待全组 departure 再放行，防 store 提前拆除）；数据条目 1h 过期自动清理。
- `stateless_init_torch_distributed_process_group`：替代 `init_process_group` 的无状态 PG 创建（不依赖全局 rank，支持动态加入进程）；gloo 走 `init_gloo_process_group`（兼容多版本 torch），设备后端委托 `current_platform.stateless_init_device_torch_dist_pg`；timeout 由 `parallel_config.cpu_distributed_timeout_seconds`（gloo）/`distributed_timeout_seconds`（设备后端）控制，经 `get_cpu_distributed_timeout_or_none`/`get_distributed_timeout_or_none` 读取；`listen_socket` 传入时跳过 rendezvous 直接建 TCPStore（消除端口绑定 TOCTOU）。
- `get_worker_rank_suffix`：生成 `dp{?}_pp{?}_tp{?}_dcp{?}_ep{?}_rank{?}` 身份串。

### P2P 探测内核

`all_reduce_utils.py` 的 `gpu_p2p_access_check`：因驱动可能谎报 `can_device_access_peer`（`vllm-project/vllm#2728`），须**真做 P2P 访问**验证——spawn 两个子进程（producer/consumer），经 CUDA IPC handle 共享 1KB 缓冲并互相改写校验（`producer` cudaMalloc+cudaMemset，`consumer` cudaIpcOpenMemHandle+cudaMemset，双队列模拟 barrier）；结果按 `CUDA_VISIBLE_DEVICES` 或物理卡序缓存到 `VLLM_CACHE_ROOT/gpu_p2p_access_cache_for_*.json`，仅 local_rank 0 计算后经 `get_world_group().barrier()` 同步。该检查是 CustomAllreduce/QuickAllReduce 可用性的前提之一；`VLLM_SKIP_P2P_CHECK` 可跳过软测、直接信任 `torch.cuda.can_device_access_peer`。

### 内核相关环境变量速查

| 变量 | 作用 |
|---|---|
| `VLLM_DISABLE_PYNCCL` | 禁用 PyNccl（回退 torch.distributed） |
| `VLLM_NCCL_SO_PATH` | 切换 NCCL 动态库 |
| `VLLM_USE_NCCL_SYMM_MEM` / `VLLM_ALLREDUCE_USE_SYMM_MEM` | NCCL/torch 对称内存 allreduce |
| `VLLM_ALLREDUCE_USE_FLASHINFER` | FlashInfer allreduce |
| `VLLM_ROCM_USE_AITER_CUSTOM_AR` | AITER 自研 allreduce（ROCm） |
| `VLLM_ROCM_QUICK_REDUCE_QUANTIZATION` | QuickReduce 量化级（FP/INT8/INT6/INT4/INT3/NONE） |
| `VLLM_BATCH_INVARIANT` | 禁用 NCCL symm mem 路径（保 batch 不变性） |
| `VLLM_SKIP_P2P_CHECK` | 跳过 P2P 实测 |
| `VLLM_DISTRIBUTED_USE_SPLIT_GROUP` | 启用 `split_group` 建组路径 |
| `VLLM_DIST_IDENT` | CPU SHM 组名标识 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
