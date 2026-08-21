## 分布式并行状态（srt/distributed）· 通信算子与 vLLM 对照

分组建模与 GroupCoordinator 见 [parallel-state_part1.md](parallel-state_part1.md)。本文覆盖通信算子分发链、设备通信器与 vLLM 差异。

### 通信算子门面（communication_op.py）

全部为 `GroupCoordinator` 的薄包装，委托 `get_tp_group()` / `get_attn_tp_group()` / `get_moe_ep_group()` / `get_moe_tp_group()`：

| 函数 | 委托 | 说明 |
|---|---|---|
| `tensor_model_parallel_all_reduce` | `get_tp_group().all_reduce` | 默认 TP 组全归约 |
| `tensor_model_parallel_quant_all_reduce` | `get_tp_group().quant_all_reduce` | NPU 专用量化归约 |
| `tensor_model_parallel_all_gather` / `gather` | `all_gather(dim=-1)` / `gather(dst=0, dim=-1)` | concat 语义 / dst 为组内本地 rank |
| `broadcast_tensor_dict` | `get_tp_group().broadcast_tensor_dict` | 未初始化时原样返回 |
| `attention_tensor_model_parallel_all_reduce` | `get_attn_tp_group()` | DP-attention 下 ATT 组 ≠ TP 组 |
| `moe_tensor_model_parallel_all_reduce` / `moe_expert_parallel_all_reduce` | `get_moe_tp_group()` / `get_moe_ep_group()` | MoE 独立组归约 |
| `tensor_model_parallel_fused_allreduce_rmsnorm` | `fused_allreduce_rmsnorm` | ROCm：AR+RMSNorm 融合（1-stage≤128KB，否则 2-stage；TC piecewise graph 走 `fused_ar_rms`） |
| `tensor_model_parallel_fused_allreduce_rmsnorm_quant_per_group` | `fused_allreduce_rmsnorm_quant_per_group` | ROCm/gfx95：AR+RMSNorm+per-group FP8 量化，`emit_bf16=True` 时额外返回 bf16 输出；不支持返回 None |

### all_reduce 分发链（parallel_state.py:648）

```
world_size==1 → 直接返回输入
CPU 张量      → torch.ops.sgl_kernel.shm_allreduce（LOCAL_SIZE 生效）否则 dist.all_reduce(device_group)
HPU/XPU/NPU  → 对应 communicator（XPU 经 inplace_all_reduce 自定义算子，防 Dynamo 分解为
               _c10d_functional 触发 sycl_event.wait() 破坏 XPU graph capture）
torch.compiler 编译中 → flashinfer_allreduce（_can_use_flashinfer_allreduce）
                       : 无任何加速通信器 ? inplace_all_reduce : outplace_all_reduce("auto")
eager 下依次裁决：pymscclpp(should_mscclpp_allreduce) > ca(should_custom_ar) > flashinfer >
                 _resolve_outplace_all_reduce_method: ca > qr > pymscclpp > torch_symm_mem > pynccl
```

- 对称内存开启时优先 `pynccl_comm.all_reduce(input_)`（in-place，经 `debug_check_symmetric_mempool` 校验）。
- `_all_reduce_in_place` 兜底：pynccl → torch_symm_mem（`out=input_`）→ `dist.all_reduce(device_group)`。
- `outplace_all_reduce` 的 `pymscclpp` 分支需 `input_.clone()` 满足自定义算子不改输入的约定；"auto" 且无可选方法时若存在 pynccl 则强制 pynccl（graph-capture 安全、NCCL 天然 out-of-place，免 clone）。
- **自定义算子**：因 Dynamo 无法传对象，`inplace_all_reduce`、`outplace_all_reduce`、`flashinfer_allreduce`、`reg_all_gather_into_tensor`、`reg_reduce_scatter_tensor`、`reg_all_to_all_single` 均经 `register_custom_op` 注册，以 `group_name` 字符串查 `_groups`（weakref 表）取回 GroupCoordinator 分发。

### 其余集合方法要点

