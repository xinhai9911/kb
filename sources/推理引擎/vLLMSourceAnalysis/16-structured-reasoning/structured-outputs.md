## Structured Outputs 结构化输出体系

本文基于 vLLM `vllm/v1/structured_output/`、`vllm/v1/worker/gpu/structured_outputs.py` 与 `vllm/config/structured_outputs.py`，说明 grammar/guided decoding 后端契约、`StructuredOutputManager` 如何衔接采样，以及相关错误处理。注：仓库中不存在顶层 `vllm/structured_outputs/` 目录，该模块在 V1 下为单数命名 `v1/structured_output/`；`vllm/parser/` 是前端输出解析（reasoning/tool 文本解析），两者是不同层次。

### 配置与请求参数

`StructuredOutputsConfig`（`vllm/config/structured_outputs.py`）：

| 字段 | 默认 | 说明 |
|---|---|---|
| `backend` | `"auto"` | `Literal["auto","xgrammar","guidance","outlines","lm-format-enforcer"]`；auto 按请求内容与后端能力选择 |
| `disable_any_whitespace` | `False` | JSON 紧凑输出；仅 xgrammar/guidance 支持 |
| `disable_additional_properties` | `False` | 仅 guidance 生效 |
| `reasoning_parser` | `""` | 推理解析器名（`--reasoning-parser`） |
| `reasoning_parser_plugin` | `""` | 外部插件路径 |
| `enable_in_reasoning` | `False` | 是否对思考段也施加语法约束 |

`compute_hash()` 无参与计算图的因素，恒为常量哈希。`model_validator` 校验后端的专属选项组合。

请求侧 `StructuredOutputsParams`（`vllm/sampling_params.py`）：`json`/`regex`/`choice`/`grammar`/`json_object`/`structural_tag` 六类约束**互斥**（多设/全不设抛 `VLLMValidationError`）；私有字段 `_backend`、`_backend_was_auto`（仅校验期设置）。`SamplingParams._validate_structured_outputs` 在请求校验时解析后端：显式 `_backend` 冲突报错；auto 模式按约束类型依次尝试 `validate_xgrammar_grammar` → `validate_guidance_grammar` → `outlines` 兜底，并记录 `_backend_was_auto`。

### 后端接口契约

`vllm/v1/structured_output/backend_types.py`：

- `StructuredOutputOptions`（Enum）：`JSON`/`JSON_OBJECT`/`REGEX`/`GRAMMAR`/`CHOICE`/`STRUCTURAL_TAG`；`StructuredOutputKey = (options, spec)`。
- `StructuredOutputGrammar`（请求级 FSM 抽象）：`accept_tokens(request_id, tokens)->bool`（接受并推进）、`validate_tokens(tokens)`（校验不推进，返回被接受的前缀，供投机解码过滤草稿）、`rollback(num_tokens)`、`fill_bitmask(bitmask, batch_index)`、`is_terminated()`、`reset()`。
- `StructuredOutputBackend`（引擎级抽象，dataclass ABC，含 `vllm_config/tokenizer/vocab_size`）：`compile_grammar(request_type, grammar_spec, stop_token_ids=None)`、`allocate_token_bitmask(max_num_seqs)`、`destroy()`。

`StructuredOutputRequest`（`v1/structured_output/request.py`）：`params` + `_grammar`（`Future | Grammar | Exception`，`is_grammar_ready` 每查一次以 100us 超时轮询 Future）+ `reasoning_ended`/`reasoning_end_token_index`/`reasoning_parser_kwargs`/`reasoner`（请求级缓存）。`structured_output_key` 为 `cached_property`，按优先级 `json → json_object → regex → choice → grammar → structural_tag` 产出键。

### StructuredOutputManager 与采样衔接

`vllm/v1/structured_output/__init__.py` 的 `StructuredOutputManager` 是引擎内核持有者（构造时注入 `Scheduler`）。单后端假设：V1 不支持按请求切换后端，首个请求确定全局 backend。

