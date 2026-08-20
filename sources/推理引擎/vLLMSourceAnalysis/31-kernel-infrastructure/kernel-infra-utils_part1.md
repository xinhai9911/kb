## Triton / FlashAttention / CUTE / TileLang 内核基础设施（一）

`vllm/triton_utils/`、`vllm/vllm_flash_attn/`、`vllm/cute_utils/`、`vllm/tilelang_utils/` 四个子包构成 vLLM 内核开发的基础设施层：统一 Triton 的探测/占位/分配/调参，包装 CUDA FlashAttention 扩展，提供 CUTE/CUTLASS DSL 手写内核原语，并对 TileLang 做 JIT 封装。被 `kernels/`、`v1/attention/`、`model_executor/layers/`（fused_moe、quantization）等广泛复用。

### triton_utils：Triton 内核开发底座

| 文件 | 职责 |
|---|---|
| `importing.py` | Triton 可用性探测（`HAS_TRITON`）与占位模块 `TritonPlaceholder` / `TritonLanguagePlaceholder` |
| `__init__.py` | 统一 re-export `triton`/`tl`/`tldevice`/`gluon`/`gl`/`aggregate` 及常量 `LOG2E`/`LOGE2`、`use_tensor_descriptor` |
| `allocation.py` | `set_triton_allocator(device)`：把 Triton 编译期内存分配接到 `torch.empty` |
| `force_first_config.py` | 替换 `Autotuner.run`，跳过 autotune 取首个有效 config |
| `tensor_descriptor.py` | `use_tensor_descriptor()` 三态开关 |

- **HAS_TRITON 判定**（`importing.py`）：`find_spec("triton")` 或 `find_spec("pytorch-triton-xpu")`；有 Triton 后进一步检查 `triton.backends` 活动驱动：非分布式环境要求恰有 1 个活动 driver，否则禁用；分布式初始化期（`CUDA_VISIBLE_DEVICES=""`，如 Ray actor 初始化）放宽为 0 个；`vllm` 为 CPU 版时要求存在 `cpu` backend。探测失败一律 `HAS_TRITON=False` 并记录 warning。
- **占位模块**：无 Triton 时 `triton = TritonPlaceholder()`（`__version__="3.4.0"`，`jit`/`autotune`/`heuristics`/`Config` 为恒等装饰器，`cdiv` 转发 `vllm.utils.math_utils.cdiv`），`tl`/`tldevice`/`gluon`/`gl`/`aggregate` 为 `TritonLanguagePlaceholder()`。效果：未装 Triton 时内核模块仍可 import，但 `tl.xxx` 为 None，平台相关函数不可用。
- **分配器**：`set_triton_allocator` 注册 `alloc_fn(size, alignment, stream) -> torch.empty(size, device, dtype=torch.int8)`，让 Triton 中间 tensor 走 vLLM 的设备内存上下文。
- **跳过 autotune**：`force_first_config.install()`（幂等，由 `VLLM_TRITON_FORCE_FIRST_CONFIG=1` 触发，见 `env_override.py`）monkeypatch `Autotuner.run`：按 `(id(self), kwargs 中 keys 的值)` 缓存已选 config 下标；对 `OutOfResources`/`CompileTimeAssertionFailure`/`PTXASError` 跳过下一个 config；无可用 config 则抛 `RuntimeError`。
- **TMA tensor descriptor**：`use_tensor_descriptor(override=None)` 三态：显式 1/0 强制开关；未设置时仅 XPU 平台自动开启（`VLLM_TRITON_USE_TD` 为正式环境变量，`VLLM_TRITON_ATTN_USE_TD` 为已废弃别名）。

**复用方（节选）**：`model_executor/layers/fused_moe/fused_moe.py` 与 `experts/fused_batched_moe.py`、`lora/ops/triton_ops/fused_moe_lora_op.py`、`mamba/gdn/olmo_gdn_linear_attn.py`（`set_triton_allocator`）；`quantization/compressed_tensors/triton_scaled_mm.py`（`set_triton_allocator` + `use_tensor_descriptor`）；`v1/attention/backends/triton_attn.py` 与 `v1/attention/ops/triton_unified_attention.py`（`use_tensor_descriptor` 决定 TMA 布局）。

### vllm_flash_attn：CUDA FlashAttention 扩展包装

`flash_attn_interface.py` 只维护两个 wrapper（源码注释："we only maintain wrappers for these two"）：`flash_attn_varlen_func` 与 `flash_attn_with_kvcache`。ROCm 不使用本包（改用上游 `flash_attn`）。

| 能力标志 | 来源 | 计算能力约束 |
|---|---|---|
| `FA2_AVAILABLE` | import `_vllm_fa2_C` | ≥ 8.0（`has_device_capability(80)`） |
| `FA3_AVAILABLE` | import `_vllm_fa3_C` | 9.x（`is_device_capability_family(90)`） |
| `FA4_AVAILABLE` | `cute/interface.py` 存在 | 9.x / 10.x / 11.x |

- `is_fa_version_supported(fa_version)` / `fa_version_unsupported_reason`：attention backend 据此选择 FA 版本（`v1/attention/backends/fa_utils.py:get_flash_attn_version`）。
- `flash_attn_varlen_func(q, k, v, ...)` 统一入口，按 `fa_version`（默认 2）分流：

| 版本 | 底层调用 | 特征 |
|---|---|---|
| FA2 | `torch.ops._vllm_fa2_C.varlen_fwd` | 不支持 `scheduler_metadata`/`q/k/v_descale`/`num_splits>1`/`mask_mod` 等 |
| FA3 | `torch.ops._vllm_fa3_C.fwd` | 需 `scheduler_metadata`（`get_scheduler_metadata` 预生成）；不支持 alibi |
| FA4 | `vllm.vllm_flash_attn.cute.interface._flash_attn_fwd` | 支持 `mask_mod`/`block_sparse_tensors`/`aux_tensors`/`output_scale`；SM90 且 K 为 fp8_e4m3fn 时走 fp8 KV 反量化路径（K/V descale 折叠进内核，仅转发 `(batch, num_kv_heads)` 的 f32 descale） |

- `compile_flash_attn_varlen_func_from_specs`：仅 FA4 的 compile-only 包装（不支持 dropout）。
- `__init__.py`：symlink 模式下（`VLLM_FLASH_ATTN_SRC_DIR`）cute/ 为真实源码树符号链接，其文件用 `flash_attn.cute.*` import，故先注册虚拟 `flash_attn` 包再 import；`FA2/FA3` 均不可用时抛 `ImportError`。
- 消费方：`v1/attention/backends/flash_attn.py`、`flash_attn_diffkv.py`（`fa_version=` 透传）、`sparse_mla_attention.py`、`models/dots3_note/`、`kimi_k3`/`inkling` 模型 op、`rotary_embedding/common.py`（`apply_rotary_emb`）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
