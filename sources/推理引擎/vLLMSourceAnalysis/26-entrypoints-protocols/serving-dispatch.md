## Serving 层转发与错误处理

生成类三个 Serving（Chat/Completion/Responses）继承 `GenerateBaseServing`（`generate/base/serving.py:115`），池化类继承 `PoolingBaseServing`（`pooling/base/serving.py:37`），二者都继承 `BaseServing`（`serve/engine/serving.py:29`）。职责链：模型校验 → 渲染 EngineInput → 构造 params → 调 `engine_client` → 输出组装。

### Serving 类层次与依赖

| 类 | 文件 | 构造依赖 |
|---|---|---|
| `BaseServing` | `serve/engine/serving.py` | `models`(OpenAIServingModels)、`model_config`、`request_logger`；提供 `_check_model`/`create_error_response`/`_base_request_id`/`_maybe_get_adapters` |
| `GenerateBaseServing` | `generate/base/serving.py` | 追加 `engine_client`、`return_tokens_as_token_ids`；提供 `create_streaming_error_response`、`_raise_if_error`、`_get_priority`/`_get_session_id` |
| `OpenAIServingChat` | `chat_completion/serving.py:115` | `online_renderer`、`response_role`、`chat_template`、`tool_parser`/`reasoning_parser`/`enable_auto_tools` 等 |
| `OpenAIServingCompletion` | `completion/serving.py:53` | `online_renderer` + 若干开关 |
| `OpenAIServingResponses` | `responses/serving.py:150` | `use_harmony`(gpt_oss 模型)、`tool_server`、`response_store`/`msg_store`/`background_tasks` |
| `PoolingBaseServing` | `pooling/base/serving.py` | 统一的 `__call__` 流水线：`_init_ctx → _preprocessing → _prepare_generators → _collect_batch → _postprocessing` |

实例由 `openai/api_server.py` 的 `init_app_state` 构造并存 `app.state`；`generate/factories.py`/`pooling/factories.py` 提供按任务分发的工厂。

### 转发主流程（以 Chat 为例）

```
create_chat_completion (chat_completion/serving.py:225)
 └─ _with_kv_transfer_rejection_cleanup(...)   # KV 远端预填充失败时通知连接器释放 pin 块
    └─ _create_chat_completion
       1. self.parser_cls(tokenizer, request.tools, ...)   # 工具/推理 parser 组装
       2. render_chat_request → (conversation, engine_inputs)
       3. request_id = f"chatcmpl-{_base_request_id(raw_request, request.request_id)}"
       4. lora_request = _maybe_get_adapters(request, supports_default_mm_loras=True)
       5. 对每个 engine_input: max_tokens=get_max_tokens(...)
       6. sampling_params = request.to_sampling_params / to_beam_search_params
       7. generator = engine_client.generate(engine_input, sampling_params, id,
                                             lora_request, trace_headers, priority,
                                             data_parallel_rank, session_id,
                                             reasoning_ended, reasoning_parser_kwargs)
       8. stream → chat_completion_stream_generator / chat_completion_full_generator
```

关键细节：

- `data_parallel_rank` 从请求头 `X-data-parallel-rank` 读取（路由注入）；`priority` 从 `X-Vllm-Priority` 头或 `request.priority` 取；`session_id` 取请求字段 → `X-Session-ID` 头 → `vllm_xargs["session_id"]`。
- 多 prompt（completion 批量）生成 `sub_request_id = f"{request_id}_{i}"`，结果用 `merge_async_iterators` 合并后按 index 归位。
- `engine_client.errored` 时**raise** `dead_error`（流式场景必须先发 200 再断流，故用异常而非 ErrorResponse）。
- 非流式完成时把 `final_res.prompt` 回填渲染出的 prompt 文本（引擎不携带）。
- `stream=True` 且 `stream_options.include_usage=False` 时，usage 只在最后一 chunk 附带；`continuous_usage_stats` 控制逐 chunk 累计 usage。

### serving 层的 tool choice 处理（区别于 18 的 parser 本体）

