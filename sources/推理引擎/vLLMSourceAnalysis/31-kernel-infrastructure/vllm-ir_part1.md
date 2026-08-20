## vLLM IR：编译层中间表示与算子多实现分发（一）

本文基于 `vllm/ir/` 源码，说明 vLLM 自建的「IR 算子层」：它既是为 torch.compile / Inductor 提供的编译期中间表示（fusion pass 的输出目标），也是"同一算子多种内核实现"的分发底座。与 17-compilation 的 `VllmIRLoweringPass` 紧密衔接。

### 模块结构

| 文件 | 行数 | 角色 |
|---|---|---|
| `ir/op.py` | ~665 | `IrOp` / `IrOpImpl` / `IrOpInplace` 核心类与 `register_op` 装饰器 |
| `ir/ops/layernorm.py` | ~80 | 现役 IR 算子：`rms_norm`、`fused_add_rms_norm` |
| `ir/tolerances.py` | ~37 | 各 dtype 数值容差默认值 `DEFAULT_TOLERANCES` |
| `ir/util.py` | ~62 | `hash_source`（源码 SHA-256）与 `weak_cache`/`weak_lru_cache` 弱引用缓存 |
| `ir/__init__.py` | — | 导出 `register_op`、`enable_torch_wrap`、`set_default_torch_wrap`、`ops` |

`vllm_ir_torch_lib = torch.library.Library("vllm_ir", "FRAGMENT")`：每个 IR op 在 `torch.ops.vllm_ir.<name>` 命名空间下注册为 torch custom op，dispatch key 为 `CompositeExplicitAutograd`（不被 ATen IR 归一化分解），并 `_register_fake` 注册 fake 实现。

### IrOp：注册与形态

`register_op` 装饰器定义 IR op，核心约束：

| 约束 | 行为 |
|---|---|
| 命名 | 必须匹配 `[a-z_][a-z_0-9]*`，否则抛 `ValueError` |
| 签名 | 不允许 keyword-only 参数（"kwargs are not allowed during lowering"），注册即抛错 |
| activations | 默认取参数名以 `x` 开头的参数（如 `x`、`x_residual`）；可显式传 `activations=[...]` |
| 原生实现 | 自动注册为 provider `"native"`，`supported=True`、`supports_args=None`（永远可用），记录 `traceback.format_stack()` 调试栈 |

```python
@register_op(allow_inplace=True)
def fused_add_rms_norm(x, x_residual, weight, epsilon, variance_size=None):
    ...
```

- 每个 op 用 `infer_schema(native_impl, mutates_args=[])` 生成 schema 并 `lib.define`；`_fake_fn` 默认直通 native，可用 `register_fake` 覆盖。
- 双调用路径（torch wrap）：`__call__` 在 `_ENABLE_TORCH_WRAP=True` 时走 `self.torch_op`（torch custom op 分发），否则直连 `_inner_call`（dispatch + `func_impl_fn`）。`set_default_torch_wrap()` 全局切换；`enable_torch_wrap()` 为上下文管理器，用于 eager 模式避开 torch 分发开销、以及非 Inductor 平台无需 lowering 的场景。
- inplace 支持：`register_op(allow_inplace=True)` 生成 `IrOpInplace`，附带 `maybe_inplace` overload（schema 基于 `mutates_args=op.activations` 推断，要求输出 Tensor 数与 activations 数一致）。

### 多实现 provider 注册

`IrOp.register_impl(provider, supported=..., supports_args=..., inplace=...)` 注册同一 op 的备选实现：

| 参数 | 语义 |
|---|---|
| `provider` | 唯一标识；不得为保留名 `native` / `unfused`，命名规则同 op |
| `supported` | 平台静态支持检查（如硬件/库是否可用），不得用于基于全局状态的开关 |
| `supports_args` | 参数级动态检查（类型/形状/strides）；签名必须与 native 同名、同参数数量、同默认值 |
| `inplace` | 实现复用激活输入内存；须 op `allow_inplace=True` |

- schema 一致性强制：注册时 `infer_schema(impl_fn)` 必须与 native schema 完全一致，否则 `ValueError`。
- 函数式语义：`func_impl_fn` 对 inplace impl 先 `clone()` 所有 activation 输入再调用，保证默认 overload 纯函数；`maybe_inplace` overload 则直连 `impl_fn` 允许就地写回。
- 真实 provider 示例（均注册 `rms_norm` / `fused_add_rms_norm`）：

| 文件 | provider | 条件 |
|---|---|---|
| `kernels/vllm_c.py` | `vllm_c` | `GPGPU_DEVICE`（CUDA-alike/XPU），且 `variance_size is None` 且 weight dtype 与 x 一致；ROCm 上对高维/非连续输入先 reshape 再调 `torch.ops._C.rms_norm` |
| `kernels/oink_ops.py` | `oink` | `has_oink_op("rmsnorm")`，2D 化 + stride 兼容 + 连续 weight |
| `kernels/aiter_ops.py` | `aiter` | `AITER_SUPPORTED`，仅 fp16/bf16 激活、无 var_size 覆盖 |

平台接入点：`Platform.import_ir_kernels()`（`platforms/interface.py`）默认 `import vllm.kernels` 完成注册；OOT 平台可覆写导入自己的内核模块。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
