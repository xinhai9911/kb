## SGLang 内核族、JIT/AOT 基础设施与 vLLM 对照（二）

续 kernels-overview.md（一）。本文枚举 `sglang/kernels/ops/` 各算子组的内核族、说明 `jit/` 与 `aot/`（sgl_kernel 轮子）如何支撑实现，并对照 vLLM 的 kernels/compilation。

### ops/ 算子组与内核族（按功能枚举）

| 组 | 代表内核 | 功能族 |
|---|---|---|
| `attention` | `decode_attention_fwd`、`extend_attention_fwd`、`context_attention_fwd`（prefill）、`merge_state_triton`、`metadata`/`dsa_metadata`（`get_num_kv_splits_triton`、`prepare_swa_spec_page_table_triton`）、`verify_splitkv_fwd`、`pad`、`position` | Triton 注意力 decode/extend/prefill、元数据、投机验证 |
| attention·FA 族 | `flash_attention.py`（fa2）、`flash_attention_v3.py`、`flash_attention_v4.py`、`flash_attention_v4_sm120.py`、`fa4_sm120/` | FlashAttention 2/3/4 与 Blackwell SM120 包装 |
| attention·MLA | `flash_mla_sm120.py`、`flash_mla_sm120_triton.py`、`mla_kv_pack_quantize_fp8.py`、`set_mla_kv_concat_q.py`、`fused_metadata_copy.py`、`verify_mla.py` | MLA 内核与量化打包 |
| attention·RoPE/Norm | `rope.py`、`rotary_triton.py`、`vision_rope.py`、`fused_qknorm_rope.py`、`fused_qk_rmsnorm_rope_gate.py`、`fused_qk_norm_rope_store.py` | RoPE 与 QK-Norm+RoPE 融合 |
| attention·稀疏/线性 | `dsa/`、`dsv4/`、`deepseek_v4_rope.py`（DeepSeek 稀疏注意力）；`fla/`（`chunk_gated_delta_rule`、`fused_recurrent_gated_delta_rule`）、`linear/`（`seg_la_fwd`、`lightning_attention`）、`kda_fused_decode.py`、`triton_gdn_fused_proj.py`（Kimi K3）；`minimax_sparse/`（`flash_decode_with_topk_idx`） | DSA/DSV4、Flash Linear Attention、KDA/GDN、MiniMax 稀疏 |
| attention·cutedsl | `cutedsl_fp8_paged_mqa_logits.py`、`cutedsl_gdn.py`、`cutedsl_kda.py`、`cutedsl_gdn_mtp_ring.py` | CUTE DSL 手写内核（decoding、GDN、KDA、MTP ring） |
| `activation` | `silu_and_mul`、`softcap` | 门控激活 |
| `communication` | `all_reduce.py`、`inkling_ar_fused.py`、`inkling_all_reduce.py`、`mp.py` | 自研/Inkling all-reduce |
| `elementwise` | `add3.py`、`add_constant.py`、`elementwise.py`（fused_pointwise 合集，含 `fused_rmsnorm`/`fused_dual_residual_rmsnorm`） | 逐元素融合 |
| `embeddings` | `vocab_parallel_embedding.py` | 词嵌入 |
| `gemm` | `dsv3_router_gemm.py`、`dsv3_fused_a_gemm.py`、`fp8_blockwise_gemm.py`、`hopper_bf16_gemv.py`、`sm120_fp8_gemv.py`、`tiny_gemm.py`、`chunked_sgmv_shrink/expand.py`、`sgemm_lora_a/b.py`、`qkv_lora_b.py`、`cutedsl_bf16_gemm.py` | DeepSeek-V3 路由/融合 GEMM、FP8、LoRA SGMM 系 |
| `grammar` | `bitmask_ops.py`、`token_filter_ops.py` | 结构化生成位掩码 |
| `kvcache` | `kvcache.py`、`cache_ops.py`、`reshape_and_cache_flash`（源自 triton_store_cache）、`mla_buffer.py`、`hicache.py`/`hisparse.py`、`zero_pages.py`、`fused_fp8_qkv_kv_cache.py` | KV 写回/索引/MLA 缓冲/分层 cache |
| `layernorm` | `rmsnorm`、`fused_add_rmsnorm`、`gemma_rmsnorm`（BaseFusedOp 范式，见（一））；`mhc.py`、`gemma4_fused_ops.py` | RMSNorm 族、多头压缩(MHC)头 |
| `lplb` | `cublasdx_solver.py`、`cuda_solver.py`、`torch_solver.py`、`shmem_budget.py` | 最小填充 LoRA 批处理（LPLB）求解器 |
| `mamba` | `causal_conv1d.py`、`causal_conv1d_triton.py`、`mamba_state_*_triton.py`、`inkling_sconv.py` | 线性注意力/状态搬运 |
| `memory` | `allocator.py`、`memcpy_triton.py`、`virtual_slot.py`、`gpu_tensor_hash.py` | 设备内存原语 |
| `moe` | `moe_align.py`、`gate_topk.py`、`moe_topk_softmax/sigmoid.py`、`triton_hash_topk.py`、`fused_moe_triton_kernels.py`、`ep_moe_kernels.py`、`deepep_waterfill_kernels.py`、`moe_wna16_marlin.py`、`mxfp8_moe_amd_gfx95.py`、`moe_front.py` | 对齐/路由 topk/EP/量化 MoE GEMM |
| `quantization` | `awq_dequantize.py`、`awq_triton.py`、`awq_marlin_repack.py`、`gptq_marlin(_repack).py`、`fp8_kernel.py`、`fp8_quantize.py`、`per_token_quant_fp8.py`、`mxfp8_quant.py`、`nvfp4_gemm_swiglu_nvfp4_quant.py`、`int8_kernel.py`、`hadamard.py` | AWQ/GPTQ/Marlin、FP8/MXFP8/NVFP4/INT8 量化与 GEMM |
| `sampling` | `top_p_renorm_triton.py`、`renorm_triton.py`、`murmur_hash.py` | 采样惩罚重归一 |
| `speculative` | `eagle.py`、`multi_layer_eagle.py`、`dflash.py`、`ngram_*.py`、`reject_sampling.py`、`spec_tree.py`、`ragged_verify_kernels.py` | 投机解码全套 |
| `kimi_k3` / `kv_canary` / `diffusion` / `mm` | K3 特化（attn_res、sp_collective）；KV canary 校验；扩散模型组 | 模型/工具专属 |

