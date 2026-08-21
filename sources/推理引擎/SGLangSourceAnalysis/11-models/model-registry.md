## 模型注册机制（registry.py）与 vLLM 差异

本文基于 `sglang/srt/models/registry.py` 与 `sglang/srt/model_loader/utils.py`，说明 SGLang 模型如何被注册、启动时如何被引擎选中，并对照 vLLM `ModelRegistry`。

### 注册方式：`EntryClass` 约定 + 包扫描（无装饰器）

SGLang **不用 `@register_model` 装饰器**，也不用 vLLM 那样的「架构名 → (模块, 类)」静态 dict。它采用**模块级约定属性 `EntryClass`**：`sglang/srt/models/` 下每个模型文件在模块顶部定义 `EntryClass = SomeForCausalLM`（或多个类组成的 list），架构名即类的 `__name__`。

| 项 | SGLang | vLLM |
|---|---|---|
| 注册原语 | 模块级 `EntryClass` 属性 | `@register_model` 装饰器 / `register_model()` 全局 API |
| 索引组织 | 无分类 dict，单表 `_ModelRegistry.models` | `_TEXT_GENERATION_MODELS` / `_MULTIMODAL_MODELS` 等 10 张分类表 |
| 加载时机 | import 即导入全部类（模块顶层立即执行） | `_LazyRegisteredModel` 延迟 import |
| 能力探测 | 无 inspect 子进程/缓存机制 | `_ModelInfo` 子进程探测 + 磁盘缓存 |
| 多架构单文件 | `EntryClass = [A, B, C]` | 一个文件多类 + `_RegisteredModel` 表条目 |
| 重复注册 | `assert` 直接报错 | 后注册覆盖 |

### `import_model_classes` 扫描逻辑

`import_model_classes(package_name, strict=False)`（`registry.py:95`，`lru_cache`）：

1. `pkgutil.iter_modules(package.__path__, prefix)` 枚举包内全部模块；`ispkg` 子包直接跳过（故 `deepseek_common/`、`inkling_common/` 两个子包不参与注册）。
2. 模块名末段命中 `envs.SGLANG_DISABLED_MODEL_ARCHS`（`environ.py:290`）则跳过。
3. `importlib.import_module` 失败时：`strict=True` 抛异常，否则 `logger.warning` 后跳过（单模块坏不影响整包）。
4. `hasattr(module, "EntryClass")` 才注册；`EntryClass` 为 list 时逐类注册，并要求类名全局唯一（`assert ... not in model_arch_name_to_cls`）。

```python
# registry.py:130-134 全局单例与双包注册
ModelRegistry = _ModelRegistry()
ModelRegistry.register("sglang.srt.models")
if external_pkg := envs.SGLANG_EXTERNAL_MODEL_PACKAGE.get():
    ModelRegistry.register(external_pkg, overwrite=True)
```

- `register(package_name, overwrite=False, strict=False)`：`overwrite=True` 允许外部包覆盖内置架构（供 MindSpore 等后端插件复用，`mindspore.py:33` 单独调用 `import_model_classes("sgl_mindspore.models")`）。
- `models` 字典值直接是**类对象**（非 `(module, class)` 字符串），因此没有懒加载与子进程 inspect。

### 引擎选中链：`resolve_model_cls`

`model_loader/utils.py:get_model_architecture`（:197）调用 `ModelRegistry.resolve_model_cls(architectures)`（`registry.py:80`）：

| 步骤 | 行为 |
|---|---|
| `_normalize_archs` | 过滤出已注册的架构；若 `architectures` 中有未注册项，**追加 `TransformersForCausalLM` 兜底**并置于队尾 |
| `_try_load_model_cls` | 按顺序返回第一个命中的 `models[arch]` |
| `_raise_for_unsupported` | 全部失败时报错：区分「已注册但无法导入/检查」与「完全不支持」两类 |

调用前的特化改写（`utils.py:200-229`）：

| 场景 | 改写 |
|---|---|
| `is_embedding_gemma` | `architectures = ["EmbeddingGemmaModel"]` |
| 量化 Mixtral（非 fp8/compressed-tensors/gptq_marlin/awq_marlin/quark_int4fp8_moe） | `["QuantMixtralForCausalLM"]` |
| `model_impl == MINDSPORE` | `["MindSporeForCausalLM"]` |
| 原生不支持或 `model_impl == TRANSFORMERS` | `resolve_transformers_arch` 检查 HF `transformers` 类可加载性，兼容则回退到 `Transformers*` 后端类（见 representative-models.md） |

解析成功后把 `_resolved_model_arch` 写回 `ModelConfig`（`utils.py:231`）。对比 vLLM：SGLang 无 `ModelConfig.registry` 属性、无 `model_class_overrides` 进程内注册钩子、无 `inspect_model_cls` 能力缓存——`is_multimodal_model` 等判定直接靠模型类自身属性（如 `get_mm_processor`）。

### 顶层统计（registry 视角）

| 类别 | 数量 | 说明 |
|---|---|---|
| `srt/models/*.py` 顶层文件 | 216 | 不含两个子包 |
| 注册文件（声明 `EntryClass`） | 195 | 扫描即注册 |
| 组件/工具文件（无 `EntryClass`） | 21 | `utils.py`、`siglip.py`、`parakeet.py`、`idefics2.py` 等被 import 引用 |
| 子包（跳过扫描） | 2 | `deepseek_common/`、`inkling_common/` |
| 架构类总数（唯一） | 246 | 见 model-index 各表 |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
