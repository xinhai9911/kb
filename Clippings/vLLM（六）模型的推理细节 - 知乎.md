---
title: "vLLM（六）模型的推理细节"
source: "https://zhuanlan.zhihu.com/p/715131885"
author: "知乎·vLLM 源码解读系列"
published:
created: 2026-08-19
description: "本系列将介绍 vLLM 的方方面面："
tags:
  - "clippings"
  - "vLLM"
  - "知乎"
series: "vLLM（知乎）"
part: "六"
---
> [Efficient Memory Management for Large Language Model Serving with PagedAttention](https://link.zhihu.com/?target=https%3A//arxiv.org/pdf/2309.06180.pdf)  
> [https://github.com/vllm-project/vllm](https://link.zhihu.com/?target=https%3A//github.com/vllm-project/vllm)  
> [https://github.com/vllm-project/vllm/issues/2492](https://link.zhihu.com/?target=https%3A//github.com/vllm-project/vllm/issues/2492)  
> [https://docs.google.com/presentation](https://link.zhihu.com/?target=https%3A//docs.google.com/presentation/d/1QL-XPFXiFpDBh86DbEegFXBXFXjix4v032GhShbKf3s/edit%23slide%3Did.p)  
> [Fast LLM Serving with vLLM and PagedAttention\_哔哩哔哩\_bilibili](https://link.zhihu.com/?target=https%3A//www.bilibili.com/video/BV1eF4m1N7rL/%3Fshare_source%3Dcopy_web%26vd_source%3Daac509da00df68a65bd1548362420c8d)

本系列将介绍 vLLM 的方方面面：

___

本文的解读会沿用前面文章的示例：

```python3
from vllm import LLM, SamplingParams prompts = [ "Hello, my name is", "The future of AI is", ] sampling_params = SamplingParams(temperature=0.8, top_p=0.95) # enforce_eager 用于是否开启 CUDA GRAPH 优化，详细见 # https://github.com/vllm-# project/vllm/pull/1926 # 这里设置 enforce_eager=True 的原因是可以调试生成阶段的模型推理过程，否则 # 会使用 CUDA GRAPH 优化模型的推理，就不能一步一步调试了。 # 如果暂时不理解 enforce_eager=True 的作用，可以先不设置这个参数 llm = LLM(model="meta-llama/Llama-2-7b-chat-hf", enforce_eager=True) outputs = llm.generate(prompts, sampling_params) # Print the outputs. for output in outputs: prompt = output.prompt generated_text = output.outputs[0].text print(f"Prompt: {prompt!r}, Generated text: {generated_text!r}")
```

## 回顾

在[SayHelloCode：vLLM（五）调度器的细节](http://zhuanlan.zhihu.com/p/692276562)，我们介绍了请求的调度，在本篇文章，我们将介绍请求的推理以及后处理。  
在介绍请求的推理前，我们再来回顾一下 LLMEngine 的`step`方法：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/engine/llm_engine.py class LLMEngine: def step(self) -> List[RequestOutput]: seq_group_metadata_list, scheduler_outputs = self.scheduler.schedule() if not scheduler_outputs.is_empty(): # 执行 worker 的 execute_model 方法进行推理 all_outputs = self._run_workers( "execute_model", driver_kwargs={ "seq_group_metadata_list": seq_group_metadata_list, # 哪些块要从 CPU 换入到 GPU "blocks_to_swap_in": scheduler_outputs.blocks_to_swap_in, # 哪些块要从 GPU 换到 CPU "blocks_to_swap_out": scheduler_outputs.blocks_to_swap_out, # 哪些块要进行拷贝 "blocks_to_copy": scheduler_outputs.blocks_to_copy, }) # 只有 driver worker 才需要返回结果 output = all_outputs[0] else: output = [] return self._process_model_outputs(output, scheduler_outputs)
```

它的逻辑如下：

-   调用 scheduler 的`schedule`方法选择要处理的 sequence group 列表（上篇文章已经介绍了）
-   调用 worker 的`execute_model`方法推理 sequence group（本篇文章介绍）
-   调用`_process_model_outputs`方法完成模型输出的后处理（本篇文章介绍）

第一部分的逻辑在上篇文章已经介绍过了，本篇文章主要介绍请求的推理以及后处理。

## 推理

经过`schedule`方法后，返回的 seq\_group\_metadata\_list 和 scheduler\_outputs 如图 1 所示：

![](https://pic4.zhimg.com/v2-3ddcda64c0a89514bf7e3278f069966f_1440w.jpg)

图 1：SequenceGroupMetadata 和 scheduler\_outputs 示意图

在介绍推理的实现前，我们先给出一张推理的流程图以便在阅读下面的源码有个直观的印象，如图 2 所示：

![](https://pic2.zhimg.com/v2-e000c0c0d24c6de73023fa0f77ba79b3_1440w.jpg)

图 2：推理流程

下面我们正式开始介绍请求的推理过程。请求的推理以调用 worker 的`execute_model`方法作为入口，它的实现如下：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/worker/worker.py class Worker: """A worker class that executes (a partition of) the model on a GPU. Each worker is associated with a single GPU. The worker is responsible for maintaining the KV cache and executing the model on the GPU. In case of distributed inference, each worker is assigned a partition of the model. """ @torch.inference_mode() def execute_model( self, seq_group_metadata_list: Optional[List[SequenceGroupMetadata]] = None, blocks_to_swap_in: Optional[Dict[int, int]] = None, blocks_to_swap_out: Optional[Dict[int, int]] = None, blocks_to_copy: Optional[Dict[int, List[int]]] = None, ) -> Optional[SamplerOutput]: # 状态同步 # 因为只有一个 worker（只用了一张卡），所以这个 worker 就是 driver_worker if self.is_driver_worker: assert seq_group_metadata_list is not None num_seq_groups = len(seq_group_metadata_list) assert blocks_to_swap_in is not None assert blocks_to_swap_out is not None assert blocks_to_copy is not None block_swapping_info = [ blocks_to_swap_in, blocks_to_swap_out, blocks_to_copy ] broadcast_object_list([num_seq_groups] + block_swapping_info, src=0) else: ... # 数据交换 self.cache_swap(*block_swapping_info) # If there is no input, we don't need to execute the model. if num_seq_groups == 0: return {} # 模型推理 output = self.model_runner.execute_model(seq_group_metadata_list, self.gpu_cache) return output
```

`execute_model`的处理逻辑如下：

-   状态同步：调用`broadcast_object_list`函数在多个 worker 间同步 num\_seq\_groups、blocks\_to\_swap\_in、blocks\_to\_swap\_out、blocks\_to\_copy 信息，保证每个 worker 的行为（状态）是一致的
-   数据交换：调用`cache_swap`方法对块执行换入、换出、拷贝操作
-   模型推理：调用 model\_runner 的`execute_model`方法推理请求，这个过程我们称为

状态同步部分只涉及了`broadcast_object_list`函数且这个函数的功能比较直观，就不做过多介绍，下面介绍数据交换部分。

### 数据交换

现在，我们来到了数据交换部分，如图 3 所示：

![](https://pica.zhimg.com/v2-1ad4866d9b0d0d93910ad39f370062bc_1440w.jpg)

图 3：数据交换

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/worker/worker.py class Worker: def cache_swap( self, blocks_to_swap_in: Dict[int, int], blocks_to_swap_out: Dict[int, int], blocks_to_copy: Dict[int, List[int]], ) -> None: # Issue cache operations. issued_cache_op = False if blocks_to_swap_in: self.cache_engine.swap_in(blocks_to_swap_in) issued_cache_op = True if blocks_to_swap_out: self.cache_engine.swap_out(blocks_to_swap_out) issued_cache_op = True if blocks_to_copy: self.cache_engine.copy(blocks_to_copy) issued_cache_op = True cache_events = self.cache_events if issued_cache_op else None # Wait for cache operations to finish. # TODO(woosuk): Profile swapping overhead and optimize if needed. if cache_events is not None: for event in cache_events: event.wait()
```

模型推理前的准备工作已基本完成，就开始进入 model\_runner 的`execute_model`方法。

### 模型推理

![](https://picx.zhimg.com/v2-5ea45912ff2aadd3ec9f64a9b7f9a7a5_1440w.jpg)

图 4：模型推理

模型推理部分会通过 worker 的`execute_model`方法调用 model\_runner 的`execute_model`方法完成请求的推理，它的实现如下：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/worker/model_runner.py class ModelRunner: @torch.inference_mode() def execute_model( self, seq_group_metadata_list: Optional[List[SequenceGroupMetadata]], kv_caches: List[Tuple[torch.Tensor, torch.Tensor]], ) -> Optional[SamplerOutput]: # 准备数据 input_tokens, input_positions, input_metadata, sampling_metadata = ( self.prepare_input_tensors(seq_group_metadata_list)) # 计算 logit if input_metadata.use_cuda_graph: graph_batch_size = input_tokens.shape[0] model_executable = self.graph_runners[graph_batch_size] else: model_executable = self.model hidden_states = model_executable( input_ids=input_tokens, positions=input_positions, kv_caches=kv_caches, input_metadata=input_metadata, ) # 采样 next token output = self.model.sample( hidden_states=hidden_states, sampling_metadata=sampling_metadata, ) return output
```

它的处理逻辑如下：

-   准备数据：调用`prepare_input_tensors`准备模型推理所需的数据
-   计算 logit：调用`model_executable`函数完成 logit 的计算
-   采样 token：调用 model 的`sample`方法决定下一个 token

前面的文章[《vLLM（二）架构概览》](https://zhuanlan.zhihu.com/p/681716326)提到，请求的处理被划分为填充阶段和生成阶段，在接下来的内容中，会反复提及填充阶段（请求第一次被处理）和生成阶段（请求已被处理过多次），如果对这两个阶段有疑惑，可以再看看[《vLLM（二）架构概览》](https://zhuanlan.zhihu.com/p/681716326)里的详细介绍。

**准备数据**

![](https://pic2.zhimg.com/v2-97160ba8aa186accc29b3da4dce10213_1440w.jpg)

图 5：准备数据

我们来看看准备数据阶段需要做哪些事情，下面是`prepare_input_tensors`的实现：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/worker/model_runner.py class ModelRunner: def prepare_input_tensors( self, seq_group_metadata_list: Optional[List[SequenceGroupMetadata]], ) -> Tuple[torch.Tensor, torch.Tensor, InputMetadata, SamplingMetadata]: if self.is_driver_worker: # 假定 group 中的所有 sequence 要么都处于填充阶段（prefill）， # 要么都处于解码阶段（decode） is_prompt = seq_group_metadata_list[0].is_prompt # 用于计算 logit if is_prompt: (input_tokens, input_positions, input_metadata, prompt_lens) = self._prepare_prompt(seq_group_metadata_list) else: (input_tokens, input_positions, input_metadata ) = self._prepare_decode(seq_group_metadata_list) prompt_lens = [] # 用于采样 token sampling_metadata = self._prepare_sample(seq_group_metadata_list, prompt_lens) ... else: ... return input_tokens, input_positions, input_metadata, sampling_metadata
```

它的处理逻辑如图 6 所示：

![](https://pic2.zhimg.com/v2-abf33173b637a71da0f0bcb5a4319fbd_1440w.jpg)

图 6：不同阶段准备数据的流程

-   准备 input\_tokens、input\_positions、input\_metadata (存储着 token 的地址），这些是计算 logit 的输入

-   如果是填充阶段，调用`_prepare_prompt`方法
-   如果是生成阶段，调用`_prepare_decode`方法

-   调用`_prepare_sample`准备 sampling\_metadata，这个是采样 token 要用到的输入

如果是填充阶段，input\_tokens、input\_positions、input\_metadata、sampling\_metadata 如图 7 所示：

![](https://pic1.zhimg.com/v2-50d612d3a33dd416c62bd6bc664ec5e6_1440w.jpg)

图 7：填充阶段

如果是生成阶段，input\_tokens、input\_positions、input\_metadata、sampling\_metadata 如图 8 所示：

![](https://picx.zhimg.com/v2-d7bbaa6b41a63b471f75903c19732261_1440w.jpg)

图 8：生成阶段

**计算 logit**

![](https://picx.zhimg.com/v2-ed0279fbe027d24c8cab673157504ed7_1440w.jpg)

图 9：计算 logit

接下来调用`model_executable`计算 logit，它会调用 LlamaForCausalLM 的`forward`方法计算 logit：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/worker/model_runner.py class ModelRunner: @torch.inference_mode() def execute_model( self, seq_group_metadata_list: Optional[List[SequenceGroupMetadata]], kv_caches: List[Tuple[torch.Tensor, torch.Tensor]], ) -> Optional[SamplerOutput]: ... # 模型推理 if input_metadata.use_cuda_graph: # 生成阶段走这个分支 graph_batch_size = input_tokens.shape[0] model_executable = self.graph_runners[graph_batch_size] else: # 填充阶段走这个分支 model_executable = self.model # 调用 LlamaForCausalLM 的 forward 方法计算 logit hidden_states = model_executable( input_ids=input_tokens, positions=input_positions, kv_caches=kv_caches, input_metadata=input_metadata, ) ... return output class LlamaForCausalLM(nn.Module): def __init__( self, config: LlamaConfig, linear_method: Optional[LinearMethodBase] = None, ) -> None: super().__init__() ... self.model = LlamaModel(config, linear_method) ... def forward( self, input_ids: torch.Tensor, positions: torch.Tensor, kv_caches: List[KVCache], input_metadata: InputMetadata, ) -> torch.Tensor: hidden_states = self.model(input_ids, positions, kv_caches, input_metadata) return hidden_states
```

LlamaForCausalLM 的`forward`方法会进一步调用 LlamaModel 的`forward`方法，它的实现如下：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/model_executor/models/llama.py class LlamaModel(nn.Module): def forward( self, input_ids: torch.Tensor, positions: torch.Tensor, kv_caches: List[KVCache], input_metadata: InputMetadata, ) -> torch.Tensor: hidden_states = self.embed_tokens(input_ids) residual = None for i in range(len(self.layers)): layer = self.layers[i] hidden_states, residual = layer( positions, hidden_states, kv_caches[i], input_metadata, residual, ) hidden_states, _ = self.norm(hidden_states, residual) return hidden_states
```

它的处理逻辑如图 10 所示：

![](https://pic1.zhimg.com/v2-39665f09f2fb4b160c0f4e8d30683df0_1440w.jpg)

图 10：计算 logit 的流程

-   先计算 token 的 embedding
-   再逐层计算 transformer layer，在这一步，会将计算的中间结果 KV 值缓存在 cache 中

这里的 transformer layer 是 LlamaDecoderLayer，它的实现如下：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/model_executor/models/llama.py class LlamaDecoderLayer(nn.Module): def __init__( self, config: LlamaConfig, linear_method: Optional[LinearMethodBase] = None, ) -> None: ... self.self_attn = LlamaAttention( hidden_size=self.hidden_size, num_heads=config.num_attention_heads, num_kv_heads=config.num_key_value_heads, rope_theta=rope_theta, rope_scaling=rope_scaling, max_position_embeddings=max_position_embeddings, linear_method=linear_method, ) def forward( self, positions: torch.Tensor, hidden_states: torch.Tensor, kv_cache: KVCache, input_metadata: InputMetadata, residual: Optional[torch.Tensor], ) -> Tuple[torch.Tensor, torch.Tensor]: ... hidden_states = self.self_attn( positions=positions, hidden_states=hidden_states, kv_cache=kv_cache, input_metadata=input_metadata, ) ... return hidden_states, residual class LlamaAttention(nn.Module): def __init__( self, hidden_size: int, num_heads: int, num_kv_heads: int, rope_theta: float = 10000, rope_scaling: Optional[Dict[str, Any]] = None, max_position_embeddings: int = 8192, linear_method: Optional[LinearMethodBase] = None, ) -> None: ... self.attn = PagedAttention(self.num_heads, self.head_dim, self.scaling, num_kv_heads=self.num_kv_heads) def forward( self, positions: torch.Tensor, hidden_states: torch.Tensor, kv_cache: KVCache, input_metadata: InputMetadata, ) -> torch.Tensor: qkv, _ = self.qkv_proj(hidden_states) q, k, v = qkv.split([self.q_size, self.kv_size, self.kv_size], dim=-1) q, k = self.rotary_emb(positions, q, k) k_cache, v_cache = kv_cache attn_output = self.attn(q, k, v, k_cache, v_cache, input_metadata) output, _ = self.o_proj(attn_output) return output
```

我们只关注 Attention 层，LlamaDecoderLayer 的 Attention 层使用的是 PagedAttention，它的 [docstring](https://zhida.zhihu.com/search?content_id=242450856&content_type=Article&match_order=1&q=docstring&zhida_source=entity) 概括了它的职责：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/model_executor/layers/attention.py class PagedAttention(nn.Module): """MHA/MQA/GQA layer with PagedAttention. This class takes query, key, and value tensors as input. The input tensors can either contain prompt tokens or generation tokens. The class does the following: 1. Reshape and store the input key and value tensors in the KV cache. 2. Perform (multi-head/multi-query/grouped-query) attention using either xformers or the PagedAttention custom op. 3. Return the output tensor. """
```

总结如下：

-   将 Key 和 Value 存储在 KV cache 中
-   计算 attention

它的具体实现如下：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/model_executor/layers/attention.py class PagedAttention(nn.Module): def forward( self, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor, key_cache: Optional[torch.Tensor], value_cache: Optional[torch.Tensor], input_metadata: InputMetadata, ) -> torch.Tensor: ... # 将 Key 和 Value 存储在 KV cache 中 if key_cache is not None and value_cache is not None: cache_ops.reshape_and_cache( key, value, key_cache, value_cache, input_metadata.slot_mapping.flatten(), ) if input_metadata.is_prompt: # 填充阶段走这个分支 ... out = xops.memory_efficient_attention_forward( query, key, value, attn_bias=input_metadata.attn_bias, p=0.0, scale=self.scale, op=xops.fmha.MemoryEfficientAttentionFlashAttentionOp[0] if (is_hip()) else None, ) output = out.view_as(query) else: # 生成阶段走这个分支 if key_cache is not None and value_cache is not None: output = _paged_attention( query, key_cache, value_cache, input_metadata, self.num_kv_heads, self.scale, self.alibi_slopes, ) else: # This happens during the initial memory profiling run for # CUDA graphs. output = torch.zeros_like(query) # Reshape the output tensor. return output.view(batch_size, seq_len, hidden_size)
```

它的处理逻辑如图 11 所示：

![](https://pica.zhimg.com/v2-6d3be1af0bfa6a7703d3a9bfbcf2cf56_1440w.jpg)

图 11：不同阶段计算 logit 的流程

-   如果是填充阶段，调用 xformers 库的`memory_efficient_attention_forward`函数计算
-   如果是生成阶段，调用`_paged_attention`进而使用自定义的`paged_attention`算子计算

**采样 token**

![](https://pic3.zhimg.com/v2-07d2a8b6376aa8fc42ebd4fb4fe0811a_1440w.jpg)

图 12：采样 token

完成 logit 的计算后，下一步是根据采样策略得到 next token。

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/worker/model_runner.py class ModelRunner: @torch.inference_mode() def execute_model( self, seq_group_metadata_list: Optional[List[SequenceGroupMetadata]], kv_caches: List[Tuple[torch.Tensor, torch.Tensor]], ) -> Optional[SamplerOutput]: ... # 采样 next token output = self.model.sample( hidden_states=hidden_states, sampling_metadata=sampling_metadata, ) return output
```

这里会调用 model 的`sample`方法：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7vllm/model_executor/models/llama.py class LlamaForCausalLM(nn.Module): def __init__( self, config: LlamaConfig, linear_method: Optional[LinearMethodBase] = None, ) -> None: super().__init__() ... self.sampler = Sampler(config.vocab_size) def sample( self, hidden_states: torch.Tensor, sampling_metadata: SamplingMetadata, ) -> Optional[SamplerOutput]: next_tokens = self.sampler(self.lm_head.weight, hidden_states, sampling_metadata)
```

最终调用 Sampler 的`forward`方法：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/model_executor/layers/sampler.py class Sampler(nn.Module): """Samples the next tokens from the model's outputs. This layer does the following: 1. Discard the hidden states that are not used for sampling (i.e., all tokens except the final one in each prompt). 2. Compute the logits for the next tokens. 3. Apply presence, frequency and repetition penalties. 4. Apply temperature scaling. 5. Apply top-p and top-k truncation. 6. Sample the next tokens. Here, each sequence group within the batch can have different sampling parameters (e.g., sampling method, temperature, top-p, top-k, etc.). """ def forward( self, embedding: torch.Tensor, hidden_states: torch.Tensor, sampling_metadata: SamplingMetadata, embedding_bias: Optional[torch.Tensor] = None, ) -> Optional[SamplerOutput]: # Get the hidden states that we use for sampling. hidden_states = _prune_hidden_states(hidden_states, sampling_metadata) # Get the logits for the next tokens. logits = _get_logits(hidden_states, embedding, embedding_bias, self.vocab_size) ... # Apply presence and frequency penalties. if do_penalties: ... ... if do_top_p_top_k: logits = _apply_top_p_top_k(logits, sampling_tensors.top_ps, sampling_tensors.top_ks) if do_min_p: ... ... # Sample the next tokens. sample_results = _sample(probs, logprobs, sampling_metadata) # Get the logprobs query results. prompt_logprobs, sample_logprobs = _get_logprobs( logprobs, sampling_metadata, sample_results) return _build_sampler_output(sample_results, sampling_metadata, prompt_logprobs, sample_logprobs)
```

输出的 output 如图 13 所示：

![](https://pic4.zhimg.com/v2-811db89f90e50bb86f19712315683a93_1440w.jpg)

图 13：output 示意图

让我们再次回到 LLMEngine 的 step 方法，step 方法的最后一个步骤是处理模型的推理结果（即 next\_tokens）。

## 后处理

![](https://pic2.zhimg.com/v2-cb74cc7e483e74f423fbf4f1520eddc3_1440w.jpg)

图 14：后处理

终于来到了 step 方法的最后一步，对模型的输出进行后处理：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/engine/llm_engine.py class LLMEngine: def step(self) -> List[RequestOutput]: ... return self._process_model_outputs(output, scheduler_outputs)
```

它会调用`_process_model_outputs`方法完成模型输出的后处理：

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/engine/llm_engine.py class LLMEngine: def _process_model_outputs( self, output: SamplerOutput, scheduler_outputs: SchedulerOutputs) -> List[RequestOutput]: # 使用模型的输出更新被调度的请求 scheduled_seq_groups = scheduler_outputs.scheduled_seq_groups for seq_group, outputs in zip(scheduled_seq_groups, output): self._process_sequence_group_outputs(seq_group, outputs) # 释放已经完成的 sequnece group self.scheduler.free_finished_seq_groups() # 创建输出 request_outputs: List[RequestOutput] = [] for seq_group in (scheduled_seq_groups + scheduler_outputs.ignored_seq_groups): request_output = RequestOutput.from_seq_group(seq_group) request_outputs.append(request_output) if self.log_stats: # Log the system stats. self._log_system_stats(scheduler_outputs.prompt_run, scheduler_outputs.num_batched_tokens) return request_outputs
```

它的处理逻辑如下：

-   使用模型的输出更新被调度的请求，例如更新 sequence 的 **logical token block**、检查 sequence 是否已经处理完成
-   释放已经完成的 sequence group
-   创建输出

完成`_process_model_outputs`方法的调用后，回到了 LLM 的`_run_engine`方法，如果还有没处理完的请求，就进入下一次循环，开始新一轮的请求调度和请求推理。

```python3
# https://github.com/vllm-project/vllm/tree/v0.2.7/vllm/entrypoints/llm.py class LLM: def _run_engine(self, use_tqdm: bool) -> List[RequestOutput]: ... outputs: List[RequestOutput] = [] while self.llm_engine.has_unfinished_requests(): step_outputs = self.llm_engine.step() for output in step_outputs: if output.finished: outputs.append(output) ... outputs = sorted(outputs, key=lambda x: int(x.request_id)) return outputs
```

至此，vLLM 的源码解读部分到此结束了，以一张流程图[可视化](https://zhida.zhihu.com/search?content_id=242450856&content_type=Article&match_order=1&q=%E5%8F%AF%E8%A7%86%E5%8C%96&zhida_source=entity)本章模型推理以及后处理的流程。

![](https://pic3.zhimg.com/v2-65eded43b9fd41e6475dcc6c78775d7c_1440w.jpg)

图 15：本章节的完整流程图

vLLM 迭代得很快，我们的解读系列是基于 [v0.2.7](https://link.zhihu.com/?target=https%3A//github.com/vllm-project/vllm/tree/v0.2.7) 版本，截至 2024.4.24，它的最新版本已经到了 [v0.4.1](https://link.zhihu.com/?target=https%3A//github.com/vllm-project/vllm/tree/v0.4.1)。之所以在这里提及它的版本，是因为它会持续添加新功能并可能伴随对代码逻辑的重构，导致不同版本之间的实现逻辑或者代码的位置发生了变化。因此，大家阅读我们的源码解读系列时，建议基于 v0.2.7 版本。  
最后，如果有时间，我会继续解读 vLLM 的新功能，欢迎大家关注。

---

> **vLLM（知乎）系列导航**：[[vLLM 系列（知乎）索引|系列索引]] ｜ 上一篇：[[vLLM（五）调度器的细节 - 知乎|五：调度器的细节]] ｜ 下一篇：[[vLLM（七）图解 LLaVA 推理流程 - 知乎|七：图解 LLaVA 推理流程]]

