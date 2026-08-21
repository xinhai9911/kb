## 注意力后端抽象、注册与选择

SGLang 把注意力内核按「后端」组织：每个后端实现 `AttentionBackend` 接口（`layers/attention/base_attn_backend.py:36`），提供一致的 KV 读写与 forward 语义，由 `ModelRunner.init_attention_backends`（`model_runner.py:919`）在启动期实例化一个（或一组）后端。

### AttentionBackend 抽象接口

```python
class AttentionBackend(ABC):
    def init_forward_metadata(self, forward_batch): ...   # eager 入口，默认 = out_graph + in_graph
    def init_forward_metadata_out_graph(self, fb, in_capture=False): ...  # 每步 host 侧元数据规划（图外）
    def init_forward_metadata_in_graph(self, fb): ...     # 可录制的 GPU 元数据 op（图内，默认 no-op）
    def init_cuda_graph_state(self, max_bs, max_num_tokens): ...
    def forward(self, q, k, v, layer, forward_batch, save_kv_cache=True, **kwargs): ...
    def forward_decode / forward_extend / forward_mixed(self, ...): ...
```

`forward` 的分派（`base_attn_backend.py:215`）：`IDLE` → 空输出；`DECODE` → `forward_decode`；`MIXED`（仅 NPU）→ `forward_mixed`；其余 → `forward_extend`。**decode/verify 共用 decode 内核，extend/target-verify 共用 prefill 内核**。

关键类属性/标志：

| 属性 | 含义 |
|---|---|
| `prefill_attention_backend_str` / `decode_attention_backend_str` | 本后端解析出的模式名（`build_attention_backends` 盖章） |
| `needs_cpu_seq_lens` | 是否依赖 CPU 侧 `seq_lens_cpu`（Triton False，FlashInfer True） |
| `extend_dummy_seqs_capped_by_req_pool` | 预分配 kv_indptr 上限 = req pool 大小（FlashInfer/Triton True） |
| `supports_ragged_verify_graph` / `supports_full_cuda_graph_chunked_prefix` | 投机验证图 / chunked-prefix FullCG 支持声明 |
| `shared_read_ends(fm)` | 调度器共享 KV 读取结束点（`SharedReadEnds`：PRE_REPLAY/IN_REPLAY/POST_REPLAY/UNKNOWN），供流同步优化 |

### 后端注册表（attention_registry.py）

`ATTENTION_BACKENDS: dict[str, Callable]`，`register_attention_backend(name)` 装饰工厂函数（`attention_registry.py:34`）。`_build_full_attention_backend_from_str`（`attention_backend_setup.py:251`）查表构造。

| 注册名 | 工厂 | 后端类 / 说明 |
|---|---|---|
| `flashinfer` | `create_flashinfer_backend` | `FlashInferAttnBackend`；`use_mla_backend` 时切 `FlashInferMLAAttnBackend` |
| `fa3` | `create_flashattention_v3_backend` | `FlashAttentionBackend`（fa_impl_ver=3）；MUSA 走 `MusaFlashAttentionBackend` |
| `fa4` | `create_flashattention_v4_backend` | `FlashAttentionBackend`(fa_impl_ver=4) |
| `triton` | `create_triton_backend` | `TritonAttnBackend`（纯 Triton 内核，禁 encoder-decoder） |
| `flashmla` | `create_flashmla_backend` | `FlashMLABackend`（继承 FlashInferMLA，decode 用 `sgl_kernel.flash_mla`） |
| `trtllm_mla` | `create_trtllm_mla_backend` | `TRTLLMMLABackend`（仅 MLA） |
| `cutedsl_mla` / `cutlass_mla` / `tokenspeed_mla` | 同名工厂 | MLA 专用（Cute DSL / Cutlass / TokenSpeed） |
| `trtllm_mha` | `create_trtllm_mha_backend` | `TRTLLMHAAttnBackend`（仅非 MLA） |
| `aiter` / `wave` / `intel_amx` / `intel_xpu` / `torch_native` / `flex_attention` / `hpc_ops` / `dual_chunk_flash_attn` | 同名工厂 | 平台/算法变体后端 |
| `ascend` | `create_ascend_backend` | NPU 后端（`hardware_backend/npu/attention/`） |
| `dsa` | `create_dsa_backend` | `DeepseekSparseAttnBackend`；`nsa` 为已废弃别名 |
| `dsv4` | `create_dsv4_backend` | DeepSeek V4（NPU/HIP/CUDA 三分支） |

