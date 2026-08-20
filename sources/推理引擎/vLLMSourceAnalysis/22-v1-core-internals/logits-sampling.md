## v1 内核采样链路：LogitsProcessor 契约与 EngineCore.step 衔接

本文聚焦 vLLM V1 内核算法的「logits 处理 → 采样」组件契约及其在 `EngineCore.step` 调度→执行→采样→输出链路中的位置。组件散落于 `vllm/v1/sample/`（采样侧）与 `vllm/v1/core/sched/`（grammar bitmask 产出），与 05 模块（采样管线算法细节）、16 模块（结构化输出后端）互补，本文侧重**组件接口契约**与**调用时序**。

### 文件布局（v1/sample/）

| 文件 | 内容 |
|---|---|
| `logits_processor/interface.py` | `LogitsProcessor` 抽象基类 + `BatchUpdate`/`MoveDirectionality` 类型 |
| `logits_processor/builtin.py` | 内置处理器：`MinTokens`/`LogitBias`/`MinP` + `process_dict_updates` |
| `logits_processor/state.py` | `BatchUpdateBuilder`（批状态变化记账）+ `LogitsProcessors`（按 argmax 不变性分组） |
| `logits_processor/__init__.py` | 工厂 `build_logitsprocs` + 插件/FQCN 加载 + `AdapterLogitsProcessor` |
| `sampler.py` | `Sampler`（nn.Module），被 `gpu_model_runner` 调用 |
| `metadata.py` | `SamplingMetadata` 逐请求采样参数张量集 |
| `rejection_sampler.py`、`ops/`、`thinking_budget_state.py` | 投机解码拒绝采样、bad_words/penalties/topk_topp 内核、思考预算状态 |

### LogitsProcessor 抽象契约（interface.py）

```python
class LogitsProcessor(ABC):
    def validate_params(cls, sampling_params): ...   # 抛 VLLMValidationError → 在线 HTTP 400
    def __init__(self, vllm_config, device, is_pin_memory): ...
    def apply(self, logits: torch.Tensor) -> torch.Tensor: ...   # 可原地修改
    def is_argmax_invariant(self) -> bool: ...   # True 则不影响贪心采样
    def update_state(self, batch_update: BatchUpdate | None): ...  # 每步 forward 前调用
```

- 构造签名三参数固定：`(vllm_config, device, is_pin_memory)`，自定义处理器也须遵循。
- `is_argmax_invariant()` 是**性能关键**契约：invariant 处理器只在随机采样路径应用（温度缩放后），non-invariant 处理器（可改变贪心 argmax 结果）必须在采样前无条件应用。

### 批状态同步：BatchUpdate / BatchUpdateBuilder

持久批中请求增删/搬移通过 `BatchUpdate`（frozen dataclass）下发：

| 字段 | 类型 | 语义 |
|---|---|---|
| `batch_size` | int | 当前批请求数 |
| `removed` | Sequence[int] | 被移除的请求下标 |
| `added` | Sequence[tuple[int, SamplingParams, list[int]\|None, list[int]]] | `(index, params, prompt_tok_ids, output_tok_ids)` |
| `moved` | Sequence[tuple[int, int, MoveDirectionality]] | `(i1, i2, UNIDIRECTIONAL/SWAP)`，请求在批内搬移 |

- `added` 中的 `output_tok_ids` 是请求输出 token 列表的**引用**，处理器始终看到最新已生成 token（min_tokens 判定依赖它）。
- 处理顺序固定 `removed → added → moved`；同一 index 可被后续 added/moved 覆盖。
- `BatchUpdateBuilder` 在一步内聚合变化：`removed_append` 必须在首次读取 `removed` 之前调用（此后禁止，防批索引错乱）；`reset()`/`get_and_reset()` 消费并清空状态，无变化返回 `None`（处理器可跳过张量重建）。
- `process_dict_updates` 是稀疏处理器的通用记账助手：返回 `needs_update` 标志，仅在变化时才重建设备张量（`LogitBias` 的 bias 索引、`MinTokens` 的 stop-token 索引均依赖该惰性重建）。

### 内置处理器与工厂

| 处理器 | is_argmax_invariant | 行为 |
|---|---|---|
| `MinTokensLogitsProcessor` | False | `len(output_tok_ids) < min_tokens` 时把 `all_stop_token_ids` 置 `-inf`；达到后自动移除 |
| `LogitBiasLogitsProcessor` | False | `logits[row, token] += bias`，用 `(req_idx, tok_idx)` 双 int32 索引切片累加 |
| `MinPLogitsProcessor` | True | `softmax` 后与 `max_prob * min_p` 比较，低于阈值 `masked_fill_(-inf)` |

