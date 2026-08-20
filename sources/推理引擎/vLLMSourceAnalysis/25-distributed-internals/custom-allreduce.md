## 自研 allreduce 内核：CustomAllreduce 深入

`vllm/distributed/device_communicators/custom_all_reduce.py` 的 `CustomAllreduce` 是 vLLM 的**节点内自研 allreduce/all-gather/reduce-scatter** 实现，CUDA kernel 本体在 `vllm/csrc/custom_all_reduce/`（经 `vllm._custom_ops` 暴露，仓库快照无 csrc 源码）。本文件只读 Python 侧封装，内核行为以封装层证据为准。

### 设计目标与适用条件

- 仅限**单节点**（`in_the_same_node_as(group, source_rank=0)` 全 true），跨节点退化：`mnnvl_only=True`，仅当支持 MNNVL multicast 时保留 custom collectives。
- 依赖 GPU P2P（NVLink/NVSwitch）；同一进程组所有通信器须绑定唯一设备。
- 支持 world size：`_SUPPORTED_WORLD_SIZES = [2, 4, 6, 8, 16]`（allreduce 主路径实际限定 `world_size <= 8`，16 仅用于 AG/RS）。
- 启用条件（逐项否决，任一不满足则 `disabled=True` 并在 `__init__` 返回）：`ops.meta_size()` 可用（排除纯 CPU）；组 backend 非 NCCL（断言）；节点内；world size 受支持；SM capability 存在且 `is_cuda`；`world_size>2` 时 `fully_connected`（经 `current_platform.is_fully_connected(physical_device_ids)` 探测，PCIe-only 多卡禁用）；非 ROCm 时 `_can_p2p(rank, world_size)` 通过（软件/驱动层 P2P 测试）。
- `fully_connected` 判定：各 rank 把**物理设备号**（`visible_device_id_to_physical_device_id`）经 `dist.all_gather` 汇集后调用平台接口。

### 缓冲布局（kernel 数据面）

| 缓冲 | 大小/分配 | 作用 |
|---|---|---|
| `meta_ptrs` | `ops.meta_size() + max_size`，`uncached=True` 共享缓冲 | **同步元数据**（自旋计数器）+ 中间 allreduce 结果暂存 |
| `buffer_ptrs` | `max(max_size, max_all_gather_size, max_reduce_scatter_size)`，预注册 IPC 缓冲 | eager 模式下输入先拷入此缓冲再执行 kernel |
| `rank_data` | 8MB uint8 device 张量 | 存各 rank IPC 缓冲指针元组（每元组 ≤16 地址，8MB 容纳 65536 元组） |

- `create_shared_buffer`：`ops.allocate_shared_buffer_and_handle` 分配 → `dist.all_gather_object` 交换 `handle` → 非本 rank 用 `ops.open_mem_handle(h)` 打开远端 IPC 句柄，得到各 rank 指针列表。
- 初始化序列：`ops.init_custom_ar(meta_ptrs, rank_data, rank, fully_connected)` 返回 `_ptr`（C++ 侧句柄）→ `ops.register_buffer(_ptr, buffer_ptrs)` 注册数据缓冲。
- 跨节点（MNNVL）路径改用 `allocate_shared_buffer_and_handle(ops.meta_size())` 单缓冲复制到各 rank 槽位；MNNVL 缓冲经 `torch.distributed._symmetric_memory` 的 `rendezvous` 分配，`handle.multicast_ptr==0` 表示不支持 multicast，整组禁用。

### 两阶段（two-stage）工作机制

封装层证据：`meta_ptrs` 注释明确"metadata for synchronization and a **temporary buffer for storing intermediate allreduce results**"。内核算法为两阶段层次式 allreduce（kernel 细节见 `csrc/custom_all_reduce/`）：

1. **stage-1 reduce**：各 rank 把自己的输入分块，经 IPC 共享缓冲 + NVLink P2P 读取对端数据，本地归约出部分结果，写入 meta 缓冲的临时区。
2. **stage-2 broadcast/all-gather**：各 rank 把归约结果写回自身缓冲，再 P2P 读取全部 rank 的部分结果，组合出完整输出。

同步用 meta 缓冲中的**自旋计数器**（kernel 内轮询，不做 `cudaStreamSynchronize`），因此整个操作可被 CUDA graph 捕获。`all_reduce` 有两个入口：

```python
ops.all_reduce(self._ptr, inp, out, 0, 0)                          # registered=True，直接归约预注册张量
ops.all_reduce(self._ptr, inp, out, self.buffer_ptrs[self.rank], self.max_size)  # 先拷入预注册缓冲
```

`custom_all_reduce()`（图感知主入口）三种情形：graph 捕获中直接 `registered=True`；warmup 时仅 `torch.empty_like` 模拟 out-of-place 分配；eager 走 `registered=False`（注释：引入一次 `cudaMemcpy`，代价 ≤1% 总时延）。

### 门控 `should_custom_ar`

