## MoE、激活函数与 RoPE/Embedding

本文覆盖 `srt/layers/moe/`、`activation.py`、`rotary_embedding/`、`vocab_parallel_embedding.py`，以及 LoRA 注入与 model_executor 衔接。attention 相关（07 模块已覆盖）不重复。

### FusedMoE 层（fused_moe_triton/layer.py）

`FusedMoE`（`layer.py:206`）是 MoE 专家层容器，内含 **w13（gate+up 融合列并行）与 w2（down 行并行）** 两组专家权重：

| 字段 | 含义 |
|---|---|
| `num_experts` / `top_k` / `num_fused_shared_experts` | 专家数 / 每 token top-k / 融合共享专家数 |
| `moe_ep_size/moe_ep_rank`、`moe_tp_size/moe_tp_rank` | 从 `get_parallel()` 取 EP/TP 划分；`num_local_experts = (num_experts-num_shared_slots)/ep_size + fused_shared` |
| `intermediate_size_per_partition` | `intermediate_size // moe_tp_size`；flashinfer_trtllm 时 round_up 到 128 |
| `quant_method` | `quant_config.get_quant_method`；无量化 → `UnquantizedFusedMoEMethod`（可选 triton/flashinfer_trtllm/deep_gemm 后端）；KT-EP 时包 `KTEPWrapperMethod` |
| `moe_runner_config` / `dispatcher` | `create_moe_runner()` 后 `create_moe_dispatcher()`；dispatcher 的 `expert_mask_gpu` 注册为非持久 buffer |

前向流程（`forward` → `forward_impl`，`layer.py:1421`）：

```python
dispatch_output = self.dispatcher.dispatch(hidden_states, topk_output)  # EP 场景做 all-gather/路由
combine_input   = self.run_moe_core(dispatch_output)                    # quant_method.apply → 专家 GEMM
final_hidden    = self.dispatcher.combine(combine_input)                # 按 topk_weights 加权组合
# reduce_results 且 (moe_tp_size>1 or moe_ep_size>1) → tensor_model_parallel_all_reduce
```

- **权重加载**：`make_expert_params_mapping`（`layer.py:1538`）生成 `(param_name, weight_name, expert_id, shard_id)` 四元组，把 checkpoint 的 `experts.{id}.{gate/down/up}` 映射到 `experts.w13_/w2_`；`_load_w13/_load_w2` 处理 TP 切分、量化 scale（per-tensor/per-group/per-channel/block）。
- TC piecewise CUDA Graph 下 `forward` 走 `moe_forward_piecewise_cuda_graph_impl` / `fused_moe_bypassed_piecewise_cuda_graph_impl`（`@register_custom_op`）。
- `moe/utils.py` 提供 `get_moe_runner_backend()`（`MoeRunnerBackend` 枚举：triton_kernels / flashinfer_trtllm / flashinfer_cutlass / deepep / cutlass / aiter / deep_gemm / marlin / hpc_ops 等）与 `get_moe_a2a_backend()`，FusedMoE/TopK 依此后端选择输出格式与 kernel。
- runner 实现在 `moe/moe_runner/`（`base.py` 的 `MoeRunnerCore` + 各后端 runner），token 路由在 `moe/token_dispatcher/`（`BaseDispatcher.dispatch/combine`，标准/DeepEP/Mooncake/Nixl/PPLX 等）。

### TopK 路由（moe/topk.py）

`TopK`（`topk.py:392`，BaseFusedOp）持有 `TopKConfig`（top_k、grouped、renormalize、correction_bias、scaling_factor 等）。`forward_cuda` 按 runner 后端选输出格式：

| 输出格式 | 触发 | 说明 |
|---|---|---|
| `StandardTopKOutput` | 默认 / triton 之外 | `select_experts` 返回 `(topk_weights, topk_ids, router_logits)` |
| `BypassedTopKOutput` | flashinfer_trtllm / flashinfer_mxfp4 | 不计算 topk，把 router_logits 直接交 kernel |
| `TritonKernelTopKOutput` | triton_kernels | `routing()` 返回 gather/scatter 索引 |
| `PackedTopKOutput` | `SGLANG_OPT_LORA_FUSED_TOPK_PACK` | topk+pack 融合（LoRA 优化） |

`select_experts`（`topk.py:2111`）按配置分发：`use_grouped_topk` → `grouped_topk`/`biased_grouped_topk`（DeepSeek 系列）；`scoring_func="sqrtsoftplus"/"sigmoid"` → `biased_topk_jit_kernel_impl`；否则 `fused_topk`（Qwen3-MoE 等），`correction_bias` 支持 biased 路由，`custom_routing_function` 可完全接管。共享专家经 `_post_process_topk_ids` 补 `top_k - num_routed_topk` 个 slot；Waterfill 负载均衡由 `_apply_waterfill` 在 TopK 层外处理。

### 激活函数（activation.py）

全部继承 `BaseFusedOp`，CUDA 下优先 JIT/sgl_kernel 的 act-and-mul 融合 kernel（输入拼 `[gate, up]`，输出宽度减半）：

