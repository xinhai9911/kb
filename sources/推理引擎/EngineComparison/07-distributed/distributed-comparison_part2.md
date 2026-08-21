## 分布式并行：通信架构对比（vLLM vs SGLang）

通信对比承接 [distributed-comparison.md](distributed-comparison.md)。事实基准：vLLM `vllm/distributed/communication_op.py`、`device_communicators/`（KB 08-distributed + 25-distributed-internals）与 SGLang `sglang/srt/distributed/communication_op.py`（KB 15-distributed _part2）。

### 一、通信架构总览

| 维度 | vLLM | SGLang |
|---|---|---|
| 门面层 | `communication_op.py`（~40 行）5 个函数全部委托 `get_tp_group()` | 委托 `get_tp_group()`/`get_attn_tp_group()`/`get_moe_ep_group()`/`get_moe_tp_group()`，另含 NPU `quant_all_reduce`、ROCm `fused_allreduce_rmsnorm(_quant_per_group)` |
| 分层模型 | 三层：`cpu_group`(gloo 控制面) / `device_group`(nccl 数据面) / `device_communicator`(加速面) | 三层同构；加速通信器直接以属性挂载 |
| 顶层通信器 | `CudaCommunicator`（组合 PyNccl 与 CustomAllreduce，持 all2all manager，出-OP 调度链） | 无顶层组合器；`all_reduce` 在 `parallel_state.py:648` 分发链中逐候选裁决 |
| 集合方法 | all_reduce/all_gather/all_gatherv/reduce_scatter(v)/gather/broadcast/send/recv/broadcast_tensor_dict/send_tensor_dict/barrier | 同款全家桶；`all_gatherv`/`reduce_scatterv`/`all_to_all_single` **强制 pynccl**；`send`/`recv` pynccl 优先（TP LM-head a2a） |

### 二、all_reduce 调度链对比

| 优先级 | vLLM `CudaCommunicator.all_reduce` | SGLang `GroupCoordinator.all_reduce` |
|---|---|---|
| 1 | `NCCL_SYMM_MEM` | world_size==1 短路；CPU 张量 → `sgl_kernel.shm_allreduce`（LOCAL_SIZE 生效） |
| 2 | `QUICK_REDUCE`（仅 ROCm MI3xx） | HPU/XPU/NPU 对应 communicator（XPU inplace_all_reduce 自定义算子防 Dynamo 分解破坏 graph） |
| 3 | `FLASHINFER` | `torch.compiler` 编译中 → `flashinfer_allreduce`（`_can_use_flashinfer_allreduce`）或 inplace/outplace 自定义算子 |
| 4 | `AITER_CUSTOM`（ROCm AITER） | eager：`pymscclpp`(`should_mscclpp_allreduce`) > `ca`(`should_custom_ar`) > flashinfer |
| 5 | `CUSTOM`（自研，单节点 TP ws 2/4/6/8/16） | `outplace_all_reduce`：`ca` > `qr` > `pymscclpp` > `torch_symm_mem` > `pynccl` |
| 6 | `SYMM_MEM` | 兜底 `dist.all_reduce(device_group)`（in-place 版本先 pynccl → symm_mem → dist） |
| 7 | `PYNCCL`（ctypes 裸 NCCL） | — |
| 8 | `torch.distributed`（nccl device_group） | — |

门控条件两者同源：`world_size`/dtype/字节数 16 对齐/弱连续（`is_weak_contiguous`）/节点内（`in_the_same_node_as`）/`fully_connected`（P2P 探测）。

### 三、关键通信器对照

| 通信器 | vLLM | SGLang |
|---|---|---|
| 裸 NCCL | `PyNcclCommunicator`（`pynccl_wrapper.NCCLLibrary` ctypes 绑定；unique id 经 gloo 广播；fp8 按 uint8 传；`VLLM_DISABLE_PYNCCL` 禁用） | `PyNcclCommunicator` 同源；`all_gatherv`/`reduce_scatterv`/`all_to_all_single`（DCP a2a 后端，graph 可捕获）强制 pynccl |
| 自研 TP allreduce | `CustomAllreduce`：单节点、ws 2/4/6/8/16、meta+IPC 缓冲、two-stage、自旋同步、CUDA graph 捕获（`capture`/`register_graph_buffers`）、`should_custom_ar` 门控 | `CustomAllreduce` 同源（`dispatch_custom_allreduce` 分发，ROCm 下换 aiter）；`should_custom_ar` 门控 |
| 快速归约 | `QuickAllReduce`（ROCm MI3xx，fp16/bf16，量化 regime FP/INT8/6/4/3） | `QuickAllReduce`（gfx942+，基于 quickreduce） |
| 额外集合通信 | `SymmMemCommunicator`（`torch.distributed._symmetric_memory`）、`FlashInferAllReduce`、`AiterCustomAllreduce`、`CpuCommunicator`（SHM）、`XpuCommunicator`、`RayPPCommunicator` | `PyMscclpp`（MSCL，需预注册张量，仅 graph）、`TorchSymmMem`、`shm_broadcast`、HPU/NPU/XPU 通信器、`mooncake_transfer_engine` |
| 共享内存广播 | `MessageQueue`（`shm_broadcast.py`：ShmRingBuffer + SpinCondition，TP 组 mq_broadcaster） | 同款（仅 src=0 走共享内存） |
| 对象通道 | `SingleWriterShmObjectStorage`（Msgpack）；`broadcast_object`/`send_object` 走 cpu_group | `send_object`/`recv_object` pickle 经 cpu_group（isend/irecv 两段式：size 张量 + 对象张量，支持 tag） |

