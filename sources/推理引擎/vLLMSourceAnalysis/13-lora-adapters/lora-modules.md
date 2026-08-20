## LoRA 权重、层注入与缓存（13-lora-adapters）

本文覆盖 `vllm/lora/` 的权重表示、加载管线、层注入、两级缓存、Punica 内核与 CUDA graph 集成。

### 权重表示

`lora_weights.py`:

| 类 | 用途 |
|---|---|
| `LoRALayerWeights` | 单层权重:`lora_a`(rank × input_dim)、`lora_b`(output_dim × rank)、`rank`、`lora_alpha`、`scaling` |
| `PackedLoRALayerWeights` | 打包层(qkv_proj / gate_up_proj 等)权重:lora_a/b 为 `list[Tensor\|None]`,None 表示该子模块无 LoRA |

- `optimize()`:把 `scaling = lora_alpha / rank` 乘入 lora_b 后置 scaling=1,减少内核乘法;packed 版按切片逐个优化。
- `PackedLoRALayerWeights.pack(loras)`:合并各切片为单一 packed 权重(均先 `optimize()`)。`pack_moe(loras, module_name, is_non_gated_moe)`:按 `[eid*3]=w1(gate)、[eid*3+1]=w2(down)、[eid*3+2]=w3(up)` 逐专家 `torch.stack` 成 `(num_experts, rank, in)` / `(num_experts, out, rank)` 三维张量;non-gated MoE 用 w1 充当 w3 并避免双重 scaling。`pack_moe_stacked` 针对 shared-outer 布局(3 个已带专家维的 w1/w2/w3 张量直接打包)。

### PEFT 配置解析

`peft_helper.py`:`PEFTHelper.from_local_dir` 读 `adapter_config.json`(或 tensorizer 流),`from_dict` 只保留类字段,`__post_init__` 计算 `vllm_lora_scaling_factor`(rsLoRA 用 `lora_alpha/√r`,否则 `lora_alpha/r`)。`validate_legal` 拒绝:`r > max_lora_rank`、`bias != "none"`、`modules_to_save` 非 None、DoRA。`vllm_max_position_embeddings` 由 worker 从模型 config 注入。

### LoRAModel 加载

`lora_model.py`:`LoRAModel` 持 `id`、`rank`、`loras: dict[module_name, LoRALayerWeights]`。`from_local_checkpoint` 支持四种来源:

1. `tensorizer_config_dict` → `TensorDeserializer` 读 `adapter_model.tensors`;
2. `adapter_model.safetensors` → `safetensors.safe_open` 懒加载;
3. `adapter_model.bin` / `.pt` → `torch.load(weights_only=True)`;
4. 均无则抛 `ValueError`。

加载时:跳过 `is_base_embedding_weights` 与模型声明的 `skip_prefixes`(如 MTP 层);`check_unexpected_modules` 校验磁盘张量名 ⊆ `expected_lora_modules`,否则抛错。`from_lora_tensors` 经 `parse_fine_tuned_lora_name`(`utils.py`)剥掉 `base_model.model.` 前缀(经 `weights_mapper._map_name` 重命名)、拆出模块名与 `is_lora_a`,再按需 `WeightsMapper` 映射。EP 模式下 `MoEEPLoadSpec` 让非本 rank 专家的张量在读取期即被跳过(`_is_remote_expert_key` 按 `.experts.N.` 判定)。

### 层注入

`model_manager._create_lora_modules` 遍历模型 `named_modules()`,对满足 `_match_target_modules`(= 模型支持的模块后缀 ∩ `target_modules` 过滤)的原子层调用 `from_layer`(`utils.py`):

```python
for lora_cls in _all_lora_classes:          # 顺序敏感,专用 wrapper 在前
    if lora_cls.can_replace_layer(layer, lora_config,
                                  packed_modules_list, model_config):
        instance = lora_cls(layer)          # 包装原层为 self.base_layer
        instance.create_lora_weights(max_loras, lora_config, model_config)
        return instance
return layer                                 # 不支持则原样返回
```

`_all_lora_classes` 覆盖:`VocabParallelEmbeddingWithLoRA`、`ColumnParallelLinearWithLoRA`、`MergedColumnParallelLinearWithLoRA`、`QKVParallelLinearWithLoRA`、`MergedQKVParallelLinearWithLoRA`、`RowParallelLinearWithLoRA`、`ReplicatedLinearWithLoRA`、`LogitsProcessorWithLoRA`、各 `...WithShardedLoRA` 变体、`MergedColumnParallelLinearVariableSliceWithLoRA`、`FusedMoEWithLoRA`、`FusedMoE3DWithLoRA`。`lm_head` 被替换时,配套的 `logits_processor` 也替换为 `LogitsProcessorWithLoRA`。

每个包装层(`BaseLayerWithLoRA`, `layers/base.py`)持 GPU 槽位缓冲:

| 缓冲 | 形状 | 说明 |
|---|---|---|
| `lora_a_stacked` | (max_loras, 1, rank, input_size) 每切片 | LoRA-A 张量池,index 即活跃槽位 |
| `lora_b_stacked` | (max_loras, 1, output_size, max_lora_rank) 每切片 | LoRA-B 张量池 |

`set_lora(index, lora_a, lora_b)` 先 `reset_lora(index)` 清零,再 `copy_` 非阻塞拷入;TP>1 时先 `slice_lora_a/b` 按行/列切分。前向经 `_apply_lora_to_output` 调 `punica_wrapper.add_lora_linear` 把 `y += (x@A)@B` 原地累加。`VLLM_LORA_ENABLE_DUAL_STREAM` 时基座与 LoRA 分别在默认/辅助 CUDA 流并行,经 `maybe_execute_in_parallel` + `torch.ops.vllm.lora_linear_async` 实现。

### 模型管理器与两级缓存

`model_manager.py`:`LoRAModelManager` 启动即创建包装层、按 `max_num_batched_tokens` 建 Punica wrapper(多模态按 language/tower/connector 前缀各建一个)。适配器分两级:

| 级别 | 容器 | 容量 | 说明 |
|---|---|---|---|
| 注册缓存 | `_registered_adapters: AdapterLRUCache[LoRAModel]` | `max_cpu_loras` | CPU 权重缓存,`_on_remove` 时 `deactivate_adapter` |
| 活跃槽位 | `_active_adapters: AdapterLRUCache[None]` | `max_loras` | GPU 缓冲,`lora_index_to_id` 记录 slot→id |

`add_adapter` → `_add_adapter`:先 `_create_merged_loras_inplace`(把子模块权重 `pack`/`pack_moe` 合并、`optimize`、pin_memory)再入注册缓存。`activate_adapter` 找空槽,对每个 `self.modules` 调 `set_lora`,把 CPU 权重拷入 GPU stacked 缓冲。`LRUCacheLoRAModelManager` 额外支持 `remove_oldest_adapter` 与 `pin_adapter`(LRU pin)。worker 侧 `WorkerLoRAManager.add_adapter` 在 `gpu_sync_allowed()` 内完成 `_load_adapter`(PEFTHelper + `from_local_checkpoint`,device="cpu")→ 注册 → 激活;`LRUCacheWorkerLoRAManager` 支持 `load_inplace` 与超容 LRU 淘汰。

### Punica 内核层

`punica_wrapper/punica_base.py` 定义接口:`add_shrink`(`y += x@lora_a`)、`add_expand`、`add_lora_linear`(shrink+expand 组合)、`add_lora_embedding`、`add_lora_logits`、`add_lora_fused_moe`/`add_lora_w13`/`add_lora_w2`(MoE)。`PunicaWrapperGPU` 用 `LoRAKernelMeta.make` 预分配 token/prompt 两套内核元数据,`prepare_tensors` 每步更新;triton 内核在 `lora/ops/triton_ops/`(lora_shrink_op.py、lora_expand_op.py、fused_moe_lora_op.py),XPU 走 `xpu_ops`。prefill 经 `compute_meta` 聚合同 LoRA 序列供 SGMV;`sampler_indices_padded` 把 -1 替换为 `max_loras-1` 再乘 batch 长度,供 sampler 内核去偏移。

### MoE LoRA 与 CUDA graph

- `FusedMoEWithLoRA` 包装 `MoERunner`,按 w13/w2 两组 stacked 缓冲存 `[w1,w3]` 切片;`FusedMoE3DWithLoRA` 对应磁盘 3D 融合布局(`gate_up_proj`/`down_proj`)。`enable_mixed_moe_lora_format` 强制 2D 通用 wrapper,`_convert_3d_to_2d_moe_lora` 在 CPU 侧把 3D 布局切成 `[w1,w2,w3]`(GPT-OSS 的 w1/w3 沿输出维交错,其余拼接)。EP 下 `_restrict_to_local_experts`/`_slice_moe_lora_ep` 只保留本 rank 专家块。
- CUDA graph:`get_captured_lora_counts(max_loras, specialize)` 为捕获用例提供激活数集合(不 specialize 时为 `[max_loras+1]`,specialize 时为 2 的幂 + `max_loras+1`);`CudagraphDispatcher._get_lora_cases` 按 `cudagraph_specialize_lora` 决定是否叠加"无 LoRA"用例,`BatchDescriptor` 增加 `has_lora`/`num_active_loras` 维。capture 前用 `maybe_setup_dummy_loras` + `maybe_select_dummy_loras`(`lora_model_runner_mixin.py`)装载 rank 8 的零权重 dummy LoRA,`create_dummy_lora` 按各包装层缓冲形状生成全零权重。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