| 方法 | 行为要点 |
|---|---|
| `all_gather` | concat 风格（`all_gather_into_tensor`），`world_size==1` 短路；CPU 走 `sgl_kernel.shm_allgather`；ROCm aiter 自定义 all-gather（`SGLANG_USE_AITER_AG`，16B 对齐/弱连续校验） |
| `all_gatherv` | 变长版本，**强制 pynccl**（`group_start/group_end` 批量执行）；支持预分配 output 缓冲 |
| `reduce_scatter` | `reduce_scatter_tensor` 前必须 `movedim(dim,0).contiguous()`（NCCL reduce_scatter 非连续 bug）；ROCm 可选 aiter custom reduce-scatter（`SGLANG_DP_USE_REDUCE_SCATTER`） |
| `reduce_scatterv` | 变长，强制 pynccl，支持 `sizes` |
| `all_to_all_single` | pynccl 优先（DCP a2a 后端，CUDA graph 可捕获），否则 `dist.all_to_all_single` |
| `gather/broadcast` | dst/src 为**组内本地 rank**，实现内转全局 rank |
| `send/recv` | pynccl 优先（TP LM-head a2a 用），否则 `dist.send/recv(device_group)` |
| `send_object/recv_object` | pickle 序列化经 **cpu_group**（isend/irecv 两段式：size 张量 + 对象张量，支持 `tag`） |
| `broadcast_object` | 有 `mq_broadcaster` 走共享内存（仅 src=0）；否则 cpu_group `broadcast_object_list` |
| `broadcast_tensor_dict` | 元数据（`TensorMetadata` namedtuple）走 cpu_group，张量按 CPU/GPU 分走 metadata_group/device_group 异步 broadcast |
| `send_tensor_dict/recv_tensor_dict` | 支持 `all_gather_group` 优化：只发切片，收端 `all_gather(dim=0)` 重建全量 |
| `barrier` | 强制 cpu_group（NCCL barrier 内部是隐式 GPU 张量 broadcast，易污染当前设备） |

`utils.py`：`get_pp_indices` 层划分（`SGLANG_PP_LAYER_PARTITION` 可覆盖，余数从末尾倒数第 2 个分区起加）；`StatelessProcessGroup` 基于 TCPStore 的元数据交换（send/recv/broadcast/all_gather/barrier，不污染默认 PG，供弹性 EP 用）；全局 TCPStore 存于 `ctx.resources`，NIXL 缓冲协调复用。

### 平台 backend

- `get_default_distributed_backend(device)`（`:2157`）：当前平台走 `platforms.current_platform.get_torch_distributed_backend_str()`，其余查 `_DEVICE_TO_DISTRIBUTED_BACKEND`（`platforms/device_mixin.py`）。CUDA 返回 "nccl"，CPU "gloo"（`platforms/cuda.py:60`）。
- `bootstrap.py`：`device=="cuda"` 且 `elastic_ep_backend=="mooncake"` 时 backend 改 "mooncake"；`_prewarm_nccl` 在 TP/PP/EP 任一 >1 时用 `get_tp_group().device_group` 做单次 all_reduce 预热；`_prewarm_tp_lm_head_all_to_all` 物化 PyNCCL P2P 资源（每 peer 4MB 预热）。
- `NaiveDistributed`：无 GPU 环境（测试）下用文件系统模拟 all_gather_object/barrier/scatter。

### 与 vLLM distributed 对照

| 维度 | vLLM | SGLang |
|---|---|---|
| 来源 | vllm/distributed | 显式标注改编自 vLLM v0.6.4.post1（进一步上溯 Megatron-LM） |
| 并行组 | world/TP/PCP/PP/DP/EP/EPLB/DCP | world/TP/PP + 扩展 ATTN_CP/ATTN_TP/ATTN_CP_OVERLAP/DCP/MOE_DP/MOE_EP/MOE_TP（无独立 EPLB 组） |
| EPLB | `_EPLB` 独立通信组（parallel_state 内） | **无** EPLB 通信组；EPLB 是独立 `srt/eplb/` 模块（在线重均衡），详见 [eplb_part1.md](eplb_part1.md) |
| backend | nccl/gloo 双 PG | 相同；另支持 `mooncake` backend（active_ranks mask + `MooncakeBackendOptions`）与 NPU HCCL `pg_options`（`get_torch_distributed_pg_options`） |
| 加速通信器 | CudaCommunicator + custom allreduce/pyncnl | PyNccl / CustomAllreduce / QuickAllReduce(ROCm) / PyMscclpp / TorchSymmMem / shm_broadcast / HPU / NPU / XPU 通信器 |
| 自定义算子 | `torch.ops.vllm.*`，`group_name` 字符串参数 | `register_custom_op` 注册于 sgl 命名空间，同以 `group_name` 查表 |
| MoE 组定制 | EP 组承载专家通信 | MOE_EP/MOE_TP 强制禁用 PyNccl/CAR；FlashInfer allreduce fusion 按 workspace 打 `_fi_workspace_hint` |
| DP-attention | DP 即数据并行 | `_ATTN_TP/_ATTN_CP/_ATTN_CP_OVERLAP` 与 TP 解耦（`attn_tp = tp/cp/dp`），`_MOE_DP` 与 CP 组别名共享 token |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
