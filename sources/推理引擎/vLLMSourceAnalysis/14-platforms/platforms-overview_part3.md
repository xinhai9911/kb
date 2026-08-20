## Platform 硬件平台抽象总览（三）：设备内存分配器与 DeviceConfig 联动

本文承接 [platforms-overview_part2.md](platforms-overview_part2.md)，分析 `vllm/device_allocator/` 的 sleep-mode 内存分配器，以及平台如何驱动 `config/device.py` 的设备类型推断。

### device_allocator 设备内存分配器

`vllm/device_allocator/` 实现 sleep-mode「按 tag 逐块卸载/恢复」机制：

| 文件 | 内容 |
|---|---|
| `__init__.py` | `MemAllocator` Protocol（`use_memory_pool/sleep/discard/wake_up/get_current_usage`）、`AllocationData` dataclass（handle/tag/cpu_backup_tensor/is_asleep）、`HandleType = (device, size, ptr, handle)`（`handle` 在 ROCm 为 `list[int]`，其余为 `int`）。工厂 `get_mem_allocator_instance()`：`is_cuda_alike()` → `CuMemAllocator`；`is_xpu()` → `XpuMemAllocator`；否则 `RuntimeError` |
| `cumem.py` | `CuMemAllocator` 单例：经 C 扩展 `vllm.cumem_allocator`（`python_create_and_map`/`python_unmap_and_release`）挂接 `torch.cuda.memory.CUDAPluggableAllocator`+MemPool。注释说明 cuda-python 绑定与 libcuda ctypes 包装均因 **context 不匹配**失败，唯一可行是 C 里调 driver API。`sleep(offload_tags)` 将指定 tag 的内存 `cudaMemcpy` 到 CPU（`pin_memory=PIN_MEMORY`）后 unmap 释放，其余直接丢弃；`wake_up` 重新 create_and_map 再拷回；`use_memory_pool(tag)` 上下文内新建 tensor 自动入池并带 tag（暂关 `expandable_segments` 规避 pytorch#147851）。ROCm 特有：free callback 对已 sleep 的分配返回**空 chunk 列表**，避免二次 unmap（物理块已释放，虚地址留作占位）。`atexit` 注册 `release_pools()` 先放 MemPool 引用，规避 pytorch#145168 的「pure virtual method called」 |
| `xpumem.py` | `XpuMemAllocator` 单例：经 `vllm_xpu_kernels` 的 `xpumem_allocator` 扩展 + `torch.xpu.memory.MemPool`/`XPUPluggableAllocator`，memcpy 走 `torch.ops._C.xpu_memcpy_sync`（`MEMCPY_DEVICE_TO_HOST`/`HOST_TO_DEVICE`），语义与 CuMemAllocator 对齐 |
| `sleep_mode_backend.py` | `SleepModeBackend` ABC（RFC #34303）：`suspend(level)/resume(tags)/state()`；能力探针类方法 `preserves_communicators`/`preserves_compiled_artifacts`/`preserves_graphs_with_communicators`/`supports_durable_storage`，供 executor 与 `/health` 免实例化自省。`SleepModeBackendFactory` 注册表默认 `cumem` → `CuMemBackend`（suspend level=1 卸载 `("weights",)` tag，level=2 全部丢弃；communicator 缓冲在池外故 `preserves_communicators=True`），第三方机制（CUDA checkpoint、CRIU、持久快照）可经 `vllm.general_plugins` 入口注册 |

分配器的生命周期与引擎 `sleep(level)` 联动：level=1 权重卸载到主机 RAM（进程内可恢复），level=2 直接丢弃（resume 时从模型源重载）。`get_current_usage()` 汇总池内所有分配的字节数，用于上报。

### 平台 → DeviceConfig 联动

`config/device.py` 的 `DeviceConfig.__post_init__`：

```python
if self.device == "auto":
    self.device_type = current_platform.device_type
    if not self.device_type:
        raise RuntimeError("Failed to infer device type, please set ...")
# uses_host_device_handling()（即 TPU）为真时保持 device=None
self.device = torch.device(self.device_type)
```

- `device="auto"` 时 `device_type` 直接取 `current_platform.device_type`（为空抛 `RuntimeError`，提示开 `VLLM_LOGGING_LEVEL=DEBUG`）；显式传入字符串或 `torch.device` 时取其类型。
- `uses_host_device_handling()`（基类默认 `is_tpu()`）为真时保持 `device=None`——部分平台输入处理走 CPU；其余平台统一 `torch.device(device_type)`。
- `compute_hash()` 返回空 factors 的哈希：注释说明设备/平台信息会由 torch/vllm 自动汇总，无需单独入哈希因子。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
