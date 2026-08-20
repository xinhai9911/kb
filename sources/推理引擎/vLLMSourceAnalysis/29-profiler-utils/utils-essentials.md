## vllm/utils 工具库核心（高频复用篇）

`vllm/utils/` 共约 39 个模块，被 engine、模型层、分布式、config 全链路 import。本文件聚焦**被广泛复用**的核心工具；基础设施类（异步/GC/内存/缓存/JSON 树）见 utils-infra.md。

### 目录速览

| 模块 | 核心符号 | 消费方示例 |
|---|---|---|
| `registry.py` | `ExtensionManager` | 工具解析器、量化、注意力后端等插件注册 |
| `torch_utils.py` | `set_random_seed`、`current_stream`、`LayerName`、`direct_register_custom_op`、dtype 映射 | 几乎所有模型/worker/分布式路径 |
| `import_utils.py` | `PlaceholderModule`、`LazyLoader`、`has_*` 可选依赖探测 | 可选加速包（deep_ep/deep_gemm 等）门控 |
| `hashing.py` | `sha256`、`sha256_cbor`、`xxhash`、`safe_hash` | 编译/缓存键、前缀缓存哈希 |
| `serial_utils.py` | `tensor2binary`/`binary2tensor`、`tensor2base64` | 多模态输入序列化、embedding 传输 |
| `__init__.py` | `random_uuid`、`is_moe_layer`、`length_from_prompt_token_ids_or_embeds` | 请求 ID、MoE 层判断 |

### ExtensionManager：注册表 helper

`registry.py` 仅 51 行，实现「按名字注册并实例化扩展类」的插件机制：

```python
FOO_REGISTRY = ExtensionManager()
@FOO_REGISTRY.register("my_foo_impl")
class MyFooImpl(Foo): ...
foo_impl = FOO_REGISTRY.load("my_foo_impl", value=123)
```

- `register(name)` 是装饰器，把类写入 `name2class: dict[str, type]`。
- `load(cls_name, *args, **kwargs)` 查表后直接构造；未注册时报 `assert "Extension class X not found"`。
- 这是整个 vLLM 唯一通用的注册表 helper；各类具体注册表（工具解析器、注意力后端等）多在各自模块内另行定义。

### torch_utils：被引最广的模块（1064 行）

**dtype 映射**：`STR_DTYPE_TO_TORCH_DTYPE` 覆盖 `float32/half/bfloat16/fp8_e4m3/fp8_e5m2/int8/nvfp4` 及 `fp8_per_token_head` 等 KV cache 专用串；`TORCH_DTYPE_TO_NUMPY_DTYPE` 供 pad 工具用。KV cache dtype 工具链：`get_kv_cache_torch_dtype`、`is_quantized_kv_cache`、`kv_cache_uses_per_token_head_scales`、`resolve_kv_cache_dtype_string`、`get_kv_cache_quant_algo_string`（把 modelopt `kv_cache_scheme` 映射到 vLLM 标准串，未知格式回退 `"auto"`）。

**随机种子管理**（`set_random_seed`，torch_utils.py:521）：非 None 时依次 `random.seed`、`np.random.seed`、`torch.manual_seed`、`current_platform.manual_seed_all(seed)`。`create_kv_caches_with_random`/`create_kv_caches_with_random_flash` 内部先调它，再按 dtype 生成均匀随机或 fp8（`_generate_random_fp8` 先用 float16 `uniform_` 再 `convert_fp8` 规避 NaN/Inf 位型）KV 缓存，广泛用于测试与 mock。

**CUDA 可见设备**：`torch_utils` 不提供 `set_cuda_visible_devices` helper；设备窄化由平台层负责（`vllm/platforms/cuda.py`、`rocm.py` 的 `device_control_env_var = "CUDA_VISIBLE_DEVICES"`）与 `vllm/envs.py` 的 `CUDA_VISIBLE_DEVICES` 读取配合完成。torch_utils 侧对应的是 `guard_cuda_initialization()` 上下文管理器——临时把 `CUDA_VISIBLE_DEVICES=""` 再还原，用于「避免意外 CUDA 初始化」的路径。

