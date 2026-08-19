---
title: "vLLM（二）架构概览"
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
part: "二"
---
> [Efficient Memory Management for Large Language Model Serving with PagedAttention](https://link.zhihu.com/?target=https%3A//arxiv.org/pdf/2309.06180.pdf)  
> [https://github.com/vllm-project/vllm](https://link.zhihu.com/?target=https%3A//github.com/vllm-project/vllm/tree/v0.2.7)  
> [https://docs.google.com/presentation](https://link.zhihu.com/?target=https%3A//docs.google.com/presentation/d/1QL-XPFXiFpDBh86DbEegFXBXFXjix4v032GhShbKf3s/edit%23slide%3Did.p)  
> [Fast LLM Serving with vLLM and PagedAttention\_哔哩哔哩\_bilibili](https://link.zhihu.com/?target=https%3A//www.bilibili.com/video/BV1eF4m1N7rL/%3Fshare_source%3Dcopy_web%26vd_source%3Daac509da00df68a65bd1548362420c8d)

本系列将介绍 vLLM 的方方面面：

___

vLLM 是一个 LLM (Large Lanuage Model) 推理和部署服务库，它结合 iterative-level schedule (常被称为 continuous batching，该[调度算法](https://zhida.zhihu.com/search?content_id=239622556&content_type=Article&match_order=1&q=%E8%B0%83%E5%BA%A6%E7%AE%97%E6%B3%95&zd_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ6aGlkYV9zZXJ2ZXIiLCJleHAiOjE3ODcyOTk3MTAsInEiOiLosIPluqbnrpfms5UiLCJ6aGlkYV9zb3VyY2UiOiJlbnRpdHkiLCJjb250ZW50X2lkIjoyMzk2MjI1NTYsImNvbnRlbnRfdHlwZSI6IkFydGljbGUiLCJtYXRjaF9vcmRlciI6MSwiemRfdG9rZW4iOm51bGx9.tCsRm4-XaCWNMoyWQvsTm9IhTNaew3IANL4MeuqH-7g&zhida_source=entity)在 [Orca](https://link.zhihu.com/?target=https%3A//www.usenix.org/system/files/osdi22-yu.pdf) 中首次被提出) 和 PagedAttention [注意力算法](https://zhida.zhihu.com/search?content_id=239622556&content_type=Article&match_order=1&q=%E6%B3%A8%E6%84%8F%E5%8A%9B%E7%AE%97%E6%B3%95&zd_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ6aGlkYV9zZXJ2ZXIiLCJleHAiOjE3ODcyOTk3MTAsInEiOiLms6jmhI_lipvnrpfms5UiLCJ6aGlkYV9zb3VyY2UiOiJlbnRpdHkiLCJjb250ZW50X2lkIjoyMzk2MjI1NTYsImNvbnRlbnRfdHlwZSI6IkFydGljbGUiLCJtYXRjaF9vcmRlciI6MSwiemRfdG9rZW4iOm51bGx9.0YnWlwm6jVDqlvLRpcWXJvvrhmvhlYGgcmkrYnYAUFE&zhida_source=entity)以提高服务的[吞吐量](https://zhida.zhihu.com/search?content_id=239622556&content_type=Article&match_order=1&q=%E5%90%9E%E5%90%90%E9%87%8F&zd_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ6aGlkYV9zZXJ2ZXIiLCJleHAiOjE3ODcyOTk3MTAsInEiOiLlkJ7lkJDph48iLCJ6aGlkYV9zb3VyY2UiOiJlbnRpdHkiLCJjb250ZW50X2lkIjoyMzk2MjI1NTYsImNvbnRlbnRfdHlwZSI6IkFydGljbGUiLCJtYXRjaF9vcmRlciI6MSwiemRfdG9rZW4iOm51bGx9.82vg1VJO0-89J6jZZJjlad0PQ-Pe7Gl3er4-f0KLyNk&zhida_source=entity)。前者（iterative-level schedule）以[单轮迭代](https://zhida.zhihu.com/search?content_id=239622556&content_type=Article&match_order=1&q=%E5%8D%95%E8%BD%AE%E8%BF%AD%E4%BB%A3&zd_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ6aGlkYV9zZXJ2ZXIiLCJleHAiOjE3ODcyOTk3MTAsInEiOiLljZXova7ov63ku6MiLCJ6aGlkYV9zb3VyY2UiOiJlbnRpdHkiLCJjb250ZW50X2lkIjoyMzk2MjI1NTYsImNvbnRlbnRfdHlwZSI6IkFydGljbGUiLCJtYXRjaF9vcmRlciI6MSwiemRfdG9rZW4iOm51bGx9.YaUZkmtJYT59rndgbH-_3McapKp6KbTQxJHKlXhWhb4&zhida_source=entity)的方式对用户的请求进行处理，即 LLM 生成一个 token 后会重新调度下一轮要处理的请求。后者（PagedAttention）受操作系统[虚拟内存](https://zhida.zhihu.com/search?content_id=239622556&content_type=Article&match_order=1&q=%E8%99%9A%E6%8B%9F%E5%86%85%E5%AD%98&zd_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ6aGlkYV9zZXJ2ZXIiLCJleHAiOjE3ODcyOTk3MTAsInEiOiLomZrmi5_lhoXlrZgiLCJ6aGlkYV9zb3VyY2UiOiJlbnRpdHkiLCJjb250ZW50X2lkIjoyMzk2MjI1NTYsImNvbnRlbnRfdHlwZSI6IkFydGljbGUiLCJtYXRjaF9vcmRlciI6MSwiemRfdG9rZW4iOm51bGx9.I1ual8YKFIP0VMqmq2PTkU9laba2DH7cC_ROOlvwPdU&zhida_source=entity)和分页思想启发，将原本连续的 KV cache 存储在不连续的空间，以避免 KV cache 带来的显存浪费。更多关于 [iterative-level schedule](https://zhida.zhihu.com/search?content_id=239622556&content_type=Article&match_order=3&q=iterative-level+schedule&zd_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ6aGlkYV9zZXJ2ZXIiLCJleHAiOjE3ODcyOTk3MTAsInEiOiJpdGVyYXRpdmUtbGV2ZWwgc2NoZWR1bGUiLCJ6aGlkYV9zb3VyY2UiOiJlbnRpdHkiLCJjb250ZW50X2lkIjoyMzk2MjI1NTYsImNvbnRlbnRfdHlwZSI6IkFydGljbGUiLCJtYXRjaF9vcmRlciI6MywiemRfdG9rZW4iOm51bGx9._6BcNZSbV-9r71pV3K27u8YDPOdFO-Wl2r4aUjsmmAM&zhida_source=entity) 和 PagedAttention 的介绍可阅读 [Achieve 23x LLM Inference Throughput & Reduce p50 Latency](https://link.zhihu.com/?target=https%3A//www.anyscale.com/blog/continuous-batching-llm-inference) 和 [vLLM: Easy, Fast, and Cheap LLM Serving with PagedAttention](https://link.zhihu.com/?target=https%3A//blog.vllm.ai/2023/06/20/vllm.html)。

上一篇文章介绍了 vLLM 的 PagedAttention 注意力算法（建议阅读本篇文章前先阅读该篇文章），

这一篇的重点是介绍 vLLM 的整体架构以及工作流，而有关 vLLM 的具体实现细节会在后续的文章介绍。

以 vLLM 的一个示例开始本篇文章的介绍。

## 使用示例

vLLM 对外提供了 LLM 和 Async[LLMEngine](https://zhida.zhihu.com/search?content_id=239622556&content_type=Article&match_order=1&q=LLMEngine&zd_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ6aGlkYV9zZXJ2ZXIiLCJleHAiOjE3ODcyOTk3MTAsInEiOiJMTE1FbmdpbmUiLCJ6aGlkYV9zb3VyY2UiOiJlbnRpdHkiLCJjb250ZW50X2lkIjoyMzk2MjI1NTYsImNvbnRlbnRfdHlwZSI6IkFydGljbGUiLCJtYXRjaF9vcmRlciI6MSwiemRfdG9rZW4iOm51bGx9.wv671RE2s26SVZ_jthGHkCJ0Xsu9U2Ux2fpa58S2xi4&zhida_source=entity) 接口，前者用于离线推理（offline inference），后者用于在线服务（online serving）。本文只提及 LLM 接口，对于 AsyncLLMEngine 接口的更多介绍请阅读 [vLLM 用户文档](https://link.zhihu.com/?target=https%3A//docs.vllm.ai/en/latest/getting_started/quickstart.html)。

LLM 主要的两个接口是[初始化方法](https://zhida.zhihu.com/search?content_id=239622556&content_type=Article&match_order=1&q=%E5%88%9D%E5%A7%8B%E5%8C%96%E6%96%B9%E6%B3%95&zd_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ6aGlkYV9zZXJ2ZXIiLCJleHAiOjE3ODcyOTk3MTAsInEiOiLliJ3lp4vljJbmlrnms5UiLCJ6aGlkYV9zb3VyY2UiOiJlbnRpdHkiLCJjb250ZW50X2lkIjoyMzk2MjI1NTYsImNvbnRlbnRfdHlwZSI6IkFydGljbGUiLCJtYXRjaF9vcmRlciI6MSwiemRfdG9rZW4iOm51bGx9.wntIvr6OeuDhs4tplWUkkgSIjUmATHbnmPHvdxs6uvM&zhida_source=entity)和 generate 方法，前者用于实例化 LLM 对象，后者处理接收到的 prompts 和采样参数。

下面是使用 LLM 接口的示例：

```python3
from vllm import LLM, SamplingParams prompts = [ "Hello, my name is", "The future of AI is", ] sampling_params = SamplingParams(temperature=0.8, top_p=0.95) llm = LLM(model="meta-llama/Llama-2-7b-chat-hf") outputs = llm.generate(prompts, sampling_params) # Print the outputs. for output in outputs: prompt = output.prompt generated_text = output.outputs[0].text print(f"Prompt: {prompt!r}, Generated text: {generated_text!r}")
```

运行上面的代码，可以看到下面的输入：

```text
Prompt: 'Hello, my name is', Generated text: ' Dustin Nelson and I’m going to be your tutor!\n' Prompt: 'The future of AI is', Generated text: ' bright, but it’s unclear how many of the blue-sky concepts we'
```

在简单了解 vLLM 的用法后，我们接下来看一下 vLLM 的整体架构。

![](https://pica.zhimg.com/v2-f49e5fc8df7e4f1a05fd5b3ba3d15904_1440w.jpg)

图1：vLLM 架构图，参考自 vLLM 论文

图 1 是 vLLM 的架构图，它的核心组件是 LLMEngine 类，外层接口类 LLM 和 AsyncLLMEngine 都是对 LLMEngine 的封装。  
LLMEngine 有两个核心组件，分别是负责请求调度的 Scheduler 和负责[模型推理](https://zhida.zhihu.com/search?content_id=239622556&content_type=Article&match_order=1&q=%E6%A8%A1%E5%9E%8B%E6%8E%A8%E7%90%86&zd_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ6aGlkYV9zZXJ2ZXIiLCJleHAiOjE3ODcyOTk3MTAsInEiOiLmqKHlnovmjqjnkIYiLCJ6aGlkYV9zb3VyY2UiOiJlbnRpdHkiLCJjb250ZW50X2lkIjoyMzk2MjI1NTYsImNvbnRlbnRfdHlwZSI6IkFydGljbGUiLCJtYXRjaF9vcmRlciI6MSwiemRfdG9rZW4iOm51bGx9.M5Wm6Z2AlwIOTwjKSagWr4-VhuaQnjMFl3Bth-39tCU&zhida_source=entity)的 Worker，前者从等待队列中选择接下来要处理的请求，后者负责使用模型对被调度的请求进行推理。

### Scheduler

Scheduler 使用 iterative-level 策略对请求进行调度（选择要被处理的请求），被调度的请求在生成一个 token 后会被重新调度。得益于 itertive-level 策略，vLLM 能够在每一轮新的迭代时选择不固定数量的请求进行处理（即 batch size 每次都不一定相同），因此它能够尽可能多地处理请求。  
请求的处理通常分为两个阶段，第一个阶段对 prompt 进行处理（也被称为填充阶段，后文使用填充阶段表示这一个阶段），生成 prompt KV cache 的同时生成第一个 token，第二个阶段是生成阶段，不断预测下一个 token。  
目前对 iterative-level 的实现有两种方式，一种是区分填充阶段和生成阶段，另一种是不区分这两个阶段。具体而言，同一个 batch 里被处理的请求是否均处于同一个阶段（例如填充阶段或者生成阶段。vLLM 采用的 iterative-level 策略是区分两个阶段的（[https://github.com/vllm-project/vllm/pull/658](https://link.zhihu.com/?target=https%3A//github.com/vllm-project/vllm/pull/658)），即同一批被调度的请求要么都处于填充阶段，要么都处于生成阶段，这和 huggingface 的 TGI 推理库一致。而提出 iterative-level 策略的 [Orca](https://link.zhihu.com/?target=https%3A//www.usenix.org/system/files/osdi22-yu.pdf) 系统是不区分这两个阶段的。  
Scheduler 中有 3 个队列，waiting（接受到的新请求会先放入 waiting 队列）、running（被调度的请求）和 swapped 队列（swapped 队列用于存放被抢占的请求，即当请求处于生成阶段时，但由于空间的不足，需暂时将 running 队列中优先级低的请求移到 swapped 队列）。在调度时，Scheduler 会按照先到先处理（first come first served）的原则从 waiting 队列中选择请求放入 running 队列（注意，实际的调度包含更多细节，会在后续的文章中做更详细的介绍）。  
此外，Scheduler 的另一个核心组件是 BlockSpaceManager，它主要负责块表的维护。

### Worker

Worker 负责模型的执行。如果模型过大，可以将模型切分到多个 Worker 共同完成请求的处理。

假设模型有 4 层，现在有 4 张卡，可以设置 Tensor Parallel=4（注意：截止 v0.4.0，vLLM 还没有支持 Pipeline Parallel），则将模型每一层切分为 4 份，每张卡存放模型的一部分。

![](https://pic2.zhimg.com/v2-a996b992fc6a363f69b2af4c4b87fcb1_1440w.jpg)

图2：将模型切分为 4 份，每张卡放模型的一部分

Worker 的一个核心组件是 [CacheEngine](https://zhida.zhihu.com/search?content_id=239622556&content_type=Article&match_order=1&q=CacheEngine&zd_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ6aGlkYV9zZXJ2ZXIiLCJleHAiOjE3ODcyOTk3MTAsInEiOiJDYWNoZUVuZ2luZSIsInpoaWRhX3NvdXJjZSI6ImVudGl0eSIsImNvbnRlbnRfaWQiOjIzOTYyMjU1NiwiY29udGVudF90eXBlIjoiQXJ0aWNsZSIsIm1hdGNoX29yZGVyIjoxLCJ6ZF90b2tlbiI6bnVsbH0.h5Xn4cTxg5rj6kYS2pjbMpHnBP61RaKJF3z7CA7BSmM&zhida_source=entity)，它负责 KV cache 的初始化以及 KV cache 的相关操作。

## 工作流

下面以具体的示例演示 vLLM 的工作流。

### 初始化

在初始化阶段，主要初始化 LLMEngine 中的 Scheduler 和 Worker 对象，Scheduler 的初始化主要是块表（block table）的初始化，Worker 的初始化包括模型的初始化以及 KV cache 的初始化，如图 3 所示：

![](https://picx.zhimg.com/v2-9c47f4e88a9293f6ec3ea009da209293_1440w.jpg)

图3：初始化 Scheduler 和 Worker

### 调度和推理

假设 vLLM 接收到 3 个请求（记为 s0, s1, s2）并放入 waiting 队列中，它们的 prompt 分别为 "Hello, my name is"、"The future of AI is" 和 "The life is"。  
接下来开始 vLLM 的调度和处理。

-   vLLM 的第一轮处理

假设 vLLM 在这一轮只能调度两个请求进行处理，那么根据先到先处理的原则，会从 waiting 队列中选择 s0 ("Hello, my name is") 和 s1 ("The future of AI is") 放入到 running 队列。对于 s0，Worker 生成的 token 为 Dustin，对于 s1，Worker 生成的 token 为 bright。同时，Worker 会将计算过程产生的 KV 值存储在 [KV cache](https://zhida.zhihu.com/search?content_id=239622556&content_type=Article&match_order=7&q=KV+cache&zd_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ6aGlkYV9zZXJ2ZXIiLCJleHAiOjE3ODcyOTk3MTAsInEiOiJLViBjYWNoZSIsInpoaWRhX3NvdXJjZSI6ImVudGl0eSIsImNvbnRlbnRfaWQiOjIzOTYyMjU1NiwiY29udGVudF90eXBlIjoiQXJ0aWNsZSIsIm1hdGNoX29yZGVyIjo3LCJ6ZF90b2tlbiI6bnVsbH0.2AMR6STfRFRvSIELl-PaoLpw7o_TnRYk4Z84F47Uzhk&zhida_source=entity) 中，如图 4 所示：

![](https://pic1.zhimg.com/v2-0744e83f0db0508c92cc3613f91b95d4_1440w.jpg)

图4：vLLM 的第一轮处理

-   vLLM 的第二轮处理

由于 waiting 队列中还有一个请求 s2（The life is)，因此，vLLM 在第二轮只会处理这一个请求，因为前面提到，vLLM 只会处理要么都是填充阶段的请求，要么都是生成阶段的请求。如图 5 所示。

![](https://pic4.zhimg.com/v2-0b4062e6adf8ef821698e6364d507923_1440w.jpg)

图5：vLLM 的第二轮处理

-   vLLM 的第三轮处理

waiting 队列中没有要处理的新请求，所以会从 running 队列中选择此轮要处理的请求（这些请求均处于生成阶段）。但由于没有多余的空间，vLLM 只会选择 s0 和 s1 进行处理。

经过多轮调度和推理，最终完成 3 个请求的处理，以上就是 vLLM 的工作流。

对于 vLLM 架构以及工作流的介绍就暂告一段落了，接下来的文章会对 vLLM 的实现细节进行解读。

---

> **vLLM（知乎）系列导航**：[[vLLM 系列（知乎）索引|系列索引]] ｜ 上一篇：[[vLLM（一）PagedAttention 算法 - 知乎|一：PagedAttention 算法]] ｜ 下一篇：[[vLLM（三）源码安装与调试 - 知乎|三：源码安装与调试]]