```python
if self.disabled or self.world_size > 8: return False
if inp_size % 16 != 0: return False        # 字节数须 16 对齐
if not is_weak_contiguous(inp): return False  # 占用单块连续内存即可（非严格 C 连续也可）
if self.world_size == 2 or self.fully_connected: return inp_size < self.max_size
return False                               # ≥4 张非 NVLink 直连卡时收益小于 NCCL
```

`max_size` 默认 8MB；symm_mem 启用时按 `CUSTOM_ALL_REDUCE_MAX_SIZES[SM版本][world_size]` 取 min。`is_weak_contiguous`（`utils.py:85`）是弱连续检查：`storage.nbytes() - storage_offset*itemsize == numel*itemsize` 即通过。

### all_gather / reduce_scatter 扩展与 MNNVL Lamport

- `should_custom_all_gather`：禁用/非 CUDA/`world_size==16 且非 mnnvl_only` 时否决；dtype 限 `float32/float16/bfloat16`；大小上限取 `max_mnnvl_all_gather_size`（multicast 可用时，按 world size 2/4/6/8/16 分别为 8/4/2/2/2 MB）或 `max_all_gather_size`（默认 2MB）；要求 `fully_connected or multicast_ptr`。
- `should_custom_reduce_scatter`：同上 dtype/对齐/大小约束，另要求 `input.shape[0] % world_size == 0`，输出切片 16 对齐。
- 两条路径：MNNVL multicast 可用走 `ops.mnnvl_lamport_all_gather/reduce_scatter`（Lamport 时钟 epoch 同步，`epochs` 为 (2,32) int32 张量），否则走 `ops.custom_all_gather/custom_reduce_scatter`。

### CUDA graph 支持：capture 与 register_graph_buffers

- `capture()` 上下文管理器：进入置 `_IS_CAPTURING=True`，退出时若未禁用则调 `register_graph_buffers()`。
- `register_graph_buffers`：`ops.get_graph_buffer_ipc_meta(_ptr)` 取本 rank 图内缓冲的 IPC handle+offset，因 `all_gather_object` 与 gloo 在 inference mode 不兼容（`pytorch/pytorch#126032`），改用**逐 rank `dist.broadcast_object_list`** 收集，最后 `ops.register_graph_buffers(_ptr, handles, offsets)` 把全组地址注册进 C++ 侧，使捕获期分配的内存地址图回放时固定。

### AITER 变体（v2，ROCm）

`aiter_custom_all_reduce.py` 的 `AiterCustomAllreduce` 是 vLLM 对 AITER `CustomAllreduce` 的薄包装（`VLLM_ROCM_USE_AITER_CUSTOM_AR` 启用），与 fused allreduce+RMSNorm 共用同一实例（`CudaCommunicator.aiter_ar_comm`）：
- `MAX_SIZE = 8192*1024*8*2`，`effective_max_size = MAX_SIZE//2`。
- `supports_dynamic_hidden_dim`：aiter < v0.1.12 的 launcher 对 hidden_dim 模板特化（仅 {512,1024,2048,4096}），v0.1.12 起改为运行时参数；旧版探测方式为 `hasattr(self._impl, "_pool")`。
- `supports_per_group_quant`：AITER ≥ (PR #2823) 暴露 fused AR+RMS+per-group quant kernel，`RocmAiterAllReduceFusionPass` 据此降级到仅 AR+RMS 融合。

### QuickAllReduce（ROCm MI3xx 补充）

`quick_all_reduce.py`，仅 ROCm MI300 系列（`gcnArchName` 含 `gfx94`/`gfx95`），作为 custom allreduce 的补充：
- 支持 world size 2/4/8，dtype 仅 fp16/bf16（bf16 可 `VLLM_ROCM_QUICK_REDUCE_CAST_BF16_TO_FP16=1` 转 fp16）。
- 量化 regime（`QuickReduceRegime`）：FP=0/INT8=1/INT6=2/INT4=3/INT3=4/NONE=5，由 `VLLM_ROCM_QUICK_REDUCE_QUANTIZATION` 选择；**INT3 仅限 TP2**（TP4/8 打包开销超过通信收益）。
- 最小触发大小 `_QR_MIN_SIZE[(dtype, ws)][regime]`（fp16/TP2 起 1MB），上限 `ops.qr_max_size()` 或 `VLLM_ROCM_QUICK_REDUCE_MAX_SIZE_BYTES_MB`；量化阈值 `VLLM_ROCM_QUICK_REDUCE_QUANTIZATION_MIN_SIZE_KB` 以下回落 FP 路径。
- 初始化 `ops.init_custom_qr(rank, world_size, qr_max_size)` → `qr_get_handle` + `all_gather_object` 交换 + `qr_open_handles`；执行 `ops.qr_all_reduce(_ptr, inp, out, qr_quant_level, use_fp16_kernels)`。用静态 IPC 缓冲，**无需独立 graph 模式**。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
