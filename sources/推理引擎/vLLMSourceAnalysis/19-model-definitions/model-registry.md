## ModelRegistry 模型注册与选中机制

本文基于 `vllm/model_executor/models/registry.py` 与 `vllm/config/model.py`，说明模型如何被注册、如何在启动时被引擎选中。

### 注册表数据组织

`registry.py` 用一组**架构名 → (模块名, 类名)** 的 dict 描述全部受支持模型（约 390 个架构名）：

| 字典 | 条目数 | 用途 |
|---|---|---|
| `_TEXT_GENERATION_MODELS` | 131 | 纯文本自回归（`*ForCausalLM` 等） |
| `_MULTIMODAL_MODELS` | 119 | 多模态（视觉/音频/ASR，`*ForConditionalGeneration`） |
| `_SPECULATIVE_DECODING_MODELS` | 56 | 投机解码草稿头（EAGLE/Medusa/MTP/DFlash/DSpark） |
| `_EMBEDDING_MODELS` | 34 | 文本与多模态 embedding 模型 |
| `_SEQUENCE_CLASSIFICATION_MODELS` | 13 | 分类/rerank 模型 |
| `_TRANSFORMERS_SUPPORTED_MODELS` | 8 | 无 vLLM 原生实现、走 Transformers 后端 |
| `_TOKEN_CLASSIFICATION_MODELS` / `_REWARD_MODELS` / `_LATE_INTERACTION_MODELS` | 6/3/9 | token 分类、奖励模型、late-interaction（ColBERT） |
| `_TRANSFORMERS_BACKEND_MODELS` | 11 | `Transformers*` 后端实现类自身 |

`_VLLM_MODELS = {**以上全部}` 合并为一张总表，再统一包装为全局单例：

```python
ModelRegistry = _ModelRegistry({
    model_arch: _LazyRegisteredModel(
        module_name=_resolve_module_name(mod_relname),
        class_name=cls_name,
    )
    for model_arch, (mod_relname, cls_name) in _VLLM_MODELS.items()
})
```

- `_resolve_module_name`：相对名（如 `"llama"`）补全为 `vllm.model_executor.models.llama`；以 `vllm.` 开头的完整路径（如 `"vllm.models.deepseek_v4"`）原样保留，用于非本目录的独立包模型。
- 额外表：`_PREVIOUSLY_SUPPORTED_MODELS`（架构→最后支持版本，用于给出更友好的报错）、`_OOT_SUPPORTED_MODELS`（转给外部插件，如 `BartModel`）。

### 注册条目的两种形态

`_BaseRegisteredModel` 抽象出"可 inspect + 可 load"两种操作，派生两类：

| 类 | 触发条件 | 行为 |
|---|---|---|
| `_RegisteredModel` | 传入 `nn.Module` 类 | 立即计算 `_ModelInfo`，`load_model_cls()` 直接返回类 |
| `_LazyRegisteredModel` | 传入 `"<module>:<class>"` 字符串 | 推迟 import；`inspect` 走**子进程 + 磁盘缓存**，避免在探测能力时初始化 CUDA |

`register_model(model_arch, model_cls)`（公开 API，供插件/OOT 使用）按类型分派：字符串必须是 `<module>:<class>` 两段式，类必须是 `nn.Module` 子类；重复注册同一架构会覆盖。

### 懒加载模型的能力探测（inspect）

`_LazyRegisteredModel.inspect_model_cls()` 返回 `_ModelInfo`（frozen dataclass），字段全部由 `_ModelInfo.from_model_cls` 从模型类的能力接口汇总而来：

| 字段（节选） | 来源 |
|---|---|
| `is_text_generation_model` / `is_pooling_model` | `interfaces_base.is_*` |
| `attn_type` / `default_seq_pooling_type` / `score_type` | `interfaces_base` 类属性或装饰器 |
| `supports_multimodal` / `supports_multimodal_raw_input_only` / `supports_encoder_tp_data` | `interfaces.SupportsMultiModal` 类标志 |
| `supports_pp` / `has_inner_state` / `is_attention_free` / `is_hybrid` | `interfaces.SupportsPP` 等协议 |
| `supported_video_pruning_methods` / `supports_mm_device_do_normalize` | `getattr(model, ..., default)` |

探测流程：先按模块文件内容算哈希 → 尝试从 `$VLLM_CACHE_ROOT/modelinfos/*.json` 读缓存；缓存 miss 时用 `_run_in_subprocess` 在**独立 Python 子进程**（`python -m vllm.model_executor.models.registry`，cloudpickle 传闭包）中导入模型并计算 `_ModelInfo`，再原子写回缓存。这样主进程不会因导入模型而拉起 CUDA。

### 引擎选中模型的解析顺序

调用链：`model_loader/utils.py:_get_model_architecture` 读 `hf_config.architectures` → `model_config.registry.resolve_model_cls(architectures, model_config)`。解析分四步：

1. `model_impl == "transformers"`（或 `"terratorch"`）：直接解析到 Transformers 后端类。
2. `convert_type == "none"` 且所有 arch 都不在表中：尝试 `_try_resolve_transformers`（若 `model_impl == "auto"`）——即校验 HF 类存在、`auto_map` 可加载、`is_backend_compatible()`，命中则回退到 `TransformersForCausalLM` 等后端类并打印警告。
3. 逐个 arch：`_normalize_arch`（命中 `runner_type`/`convert_type` 架构默认值映射时换算为基类名，如 DFlash 后缀剥离）→ `_try_load_model_cls`（`lru_cache` + `current_platform.verify_model_arch` 平台校验）。
4. 全部失败 → `_raise_for_unsupported`：区分"注册过但 inspect 失败"、"旧版本支持过"、"已转 OOT 插件"、"完全未知"四类报错。

`inspect_model_cls` 与 `resolve_model_cls` 结构完全对称，前者返回 `(_ModelInfo, arch)`，后者返回 `(模型类, arch)`；`ModelConfig` 在 `__post_init__` 时先 `inspect` 得到 `_model_info`，后续 `is_multimodal_model`/`supports_pp` 等属性直接读缓存结果，不再重复探测。

### ModelConfig 与注册表的耦合

- `ModelConfig.registry` 属性（`config/model.py:1016`）是唯一访问入口，返回全局 `me_models.ModelRegistry`；访问前会执行 `_maybe_register_model_class_overrides`，把 `model_class_overrides` 里配置的 `(arch, target)` 就地注册进**本进程**的注册表（进程内幂等）。
- `get_model_architecture`（`model_loader/utils.py:233`）按 `(model, convert_type, runner_type, trust_remote_code, model_impl, architectures)` 哈希缓存解析结果。
- `convert_type` 非 `"none"` 时（`--convert-type embed/classify`），在注册表解析出 `model_cls` 之后再包一层 `as_embedding_model` / `as_seq_cls_model`（见 model-common-components.md）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
