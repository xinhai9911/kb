## 约束解码（Grammar-Guided Decoding）后端与采样衔接

本文基于 `sglang/srt/constrained/`（9 文件 + `torch_ops/`），说明 grammar 抽象契约、xgrammar/outlines/llguidance 三后端如何编译并约束采样（bitmask/logits mask）、`GrammarManager` 缓存与调度衔接，以及思考段（reasoner）包装。

### 模块结构

| 文件 | 职责 |
|---|---|
| `base_grammar_backend.py` | 抽象契约、`GrammarMask`/`GrammarRow`/`GrammarStats`、`InvalidGrammarObject`、注册表与工厂 |
| `grammar_manager.py` | `GrammarManager`：异步编译队列、缓存、PP/DP/TP 同步、超时失败处理 |
| `xgrammar_backend.py` | xgrammar 后端（含 token filter 与 structural tag） |
| `outlines_backend.py` / `outlines_jump_forward.py` | outlines 后端（JSON→regex→FSM）/ 压缩 FSM jump-forward 表 |
| `llguidance_backend.py` | llguidance 后端，Rust 原生 bitmask kernel |
| `reasoner_grammar_backend.py` | `ReasonerGrammarBackend/Object`：思考段结束前不施加约束 |
| `utils.py` / `torch_ops/` | `is_legacy_structural_tag` 判别；`set_token_filter_torch` 非 CUDA token filter |

### BaseGrammarObject 契约（base_grammar_backend.py）

| 方法 | 语义 |
|---|---|
| `accept_token(token)` | 推进 FSM（xgrammar 拒绝时报错；llguidance 遇 EOS 置 `finished`） |
| `rollback(k)` / `is_terminated()` | 回退（投机/重采样）/ 终止判定 |
| `allocate_vocab_mask` | 分配 mask 张量（xgrammar 用 `get_bitmask_shape`+`bitmask_dtype` 填 `-1` 并 pin_memory；outlines 用 `torch.bool` 全 0） |
| `fill_vocab_mask(mask, idx)` | 将下一步允许 token 写入第 idx 行；`fill_vocab_mask_batched` 批量填（llguidance 覆写为原生 kernel） |
| `move_vocab_mask` / `apply_vocab_mask` | 搬运 / 在 logits 就地应用（CUDA 走 `sgl_kernel.apply_token_bitmask_inplace_cuda`，其余 Triton `bitmask_ops`，npu/cpu 另有分支） |
| `try_jump_forward` 系列 | jump-forward 加速：确定性中间串旁路采样 |
| `copy()` | 每请求独立 grammar（缓存命中时复制；xgrammar 重建 `GrammarMatcher`） |

`GrammarMask`（149）携带「任一 grammar 句柄 + vocab_mask」，`apply(logits)` 委托后端应用；`GrammarRow`（51）为 `(row, grammar)` 批量填充条目。编译失败统一用 `InvalidGrammarObject(error_message)` 表达，不抛异常到请求路径。

### BaseGrammarBackend 缓存与分派

`BaseGrammarBackend.__init__`：`ThreadPoolExecutor` + `cache: Dict[(key_type, key_string), BaseGrammarObject]`。

- `get_cached_or_future_value(key, require_reasoning)`（284）：命中→`value.copy()` + `maybe_init_reasoning`；未命中→`executor.submit(_init_value_dispatch)` 返回 `Future`（`cache_hit=False` 者入 grammar 队列）。
- `_init_value_dispatch`（259）：先 NUL 检查（`_grammar_key_contains_nul`，`\x00` 会让 xgrammar regex 转换器段错误，见 mlc-ai/xgrammar#850），再按 `key_type` 分派 `dispatch_json/regex/ebnf/structural_tag`，记录 `GrammarStats.compilation_time`。
- `create_grammar_backend`（351）：优先级 = 注册表自定义后端（`register_grammar_backend`）> `--grammar-backend` 四种默认（`server_args.py:245`：`xgrammar/outlines/llguidance/none`）。xgrammar 初始化抛 `TokenizerNotSupportedError` 时回退 `grammar_backend="none"`（`--enable-strict-thinking` 下直接报错）。配置 `reasoning_parser` 且模型有 `think_end_ids` 时再包一层 `ReasonerGrammarBackend`。

### 三后端编译对照

| 维度 | xgrammar | outlines | llguidance |
|---|---|---|---|
| JSON | `compile_json_schema(schema, any_whitespace)`；`$$ANY$$` 用 builtin | `build_regex_from_schema` + `RegexGuide.from_regex` | `grammar_from_json_schema(whitespace_flexible/pattern)` |
| Regex / EBNF | `compile_regex` / `compile_grammar` | `RegexGuide.from_regex` / 不支持 | `grammar_from("regex"/"ebnf")` |
| Structural tag | legacy：`StructuralTag.from_legacy_structural_tag`；new：直接编译 | 不支持 | `StructTag.to_grammar`（trigger 按 `begin.startswith(trigger)` 匹配，支持每工具独立 trigger） |
| mask 类型/填充 | 打包 int bitmask（`bitmask_dtype` 初值 `-1`）/ `matcher.fill_next_token_bitmask` | `torch.bool`，`scatter_` 置 0 / `guide.get_next_instruction` | llguidance 打包 int32 / `fill_next_token_bitmask(_par)` 原生 kernel |
| Token filter | 支持（triton/torch） | 否 | 否 |
| Jump forward | `find_jump_forward_string()` | `OutlinesJumpForwardMap`（压缩 FSM） | `compute_ff_tokens()` |

