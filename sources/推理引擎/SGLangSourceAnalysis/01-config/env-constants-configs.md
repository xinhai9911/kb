## 环境变量、常量与 configs 子配置

### 环境变量体系（srt/environ.py，1677 行）

`environ.py` 用描述符类构建 `SGLANG_*` 环境变量注册表，与 vLLM 的 `envs` 模块（dict + `__getattr__`）思路不同，SGLang 采用**类级描述符**：

| 类 | 解析 | 说明 |
|---|---|---|
| `EnvField` | — | 基类：`get()` 读取 `os.getenv(name)`，未设置返回默认值；解析失败 `warnings.warn` 并回退默认（`environ.py:57-76`）；`__bool__/__len__` 抛错强制 `.get()` |
| `EnvStr` / `EnvBool` / `EnvInt` / `EnvFloat` / `EnvTuple` / `EnvJSON` | 各自 `parse()` | bool 接受 `true/1/yes/y`；Tuple 按逗号切分；JSON 支持文件路径或字面量 |
| `EnvBoolWithAlias` / `EnvIntWithAlias` | 继承 `_DeprecatedEnvFallback` | 主变量未设时读取 `deprecated_name` 并告警迁移 |

```python
# environ.py:265-275（注册表片段）
class Envs:
    SGLANG_USE_MODELSCOPE = EnvBool(False)
    SGLANG_WARMUP_TIMEOUT = EnvFloat(-1)
    ...
envs = Envs()            # 单例，environ.py:1521
EnvField._allow_set_name = False   # 禁止后续追加
```

- 注册表含 **约 550 个字段**，按主题分组（Runtime/HTTP/Logging/内存池/调度/缓存/分布式/各模型后端如 Inkling、DSA、MiniMax 等），每组配三行横幅并限 <30 字段。
- `_DeprecatedEnv` 注册表 + `_handle_deprecated_envs()`（`environ.py:1629`）在导入时统一处理废弃变量：改名转发（如 `SGLANG_QUEUED_TIMEOUT_MS→SGLANG_REQ_WAITING_TIMEOUT` 且毫秒→秒）、极性翻转（`SGLANG_DISABLE_*→SGLANG_ENABLE_*`）、以及 `SGL_`→`SGLANG_` 前缀重写。
- `third_party_cache_defaults()` / `redirect_third_party_caches()`（`environ.py:1643`）把 Triton/Inductor/NV/FlashInfer 的 JIT 缓存统一重定向到 `SGLANG_CACHE_DIR` 下。
- server_args 解析管线 `_handle_environment_variables()`（`server_args.py:8150`）反向把 CLI 参数写回环境变量（如 `enable_torch_compile`→`SGLANG_ENABLE_TORCH_COMPILE`），供子进程继承。

### 常量（srt/constants.py，14 行）

```python
GPU_MEMORY_TYPE_KV_CACHE = "kv_cache"
GPU_MEMORY_TYPE_WEIGHTS = "weights"
GPU_MEMORY_TYPE_CUDA_GRAPH = "cuda_graph"
HEALTH_CHECK_RID_PREFIX = "HEALTH_CHECK"
GIB_BYTES = 1073741824  # 1024**3
```

三类 GPU 显存用途常量（KV 缓存 / 权重 / CUDA graph）贯穿显存规划；`GIB_BYTES` 用于内存换算。

### configs/ 子配置（srt/configs/）

`ServerArgs` 之外，模型与加载相关配置收敛于独立类（`__init__.py` 统一 re-export）：

| 类 | 形态 | 职责 |
|---|---|---|
| `ModelConfig`（model_config.py:257，约 2100 行） | 普通类（非 dataclass） | 加载 HF config、推导 `context_length`/模型形状、量化校验、多模态能力判定；`from_server_args(server_args, is_draft_model=...)`（:567）由 ServerArgs 投影构造，draft 模型复用同参数 |
| `LoadConfig`（load_config.py:41） | `@dataclass` | 权重加载：`LoadFormat` 枚举（:17）、`download_dir`、`ignore_patterns`（默认 `original/**/*`）、ModelOpt/remote-instance/weight-cache 选项；`__post_init__` 解析 `model_loader_extra_config` JSON |
| `DeviceConfig`（device_config.py:13） | 普通类 | 设备校验（`cuda/xpu/hpu/cpu/npu/musa/mps`）+ `torch.device` 构造 |
| `ModelConfigParserBase`（model_config_parser_registry.py） | 注册表 | `register_model_config_parser` 插件化解析 config.json（`model_config_parser="auto"` 时 `mistral`/`hf` 启发式选择） |
| 模型专用 dataclass（50+ 个） | `@dataclass` | Deepseek/Qwen/Kimi/GLM 等架构的自定义 config（`deepseek_v4.py`、`qwen3_5.py` 等） |
| `update_config.py` | 工具 | TP 不整除时 padding 模型 shape（head/KV-head/intermediate），记录 `original_*` 字段 |

### YAML 配置合并（server_args_config_parser.py，187 行）

`ConfigArgumentMerger` 实现 `--config` YAML 支持：解析 YAML 字典 → 转 `['--key', value, ...]` → 插入 CLI 参数流。布尔 `store_true` 仅 `true` 时追加 flag；dict 值 `json.dumps` 序列化；仅支持 `store_true`/`store` 两种 action，其余报错。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
