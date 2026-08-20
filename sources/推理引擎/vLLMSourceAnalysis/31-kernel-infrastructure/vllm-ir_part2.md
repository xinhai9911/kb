## vLLM IR：编译层中间表示与算子多实现分发（二）

### 优先级与分发（hot path）

```python
def dispatch(self, *args, **kwargs) -> IrOpImpl:
    if not self._priority_impls:
        return self.impls["native"]            # 未设优先级 → native + warning_once
    for impl in self._priority_impls:           # 依序取首个 supports_args 通过的 impl
        ...
```

- `set_default(priority)`：进程级永久设置（worker 初始化用）；`set_priority(priority)`：上下文管理器（作用域内临时切换）。
- `_filter_priority_impls`：跳过 `supported=False` 的实现；一旦遇到 `supports_args is None`（支持一切参数）即截断；若列表末尾仍不能兜底所有参数，自动追加 `native` 并 `warning_once` 提示。
- 分发前 `supports_args` 签名与 native 强校验的目的：让 hot path 直接按位置参数调用，避免拆包开销（源码注释 "Matching signatures allow faster dispatch on the hotpath"）。

### 容差与测试设施

- `DEFAULT_TOLERANCES`（`tolerances.py`）按 mantissa 精度给出 atol/rtol 默认值，用于 IR op 实现与 native 的对比验证：

| dtype | atol / rtol | 备注 |
|---|---|---|
| float64 | 1e-8 / 1e-8 | 52-bit mantissa |
| float32 | 1e-5 / 1.3e-6 | 23-bit mantissa |
| float16 | 1e-3 / 1e-3 | 10-bit mantissa |
| bfloat16 | 1e-3 / 1.6e-2 | 7-bit mantissa，rtol 放宽 |
| float8_e4m3fn | 1e-1 / 1e-1 | 3-bit mantissa |
| float8_e5m2 | 2e-1 / 2e-1 | 2-bit mantissa |
| float4_e2m1fn_x2 | 3e-1 / 3e-1 | 1-bit mantissa，packed x2 |
| int8 | 1 / 0 | 取整误差，rtol 无意义 |

- `op.override_tolerance(dtype, atol=..., rtol=...)` 按 op 覆盖（`ops/layernorm.py` 对 fp16 放宽为 1e-2/2e-3，因大形状归约累积舍入误差）。
- `register_input_generator` / `generate_inputs(**kwargs)`：为测试/编译缓存生成样例输入（`ops/layernorm.py` 内置 `(num_tokens, hidden_size, dtype, ...)` 生成器）。

### 哈希与编译缓存

- `util.hash_source(*srcs)`：对函数 `inspect.getsource`、Path 文件内容等做 SHA-256，是 impl 变更检测的基础。
- `IrOpImpl.uuid()`：`weak_cache` 缓存的对 `impl_fn` 所在源文件的哈希——`VllmIRLoweringPass.uuid()`（`compilation/passes/ir/lowering_pass.py`）把每个 op 的优先级列表 + 对应 impl uuid 拼入 Inductor 编译缓存 key；`IrOpPriorityConfig.compute_hash()`（`config/kernel.py`）同理把 impl uuid 纳入 `KernelConfig.compute_hash()`。实现被 Dynamo 隐藏（不在 traced 文件列表），故需显式纳入哈希。

### 在编译管线中的角色（衔接 17-compilation）

```
fusion pass（add/allreduce_rms、sequence_parallelism、rms_quant、qk_norm_rope_kvcache、
           rocm_aiter 等）把 torch 原语替换为 vllm.ir.ops.* 节点
        ↓
VllmIRLoweringPass（post-grad，fusion 之后、clone_elimination 之前）
    - PatternMatcherPass 匹配 CallFunctionVarArgs(IrOp.torch_op 列表)
    - 用 fake args（node.meta["val"]）调 ir_op.dispatch() 选中 impl
    - replace_by_example(impl.func_impl_fn, ..., run_functional_passes=False)
    - 结束后扫描残留 vllm_ir 节点并 warning；selected_impls 记录 op→node→provider
```

- 生命周期装配：`pass_manager.py` 在 fusion pass 队列末尾构造 `VllmIRLoweringPass`，其 `uuid()` 参与 `PostGradPassManager.uuid()`。
- 配置联动：`KernelConfig.ir_op_priority`（`IrOpPriorityConfig`）声明每 op 的优先级列表；`VllmConfig.__post_init__` 经 `current_platform.get_default_ir_op_priority()` 追加平台默认值（幂等去重）；`worker_base.py` 初始化时依次 `kernel_config.ir_op_priority.set_default()` 与 `vllm.ir.set_default_torch_wrap(...)`。
- torch wrap 开关：`ir_enable_torch_wrap` 默认 = `mode==VLLM_COMPILE and backend=="inductor"`（`config/vllm.py`）；CPU 平台在 `config/cpu.py` 强制 `False`。
- `apply_arg_defaults` 仅服务 lowering：补齐 native 签名默认值用于替换跟踪，注释明确 "SHOULD NOT BE USED IN THE DISPATCH PATH (SLOW)"。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
