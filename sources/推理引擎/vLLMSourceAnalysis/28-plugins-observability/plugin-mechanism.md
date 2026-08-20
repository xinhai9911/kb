## 插件机制与扩展点（plugins）

vLLM 插件系统基于 Python `importlib.metadata` 的 **entry points 分组（group）** 机制：外部包在打包元数据中把工厂函数注册到某个 `vllm.*` 组名下，运行期按组发现并加载。核心实现在 `vllm/plugins/__init__.py`。

### 插件组（PluginGroup）常量与加载时机

| 组常量 | 值 | 加载进程 | 用途 |
|---|---|---|---|
| `DEFAULT_PLUGINS_GROUP` | `vllm.general_plugins` | 所有进程（process0、EngineCore、worker） | 通用插件，加载后直接执行函数副作用（如注册新量化方法、设备类型、worker RPC） |
| `IO_PROCESSOR_PLUGINS_GROUP` | `vllm.io_processor_plugins` | 仅 process0 | IO 预处理/后处理插件，按模型配置挑选 |
| `PLATFORM_PLUGINS_GROUP` | `vllm.platform_plugins` | 所有进程（首次 `current_platform` 时） | 返回平台类 qualname，`vllm/platforms/__init__.py:229` 激活 |
| `STAT_LOGGER_PLUGINS_GROUP` | `vllm.stat_logger_plugins` | 仅 process0（async 模式） | 返回统计 logger 类，`vllm/v1/metrics/loggers.py:77` 实例化 |
| `ENDPOINT_PLUGINS_GROUP` | `vllm.endpoint_plugins` | 仅 API server 前端进程 | 返回 `EndpointPlugin` 实例，为 HTTP 服务挂路由 |

`load_general_plugins()`（`plugins/__init__.py:77`）用模块级 `plugins_loaded` 全局标志保证**单进程只加载一次**，但其 docstring 明确警告：插件可能被多进程重复加载，须设计为可幂等执行。调用点包括 `engine/arg_utils.py:2869`（CLI 解析前，让插件能向 `--quantization`/`--device` 注入新选项）、`v1/engine/core.py:118`（EngineCore 进程）、`v1/worker/worker_base.py:251`、`model_executor/models/registry.py:1521`。

### load_plugins_by_group 加载流程

```python
def load_plugins_by_group(group: str) -> dict[str, Callable[[], Any]]:
    discovered_plugins = entry_points(group=group)
    ...
    for plugin in discovered_plugins:
        if allowed_plugins is None or plugin.name in allowed_plugins:
            func = plugin.load()
            plugins[plugin.name] = func
```

关键行为：
- 用 `entry_points(group=...)` 按组发现，返回 `{插件名: 工厂函数}`；默认组用 DEBUG 日志、其余组用 INFO 日志打印清单。
- **白名单语义**由 `VLLM_PLUGINS`（`vllm/envs.py:1150`）决定：环境变量**未设置** → `None` → 加载组内全部插件；设置为**逗号分隔列表** → 仅加载名字命中的插件；设为**空字符串** → 解析为 `[""]`，即空白名单，不加载任何插件。
- 单个插件 `load()` 失败只记异常日志、跳过，不影响同组其他插件。

### Endpoint 插件：最严格的契约

`endpoint_plugins/interface.py` 定义 `EndpointPlugin`（`@runtime_checkable` Protocol），入口点必须解析到**零参可调用（类或工厂）**，返回满足该协议的对象：

| 成员 | 说明 |
|---|---|
| `name: str` | 插件名，用于日志与 `VLLM_PLUGINS` 白名单 |
| `required_tasks: tuple[SupportedTask, ...] \| None` | 服务器支持的 task 集合须与该集合相交才加载；`None` 表示无要求 |
| `attach_router(app: FastAPI)` | `build_app()` 挂完核心路由后调用，可覆盖同名核心路由，当前不做冲突检测（RFC #46565 跟进） |
| `async init_state(engine_client, state, args)` | `init_app_state()` 后初始化插件路由依赖的 app state；`engine_client` 允许为 `None`（CPU-only render server 无引擎） |

