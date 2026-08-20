## CustomOp 自定义算子机制

### 抽象层次

`vllm/model_executor/custom_op.py` 定义两级抽象，全局注册表：

```text
op_registry      : dict[str, CustomOp | PluggableLayer]    # 树内注册
op_registry_oot  : dict[str, CustomOp | PluggableLayer]    # 树外(oot)替换注册
```

| 基类 | 特点 |
|---|---|
| `CustomOp` | 单算子封装：提供 `forward_native/cuda/hip/cpu/tpu/xpu/oot` 各平台实现，构造时 `dispatch_forward` 选定一个；不持有子模块状态 |
| `PluggableLayer` | 模块组合抽象：可实例化子 `nn.Module`、可持有参数/缓冲区；不做平台 `forward_*` 派发，而是在实例化时整体替换类 |

两者都通过 `__new__` 拦截：若该 `name` 出现在 `op_registry_oot`，直接用树外类创建实例（`logger.debug` 记录）。

### 注册与替换装饰器

| 装饰器 | 语义 |
|---|---|
| `@CustomOp.register(name, dynamic_arg_dims=None)` | 注册 in-tree 算子，`name` 不可重复；`dynamic_arg_dims` 标记需 `torch._dynamo.mark_dynamic` 的动态维度 |
| `@CustomOp.register_oot([name=...])` | 注册 out-of-tree 替换算子（可裸用 `@X.register_oot` 或带参 `@X.register_oot(name=...)`），替换名默认取被注册类名 |
| `@PluggableLayer.register(name)` | 注册可插拔层 |
| `@PluggableLayer.register_oot([name=...])` | 注册 OOT 可插拔层 |
| `maybe_get_oot_by_class(class_type)` | 按类名查 `op_registry_oot`，命中则返回替换类 |

### 是否 fused：`enabled()` 与编译配置

`CustomOp.enabled()` 依据 `CompilationConfig.custom_ops`（`vllm/config/compilation.py`）判定：

```text
custom_ops -> ['all' | 'none']，再叠加 '+op_name' / '-op_name' 名单
enabled = (default_on() or 有 '+name') and 无 '-name'
```

- 基础模式唯一：`custom_ops.count("none") + count("all") == 1`，否则抛 `ValueError`。
- 默认值 `default_on()`：用 Inductor 后端时 `'none'`，否则 `'all'`（算子默认开启）。
- 同名同时出现 `+x` 与 `-x` 抛 `ValueError`。
- `__init__` 的 `enforce_enable=True` 可强制启用（如 ViT 图模式），并把算子名写入 `compilation_config.enabled_custom_ops`/`disabled_custom_ops`。
- 未注册（无 `name`）的类：告警一次，按全局默认判定（`default_on()`）。

### 平台派发（`dispatch_forward`）

构造时一次性选定 `_forward_method`：

```text
enabled? 否 -> maybe_compile(forward_native)（不启用则编译原生实现，便于 torch.compile）
平台判定 -> 按序：
  is_rocm()  -> forward_hip        is_cpu() -> forward_cpu
  is_tpu()   -> forward_tpu        is_xpu() -> forward_xpu
  is_out_of_tree() -> forward_oot  否则      -> forward_cuda
```

默认回退链：`forward_hip` 复用处 `forward_cuda`；`forward_tpu`/`forward_xpu`/`forward_cpu`/`forward_oot` 默认复用 `forward_native`。因此一个自定义算子在 CUDA 上写 `forward_cuda`、其余平台自动落回 PyTorch 原生即可。dispatch 假设 vLLM 仅为单一后端构建，不支持运行时动态切换。

### 禁用态编译（`maybe_compile`）

当算子被禁用时，`forward_native` 可用 `torch.compile` 编译：

```text
编译开启且 mode != NONE 且 backend != "eager" 时：
  有 _dynamic_arg_dims -> dynamic=False + 逐个 mark_dynamic + 包装
  否则                 -> dynamic=True（避免反复重编译）
```

好处：从不透明 custom op 内部（如 `fused_moe`、`unified_attention`）调用的钩子也能被编译；跨算子融合不做，仍应尽量解开 opaque op。

### op 验证（golden 校验）

运行时源码内**无显式 golden 比对机制**（「未确认」）：`model_executor` 不包含 golden 校验代码。相关正确性保障分散在：

| 机制 | 位置 | 说明 |
|---|---|---|
| `forward_native` 参考实现 | 各 CustomOp 子类 | 官方标注「可用于测试」，作为原生参考行为 |
| `torch.library.opcheck` | `tests/kernels/utils.py::opcheck` | 用提供 args/kwargs 的确定性输出校验自定义算子（schema/autograd/faketensor/aot_dispatch 检查），并 patch `allclose` 支持 fp8/bf16 ULP 距离 |
| golden 参考核 | `tests/kernels/utils.py::ref_masked_attention` 等 | 以纯 PyTorch 实现作 golden 参考（docstring 明示 `"Golden" masked attention reference`），实测输出用 pass-rate / max-error / mean-error 三层断言 `_assert_accurate` 比对 |
| 确定性断言 | `_assert_deterministic` | 多次调用产出按位一致的结果 |

即 golden 校验发生在测试阶段：以 `forward_native`/纯 PyTorch 参考实现为 golden，比对 fused 或平台专用 kernel 的输出（含 pass-rate、`max_violation_factor*atol` 上界、`mean <= atol/4`）。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)