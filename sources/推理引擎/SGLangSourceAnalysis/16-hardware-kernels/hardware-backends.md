## SGLang 硬件后端：hardware_backend 平台目录与调度衔接

`python/sglang/srt/hardware_backend/`（约 78 个 .py，6 个平台子目录）不是一套「后端抽象类」，而是一个**按设备平台组织的扩展目录**：顶层无 `__init__.py`，各平台目录被 `srt/` 各组件按需懒加载。真正的「后端抽象」分两处：注意力走 `srt/layers/attention/base_attn_backend.py::AttentionBackend`（见 07-attention），内核实现走 `sglang/kernels/fused_op.py::BaseFusedOp`（见本文档姊妹篇 kernels-overview）。本模块聚焦平台目录本身。

### 平台目录总览

| 子目录 | 平台 | 核心文件 | 定位 |
|---|---|---|---|
| `gpu/` | NVIDIA/通用 CUDA | `quantization/awq_kernels.py`、`gptq_kernels.py` | 仅量化 kernel 的平台分派壳 |
| `cpu/` | CPU（x86/AMX） | `quantization/awq_kernels.py`、`gptq_kernels.py` | 与 gpu 同构的 CPU 量化 kernel |
| `npu/` | Ascend NPU | `attention/`（6 个后端）、`graph_runner/`、`moe/`、`quantization/`、`dsv4/`、`batch_invariant_ops/` | 最完整的独立平台移植（约 41 文件） |
| `mlx/` | Apple Silicon | `model_runner.py`、`tp_worker.py`、`kv_cache/`、`aot.py`、`sampling.py`、`moe/`、`scheduler_mixin.py` | 用 mlx-lm 托管模型的完整 MLX 运行栈 |
| `musa/` | Moore Threads MUSA | `attention/flashattention_backend.py`、`kernels/topk.py`、`utils/patch_torch.py` | 注意力+少量 kernel 适配 |
| `xpu/` | Intel XPU | `graph_runner/xpu_full_graph_backend.py`、`kernels/fla/` | CUDA Graph 后端 + 线性注意力内核 |

### gpu/ 与 cpu/：量化内核的平台分派

两个 `quantization/` 目录分别是 AWQ/GPTQ 量化 scheme 的平台侧「kernel 选择器」，由 `srt/layers/quantization/*/schemes/` 引用。`gpu/quantization/awq_kernels.py` 的分派链（按平台依次尝试）：

| 平台分支 | 选择的 awq_dequantize 实现 | 出处 |
|---|---|---|
| XPU | `sgl_kernel.awq_dequantize` | `sgl_kernel` 轮子 |
| HIP | `awq_dequantize_triton` | `kernels/ops/quantization/awq_triton.py` |
| 其余(CUDA) | `ops/quantization/awq_dequantize` → Triton 回退 → `sgl_kernel` | CUDA 优先 JIT 算子，失败逐级回退 |

- 未命中任何平台时兜底 `_unsupported_awq_dequantize`（抛 `RuntimeError`）。
- `awq_dequantize` 经 `register_custom_op_from_extern`（`srt/utils/custom_op.py`）注册 `fake_impl`，供 torch.compile 图内使用（`awq_kernels.py:59`）。
- 同文件的 `AWQLinearKernel` / `AWQMarlinLinearKernel` / `AWQMoEKernel` 是对量化层的三个 kernel 门面：`process_weights_after_loading` 做 Marlin repack/permute（`awq_marlin_repack`、`marlin_permute_scales`、`marlin_moe_permute_scales`），`apply` 走 `apply_awq_marlin_linear` / `MoeRunner.run`。
- 消费方：`layers/quantization/awq/schemes/awq_linear.py`、`awq_marlin.py`、`awq_moe.py`（gpu），`awq_cpu.py`（cpu）；gptq 同理（`gptq_marlin.py`、`gptq_moe.py`、`gptq_linear.py` / `gptq_cpu.py`），compressed_tensors 的 WNa16 MoE 也引 gpu/gptq_kernels。

### npu/：Ascend 深度移植

`npu/attention/` 提供 6 个 `AttentionBackend` 子类，均继承 `srt/layers/attention/base_attn_backend.py`（接口见 07-attention/attention-backends.md），并注册进 `attention_registry`（注册名 `ascend` 系列）：

