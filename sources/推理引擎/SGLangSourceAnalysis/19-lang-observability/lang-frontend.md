## sglang.lang 前端 DSL：编程模型与后端翻译

本文覆盖 `lang/`（14 文件），说明 SGLang 独有的「可编程提示词」前端：`@sgl.function` 声明式程序、IR/解释器/跟踪器三态执行、`sgl.gen`/`sgl.select`/聊天原语，以及各 backend 如何把 IR 翻译成 HTTP 请求或 OpenAI 调用。与 vLLM（无此层）的差异对照见文末。

### 模块文件地图（lang/）

| 文件 | 职责 |
|---|---|
| `api.py` | 公开 API：`function`/`gen`/`gen_int`/`gen_string`/`select`/`image`/`video`/`system`/`user`/`assistant`/`separate_reasoning`/`Runtime`/`Engine`/`set_default_backend` |
| `ir.py` | IR 节点：`SglExpr`（带 `node_id`/`prev_node` 图链）、`SglExprList`、`SglGen`、`SglSelect`、`SglRoleBegin/End`、`SglFork`/`SglGetForkItem`、`SglVariable`、`SglCommitLazy`、`SglConcateAndAppend`、`SglSeparateReasoning`；`SglSamplingParams` |
| `interpreter.py` | `run_program`/`run_program_batch`；`StreamExecutor`（后台线程+队列逐表达式执行）、`ProgramState`、`ProgramStateGroup` |
| `tracer.py` | `trace_program`/`extract_prefix_by_tracing`；`TracerProgramState` 只建 IR 不调后端；`TracingScope` |
| `choices.py` | `select` 决策：`TokenLengthNormalized`/`GreedyTokenSelection`/`UnconditionalLikelihoodNormalized` |
| `chat_template.py` | `ChatTemplate` 注册表、按 model_path 匹配、role 前后缀与 stop 串 |
| `global_config.py` | 进程级前端配置（verbosity、default_backend、输出 token 化、precache/parallel_encoding 开关） |
| `backend/base_backend.py` | `BaseBackend` 抽象：`generate`/`generate_stream`/`select`/`concatenate_and_append` 等 |
| `backend/runtime_endpoint.py` | `RuntimeEndpoint`（HTTP 翻译）+ `Runtime`（spawn 拉起 server 的包装） |
| `backend/openai.py`/`anthropic.py`/`vertexai.py`/`litellm.py`/`crusoe.py` | 第三方 API 后端 |

### 编程模型：声明式定义、双执行态

`@sgl.function` 修饰普通 Python 函数（首个参数必须是 `s`，即 `ProgramState`），体内用 `s +=` 累积表达式；定义本身**不执行**，调用形态由上下文决定：

| 入口 | 执行方式 |
|---|---|
| `SglFunction.run()`（ir.py:160） | 解释执行：`run_program` → `StreamExecutor` 逐表达式真实调 backend |
| `SglFunction.trace()`（ir.py:304） | 跟踪：`TracerProgramState` 只追加 IR 节点，零后端调用 |
| `SglFunction.__call__`（ir.py:316） | 分派：`TracingScope` 存在 → trace，否则 → run |
| `SglFunction.run_batch()`（ir.py:223） | 批量：线程池跑 `run_program`（`num_threads="auto"` = `max(96, cpu*16)`） |
| `SglFunction.cache()`（ir.py:310） | 前缀预热：trace 提取公共前缀后 `backend.cache_prefix` |

`run` 把函数体交给 `StreamExecutor`（interpreter.py:274）：worker 线程从 `queue` 取 `SglExpr` 按类型派发 `_execute`（interpreter.py:461）；`ProgramState` 提供 `text()`/`messages()`/`get_var()`/`text_iter()`（流式）取数。**采样合并**：`sgl.gen()` 是单点覆盖，`run()` 默认参数为基线，`_resolve_sampling_params`（interpreter.py:799）以默认值为底 deepcopy 后逐字段覆盖（`value is not None`），再把 chat template 的 `stop_str` 并入 `stop`。

### 生成原语：gen / select / 角色

| 原语 | 行为 |
|---|---|
| `sgl.gen(name, ...)` | 构造 `SglGen`；`choices=` 改走 `SglSelect`（api.py:102）；`regex=` 先 `re.compile` 校验 |
| `sgl.gen_int`/`gen_string` | 预置 `dtype=int/str`；`RuntimeEndpoint._handle_dtype_to_regex`（runtime_endpoint.py:127）翻译为 `REGEX_INT`/`REGEX_STR` 等正则并补 `stop` |
| `sgl.select(name, choices, ...)` | 构造 `SglSelect`；解释执行调 `backend.select` |
| `sgl.image`/`sgl.video` | base64 编码追加 `s.images_`，文本侧插 template 的 `<image>` token（interpreter.py:524） |
| `sgl.system/user/assistant(expr)` 与 `*_begin/_end` | 包 `SglRoleBegin/End`；空参形式返回 contextmanager（`_role_common`，interpreter.py:858） |
| `sgl.separate_reasoning(gen)` | 包 `SglSeparateReasoning`；用 `srt/parser/reasoning_parser.ReasoningParser` 把输出切为 `reasoning_content` 与正文两个变量（interpreter.py:754） |

