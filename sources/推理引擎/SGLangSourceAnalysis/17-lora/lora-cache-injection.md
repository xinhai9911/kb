## LoRA 权重加载、GPU 权重池与层注入（17-lora）

本文覆盖 `lora/lora_manager.py`、`lora/mem_pool.py`、`lora/lora.py`、`lora/layers.py` 的权重加载、权重池缓存与层注入机制。

### 适配器加载管线

`LoRAManager`(`lora_manager.py:63`)初始化(`init_state`):`init_lora_adapters` → `init_lora_shapes` → `init_lora_modules` → `init_memory_pool` → `update_lora_info`。

```
load_lora_adapter(lora_ref)            # lora_manager.py:225
  ├─ LoRAConfig(path, base_vocab_size) # 读 adapter_config.json
  ├─ validate_new_adapter              # 拒绝:新增词表 token、DoRA、同名、
  │                                    #   池不兼容(rank/target)、pinned 占满槽位
  ├─ load_lora_weights                 # lora_manager.py:771
  │    └─ LoRAAdapter.initialize_weights (lora.py:143)
  │         └─ DefaultModelLoader._get_weights_iterator(Source(path, fall_back_to_pt=True))
  │              └─ _process_weight 按层路由 → _normalize_weights
  └─ 登记 lora_refs / num_pinned_loras
```

`LoRAAdapter`(`lora.py:54`)持有 CPU 权重:`layers: ModuleList[LoRALayer]`(每层一个,`LoRALayer.weights: Dict[name, Tensor]`)、`embedding_layers`(embed_tokens/lm_head)、`added_tokens_embeddings`;`base_model` 用 `object.__setattr__` 保存以避免成为子模块泄漏参数。`scaling = lora_alpha / r`。

`_process_weight`(`lora.py:164`)路由:`unembed_tokens`→`lm_head` 改名;带层号 → 存入对应 `layers[i].weights`;embed_tokens/lm_head 须在 adapter `target_modules` 内;`input_embeddings`/`output_embeddings` → 新增 token 嵌入(校验 `shape[0] == lora_added_tokens_size`)。

`_normalize_weights`(`lora.py:202`)做 PEFT 键名 → SGLang 融合键名归一化:

| 归一化 | 逻辑 |
|---|---|
| `normalize_qkv_proj` | `q/k/v_proj` 按 dim0 concat → `qkv_proj`;缺失的 k 补零;已 stack 的 qkv A 权重 `repeat(3,1)` |
| `normalize_gate_up_proj` | `gate+up_proj` → `gate_up_proj`;非 gated MoE(`_is_non_gated_moe_weight`)仅改名不 stack;gated 路径缺失 up 则补零;已 stack 的 A 权重 `repeat(2,·)` |
| `normalize_fused_qkv_a_proj` | DeepSeek MLA: `q_a_proj`+`kv_a_proj_with_mqa` → `fused_qkv_a_proj_with_mqa`(dim0 concat,缺失补零) |
| `_normalize_in_proj` / `_normalize_in_proj_qkvz` | Mamba `gate+x→in_proj`;GDN(Qwen3.5) 4 个 in_proj_q/k/v/z → `in_proj_qkvz` |
| `normalize_inkling_qkvr_proj` | Inkling 拆分的注意力权重 concat 到 `qkvr`,A 按 rank 维 repeat 4× |

### GPU 权重池:LoRAMemoryPool

`mem_pool.py:131`。核心容器:

| 容器 | 结构 | 说明 |
|---|---|---|
| `A_buffer` / `B_buffer` | `Dict[str, List[Tensor]]`,键=目标模块名,值=每层一个张量 | 标准模块 3D `[max_loras_per_batch, rank(×c), hidden]`;MoE 4D `[max_loras, num_experts, rank(×c), hidden]` |
| `embedding_A/B_buffer`、`lm_head_A/B_buffer` | `Dict[str, Tensor]` | 词表嵌入类,单张量 |
| `new_embeddings_buffer` | `(max_loras, lora_added_tokens_size, embed_dim)` | 新增 token 嵌入 |
| `uid_to_buffer_id` / `buffer_id_to_uid` | 槽位映射 | `buffer_id_to_uid` 初值 `EMPTY_SLOT`(单例),`None` 也是合法 uid(基座模型) |

维度推导:`get_lora_A_shape`/`get_lora_B_shape`(`mem_pool.py:394/492`)经 `get_hidden_dim`(`utils.py:106`)取模块出入维,`get_stacked_multiply`(`utils.py:290`)给出 c 倍数(qkv=3、gate_up=2、in_proj_qkvz=4、fused_qkv_a=2)。TP 切分:`_effective_tp_size` 区分 routed MoE(`moe_tp_size`)、注意力投影(`attn_tp_size`,DP 注意下更小)、其余(`tp_size`);`get_lora_B_shape` 对 qkv_proj 在 `num_kv_heads < tp_size` 时按"K/V 头复制"逻辑计算每 rank B 输出维(`_column_parallel_lora_b_per_rank_dim`,mem_pool.py:457)。

