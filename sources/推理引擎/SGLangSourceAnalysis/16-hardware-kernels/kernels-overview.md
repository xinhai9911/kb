## SGLang 统一内核命名空间 sglang/kernels：注册表、选择器与 BaseFusedOp（一）

`python/sglang/kernels/`（约 590 文件）按 RFC #29630 重构为**统一内核命名空间**：`spec.py`（元数据）→ `registry.py`（目录）→ `selector.py`（固定路径解析）→ `fused_op.py`（多后端算子契约）→ `ops/<group>/`（算子组，薄包装）→ `jit/`（JIT CUDA 基础设施）与 `aot/`（sgl_kernel 轮子源码）。核心理念：**注册只记元数据、后端按需懒加载、同一算子可有多个实现并存**。本文聚焦抽象与分派。

### 目录与职责

| 文件/目录 | 职责 |
|---|---|
| `spec.py` | `KernelBackend`/`DeviceType`/`PlatformInfo`/`CapabilityRequirement`/`FormatSignature`/`KernelSpec`（依赖自由的 msgspec 元数据，import 时不碰 torch） |
| `registry.py` | `KernelRegistry` + 进程级 `registry` + `register_kernel()`；以 `"<group>.<name>"` 为键存 spec 列表，同 (op,backend) 冲突注册抛错 |
| `selector.py` | `select_kernel(op, backend=None)` 确定性解析 + `get_kernel()`（lru 缓存 callable，公开包装的快速路径） |
| `fused_op.py` | `BaseFusedOp`（原 `srt/layers/utils.py::MultiPlatformOp` 的继任者）+ `register_fused_op` + 全局强制开关/追踪 |
| `ops/` | 20 个算子组子包（见 part2 族枚举），每函数是模块级实例上的薄包装 |
| `jit/` | JIT CUDA 构建/运行基础设施（`utils/compile/`、`csrc/`、`include/sgl_kernel/`） |
| `aot/` | `sgl_kernel` 轮子源码（CMake + pyproject 多平台变体 + `python/sgl_kernel/` 命名空间 + `csrc/`） |

### KernelBackend：实现「出处」而非设备

`KernelBackend`（`spec.py:29`）命名内核的**来源/构建方式**，与运行设备解耦——同出处可为多设备构建；设备支持由 `CapabilityRequirement` 逐 (op, backend) 声明。

| 值 | 含义 | 设备 |
|---|---|---|
| `TORCH` / `TORCH_COMPILE` | 纯 torch 参考 / `torch.compile(native)` | 任意 |
| `TRITON` | Triton 内核 | CUDA/ROCm 等 |
| `JIT` | `sglang.kernels.jit`（nvcc/hipcc 即时编译） | CUDA/ROCm |
| `AOT` | `sgl_kernel` 轮子（AOT CUDA/C++） | CUDA/ROCm |
| `CUTE_DSL` / `FLYDSL` | CUTE/CUTLASS DSL 手写内核 / FlyDSL MLIR（HIP gfx950） | CUDA / HIP |
| `FLASHINFER` / `DEEPGEMM` / `AITER` | 第三方内核库 | CUDA / CUDA / HIP |
| `TORCH_NPU` | torch_npu 厂商运行时 | Ascend NPU |

- `DeviceType` 只含 `CUDA/HIP/NPU/CPU`；`PlatformInfo.detect()` 在无 torch/无加速器时安全返回默认 CPU。
- `CapabilityRequirement` 是**设备 + 可选 SM 架构窗口**（`CapabilityRequirement.cuda(min_sm=(10,0))`），集合内 OR 语义；空集合 = 不限制。取代旧 `requires_cuda/requires_hip` 布尔（AND 语义表达不了「CUDA 或 HIP」）。

### 选择语义：无启发式优先级

`select_kernel`（`selector.py:38`）不排优先级：单后端 op 直接命中；多后端按 `is_available(platform)`（能力硬过滤）后**恰剩一个**才唯一化，多个可用则必须显式 `backend=`，零可用抛 `ValueError`。`get_kernel` 解析并缓存 callable。

### BaseFusedOp：forward 分派契约

`BaseFusedOp`（`fused_op.py:332`）是标准 `torch.nn.Module`，一个逻辑算子 + 两个正交维度：

| 维度 | 方法 | 说明 |
|---|---|---|
| 内核出处 | `forward_native`（**必需**，纯 torch 基准）/ `forward_torch_compile` / `forward_triton` / `forward_jit` / `forward_aot` / `forward_cute_dsl` / `forward_flashinfer` / `forward_deepgemm` / `forward_aiter` / `forward_torch_npu` | 各 `forward_<backend>` 同名签名，仅重写者可用；`available` 还须声明在 `capabilities` 才进自动选择 |
| 平台设备 | `forward_cuda` / `forward_hip`（隐式回退 CUDA）/ `forward_musa`（无隐式 CUDA 回退）/ `forward_npu` / `forward_xpu` / `forward_cpu`（仅 AMX）/ OOT `forward_<key>` | CUDA/HIP 不算内核出处；MUSA 需显式 `forward_musa` 才走 CUDA 路径 |

**分派优先级**（`fused_op.py:23`，静态部分首次调用时解析并缓存到 `self._forward_method`）：

| 序 | 步骤 |
|---|---|
| 1 | 显式 `forward(..., backend=...)`（未实现即抛，不静默降级） |
| 2 | 全局强制后端 `SGLANG_FORCE_FUSED_OP_BACKEND`（best-effort，未实现则回退正常分派 + 一次性警告） |
| 3 | OOT 平台 override（`register_oot_forward`，其次 `forward_<key>`） |
| 4 | 优化内核后端按 `priority`（默认 `DEFAULT_PRIORITY`：AOT→JIT→FLASHINFER→DEEPGEMM→CUTE_DSL→AITER→TORCH_NPU→TRITON→TORCH），经 `backend_eligible()`（CapabilityRequirement 匹配）过滤；重写 `backend_eligible` 可加逐调用形状/dtype 门控，转为动态选择 |
| 5 | 平台专用 `forward_<device>` |
| 6 | `forward_native` 兜底 |

- **torch.compile 模式**：`enter_torch_compile(num_tokens)` / `leave_torch_compile()` 幂等切换，外层编译期间算子切到编译安全路径（默认 native，TopK/FusedMoE 重写 `_torch_compile_forward` 保持 bs>1 行为）。
- **调试开关**：`SGLANG_FORCE_FUSED_OP_BACKEND=torch` 一键全量切 torch 参考做数值二分；`enable_fused_op_trace()` 记录每次调用的 op/backend/tensor 形状，得到模型实际内核清单。
- **注册**：`register_fused_op(instance, module, attr)` 把每个可用后端以 `"<module>:<attr>.forward_<backend>"` 目标注册进 registry，使 `select_kernel(..., backend=...)` 与目录盘点依然可用。

### ops 组包装实例（layernorm）

`ops/layernorm/__init__.py` 是范式：`RMSNormOp` 的 `capabilities = {AOT: CUDA, JIT: CUDA, AITER: HIP, TORCH_NPU: NPU}`，优先级 `(AOT, JIT, AITER, TORCH_NPU, TORCH)`——同一 `AOT` 出处在不同设备解析到不同实现（CUDA→`sgl_kernel.rmsnorm`，HIP→`aiter.rmsnorm2d_fwd`，NPU→`torch_npu.npu_rms_norm`）。模块级 `rmsnorm(...)` 是 `_RMSNORM = register_fused_op(RMSNormOp(), ...)` 实例的薄包装。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