**select 实现**（runtime_endpoint.py:248）：先发 `max_new_tokens=0` 请求拿 `prompt_tokens`，`logprob_start_len=max(prompt_len-2,0)`（token healing），再对 `text+c` 各候选项批量请求 `return_logprob=True`；`choices_method` 在 `choices.py` 内比较归一化 logprob（或贪心/无条件归一化），返回 `ChoicesDecision`。

### backend 翻译：HTTP 与第三方 API

`RuntimeEndpoint`（runtime_endpoint.py:26）构造时 GET `/get_model_info` 并据此推断 chat template；`generate` 把已累积 `s.text_` 与 `to_srt_kwargs()` 打包 POST `/generate`：

```python
data = {"text": s.text_, "sampling_params": {"skip_special_tokens": ...,
        **sampling_params.to_srt_kwargs()}}
res = http_request(self.base_url + "/generate", json=data, ...)
```

| 后端操作 | HTTP 端点 | 负载要点 |
|---|---|---|
| `generate`/`generate_stream` | `POST /generate` | `text`+`sampling_params`+`return_logprob` 等；流式用 SSE `data:` 行取增量 |
| `select` | `POST /generate`×2~3 | 前缀缓存 + 批量 logprob + 可选无条件 logprob |
| `cache_prefix` | `POST /generate` | `{"text": prefix, "sampling_params": {"max_new_tokens": 0}}` |
| `concatenate_and_append` | `POST /concate_and_append_request` | `{src_rids, dst_rid}`，fork 分支 KV 直接拼接（`SglConcateAndAppend`） |
| `flush_cache`/`get_server_info` | `POST /flush_cache` / `GET /server_info` | — |

**Runtime 包装**（runtime_endpoint.py:356）：`sgl.Runtime(**server_args)` 用 `multiprocessing.spawn` 起 `launch_server`，轮询 `/health_generate` 就绪后包 `RuntimeEndpoint`，`atexit` 注册 `shutdown`（`kill_process_tree`）；另提供裸 `generate`/`encode`/`async_generate`。`sgl.Engine` 直通 `srt/entrypoints/engine.py` 离线 `Engine`（不经 HTTP，见 09-entrypoints/engine-api.md）。

**OpenAI 后端**（openai.py:56）走 `openai.OpenAI` 客户端，`gen_int` 用 tiktoken 数字 `logit_bias` 掩码；`SglSamplingParams.to_*_kwargs`（ir.py:64-138）按后端裁剪（OpenAI 无 `top_k`，Anthropic 无 frequency/presence penalty），`regex` 不支持时告警。

### fork/join 与 API 推测执行

- `ProgramState.fork(size)`（interpreter.py:888）复制变量/文本/消息，产 `ProgramStateGroup`；`join()` 两模式：`gather_variable` 合并新变量；`concate_and_append` 发 `SglConcateAndAppend` 做 **KV 缓存拼接**（需 `support_concate_and_append`，仅 RuntimeEndpoint=True，interpreter.py:493）。
- **API 推测执行**（`num_api_spec_tokens`）：chat 接口模型下 assistant 内 `gen` 先存懒调用、角色结束 `role_end_generate` 一次性执行；completion 接口走 `_spec_gen`（interpreter.py:543）在推测文本上做 stop 查找。

### 与 vLLM 的对照

vLLM **没有**等价前端 DSL：prompt 由调用方手工构造字符串/`messages` 列表，结构化输出走 guided decoding/工具解析器（见 vLLM 18-tool-parsers、SGLang 14-function-constrained），不存在「程序 + IR」抽象。

| 维度 | SGLang `sgl.lang` | vLLM |
|---|---|---|
| 编程抽象 | `@sgl.function` + `s += sgl.gen(...)`，IR 图可 `print_graph_dfs`（ir.py:361） | 无；prompt 即文本/消息 |
| 执行态 | run（解释）/ trace（建 IR）双态，`TracingScope` 嵌套自动切换 | 单一调用路径 |
| 多分支 | `fork/join` + `concate_and_append` 复用 KV | 无（需自行重复请求） |
| 选择式解码 | `sgl.select` 用 logprob 比较（token healing） | 无对应原语 |
| 后端可插拔 | `BaseBackend` 多实现（HTTP/OpenAI/Anthropic/Vertex/LiteLLM） | 仅本地 Engine（vLLM `LLM`） |
| 批量 | `run_batch` 线程池 + trace 预缓存公共前缀 | `LLM.generate` 内部 batch |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
