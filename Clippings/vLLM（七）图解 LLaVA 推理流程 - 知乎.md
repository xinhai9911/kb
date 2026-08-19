---
title: "vLLM（七）图解 LLaVA 推理流程"
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
part: "七"
---
本系列将介绍 vLLM 的方方面面：

___

距离上一篇 [vLLM](https://zhuanlan.zhihu.com/p/715131885) 的源码解读已经过去大半年了。一直想写一篇 vLLM 中 VLM (Vision Language Model) 的源码解读，但一直拖着没整理，今天年初二，有空闲的时间，就好好整理了一下。  
如果有关注过另一个系列（[LLaVA](https://zhuanlan.zhihu.com/p/696654492)）的朋友大概会疑惑，[VLM 的源码解读](https://zhuanlan.zhihu.com/p/696654492)已经有一篇了，为什么还要再写一篇。其实是因为我对 vLLM 的 VLM 推理流程比较感兴趣，例如：

-   如何为 [Vision Tower](https://zhida.zhihu.com/search?content_id=253175609&content_type=Article&match_order=1&q=Vision+Tower&zhida_source=entity) (也称为 Vision Encoder）预留[显存](https://zhida.zhihu.com/search?content_id=253175609&content_type=Article&match_order=1&q=%E6%98%BE%E5%AD%98&zhida_source=entity)才能保证不会因为 Vision Tower 导致 OOM
-   图片的预处理是在哪里进行的（不同版本的 vLLM 会有区别，详情见 [#10114](https://link.zhihu.com/?target=https%3A//github.com/vllm-project/vllm/issues/10114)
-   文本和图像的 embedding 是在哪里拼接的

相信大家读完这篇文章就可以解答上面的三个问题了。话不多说，这就开始。  
我们以下面的代码为例介绍 VLM 的推理流程。源码版本 [v0.6.6.post1](https://link.zhihu.com/?target=https%3A//github.com/vllm-project/vllm/tree/v0.6.6.post1)。

```python3
from vllm import LLM, SamplingParams from PIL import Image # 模型下载路径 https://huggingface.co/llava-hf/llava-1.5-7b-hf # limit_mm_per_prompt={"image": 1} 用于控制每个请求的图片数，这里表示 # 一个请求最多只能包含一张图片 llm = LLM(model="llava-hf/llava-1.5-7b-hf", limit_mm_per_prompt={"image": 1}) sampling_params = SamplingParams(max_tokens=256) prompt = "USER: <image>\nWhat are the things I should be cautious about when I visit here?\nASSISTANT:" image = Image.open("view.jpg") outputs = llm.generate( { "prompt": prompt, "multi_modal_data": {"image": image}, }, sampling_params=sampling_params, ) for o in outputs: generated_text = o.outputs[0].text print(generated_text)
```

运行上面的代码，可以得到下面的输出：

```python3
When visiting this location, you should be cautious about several factors. First, be aware of safety measures around the park, main street, and boat dock area. Keep a close eye on traffic and pedestrian areas to ensure that you follow the rules and stay safe. Also, pay attention to any signs or barriers that might be in place, like warnings or restricted areas, as this will ensure your safety while in the park or near the dock. Additionally, considering the presence of a boat dock, be cautious about water activities, falling into the water if you are not a strong swimmer, and being attentive to boats and other watercraft that could pass by. Remember to enjoy your visit while keeping safety in mind.
```

## 推理流程概览

在开始介绍推理流程前，我们先给出 vLLM 中 LLaVA 的推理流程图，如图 1 所示，以便大家有个直观的了解。

![](https://pic4.zhimg.com/v2-8f79be41dee80b1689de03d7f9ee4c03_1440w.jpg)

图 1：推理流程概览

接下来，首先介绍 LLM 的初始化。

## LLM 初始化

```python3
# limit_mm_per_prompt={"image": 1} 用于控制每个请求的图片数，这里表示 # 一个请求最多只能包含一张图片 llm = LLM(model="llava-hf/llava-1.5-7b-hf", limit_mm_per_prompt={"image": 1})
```

当上面这行代码被执行时，主要完成了 LLM（vLLM 的入口）、LLMEngine（vLLM 的核心类）以及 Llava 模块的初始化，这些模块的初始化在前面的[几篇文章](https://zhuanlan.zhihu.com/p/681716326)都有详细介绍，但有一些小差别，那就是 VLM 的推理涉及图片（当然其他的 [VLM 模型](https://zhida.zhihu.com/search?content_id=253175609&content_type=Article&match_order=1&q=VLM+%E6%A8%A1%E5%9E%8B&zhida_source=entity)还可能涉及视频和音频，但本篇文章只关注图片）。我们知道，vLLM 的核心之一是提前预分配 gpu block（确定 gpu block 的数目），那么，有了图片的参与，我们应该怎么确定 gpu block 的数目才能保证在运行时不会由于 Vision Tower 的原因 OOM，换句话说，我们应该为图片的处理（LLaVA 使用的 Vision Tower 为 [CLIPModel](https://zhida.zhihu.com/search?content_id=253175609&content_type=Article&match_order=1&q=CLIPModel&zhida_source=entity)）预留多少显存呢？  
vLLM 的做法是在 profile run（LLMEngine 初始化时需要通过 profile run 来确定 gpu block 的数目）时根据下面的三个要素构造一个极限 dummy data：

-   每个请求能接受的最大图片分辨率（对应一张图片最多能消耗多少显存）
-   每个请求能接受的图片数上限（对应`limit_mm_per_prompt={"image": 1}`）
-   同时处理的最大请求数（注意，这个值和用户传入的 max\_num\_seqs 不一定相同）

通过 profile run 满足上面三个要素的 dummy data，即可确定真正处理请求时最多消耗多少显存（包含了 CLIPModel 会消耗的最大显存）。  
下面是 profile run 的逻辑：

```python3
# https://github.com/vllm-project/vllm/blob/v0.6.6.post1/vllm/worker/model_runner.py class GPUModelRunnerBase(ModelRunnerBase[TModelInputForGPU]): @torch.inference_mode() def profile_run(self) -> None: # Enable top-k sampling to reflect the accurate memory usage. sampling_params = SamplingParams(top_p=0.99, top_k=self.vocab_size - 1) max_num_batched_tokens = self.scheduler_config.max_num_batched_tokens max_num_seqs = self.scheduler_config.max_num_seqs # This represents the maximum number of different requests # that will have unique loras, an therefore the max amount of memory # consumption create dummy lora request copies from the lora request # passed in, which contains a lora from the lora warmup path. dummy_lora_requests: List[LoRARequest] = [] dummy_lora_requests_per_seq: List[LoRARequest] = [] ... # Profile memory usage with max_num_sequences sequences and the total # number of tokens equal to max_num_batched_tokens. seqs: List[SequenceGroupMetadata] = [] # Additional GPU memory may be needed for multi-modal encoding, which # needs to be accounted for when calculating the GPU blocks for # vLLM blocker manager. # To exercise the worst scenario for GPU memory consumption, # the number of seqs (batch_size) is chosen to maximize the number # of images processed. # 调用 MultiModalRegistry 的 get_max_tokens_by_modality 方法 # 确定每个 sequence（请求）的 multimodal 最多占用多少 token， # 例如 limit_mm_per_prompt={"image": 1} max_mm_tokens = self.mm_registry.get_max_multimodal_tokens( self.model_config) if max_mm_tokens > 0: max_num_seqs_orig = max_num_seqs # 对应上面的第三个要素 max_num_seqs = min(max_num_seqs, max_num_batched_tokens // max_mm_tokens) if max_num_seqs < 1: expr = (f"min({max_num_seqs_orig}, " f"{max_num_batched_tokens} // {max_mm_tokens})") logger.warning( "Computed max_num_seqs (%s) to be less than 1. " "Setting it to the minimum value of 1.", expr) max_num_seqs = 1 batch_size = 0 for group_id in range(max_num_seqs): seq_len = (max_num_batched_tokens // max_num_seqs + (group_id < max_num_batched_tokens % max_num_seqs)) batch_size += seq_len # 构造 dummy data，满足上面的第一和第二要素 dummy_data = self.input_registry \ .dummy_data_for_profiling(self.model_config, seq_len, self.mm_registry) ... ... self.execute_model(model_input, kv_caches, intermediate_tensors) torch.cuda.synchronize() return class MultiModalRegistry: def get_max_tokens_by_modality( self, model_config: "ModelConfig", ) -> Mapping[str, int]: limits_per_plugin = self._limits_by_model[model_config] return { key: limits_per_plugin[key] * max_tokens_per_mm_item for key, max_tokens_per_mm_item in self.get_max_tokens_per_item_by_modality(model_config).items() }
```

LLM 的初始化就不做过多介绍了，如果对细节感兴趣，推荐阅读前面的几篇文章。

## 数据预处理

数据预处理主要涉及三个类，分别是：

-   InputPreprocessor：vLLM 中数据预处理的入口，它会调用 Llava 的 LlavaMultiModalProcessor 完成输入数据的预处理
-   LlavaMultiModalProcessor：Llava 中负责处理输入数据预处理的类
-   LlavaProcessor：Tokenizer 和 Image Processor 的组合，负责将文本 tokenize 成 token\_ids 以及将图片处理成 Vision Tower (CLIPModel) 接受的格式。它的实现位于 [transformers](https://link.zhihu.com/?target=https%3A//github.com/huggingface/transformers/blob/main/src/transformers/models/llava/processing_llava.py)。

![](https://picx.zhimg.com/v2-faec69f4319257c9bb4775f2092767d5_1440w.jpg)

图 2：数据预处理

图 2 是 LLaVA 中数据预处理的输入和输入。如图 2 所示，输入是 text 和 PIL image，输出是 token\_ids 和 Image Tensor，值得注意的是，这里的 token\_ids 已经填充了 576（LLaVA 一张图对应 576 个 token）个 image token。  
数据预处理的操作在 LLMEngine 的 add\_request 方法内完成，它的实现如下：

```python3
# https://github.com/vllm-project/vllm/blob/v0.6.6.post1/vllm/engine/llm_engine.py class LLMEngine: def add_request( self, request_id: str, prompt: Optional[PromptType] = None, params: Optional[Union[SamplingParams, PoolingParams]] = None, arrival_time: Optional[float] = None, lora_request: Optional[LoRARequest] = None, trace_headers: Optional[Mapping[str, str]] = None, prompt_adapter_request: Optional[PromptAdapterRequest] = None, priority: int = 0, *, inputs: Optional[PromptType] = None, # DEPRECATED ) -> None: """Add a request to the engine's request pool. The request is added to the request pool and will be processed by the scheduler as `engine.step()` is called. The exact scheduling policy is determined by the scheduler. """ ... # 最终调用 LlavaProcessor 完成请求的预处理，包括 prompt 的 tokenize 以及图片的预处理 # preprocessed_inputs: { # "prompt": "<s> USER: <image><image><image>...ASSISTANT:' # "prompt_token_ids": [1, 3148, 1001, 29901, 29871, 32000, 32000, ...,29901], # "mm_kwargs": ... # } preprocessed_inputs = self.input_preprocessor.preprocess( prompt, request_id=request_id, lora_request=lora_request, prompt_adapter_request=prompt_adapter_request, ) # llava 没有对 preprocessed_inputs 做处理，所以 # processed_inputs 就是 preprocessed_inputs processed_inputs = self.input_processor(preprocessed_inputs) self._add_processed_request( request_id=request_id, processed_inputs=processed_inputs, params=params, arrival_time=arrival_time, lora_request=lora_request, prompt_adapter_request=prompt_adapter_request, trace_headers=trace_headers, priority=priority, ) # vllm/model_executor/models/llava.py class LlavaMultiModalProcessor(BaseMultiModalProcessor): pass
```

## 模型推理

图 3 是模型的推理流程图。

![](https://pic4.zhimg.com/v2-b8fd865eb0285279dacc5e78444a66dd_1440w.jpg)

图 3：模型推理

```python3
# vllm/engine/llm_engine.py class LLMEngine: def step(self): # 调度，决定哪些请求即将被处理 ... = self.scheduler[virtual_engine].schedule() # 模型 forward outputs = self.model_executor.execute_model( execute_model_req=execute_model_req) # vllm/model_executor/models/llava.py @MULTIMODAL_REGISTRY.register_processor(LlavaMultiModalProcessor) class LlavaForConditionalGeneration(nn.Module, SupportsMultiModal, SupportsPP): def forward(self, ...): ... vision_embeddings = self.get_multimodal_embeddings(**kwargs) inputs_embeds = self.get_input_embeddings(input_ids, vision_embeddings) input_ids = None hidden_states = self.language_model.model(input_ids, positions, kv_caches, attn_metadata, intermediate_tensors, inputs_embeds=inputs_embeds) return hidden_states
```

经过一层层的调用后，来到了`LlavaForConditionalGeneration`的 forward 方法，在这个方法中，执行五个步骤：  

1.  调用 vision tower 将图片 encode 成 CLIP 特征，特征的 shape 是 \[1, 576, 1024\]
2.  调用 multi-modal projector 将 CLIP 特征投影到文本[特征空间](https://zhida.zhihu.com/search?content_id=253175609&content_type=Article&match_order=1&q=%E7%89%B9%E5%BE%81%E7%A9%BA%E9%97%B4&zhida_source=entity)，记为 **I** (image embedding)，它的 shape 是 \[1, 576, 4096\]
3.  调用 language model 将 input\_ids 转好为文本特征，记为 **T** (text embedding)，它的 shape 是 \[604, 4096\]
4.  合并 I 和 T，即使用 I 替换 T 中的 placeholder
5.  调用 language model 完成一次 forward

上面的五个步骤中，其他的就不过多介绍了，只介绍一下 I 和 T 的合并，它的实现如下：

```python3
# vllm/model_executor/models/utils.py def _flatten_embeddings(embeddings: NestedTensors) -> torch.Tensor: """ Recursively flattens and concatenates NestedTensors on all but the last dimension. """ if isinstance(embeddings, torch.Tensor): # Flatten all but the last dimension. # embeddings: [1, 576, 4096] # -> # [576, 4096] return embeddings.flatten(0, -2) return torch.cat(tuple(_flatten_embeddings(t) for t in embeddings)) def _merge_multimodal_embeddings( inputs_embeds: torch.Tensor, is_multimodal: torch.Tensor, multimodal_embeddings: NestedTensors, ) -> torch.Tensor: """ Merge ``multimodal_embeddings`` into ``inputs_embeds`` by overwriting the positions in ``inputs_embeds`` corresponding to placeholder tokens in ``input_ids``. Note: This updates ``inputs_embeds`` in place. """ # is_multimodal: Size[604] # num_expected_tokens=576，因为 Llava 中一张图对应固定的 576 个 token num_expected_tokens = is_multimodal.sum().item() assert isinstance(num_expected_tokens, int) # [1, 576, 4096] -> [576, 4096] flattened = _flatten_embeddings(multimodal_embeddings) if flattened.shape[0] != num_expected_tokens: expr = _embedding_count_expression(multimodal_embeddings) raise ValueError( f"Attempted to assign {expr} = {flattened.shape[0]} " f"multimodal tokens to {num_expected_tokens} placeholders") inputs_embeds[is_multimodal] = flattened return inputs_embeds def merge_multimodal_embeddings( input_ids: torch.Tensor, inputs_embeds: torch.Tensor, multimodal_embeddings: NestedTensors, placeholder_token_id: Union[int, List[int]], ) -> torch.Tensor: """ Merge ``multimodal_embeddings`` into ``inputs_embeds`` by overwriting the positions in ``inputs_embeds`` corresponding to placeholder tokens in ``input_ids``. ``placeholder_token_id`` can be a list of token ids (e.g, token ids of img_start, img_break, and img_end tokens) when needed: This means the order of these tokens in the ``input_ids`` MUST MATCH the order of their embeddings in ``multimodal_embeddings`` since we need to slice-merge instead of individually scattering. For example, if input_ids is "TTTTTSIIIBIIIBIIIETTT", where - T is text token - S is image start token - I is image embedding token - B is image break token - E is image end token. Then the image embeddings (that correspond to I's) from vision encoder must be padded with embeddings of S, B, and E in the same order of input_ids for a correct embedding merge. Note: This updates ``inputs_embeds`` in place. """ ... return _merge_multimodal_embeddings( inputs_embeds, (input_ids == placeholder_token_id), multimodal_embeddings, )
```

至此，LLaVA 的推理流程就介绍完了，vLLM 中的其他 VLM 推理流程也基本一致。

## 参考

1.  [Multi-Modal Data Processing](https://link.zhihu.com/?target=https%3A//docs.vllm.ai/en/latest/design/mm_processing.html)
2.  [Multi-Model Support](https://link.zhihu.com/?target=https%3A//docs.vllm.ai/en/latest/contributing/model/multimodal.html)
3.  [\[RFC\]: Multi-modality Support on vLLM #4194](https://link.zhihu.com/?target=https%3A//github.com/vllm-project/vllm/issues/4194)
4.  [\[RFC\]: Merge input processor and input mapper for multi-modal models #10114](https://link.zhihu.com/?target=https%3A//github.com/vllm-project/vllm/issues/10114)
5.  [LLaVA（四）图解 LLaVA 推理流程](https://zhuanlan.zhihu.com/p/696654492)

---

> **vLLM（知乎）系列导航**：[[vLLM 系列（知乎）索引|系列索引]] ｜ 上一篇：[[vLLM（六）模型的推理细节 - 知乎|六：模型的推理细节]]

