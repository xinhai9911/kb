## Engine 离线接口（同步 / 异步 generate）

源码：`sglang/srt/entrypoints/engine.py`（约 75KB，`Engine` 类）+ `sglang/srt/entrypoints/EngineBase.py`（抽象基类）+ `sglang/srt/entrypoints/engine_score_mixin.py`（打分扩展）。在线 HTTP 入口见 [http-server.md](http-server.md)。

### 接口层次

| 类 | 文件:行 | 角色 |
|---|---|---|
| `EngineBase` | `entrypoints/EngineBase.py:7` | 抽象基类：`generate`/`flush_cache`/`update_weights_from_tensor`/`load_lora_adapter`/`release_memory_occupation`/`resume_memory_occupation`/`shutdown` 等抽象方法 |
| `Engine` | `entrypoints/engine.py:207` | 离线推理主类，实现 `EngineBase`，混入 `EngineScoreMixin`；构造即拉起 Scheduler/Detokenizer 子进程并返回 TokenizerManager 句柄 |
| `EngineScoreMixin` | `entrypoints/engine_score_mixin.py` | 打分扩展：`score()` 把 `data_1/data_2` 拼成对比序列走 `GenerateReqInput` |
| `HttpServerEngineAdapter` | `entrypoints/http_server_engine.py:49` | `EngineBase` 的 HTTP 形态：子进程起 `launch_server`，方法经 HTTP 请求转发（供 VerlEngine 等外部调用方用） |
| `init_tokenizer_manager` | `entrypoints/engine.py:155` | 在引擎主进程内实例化 `TokenizerManager` + `TemplateManager`，并按 chat template 自动推断 `reasoning_parser`/`tool_call_parser` |

`Engine` 与 `launch_server` 共用同一套 `_launch_subprocesses`（:1060），区别仅在：离线场景主进程不挂 FastAPI，直接调用 `tokenizer_manager.generate_request`。

### 构造与进程拓扑

`Engine(**kwargs)`（:232）参数与 `ServerArgs` 一致（`kwargs` 直接构造 `ServerArgs`，默认 `log_level="error"`），也可直接传 `server_args=` 实例。构造流程：

1. `load_plugins()` → 解析 `ServerArgs` → `atexit.register(self.shutdown)` 自动回收。
2. `self._launch_subprocesses(...)`：拉起 Scheduler 子进程（每 TP rank 一个）、DetokenizerManager 子进程，主进程内初始化 `TokenizerManager`；多 tokenizer 模式改用 `MultiTokenizerRouter`。进程模型细节见 [00-overview](../00-overview/architecture_part1.md)。
3. 初始化 ZMQ DEALER socket `self.send_to_rpc`（`rpc_ipc_name`，`node_rank==0` 时），用于控制面 RPC。
4. 获取/创建 asyncio 事件循环 `self.loop`（离线同步 API 用它 `run_until_complete`）。

### generate 与 async_generate

`Engine.generate`（:360）与 `Engine.async_generate`（:470）签名完全一致（`prompt`/`sampling_params`/`input_ids`/多模态/`return_logprob`/`stream`/`lora_path`/`routed_dp_rank`/`session_id`/`priority`/`cache_salt` 等），统一构造 `GenerateReqInput` 后交给 TokenizerManager：

```python
def generate(self, prompt=None, sampling_params=None, input_ids=None, ...,
             stream: bool = False, ...) -> Union[Dict, Iterator[Dict]]:
    obj = GenerateReqInput(text=prompt, input_ids=input_ids, sampling_params=sampling_params, ...)
    generator = self.tokenizer_manager.generate_request(obj, None)   # request=None（无 HTTP 层）
    if stream:
        def generator_wrapper():                        # 同步流式：事件循环逐帧转 yield
            while True:
                try:
                    chunk = self.loop.run_until_complete(generator.__anext__())
                    yield chunk
                except StopAsyncIteration:
                    break
        return generator_wrapper()
    else:
        return self.loop.run_until_complete(generator.__anext__())   # 同步非流式：取首帧
```

| 方法 | 返回 | 说明 |
|---|---|---|
| `generate` | `Dict` / `Iterator[Dict]` | 同步；`stream=True` 时用 `self.loop.run_until_complete` 包装异步生成器 |
| `async_generate` | `Dict` / `AsyncIterator[Dict]` | 异步；`stream=True` 时直接返回 async generator |
| `encode` / `async_encode` | `Dict` | embedding 离线接口（`EmbeddingReqInput`），同步版同样走 `run_until_complete` |
| `score(query, items, label_token_ids, apply_softmax, item_first, ...)`（`EngineScoreMixin`，`engine_score_mixin.py:29`） | `ScoreResult` | 打分：CausalLM 模型返回各 `label_token_id` 的生成概率，SequenceClassification 模型返回分类头 logits；另有 `async_score` 异步版 |

### 其他公开方法

| 方法 | 用途 |
|---|---|
| `flush_cache` / `open_session` / `close_session` | 清缓存 / 会话式提示（`session_params`） |
| `start_profile` / `stop_profile` / `start_expert_distribution_record` 等 | 剖析与 MoE 专家分布记录 |
| `update_weights_from_tensor/distributed/disk/ipc` / `update_weight_version` / `init_weights_update_group` / `destroy_weights_update_group` / `get_weights_by_name` | 权重热更新设施（RL 训练、模型热切换） |
| `load_lora_adapter` / `unload_lora_adapter` / `async_load_lora_adapter` | 运行时 LoRA 热加载/卸载（不重启引擎） |
| `release_memory_occupation` / `resume_memory_occupation` | 显存释放/恢复（MPS 等受限平台） |
| `freeze_gc` | 冻结/解冻 Python GC（warmup 后常用） |
| `collective_rpc(method, **kwargs)` | 对所有 scheduler 广播 RPC |
| `get_server_info` / `get_model_info` | 对应 HTTP 的 `/server_info`、`/model_info` |
| `shutdown` | 停子进程并清理资源（`atexit` 自动注册） |

### 与 vLLM 离线 API 对照

| 维度 | SGLang `Engine` | vLLM `LLM`（`vllm/entrypoints/llm.py`） |
|---|---|---|
| 构造 | `Engine(model_path=..., ...)`（kwargs=ServerArgs） | `LLM(model, **kwargs)`（kwargs=EngineArgs） |
| 生成 | `generate(prompt, sampling_params, stream=...)` → `Dict` | `generate(prompts, sampling_params)` → `list[RequestOutput]` |
| 流式 | 同步流式用生成器，异步用 `async_generate` | 同步引擎不流式；流式走 `AsyncLLM`/`vllm serve` |
| 输出 | 裸 dict（`text`/`meta_info`/`output_ids`） | `RequestOutput` 对象（requests 抽象） |
| 并行 | 内部 `_launch_subprocesses`（spawn） | 内部构造 `LLMEngine`（V1），EngineCore 默认独立进程 |
| 嵌入 | `encode(prompt, ...)` | `encode(prompts, pooling_params, pooling_task=...)`（须显式指定 pooling_task） |
| 权重更新 | 内置 `update_weights_*` 全家桶 + LoRA 热加载 | `start_weight_update`/`update_weights`/`finish_weight_update`（RL 训练链） |
| 会话 | `open_session`/`session_id`（持续提示，不等同对话） | 无内置 session 概念 |

两者都坚持「离线接口 = 直接驱动引擎进程、不经 HTTP」，且都围绕一个 manager/engine 句柄封装批处理；主要差异在输出模型（裸 dict vs 强类型 RequestOutput）与流式形态。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
