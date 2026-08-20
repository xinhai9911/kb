## transformers_utils 配置适配层：HF config → ModelConfig

本文基于 `vllm/transformers_utils/config.py`、`config_parser_base.py`、`configs/`、`model_arch_config_convertor.py`，说明 HF config 如何被读取、定制并转换为 `ModelConfig` 可用的架构/参数字典。注意：本版本（Transformers v5 起，vLLM ≥0.24）将分词器拆至 `vllm/tokenizers/`（见 tokenizer-detokenizer.md），`transformers_utils/` 聚焦配置与处理器。

### 模块文件全景

| 文件 | 职责 |
|---|---|
| `config.py` | 核心：`get_config()` 入口、config parser 注册、`_CONFIG_REGISTRY`、RoPE/量化/投机补丁 |
| `config_parser_base.py` | `ConfigParserBase` 抽象基类（`parse` 返回 `(config_dict, PretrainedConfig)`） |
| `configs/` | HF 缺失或需覆盖的 `*Config` 类，按 `_CLASS_TO_MODULE` 懒加载 |
| `model_arch_config_convertor.py` | 把 `PretrainedConfig` 转成 `ModelArchitectureConfig`（含逐层异构处理） |
| `repo_utils.py` / `utils.py` | HF Hub 交互、模型重定向、safetensors 元数据解析（详见 weight-loading.md） |
| `processor.py` / `processors/` | 多模态输入处理器加载与注册（详见 tokenizer-detokenizer.md） |
| `dynamic_module.py` | `trust_remote_code` 动态模块类解析（静默失败封装） |

### config parser 注册机制

- `ConfigParserBase.parse(model, trust_remote_code, revision, code_revision, **kwargs) -> tuple[dict, PretrainedConfig]`，同时返回原始 config_dict 与实例化 config。
- `_CONFIG_FORMAT_TO_CONFIG_PARSER = {"hf": HFConfigParser, "mistral": MistralConfigParser}`；`get_config_parser(format)` 工厂获取，`@register_config_parser("xxx")` 装饰器可注册自定义解析器（须继承基类）。
- `ConfigFormat` 枚举：`auto`/`hf`/`mistral`。

### get_config 加载链路（config.py:687）

1. **格式探测**（`config_format="auto"`）：先查 `is_mistral_model_repo()`（仓库含 `consolidated*.safetensors`）且存在 `params.json` → `mistral`；否则存在 `config.json` → `hf`；两者皆无抛 `ValueError`。
2. `with_retry` 包住 `parser.parse(...)`，容忍并发 HF 缓存刷新瞬间看不到 config.json。
3. **architectures 兜底**：config 无 `architectures` 字段时，按 `model_type` 查 transformers 的 `MODEL_MAPPING_NAMES` 补 `architectures=[...]`（查不到则警告并提示传 `hf_overrides`）。
4. **量化配置**：优先 `config_dict["quantization_config"]`（ModelOpt ≥0.31 内嵌）；否则读同目录 `hf_quant_config.json`（ModelOpt ≤0.29 旧格式）。检测到 `scale_fmt="ue8m0"` 时自动置 `VLLM_USE_DEEP_GEMM_E8M0=1`。
5. **hf_overrides 应用**：`hf_overrides_kw`（dict）→ `config.update(kw)`；`hf_overrides_fn`（callable）→ `config = fn(config)`。
6. **RoPE 统一修补**：`patch_rope_parameters()` 对根 config、`get_text_config()`、`sub_configs` 逐一执行，标准化 `rope_parameters`、迁移 `rope_theta`/`rotary_emb_base` 等旧字段名（`getattr_iter` 带 warn 探测）。

### HFConfigParser.parse 细节（config.py:247）

