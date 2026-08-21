## LoRA 与适配器总览（17-lora）

本文基于 SGLang `sglang/srt/lora/` 源码，说明 LoRA 请求如何表示、注册、调度，以及如何与调度器 / 模型执行器衔接。SGLang 的 LoRA 实现融合了 S-LoRA（千级并发适配器）与 Punica（多租户 LoRA 服务）思想（见 `lora.py:15-16` 头注）。

### 模块文件清单

顶层共 13 个 `.py`（含子目录 `backend/`、`torch_ops/`、`marlin_lora_temp/`、`trtllm_lora_temp/` 约 45 个文件）：

| 文件 | 职责 |
|---|---|
| `lora_registry.py` | `LoRARef`(适配器引用记录) + `LoRARegistry`(tokenizer 侧全局注册表,含引用计数) |
| `lora_config.py` | `LoRAConfig`:解析 `adapter_config.json`、`added_tokens.json` |
| `lora.py` | `LoRAAdapter` / `LoRALayer`:CPU 权重容器与键名归一化(stack qkv/gate_up 等) |
| `lora_manager.py` | `LoRAManager`:适配器加载/卸载、目标模块注入、与后端衔接 |
| `mem_pool.py` | `LoRAMemoryPool`:GPU 权重池、槽位分配、逐出(eviction) |
| `eviction_policy.py` | LRU / FIFO 逐出策略 |
| `lora_drainer.py` | 公平调度:饥饿适配器检测、运行中适配器排空 |
| `lora_overlap_loader.py` | 异步权重加载(H2D 与计算重叠) |
| `layers.py` | `BaseLayerWithLoRA` 及全部包装层 |
| `utils.py` | 目标模块归一化、hidden dim 推导、LoRABatchInfo 等 |
| `backend/` | `base_backend` 抽象 + `triton`/`chunked`(csgmv)/`torch_native`/`ascend` 内核实现 |
| `lora_moe_runners.py`、`lora_moe_runner_marlin.py` | MoE LoRA 内核 runner(实验性) |
| `torch_ops/` | sglang 自定义算子入口(`lora_ops.py`、`graph_lora_ops.py`) |

### 请求表示:LoRARef 与 LoRARegistry

`lora_registry.py`:

| 组件 | 说明 |
|---|---|
| `LoRARef`(msgspec.Struct, frozen) | 字段:`lora_id`(默认 `uuid4().hex`)、`lora_name`、`lora_path`、`pinned`。`deterministic_id(lora_name, lora_path)` 用 `uuid5(NAMESPACE_URL, f"{name}\\0{path}")` 生成稳定 id,保证多节点各自解析 `--lora-paths` 时同一适配器 id 一致 |
| `LoRARegistry` | 常驻 tokenizer manager 进程,是全部可用适配器的单一事实来源;`_registry: OrderedDict[str, LoRARef]` 按 LRU 排序,`_counters: Dict[lora_id, ConcurrentCounter]` 跟踪在途请求 |

关键 API:`register`/`unregister`(写锁)、`acquire(lora_name)`(查 id 并计数器 +1)、`release(lora_id)`(计数器 -1)、`wait_for_unload`(等计数归零后安全卸载)、`lru_lora_name(exclude_pinned)`(供淘汰候选)。注册表与调度器之间采用"两阶段更新 + 最终一致"模型。

### 配置与启动参数

`LoRAConfig`(`lora_config.py`)解析 PEFT 配置:`target_modules`、`r`、`lora_alpha`、`use_dora`、`lora_added_tokens_size`(过滤掉 `< base_vocab_size` 的伪新增 token)。服务级参数(`server_args.py:2909-3002`):

| 参数 | 默认 | 说明 |
|---|---|---|
| `--enable-lora` | 有 `lora-paths` 时自动开启 | LoRA 总开关 |
| `--lora-paths` | [] | `PATH` / `NAME=PATH` / JSON dict,解析为 `LoRARef` 列表 |
| `--max-lora-rank` | 自动推断 | 权重池 rank 维上限 |
| `--lora-target-modules` | 自动推断 | 目标模块后缀并集;`all` 表示全部支持模块 |
| `--max-loras-per-batch` | 1 | 单 batch 最多同时激活的 LoRA 数,即 GPU 槽位数 |
| `--max-loaded-loras` | 无 | CPU 缓存适配器数上限,须 `>= max-loras-per-batch` |
| `--lora-eviction-policy` | lru | `lru` / `fifo` |
| `--lora-backend` | triton | `triton` / `csgmv` / `torch_native` / `ascend` |
| `--enable-lora-overlap-loading` | False | 异步权重加载 |
| `--lora-drain-wait-threshold` | 0 | >0 时启用 LoRA 排空调度 |
| `--lora-strict-loading` | False | 权重名不匹配时报错 |