### 后端字符串解析与默认选择

`server_args.py` 三个字段：`attention_backend`（通用）、`prefill_attention_backend`/`decode_attention_backend`（拆分覆盖）。`attention_backends_of`（`arg_groups/overrides.py:277`）：拆分字段为空时回退 `attention_backend`，返回 `(prefill, decode)`。

`_get_default_attn_backend`（`server_args.py:5903`）按架构+硬件自动选默认：

| 场景 | 默认后端 |
|---|---|
| MHA + Hopper（CUDA≥12.3，无 spec 或 topk=1） | `fa3`（flashinfer 0.6.1 在 Hopper 有性能回退，issue #17411） |
| MHA + SM100/103（Blackwell B200/GB200/B300） | 非对称 KV → `fa4`，否则 `trtllm_mha`（SM120 不支持，回退 flashinfer） |
| MHA + HIP / MPS | `aiter` / `torch_native` |
| MHA + 其余 | `flashinfer`（可用且无 attention sinks）否则 `triton` |
| MLA + Hopper / SM100 / HIP / 其余 | `fa3` / `flashinfer` / `aiter`（头数 128/16）或 `triton` / `triton` |

其他修正 pass：`torch_native`/`flex_attention` 禁用 CUDA graph；fa3 fp8 回退；MLA/KV4 页面约束；`dual_chunk_flash_attn` 对 Fa-2 chunk 化处理。

### 运行时装配（attention_backend_setup.py）

`resolve_attention_backend_strs`（:158）：draft worker 用 `draft_attention_backend` 覆盖为单后端；否则用 `runtime_context.attention_backends()`（读取执行包内的 (prefill, decode)）。

`build_attention_backends`（:69）构造 `AttentionBackends`：

| 模式 | 装配 |
|---|---|
| PDmux（`enable_pdmux`） | 1 个 `attn_backend` + `decode_attn_backend_group`（每 SM 组一个）+ `decode_attn_backend` |
| Two-batch overlap | `TboAttnBackend.init_new` 包装 |
| 普通 | 单个 `attn_backend`，`decode_attn_backend=None` |

- **prefill ≠ decode 时**：`HybridAttnBackend`（`hybrid_attn_backend.py:21`）组合两个后端，`_select_backend(forward_mode)` 按模式路由（decode/idle → decode；target_verify → 按 `speculative_attention_mode`；其余 → prefill）。整个封装再交给 `attn_backend_wrapper`。
- **`attn_backend_wrapper`**（`attention_registry.py:309`）：对 MiniMax 稀疏、mambaish/linear-attention、KDA、Lightning、ShortConv 等混合架构模型，把 full-attention 后端与线性/稀疏后端组合为混合后端（如 `MiniMaxHybridAttnBackend`、`HybridLinearAttnBackend`）。

### ForwardContext 与 get_attn_backend

`get_attn_backend()`（`model_executor/forward_context.py:66`）从当前 `ForwardContext.attn_backend` 读取后端——每层 forward 唯一入口。`ModelRunner._forward_raw` 用 `forward_context(ForwardContext(attn_backend=self.attn_backend))` 发布（`model_runner.py:1651`）；PDmux 的 eager decode 用 `decode_attn_backend` 覆盖（`eager_runner.py:224`）。`get_token_to_kv_pool()`/`get_req_to_token_pool()` 也从后端派生。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