| 方法 | 行为 |
|---|---|
| `grammar_init(request)` | 首次按 `params._backend` 实例化 `XgrammarBackend`/`GuidanceBackend`/`OutlinesBackend`（懒导入）/`LMFormatEnforcerBackend`；默认**异步**提交 `_create_grammar` 到 `ThreadPoolExecutor`（`external_launcher` 分布式后端因各 TP rank 调度不同步会死锁，改同步），Future 存入请求 |
| `_create_grammar` | 取 `structured_output_key` → `backend.compile_grammar(..., stop_token_ids=all_stop_token_ids)`；失败记日志并按请求隔离（Future 携带异常） |
| `grammar_bitmask(requests, ids, spec_tokens)` | 产出 `np.int32` bitmask（numpy 便于跨进程序列化）；按 `max_num_seqs*(1+投机数)` 分配；投机窗口内若 `reasoner.is_reasoning_end_streaming` 中途越过思考段（用 `simulated_buf = prompt+全部窗口token` 模拟），越过点之后的行才填 bitmask，再 `accept_tokens`/`rollback` 对齐 |
| `should_fill_bitmask(request)` | `enable_in_reasoning` 或 `reasoning_ended` 为真 → 填；否则用 `reasoner.is_reasoning_end(prompt)` 惰性初始化 `reasoning_ended` |
| `should_advance(request, new_token_ids)` | 无结构化输出返回 `False`；思考已结束则推进 grammar；否则用 `new_token_ids` 作 delta 窗口调 `is_reasoning_end_streaming`，命中则置 `reasoning_ended` 并记 `reasoning_end_token_index` |
| `trim_reasoning_for_advance(request, new_token_ids)` | 依据 `reasoning_end_token_index` 丢弃步内思考 token，防止 marker 使 grammar 拒绝（issue #44006） |

采样链路（`v1/core/sched/scheduler.py`）：

1. 请求入队即置 `WAITING_FOR_STRUCTURED_OUTPUT_GRAMMAR`；grammar Future 就绪才转 `WAITING`；编译失败入 `grammar_compile_error_reqs` 使该请求失败。
2. 调度输出 `has_structured_output_requests` → `get_grammar_bitmask` 产 `GrammarOutput(ids, bitmask)`。
3. GPU runner 前向后在 logits 上应用 bitmask（`apply_grammar_bitmask`）：GPU 路径用 `xgr.apply_token_bitmask_inplace`；`StructuredOutputsWorker`（`v1/worker/gpu/structured_outputs.py`）的 Triton kernel 用于 CPU/自适应验证路径，按 `cu_num_logits` 定位每请求行并把掩码位写 `-inf`，等效于采样前剪枝。
4. `update_from_output` 消费新 token：`should_advance` + `trim_reasoning_for_advance` 后 `grammar.accept_tokens`；投机解码草稿经 `grammar.validate_tokens` 过滤非法 token 后回填。

### 后端实现要点

- `XgrammarBackend`（`backend_xgrammar.py`）：`xgr.TokenizerInfo.from_huggingface`（Mistral 系特殊处理 RAW/BYTE_FALLBACK vocab 与 `add_prefix_space`）；`GrammarCompiler(max_threads=8, cache_enabled, cache_limit_bytes=VLLM_XGRAMMAR_CACHE_MB)`；按 `StructuredOutputOptions` 分发 `compile_json_schema`（`any_whitespace`）/`compile_grammar`/`compile_regex`/`compile_structural_tag`。
- `utils.py`：`compile_regex_with_timeout`（ReDoS 防护，超时抛 `ValueError`，`VLLM_REGEX_COMPILATION_TIMEOUT_S` 控制）；`grammar_is_likely_lark`/`convert_lark_to_ebnf` 语法转换；`choice_as_grammar` 把枚举转 EBNF；`OutlinesVocabulary`/`OutlinesDiskCache`（SQLite + serde 二进制，避免 pickle 反序列化风险）。
- `backend_guidance.py`、`backend_outlines.py`、`backend_lm_format_enforcer.py` 提供对应后端与各自 grammar 校验函数。

### 错误处理（faq 相关）

| 场景 | 行为 |
|---|---|
| 多约束同时指定 / 全不指定 | `StructuredOutputsParams.__post_init__` 抛 `VLLMValidationError` |
| `grammar` 为空串 / `json_object=False` / regex 含 NUL | `SamplingParams._validate_structured_outputs` 提前抛 `ValueError`，避免引擎侧崩溃 |
| 请求显式 `_backend` 与解析结果冲突 | 抛错并要求移除 `_backend` |
| 恶意/复杂正则编译超时 | `compile_regex_with_timeout` 抛 `ValueError`（提示嵌套量词类 ReDoS） |
| grammar 编译失败 | 异常随 Future 传递，仅该请求失败（scheduler 经 `grammar_compile_error_reqs` 处理），不拖垮引擎 |
| 投机窗口内非法 token | `grammar_bitmask` 内 `AssertionError`（思考段后草稿被拒属预期，仅此时豁免） |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