outlines 的 jump-forward 未显式启用（`_compile_regex` 中 `jump_forward_map=None`），`outlines_jump_forward.py` 保留完整压缩 FSM 表构造（`init_state_to_jump_forward`，磁盘缓存由 `SGLANG_DISABLE_OUTLINES_DISK_CACHE` 控制，默认关闭）。

### GrammarManager：异步编译与多进程同步（grammar_manager.py）

`process_req_with_grammar`（131）：四类约束互斥（`sampling_params.py:71-74` 的 `json_schema/regex/ebnf/structural_tag`，`normalize()` 校验唯一）；构造 key → 取缓存/Future → `req.grammar = value`，未命中入 `grammar_queue`（调度器据此暂不入队，`scheduler.py:2706`）。

`get_ready_grammar_requests`（184）：PP0 轮询（`SGLANG_GRAMMAR_POLL_INTERVAL`，默认 0.005s）Future `done()`；就绪/超时集合经 `all_gather_object` 同步（就绪取交集、失败取并集，跨 DP/TP），再经 `_pp_sync_ready_failed` 逐级 PP 转发（`P2PTag.GRAMMAR_PP_SYNC`）。就绪后 `Future.result()` + `set_cache` 写回；编译异常/超时 → `InvalidGrammarObject` + `set_finish_with_abort`。`abort_requests`（109）对未完成 Future `cancel()`；`custom_params.thinking_budget` 可改写 `ReasonerGrammarObject.max_think_tokens`。

### 采样衔接

- `sampling_batch_info.py:239 update_regex_vocab_mask`：`allocate_vocab_mask` → 收集未终止请求的 `GrammarRow` → `fill_vocab_mask_batched` → `move_vocab_mask` → 存 `self.grammar_mask`；采样时 `grammar_mask.apply(logits)`（296）把非法 token 的 logits 置 `-inf`。
- 输出侧 `batch_result_processor.py:574 _apply_prefill_grammar`：对新 token `req.grammar.accept_token(next_token_id)`（非法抛 `ValueError` → `FINISH_ABORT`）并同步 `grammar.finished`；decode 后同理（`decode_schedule_batch_mixin.py:128`、`disaggregation/prefill.py:763`）。
- 投机解码：`spec_utils.py` 对草稿 token 树 DFS（`traverse_tree` 477-506），逐节点 `accept_token`/`fill_vocab_mask`/`rollback`，产出覆盖全部草稿位的 bitmask（`generate_token_bitmask` 509）；llguidance 另有原生草稿链 kernel `fill_next_token_bitmask_par_with_draft_tokens`。

### ReasonerGrammarObject：思考段推迟约束

`reasoner_grammar_backend.py`：`think_end_ids` 由 `reasoning_parser.detector.think_end_token` 编码，用 `TokenSequenceMatcher` 匹配。`fill_vocab_mask` 中 thinking 阶段不施加 grammar 约束，仅可选 token filter（`--enable-strict-thinking`：排除 `think_excluded_token_ids`，或到 `max_think_tokens` 后强制输出 think_end）；generation 阶段才转发内层 grammar。

### 与 vLLM structured_outputs 对照

| 维度 | vLLM `v1/structured_output/` | SGLang `srt/constrained/` |
|---|---|---|
| 组织 | `StructuredOutputManager`（引擎级单例，单后端全局） | `GrammarManager`（per-scheduler）+ `BaseGrammarBackend` |
| 请求 FSM | `StructuredOutputGrammar` | `BaseGrammarObject` |
| 缓存 | `StructuredOutputRequest._grammar` Future + key | `BaseGrammarBackend.cache` + `get_cached_or_future_value`，命中 `copy()` |
| 后端 | xgrammar/guidance/outlines/lm-format-enforcer | xgrammar/outlines/llguidance（+ 可注册自定义） |
| bitmask 应用 | GPU `xgr.apply_token_bitmask_inplace`；Triton kernel | `sgl_kernel.apply_token_bitmask_inplace_cuda` / Triton `bitmask_ops` / npu/cpu 分支 |
| 思考段 | `request.reasoner` + `enable_in_reasoning` | `ReasonerGrammarBackend` 包装 + token filter |
| 特有能力 | — | structural tag（legacy/new）、jump-forward、PP 同步、`copy()` 独立 FSM |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