### 四、自定义算子与 all2all

| 维度 | vLLM | SGLang |
|---|---|---|
| 注册 | `torch.ops.vllm.*`（all_reduce/all_gather/reduce_scatter/fused_scaled_matmul_reduce_scatter），Dynamo 无法传对象 → 以 `group_name` 字符串查表；各算子有 fake 实现供 meta 设备 | `register_custom_op` 注册于 sgl 命名空间（inplace/outplace_all_reduce、flashinfer_allreduce、reg_all_gather/reg_reduce_scatter/reg_all_to_all_single），以 `group_name` 查 `_groups` weakref 表 |
| all2all 后端 | `parallel_config.all2all_backend`：naive/allgather_reducescatter/deepep_high_throughput/deepep_low_latency/deepep_v2/nixl_ep/flashinfer_nvlink(two/one)-sided/mori_high_throughput/mori_low_latency；`All2AllManagerBase` 6 个 manager（AgRs/DeepEPV2/NixlEP/FlashInferNVLink×2/Mori） | 无独立 all2all manager 层：MoE dispatch/combine 走 pynccl `all_to_all_single`/`all_gather`+a2a backend；FlashInfer allreduce fusion 按 workspace 打 hint |
| MoE 组定制 | EP 组承载专家通信（`use_all2all=True` 时）；EPLB 独立分组隔离 MoE 通信防死锁 | `_MOE_EP`/`_MOE_TP` 强制 `use_pynccl=False, use_custom_allreduce=False`；`_fi_workspace_hint` 分发 FlashInfer workspace |
| EPLB 通信器 | `EplbCommunicator`：TorchDistNccl / TorchDistGlooStaged / Nixl / PyNccl 四实现，工厂 `create_eplb_communicator` | 无（EPLB 权重搬迁走 `torch.distributed.P2POp`） |

### 五、backend 选择与 Gloo 定位

| 维度 | vLLM | SGLang |
|---|---|---|
| 平台 backend | CUDA/ROCm `"cpu:gloo,cuda:nccl"`/nccl；CPU gloo；XPU xccl（外部双后端）；`VLLM_DISTRIBUTED_USE_SPLIT_GROUP` 从默认 PG 切分子组 | `platforms.current_platform.get_torch_distributed_backend_str()`：CUDA→"nccl"、CPU→"gloo"；`bootstrap.py` 弹性 EP `elastic_ep_backend=="mooncake"` 时改 "mooncake" |
| Gloo 角色 | cpu_group 控制面：对象广播、barrier、NCCL unique id 分发、`in_the_same_node_as` 节点探测；无独立 Python 类 | 同：元数据通道 + barrier；`send_object`/`recv_object` 控制面 |
| 无 GPU 回退 | CPU 平台走 CpuCommunicator（SHM） | `NaiveDistributed`：文件系统 rendezvous 模拟 all_gather_object/barrier/scatter（测试） |
| 预热 | — | `_prewarm_nccl`（TP/PP/EP 任一 >1 时单次 all_reduce）；`_prewarm_tp_lm_head_all_to_all` 物化 PyNCCL P2P 资源（每 peer 4MB） |

> 关键差异：vLLM 用 **CudaCommunicator 顶层组合器 + All2AllManager 抽象**统一加速通信与 MoE all2all 策略（后端可插拔：DeepEP/NIXL/FlashInfer/Mori）；SGLang 用**分发链直接裁决 + pynccl 强制路径**实现同等能力，并把 MoE/attention 通信组从 TP 组彻底解耦——两者各有取舍，vLLM 策略层更薄而多、SGLang 门面层更薄而组更细。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