### jit/ 与 aot/：两套 CUDA 实现源

| 层 | 内容 |
|---|---|
| `jit/` | `utils/compile/loader.py::load_jit`：以 args + csrc 相对路径 + `(export_name, kernel_name)` wrapper 列表构造 `BuildSpec` → ninja 生成 → 缓存键命中（`cache.compute_build_key`）→ 未命中在 staging 目录构建后原子 rename 发布；`_build_lock`（fcntl flock）把 TP 多 rank 冷缓存并发编译合并为一次（注释实测 8 rank 14.0s→9.0s）；产物用 `tvm_ffi.load_module` 加载。`include/sgl_kernel/` 提供 cta/tile/warp/mbarrier/atomic 等 CUDA 原语头；`csrc/` 按功能目录存放 .cuh |
| `aot/` | `sgl_kernel` 轮子源码：`python/sgl_kernel/`（`allreduce.py`、`attention.py`、`flash_attn.py`、`flash_mla.py`、`gemm.py`、`moe.py`、`quantization/`、`sampling.py`、`grammar.py`、`kvcacheio.py`、`metal.py`、`musa.py` 等）+ `csrc/`（`common_extension.cc` 及 allreduce/attention/elementwise/cpu/cutlass_extensions/…）+ `pyproject{,_rocm,_musa,_cpu}.toml`、`setup_metal.py` |

`ops` 公开包装默认钉在 AOT（稳定轮子边界、形状支持最广）；JIT 并行注册做库存，签名不同时显式 `select_kernel("layernorm.rmsnorm", backend=KernelBackend.JIT)`（README 例）。

### 与 layers(10)、attention(07) 的衔接

- `srt/layers/` 直接 `from sglang.kernels.ops...`：`activation.py`（silu_and_mul 族）、`logits_processor.py`（softcap）、`attn_residual.py`/`k3_*`（kimi_k3 族）、`dp_attention.py`（memory.memcpy_triton、quantization.fp8_kernel）。
- 量化 scheme（10-layers 的 `scheme` 概念）→ `hardware_backend/gpu|cpu/quantization/*_kernels.py` → 再落到 `ops.quantization.*` 或 `sgl_kernel`（见 hardware-backends.md）。
- 注意力（07）：`ops/attention` 的 Triton 内核即 `layers/attention/triton_ops` 与 `model_executor` 迁移而来（`ops/attention/__init__.py` 注明）；`flash_mla_sm120` 等支撑 `FlashMLABackend` 等 MLA 后端。

### 与 vLLM kernels/compilation 对照

| 维度 | vLLM | SGLang |
|---|---|---|
| 算子入口 | `vllm/_custom_ops.py` 封装 `torch.ops._C*`（C++ 注册） | `sglang.kernels.ops.*` 薄包装 + `KernelSpec` 元数据注册（RFC #29630） |
| 多后端/多平台 | 按平台 import 分支 | `BaseFusedOp` 统一契约：`forward_<backend>` × `forward_<device>` + 分派优先级 + 全局强制开关 |
| Triton 基础设施 | `vllm/triton_utils/`（探测/占位/分配器/跳过 autotune） | `kernels/jit/utils/`（ninja 构建、缓存、跨进程构建锁、tvm_ffi 加载） |
| AOT 内核 | `csrc/` + `libtorch_*` 编译入包 | `kernels/aot/` 独立 `sgl_kernel` 轮子（多平台 pyproject 变体） |
| 编译 | `vllm/compilation/` | `srt/compilation/`（明确注明 Adapted from vLLM v0.10.0 backend.py），按平台选 piecewise backend |
| torch.compile 集成 | `@register_fake` | `enter/leave_torch_compile` 模式协议 + `@debug_kernel_api` 日志钩子 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
