## TokenizerManager：主进程前端（请求接收与分派）

本文基于 `sglang/srt/managers/` 源码，说明 TokenizerManager 如何接收 HTTP 请求、维护每个请求的状态、批处理 tokenize 并分派给 Scheduler。进程级拓扑（主进程 = HTTP server + TokenizerManager、多 tokenizer worker 形态）已在 [00-overview](../00-overview/architecture_part1.md) 交代，此处聚焦其内部行为。

### 组件与职责

| 类 | 文件:行 | 角色 |
|---|---|---|
| `TokenizerManager` | `managers/tokenizer_manager.py:386` | 主进程前端本体：tokenize、`_dispatch_to_scheduler` 下发、`handle_loop` 收 Detokenizer 回包、组装响应 |
| `TokenizerWorker` | `managers/multi_tokenizer_mixin.py:647` | 多 HTTP worker 模式下 `TokenizerManager` 的子类，独立进程、仅单线程 tokenize |
| `MultiTokenizerRouter` | `managers/multi_tokenizer_mixin.py:429` | 多 tokenizer 模式的中转：worker→scheduler 下行、detokenizer→worker 上行、pause/continue 广播 |
| `AsyncDynamicbatchTokenizer` | `managers/async_dynamic_batch_tokenizer.py:17` | 可选动态批 tokenizer：单线程 executor + asyncio 队列按 `max_batch_size`/超时攒批 |
| `ReqState` | `managers/tokenizer_manager.py:215` | 单请求在 Tokenizer 侧的状态容器 |

### 请求进入：generate_request

`POST /generate` → `TokenizerManager.generate_request`（`tokenizer_manager.py:765`），单/批量统一走如下流程：

```python
async def generate_request(self, obj, request=None):
    obj.normalize_batch_and_arguments()      # 补全 rid、摊平文本/input_ids 为 batch
    self._init_req_state(obj, request)       # rid_to_state[rid] = ReqState(...)
    async with self.is_pause_cond:
        await self.is_pause_cond.wait_for(lambda: not self.is_pause)  # 权重更新暂停门
    if obj.is_single:
        tokenized_obj = await self._tokenize_one_request(obj)
        self._send_one_request(tokenized_obj)         # PUSH 单条到 scheduler
        async for response in self._wait_one_response(obj, request):
            yield response                            # 异步等待回包
    else:
        async for response in self._handle_batch_request(obj, request):
            yield response
```

- `normalize_batch_and_arguments()` 为未指定 rid 的请求生成 id（批量时以 `rid` 为前缀扩展为逐项 id），并统一 `text`/`input_ids`/`input_embeds` 三选一的输入形态。
- `_init_req_state`（:3374）为每个 rid 创建 `ReqState` 并登记进 `self.rid_to_state`（`Dict[str, ReqState]`，:581）；重复 rid 直接抛 `ValueError`。任何 dispatch 前异常都会经 `_discard_pending_req_states`（:3419）清掉未完成状态，避免泄漏。
- `is_pause` 门：权重更新（`model_update_lock` writer 持有）期间暂停新请求进入。

### ReqState：对话/流式状态保持

| 字段 | 说明 |
|---|---|
| `out_list` / `event` / `finished` | 待消费输出块队列 + `asyncio.Event` 唤醒 + 结束标志；`_wait_one_response` 循环 `event.wait()` 后原子取空 `out_list` |
| `output_ids` / 各类 `*_logprobs_*` 列表 | 增量累积输出 token 与 logprob 中间结果（:256 起） |
| `last_output_offset` / `text_chunks` | 增量流式：`text` 懒拼接，`append_text`/`get_text` 按块累积以规避 O(n²) 字符串重建 |
| `time_stats` | `APIServerReqTimeStats` 记录 created/tokenize/dispatch/response 各阶段时间戳 |
| `prompt_token_ids` | `return_prompt_token_ids=True` 时回填 tokenize 结果 |

### 批处理与动态批 tokenizer

批量路径 `_handle_batch_request`（:1841）：

