## Triton / FlashAttention / CUTE / TileLang 内核基础设施（二）

### cute_utils：CUTE/CUTLASS DSL 手写内核原语

基于 `cutlass` Python 库（`cutlass.cutlass_dsl`、`cutlass._mlir`、`cute.nvgpu`），全部函数以 `@dsl_user_op` 暴露，经 MLIR 编译期展开（函数签名带 `loc=None, ip=None`）。主要供 Kimi/DeepSeek 等 NVIDIA 专有模型 CuteDSL op 使用。

| 文件 | 内容 |
|---|---|
| `__init__.py` | dtype 映射、TMA/`mma_sync`、bf16x2 位级运算 |
| `_tcgen05.py` | SM90+ tensor memory（tmem）与 `tcgen05.*` 指令封装 |
| `cvt.py` | 打包/解包数值转换（fp32/bf16/fp8/fp4） |
| `mbarrier.py` | mbarrier `arrive` / `arrive_expect_tx` |

- **__init__.py 关键项**：`_TORCH_TO_CUTE_DTYPE`（bf16/fp8_e4m3fn/fp32）与 `_CUTE_TO_PTX_DTYPE`（bf16/f16/e4m3/f32）；`EVICT_NORMAL/FIRST/LAST`（来自 `cute/arch/copy_sm90_desc.hpp`）；`recast_val`（llvm.bitcast 重解释）；`to_cta0_smem`（global 地址 `& 0xFEFF_FFFF` 转 shared 地址空间指针）；`simple_tma_copy`（包装 `CopyBulkTensorTileG2SOp/S2GOp` 的 `tma_partition`+`group_modes`+`cute.copy`，支持 `tma_bar_ptr` 与 cache policy）；`fence_before_tma_store`（PTX `fence.proxy.async...`）；`mma_sync`（PTX `mma.sync.aligned.m16n8k{K}.row.col`，K=256/位宽，SSA fragment 先落寄存器再重解释为 Int32）；`_bf16x2_abs/neg/max/mul.rn/sub.rn`（对打包 bf16x2 的内联汇编单目/双目运算）。
- **_tcgen05.py**：命名避开 `cute.nvgpu.tcgen05` 冲突。`alloc`/`dealloc`（`tcgen05_alloc/dealloc`，cta_group 1/2）；`make_bf16_idesc`（按位构造 MMA 指令描述符，含 negate/transpose 位）；`make_sdesc_128B_swizzle`；`mma_f16`/`mma_ts_f16`（`tcgen05_mma`，后者 A 操作数也来自 tmem）；`commit`（`tcgen05_commit`，支持 multicast mask）；`ld`/`st`（`tcgen05_ld/st`，shape `32x32b`/`16x128b`/`16x256b` 映射寄存器数 1/2/4）；`fence_before/after_thread_sync`、`wait_ld`/`wait_st`。
- **cvt.py**：`fp32x2_to_bf16x2`、`bf16x2_to_fp32x2`（shl/and 解包）、`fp8x4_to_bf16x4`（经 fp16 中转，因 PTX 只有 fp8→fp16）、`fp32x2_to_fp8x2`、`fp8x4_to_fp16x4`、`fp32x4_to_fp8x4`、`fp32x8_to_fp4x8`（`cvt.rn.satfinite.e2m1x2.f32`）。
- **消费方**：`models/deepseek_v32/nvidia/ops/fused_q_cutedsl.py`、`models/kimi_k3/nvidia/ops/cute_dsl/gemm_rs.py`（`_tcgen05`+`mbarrier`+`simple_tma_copy`）、`models/deepseek_v4/nvidia/ops/fused_indexer_q_cutedsl.py`、`fused_moe/router/bf16x3_router_gemm_cutedsl.py`、`model_executor/kernels/attention/dsa/dcp_indexer_cutedsl.py`（`recast_val`）、`models/minimax_m3/nvidia/ops/index_decode_score.py`。

### tilelang_utils：TileLang JIT 封装

`tilelang_utils/__init__.py` 提供 `tilelang_jit` 装饰器与 `T`/`tilelang` 模块级句柄：

- 导入策略：CUDA 平台 import 时即要求 TileLang（未装则 `ImportError` 提示 `pip install tilelang`）；ROCm 延迟到首次内核调用（`_ensure_tilelang_imported`），并把 `T`/`tilelang` 注入被装饰函数的 `__globals__`。
- 统一 pass 配置（`_get_pass_configs`，`functools.cache`）：`TL_DISABLE_WARP_SPECIALIZED=True`、`TL_DISABLE_TMA_LOWER=True`；CUDA 上另设 `TL_PTXAS_REGISTER_USAGE_LEVEL=10`。
- 消费方：`model_executor/kernels/mhc/tilelang_kernels.py`（8 个 `@tilelang_jit` 内核）；`utils/jit_monitor.py` 挂钩 TileLang `JITImpl.compile` 记录编译耗时。

### 基础设施复用总览

| 基础设施 | 内核 / 注意力 / 量化消费方 |
|---|---|
| `triton_utils`（分配器/占位/TD/跳过 autotune） | fused_moe、fused_batched_moe、compressed_tensors/triton_scaled_mm、mamba/gdn、lora/fused_moe_lora_op、triton_attn、triton_unified_attention |
| `vllm_flash_attn`（FA2/3/4 统一 wrapper） | flash_attn、flash_attn_diffkv、sparse_mla_attention、fa_utils、dots3_note、rotary_embedding |
| `cute_utils`（CUTE/DSL 原语） | kimi_k3、deepseek_v32/v4、minimax_m3、bf16x3_router_gemm、dcp_indexer_cutedsl |
| `tilelang_utils`（JIT 封装） | mhc/tilelang_kernels |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