加载规则（`load_endpoint_plugins`，`plugins/__init__.py:93`）比通用组**更严格**——默认不加载：
- `VLLM_PLUGINS` 未设置时直接返回 `[]`，若发现已注册插件会打 WARNING（"Endpoint plugins add HTTP routes and must be explicitly allowlisted"）。
- 仅当插件在 `VLLM_PLUGINS` 白名单**且** `required_tasks` 通过时才实例化；`VLLM_PLUGINS=""` 视为"匹配不到任何名字的空白名单"而非"未设置"。

接线分两阶段（`entrypoints/openai/api_server.py`）：`_attach_endpoint_plugins`（Phase A，挂路由并写入 `app.state.endpoint_plugins`）与 `_init_endpoint_plugins_state`（Phase B，逐插件 `init_state`）。文档明确：插件只能通过 `EngineClient`（如 `collective_rpc`）触达引擎，不得另辟引擎访问路径；若还需引擎侧行为，应搭配 `vllm.general_plugins` 入口点成对注册。

### IO Processor 插件

`io_processors/interface.py:19` 的抽象基类 `IOProcessor(ABC, Generic[IOProcessorInput, IOProcessorOutput])` 定义引擎 I/O 前后处理：

| 方法 | 签名 | 说明 |
|---|---|---|
| `parse_data(data)` | `object → IOProcessorInput` | 解析请求体；旧名 `parse_request` 触发 DeprecationWarning（v0.19 移除） |
| `merge_sampling_params(params)` | `SamplingParams | None → SamplingParams` | 缺省时构造 `SamplingParams()` |
| `merge_pooling_params(params)` | `PoolingParams | None → PoolingParams` | 缺省时构造 `PoolingParams(task="plugin")`；两者由旧 `validate_or_generate_params` 拆分而来 |
| `pre_process(prompt, request_id, **kwargs)` | `→ PromptType \| Sequence[PromptType]` | 抽象方法 |
| `post_process(model_output, request_id, **kwargs)` | `→ IOProcessorOutput` | 抽象方法；async 版先按 id 排序再调用 |

选择机制（`io_processors/__init__.py`）：
- `has_io_processor` / `get_io_processor` 优先取 `plugin_from_init` 参数，否则读 **HF config 自定义字段 `io_processor_plugin`**（`model_config.hf_config.to_dict()`）。
- `get_io_processor` 加载 `vllm.io_processor_plugins` 组，逐一执行工厂拿到处理器类的 **qualname**，再 `resolve_obj_by_qualname` 解析并实例化为 `plugin_cls(vllm_config, renderer)`；模型要求的插件未安装时抛 `ValueError`。

### LoRA Resolver 插件

LoRA 解析器通过 `LoRAResolverRegistry.register_resolver(name, resolver)` 注册（`vllm/lora/resolver.py`）：

| Resolver | 文件 | 触发条件 | 行为 |
|---|---|---|---|
| `FilesystemResolver` | `lora_resolvers/filesystem_resolver.py` | `VLLM_LORA_RESOLVER_CACHE_DIR` 指向存在的目录 | 在缓存目录下找 `<lora_name>/adapter_config.json`，校验 `peft_type=="LORA"` 且 `base_model_name_or_path` 匹配后才构造 `LoRARequest(lora_name, lora_int_id=abs(hash(lora_name)), lora_path)` |
| `HfHubResolver` | `lora_resolvers/hf_hub_resolver.py` | `VLLM_LORA_RESOLVER_HF_REPO_LIST` 非空**且** `VLLM_PLUGINS` 含 `lora_hf_hub_resolver` | 继承 FilesystemResolver；先匹配 `<org>/<repo>`，`snapshot_download` 含 adapter_config 的子路径后复用文件系统解析；构造时打 WARNING 提示远程下载不安全、不适用于生产 |

HF resolver 多一道"显式 opt-in"门槛：`VLLM_LORA_RESOLVER_HF_REPO_LIST` 已设置但未在白名单启用时仅打 WARNING，不注册。

### 关键设计要点

- 插件本质是"运行期执行的工厂函数集合"，与配置无关、无状态注册表；通用组由进程各自调用 `load_general_plugins()` 触发，依赖 `plugins_loaded` 防止同进程重复执行。
- 安全立场分级：通用组"默认全加载"→ IO/Platform"按需加载"→ Endpoint"默认不加载、必须白名单"。因为 endpoint 插件直接暴露 HTTP 路由，攻击面最大（见 `docs/usage/security.md`）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
