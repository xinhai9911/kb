---
title: "vLLM（五）调度器的细节"
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
part: "五"
---
> [Efficient Memory Management for Large Language Model Serving with PagedAttention](https://link.zhihu.com/?target=https%3A//arxiv.org/pdf/2309.06180.pdf)  
> [https://github.com/vllm-project/vllm](https://link.zhihu.com/?target=https%3A//github.com/vllm-project/vllm)  
> [https://github.com/vllm-project/vllm/issues/2492](https://link.zhihu.com/?target=https%3A//github.com/vllm-project/vllm/issues/2492)  
> [https://docs.google.com/presentation](https://link.zhihu.com/?target=https%3A//docs.google.com/presentation/d/1QL-XPFXiFpDBh86DbEegFXBXFXjix4v032GhShbKf3s/edit%23slide%3Did.p)  
> [Fast LLM Serving with vLLM and PagedAttention\_哔哩哔哩\_bilibili](https://link.zhihu.com/?target=https%3A//www.bilibili.com/video/BV1eF4m1N7rL/%3Fshare_source%3Dcopy_web%26vd_source%3Daac509da00df68a65bd1548362420c8d)

本系列将介绍 vLLM 的方方面面：

___

在 [SayHelloCode：vLLM（四）核心组件的初始化](https://zhuanlan.zhihu.com/p/692202970)这篇文章中，我们介绍了 vLLM 的初始化操作。在本篇文章，我们将会一起看看 Scheduler 是如何调度请求的。

## 回顾

我们先回顾一下 LLM 的 generate 接口做了哪些事情：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/entrypoints/llm.py class LLM: def generate( self, prompts: Optional[Union[str, List[str]]] = None, sampling_params: Optional[SamplingParams] = None, prompt_token_ids: Optional[List[List[int]]] = None, use_tqdm: bool = True, ) -> List[RequestOutput]: """Generates the completions for the input prompts. NOTE: This class automatically batches the given prompts, considering the memory constraint. For the best performance, put all of your prompts into a single list and pass it to this method. """ ... for i in range(num_requests): prompt = prompts[i] if prompts is not None else None token_ids = None if prompt_token_ids is None else prompt_token_ids[ i] self._add_request(prompt, sampling_params, token_ids) return self._run_engine(use_tqdm)
```

-   不断调用`_add_request`完成请求的预处理
-   调用`_run_engine`完成请求的处理

## 预处理

我们首先来看看 LLM 的`_add_request`方法，它调用了 LLMEngine 的`add_request`方法来完成请求的预处理：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/entrypoints/llm.py class LLM: def _add_request( self, prompt: Optional[str], sampling_params: SamplingParams, prompt_token_ids: Optional[List[int]], ) -> None: request_id = str(next(self.request_counter)) self.llm_engine.add_request(request_id, prompt, sampling_params, prompt_token_ids)
```

在这里会生成一个 request id，用于唯一标识一个请求，LLMEngine 的 scheduler 会根据 request id 来完成先进先出的调度（fcfs）。  
LLMEngine 的`add_request`方法如下：

```python3
# https://github.com/vllm-project/vllm/blob/v0.2.7/vllm/engine/llm_engine.py class LLMEngine: def add_request( self, request_id: str, prompt: Optional[str], sampling_params: SamplingParams, prompt_token_ids: Optional[List[int]] = None, arrival_time: Optional[float] = None, ) -> None: """Add a request to the engine's request pool. The request is added to the request pool and will be processed by the scheduler as `engine.step()` is called. The exact scheduling policy is determined by the scheduler. """ if arrival_time is None: arrival_time = time.monotonic() if prompt_token_ids is None: assert prompt is not None prompt_token_ids = self.tokenizer.encode(prompt) # 创建 sequence 对象 block_size = self.cache_config.block_size seq_id = next(self.seq_counter) seq = Sequence(seq_id, prompt, prompt_token_ids, block_size) # 创建 sequence 组，用于管理来自同一请求的多个生成结果（例如 beam search） seq_group = SequenceGroup(request_id, [seq], sampling_params, arrival_time) # 将 sequence 组添加到 scheduler 的 waiting 队列 self.scheduler.add_seq_group(seq_group)
```

在 add\_request 方法里，首先 tokenize prompt，然后将 prompt 封装成 Sequence 对象，再将 Sequence 对象封装成 SequenceGroup 并添加到 scheduler 的 waiting 队列。  
Sequence 存储着数据（token ids）、状态（status）、logical token block 等信息，SequenceGroup 则是来自于同一请求的一组 Sequence，例如使用 beam search 策略解码时，需将多个输出存储在 SequenceGroup 中。  
以 prompt="Hello, my name is" 为例，经过 add\_request 方法，它最终会被封装成 SequenceGroup，如图 1 所示：

![](https://pic3.zhimg.com/v2-1a5b1b0118ae6f050ebdfa8cac8aadfe_1440w.jpg)

图 1

它们之间的关系如图 2 所示：

![](https://pica.zhimg.com/v2-c0494168ed54bb433b3dea1ca74ea928_1440w.jpg)

图 2

Sequence 的初始化方法如下：

```python3
# https://github.com/vllm-project/vllm/blob/v0.2.7/vllm/sequence.py class Sequence: """Stores the data, status, and block information of a sequence. Args: seq_id: The ID of the sequence. prompt: The prompt of the sequence. prompt_token_ids: The token IDs of the prompt. block_size: The block size of the sequence. Should be the same as the block size used by the block manager and cache engine. """ def __init__( self, seq_id: int, prompt: str, prompt_token_ids: List[int], block_size: int, ) -> None: ... self.data = SequenceData(prompt_token_ids) self.logical_token_blocks: List[LogicalTokenBlock] = [] # 使用 prompt token id 初始化 logical token block self._append_tokens_to_blocks(prompt_token_ids) self.status = SequenceStatus.WAITING
```

在这里会调用`_append_tokens_to_blocks`初始化 logical token blocks。Sequence 实例化后的示意图如图 3 所示：

![](https://pic1.zhimg.com/v2-20338ae2767a6c7e23ac81b587824a1a_1440w.jpg)

图 3：Sequence 实例

完成 Sequence 的[实例化](https://zhida.zhihu.com/search?content_id=241969629&content_type=Article&match_order=2&q=%E5%AE%9E%E4%BE%8B%E5%8C%96&zhida_source=entity)后，就将其封装成 SequenceGroup。  
SequenceGroup 的定义如下：

```python3
# https://github.com/vllm-project/vllm/blob/v0.2.7/vllm/sequence.py class SequenceGroup: """A group of sequences that are generated from the same prompt. Args: request_id: The ID of the request. seqs: The list of sequences. sampling_params: The sampling parameters used to generate the outputs. arrival_time: The arrival time of the request. """ def __init__( self, request_id: str, seqs: List[Sequence], sampling_params: SamplingParams, arrival_time: float, ) -> None: self.request_id = request_id self.seqs_dict = {seq.seq_id: seq for seq in seqs} self.sampling_params = sampling_params self.arrival_time = arrival_time self.prompt_logprobs: Optional[PromptLogprobs] = None
```

SequenceGroup 实例化后的示意图如图 4 所示：

![](https://pic3.zhimg.com/v2-1a5b1b0118ae6f050ebdfa8cac8aadfe_1440w.jpg)

图 4：SequenceGroup 实例

## 调度

完成请求的预处理后，LLM 调用`_run_engine`完成请求的处理。

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/entrypoints/llm.py class LLM: def _run_engine(self, use_tqdm: bool) -> List[RequestOutput]: ... # Run the engine. outputs: List[RequestOutput] = [] while self.llm_engine.has_unfinished_requests(): step_outputs = self.llm_engine.step() for output in step_outputs: if output.finished: outputs.append(output) if use_tqdm: pbar.update(1) ... # Sort the outputs by request ID. # This is necessary because some requests may be finished earlier than # its previous requests. outputs = sorted(outputs, key=lambda x: int(x.request_id)) return outputs
```

`_run_engine`主要调用 LLMEngine 的 step 方法完成请求的处理。  
LLMEngine step 方法的 docstring 对其职责做了概括：

> This function performs one decoding iteration of the engine. It first schedules the sequences to be executed in the next iteration and the token blocks to be swapped in/out/copy. Then, it executes the model and updates the scheduler with the model outputs. Finally, it decodes the sequences and returns the newly generated results.

它的逻辑如下：

-   调用 scheduler 的`schedule`方法选择要处理的 sequence group 列表（本篇文章只介绍这部分）
-   调用 worker 的`execute_model`方法推理 sequence group（待下篇文章介绍）
-   调用`_process_model_outputs`方法完成模型输出的[后处理](https://zhida.zhihu.com/search?content_id=241969629&content_type=Article&match_order=1&q=%E5%90%8E%E5%A4%84%E7%90%86&zhida_source=entity)（待下篇文章介绍）

它的实现如下：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/engine/llm_engine.py class LLMEngine: def step(self) -> List[RequestOutput]: """Performs one decoding iteration and returns newly generated results. This function performs one decoding iteration of the engine. It first schedules the sequences to be executed in the next iteration and the token blocks to be swapped in/out/copy. Then, it executes the model and updates the scheduler with the model outputs. Finally, it decodes the sequences and returns the newly generated results. """ seq_group_metadata_list, scheduler_outputs = self.scheduler.schedule() if not scheduler_outputs.is_empty(): # 执行 worker 的 execute_model 方法进行推理 all_outputs = self._run_workers( "execute_model", driver_kwargs={ "seq_group_metadata_list": seq_group_metadata_list, # 哪些块要从 CPU 换入到 GPU "blocks_to_swap_in": scheduler_outputs.blocks_to_swap_in, # 哪些块要从 GPU 换到 CPU "blocks_to_swap_out": scheduler_outputs.blocks_to_swap_out, # 哪些块要进行拷贝 "blocks_to_copy": scheduler_outputs.blocks_to_copy, }) # 只有 driver worker 才需要返回结果 output = all_outputs[0] else: output = [] return self._process_model_outputs(output, scheduler_outputs)
```

我们先来看一下 scheduler 的 schedule 方法做了哪些事情。

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/core/scheduler.py class Scheduler: def schedule(self) -> Tuple[List[SequenceGroupMetadata], SchedulerOutputs]: # 选择要进行处理的 sequence group # 此方法会改变 self.running, self.swapped, self.waiting 队列的状态， # 即队列里的元素会发生增减 scheduler_outputs = self._schedule() # 创建用于模型推理的输入 seq_group_metadata_list seq_group_metadata_list: List[SequenceGroupMetadata] = [] for seq_group in scheduler_outputs.scheduled_seq_groups: seq_data: Dict[int, SequenceData] = {} block_tables: Dict[int, List[int]] = {} for seq in seq_group.get_seqs(status=SequenceStatus.RUNNING): seq_id = seq.seq_id seq_data[seq_id] = seq.data block_tables[seq_id] = self.block_manager.get_block_table(seq) seq_group_metadata = SequenceGroupMetadata( request_id=seq_group.request_id, is_prompt=scheduler_outputs.prompt_run, seq_data=seq_data, sampling_params=seq_group.sampling_params, block_tables=block_tables, ) seq_group_metadata_list.append(seq_group_metadata) return seq_group_metadata_list, scheduler_outputs
```

schedule 方法的处理步骤如下：

-   调用`_schedule`方法：在`_schedule`方法中决定哪些 sequence group 会被调度以及 block 要被交换（从 GPU 换出到 CPU，或 CPU 换入到 GPU）或拷贝。
-   基于`_schedule`返回的 scheduler\_outputs 创建 worker 的 execute\_model 方法所需的数据

来到`_schedule`方法，请求调度的具体实现在这个方法中。同样，我们先概述`_schedule`的处理逻辑。

-   如果 scheduler 的 swapped 队列为空，则从 waiting 队列选择满足条件的 sequence group 加入到 running 队列，可以看出，**swapped 队列的优先级高于 waiting 队列，因为只有 swapped 为空的情况下，才有可能调度 waiting 队列的 sequence group**
-   如果 scheduler 的 swapped 队列不为空，或者 swapped 为空但 waiting 队列为空（也有可能 waiting 不为空，但没有空闲的 block 可分配），则会从 running 队列或 swapped 队列选择 sequence group

图 5 是 waiting、running 和 swapped 三个队列之间的转换关系。

![](https://pic2.zhimg.com/v2-0bff7b2ce98d02601b3d176f8729a5a3_1440w.jpg)

图 5：waiting、running 和 swapped 三个队列之间的转换关系

我们先来看看 scheduler 的 swapped 队列为空的情况。

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/core/scheduler.py class Scheduler: def _schedule(self) -> SchedulerOutputs: ... # 如果 swapped 为空，则尽可能地从 waiting 队列选择 sequence group # 加入到 running 队列，而这些被选择的 sequence group 会进行填充阶段的计算 if not self.swapped: ignored_seq_groups: List[SequenceGroup] = [] # scheduled 里的 sequence group 会进行填充阶段的计算 scheduled: List[SequenceGroup] = [] # The total number of sequences on the fly, including the # requests in the generation phase. num_curr_seqs = sum(seq_group.get_max_num_running_seqs() for seq_group in self.running) seq_lens: List[int] = [] while self.waiting: # 取 waiting 队列的第一个 sequence group seq_group = self.waiting[0] waiting_seqs = seq_group.get_seqs( status=SequenceStatus.WAITING) assert len(waiting_seqs) == 1, ( "Waiting sequence group should have only one prompt " "sequence.") num_prompt_tokens = waiting_seqs[0].get_len() # 判断 prompt 的 token 数是否大于限制 if num_prompt_tokens > self.prompt_limit: logger.warning( f"Input prompt ({num_prompt_tokens} tokens) is too long" f" and exceeds limit of {self.prompt_limit}") for seq in waiting_seqs: seq.status = SequenceStatus.FINISHED_IGNORED ignored_seq_groups.append(seq_group) self.waiting.pop(0) continue # 判断是否还有空闲的 block 分配给当前 sequence group can_allocate = self.block_manager.can_allocate(seq_group) if can_allocate == AllocStatus.LATER: break elif can_allocate == AllocStatus.NEVER: logger.warning( f"Input prompt ({num_prompt_tokens} tokens) is too long" f" and exceeds the capacity of block_manager") for seq in waiting_seqs: seq.status = SequenceStatus.FINISHED_IGNORED ignored_seq_groups.append(seq_group) self.waiting.pop(0) continue # 被选中的所有 sequence group 的总 token 是否超过 max_num_batched_tokens new_seq_lens = seq_lens + [num_prompt_tokens] num_batched_tokens = len(new_seq_lens) * max(new_seq_lens) if (num_batched_tokens > self.scheduler_config.max_num_batched_tokens): break # 当前要处理的 sequence 是否大于最大能处理的 sequence num_new_seqs = seq_group.get_max_num_running_seqs() if (num_curr_seqs + num_new_seqs > self.scheduler_config.max_num_seqs): break # padding 的数量是否超过了限定的 max_paddings num_paddings = num_batched_tokens - sum(new_seq_lens) if num_paddings > self.scheduler_config.max_paddings: break seq_lens = new_seq_lens # 弹出当前的 sequence group seq_group = self.waiting.pop(0) # 为当前 sequence group 分配 physical token blocks self._allocate(seq_group) # 将当前的 sequence group 添加到 running 队列 self.running.append(seq_group) num_curr_seqs += num_new_seqs # 将当前的 sequence group 添加到要进行填充阶段计算的列表 scheduled.append(seq_group) # 将被调度的 sequence group 封装成 SchedulerOutputs # 如果 scheduled 或 ignored_seq_groups 都为空，则会走 # swapped 不为空的逻辑 if scheduled or ignored_seq_groups: scheduler_outputs = SchedulerOutputs( scheduled_seq_groups=scheduled, prompt_run=True, num_batched_tokens=len(seq_lens) * max(seq_lens) if seq_lens else 0, blocks_to_swap_in=blocks_to_swap_in, blocks_to_swap_out=blocks_to_swap_out, blocks_to_copy=blocks_to_copy, ignored_seq_groups=ignored_seq_groups, ) return scheduler_outputs ... return scheduler_outputs
```

上面的注释分析了当 swapped 队列为空时，waiting 队列的 sequence group 被调度的逻辑，总结如下：

-   \_schedule 方法会从左到右遍历 waiting 队列（先来先处理策略）
-   对于每个 sequence group，调用 block\_manager 的`can_allocate`方法判断是否能给 sequence group 分配 physical token block
-   如果可以分配，则调用 block\_mananger 的`allocate`方法为 sequence group 分配 physical token block

调度流程如图 6 所示：

![](https://pic2.zhimg.com/v2-16e3e6e94a399a0c06c2ab676af58021_1440w.jpg)

图 6：swapped 队列为空

调度过程调用了 block\_manager 的`can_allocate`方法，它的实现如下：

```python3
# vllm/core/block_manager.py class BlockSpaceManager: def can_allocate(self, seq_group: SequenceGroup) -> AllocStatus: # FIXME(woosuk): Here we assume that all sequences in the group share # the same prompt. This may not be true for preempted sequences. seq = seq_group.get_seqs(status=SequenceStatus.WAITING)[0] num_required_blocks = len(seq.logical_token_blocks) ... num_free_gpu_blocks = self.gpu_allocator.get_num_free_blocks() # Use watermark to avoid frequent cache eviction. if (self.num_total_gpu_blocks - num_required_blocks < self.watermark_blocks): # sequence 要求分配的块数大于开辟的显存块数， # 这个 sequence 永远不会被处理，所以返回 NEVER return AllocStatus.NEVER if num_free_gpu_blocks - num_required_blocks >= self.watermark_blocks: # sequence 要求分配的块数可以被满足 return AllocStatus.OK else: # sequence 要求分配的块数暂时不能被满足 return AllocStatus.LATER
```

调用 scheduler 的`_allocate` 进而调用 block\_manager 的`allocate`方法为 sequence group 分配 PhysicalTokenBlock：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/core/scheduler.py class Scheduler: def _schedule(self) -> SchedulerOutputs: ... if not self.swapped: ... while self.waiting: ... seq_group = self.waiting.pop(0) self._allocate(seq_group) self.running.append(seq_group) num_curr_seqs += num_new_seqs scheduled.append(seq_group) ... ... return scheduler_outputs def _allocate(self, seq_group: SequenceGroup) -> None: # 调用 block manager 的 allocate 方法分配 physical token block self.block_manager.allocate(seq_group) # 将 sequence 的状态设置为 RUNNING，即将要被处理 for seq in seq_group.get_seqs(status=SequenceStatus.WAITING): seq.status = SequenceStatus.RUNNING # https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/core/block_manager.py class BlockSpaceManager: def allocate(self, seq_group: SequenceGroup) -> None: # NOTE: Here we assume that all sequences in the group have the same # prompt. seq = seq_group.get_seqs(status=SequenceStatus.WAITING)[0] # 为请求的 prompt token 分配 physical token block block_table: BlockTable = [] for logical_idx in range(len(seq.logical_token_blocks)): if (self.block_sliding_window is not None and logical_idx >= self.block_sliding_window): block = block_table[logical_idx % self.block_sliding_window] else: block = self.gpu_allocator.allocate() # 设置 block 的引用数，copy on write 机制会用到 block.ref_count = seq_group.num_seqs() block_table.append(block) # Assign the block table for each sequence. for seq in seq_group.get_seqs(status=SequenceStatus.WAITING): self.block_tables[seq.seq_id] = block_table.copy()
```

完成 waiting 队列的遍历后，会将待处理的 sequence group 封装成 SchedulerOutputs 返回，如图 7 所示：

![](https://pic1.zhimg.com/v2-44f38e1d8ca6012e1c27a7db155abcea_1440w.jpg)

图 7：SchedulerOutputs 示意图

前面介绍了 swapped 队列为空的情况，下面继续介绍 swapped 队列不为空或者 swapped 队列为空但 waiting 队列为空（也有可能 waiting 队列不为空，但没有空闲的 block 可分配）。

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/core/scheduler.py class Scheduler: def _schedule(self) -> SchedulerOutputs: if not self.swapped: ... self.running = self.policy.sort_by_priority(now, self.running) # Reserve new token slots for the running sequence groups. running: List[SequenceGroup] = [] # 被抢占的 sequence group，即它的 GPU KV cache 要被释放 preempted: List[SequenceGroup] = [] while self.running: seq_group = self.running.pop(0) # 当没有空闲的 block 可分配给当前 sequence group 时，会发生抢占 while not self.block_manager.can_append_slot(seq_group): # 如果 running 还有其他 sequence group，抢占优先级最低的 sequence group if self.running: # 抢占优先级最低的 sequence group victim_seq_group = self.running.pop(-1) # 发生抢占，后面会介绍这个方法 self._preempt(victim_seq_group, blocks_to_swap_out) preempted.append(victim_seq_group) # 否则抢占当前的 sequence group else: self._preempt(seq_group, blocks_to_swap_out) preempted.append(seq_group) break else: # 为 sequence group 的每个 sequence 添加 slot，注意，这里是添加 slot，而不是 block， # 因为有可能 sequence 的 physical token block 还有空闲的 slot，这种情况就无需 # 分配新的 physical token block self._append_slot(seq_group, blocks_to_copy) running.append(seq_group) self.running = running self.swapped = self.policy.sort_by_priority(now, self.swapped) # 如果没有发生抢占，则表示可能还有空闲的 block，所以尝试将 swapped 队列 # 的 sequence group 重新添加到 running 队列 if not preempted: num_curr_seqs = sum(seq_group.get_max_num_running_seqs() for seq_group in self.running) while self.swapped: seq_group = self.swapped[0] # 判断 sequence group 是否能被换入 # 后面会介绍这个方法 if not self.block_manager.can_swap_in(seq_group): break # 判断总的 sequence 数量是否大于限定的 max_num_seqs num_new_seqs = seq_group.get_max_num_running_seqs() if (num_curr_seqs + num_new_seqs > self.scheduler_config.max_num_seqs): break # 将 block 从 cpu 换入到 gpu # 注意：只是 physical token block 的换入，真正显存里的内容还没发生变化 seq_group = self.swapped.pop(0) self._swap_in(seq_group, blocks_to_swap_in) self._append_slot(seq_group, blocks_to_copy) num_curr_seqs += num_new_seqs self.running.append(seq_group) # Each sequence in the generation phase only takes one token slot. # Therefore, the number of batched tokens is equal to the number of # sequences in the RUNNING state. num_batched_tokens = sum( seq_group.num_seqs(status=SequenceStatus.RUNNING) for seq_group in self.running) scheduler_outputs = SchedulerOutputs( scheduled_seq_groups=self.running, prompt_run=False, num_batched_tokens=num_batched_tokens, blocks_to_swap_in=blocks_to_swap_in, blocks_to_swap_out=blocks_to_swap_out, blocks_to_copy=blocks_to_copy, ignored_seq_groups=[], ) return scheduler_outputs
```

上述调度过程的流程图如图 8 所示：

![](https://pic4.zhimg.com/v2-c58d5127522e2718277762b20da7ab95_1440w.jpg)

图 8

我们再回过头来看看前面提到但没有介绍的方法：

-   block\_manager 的 `can_append_slot`方法：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/core/block_manager.py class BlockSpaceManager: """Manages the mapping between logical and physical token blocks.""" def can_append_slot(self, seq_group: SequenceGroup) -> bool: # 简单的判断方法：判断当前 sequence group 处于 running 状态的 sequence 的数量是否 # 小于等于空闲的 gpu block 数 num_free_gpu_blocks = self.gpu_allocator.get_num_free_blocks() num_seqs = seq_group.num_seqs(status=SequenceStatus.RUNNING) return num_seqs <= num_free_gpu_blocks
```

-   scheduler 的`_preempt`方法：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/core/scheduler.py class Scheduler: def _preempt( self, seq_group: SequenceGroup, blocks_to_swap_out: Dict[int, int], preemption_mode: Optional[PreemptionMode] = None, ) -> None: # If preemption mode is not specified, we determine the mode as follows: # We use recomputation by default since it incurs lower overhead than # swapping. However, when the sequence group has multiple sequences # (e.g., beam search), recomputation is not currently supported. In # such a case, we use swapping instead. # FIXME(woosuk): This makes our scheduling policy a bit bizarre. # As swapped sequences are prioritized over waiting sequences, # sequence groups with multiple sequences are implicitly prioritized # over sequence groups with a single sequence. # TODO(woosuk): Support recomputation for sequence groups with multiple # sequences. This may require a more sophisticated CUDA kernel. if preemption_mode is None: if seq_group.get_max_num_running_seqs() == 1: preemption_mode = PreemptionMode.RECOMPUTE else: preemption_mode = PreemptionMode.SWAP if preemption_mode == PreemptionMode.RECOMPUTE: self._preempt_by_recompute(seq_group) elif preemption_mode == PreemptionMode.SWAP: self._preempt_by_swap(seq_group, blocks_to_swap_out) else: raise AssertionError("Invalid preemption mode.")
```

-   scheduler 的`_append_slot`方法：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/core/scheduler.py class Scheduler: def _append_slot( self, seq_group: SequenceGroup, blocks_to_copy: Dict[int, List[int]], ) -> None: for seq in seq_group.get_seqs(status=SequenceStatus.RUNNING): ret = self.block_manager.append_slot(seq) if ret is not None: # copy on write 机制 src_block, dst_block = ret if src_block in blocks_to_copy: blocks_to_copy[src_block].append(dst_block) else: blocks_to_copy[src_block] = [dst_block] # https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/core/block_manager.py class BlockSpaceManager: def append_slot(self, seq: Sequence) -> Optional[Tuple[int, int]]: """Allocate a physical slot for a new token.""" logical_blocks = seq.logical_token_blocks block_table = self.block_tables[seq.seq_id] if len(block_table) < len(logical_blocks): if (self.block_sliding_window and len(block_table) >= self.block_sliding_window): # re-use a block block_table.append(block_table[len(block_table) % self.block_sliding_window]) else: # sequence 有新的 logical token block # 所以这里也要分配一个新的 physical token block block = self.gpu_allocator.allocate() block_table.append(block) return None # We want to append the token to the last physical block. last_block = block_table[-1] assert last_block.device == Device.GPU if last_block.ref_count == 1: # Not shared with other sequences. Appendable. return None else: # The last block is shared with other sequences. # Copy on Write: Allocate a new block and copy the tokens. new_block = self.gpu_allocator.allocate() block_table[-1] = new_block self.gpu_allocator.free(last_block) return last_block.block_number, new_block.block_number
```

-   block\_manager 的`can_swap_in`方法

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/core/block_manager.py class BlockSpaceManager: """Manages the mapping between logical and physical token blocks.""" def can_swap_in(self, seq_group: SequenceGroup) -> bool: blocks = self._get_physical_blocks(seq_group) num_swapped_seqs = seq_group.num_seqs(status=SequenceStatus.SWAPPED) num_free_blocks = self.gpu_allocator.get_num_free_blocks() # NOTE: Conservatively, we assume that every sequence will allocate # at least one free block right after the swap-in. # NOTE: This should match the logic in can_append_slot(). num_required_blocks = len(blocks) + num_swapped_seqs return num_free_blocks - num_required_blocks >= self.watermark_blocks
```

`_schedule`方法介绍得差不多了，我们最后回到`schedule`方法：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/core/scheduler.py class Scheduler: def schedule(self) -> Tuple[List[SequenceGroupMetadata], SchedulerOutputs]: # 选择要进行处理的 sequence group # 此方法会改变 self.running, self.swapped, self.waiting 队列的状态， # 即队列里的元素会发生增减 scheduler_outputs = self._schedule() # 创建用于模型推理的输入 seq_group_metadata_list seq_group_metadata_list: List[SequenceGroupMetadata] = [] for seq_group in scheduler_outputs.scheduled_seq_groups: seq_data: Dict[int, SequenceData] = {} block_tables: Dict[int, List[int]] = {} for seq in seq_group.get_seqs(status=SequenceStatus.RUNNING): seq_id = seq.seq_id seq_data[seq_id] = seq.data block_tables[seq_id] = self.block_manager.get_block_table(seq) seq_group_metadata = SequenceGroupMetadata( request_id=seq_group.request_id, is_prompt=scheduler_outputs.prompt_run, seq_data=seq_data, sampling_params=seq_group.sampling_params, block_tables=block_tables, ) seq_group_metadata_list.append(seq_group_metadata) return seq_group_metadata_list, scheduler_outputs
```

在 `schedule` 方法中，进一步将`scheduler_outputs`封装成`SequenceGroupMetadata`，如图 9 所示：

![](https://pic4.zhimg.com/v2-3ddcda64c0a89514bf7e3278f069966f_1440w.jpg)

图 9：SequenceGroupMetadata 示意图

最终，scheduler 的`schedule`方法返回`seq_group_metadata_list`和`scheduler_outputs`，其中，`seq_group_metadata_list`会在后续传给 worker 的`execute_model`方法。  
至此，请求的调度已经完成，接下来将进行请求的推理，这一部分会在下一篇文章介绍。  
文章的最后，附上调度的完整流程图：

![](https://pica.zhimg.com/v2-ae65628ccd7a4c6eb0a5539711004c72_1440w.jpg)

图 10：完整流程图

---

> **vLLM（知乎）系列导航**：[[vLLM 系列（知乎）索引|系列索引]] ｜ 上一篇：[[vLLM（四）核心组件的初始化 - 知乎|四：核心组件的初始化]] ｜ 下一篇：[[vLLM（六）模型的推理细节 - 知乎|六：模型的推理细节]]

