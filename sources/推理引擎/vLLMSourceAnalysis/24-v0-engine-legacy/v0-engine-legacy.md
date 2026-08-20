## v0 引擎兼容层总览

`vllm/engine/` 在 V1 架构下已退化为「兼容层」：v0 时代的两大引擎类不再有独立实现，而是直接**别名**到 V1 引擎；真正有大量逻辑的只剩 `arg_utils.py`（CLI 参数装配）与 `protocol.py`（客户端协议）。

### 目录现状（本 checkout 实际文件）

| 文件 | 大小 | 角色 |
|---|---|---|
| `__init__.py` | 0 字节 | 空包标记，无导出 |
| `arg_utils.py` | 2890 行 | `EngineArgs`/`AsyncEngineArgs`：CLI 参数 → `VllmConfig` 的唯一入口 |
| `llm_engine.py` | 8 行 | `LLMEngine` 别名 shim → `vllm.v1.engine.llm_engine.LLMEngine` |
| `async_llm_engine.py` | 8 行 | `AsyncLLMEngine` 别名 shim → `vllm.v1.engine.async_llm.AsyncLLM` |
| `protocol.py` | 282 行 | `EngineClient` 协议 ABC + `StreamingInput` |

v0 历史文件（如旧版 `LLMEngine.step()` 单层调度实现）已被删除，只保留上述 5 个文件。v0 时代的 executor / worker / ModelRunner 等已删除实现的详细分析见 [20-model-executor-runner](../20-model-executor-runner/executor-architecture.md)（其 v0 侧基于共存期提交 `a4528f0cac`，与本文件当前现状对照阅读）。

### 别名 shim（核心事实）

`llm_engine.py` 全文：

```python
from vllm.v1.engine.llm_engine import LLMEngine as V1LLMEngine

LLMEngine = V1LLMEngine  # type: ignore
"""The `LLMEngine` class is an alias of [vllm.v1.engine.llm_engine.LLMEngine][]."""
```

`async_llm_engine.py` 全文：

```python
from vllm.v1.engine.async_llm import AsyncLLM

AsyncLLMEngine = AsyncLLM  # type: ignore
"""The `AsyncLLMEngine` class is an alias of [vllm.v1.engine.async_llm.AsyncLLM][]."""
```

关键点：

- 两个 shim **只有赋值别名**，没有子类化、没有 `__getattr__` 代理、没有 deprecated 装饰器。
- v1 `LLMEngine` 类自身的 docstring 写明 **「Legacy LLMEngine for backwards compatibility.」**（`vllm/v1/engine/llm_engine.py:60`），即 v1 保留了兼容形态而非删除。
- 因此 `vllm.engine.llm_engine.LLMEngine` 与 `vllm.v1.engine.llm_engine.LLMEngine` 是**同一个类对象**，导入路径不影响行为。

### 顶层导出与使用方

`vllm/__init__.py` 的 `MODULE_ATTRS` 懒加载映射仍指向 v0 路径：

| 顶层名称 | 懒加载路径 |
|---|---|
| `vllm.LLMEngine` | `.engine.llm_engine:LLMEngine` |
| `vllm.AsyncLLMEngine` | `.engine.async_llm_engine:AsyncLLMEngine` |
| `vllm.EngineArgs` / `vllm.AsyncEngineArgs` | `.engine.arg_utils:EngineArgs` / `:AsyncEngineArgs` |

- 离线入口 `vllm/entrypoints/llm.py:55` 的 `LLM` 类**直接** `from vllm.v1.engine.llm_engine import LLMEngine`（跳过 v0 别名），其 docstring 仍引导服务化用户使用 `vllm.AsyncLLMEngine`。
- v1 异步引擎 `vllm/v1/engine/async_llm.py` 反向依赖 v0 兼容层：`from vllm.engine.arg_utils import AsyncEngineArgs`、`from vllm.engine.protocol import EngineClient, StreamingInput` —— 即 **v1 引擎本身在使用 v0 的 CLI 参数类与协议定义**。
- 大量 entrypoints 通过 `from vllm.engine.protocol import EngineClient` 引用客户端契约（generate/serve/grpc/cohere 等）。

### 与 v1 引擎的对照（谁封装谁）

| 维度 | v0 兼容层（本目录） | v1 引擎 |
|---|---|---|
| `LLMEngine` | 别名，对象即 `v1.engine.llm_engine.LLMEngine` | 本体；`InputProcessor`/`OutputProcessor`/`EngineCoreClient` 组装 |
| `AsyncLLMEngine` | 别名，对象即 `v1.engine.async_llm.AsyncLLM` | 本体；后台 `output_handler` 任务消费 EngineCore 输出 |
| 引擎内核 | 无（旧单层调度已删除） | `v1/engine/core.py` `EngineCore`（独立进程/ZMQ） |
| 参数装配 | `EngineArgs`（两代共用，v1 也 import） | 复用 v0 `EngineArgs` |
| 协议 | `EngineClient` ABC（v1 `AsyncLLM` 实现它） | `AsyncLLM` 即实现类 |
| deprecated 标记 | 无显式装饰器 | v1 `LLMEngine` docstring 自述 "Legacy ... backwards compatibility" |

### v1 LLMEngine 兼容接口行为（别名后即其行为）

接口位于 `vllm/v1/engine/llm_engine.py`：

| 接口 | 签名 | 行为 |
|---|---|---|
| `add_request` | `(request_id: str, prompt, params, arrival_time=None, lora_request=None, tokenization_kwargs=None, trace_headers=None, priority=0, session_id=None, prompt_text=None) -> str` | `request_id` 非 `str` 抛 `TypeError`；`prompt` 为 `EngineCoreRequest` 时警告 deprecated（v0.18 移除）并直接采用，否则走 `input_processor.process_inputs`；`n>1` 时经 `ParentRequest` fan-out 复制为 n 个子请求 |
| `step` | `() -> list[RequestOutput \| PoolingRequestOutput]` | ① `engine_core.get_output()` → ② `output_processor.process_outputs` + `update_scheduler_stats` → ③ `engine_core.abort_requests(reqs_to_abort)` → ④ `logger_manager.record` 统计 |
| `abort_request` | `(request_ids: list[str], internal: bool = False)` | 先 `output_processor.abort_requests` 再 `engine_core.abort_requests`，双端清理 |
| `sleep`/`wake_up` | `(level=1, mode="abort")` / `(tags=None)` | level≥1 清多模态 cache 后下传 `engine_core` |
| `shutdown` | `(timeout=None)` | 关闭 client 与后台进程 |

- `AsyncLLM`（v1）实现 `EngineClient.generate/encode/abort/...` 等全部异步接口，见 `vllm/v1/engine/async_llm.py`；`LLM`/serve 实际驱动路径与其一致，仅同步/异步驱动方式不同。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