| 场景 | 行为 |
|---|---|
| `parallel_sample_num == 1` 且 `_should_use_batch_tokenization`（:1581，要求无 input_ids/input_embeds/mm、开启 `--enable-tokenizer-batch-encode`） | `_batch_tokenize_and_process`（:1507）一次性 `_tokenize_texts` 全部文本 → `_send_batch_request`（:1619）组装 `BatchTokenizedGenerateReqInput(batch=[...])` 单条 PUSH 下发 |
| `parallel_sample_num == 1` 其余 | 逐条 `_tokenize_one_request` → `_send_one_request` |
| `parallel_sample_num > 1` | 先发 `max_new_tokens=0` 的 prefill 探测请求缓存公共前缀，再为每个样本 `regenerate_rid()` 展开并逐条下发（:1890-1936）；`batch_size > 128` 时告警提示性能不佳 |

`--enable-dynamic-batch-tokenizer` 时构造 `AsyncDynamicbatchTokenizer`（`tokenizer_manager.py:522`）：`max_batch_size`（默认 32）、`batch_wait_timeout_s`（默认 0.002s）两个参数；asyncio 队列攒批，队空立即处理，否则等待攒到 `max_batch_size` 或超时；批内 kwargs 全一致时走单次 `batch_encode`，否则逐条回退。

### 结果回环：handle_loop → _wait_one_response

```python
async def handle_loop(self):                  # :2199，auto_create_handle_loop(:2174) 首次请求时懒创建
    while True:
        recv_obj = await async_sock_recv(self.recv_from_detokenizer)   # PULL detokenizer_ipc
        if isinstance(recv_obj, (BatchStrOutput, BatchEmbeddingOutput, BatchTokenIDOutput)):
            await self._handle_batch_output(recv_obj)   # 数据面
        else:
            self._result_dispatcher(recv_obj)           # 控制面按类型分派
```

- `_handle_batch_output`（:2214）对每个 rid 查 `rid_to_state`，构造 `meta_info`（`id`/`finish_reason`/`prompt_tokens`/`weight_version`/`num_retractions`，:2241-2247），填 logprob/采样 mask 后把输出 dict 追加进 `state.out_list` 并 `event.set()`；`batch_notify_size` 控制一次批量唤醒的请求数上限（:2228/:2490）。
- `_wait_one_response`（:1733）阻塞在 `state.event.wait()`（超时 `_REQUEST_STATE_WAIT_TIMEOUT`，断开连接则 `abort_request`）；流式按块 yield，增量流式时 `_coalesce_streaming_chunks`（:1652）合并积压 chunk；非流式取 `out_list[-1]` 末块；结束前记录 `response_sent_to_client_ts` 并写日志/指标。

### 中止与暂停

- `abort_request`（:1991）向 scheduler PUSH `AbortReq(rid, abort_all)`；HTTP 侧 `create_abort_task`（:2160）在客户端断开 2 秒后自动触发。
- Scheduler 回 `AbortReq` 回执时 `_handle_abort_req`（:3166）：置 `state.finished`、按 `finish_reason` 组装响应并删除 `rid_to_state` 条目（与正常 finish 存在竞态，用 `.get()` 容忍已删除）。
- `pause_generation`/`continue_generation`（:2010/:2025）置 `is_pause` 并通过 `is_pause_cond.notify_all()` 唤醒等待中的请求；多 tokenizer 模式下经 router 广播 `PauseContinueBroadcastReq`。

### 多 tokenizer worker 模式

`TokenizerWorker` 把 `send_to_scheduler` 指向 `tokenizer_worker_ipc_name`，启动时向 router 发 `TokenizerWorkerRegistrationReq` 注册。`MultiTokenizerRouter` 两条协程：下行 `receive_from_worker → send_to_scheduler`（pause/continue 额外扇出广播），上行 `recv_from_detokenizer → 按 http_worker_ipc 分发到对应 worker`。`http_worker_ipc` 由 `_dispatch_to_scheduler`（:569）在 `tokenizer_ipc_name` 非空时调用 `stamp_http_worker_ipc` 打到消息上，作为回程路由键。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