| 文件 | 后端类 | 覆盖场景 |
|---|---|---|
| `ascend_backend.py`（3007 行） | `AscendAttnBackend` | 主力后端：FIA/NZ 格式、`sgl_kernel_npu.attention`、Triton 掩码构建、MLS/DSA 辅助 |
| `ascend_dsv4_backend.py` | `AscendDsv4AttnBackend` | DeepSeek-V4 注意力（2110 行） |
| `ascend_kda_backend.py` | `AscendKDAAttnBackend` | Kimi K3 KDA 线性注意力 |
| `ascend_gdn_backend.py` | `AscendGDNAttnBackend` | GDN（gated delta network） |
| `ascend_hybrid_linear_attn_backend.py` | `AscendHybridLinearAttnBackend` | 混合线性注意力 |
| `ascend_torch_native_backend.py` | `AscendTorchNativeAttnBackend` | torch 原生回退 |

配套模块：`mla_preprocess.py`（MLA FIA-NZ 预处理开关）、`npu/moe/`（topk、fuseep、init/finalize_routing、matmul、quant）、`npu/quantization/`（linear_method_npu、moe_methods、online_moe_methods）、`npu/dsv4/`（c128_sidecar、dsv4_allocator、rope、memory_pool）、`npu/modules/`（deepseek_v2_attention_mla、glm46v/minimax_m3/qwen_vl processor）、`npu/graph_runner/`（`npu_cudagraph_backend.py` 及 eagle/vit graph runner）。

### mlx/：Apple Silicon 独立运行栈

与其它平台不同，mlx/ 是**一整套模型运行栈**（复用 mlx-lm）：

| 文件 | 职责 |
|---|---|
| `model_runner.py` | MLX 版 ModelRunner：从 `MlxAttentionKVPool` 读 KV、恢复原生辅助层状态、前向后写回；暴露 `*_start`/`*_finalize` 懒求值接口供 overlap 调度流水 CPU 簿记与 GPU 执行 |
| `kv_cache/` | `ContiguousAttentionKVCache`（全注意力）、`WindowedAttentionKVCache`（SWA）、`MlxAttentionKVPool`、`MLXAttentionWrapper`、`patch_model_attention`；共享池只存全注意力层，SWA 前缀命中会重算整段前缀 |
| `aot.py` | AOT 内核选择：`sgl_kernel.metal.rope_pool_fused`（Metal 原生内核，经 `setup_metal.py` 构建），`MlxAOTKernelSet` 注册表 |
| `moe/`、`sampling.py`、`tp_worker.py`、`scheduler_mixin.py` | MoE（fused_swiglu）、采样/对数概率、TP worker、调度 mixin |

### musa/ 与 xpu/

- `musa/attention/flashattention_backend.py`（951 行）：MUSA 版 FlashAttention 后端（07-attention 表中 `fa3` 的 MUSA 变体 `MusaFlashAttentionBackend`）。
- `musa/utils/patch_torch.py`：torch 行为修补；`layers/utils/cp_utils.py`：上下文并行工具。
- `xpu/graph_runner/`：`xpu_full_graph_backend.py`（100 行）等 XPU CUDA-Graph 替代；`xpu/kernels/fla/`：线性注意力 Triton 内核（chunk_delta_h、chunk_fwd、fused_sigmoid_gating_recurrent）。

### 与其它模块的衔接

| 衔接点 | 机制 | 位置 |
|---|---|---|
| 注意力（07） | NPU 后端实现 `AttentionBackend` 接口并注册；`attention_backend_setup.py` 在 `_build_full_attention_backend_from_str` 选中后，NPU 平台懒加载 `hardware_backend.npu.utils::lazy_init_zbal_gva_mem` | `model_runner_components/attention_backend_setup.py` |
| CUDA Graph（模型运行器） | `runner_backend/utils.py` 按平台懒导入：NPU → `npu_cudagraph_backend`，XPU → `xpu_full_graph_backend` | `model_executor/runner_backend/utils.py` |
| batch_invariant_ops | 用 `torch.library` 覆盖 aten 算子（`mm`/`addmm`/`bmm`/`_log_softmax`/`mean.dim`/`rms_norm`），dispatch key 取 `get_dispatch_device_backend()`（CUDA/XPU/NPU）；NPU 覆盖来自 `npu/batch_invariant_ops/npu_batch_invariant_ops.py` | `srt/batch_invariant_ops/batch_invariant_ops.py:1061` |
| compilation | `make_backend` 按平台选 piecewise 编译后端（CUDA/NPU/XPU），OOT 平台走 `current_platform.get_piecewise_backend_cls()`；`srt/compilation/` 整体改编自 vLLM v0.10.0 `compilation/backend.py` | `srt/compilation/backend.py:43` |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