| 环节 | 行为 |
|---|---|
| parser 选择 | `ParserManager.get_parser(tool_parser_name, reasoning_parser_name, enable_auto_tools, model_name, is_harmony)` 在构造时决定用哪套工具/reasoning parser |
| 渲染期 | `ChatParams.tool_choice = request.tool_choice if request.tools else None`——无 tools 时折叠默认，模板不注入工具指令 |
| `exclude_tools_when_tool_choice_none` | 服务端开关：`tool_choice=="none"` 时连 tool 定义也排除，防止 prompt 泄漏函数 schema |
| `enable_auto_tools` | 自动工具选择（服务端 `--enable-auto-tool-choice`），需配合 `--tool-call-parser`（`validate_parsed_serve_args` 强制） |
| Responses 内置工具 | `extract_tool_types(request.tools)` 过滤请求实际启用的工具（browser/code_interpreter/container），仅当 `tool_server` 已注册才执行；工具循环在 `responses_full_generator` 中 `_render_next_turn` 迭代 |
| reasoning 解析 | `parser.is_reasoning_end(prompt_token_ids)` 判断 reasoning 是否结束 → 传入 `engine_client.generate(reasoning_ended=...)` |

### 错误 → HTTP 状态码映射

统一入口 `create_error_response`（`serve/exception_handling/error_response.py:17`），产出 `ErrorResponse(error=ErrorInfo(message, type, param, code))`。异常分派表：

| 异常类型 | err_type | HTTP |
|---|---|---|
| `VLLMValidationError` | `BadRequestError` | 400（param 取 `exc.parameter`） |
| `VLLMUnprocessableEntityError` | `UnprocessableEntityError` | 422 |
| `VLLMNotFoundError` | `NotFoundError` | 404 |
| 其他 `VLLMClientError` | `BadRequestError` | 400 |
| `GenerationError` | `InternalServerError` | 500（`exc.status_code`） |
| 其他 `VLLMServerError` | `InternalServerError` | 500 |
| `ValueError`/`TypeError`/`OverflowError`（未迁移兜底） | `BadRequestError` | 400 |
| `NotImplementedError` | `NotImplementedError` | 501 |
| jinja2 `TemplateError` | `BadRequestError` | 400 |
| 其余未知异常 | `InternalServerError` | 500 |

判据：`VLLMClientError` 系 4xx，`VLLMServerError` 系 5xx。

FastAPI 全局 handler 注册于 `serve/exception_handling/register.py`：

- `vllm_error_handler`：`EngineDeadError`/`EngineGenerateError` → 调 `terminate_if_errored` 检查是否关停服务后返回错误；`GenerationError` → 500；其余走通用 `exception_handler`。
- `validation_exception_handler`（`RequestValidationError`）：从 pydantic 错误 `ctx["error"]` 中找回 `VLLMValidationError.parameter`；否则用 `clean_loc_for_param` 清洗内部 loc 标记（pydantic-core 的 `function-wrap`/`union`/`tagged-union` 等内部 schema-kind 一律丢弃，避免参数路径暴露内部实现）；**消息用 `exc.errors()` 重新拼接而非 `str(exc)`**（后者泄漏服务端文件路径）。返回 400。
- 路由层：`chat_completion/api_router.py` 的 `@router.post("/v1/chat/completions")` 声明 `responses={400/404/500/501: ErrorResponse}`；非流式结果若是 `ErrorResponse` 则 `JSONResponse(status_code=generator.error.code)`，流式返回 `text/event-stream`。`with_cancellation` 装饰器监听 http.disconnect 取消 handler，`load_aware_call` 做服务端负载计数。

### Chat 模板解析（chat_utils.py）

- `load_chat_template(chat_template)`：支持文件路径/内联 Jinja，缺省取 tokenizer 自带模板，无模板时抛 `ChatTemplateResolutionError`（`ValueError` 子类）。
- 模板渲染参数经 `ChatParams.with_defaults(default_chat_template_kwargs)` 合并服务端默认 kwargs。
- `get_tool_call_id_type(model_config)`：Kimi 系列（`kimi_k2` 等 model_type）工具调用 ID 生成 `functions.{func}:{idx}`，其余 `chatcmpl-tool-{uuid}`；`ToolCall.id` 默认工厂即 `make_tool_call_id()`。

### 服务参数（FrontendArgs）与 EngineArgs 对照

`openai/cli_args.py:366 make_arg_parser`：`FrontendArgs.add_cli_args(parser)` + `AsyncEngineArgs.add_cli_args(parser)`。服务端参数（host/port/api_key/ssl/middleware/chat_template/tool_call_parser 等）在 `FrontendArgs`，引擎参数由 `AsyncEngineArgs` 提供，最终 `AsyncEngineArgs.from_cli_args(args)` → `create_engine_config()`。`validate_parsed_serve_args` 启动前校验组合约束（如 `--enable-auto-tool-choice` 必须配 `--tool-call-parser`）。endpoint 插件经 `_attach_endpoint_plugins` 从 `vllm.plugins.load_endpoint_plugins(supported_tasks)` 加载，路由最后挂载以允许覆盖核心路由。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