### 调度器衔接:登记与缓存

- 请求携带 `lora_id`(`Req` 字段,`schedule_batch.py:930`);构造时 `lora_id` 被拼接到 `extra_key`(`schedule_batch.py:923-926`),随后作为 `RadixKey.extra_key` 参与 radix cache 前缀匹配(`schedule_batch.py:1353-1364`)——**同一前缀在不同 LoRA 下命中不同缓存节点**,KV 缓存按 LoRA 隔离。
- 调度主循环(`scheduler.py:3332-3345`):收集 `running_loras`(运行批 + chunked 待运行请求),更新 `LoRADrainer` 状态;`_can_schedule_lora_req`(`scheduler.py:3522`)依次检查:排空限制(`can_schedule`)→ 已在运行集合 → overlap loader 或 `validate_lora_batch`(槽位容量 + pinned 配额)。
- `LoRADrainer`(`lora_drainer.py`):当运行适配器数已满且等待队列出现"饥饿"适配器(等待超 `lora_drain_wait_threshold`),按 `max_remaining_tokens` 最少者标记 `is_draining_for`,排空期间不再接收新请求。
- 每步前向:模型执行器 `ForwardBatch` 派生 `lora_ids=[req.lora_id for req in batch.reqs]`(`forward_batch_info.py:802`),随后 `fetch_new_loras`(加载进池)+ `prepare_lora_batch`(`forward_batch_info.py:922-929`)。
- 热加载/卸载:调度器 `load_lora_adapter` / `load_lora_adapter_from_tensors` / `unload_lora_adapter`(`scheduler.py:4870-4891`)经 tp_worker 转发到 `model_runner.lora_manager`。

### 端到端流程

```
tokenizer manager 进程:LoRARegistry.acquire(lora_name) → lora_id(计数器+1)
        ↓ HTTP 请求 /llm 的 model 字段 "model:adapter"
scheduler:Req.lora_id;extra_key 追加 lora_id → radix cache 按 LoRA 隔离 KV
        ↓ 调度循环 scheduler.py:3332
_can_schedule_lora_req → validate_lora_batch / LoRAOverlapLoader
        ↓ ForwardBatch 构建(forward_batch_info.py:802,922-929)
fetch_new_loras(权重拷入 GPU 池) → prepare_lora_batch(构建 batch 元数据)
        ↓ base_runner.py:621 / decode_cuda_graph_runner.py:1146
各包装层 forward:base 层计算 + lora_backend.run_lora_a/b_sgemm 增量
```

### 与 vLLM 13-lora-adapters 对照

| 维度 | SGLang(17-lora) | vLLM(13-lora) |
|---|---|---|
| 请求表示 | `LoRARef` + 全局 `LoRARegistry`(按名查 id、引用计数) | `LoRARequest`(msgspec Struct)+ `LoRAResolver` |
| 权重容器 | `LoRAAdapter`(CPU,含键名归一化 stack) | `LoRAModel` / `LoRALayerWeights` / `PackedLoRALayerWeights` |
| 缓存组织 | `LoRAMemoryPool` 单级 GPU 池 + LRU/FIFO 逐出;pinned 槽位 | 注册缓存(`max_cpu_loras`)+ 活跃槽位(`max_loras`)两级 |
| 层注入 | 启动期 `init_lora_modules` + `replace_submodule`,包装层直接持有池张量引用 | 启动期 `_create_lora_modules` + `from_layer`,包装层持 stacked 缓冲 |
| 内核 | `BaseLoRABackend` 可插拔(triton/csgmv/torch_native/ascend),segment-gemm | `PunicaWrapper` + `ops/`(torch/triton/xpu) |
| 调度公平 | `LoRADrainer` 饥饿检测 + 排空 | 无对应机制(靠 `max_loras` 与 LRU) |

> 返回：[skill.md](../skill.md) | [faq.md](../faq.md)
