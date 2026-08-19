---
title: "vLLM（四）核心组件的初始化"
source: ""
author: "知乎·vLLM 源码解读系列"
published:
created: 2026-08-19
description: "本系列将介绍 vLLM 的方方面面："
tags:
  - "clippings"
  - "vLLM"
  - "知乎"
series: "vLLM（知乎）"
part: "四"
---
> [Efficient Memory Management for Large Language Model Serving with PagedAttention](https://link.zhihu.com/?target=https%3A//arxiv.org/pdf/2309.06180.pdf)  
> [https://github.com/vllm-project/vllm](https://link.zhihu.com/?target=https%3A//github.com/vllm-project/vllm)  
> [https://docs.google.com/presentation](https://link.zhihu.com/?target=https%3A//docs.google.com/presentation)  
> [Fast LLM Serving with vLLM and PagedAttention\_哔哩哔哩\_bilibili](https://link.zhihu.com/?target=https%3A//www.bilibili.com/video/BV1eF4m1N7rL/%3Fshare_source%3Dcopy_web%26vd_source%3Daac509da00df68a65bd1548362420c8d)

本系列将介绍 vLLM 的方方面面：

___

vLLM 的源码解读计划分三篇文章介绍，第一篇（本篇）介绍 vLLM 组件的初始化，第二篇介绍调度策略的实现细节，第三篇介绍模型的推理细节。  
温馨提示，在阅读本篇文章前，建议先阅读[vLLM（一）PagedAttention 算法](https://zhuanlan.zhihu.com/p/680153425)和[vLLM（二）架构概览](https://zhuanlan.zhihu.com/p/681716326)。

接下来，开始介绍 vLLM 组件的初始化，使用的 vLLM 版本为 [v0.2.7](https://link.zhihu.com/?target=https%3A//github.com/vllm-project/vllm/tree/v0.2.7)。

## LLM

vLLM 对外提供了 LLM 和 AsyncLLMEngine 接口，前者用于离线推理（offline inference），后者用于在线服务（online serving）。源码解读主要以 LLM 为入口介绍 vLLM 的实现细节。  
LLM 的初始化方法如下：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/entrypoints/llm.py class LLM: """根据 prompt 和采样参数生成文本""" def __init__( self, model: str, ... ) -> None: engine_args = EngineArgs( model=model, ... **kwargs, ) # 初始化 LLMEngine self.llm_engine = LLMEngine.from_engine_args(engine_args) self.request_counter = Counter()
```

初始化方法主要完成 LLMEngine 的初始化，LLMEngine 将会以 iteration-level 策略（常称 continous batching）调度请求并进行推理。  
顺便介绍一下它的 generate 方法：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/entrypoints/llm.py class LLM: def generate( self, prompts: Optional[Union[str, List[str]]] = None, sampling_params: Optional[SamplingParams] = None, prompt_token_ids: Optional[List[List[int]]] = None, use_tqdm: bool = True, ) -> List[RequestOutput]: """Generates the completions for the input prompts.""" ... for i in range(num_requests): prompt = prompts[i] if prompts is not None else None token_ids = None if prompt_token_ids is None else prompt_token_ids[ i] self._add_request(prompt, sampling_params, token_ids) return self._run_engine(use_tqdm)
```

处理逻辑：

-   先逐请求调用`_add_request`方法将请求添加到 llm\_engine（LLMEngine 的实例）。调用`generate`的时候可以把多个请求一次性传给`generate`方法，可以提升处理请求的并发量。
-   后调用`_run_engine`方法完成请求的处理。`_run_engine`内部有个 while 循环，循环体内调用`llm_engine`的`step`方法处理请求，直到所有的请求被处理完成。

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/entrypoints/llm.py class LLM: def _run_engine(self, use_tqdm: bool) -> List[RequestOutput]: ... # Run the engine. outputs: List[RequestOutput] = [] while self.llm_engine.has_unfinished_requests(): step_outputs = self.llm_engine.step() for output in step_outputs: if output.finished: outputs.append(output) if use_tqdm: pbar.update(1) ...
```

可以看到 LLM 类只是一个对外接口，核心的处理逻辑都在 LLMEngine。接下来深入分析 LLMEngine 是什么以及它承担了哪些责任。

## LLMEngine

LLMEngine 接受请求并生成输出。下面是 LLMEngine [docstring](https://zhida.zhihu.com/search?content_id=241953278&content_type=Article&match_order=1&q=docstring&zhida_source=entity) 对它功能的概括：

> This is the main class for the vLLM engine. It receives requests from clients and generates texts from the LLM. It includes a tokenizer, a language model (possibly distributed across multiple GPUs), and GPU memory space allocated for intermediate states (aka KV cache). This class utilizes iteration-level scheduling and efficient memory management to maximize the serving throughput.

一句话概括 LLMEngine 的核心：以 continuous batching 策略处理请求，并借助高效的显存管理机制（Paged Attention）最大化[吞吐量](https://zhida.zhihu.com/search?content_id=241953278&content_type=Article&match_order=1&q=%E5%90%9E%E5%90%90%E9%87%8F&zhida_source=entity)。  
LLMEngine 主要包含 2 个核心组件：

-   driver\_worker：Worker 的实例，负责请求（可能有多个）的单次推理
-   scheduler：Scheduler 的实例，主要负责以 iteration-level 策略调度请求

LLMEngine 核心组件之间的关系如图 1 所示：

![](https://pic1.zhimg.com/v2-f1c6d2e41bd27b8424e1824539748354_1440w.jpg)

图1：LLMEngine 核心组件

它的初始化方法如下：

```python3
# https://github.com/vllm-project/vllm/blob/v0.2.7/vllm/engine/llm_engine.py class LLMEngine: def __init__( self, model_config: ModelConfig, cache_config: CacheConfig, parallel_config: ParallelConfig, scheduler_config: SchedulerConfig, placement_group: Optional["PlacementGroup"], log_stats: bool, ) -> None: ... # 初始化 Worker if self.parallel_config.worker_use_ray: # Disable Ray usage stats collection. ray_usage = os.environ.get("RAY_USAGE_STATS_ENABLED", "0") if ray_usage != "1": os.environ["RAY_USAGE_STATS_ENABLED"] = "0" self._init_workers_ray(placement_group) else: self._init_workers() # 初始化 CacheEngine self._init_cache() # 初始化 Scheduler self.scheduler = Scheduler(scheduler_config, cache_config) ...
```

主要做了 3 件事情：

-   初始化 Worker
-   初始化 CacheEngine，它是 Worker 的一个组件（属性），职责是管理 KV cache，包括 GPU cache 和 CPU cache
-   初始化 Scheduler

### Worker

Worker 的初始化比较简单，包括：

-   初始化一个 Worker 对象
-   初始化分布式环境（用于支持 [Tensor Parallelism](https://zhida.zhihu.com/search?content_id=241953278&content_type=Article&match_order=1&q=Tensor+Parallelism&zhida_source=entity)）
-   加载模型

```python3
# https://github.com/vllm-project/vllm/blob/v0.2.7/vllm/engine/llm_engine.py class LLMEngine: def _init_workers(self): # Lazy import the Worker to avoid importing torch.cuda/xformers # before CUDA_VISIBLE_DEVICES is set in the Worker from vllm.worker.worker import Worker assert self.parallel_config.world_size == 1, ( "Ray is required if parallel_config.world_size > 1.") self.workers: List[Worker] = [] distributed_init_method = f"tcp://{get_ip()}:{get_open_port()}" self.driver_worker = Worker( self.model_config, self.parallel_config, self.scheduler_config, local_rank=0, rank=0, distributed_init_method=distributed_init_method, is_driver_worker=True, ) # 初始化分布式环境 self._run_workers("init_model") # 加载模型 self._run_workers("load_model")
```

Worker 的初始化定义如下：

```python3
# https://github.com/vllm-project/vllm/blob/v0.2.7/vllm/worker/worker.py class Worker: """ 每个 worker 关联一个 GPU。worker 负责 KV cache 的管理和在 GPU 上运行模型。 在分布式推理的情况下（例如 Tensor Parallelism），每个 worker 包含了模型的一部分。 """ def __init__( self, model_config: ModelConfig, parallel_config: ParallelConfig, scheduler_config: SchedulerConfig, local_rank: int, rank: int, distributed_init_method: str, is_driver_worker: bool = False, ) -> None: ... self.model_runner = ModelRunner(model_config, parallel_config, scheduler_config, is_driver_worker) ... # cache_engine 会在调用 init_cache_engine 时进行初始化 self.cache_engine = None ... def init_model(self) -> None: ... # 设置 device self.device = torch.device(f"cuda:{self.local_rank}") torch.cuda.set_device(self.device) _check_if_gpu_supports_dtype(self.model_config.dtype) # 初始化分布式环境 _init_distributed_environment(self.parallel_config, self.rank, self.distributed_init_method) # 设置种子 set_random_seed(self.model_config.seed) def load_model(self): self.model_runner.load_model()
```

**ModelRunner**

ModelRunner 是 Worker 的一个组件，是对 Model 的封装，主要负责模型的推理。

```python3
# https://github.com/vllm-project/vllm/blob/v0.2.7/vllm/worker/model_runner.py class ModelRunner: def __init__( self, model_config: ModelConfig, parallel_config: ParallelConfig, scheduler_config: SchedulerConfig, is_driver_worker: bool = False, ): ... self.model = None ... def load_model(self) -> None: self.model = get_model(self.model_config)
```

**CacheEngine**

CacheEngine 是 Worker 的另一个组件，用于 KV cache 的管理，它的职责是初始化和管理 GPU 和 CPU KV cache。CPU KV cache 的用途是当 GPU KV cache 的空间不足时，可以将一个请求的 KV cache 先暂时换到 CPU KV cache。  
CacheEngine 对 KV cache 的管理是通过提前将一大块空间（显存或内存）划分成多个块（block），每块有 block\_size 个 slot，每个 slot 存放一个 token 对应的 K V 值。  
下面是 LLMEngine 中初始化 CacheEngine 的逻辑：

```python3
# https://github.com/vllm-project/vllm/blob/v0.2.7/vllm/engine/llm_engine.py class LLMEngine: def _init_cache(self) -> None: """Profiles the memory usage and initializes the KV cache.""" # Get the maximum number of blocks that can be allocated on GPU and CPU. num_blocks = self._run_workers( "profile_num_available_blocks", block_size=self.cache_config.block_size, gpu_memory_utilization=self.cache_config.gpu_memory_utilization, cpu_swap_space=self.cache_config.swap_space_bytes, ) # 因为所有 worker 执行的推理都一样，所以取 worker 中最小的一个 # 以确保不会在某张卡上出现显存不足的情况 num_gpu_blocks = min(b[0] for b in num_blocks) num_cpu_blocks = min(b[1] for b in num_blocks) ... self.cache_config.num_gpu_blocks = num_gpu_blocks self.cache_config.num_cpu_blocks = num_cpu_blocks # 初始化 CacheEngine self._run_workers("init_cache_engine", cache_config=self.cache_config) # Warm up the model. This includes capturing the model into CUDA graph # if enforce_eager is False. self._run_workers("warm_up_model")
```

-   调用 worker 的`profile_num_available_blocks`方法分析显存的情况并返回可以开辟的块数量
-   调用 worker 的`init_cache_engine`方法初始化 CacheEngine（会完成一大块空间的分配）
-   调用 worker 的`warm_up_model`方法，目的是优化模型执行过程中的 CPU 开销（[https://github.com/vllm-project/vllm/pull/1926](https://link.zhihu.com/?target=https%3A//github.com/vllm-project/vllm/pull/1926)）

下面介绍`profile_num_available_blocks`是如何计算可以开辟的块数量。

```python3
# https://github.com/vllm-project/vllm/blob/v0.2.7/vllm/worker/worker.py class Worker: @torch.inference_mode() def profile_num_available_blocks( self, block_size: int, gpu_memory_utilization: float, cpu_swap_space: int, ) -> Tuple[int, int]: # Profile the memory usage of the model and get the maximum number of # cache blocks that can be allocated with the remaining free memory. torch.cuda.empty_cache() # 调用 model_runner 的 profile_run 执行一次推理以分析显存的使用情况 self.model_runner.profile_run() # Calculate the number of blocks that can be allocated with the # profiled peak memory. torch.cuda.synchronize() free_gpu_memory, total_gpu_memory = torch.cuda.mem_get_info() peak_memory = total_gpu_memory - free_gpu_memory cache_block_size = CacheEngine.get_cache_block_size( block_size, self.model_config, self.parallel_config) num_gpu_blocks = int( (total_gpu_memory * gpu_memory_utilization - peak_memory) // cache_block_size) num_cpu_blocks = int(cpu_swap_space // cache_block_size) num_gpu_blocks = max(num_gpu_blocks, 0) num_cpu_blocks = max(num_cpu_blocks, 0) torch.cuda.empty_cache() return num_gpu_blocks, num_cpu_blocks
```

`profile_num_available_blocks`首先调用 model\_runner 的`profile_run`方法执行一次 forward 的过程以分析显存的使用情况，后调用 CacheEngine 的`get_cache_block_size`方法计算一个块要占用的空间，最后计算可以开辟的 GPU 块和 CPU 块数量。

```python3
# https://github.com/vllm-project/vllm/blob/v0.2.7/vllm/worker/cache_engine.py class CacheEngine: @staticmethod def get_cache_block_size( block_size: int, model_config: ModelConfig, parallel_config: ParallelConfig, ) -> int: head_size = model_config.get_head_size() num_heads = model_config.get_num_kv_heads(parallel_config) num_layers = model_config.get_num_layers(parallel_config) key_cache_block = block_size * num_heads * head_size value_cache_block = key_cache_block total = num_layers * (key_cache_block + value_cache_block) dtype_size = _get_dtype_size(model_config.dtype) return dtype_size * total
```

块占用空间的计算公式如下：`block_size * 2 * num_head * head_size * num_layers`，  
即每个块可以存放 block\_size 个 token 对应的 K V 值，每个 token 对应的 K V 个数为`2 * num_head * head_size * num_layers`，所以每个块总共要存放`block_size * 2 * num_head * head_size * num_layers`个值，每个值占用的空间为 dtype\_size 个字节（如果 [tensor](https://zhida.zhihu.com/search?content_id=241953278&content_type=Article&match_order=1&q=tensor&zhida_source=entity) 的 dtype 为 float16，则 dtype\_size 为 2，dtype 为 float32，则 dtype\_size 为 4）。  
在完成块数量的计算后，接下来就真正开始初始化 CacheEngine。

```python3
# https://github.com/vllm-project/vllm/blob/v0.2.7/vllm/worker/worker.py class Worker: def init_cache_engine(self, cache_config: CacheConfig) -> None: self.cache_config = cache_config self.cache_engine = CacheEngine(self.cache_config, self.model_config, self.parallel_config) self.cache_events = self.cache_engine.events self.gpu_cache = self.cache_engine.gpu_cache self.model_runner.set_block_size(self.cache_engine.block_size)
```

CacheEngine 的初始化完成两件事情：

-   分配 KV cache 空间
-   创建 KV cache 操作相关的 cuda stream（例如将块的内容从 GPU 拷贝到 CPU）

CacheEngine 的定义如下：

```python3
# https://github.com/vllm-project/vllm/blob/v0.2.7/vllm/worker/cache_engine.py class CacheEngine: """管理 KV cache。 CacheEngine 负责 GPU cache 和 CPU cache 的初始化和管理，同时也提供 KV cache 操作相关的方法 """ def __init__( self, cache_config: CacheConfig, model_config: ModelConfig, parallel_config: ParallelConfig, ) -> None: ... # 初始化 KV cache 空间 self.gpu_cache = self.allocate_gpu_cache() self.cpu_cache = self.allocate_cpu_cache() # 初始化 cuda stream 用于 cache 的相关操作 self.cache_stream = torch.cuda.Stream() assert self.cache_stream != torch.cuda.current_stream() # Initialize the events for stream synchronization. self.events = [torch.cuda.Event() for _ in range(self.num_layers)]
```

Cache 空间的分配包括对显存以及内存空间的分配，分别调用 CacheEngine 的`allocate_gpu_cache`方法和 `allocate_cpu_cache`方法完成分配。

```python3
# https://github.com/vllm-project/vllm/blob/v0.2.7/vllm/worker/cache_engine.py class CacheEngine: def allocate_gpu_cache(self) -> List[KVCache]: gpu_cache: List[KVCache] = [] key_block_shape = self.get_key_block_shape() value_block_shape = self.get_value_block_shape() for _ in range(self.num_layers): key_blocks = torch.empty( size=(self.num_gpu_blocks, *key_block_shape), dtype=self.dtype, device="cuda", ) value_blocks = torch.empty( size=(self.num_gpu_blocks, *value_block_shape), dtype=self.dtype, device="cuda", ) gpu_cache.append((key_blocks, value_blocks)) return gpu_cache
```

这里有一个需要注意的点，key 和 value 的 block shape 有区别，具体原因我们在后面的文章再介绍。  
我们以一个例子来结束对 CacheEngine 的介绍。

假设显存可开辟的块数为 4，模型有 4 层，则图 2 为 CacheEngine 初始化后 KV cache 的示意图。

![](https://pic3.zhimg.com/v2-ee775bbe1cbc0532400bced61141053e_1440w.jpg)

图 2：KV cache 示意图

LLMEngine 初始化的最后一步是初始化 Scheduler。

### Scheduler

Scheduler 的初始化包括：

-   实例化 policy 调度策略：目前只支持先进先出（fcfs），即先接收的请求先处理
-   初始化 block\_manager：BlockSpaceManager 实例
-   初始化 3 个队列

-   waiting：处于等待状态的请求，存放还未被处理的请求
-   running：处于运行状态的请求，已经被处理过或正在处理的请求
-   swapped：处于被换出状态的请求，这些请求的 KV cache 存放在 CPU 上

Scheduler 的初始化实现如下：

```python3
# https://github.com/vllm-project/vllm/blob/v0.2.7/vllm/core/scheduler.py class Scheduler: def __init__( self, scheduler_config: SchedulerConfig, cache_config: CacheConfig, ) -> None: self.scheduler_config = scheduler_config self.cache_config = cache_config self.prompt_limit = min(self.scheduler_config.max_model_len, self.scheduler_config.max_num_batched_tokens) # 初始化调度策略，暂时只支持先入先出，请先到的请求会先被处理 self.policy = PolicyFactory.get_policy(policy_name="fcfs") # 初始化 BlockSpaceManager self.block_manager = BlockSpaceManager( block_size=self.cache_config.block_size, num_gpu_blocks=self.cache_config.num_gpu_blocks, num_cpu_blocks=self.cache_config.num_cpu_blocks, sliding_window=self.cache_config.sliding_window) # 处于等待（未被处理）状态的请求 self.waiting: Deque[SequenceGroup] = deque() # 处于运行状态的请求 self.running: Deque[SequenceGroup] = deque() # 处于被换出状态的请求 self.swapped: Deque[SequenceGroup] = deque()
```

对于 policy 的实例化就不做太多介绍了，主要介绍 BlockSpaceManager。

  
BlockSpaceManager 用于管理 logical token block 和 physical token block 之间的[映射关系](https://zhida.zhihu.com/search?content_id=241953278&content_type=Article&match_order=1&q=%E6%98%A0%E5%B0%84%E5%85%B3%E7%B3%BB&zhida_source=entity)，而前面提到的 CacheEngine 是用于 KV cache 的初始化和管理（真正开辟显存空间和内存空间），它们的关系如图 3 所示：

![](https://picx.zhimg.com/v2-b4faf833ce5d56b345958cbd6baccb99_1440w.jpg)

图 3

-   physical token block 可以理解为 KV cache block 的状态表示，它们之间是一一对应的关系，在为请求分配 block 时实际上分配的是 physical token block，但真正进行计算（推理）时操作的是 KV cache block
-   logical token block 是 physical token block 逻辑层面的表示，当请求需要占用 x 个 logical token block 时，当请求被调度时也会为请求分配 x 个 physical token block。注意：当请求到达 LLMEngine 时就会分配 logical token block，只有当请求被调度时才会分配 physical token block

BlockSpaceManager 主要有 4 个属性：

-   watermark\_blocks：用于避免频繁换出操作，解释见 [https://github.com/vllm-project/vllm/pull/11](https://link.zhihu.com/?target=https%3A//github.com/vllm-project/vllm/pull/11)
-   gpu\_allocator：BlockAllocator 实例，用于管理空闲的 physical token block
-   cpu\_allocator：同 gpu\_allocator，只不过 device 是 CPU
-   block\_tables：维护请求 id 到 physical token block 的映射

BlockSpaceManager 的初始化逻辑如下：

```python3
# https://github.com/vllm-project/vllm/blob/v0.2.7/vllm/core/block_manager.py class BlockSpaceManager: """Manages the mapping between logical and physical token blocks.""" def __init__( self, block_size: int, num_gpu_blocks: int, num_cpu_blocks: int, watermark: float = 0.01, sliding_window: Optional[int] = None, ) -> None: ... self.watermark_blocks = int(watermark * num_gpu_blocks) self.gpu_allocator = BlockAllocator(Device.GPU, block_size, num_gpu_blocks) self.cpu_allocator = BlockAllocator(Device.CPU, block_size, num_cpu_blocks) # Mapping: seq_id -> BlockTable. self.block_tables: Dict[int, BlockTable] = {}
```

这里只介绍 gpu\_allocator，它是 BlockAllocator 实例，用于管理空闲的 physical token block，它的实现如下：

```python3
# https://github.com/vllm-project/vllm/blob/v0.2.7/vllm/core/block_manager.py class BlockAllocator: """Manages free physical token blocks for a device. The allocator maintains a list of free blocks and allocates a block when requested. When a block is freed, its reference count is decremented. If the reference count becomes zero, the block is added back to the free list. """ def __init__( self, device: Device, block_size: int, num_blocks: int, ) -> None: ... # Initialize the free blocks. self.free_blocks: BlockTable = [] for i in range(num_blocks): block = PhysicalTokenBlock(device=device, block_number=i, block_size=block_size) self.free_blocks.append(block) # https://github.com/vllm-project/vllm/blob/v0.2.7/vllm/block.py class PhysicalTokenBlock: """Represents the state of a block in the KV cache.""" def __init__( self, device: Device, block_number: int, block_size: int, ) -> None: self.device = device self.block_number = block_number self.block_size = block_size self.ref_count = 0 def __repr__(self) -> str: return (f'PhysicalTokenBlock(device={self.device}, ' f'block_number={self.block_number}, ' f'ref_count={self.ref_count})')
```

以上就是 vLLM 核心组件的初始化细节，最后以一张时序图总结 vLLM 的初始化流程：

![](https://pic4.zhimg.com/v2-ad6028803e724e6a1140124cdd46968d_1440w.jpg)

图 4：初始化时序图

下一篇文章介绍当一个请求到来时，Scheduler 是如何调度的。

欢迎关注。

---

> **vLLM（知乎）系列导航**：[[vLLM 系列（知乎）索引|系列索引]] ｜ 上一篇：[[vLLM（三）源码安装与调试 - 知乎|三：源码安装与调试]] ｜ 下一篇：[[vLLM（五）调度器的细节 - 知乎|五：调度器的细节]]

