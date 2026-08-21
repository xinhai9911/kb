## HTTP 服务与端点清单（SGLang Runtime）_part2：兼容协议与请求模型

续 [_part1](http-server_part1.md)。本部分覆盖权重更新/HiCache 等管理端点、OpenAI 兼容端点、其他协议族，以及 `/generate` 核心逻辑与请求模型。

### 端点总览（续）

| 族 | 方法 | 路径 | 用途 |
|---|---|---|---|
| 权重更新 | POST | `/update_weights_from_disk` `/update_weights_from_tensor` `/update_weights_from_distributed` `/update_weights_from_ipc` `/update_weight_version` | 热更新权重（磁盘/张量/分布式/IPC）与版本号，:1235-1464 |
| 权重更新 | POST | `/init_weights_update_group` `/destroy_weights_update_group` | RL 训练权重更新组生命周期，:1339/:1355 |
| 权重更新 | POST | `/init_weights_send_group_for_remote_instance` `/send_weights_to_remote_instance` | 跨实例权重传输，:1264/:1283 |
| 权重更新 | GET/POST | `/get_weights_by_name` | 按名取权重（截断），:1466 |
| HiCache | GET/POST | `/hicache/storage-backend`（PUT/DELETE/GET） | 挂载/卸载/查询外部 KV 存储后端，:1078-1155 |
| HiCache | GET/POST | `/clear_hicache_storage_backend` | 旧名；`/hicache/storage-backend/clear` 新路径 |
| 语料 | POST/GET | `/add_external_corpus` `/remove_external_corpus` `/list_external_corpora` | 外部检索语料管理，:984-1040 |
| Dumper | POST | `/dumper/{method}` | 张量 dump 控制（`DUMPER_SERVER_PORT=reuse` 时注册），:870 |
| OpenAI | POST | `/v1/completions` `/v1/chat/completions` | 文本补全 / 对话补全（流式 SSE），:1714/:1722 |
| OpenAI | POST | `/v1/embeddings` `/v1/classify` | 嵌入 / 分类，:1732/:1744 |
| OpenAI | POST | `/v1/tokenize`（`/tokenize` 别名）`/v1/detokenize`（`/detokenize`） | 分词 / 反分词，:1756/:1774 |
| OpenAI | POST | `/v1/score` `/v1/rerank` | 打分（logprob/分类头）/ 重排，:1900/:1943 |
| OpenAI | POST | `/v1/responses` `/v1/responses/{id}` `/v1/responses/{id}/cancel` | Responses API（含后台任务），:1908-1940 |
| OpenAI | GET | `/v1/models` `/v1/models/{model:path}` | 模型列表（含 LoRA 适配器）/ 单模型，:1843/:1875 |
| OpenAI | POST | `/v1/audio/transcriptions` | 语音转写（multipart form），:1792 |
| OpenAI | WS | `/v1/realtime` | Realtime 转写子集 WebSocket，:1832 |
| Ollama | POST | `/api/chat` `/api/generate` `/api/tags` `/api/show` | Ollama 兼容（`SGLANG_OLLAMA_*_ROUTE` 可改路径），:1973-1996 |
| Anthropic | POST | `/v1/messages` `/v1/messages/count_tokens` | Anthropic Messages 兼容，:2002/:2012 |
| SageMaker | GET/POST | `/ping` `/invocations` | SageMaker 容器协议，:2023/:2029 |
| Vertex | POST | `/vertex_generate` | Vertex AI 预测协议（`AIP_PREDICT_ROUTE` 可改），:2040 |
| 根 | GET/HEAD | `/`（或 `SGLANG_OLLAMA_ROOT_ROUTE`） | 探活文案，:1955-1970 |

合计 80+ 路径（含别名与废弃端点）。所有 `/v1/*` 的 JSON 端点都带 `Depends(validate_json_request)`（:635，强制 `Content-Type: application/json`）。

### /generate：v0 风格核心端点

`POST/PUT /generate`（`http_server.py:889`）把请求体 JSON 直接绑定为 `GenerateReqInput` dataclass：