| 类 | 语义/后端 |
|---|---|
| `SiluAndMul:130` | SwiGLU 主路径；JIT kernel 要求 per-rank hidden 整除向量宽（SM100+ 32B，否则 16B），不整除回退 sgl_kernel；ROCm+aiter 可选 `forward_aiter` |
| `SituAndMul:187` | Kimi K3 的 `beta·tanh(gate/beta)·sigmoid(gate)·up`，`linear_beta` 软裁剪 |
| `GeluAndMul:223` | tanh/none 两种近似 |
| `NewGELU / ReLU2 / QuickGELU / XIELU` | GPT-2 变体 / 平方 ReLU / 快速 GELU / 可学习参数 xIELU |
| `ScaledActivation:417` | AWQ 等量化场景，`act(x)/scales`，scale 按 TP 切分加载 |

`get_act_fn`（`activation.py:468`）查 `_ACTIVATION_REGISTRY`（gelu/gelu_pytorch_tanh/gelu_new/relu2/xielu），若量化配置声明 scaled act 则包 `ScaledActivation`。

### RoPE（rotary_embedding/）

- `RotaryEmbedding`（`base.py:78`，BaseFusedOp）：`inv_freq = base^(-arange(0,rotary_dim,2)/rotary_dim)`，预计算 `cos_sin_cache = cat([cos,sin], -1)`（默认保 FP32）。`forward_cuda` 优先 `apply_rope_with_cos_sin_cache_inplace`（可透传 `fused_set_kv_buffer_arg` 直接写 KV cache），`head_size∉{64,128,256,512}` 时回退 `fallback_rotary_embedding`；`_ensure_cos_sin_cache_length` 按需增量扩展 cache。
- `LinearScalingRotaryEmbedding`（`base.py:488`）：多个 scaling factor 各自算 cache 后**拼接成一个大 cache**，用 offset 索引——多 LoRA 适配器可 batched 旋转（vLLM 同款设计）。
- `factory.py:get_rope`：按 `rope_scaling.rope_type` 构造变体（llama3 / default(mrope/fope) / linear / dynamic(NTK alpha 或 scaling) / yarn / deepseek_yarn / longrope(Phi3) / proportional(Gemma4) / dual_chunk）；进程级 `_ROPE_DICT` 缓存带「死缓存回收」（buffer 迁移到 meta 设备则剔除，防模型卸载毒化全局）。`get_rope_wrapper` 在 ROCm+aiter 下走 aiter。
- 变体族：`rope_variant.py`（DeepseekScaling/DualChunk/DynamicNTKAlpha/DynamicNTKScaling/Fourier/Llama3/Phi3LongRoPE/Gemma4）、`mrope.py`（MRotaryEmbedding 多维位置，Vision/多模态）、`yarn.py`。

### 词表并行 Embedding（vocab_parallel_embedding.py）

`VocabParallelEmbedding`（`:188`）：vocab 维切分，pad 到 64（`DEFAULT_VOCAB_PADDING_SIZE`）。**base 词表与 LoRA 新增词表分别切分+填充**后放入同一张量（LoRA 词表恒在尾部）。`VocabParallelEmbeddingShardIndices` 记录 org/added 各自 padded 起止；前向用 `get_masked_input_and_mask`（torch.compile 融合）做 mask+offset，再 `tensor_model_parallel_all_reduce`。`get_embedding_tp_kwargs`（`:166`）：DeepSeek-V3.1/Kimi-K2.5 系可开 `SGLANG_ENABLE_EMBED_REPLICATION` 全量复制省 all-reduce，DP-attention 下 reduce 收窄到 attn_tp_group。

### LoRA 注入与 model_executor 衔接

- **注入点**（`srt/lora/layers.py`）：`BaseLayerWithLoRA` 提供 `process_lora(adapter)` 基座；子类按需包装原生层——`VocabParallelEmbeddingWithLoRA`、`ParallelLMHeadWithLoRA`、`ColumnParallelLinearWithLoRA`、`MergedColumnParallelLinearWithLoRA`、`QKVParallelLinearWithLoRA`、`RowParallelLinearWithLoRA`、`ReplicatedLinearWithLoRA`、`FusedMoEWithLoRA`（`:931`，MoE 路由到 `lora_moe_runner_marlin.py`）。LoRA 权重在 forward 中按激活的 adapter 相加/替换。
- **与 model_executor 衔接**：模型文件（如 `srt/models/deepseek_v2.py:90-113`）直接 import `RMSNorm / MergedColumnParallelLinear / RowParallelLinear / FusedMoE / TopK` 组装；层通过 `get_parallel()`（tp/ep rank）与 `get_exec()`（comm 开关、moe 配置）从 runtime_context 取运行时状态；`BaseFusedOp.forward` 依据平台与 kernel 注册表自动选 `forward_cuda/hip/...`，全部算子共享 `forward_native` 作为正确性基准。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
