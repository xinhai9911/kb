## LoRA 与适配器总览（13-lora-adapters）

本文基于 vLLM `vllm/lora/` 源码,说明 LoRA 请求如何表示、分发,以及如何与调度器 / 模型执行器衔接。本版本(v1 架构)中 lora 模块已由旧版 `lora.py/layers.py` 重构为 `lora_model.py / lora_weights.py / model_manager.py` 分工。

### 模块文件清单

| 文件 | 职责 |
|---|---|
| `vllm/lora/request.py` | `LoRARequest`(msgspec.Struct):请求携带的适配器描述 |
| `vllm/lora/resolver.py` | `LoRAResolver` 抽象基类 + 全局注册表,支持从远端获取适配器 |
| `vllm/lora/peft_helper.py` | `PEFTHelper`:解析 `adapter_config.json` 并校验 PEFT 特性 |
| `vllm/lora/lora_weights.py` | `LoRALayerWeights` / `PackedLoRALayerWeights`:单层权重与打包 |
| `vllm/lora/lora_model.py` | `LoRAModel`:一个完整适配器的权重容器与加载 |
| `vllm/lora/model_manager.py` | `LoRAModelManager` / `LRUCacheLoRAModelManager`:适配器注册、激活、缓存 |
| `vllm/lora/worker_manager.py` | `WorkerLoRAManager` / `LRUCacheWorkerLoRAManager`:worker 侧加载与换入换出 |
| `vllm/lora/layers/` | `BaseLayerWithLoRA` 及全部线性 / MoE / 词表包装层 |
| `vllm/lora/punica_wrapper/` | `PunicaWrapperBase` 及 GPU/CPU/XPU 实现,维护内核元数据 |
| `vllm/lora/ops/` | `lora_shrink` / `lora_expand` / `fused_moe_lora` 等 torch/triton/xpu 内核 |
| `vllm/lora/utils.py` | `from_layer`(层替换工厂)、权重名解析、packed 映射等工具 |

### 请求表示:LoRARequest

定义于 `vllm/lora/request.py`,继承 `msgspec.Struct(omit_defaults=True, array_like=True)`,可经 msgpack 跨进程传递:

| 字段 | 类型 | 说明 |
|---|---|---|
| `lora_name` | `str` | 适配器名,作为跨引擎的相等性标识 |
| `lora_int_id` | `int` | 全局唯一整数 id,`__post_init__` 强制 `> 0` |
| `lora_path` | `str` | 本地目录或 HF/ModelScope repo id,不可为空 |
| `base_model_name` | `str \| None` | 目标基座模型名 |
| `tensorizer_config_dict` | `dict \| None` | tensorizer 流式反序列化配置 |
| `load_inplace` | `bool` | 为 True 时即使同 id 已缓存也强制重载并原位替换 |
| `is_3d_lora_weight` | `bool` | MoE 权重是否为 3D 融合布局(仅 `enable_mixed_moe_lora_format` 时被查询) |

`__eq__`/`__hash__` 均基于 `lora_name`,使同一适配器在不同引擎(如 DP)间可互相识别。`adapter_id`/`name`/`path` 为 `lora_int_id`/`lora_name`/`lora_path` 的属性别名。

### 适配器解析:LoRAResolver

`vllm/lora/resolver.py`:`LoRAResolver` 抽象类声明 `async resolve_lora(base_model_name, lora_name) -> LoRARequest | None`,由实现方负责"按名定位并下载"适配器(如从 S3/blob 存储)。`_LoRAResolverRegistry` 提供 `register_resolver`/`get_resolver`/`get_supported_resolvers`,全局单例 `LoRAResolverRegistry` 承载注册表。

### 请求端到端分发流程

