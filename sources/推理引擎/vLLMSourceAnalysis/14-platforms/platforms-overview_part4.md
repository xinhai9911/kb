## Platform 硬件平台抽象总览（四）：静态属性契约与能力钩子

本文承接 [platforms-overview_part1.md](platforms-overview_part1.md)，说明 `Platform` 静态类属性契约与能力钩子分类的前半部分；注意力后端选择、配置介入、block size 对齐、计算特性、分布式编译钩子及兜底属性代理见 [platforms-overview_part5.md](platforms-overview_part5.md)。

### 静态类属性契约

| 属性 | 基类默认 | 用途 |
|---|---|---|
| `_enum` | 无默认（子类必填） | 驱动 `is_cuda()`/`is_rocm()`/… 全部身份判定 |
| `device_name` / `device_type` | 子类必填 | `device_type` 同时是 `torch.<device_type>` 的模块名（见兜底 `__getattr__`） |
| `dispatch_key` | `"CPU"` | PyTorch dispatch key，未在 torch 注册的平台用 CPU 兜底 |
| `ray_device_key` | `""` | Ray 资源名；空串表示不支持 Ray |
| `device_control_env_var` | `"VLLM_DEVICE_CONTROL_ENV_VAR_PLACEHOLDER"` | 平台无关的可见设备控制变量抽象 |
| `ray_noset_device_env_vars` | `[]` | 需置 1 以阻止 Ray 改写可见设备的变量名列表 |
| `simple_compile_backend` | `"inductor"` | 编译**独立小函数**用的 backend（模型 forward 另有编译策略）；`get_compile_backend()` 默认原样返回 |
| `dist_backend` | `""` | torch.distributed 通信后端名 |
| `supported_quantization` | `[]` | 空列表表示不做限制；`verify_quantization(quant)` 仅在非空且不含该项时抛 `ValueError` |
| `additional_env_vars` | `[]` | 平台附加环境变量声明 |
| `_global_graph_pool` | `None` | 类级缓存，`get_global_graph_pool()` 首次调用时经 `graph_pool_handle()` 填充 |
| `pass_key`（property） | `"post_grad_custom_post_pass"` | PassManager 注册进 Inductor config 的键名 |
| `supported_dtypes`（property） | `[bf16, fp16, fp32]` | **顺序敏感**：`dtype="auto"` 遇到不支持类型时以首元素为回退 |

### 能力钩子分类

**身份与全局特性**（实例方法，基于 `_enum`）

| 钩子 | 默认行为 |
|---|---|
| `is_cuda`/`is_rocm`/`is_tpu`/`is_xpu`/`is_cpu`/`is_out_of_tree`/`is_unspecified` | `_enum` 相等比较 |
| `is_cuda_alike()` | `_enum in (CUDA, ROCM)`——无状态版 `torch.cuda.is_available` |
| `is_zen_cpu()` | `False`（仅 `ZenCpuPlatform` 覆写为 `True`） |
| `uses_host_device_handling()` | `is_tpu()`；为真时 vLLM 保持 `DeviceConfig.device` 不设 |
| `is_sleep_mode_available()` | `_enum in (CUDA, ROCM, XPU)`。注释说明 ROCm 实际仅 MI3xx 支持，但此处无法无状态判定型号，故整体返回 `True` |
| `is_cumem_allocator_available()` | 尝试 `from vllm.device_allocator.cumem import cumem_available`，`ImportError` 时 `False` |
| `get_max_output_tokens(prompt_len)` | `sys.maxsize` |

**设备查询**（默认 `raise NotImplementedError` 的强制项以 ⚠ 标注）

| 钩子 | 默认 |
|---|---|
| `get_device_capability(device_id=0)` | `None` |
| `get_device_name` / `get_device_uuid` / `get_device_total_memory` | ⚠ |
| `get_all_gpu_pci_bus_ids()` | ⚠（报错文案指向 `VLLM_GPU_NIC_PCIE_MAPPING`，用于 RDMA NIC 选择） |
| `set_device(device)` / `manual_seed_all(seed)` | ⚠ |
| `get_current_memory_usage(device=None)` | ⚠ |
| `num_compute_units(device_id=0)` | ⚠（NVIDIA SM / AMD CU / Intel EU 的统一名） |
| `inference_mode()` | `torch.inference_mode(mode=True)`；docstring 注明 TPU 等需覆写为 `torch.no_grad` |
| `is_pin_memory_available()` | WSL 下（`in_wsl()` 检测 uname 含 `microsoft`）保守返回 `False`，否则 `True` |
| `is_integrated_gpu(device_id=0)` | `False`；docstring 说明 UMA 设备（GH200/DGX Spark/Jetson Orin）上 `cudaMemGetInfo` 会低报可用内存 |

**三重设备 ID 命名空间。** `interface.py` 用整段注释明确区分：*logical*（vLLM 本地 ID，如 local rank）、*visible*（应用 `device_control_env_var` 后当前进程内的 torch 序号）、*physical*（NVML 等管理 API 使用的全局 ID，不受可见性变量重映射）。对应三个转换方法：

| 方法 | 方向 |
|---|---|
| `device_id_to_physical_device_id(int)` | logical → physical。优先查 `_assigned_physical_gpu_ids`（越界抛 `IndexError`）；否则查 `device_control_env_var`（**空串视为未设**，兼容 Ray 在 GPU 节点上的 CPU-only placement group）；再否则原值返回 |
| `logical_device_id_to_visible_device_id(int)` | logical → visible。先转 physical，再在可见列表中 `index()`；不在列表内抛 `RuntimeError` |
| `visible_device_id_to_physical_device_id(int)` | visible → physical（上者的逆向 env 翻译，与 logical 映射无关） |

`device_control_id_to_physical_device_id(str)` 是单条目解析钩子，默认 `int()`，失败抛 `ValueError`；`set_assigned_physical_gpu_ids(ids)` 幂等，重复传入不同值抛 `RuntimeError`。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