```python
@app.api_route("/generate", methods=["POST", "PUT"], response_class=SGLangORJSONResponse)
async def generate_request(obj: GenerateReqInput, request: Request):
    if envs.SGLANG_ENABLE_REQUEST_HEADER_OVERRIDES.get():
        apply_header_overrides(obj, request.headers)      # 请求头覆盖 sampling 等字段
    if obj.stream:
        async def stream_results() -> AsyncIterator[bytes]:
            async for out in _global_state.tokenizer_manager.generate_request(obj, request):
                yield b"data: " + dumps_json(out) + b"\n\n"   # SSE 帧
            yield b"data: [DONE]\n\n"
        return StreamingResponse(stream_results(), media_type="text/event-stream",
                                 background=_global_state.tokenizer_manager.create_abort_task(obj))
    else:
        ret = await _global_state.tokenizer_manager.generate_request(obj, request).__anext__()
        return orjson_response(ret)
```

- 非流式只取异步生成器的第一帧即返回；流式按 SSE 逐帧输出，`create_abort_task` 作为 background 在客户端断开时调 `abort_request`。
- 请求进入 `TokenizerManager.generate_request`（`managers/tokenizer_manager.py:765`，细节见 [02-managers](../02-managers/tokenizer-manager.md)）：`normalize_batch_and_arguments` → tokenize → PUSH 给 Scheduler → 等 Detokenizer 回包。

### 请求模型（`sglang/srt/managers/io_struct.py`）

| 模型 | 类型 | 说明 |
|---|---|---|
| `GenerateReqInput` | `@dataclass` :160 | `/generate` 请求体：`text`/`input_ids`/`input_embeds` 三选一；`sampling_params`；`image/video/audio_data` 多模态；`return_logprob`/`top_logprobs_num`；`stream`；`lora_path`/`custom_logit_processor`；disagg 三件套 `bootstrap_host/port/room`；DP 路由 `routed_dp_rank`；`session_id`/`session_params`（互斥）；`priority`、`cache_salt`、`return_hidden_states` 等 |
| `EmbeddingReqInput` | `@dataclass` :1071 | `/encode` 请求体：`text`/`input_ids`、`image/video/audio_data`、`embed_override_token_id`/`embed_overrides`、`dimensions`（Matryoshka）、`return_pooled_hidden_states`、`is_cross_encoder_request` |
| `AbortReq` | `msgspec.Struct` :2005 | `/abort_request` 的 `rid` |
| `UpdateWeightFromDiskReqInput` 等 | `msgspec.Struct` :1743 起 | 各权重更新/管理端点的请求体（均为 tag 化 Struct） |

注意：`GenerateReqInput` 与 `EmbeddingReqInput` 是 pydantic 兼容的 `@dataclass`（HTTP 绑定用）；进程间传输时在 TokenizerManager 内转换为 tag 化的 `TokenizedGenerateReqInput`/`BatchTokenizedGenerateReqInput`（`msgspec.Struct`，:941/:1055），走 ZMQ msgpack。

OpenAI 兼容请求模型在 `entrypoints/openai/protocol.py`（全部 `BaseModel`）：`CompletionRequest` :328（含 `sglang` 扩展字段 `sgl_ext`）、`ChatCompletionRequest` :823、`EmbeddingRequest` :1284、`ClassifyRequest` :1315、`ScoringRequest` :1350、`V1RerankReqInput` :1386、`TokenizeRequest`/`DetokenizeRequest` :1443/:1488、`ResponsesRequest` :1576、`TranscriptionRequest` :2052。

### OpenAI serving 中间层与鉴权

- `lifespan` 把 `OpenAIServingCompletion/Chat/Embedding/Classify/Score/Rerank/Tokenize/Detokenize/Transcription/Responses` 挂到 `app.state.*`；每个 handler 内部都调 `TokenizerManager.generate_request` 并把输出转成 OpenAI 协议响应（chat 走 `TemplateManager` 渲染）。
- 鉴权中间件 `add_api_key_middleware`（`srt/utils/auth.py`）：`--api-key` 对所有端点生效，`--admin-api-key` 仅管理端点；`@auth_level(AuthLevel.ADMIN_OPTIONAL)` 标记管理端点（`/set_internal_state`、`/dumper/{method}` 等）。
- `apply_header_overrides`（`request_headers.py`）在 `SGLANG_ENABLE_REQUEST_HEADER_OVERRIDES=1` 时允许请求头改写 sampling 参数。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