### 槽位分配与逐出

`prepare_lora_batch(cur_uids, ...)`(`mem_pool.py:740`):对 batch 所需 uid 集合:

1. `get_available_buffer_slot`:优先空槽;满则收集候选(跳过本批在用、跳过 pinned),**优先逐出 LoRA 而非基座模型 None**(仅全 LoRA 批时允许逐出 None),按 eviction_policy(LRU/FIFO)选 victim;
2. `load_lora_weight_to_buffer`(`mem_pool.py:851`):逐层把 adapter CPU 权重拷入 GPU 缓冲——标准模块 `slice_lora_a/b_weights` 按 TP rank 切分后 `copy_weight_into_buffer`(pinned 源 + 非阻塞拷贝);MoE 按 `_iter_local_expert_weights` 过滤非本 rank 专家(EP);权重缺省时清零避免污染;`lora_B` 乘 `adapter.scaling`;槽位按 `max_lora_rank` 间距放置,内核按 `[:max_r]` / `[max_r:2*max_r]` 切片;
3. 基座模型 `uid=None` 固定占槽(init 时 `fetch_new_loras({None})`,`lora_manager.py:876`),逐出后 `_clear_buffer_slot_for_base` 清零保证 CUDA graph 回放安全。

加载前还会全量预校验权重名(`get_target_module_name` 最长匹配),不匹配权重在 `strict_loading` 时抛错、否则告警跳过(`mem_pool.py:883-914`)。

### 层注入:BaseLayerWithLoRA

`init_lora_modules`(`lora_manager.py:884`)遍历 `base_model.named_modules()`:embed_tokens/lm_head 提前处理(并解开 `tie_word_embeddings`——新建共享底层权重的 `ParallelLMHead` 使 named_modules 可见);其余按 `parts[-1] in target_modules` 或最后两段匹配;`FusedMoE` 类在 `{"gate_up_proj","down_proj"} ⊆ target_modules` 时整层包装。替换动作 `set_lora_module` → `get_lora_layer`(`layers.py:1291`)→ `replace_submodule`(`utils/common.py:2360`)。

`get_lora_layer` 的类型映射(顺序敏感):`FusedMoE→FusedMoEWithLoRA`、`ParallelLMHead→ParallelLMHeadWithLoRA`、`VocabParallelEmbedding→VocabParallelEmbeddingWithLoRA`、`ReplicatedLinear/QKVParallelLinear/MergedColumnParallelLinear/ColumnParallelLinear/RowParallelLinear` 对应包装层,`is_inkling_qkvr` 特判。

`BaseLayerWithLoRA`(`layers.py:34`)包装原层为 `self.base_layer`,反射 `weight`/`bias`/`reduce_results`;`lora_active` 要求 `set_lora` 且 backend 有 batch 元数据。`update_lora_info`(`lora_manager.py:472`)把池内张量通过 `set_lora_info` 注入各层,MoE 层按 `gate_up_proj_moe/down_proj_moe`(或 `_shared_moe`)取 4D 张量。前向如 `ColumnParallelLinearWithLoRA.forward`(`layers.py:480`):基座量化计算后,`lora_active` 时 `apply_lora` = `run_lora_a_sgemm(x, A)` + `run_lora_b_sgemm(a, B, output_offset, base_output)` 原地累加。

### 内核后端与 batch 元数据

`BaseLoRABackend`(`backend/base_backend.py:12`):`prepare_lora_batch` 由各后端实现;`TritonLoRABackend`(`backend/triton_backend.py:265`)构建 `LoRABatchInfo`(`utils.py:28`,含 `seg_indptr/weight_indices/lora_ranks/scalings/permutation`),并生成 MoE 的 `MoELoRABatchInfo`(`token_lora_mapping`/`adapter_enabled`,经 `_compute_moe_lora_info` triton 内核填充)。CSGMV 后端按 `max_lora_chunk_size` 分块。backend 注册表见 `backend/lora_registry.py`(triton 默认,flashinfer 已废弃)。

### 异步加载与 CUDA graph

- `LoRAOverlapLoader`(`lora_overlap_loader.py:21`):独立 CUDA 流上 `fetch_new_loras`,用 CUDA Event 记录加载完成,主流 `wait_event`;pending 事件存在 `lora_manager.pending_lora_load_events`。
- CUDA graph 两阶段:`init_cuda_graph_moe_buffers`(Phase 1,MoE 中间缓冲,须在 memory pool 之前分配,`lora_manager.py:198`);`init_cuda_graph_batch_info`(Phase 2,静态 batch 元数据,`lora_manager.py:125`);decode/prefill graph 回放前 `prepare_lora_batch`(`decode_cuda_graph_runner.py:1146`、`prefill_cuda_graph_runner.py:1380`)。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
