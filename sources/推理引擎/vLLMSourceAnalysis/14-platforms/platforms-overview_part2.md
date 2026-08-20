## Platform 硬件平台抽象总览（二）：后端差异对比

本文承接 [platforms-overview_part1.md](platforms-overview_part1.md)，对比 CUDA / ROCm / CPU / XPU 各后端关键能力差异；设备内存分配器见 [platforms-overview_part3.md](platforms-overview_part3.md)。TPU 由 `platforms/tpu.py` 转发到树外 `tpu_inference` 包；本版源码树内**无** HPU/Neuron 后端，二者走 out-of-tree 插件路径。

### 后端静态属性对比

| 类 | `_enum` | `device_type` | `dispatch_key` | `ray_device_key` | `dist_backend` | `device_control_env_var` |
|---|---|---|---|---|---|---|
| `CudaPlatformBase`（cuda.py:208） | CUDA | `"cuda"` | `"CUDA"` | `"GPU"` | `"nccl"` | `CUDA_VISIBLE_DEVICES` |
| `RocmPlatform`（rocm.py:498） | ROCM | `"cuda"` | `"CUDA"` | `"GPU"` | `"nccl"` | `CUDA_VISIBLE_DEVICES` |
| `CpuPlatform`（cpu.py:42） | CPU | `"cpu"` | `"CPU"` | `""`（不支持 Ray） | `"gloo"` | `DEVICE_CONTROL_ENV_VAR` |
| `ZenCpuPlatform`（zen_cpu.py:12） | CPU | `"cpu"` | 继承 CPU | 继承 | `"gloo"` | 继承 |
| `XPUPlatform`（xpu.py:103） | XPU | `"xpu"` | `"XPU"` | `"GPU"` | `"xccl"` | `ZE_AFFINITY_MASK` |

- ROCm `device_type="cuda"`：完全复用 `torch.cuda` 接口栈。导入时 `_sync_hip_cuda_env_vars()` 强制 `HIP_VISIBLE_DEVICES` 与 `CUDA_VISIBLE_DEVICES` 一致（冲突 → `ValueError`），并告警 CUDA_VISIBLE_DEVICES 于 v0.26.0 弃用。XPU 的 `dist_backend="xccl"` 由 `platforms/__init__.py` 探测阶段动态写入。
- `CudaPlatform` 运行时在 NVML 版与 `torch.cuda` 版间二选一（cuda.py:1022）；NVML 可无状态查询（不初始化 CUDA context），Jetson 等无 NVML 环境走后者。模块末尾 `log_warnings()` 检查多型号混插需 `CUDA_DEVICE_ORDER=PCI_BUS_ID`。

### supported_dtypes 与 dtype 校验

`supported_dtypes` 顺序敏感：`dtype="auto"` 遇到不支持类型时以**首元素**回退。

| 后端 | supported_dtypes | 判定 |
|---|---|---|
| CUDA | 计算能力 ≥80 → `[bf16, fp16, fp32]`；≥60 → `[fp16, fp32]`；否则 `[fp32]` | 按 `DeviceCapability` 分级 |
| ROCm / XPU | 继承基类 `[bf16, fp16, fp32]` | — |
| CPU | POWERPC → `[bf16, fp32, fp16]`；ARM+macOS → 依 `sysctl hw.optional.arm.FEAT_BF16`；RISCV → `[bf16, fp16, fp32]`；其余同默认 | 按 `CpuArchEnum` 分级 |
| ZenCpu | `[bf16, fp32]` | AMD CPU 无 fp16 计算 |

`check_if_supports_dtype`：CUDA/ROCm 对 bf16 要求计算能力 ≥8.0，否则 `ValueError` 并建议 `--dtype=half`；XPU 对 Arc A770 抛 bf16 精度已知问题，同样建议 `--dtype=half`。

### 注意力后端选择差异

`get_attn_backend_cls` 返回后端类**全限定名路径**，供 `vllm/v1/attention/selector.py` 惰性加载。

| 后端 | 候选优先级与规则 |
|---|---|
| CUDA | 按计算能力生成优先级列表并逐个 `validate_configuration()` 过滤，取优先级最小者。非 MLA：SM100f（major==10 且非因果）优先 `FLASHINFER`，否则 `FLASH_ATTN` 优先，候选含 `TRITON_ATTN`/`FLEX_ATTENTION`/`TURBOQUANT`。MLA 按 major==10/12/其余三档给出 `FLASHINFER_MLA`/`FLASH_ATTN_MLA`/`TRITON_MLA` 等次序（10 档含 sparse 族）。`--block-size` 排除更高优先级后端时仅告警降级 |
| ROCm | 候选 `ROCM_ATTN`/`ROCM_AITER_FA`/`ROCM_AITER_UNIFIED_ATTN`/`TRITON_ATTN`/`TURBOQUANT`；KV connector 或 encoder-decoder（legacy K-V 外层布局与 encoder 后端不兼容）时剔除 `ROCM_ATTN`。MLA：AITER 启用 → `ROCM_AITER_MLA` 优先，否则仅 `TRITON_MLA` |
| CPU | 固定 `CPU_ATTN`；MLA → `CPU_MLA`（参考实现，decode kernel 仅支持 block_size=16，`check_and_update_config` 无条件覆写）；`use_sparse` → `NotImplementedError` |
| XPU | `turboquant_*` KV dtype → `TURBOQUANT`；sparse → `XPU_MLA_SPARSE`；MLA → `TRITON_MLA`；float32 → 降级 `TRITON_ATTN`；mm-prefix-LM → `TRITON_ATTN`（Flash Attn 无 FA4 kernel，无法施加双向 mask，显式指定时告警放行） |

