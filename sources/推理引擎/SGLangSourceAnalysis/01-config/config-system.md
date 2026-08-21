## ServerArgs 配置体系总览

SGLang 无 vLLM 式的 `VllmConfig` 聚合类：`ServerArgs`（`sglang/srt/server_args.py`，约 10073 行）自身即是全部 CLI/服务参数的唯一载体，经 `__post_init__` 解析后以只读形态发布，再投影为 `RuntimeContext` 的配置命名空间袋（config bag）。

### ServerArgs 类结构

`ServerArgs` 是普通 `@dataclasses.dataclass`（`server_args.py:453-454`），字段通过 `typing.Annotated` 挂三种元数据（`arg_groups/arg_utils.py`）：

| 注解 | 类型 | 作用 |
|---|---|---|
| `A[T, "帮助文本"]` | `Annotated[T, str]` | 简写形式，字符串即 help |
| `Arg(help, choices, aliases, type_parser, nargs, action, no_cli, resolvable)` | 冻结 dataclass | 完整 CLI 元数据（`arg_utils.py:61-83`） |
| `NS("exec.kernel")` | 冻结 dataclass | 字段所属配置命名空间路径，驱动 `RuntimeContext` 配置包（约 475 处） |

```python
# server_args.py:1019-1028（字段声明示例）
nnodes: A[int, "The number of nodes.", NS("parallel")] = 1
tp_size: A[int, Arg(help="The tensor parallelism size.",
                    aliases=["--tensor-parallel-size"]), NS("parallel")] = 1
```

`add_cli_args_from_dataclass`（`arg_utils.py:218`）扫描 `A[T, ...]` 注解自动生成 argparse 参数：字段名 `tp_size` 派生 `--tp-size`，`Arg.aliases` 提供 `--tensor-parallel-size`；`dest` 锚定回字段名保证 `argparse.Namespace` 属性与 dataclass 字段一致。`no_cli=True` 的字段（如 `enable_dsa_prefill_context_parallel`）不暴露 CLI。少数字段（动态 choices、`--config`、废弃 flag）手工注册于 `add_cli_args`（`server_args.py:8748`）。

### 构造路径

| 入口 | 机制 |
|---|---|
| CLI（`sglang serve`） | `ServerArgs.from_cli_args(args)`（`server_args.py:9010`）：从 Namespace 取有值的 dataclass 字段组装实例 |
| Python `sglang.Engine(**kwargs)` | `entrypoints/engine.py:251`：`self.server_args_class(**kwargs)`，kwargs 与 ServerArgs 字段一一对应 |
| YAML 配置文件 | `--config` 由 `ConfigArgumentMerger`（`server_args_config_parser.py`）合并，优先级 **CLI > Config > 默认值**；仅支持 `store_true`/`store` action |
| 直接传对象 | `Engine(server_args=...)` 跳过 kwargs 构造 |

### 解析管线（__post_init__）

`__post_init__`（`server_args.py:3617`）调用 `_run_resolution_pipeline()`（`server_args.py:3620`）——一个约 60 步的**有序 dispatcher**，每步是命名 `_handle_*` 方法，按领域排序：

```
模型路径/能力 → 并行(TP/PP/DP/CP/MoE-EP) → 内核/attention 后端
→ CUDA graph → 内存/缓存(mem_fraction_static, chunked_prefill_size)
→ 语法/投机解码 → 加载格式 → 环境变量传播 → 各类校验
→ 末尾 materialize_declarations(self) 一次性落地声明
```

要点：
- `model_path in ["none","dummy"]` 时提前短路，跳过模型相关步骤。
- `resolvable=True` 字段经 `arg_groups/overrides.py`（2733 行）声明式解析：`_resolved` 只读视图 + `_late_resolution`（`server_args.py:9099`）+ `materialize_declarations`。
- 解析完成后 `__setattr__` 守卫（`server_args.py:9110`）令字段只读，报错提示改用 `get_context().override(...)`。
- `check_server_args()`（`server_args.py:9225`）做断言级交叉校验（如 `chunked_prefill_size % page_size == 0`、优先级调度要求 `schedule_policy in [fcfs, lof]`）。

### RuntimeContext 配置包

`runtime_context.py` 把解析后的配置按 `NS(...)` 路径投影为只读配置袋：`get_exec()/get_memory()/get_schedule()/get_model()/get_serving()/get_mm()/get_disagg()/get_observability()` 等，属性链读取如 `get_exec().moe.moe_runner_backend`；`get_server_args()` 保留原始只读记录供调试复现。`PortArgs.init_new`（`server_args.py:9933`）则从 server_args 派生 ZMQ/IPC 端口与 `instance_id`。

### 与 vLLM 对照

| 维度 | vLLM | SGLang |
|---|---|---|
| CLI 入口 | `EngineArgs`（`vllm/engine/arg_utils.py`） | `ServerArgs`（`srt/server_args.py`） |
| 聚合配置 | `VllmConfig`（pydantic dataclass，`vllm/config/vllm.py`） | 无聚合类；ServerArgs + RuntimeContext 配置袋 |
| 类型体系 | pydantic dataclass（`config()` 装饰器，`extra="forbid"`） | 普通 `dataclasses.dataclass` + `Annotated` |
| CLI 生成 | 手工 `add_argument` | `add_cli_args_from_dataclass` 注解自动派生 |
| 哈希 | `compute_hash()` 作 torch.compile / CUDA graph 缓存键 | 无 `compute_hash` |
| 子配置 | `ModelConfig/CacheConfig/ParallelConfig/...` | `ModelConfig/LoadConfig/DeviceConfig` 等（见 env-constants-configs.md） |
| 覆盖机制 | `utils.update_config` 递归合并 + `with_hf_config` | `arg_groups/overrides.py` 声明式解析 + `materialize_declarations` |
| 环境变量 | `vllm.envs` 模块 + `environment_variables` dict + `validate_environ` | `sglang.srt.environ` 的 `Envs` 描述符类 |
| 校验 | `VllmConfig.__post_init__` + `verify_and_update_config` | `_run_resolution_pipeline` 有序 `_handle_*` + `check_server_args` |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