- 工厂 `build_logitsprocs`：`BUILTIN_LOGITS_PROCESSORS = [MinTokens, LogitBias, MinP]`，其后接插件与 FQCN 自定义处理器。
- 插件入口点组 `vllm.logits_processors`；FQCN 语法 `<module>:<qualname>`。
- 特例：pooling 模型拒绝自定义处理器；投机解码启用时只保留 MinTokens 并告警 min_p/logit_bias 不生效。
- `AdapterLogitsProcessor`：把 v0 风格逐请求处理器包装为 `partial[torch.Tensor]`（参数按签名 2 参 `(output_ids)` 或 3 参 `(prompt_ids, output_ids)` 注入），`apply` 时按 `req_info` 逐行修改 logits。
- `LogitsProcessors` 构造时按 `is_argmax_invariant()` 静态分组为 `argmax_invariant` / `non_argmax_invariant` 两个列表，采样器按路径分别取用。

### EngineCore.step 链路中的采样调用点

`vllm/v1/engine/core.py` 的 `step()`（非批队列路径）与 `step_with_batch_queue()`（`max_concurrent_batches>1`）：

```
1. scheduler.schedule(throttle_prefills)              # 调度决策
2. model_executor.execute_model(scheduler_output, non_block=True)   # 前向（Future）
3. grammar_output = scheduler.get_grammar_bitmask(scheduler_output) # 结构化输出 bitmask
4. model_output = future.result()
5. 若 model_output is None → model_executor.sample_tokens(grammar_output)  # 采样后置
6. scheduler.update_from_output(scheduler_output, model_output)  # 消费 token、判停、产 EngineCoreOutputs
```

| 关键分支 | 行为 |
|---|---|
| `is_pooling_model` | 不采样，直接返回 exec future |
| `scheduler_output.pending_structured_output_tokens` 为真 | 本步**延迟采样**（`deferred_scheduler_output`），待上一步输出 token 到位算出 bitmask 后再 `sample_tokens`（见下） |
| 采样 `model_output is None` | `execute_model` 失败时重抛 exec future 异常 |

`_process_engine_step`（busy loop 内）调用 `step_fn()`，把 `EngineCoreOutputs` 逐 client 推入 `output_queue`，随后 `post_step(model_executed)`（异步调度时取草稿 token 写回 scheduler）。

### 结构化输出 bitmask 衔接（参考 16 模块）

1. `scheduler.get_grammar_bitmask`：收集本步已调度且 `use_structured_output`（且非 prefill chunk）的请求，调 `StructuredOutputManager.grammar_bitmask` 产出 `GrammarOutput(structured_output_request_ids, grammar_bitmask)`（`np.int32`，numpy 便于跨进程）。
2. 投递到 worker：`gpu_model_runner.sample_tokens(grammar_output)` 中，**前向 logits 上先应用 bitmask 再进 Sampler**：
   - `structured_output/utils.py::apply_grammar_bitmask`：把 compact 的 bitmask 按 `input_batch.req_ids` 重排回整批（spec tokens 会偏移 logit 行号），GPU 用 `xgr.apply_token_bitmask_inplace`，CPU 走 float32 拷贝回写。
   - 规格：bitmask 覆盖 `1 + len(spec_tokens)` 行（投机窗口每位置一行），未覆盖行填 `-1`（全允许）。
3. 投机解码 + 结构化输出：`pending_structured_output_tokens` 延迟采样路径中，`check_for_draft_tokens` 时先 `take_draft_token_ids` 并 `update_draft_token_ids_in_output` 过滤非法草稿（pad `-1` 跳过），再算 bitmask。
4. `update_from_output` 消费新 token 后由 `StructuredOutputManager.should_advance` → `grammar.accept_tokens` 推进 FSM（详见 16 模块）。

### Sampler 与批元数据装配

- `SamplingMetadata`（`v1/sample/metadata.py`）由 `gpu_input_batch.py` 的 `InputBatch` 构建并持有（`input_batch.sampling_metadata`）；`Sampler.forward` 的输入为 logits + metadata。
- `gpu_model_runner._sample` 选择路径：无 `spec_decode_metadata` 直接 `self.sampler(logits, sampling_metadata)`；否则走 `rejection_sampler`（投机解码）。采样前 `input_batch.update_async_output_token_ids()` 回填上一步新 token（async scheduling）。
- `Sampler` 内部顺序（详见 05 模块）：allowed mask → bad words → **non_argmax_invariant 处理器** → 惩罚 → 温度 → **argmax_invariant 处理器**（min_p）→ top_k/top_p → 采样。`MinTokens.apply_with_spec_decode` 为投机专用变体：按 `num_draft_tokens` 累计行偏移，只 mask 未满足 min_tokens 的前 `remaining` 个草稿位置。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