| 步骤 | 关键行为 |
|---|---|
| 读取原始 dict | `PretrainedConfig.get_config_dict(model, revision, code_revision)`，`local_files_only` 跟随 `HF_HUB_OFFLINE` |
| 解析 model_type | 取 `config_dict["model_type"]`；为 `None` 且含 `speculators_config` 时归为 `"speculators"`；`hf_overrides` 可改写 model_type（callable 时用 dummy config 试算） |
| 投机解码特殊路径 | `model_type in {"eagle","speculators","medusa"}` → 直接用注册类 `from_pretrained`（不注册 AutoConfig） |
| 注册自定义类 | `model_type in _CONFIG_REGISTRY` → `_register_config_class()` 注册进 `AutoConfig`，使后续 AutoTokenizer/AutoProcessor 复用；若磁盘 model_type 与覆盖值不同则双名注册；注册后 `trust_remote_code=False`（不再是 remote code） |
| 正式加载 | `AutoConfig.from_pretrained(...)`；`ValueError` 含 "requires you to execute the configuration file" 时给出 `--trust-remote-code` 提示 |
| 收尾 | `_maybe_remap_hf_config_attrs`（如 `llm_config → text_config`） |

针对旧 Transformers 的兼容补丁：`_patch_hf_transformers_validate_rope`（`ignore_keys` 参数迁移）、`_patch_hf_transformers_allowed_layer_types`（扩展 `ALLOWED_LAYER_TYPES`，如 GLM-5.2 的 `deepseek_sparse_attention`）。

### _CONFIG_REGISTRY（config.py:72，LazyConfigDict）

`dict[model_type → config 类名]`，值为类名时经 `configs` 包 `__getattr__` 懒加载。要点：

| 类别 | 示例 |
|---|---|
| 复用 HF 官方类 | `kimi_k2 → DeepseekV3Config`、`deepseek_v32 → DeepseekV3Config`（注释：同架构） |
| vLLM 自定义类 | `chatglm → ChatGLMConfig`、`falcon` 旧版 `RefinedWeb/RefinedWebModel → RWConfig` |
| 多模态子类 | `hunyuan_vl`/`qwen3_5`/`step3_vl` 等一组 Config 均注册到同一 model_type |
| 投机解码集 | `_SPECULATIVE_DECODING_CONFIGS = {"eagle","speculators","medusa"}` |

`configs/__init__.py` 的 `_CLASS_TO_MODULE` 提供「类名 → 模块路径」映射（90+ 类，含 Inkling 指向 `vllm.models.inkling.configs` 与特殊项 `DeepseekV3Config → "transformers"`）。`configs/speculators/` 子包（`base.py`/`algos.py`）承载 speculators 格式解析；`maybe_override_with_speculators()`（config.py:631）在检测到 `speculators_config` 时提取投机配置、把 model/tokenizer 改指向 verifier 模型。

### MistralConfigParser（config.py:347）

- 读取 `params.json`；缺 `max_position_embeddings` 时经 HF config 回退（默认 128000）。
- 缺 `dtype` 时用 `get_safetensors_params_metadata` 读 `consolidated*.safetensors` 头部 dtype 推断（临时 patch HF 常量 `SAFETENSORS_SINGLE_FILE`）。
- `adapt_config_dict(config_dict, defaults=hf_config_dict)` 用 HF config 补齐缺失字段。

### ModelConfig 消费（vllm/config/model.py）

`ModelConfig.__init__`（model.py:608）调用 `get_config(...)` 得到 `self.hf_config`，随后：

```python
self.hf_text_config = get_hf_text_config(self.hf_config)   # 多模态取 text 子配置
self.model_arch_config = self.get_model_arch_config()      # 架构参数化
self.runner_type / convert_type = registry 判定
```

`get_model_arch_config()`（model.py:882）按 `hf_config.model_type` 查 `MODEL_ARCH_CONFIG_CONVERTORS`，默认 `ModelArchConfigConvertorBase`。convertor 的字段提取与异构合并细节见 [config-mapping_part2.md](config-mapping_part2.md)。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
