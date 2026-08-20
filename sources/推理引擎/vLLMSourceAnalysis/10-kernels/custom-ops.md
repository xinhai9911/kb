## vLLM 自定义算子 Python 封装（vllm/_custom_ops.py）

文件：`vllm/_custom_ops.py`（约 4240 行）。模型各层不直接调 C 内核，统一经此模块封装 `torch.ops._C*` 系列算子（在 `csrc/` 用 `torch.library` 注册）。加载时执行 `current_platform.import_kernels()` 载入内核库；多数算子附 `@register_fake` 供 torch.compile。

### 底层命名空间

| 命名空间 | 注册位置（csrc） | 覆盖 |
|---|---|---|
| `torch.ops._C` | `libtorch_stable/torch_bindings.cpp` | 通用 CUDA/CPU：norm、rope、quant、mamba、融合算子、SM100 MLA |
| `torch.ops._C_cache_ops` | 同文件 | KV Cache：reshape_and_cache、concat_and_cache_mla、swap_blocks、cp_gather_*、convert_fp8 |
| `torch.ops._moe_C` | `libtorch_stable/moe/torch_bindings.cpp` | MoE：topk、align、moe_wna16、marlin_moe、shuffle_rows |
| `torch.ops._rocm_C` | `rocm/torch_bindings.cpp` | ROCm 专用：paged_attention、q_gemm_rdna3、skinny_gemms |

另有 Triton 回退路径：`VLLM_USE_TRITON_AWQ=1` 时 AWQ 走 `model_executor/layers/quantization/awq_triton.py`；`cutlass_scaled_mm` 在 ROCm 或不满足 CUTLASS 形状约束时走 `triton_scaled_mm`。

### Paged Attention 与注意力辅助

| 函数（_custom_ops） | 用途 |
|---|---|
| `paged_attention_rocm` | ROCm paged attention（`_rocm_C`，按 `mfma_type` 选 fp8/f16） |
| `merge_attn_states` | 合并 prefix 与 suffix 两组 attention 状态（FlashMLA 分段推理） |
| `mla_decode_kvcache_cpu`、`sm100_cutlass_mla_decode`、`sm100_cutlass_mla_get_workspace_size` | MLA decode（CPU 内核；Blackwell SM100 CUTLASS MLA） |
| `rotary_embedding`、`fused_qk_norm_rope` | RoPE；QK RMSNorm+RoPE 融合 |
| `fused_minimax_m3_qknorm_rope_kv_insert` | MiniMax-M3 融合 QK 归一化+RoPE+KV 写入 |
| `top_k_per_row_prefill` / `top_k_per_row_decode`、`indexer_k_quant_and_cache`、`concat_mla_q` | 稀疏/M3 index 注意力 top-k 与 MLA Q 拼接 |

### KV Cache 写入与调度

| 函数 | 用途 |
|---|---|
| `reshape_and_cache` / `reshape_and_cache_flash` | 增量 K/V 写入 paged KV cache（普通/FlashMLA 布局） |
| `concat_and_cache_mla` / `_grouped` / `_rope_fused` | MLA `kv_c`/`k_pe` 拼接后写入 cache |
| `swap_blocks` / `swap_blocks_batch` | KV block 换入换出（swap 调度，CPU/GPU） |
| `gather_and_maybe_dequant_cache`、`cp_gather_cache`、`cp_gather_and_upconvert_fp8_kv_cache` | Context Parallel：跨 rank 收集 KV 并可反量化 |
| `convert_fp8` | KV cache dtype 转换 |

### 位置编码 / 归一化 / 采样

| 函数 | 用途 |
|---|---|
| `rms_norm`、`fused_add_rms_norm` | RMSNorm 及残差融合 |
| `rms_norm_dynamic_per_token_quant`、`rms_norm_per_block_quant` | 归一化+量化融合（动态 per-token / per-block，1D 尺度含 TMA 对齐） |
| `silu_and_mul_per_block_quant` | SiLU+Mul 激活+block 量化融合 |
| `apply_repetition_penalties` | 采样重复惩罚（CUDA 原语优先，否则 torch） |
| `ngram_compute_n_gram_ids` | LongCat n-gram 嵌入索引核 |

### 量化 GEMM（AWQ/GPTQ/Marlin/Machete/CUTLASS）

| 类别 | 函数 | 用途 |
|---|---|---|
| AWQ | `awq_dequantize`、`awq_gemm` | W4A16 AWQ 反量化与 GEMM（Triton 可切换） |
| GPTQ | `gptq_gemm`、`gptq_shuffle` | GPTQ GEMM 与列重排 |
| Marlin | `gptq_marlin_repack`、`awq_marlin_repack`、`gptq_marlin_moe_repack`、`awq_marlin_moe_repack`、`marlin_gemm`、`marlin_int4_fp8_preprocess` | Marlin repack/GEMM（MoE repack 为 Python 循环） |
| Machete | `machete_supported_schedules`、`machete_mm`、`machete_prepack_B` | Machete 量化 GEMM（schedule 查询/prepack） |
| CUTLASS W4A8 | `cutlass_w4a8_mm`、`cutlass_encode_and_reorder_int4b`、`cutlass_w4a8_moe_mm`、`cutlass_encode_and_reorder_int4b_grouped`、`cutlass_pack_scale_fp8`、`permute_cols` | INT4xFP8 GEMM 及权重编码重排 |
| FP8 | `scaled_fp8_quant` | 动态/静态 FP8 量化（支持 per-token/per-channel/group 尺度） |
| INT8 | `scaled_int8_quant` | int8 量化（对称/非对称、per-token） |
| allspark | `allspark_repack_weight`、`allspark_w8a16_gemm` | Ampere W8A16 融合 GEMM（n32k16 重排） |

