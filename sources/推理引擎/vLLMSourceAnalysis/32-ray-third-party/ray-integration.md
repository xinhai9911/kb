## vllm/ray 包：Ray 后端集成基础设施

`vllm/ray/` 共 3 个文件：`__init__.py`（空包标记）、`lazy_utils.py`（Ray 惰性探测）、`ray_env.py`（驱动→Worker 环境变量传播）。其设计要点是**模块本身不依赖 Ray 是否安装**——对 `ray` 的所有 `import` 都发生在函数内部并包在 try/except 中，全项目可在无 Ray 环境下安全引用。

### lazy_utils：Ray 惰性探测

| 函数 | 行为 | 失败语义 |
|---|---|---|
| `is_ray_initialized()` | `import ray` 后返回 `ray.is_initialized()` | `ImportError`/`AttributeError` → `False` |
| `is_in_ray_actor()` | Ray 已初始化 且 `ray.get_runtime_context().get_actor_id()` 非 `None` | 同上 → `False` |

使用方（均不做顶层 `import ray`，靠此封装探测）：

| 调用方 | 用途 |
|---|---|
| `engine/arg_utils.py:2037` | `is_ray_initialized()` 检测 Ray Serve 上下文（Ray task 中调用 `create_engine_config`），取 `ray.get_runtime_context().runtime_env`，日志对 `env_vars` 脱敏后打印 |
| `engine/arg_utils.py:2056` | `is_in_ray_actor()` 时取 `ray.util.get_current_placement_group()`，将当前 placement group 传给 spawn 的子进程 |
| `utils/system_utils.py:134` | `_maybe_force_spawn()` 在 Ray actor 内强制 `spawn` 多进程启动方式，并把 `RAY_ADDRESS = ray.get_runtime_context().gcs_address` 写入环境供子进程连接集群 |

### ray_env：驱动→Worker 环境变量传播

核心 API `get_env_vars_to_copy(exclude_vars, additional_vars, destination)`（`destination` 仅用于日志标签）返回**需要从 driver 复制到 Ray actor/worker 的环境变量名集合**，逻辑为四类来源的并集再扣除排除集：

```
result = (环境变量注册表) ∪ (前缀命中) ∪ (显式单变量) ∪ (调用方 additional_vars)
result -= (exclude_vars ∪ RAY_NON_CARRY_OVER_ENV_VARS)
```

| 来源 | 内容 |
|---|---|
| `vllm.envs.environment_variables` | vLLM 注册的全部 `VLLM_*` 环境变量名（模块级 dict 的键） |
| 前缀命中 | `os.environ` 中名字以 `DEFAULT_ENV_VAR_PREFIXES` ∪ `VLLM_RAY_EXTRA_ENV_VAR_PREFIXES_TO_COPY`（逗号分隔 CSV）任一前缀开头 |
| 显式单变量 | `DEFAULT_EXTRA_ENV_VARS` ∪ `VLLM_RAY_EXTRA_ENV_VARS_TO_COPY`（CSV） |
| 调用方补充 | `additional_vars`，如平台特定变量 |
| 排除 | `exclude_vars`（如 worker 专用变量）+ 用户黑名单 |

内置默认前缀与单变量：

| 前缀/变量 | 覆盖内容 |
|---|---|
| `VLLM_` | vLLM 全部运行配置 |
| `FLASH_ATTENTION_` | FlashAttention 后端开关 |
| `LMCACHE_` | KV cache 相关 |
| `NCCL_` / `UCX_` | 分布式通信库配置 |
| `HF_` / `HUGGING_FACE_` | HuggingFace 下载/缓存 |
| `PYTHONHASHSEED` | 单变量，保证 hash 种子一致 |

**用户黑名单机制**：黑名单文件 `RAY_NON_CARRY_OVER_ENV_VARS_FILE = $VLLM_CONFIG_ROOT/ray_non_carry_over_env_vars.json`（`VLLM_CONFIG_ROOT` 默认 `~/.config/vllm`），以 JSON 数组形式列出禁止传播的变量；文件缺失时为空集，JSON 解析失败时告警并回退空集。`get_env_vars_to_copy` 末尾会打印将被复制（且当前确实存在）的变量列表。

### 消费链路（与 08-distributed / 02-engine-core 的衔接）

| 消费者 | 用法 |
|---|---|
| `v1/executor/ray_executor.py:323` `RayDistributedExecutor` | 在 `_run_workers` 中 `get_env_vars_to_copy(exclude_vars=WORKER_SPECIFIC_ENV_VARS, additional_vars=set(current_platform.additional_env_vars), destination="workers")`，把 `os.environ` 中命中项并入每 worker 的 `all_args_to_update_environment_variables`，再经 `collective_rpc("update_environment_variables", ...)` 广播；此外 `_update_noset_device_env_vars` 把 `current_platform.ray_noset_device_env_vars` 置 `"1"`（禁设备抢占）。与 [08-distributed/worker-executor.md](../08-distributed/worker-executor.md) 中的 `RayDistributedExecutor`/`RayExecutorV2`（`VLLM_USE_RAY_V2_EXECUTOR_BACKEND=1`）对应 |
| `v1/executor/ray_env_utils.py` `get_driver_env_vars(worker_specific_vars)` | 直接返回 `os.environ` 全部项减去 worker 专用变量与 `RAY_NON_CARRY_OVER_ENV_VARS`，供 v2 executor 使用 |
| `v1/engine/utils.py:403` `CoreEngineActorManager` | 为 `EngineCoreActor`/`DPMoEEngineCoreActor` 构造 `RuntimeEnv(env_vars=...)`（由 `get_env_vars_to_copy(destination=actor_class.__name__, exclude_vars=WORKER_SPECIFIC_ENV_VARS)` 得到），把 driver 环境带入 Ray actor 形态的 EngineCore（见 02-engine-core） |

### 相关 VLLM_* 环境变量（`vllm/envs.py`）

| 变量 | 默认 | 用途 |
|---|---|---|
| `VLLM_CONFIG_ROOT` | `~/.config/vllm` | 黑名单 JSON 所在目录 |
| `VLLM_RAY_EXTRA_ENV_VAR_PREFIXES_TO_COPY` | `""` | 追加前缀（CSV，累加不覆盖） |
| `VLLM_RAY_EXTRA_ENV_VARS_TO_COPY` | `""` | 追加单变量（CSV，累加不覆盖） |
| `VLLM_RAY_PER_WORKER_GPUS` | `1.0` | 每 Ray worker 的 GPU 数量 |
| `VLLM_RAY_BUNDLE_INDICES` | `""` | worker bundle 索引 |
| `VLLM_RAY_DP_PACK_STRATEGY` | `strict` | DP worker 打包策略（strict/fill/span） |
| `VLLM_RAY_DP_PLACEMENT_NODE_IPS` | `""` | DP placement 指定节点 IP |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