ViT attention（约束只能平台层覆写）：CUDA ≥80 支持 `[FLASH_ATTN, TRITON_ATTN, TORCH_SDPA, FLASHINFER]`；ROCm `[FLASH_ATTN, ROCM_AITER_FA, TRITON_ATTN, TORCH_SDPA]`（CDNA 优先 AITER/FlashAttn，RDNA 走 Triton）；XPU `[FLASH_ATTN, TRITON_ATTN, TORCH_SDPA]`。

### 设备能力（capability）表达

| 后端 | `get_device_capability` | 要点 |
|---|---|---|
| CUDA | NVML 或 `torch.cuda` | NVML 用**物理**设备 ID，不受 `CUDA_VISIBLE_DEVICES` 影响，不初始化 CUDA context |
| ROCm | 由 GCN arch 解析 | 模块加载时经 `amdsmi` 一次性解析 `_GCN_ARCH`（如 `gfx942`），映射 `(9,4)`；不初始化 HIP context，保住 `fork` 多进程语义 |
| CPU | `None`（基类） | 无计算能力概念 |
| XPU | 恒 `None` | capability 格式与 CUDA 不同，避免误用 |

ROCm 的模块级架构布尔量（普通 Python bool，torch.compile/Dynamo 安全）是按型号选内核的基础：`_ON_GFX9`（gfx90a/942/950）、`_ON_GFX11`、`_ON_GFX12X`、`_ON_CDNA`（gfx9/gfx1250）、`_ON_RDNA`、`_ON_RDNA4`（gfx1200/1201）、`_ON_MI3XX`（gfx942/950），对应 `on_cdna()/on_rdna()/on_mi3xx()/on_gfx942()…`，`get_cdna_version()` 返回 2/3/4/5。生效点：`supports_fp8 = on_cdna() or on_rdna4()`；`is_fp8_fnuz = "gfx94" in _GCN_ARCH`（`fp8_dtype()` → `float8_e4m3fnuz`）；`use_custom_allreduce` 仅 MI300（gfx94/gfx95）。设备名经 `_ROCM_DEVICE_ID_NAME_MAP` 映射（0x74a1→MI300X、0x74a5→MI325X 等）。

### 编译 / 分布式 / 内存钩子差异

| 钩子 | CUDA | ROCm | CPU | XPU |
|---|---|---|---|---|
| `support_static_graph_mode` | True | True | False（`cudagraph_capture_sizes=[]`） | True（实验性，仅单卡，需 `VLLM_XPU_ENABLE_XPU_GRAPH=1`） |
| `get_static_graph_wrapper_cls` | CUDAGraphWrapper | CUDAGraphWrapper | 基类 | CUDAGraphWrapper |
| `use_custom_allreduce` | True | 仅 MI300 | False | False |
| `use_custom_op_collectives` | True | True | False | True |
| `opaque_attention_op` / `support_hybrid_kv_cache` | True | True | True | True |
| `get_punica_wrapper` | PunicaWrapperGPU | PunicaWrapperGPU | PunicaWrapperCPU | PunicaWrapperXPU（`XPU_USE_TRITON_KERNEL=1` → GPU wrapper） |
| `get_device_communicator_cls` | CudaCommunicator | CudaCommunicator | CpuCommunicator | XpuCommunicator |
| `is_pin_memory_available` | WSL2 内核 ≥4.19.121 且 `VLLM_WSL2_ENABLE_PIN_MEMORY=1` | WSL2 内核门槛 | False | True |
| `import_kernels` | `_C_stable_libtorch`+`_moe_C_stable_libtorch`+可选 `_qutlass_C` | 额外 `_rocm_C` | x86 按 AVX512/AVX2 选 `_C`/`_C_AVX512`/`_C_AVX2` | **不** import `vllm._C`；顶层直接 import `vllm_xpu_kernels.*` |

`check_and_update_config` 平台介入要点：CUDA `worker_cls` auto → `gpu_worker.Worker`，mm-prefix-LM 强制 `--disable-chunked-mm-input`，WSL2+UVA+CUDA graph 组合告警（WDDM 对 pin memory 有 ~50% 物理 RAM 硬上限）；ROCm 在 DCP/PCP>1 且 full CUDA graph 时降级 `PIECEWISE`；CPU `worker_cls` → `cpu_worker.CPUWorker`、`block_size` 默认 128（MLA 强制 16）、`async_scheduling=False`、禁用 DBO、`spawn` 多进程、LD_PRELOAD libgomp/libtcmalloc；XPU 关 6 个 fusion pass、UVA offload 时禁 Inductor static Triton launcher、`shutdown_timeout` 0→5。`apply_config_platform_defaults` 仅 ROCm 覆写：按 AITER 开关追加 `+quant_fp8`/`+grouped_topk`/`+sparse_attn_indexer`。

### device_allocator 与 DeviceConfig 联动

`vllm/device_allocator/`（sleep-mode 按 tag 逐块卸载/恢复）与 `config/device.py` 的平台联动见 [platforms-overview_part3.md](platforms-overview_part3.md)。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