### FP4 / MXFP4 量化与 GEMM

| 函数 | 用途 |
|---|---|
| `scaled_fp4_quant` | NVFP4 量化（16 元素/尺度，128x4/8x4 swizzle，trtllm 后端小 batch 走 8x4） |
| `scaled_fp4_experts_quant`、`silu_and_mul_scaled_fp4_experts_quant` | MoE packed 输入的 NVFP4 量化（Silu+Mul 融合） |
| `mxfp4_experts_quant`、`silu_and_mul_mxfp4_experts_quant` | MXFP4（E8M0 尺度、32 元素 block）MoE 量化 |
| `cutlass_scaled_fp4_mm`、`cutlass_fp4_moe_mm`、`cutlass_mxfp4_moe_mm` | FP4/MXFP4 GEMM 及 MoE grouped GEMM |
| `cutlass_scaled_mm_supports_fp4/fp8/block_fp8`、`mxfp4_experts_quant_supported`、`cutlass_group_gemm_supported` | 能力探测 |
| `cutlass_scaled_mm`、`cutlass_scaled_mm_azp` | FP8 尺度化 GEMM（含 zero-point 修正），支持 DeepSeek 式 block scale |

### MoE 路由与 GEMM

| 函数 | 用途 |
|---|---|
| `get_cutlass_moe_mm_data`、`get_cutlass_batched_moe_mm_data`、`get_cutlass_moe_mm_problem_sizes_from_expert_offsets` | CUTLASS grouped GEMM 的 (M,N,K) problem size 准备 |
| `cutlass_moe_mm` | FP8 CUTLASS MoE GEMM |
| `moe_sum`、`moe_align_block_size`、`batched_moe_align_block_size`、`moe_lora_align_block_size` | token 排序/对齐（含 LoRA） |
| `moe_wna16_gemm`、`moe_wna16_marlin_gemm` | MoE 量化 GEMM（CUDA 限定） |
| `topk_softmax`、`topk_sigmoid`、`topk_hash_softplus_sqrt`、`grouped_topk` | 路由 top-k（softmax/sigmoid/hash 变体，grouped 支持 e-score bias） |
| `dsv3_router_gemm`、`fp32_router_gemm`、`dsv3_fused_a_gemm` | DeepSeek-V3 路由 GEMM 与 fused-a（PP/DSA） |
| `shuffle_rows` | MoE 输入按 dst2src_map 置换 |

### Mamba / 线性注意力（GDN/KDA/K3）

| 函数 | 用途 |
|---|---|
| `selective_scan_fwd`、`mamba_chunk_scan_fwd_cpu`、`selective_state_update_cpu`、`causal_conv1d_update_cpu_vec` | Mamba SSM scan 与状态更新 |
| `fused_kda_decode` | Kimi K3 KDA decode（输入投影+conv+SSM 融合） |
| `fused_gdn_decode_post_conv_mtp` | GDN decode+post-conv（MTP 场景） |
| `kimi_k3_attn_res` | K3 attention residual（prefix+delta+blocks 归一化融合） |
| `causal_conv1d_weight_pack`、`causal_conv1d_fwd_cpu`、`causal_conv1d_update_cpu`、`chunk_gated_delta_rule_cpu`、`fused_sigmoid_gating_delta_rule_update_cpu` | Delta Rule 线性注意力 CPU 路径 |

### 集合通信（CUDA Graph / NVLink）

| 函数 | 用途 |
|---|---|
| `init_custom_ar`、`all_reduce`、`custom_all_gather`、`custom_reduce_scatter`、`mnnvl_lamport_all_gather`、`mnnvl_lamport_reduce_scatter` | CustomAllReduce（UVA 直连，含 CUDA Graph 支持：register_buffer/get_graph_buffer_ipc_meta/register_graph_buffers、共享内存句柄 open_mem_handle/free_shared_buffer） |
| `init_custom_qr`、`qr_all_reduce`、`qr_get_handle`、`qr_open_handles`、`qr_max_size` | QuickReduce（NVLink SHARP 硬件规约，`csrc/quickreduce/`） |
| `get_device_attribute`、`get_max_shared_memory_per_block_device_attribute` | 设备能力查询 |

### ROCm 专用与 CPU 后端

| 类别 | 函数 | 用途 |
|---|---|---|
| ROCm GEMM | `LLMM1`、`wvSplitK`、`wvSplitK_int4_g`、`wvSplitKrc`、`wvSplitKQ` | skinny GEMM（int8/fp8 变体） |
| ROCm GPTQ | `gptq_gemm_rdna3`、`gptq_gemm_rdna3_wmma`、`moe_gptq_gemm_rdna3` | RDNA3 W4A16 |
| CPU GEMM | `fused_experts_cpu`、`cpu_fused_moe`、`cpu_fused_moe_int8`、`cpu_gemm_wna16`、`int4_scaled_mm_cpu`、`fp8_scaled_mm_cpu`、`cpu_activation_lut_bf16` | CPU MoE/GEMM/激活 LUT |
| oneDNN/ACL | `onednn_mm`、`onednn_scaled_mm`、`onednn_scaled_int8_quant`、`is_onednn_acl_supported`、`create_onednn_mm/scaled_mm` | oneDNN/ACL 路径 |
| CPU 注意力 | `cpu_attention_with_kv_cache`、`cpu_attn_get_scheduler_metadata`、`cpu_attn_reshape_and_cache` | CPU paged attention 调度与 KV 写回 |
| 其它 | `matmul_mxf4_bf16_tn`、`fusedQuantizeMx`、`fusedQuantizeNv`、`safeFusedQuantizeNv`、`hadacore_transform` | MX/NV FP4 量化与 HADA Core 变换 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)