```
前端 add_request(lora_request)  → EngineCoreRequest.lora_request
        ↓ v1/engine/__init__.py
scheduler 调度 → Request.lora_request  → EngineInput / InputBatch 构建
        ↓ v1/worker/gpu_input_batch.py:489-499
request_lora_mapping[req_index] = lora_id   # 0 表示无 LoRA
lora_id_to_lora_request[lora_id] = request.lora_request
        ↓ gpu_model_runner.prepare_inputs (gpu_model_runner.py:2345)
set_active_loras(input_batch, num_scheduled_tokens, num_sampled_tokens)
        ↓ lora_model_runner_mixin.py:77-83
LoRAMapping(token_lora_mapping, prompt_lora_mapping, is_prefill=True)
lora_manager.set_active_adapters(lora_requests, mapping)
        ↓ model_manager.set_adapter_mapping → punica_wrapper.update_metadata
内核元数据就绪 → 各层 forward 调用 add_lora_linear/add_lora_fused_moe 执行
```

关键拆分(`gpu_input_batch.py:1005 make_lora_inputs`):`token_lora_mapping` 大小为 `Σ num_scheduled_tokens`(每个 token 对应一个 LoRA id),`prompt_lora_mapping` 大小为 `Σ num_sampled_tokens`(采样步使用);`lora_requests` 为该 batch 用到的全部 `LoRARequest` 集合。请求离开 batch 时(`gpu_input_batch.py:551`)从映射表删除对应 id。

### 与模型执行器的衔接

本版本没有独立 `apply_lora` 方法——层注入发生在模型加载期(`model_manager._create_lora_modules` 用包装层替换原子模块),前向期每个被包装层的 `forward` 内联执行"基座层计算 + LoRA 增量":

- `LoRAModelManager.set_adapter_mapping(mapping)` 内部先比对 `_last_mapping` 与 `_last_slot_layout`,只有变化时才重建 punica 元数据,避免每步重复 GPU→CPU 同步。
- `LoRAMapping`(`layers/utils.py`)字段:`index_mapping`(batch 行→LoRA id)、`prompt_mapping`、`is_prefill`、`type`(`LoRAMappingType.LANGUAGE/TOWER/CONNECTOR`,多模态 tower/connector 用)。
- `PunicaWrapperBase.update_metadata` 用 `convert_mapping`(`punica_wrapper/utils.py`)把映射翻译为 4 个索引张量:`token_lora_indices`、`sampler_indices`、`sampler_indices_padded`、`embeddings_indices`;id 为 -1 表示"无 LoRA"。prefill 时再经 `compute_meta` 用 `unique_consecutive` 聚合连续同 LoRA 的序列,供 SGMV 内核按"聚类后 batch"执行。
- worker 侧按需热加载:`Executor.add_lora` 经 `collective_rpc("add_lora")` → `gpu_worker.py:1214` → `model_runner.add_lora` → `lora_manager.add_adapter`,即插即用,不重启引擎。

### LoRAConfig 关键配置

定义于 `vllm/config/lora.py`,参与 `compute_hash()`(影响计算图结构的字段:max_lora_rank、max_loras、fully_sharded_loras、lora_dtype、target_modules 等):

| 字段 | 默认 | 说明 |
|---|---|---|
| `max_lora_rank` | 16 | 最大 rank(Literal: 1/8/16/32/64/128/256/320/512),决定 stacked 缓冲 rank 维 |
| `max_loras` | 1 | 单 batch 最多激活的 LoRA 数(即 GPU slot 数) |
| `max_cpu_loras` | =max_loras | CPU 缓存上限,必须 `>= max_loras` |
| `fully_sharded_loras` | False | 是否全张量并行分片 LoRA 权重 |
| `lora_dtype` | "auto" | "auto" 时取基座模型 dtype |
| `target_modules` | None | 部署期限定模块后缀,None 表示全支持模块 |
| `specialize_active_lora` | False | 按激活 LoRA 数量专门化 CUDA graph |
| `enable_mixed_moe_lora_format` | False | 强制通用 2D MoE wrapper,2D/3D 适配器共存 |
| `enable_moe_shared_loras` | False | MoE 专家共享权重布局 |
| `enable_tower_connector_lora` | False | 多模态 tower/connector 的 LoRA(实验性) |

### 关于 Prompt Adapter

本版本 `vllm/model_executor/layers/` 下不存在 `prompt_adapter` 目录,全库搜索无 `PromptAdapter` 引用,即当前源码未实现独立 prompt adapter 模块;可注入的适配器类型仅为 LoRA。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
