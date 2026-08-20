## 核心数据模型（二）：BlockTable / ForwardContext / HTTPConnection

本文承接 [sequence-model_part1.md](sequence-model_part1.md)，覆盖 KV 块表（`vllm/v1/worker/block_table.py`）、前向上下文（`vllm/forward_context.py`）与媒体抓取 HTTP 客户端（`vllm/connections.py`）。

### BlockTable（vllm/v1/worker/block_table.py）

KV 缓存的设备端块表，面向 Triton 内核的扁平 buffer 布局。

构造参数：`block_size`（分配块大小）、`max_num_reqs`、`max_num_blocks_per_req`、`max_num_batched_tokens`、`pin_memory`、`device`、`kernel_block_size`（注意力内核块大小）、`cp_kv_cache_interleave_size`、`slot_mapping_mode=TOKEN_TO_KV_SLOT`。

- **hybrid 块**：`kernel_block_size != block_size` 时，`blocks_per_kv_block = block_size // kernel_block_size`，`block_size` 改为内核块大小，`max_num_blocks_per_req` 按比例放大；分配侧与计算侧块粒度解耦。
- buffer 经 `CpuGpuBuffer` 双端分配：`block_table`（`[max_num_reqs, max_num_blocks_per_req]` int32）、`num_blocks_per_row`（numpy int32）、`slot_mapping`（`[max_num_batched_tokens]` int64）。
- 构造时读取 PCP/DCP 世界规模（`get_pcp_group`/`get_dcp_group`，未初始化时按 1/0 兜底），并注册 slot mapping Triton 内核 warmup。

行操作（按 `row_idx`，每请求一行）：

| 方法 | 行为 |
|---|---|
| `add_row` / `append_row` | 清零计数后追加 / 直接追加；hybrid 时先 `map_to_kernel_blocks` 展开 |
| `clear_row` / `move_row` | 清空一行；搬运后**清空源行**（防 dummy-run 批读到已释放块的 mamba 状态槽） |
| `swap_row` | 两行互换 |
| `compute_slot_mapping(num_reqs, query_start_loc, positions)` | 调 `_COMPUTE_SLOT_MAPPING_KERNEL`（Triton）逐 token 计算 `slot_mapping`；`SlotMappingMode.NONE`（Mamba 类状态缓存）直接跳过 |
| `commit_block_table` / `clear` | CPU→GPU 拷回 / 双端清零 |
| `get_device_tensor` / `get_cpu_tensor` / `get_numpy_array` | 只读访问 |

slot mapping 内核为**上下文并行感知**：按 `virtual_block_size = KV_CACHE_BLOCK_SIZE * TOTAL_CP_WORLD_SIZE` 定位虚拟块，仅本 rank 拥有的插槽写真实 slot，其余写 `PAD_SLOT_ID`（CUDA graph 兼容）；同时处理 DCP 下的 KV 交织（`cp_kv_cache_interleave_size`）。

辅助函数 `get_block_table_width(max_num_blocks, block_size, kernel_block_size=None, token_alignment=128)`：做 `token_alignment` 对齐与虚拟块拆分后返回表宽；`kernel_block_size` 必须整除 `block_size`，`token_alignment` 必须为正。

`MultiGroupBlockTable`：为多 KV cache 组（如 Mamba+attention 混合模型）各持一张 `BlockTable`，行操作统一转发，`__getitem__(i)` 取第 i 组；各表宽度按 `slot_mapping_mode` 决定是否做 token 对齐。

### ForwardContext（vllm/forward_context.py）

前向执行的编译/执行期全局状态。模块级单例 `_forward_context`，配套四个函数：

| 函数 | 行为 |
|---|---|
| `get_forward_context()` | 取当前上下文，未设置时 `assert` 报错（提示先 `set_forward_context`） |
| `is_forward_context_available()` | 布尔判断 |
| `override_forward_context(ctx)` | 上下文管理器，临时覆盖（保存/恢复前值） |
| `set_forward_context(attn_metadata, vllm_config, ...)` | 主入口：构造上下文并进入 override，退出时可能记录 batchsize 耗时统计 |

`ForwardContext`（dataclass）字段：

| 字段 | 说明 |
|---|---|
| `no_compile_layers` / `all_moe_layers` / `moe_layer_index` | 取自 `compilation_config.static_forward_context`；`fast_moe_cold_start` 时用字符串列表+计数器喂给 moe 自定义算子，避免编译图硬编码字符串（issue #31985） |
| `attn_metadata` | `dict[str, AttentionMetadata]`（v1）或两元素 list（DBO 双 microbatch），逐 attention 层名索引 |
| `slot_mapping` | 逐层 slot 映射张量 |
| `dp_metadata` | `DPMetadata \| None` |
| `cudagraph_runtime_mode` | `CUDAGraphMode`，缺省 `NONE`；`__post_init__` 校验合法性 |
| `batch_descriptor` / `ubatch_slices` / `is_padding` / `skip_compiled` | CUDA graph 分派描述 / micro-batch 切片 / token 轴 padding 掩码 / 绕过编译走 `.forward()` |
| `additional_kwargs` | 平台注入的附加参数（`current_platform.set_additional_forward_context`） |

`BatchDescriptor`（frozen）：CUDA graph 分派键，含 `num_tokens`、`num_reqs`（PIECEWISE 下可为 `None`）、`uniform`、`has_lora`、`num_active_loras`。`DPMetadata`：`num_tokens_across_dp_cpu` + `local_sizes`；`make()` 断言 DP>1 或 SP MoE 且 `is_moe_model is not False`；`sp_local_sizes()` 上下文计算按 SP 切分的 token 数；`cu_tokens_across_sp(sp_size)` 给出跨 SP rank 的 cumsum。`set_forward_context` 在 DP>1 时经 `coordinate_batch_across_dp`（`allow_microbatching=False`）协调批大小。`VLLM_LOG_BATCHSIZE_INTERVAL>=0` 时按 batchsize 统计前向中位数耗时（ms）。

### HTTPConnection（vllm/connections.py）

多模态媒体抓取的 HTTP 客户端（同步 `requests.Session` + 异步 `aiohttp.ClientSession`，`trust_env=True`），模块级单例 `global_http_connection`。

| 方法 | 说明 |
|---|---|
| `get_response` / `get_async_response` | 原始响应；URL 仅接受 `http`/`https` scheme，User-Agent 为 `vLLM/{__version__}` |
| `get_bytes`/`get_text`/`get_json` 及 async 版 | `raise_for_status()` 后取 body |
| `download_file`/`async_download_file` | 分块落盘（`chunk_size=128`），失败先清理半成品再重试 |

重试语义：`_sync_retry`/`_async_retry` 装饰器，`max_retries = max(VLLM_MEDIA_FETCH_MAX_RETRIES, 1)`；指数退避因子 4，第 N 次尝试 timeout = `base_timeout * 4^N`、退避 sleep `4^N` 秒。`_is_retryable`：各类 timeout、连接级失败、`ServerDisconnectedError`、5xx（含 S3 `503 SlowDown`）；4xx 与编程错误（`ValueError`/`TypeError`）不重试。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
