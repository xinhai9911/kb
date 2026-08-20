## 用量统计上报（usage/usage_lib.py）

vLLM 默认向官方统计服务器上报匿名用量数据（版本、平台、模型架构、部分配置），用于了解部署分布。整个逻辑集中在 `vllm/usage/usage_lib.py`（约 9500 字节），模块级单例 `usage_message = UsageMessage()`。

### 开关机制：is_usage_stats_enabled

默认**开启**，任一条件满足即关闭（`usage_lib.py:50`）：

| 开关 | 形式 |
|---|---|
| `VLLM_DO_NOT_TRACK=1` | 环境变量（`vllm/envs.py:822`） |
| `DO_NOT_TRACK=1` | 环境变量（Do Not Track 标准） |
| `VLLM_NO_USAGE_STATS=1` | 环境变量（`vllm/envs.py:821`） |
| `~/.config/vllm/do_not_track` 文件存在 | 文件路径由 `VLLM_CONFIG_ROOT`（默认 `~/.config/vllm`）拼接 |

首次调用后缓存到模块级 `_USAGE_STATS_ENABLED`。上报服务器 `VLLM_USAGE_STATS_SERVER` 默认 `https://stats.vllm.ai`，可用 `VLLM_USAGE_SOURCE`（默认 `"production"`）标记数据来源。

### 上报数据模型（UsageMessage）

服务器只支持**扁平 KV**，字段在 `__init__` 中显式声明并全部初始化为 `None`：

| 分组 | 字段 |
|---|---|
| 环境/平台 | `uuid`(uuid4)、`provider`、`num_cpu`、`cpu_type`、`cpu_family_model_stepping`、`total_memory`、`architecture`、`platform`、`xpu_runtime`、`cuda_runtime`、`gpu_count`、`gpu_type`、`gpu_memory_per_device` |
| vLLM 信息 | `model_architecture`、`vllm_version`、`context` |
| 元数据 | `log_time`（UTC 纳秒）、`source` |
| 附加 | `env_var_json`：固定收集 5 个环境变量（`VLLM_USE_MODELSCOPE`、`VLLM_USE_FLASHINFER_SAMPLER`、`VLLM_PP_LAYER_PARTITION`、`VLLM_USE_TRITON_AWQ`、`VLLM_ENABLE_V1_MULTIPROCESSING`） |

`UsageContext` 枚举标注上报入口：`LLM_CLASS`/`API_SERVER`/`OPENAI_API_SERVER`/`OPENAI_BATCH_RUNNER`/`ENGINE_CONTEXT`/`UNKNOWN_CONTEXT`。

### 上报流程

```python
def report_usage(self, model_architecture, usage_context, extra_kvs=None):
    Thread(target=self._report_usage_worker, ..., daemon=True).start()

def _report_usage_worker(...):
    self._report_usage_once(...)      # 一次性全量
    self._report_continuous_usage()   # 之后每 10 分钟心跳
```

- **一次性上报**（`_report_usage_once`）：按 `current_platform` 收集设备信息——cuda_alike 取 `device_count()` + `cuda_get_device_properties(0, ("name","total_memory"))`；cuda 加 `torch.version.cuda`；xpu 走 `torch.xpu`；TPU 尝试 `tpu_inference` 库；`_detect_cloud_provider` 通过 DMI 文件（`/sys/class/dmi/id/*`，识别 amazon→AWS、microsoft→AZURE、google→GCP、oraclecloud→OCI）或 `RUNPOD_DC_ID` 环境变量探测云厂商，未命中返回 `"UNKNOWN"`；再用 `psutil`、`cpuinfo` 补 CPU/内存；最后把 `vars(self)` 合并 `extra_kvs` 后 `_write_to_file` + `_send_to_server`。
- **持续心跳**（`_report_continuous_usage`）：每 600 秒发送 `uuid` + `log_time` + `_GLOBAL_RUNTIME_DATA`（由 `set_runtime_usage_data(key, value)` 写入的全局运行时数据），用于统计运行时长与性能指标。
- **落盘**：JSON 逐行 append 到 `~/.config/vllm/usage_stats.json`。
- **发送**：`requests.Session().post(_USAGE_STATS_SERVER, json=data)`，`RequestException` 仅记 debug 日志，静默失败。

### 上报入口与附加配置

`v1/utils.py` 的 `report_usage_stats(vllm_config, usage_context)`（默认 `UsageContext.ENGINE_CONTEXT`）先过 `is_usage_stats_enabled()`，再组装 `extra_kvs` 上报配置指纹：`dtype`、`block_size`、`gpu_memory_utilization`、`kv_cache_memory_bytes`、`quantization`、`kv_cache_dtype`、`enable_lora`、`enable_prefix_caching`、`enforce_eager`、`disable_custom_all_reduce`、`kv_connector`（KV 传输模式）、`attention_backend`、`compilation_mode`（枚举取 name）与投机解码配置（`method`、`num_speculative_tokens`）；模型架构取 `get_architecture_class_name`，transformers 后端时包装为 `TransformersForCausalLM(Starcoder2ForCausalLM)` 形式。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