**Stream 管理**：模块导入时即**全局 patch** `torch.cuda.set_stream = _patched_set_stream`，用线程局部变量记录当前流；`current_stream()` 直接读 TLS，避免 `torch.cuda.current_stream()` 每次构造新对象的高开销（注释强调假设 C/C++ 不会绕过 set_stream 切流）。`aux_stream()` 返回进程级单例辅助流（MoE shared_expert 与 router overlap 用）。

**torch.compile 相关**：`LayerName`（torch >= 2.11 时注册为 hoisted opaque type，`VLLM_USE_LAYERNAME` 可关）把层名字符串作为图输入避免按层重编译；`direct_register_custom_op` 绕开 `torch.library.custom_op` 的派发开销，直接 `infer_schema` + `vllm_lib.define/impl` 注册（含 fake 实现）。

**线程/调度**：`set_torch_threads_for_runtime()` 稳态服务期把 torch intra-op 线程压到 1（spin-wait 与 cgroup 配额问题）；`available_cpu_count()`/`startup_omp_num_threads` 感知 `sched_getaffinity` 与 cgroup CPU quota；`set_default_torch_dtype`/`set_default_torch_num_threads` 上下文管理器。

其他：`current_stream`、`weak_ref_tensor(s)`（PP 的 `IntermediateTensors` 弱引用）、`get_accelerator_view_from_cpu_tensor`（UVA 零拷贝）、`is_lossless_cast`/`common_broadcastable_dtype`、`async_tensor_h2d`/`make_tensor_with_pad`、`is_torch_equal_or_newer`、`PIN_MEMORY = is_pin_memory_available()`。

### import_utils：可选依赖门控

- `PlaceholderModule(name)`：模块缺失时的占位对象，重写了全部 dunder 方法让**任何下游使用都抛出带指引的 ImportError**（查 `get_vllm_optional_dependencies()` 提示 `pip install vllm[extra]`）。
- `LazyLoader`：延迟 import 模块（如 xgrammar、mistral tokenizer），避免启动期副作用。
- `_has_module`/`_has_module_spec`（均 `@cache`）：前者 find_spec + 试导入（验证 native 依赖），后者只查 spec 不导入。
- 探测函数族：`has_deep_ep`/`has_deep_ep_v2`（v2 还需运行时 NCCL >= 2.30.4，用 `ctypes` 加载真库而非 torch 编译期常量）、`has_deep_gemm`（外部包优先，回退 `vllm.third_party`）、`has_tilelang`、`has_humming`、`has_aiter`、`has_fbgemm_gpu`、`has_cutedsl`、`has_triton_kernels`（并触发 `import_triton_kernels` 回退）等。
- `import_pynvml()`：为避免社区 `pynvml` 冲突，强制使用 vendored `vllm.third_party.pynvml`。

### hashing：编译/缓存键

| 函数 | 序列化 | 用途 |
|---|---|---|
| `sha256(input)` | pickle（HIGHEST_PROTOCOL） | 任意可 pickle 对象 → 32 字节 |
| `sha256_cbor(input)` | cbor2 `canonical=True` | 跨语言确定性哈希（config `compute_hash` 用） |
| `xxhash`/`xxhash_cbor` | 同上前置 | 前缀缓存哈希（可选依赖 xxhash，未装则抛 ModuleNotFoundError） |
| `get_hash_fn_by_name(name)` | — | 按名字取哈希函数（`prefix_caching` 配置） |
| `safe_hash(data)` | md5，FIPS 环境回退 sha256 | 配置摘要 |

### serial_utils 与 jsontree 概览

- `serial_utils.py`：`DTypeInfo` 记录「torch 存储 dtype / 可视图 dtype / numpy 视图 dtype」三元组，`EMBED_DTYPES`（float32/float16/bfloat16/fp8_e4m3/fp8_e5m2）与 `MM_METADATA_DTYPES`（int32/int64/uint8/bool）构成白名单；`tensor2binary`/`binary2tensor` 支持端序（native/big/little）转换，`tensor2base64`/`numpy2base64` 用于 torch.save / .npy 编码。
- `jsontree.py`：嵌套 JSON 结构（dict/list/tuple，叶子任意类型）的遍历工具：`json_iter_leaves`、`json_map_leaves`、`json_reduce_leaves`、`json_count_leaves`，多模态输入批处理（`BatchedTensorInputs`）中广泛使用。

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
