## 设备通信器（device_communicators）

### 架构概览

`GroupCoordinator` 在 `use_device_communicator=True` 时按 `current_platform.get_device_communicator_cls()`（平台路由，见 `vllm/platforms/`）构造 `DeviceCommunicatorBase` 子类。集合操作经 device_communicator 执行；Gloo 不单独封装，直接以 `cpu_group`（`backend="gloo"`）形式存在于每个并行组，用于 CPU 元数据协调、barrier、对象广播与 NCCL unique id 分发。

### 通信器一览

| 类 / 模块 | 后端 | 用途 |
|---|---|---|
| `DeviceCommunicatorBase`（`base_device_communicator.py`） | 抽象 | 所有设备通信器基类：`all_reduce`/`all_gather`/`reduce_scatter`/`gather`/`send`/`recv`/`broadcast`，默认实现全部走 `torch.distributed` device_group |
| `CudaCommunicator`（`cuda_communicator.py`） | CUDA 组合 | CUDA 顶层通信器：组合 PyNccl 与各自定义 allreduce，实现 all-reduce 后端调度链，持有 all2all manager |
| `PyNcclCommunicator`（`pynccl.py`） | NCCL | 经 ctypes 封装的裸 NCCL（`NCCLLibrary`，见 `pynccl_wrapper.py`），绕过 torch.distributed，支持 all_reduce/all_gather(v)/reduce_scatter(v)/send/recv/broadcast/group_start/group_end/window register |
| `CustomAllreduce`（`custom_all_reduce.py`） | 自研 TP allreduce | 单节点 TP 快速 allreduce（world sizes 2/4/6/8/16），可配 `custom_all_gather`/`custom_reduce_scatter` |
| `QuickAllReduce`（`quick_all_reduce.py`） | QuickReduce | ROCm（AMD MI3xx）快速 allreduce，为 CustomAllreduce 的补充 |
| `FlashInferAllReduce`（`flashinfer_all_reduce.py`） | FlashInfer | 基于 FlashInfer 的 allreduce（workspace 可 checkpoint 准备/恢复） |
| `AiterCustomAllreduce`（`aiter_custom_all_reduce.py`） | AITER | ROCmAITER 自定义 allreduce |
| `SymmMemCommunicator`（`symm_mem.py`） | Torch 对称内存 | 基于 `torch.distributed._symmetric_memory` 的 allreduce |
| `CpuCommunicator`（`cpu_communicator.py`） | CPU SHM / gloo | CPU 平台通信器；TP/PP 组共享 SHM 组名时改用 `_CPUSHMDistributed`（共享内存），`supports_tensor_dict=True` |
| `XpuCommunicator`（`xpu_communicator.py`） | XCCL | XPU 平台通信器，all_reduce 走 device_group，all2all 仅支持 AgRs |
| `RayPPCommunicator`（`ray_communicator.py`） | Ray | PP 组经 Ray 的通信器 |
| `MessageQueue`（`shm_broadcast.py`） | 共享内存+ZMQ | 跨进程对象/张量广播队列（TP 组 mq_broadcaster），内含 `ShmRingBuffer`、自旋锁 `SpinCondition` |
| `SingleWriterShmObjectStorage`（`shm_object_storage.py`） | 共享内存 | 单写者对象存储（支持 Msgpack 序列化） |
| `AgRsAll2AllManager` / `DeepEPV2All2AllManager` / `NixlEPAll2AllManager` / `FlashInferNVLinkTwoSidedManager` / `FlashInferNVLinkOneSidedManager` / `MoriAll2AllManager`（`all2all.py`） | all2all | EP 组 MoE dispatch/combine 策略，基类 `All2AllManagerBase` 提供 fault tolerance 查询 |
| `EplbCommunicator`（`eplb/eplb_communicator.py`） | NCCL/Gloo/Nixl | EP 负载均衡通信：`TorchDistNcclEplbCommunicator` / `TorchDistGlooStagedEplbCommunicator` / `NixlEplbCommunicator` / `PyNcclEplbCommunicator`，工厂 `create_eplb_communicator` |

> `All2AllManagerBase`（`base_device_communicator.py`）为 all2all manager 基类：`dispatch_router_logits`/`dispatch`/`combine`/`query_active_mask`/`query_fault`/`clean_buffers`。
> 辅助模块：`cuda_wrapper.py`（`CudaRTLibrary`，ctypes 绑定 CUDA runtime，用于 `all_reduce_utils.py` 的 `gpu_p2p_access_check` 等）；`pynccl_allocator.py`（`nccl_symm_mem_context` 对称内存池）；`mnnvl_compat.py`（`CustomCommunicator` 把 vLLM ProcessGroup 适配为 FlashInfer `CommBackend`，供 MNNVL NVLink two-sided alltoall 使用）。

### CudaCommunicator 的 all-reduce 调度链

`all_reduce()` 依次尝试，逐个前移：

```
NCCL_SYMM_MEM → QUICK_REDUCE → FLASHINFER → AITER_CUSTOM → CUSTOM(自研) → SYMM_MEM → PYNCCL → torch.distributed 兜底
```

选择因素：`VLLM_ALLREDUCE_USE_SYMM_MEM`、`VLLM_ALLREDUCE_USE_FLASHINFER`、`_ENABLE_CUSTOM_ALL_REDUCE`（`set_custom_all_reduce` 设置，禁用自定义时关）、world size 阈值、张量 dtype/size 门控（`should_custom_ar`/`should_use_fi_ar`/`should_use_symm_mem`）。自研 CustomAllreduce 仅限 TP 组固定 world sizes；QUICK_REDUCE 仅 ROCm MI3xx。`VLLM_DISABLE_PYNCCL=1` 可禁用 PyNccl（此时 allreduce 回退 torch.distributed）。

all2all 后端由 `parallel_config.all2all_backend` 选择：`naive`/`allgather_reducescatter`/`deepep_high_throughput`/`deepep_low_latency`/`deepep_v2`/`nixl_ep`/`flashinfer_nvlink_two_sided`（旧名 `flashinfer_all2allv`）/`flashinfer_nvlink_one_sided`/`mori_high_throughput`/`mori_low_latency`。

### PyNcclCommunicator 要点

- 由 `NCCLLibrary`（`pynccl_wrapper.py`）用 ctypes 绑定 `libnccl`，unique id 由 rank 0 `ncclGetUniqueId` 生成，经 gloo 广播分发。
- 绑定单一设备：张量设备不一致会触发 illegal memory access 断言。
- `world_size==1` 或缺少 NCCL 库、`VLLM_DISABLE_PYNCCL` 时 `available=False`、`disabled=True`。
- `send`/`recv` 对 fp8 类型按 uint8 处理；`batch_isend_irecv` 用 group start/end 批量 P2P。
- `all_gatherv`/`reduce_scatterv` 基于 `ncclBroadcast`/`ncclReduce` 循环实现。
- `destroy()` 在 daemon 线程以 5s 超时 abort，避免与 CUDA graph 释放自死锁。
- 对称内存开启时注册 `all_reduce_symmetric_with_copy` 自定义算子（`pynccl_allocator.py` 管理 `nccl_symm_mem_context`）。

### Gloo 的定位

Gloo 无独立 Python 类，作用为：

- `GroupCoordinator.cpu_group` 与每个子组相伴的 `backend="gloo"` PG。
- `broadcast_object`/`send_object`/`recv_object`/`broadcast_tensor_dict` 元数据通道。
- NCCL unique id 广播、`barrier`、`in_the_same_node_as` 等环控制面。
- `init_gloo_process_group` 支持无状态 Gloo PG 创建（兼容多版本 torch）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)