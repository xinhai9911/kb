## Platform 硬件平台抽象总览（一）：接口契约与平台解析

本文基于 vLLM `vllm/platforms/` 源码，说明 `Platform` 基类提供的能力钩子契约，以及 `current_platform` 的探测与惰性解析机制。后端差异对比见 [platforms-overview_part2.md](platforms-overview_part2.md)，设备内存分配器见 [platforms-overview_part3.md](platforms-overview_part3.md)，静态属性契约与能力钩子分类见 [platforms-overview_part4.md](platforms-overview_part4.md)。

### 模块组成

| 文件 | 内容 |
|---|---|
| `platforms/interface.py` | `Platform` 基类（能力钩子全集）、`PlatformEnum`、`CpuArchEnum`、`DeviceCapability`、`UnspecifiedPlatform` |
| `platforms/__init__.py` | 各后端探测插件、`resolve_current_platform_cls_qualname()`、`current_platform` 惰性属性 |
| `platforms/cuda.py` | `CudaPlatformBase` + `NvmlCudaPlatform`/`NonNvmlCudaPlatform`，导出 `CudaPlatform` |
| `platforms/rocm.py` | `RocmPlatform` + gfx 架构判定辅助函数（`on_cdna`/`on_rdna4`/`on_mi3xx`/`on_gfx9…`） |
| `platforms/cpu.py` | `CpuPlatform`，含 NUMA 拓扑发现、ISA 分支内核导入 |
| `platforms/zen_cpu.py` | `ZenCpuPlatform(CpuPlatform)`，AMD Zen + zentorch 优化 |
| `platforms/xpu.py` | `XPUPlatform`（Intel GPU） |
| `platforms/tpu.py` | 仅为转发 shim：`TpuPlatform = tpu_inference.platforms.TpuPlatform`，并置 `USE_TPU_INFERENCE = True`；导入失败时 `logger.error` |

注：当前版本树内**不再包含** `hpu.py`/`neuron.py`。TPU 实现已外置到 `tpu_inference` 包，HPU/Neuron 等后端走 out-of-tree 插件路径（见下文 `PLATFORM_PLUGINS_GROUP`）。

### 枚举与能力版本

```python
class PlatformEnum(enum.Enum):
    CUDA = enum.auto(); ROCM = enum.auto(); TPU = enum.auto()
    XPU = enum.auto(); CPU = enum.auto(); OOT = enum.auto(); UNSPECIFIED = enum.auto()
```

| 类型 | 说明 |
|---|---|
| `PlatformEnum` | 七个取值；`OOT` 表示树外插件平台，`UNSPECIFIED` 表示未检测到任何加速器 |
| `CpuArchEnum` | `X86`/`ARM`/`POWERPC`/`S390X`/`RISCV`/`OTHER`/`UNKNOWN`，由 `Platform.get_cpu_architecture()` 依 `platform.machine()` 推断 |
| `DeviceCapability` | `NamedTuple(major, minor)`，实现全套比较运算符 + `as_version_str()` + `to_int()`（`major*10+minor`，断言 `minor<10`） |

围绕 `DeviceCapability` 有三个判定辅助：`has_device_capability(cap)`（`>=`）、`is_device_capability(cap)`（`==`）、`is_device_capability_family(cap)`（`//10` 相等，对应 CUDA 13 的 10.x/11.x/12.x family 语义）。三者在 `get_device_capability()` 返回 `None` 时统一返回 `False`。

### current_platform 如何确定

**第一步：探测插件。** `platforms/__init__.py` 为每个内置后端定义一个返回「平台类全限定名或 `None`」的探测函数：

| 插件键 | 函数 | 判定依据 |
|---|---|---|
| `tpu` | `tpu_platform_plugin` | `envs.VLLM_TPU_USING_PATHWAYS` → `tpu_inference.platforms.tpu_platform.TpuPlatform`；否则能 `import libtpu` → `vllm.platforms.tpu.TpuPlatform` |
| `cuda` | `cuda_platform_plugin` | `pynvml.nvmlDeviceGetCount() > 0` 且 vLLM 版本串不含 `"cpu"`；NVML 异常时若检出 Jetson（`/etc/nv_tegra_release` 或 `/sys/class/tegra-firmware`）仍判为 CUDA；非 NVML 类异常直接重抛 |
| `rocm` | `rocm_platform_plugin` | `amdsmi.amdsmi_get_processor_handles()` 非空 |
| `xpu` | `xpu_platform_plugin` | `torch.xpu.is_available()`；若 `torch.distributed.is_xccl_available()` 则顺带把 `XPUPlatform.dist_backend` 设为 `"xccl"` |
| `cpu` | `cpu_platform_plugin` | `envs.VLLM_TARGET_DEVICE == "cpu"`，或 vLLM 版本串含 `"cpu"`，或 `sys.platform` 为 darwin。命中后若 `_is_amd_zen_cpu()`（`/proc/cpuinfo` 同时含 `AuthenticAMD` 与 `avx512`）且 `zentorch` 可导入，返回 `ZenCpuPlatform`，否则 `CpuPlatform` |

**第二步：`resolve_current_platform_cls_qualname()` 的仲裁顺序。**

1. `VLLM_TARGET_DEVICE == "cpu"` 是**权威短路**：直接返回 CPU 平台，不再探测其他插件。注释说明原因——纯 CPU CI 复用加速器 wheel 且跑在加速器主机上，逐个探测会同时激活 CPU 与宿主加速器。
2. 通过 `load_plugins_by_group(PLATFORM_PLUGINS_GROUP)` 加载树外插件，与内置插件 `chain` 后逐个调用（单个插件抛异常被静默忽略）。
3. 树外插件激活 ≥2 个 → `RuntimeError`；恰好 1 个 → 采用它（`logger.info` 记录），**树外优先于内置**。
4. 否则内置插件激活 ≥2 个 → `RuntimeError`；恰好 1 个 → 采用。
5. 全无 → `vllm.platforms.interface.UnspecifiedPlatform`。

**第三步：惰性实例化。** 模块级 `__getattr__` 拦截 `current_platform` 访问：

```python
global _current_platform
if _current_platform is None:
    platform_cls_qualname = resolve_current_platform_cls_qualname()
    _current_platform = resolve_obj_by_qualname(platform_cls_qualname)()
    global _init_trace
    _init_trace = "".join(traceback.format_stack())
return _current_platform
```

之所以不能在 `import vllm.platforms` 时就解析：树外插件需要先 `from vllm.platforms import Platform` 才能继承基类，因此解析必须晚于插件加载。`_init_trace` 保存首次解析时的调用栈，便于排查「过早访问 `current_platform`」。模块同时定义 `__setattr__`，允许测试或插件直接覆写 `current_platform`。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
