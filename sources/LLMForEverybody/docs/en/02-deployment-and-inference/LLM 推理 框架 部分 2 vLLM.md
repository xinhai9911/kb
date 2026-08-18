---
aliases: ["llm-inference-frameworks-part-2-vllm"]
---

Large-model inference frameworks, part 2: vLLM

`vLLM`[1](#refer-anchor-1) is an inference framework based on PagedAttention. It provides efficient, fast, low-cost LLM serving through paged processing of attention computation. During inference, vLLM splits attention computation into several pages, each computing only part of the attention distribution. This reduces computation and memory requirements and improves inference efficiency.

## 1. PagedAttention

The performance bottleneck of LLM serving is memory, meaning GPU memory. During autoregressive decoding, all input tokens of the LLM create their attention key and value tensors. These tensors are stored in GPU memory for generating the next tokens. Such cached key and value tensors are usually called KV Cache. KV Cache has the following features:

- Large size: in LLaMA-13B, one sequence can take up to 1.7 GB.
- Dynamic shape: size depends on sequence length, and sequence length varies a lot and is unpredictable. So efficient KV Cache management is a serious challenge. Existing systems lose 60% to 80% of memory because of fragmentation and excessive reservation.

To solve this problem, vLLM introduced PagedAttention, an attention algorithm inspired by classic virtual memory and paging ideas in operating systems. Unlike traditional attention algorithms, PagedAttention allows contiguous keys and values to be stored in non-contiguous memory regions. More specifically, PagedAttention splits each sequence's KV Cache into blocks, and each block contains keys and values for a fixed number of tokens. During attention computation, the PagedAttention kernel efficiently finds and fetches these blocks.

![PagedAttention: KV Cache is split into blocks. Blocks do not have to be contiguous in memory.](../../../02-第二章-部署与推理/assest/大模型推理框架（二）vLLM/0.gif)

Since blocks do not have to be contiguous in memory, keys and values can be managed more flexibly, like virtual memory in an operating system: blocks can be viewed as pages, tokens as bytes, and sequences as processes. A sequence's contiguous ***logical blocks*** are mapped through a **block table** to non-contiguous ***physical blocks***. Physical blocks are allocated as needed when new tokens are generated.

![Example generation process for a request sampling multiple outputs](../../../02-第二章-部署与推理/assest/大模型推理框架（二）vLLM/1.gif)

In PagedAttention, memory loss happens only in the last block of a sequence. In practice, this gives almost optimal memory usage: the waste ratio is below 4%. The memory-efficiency improvement is very useful: it lets the system batch more sequences, improves GPU utilization, and significantly increases throughput, as shown in the performance results above.

PagedAttention has another key advantage: efficient memory sharing. For example, with parallel sampling, the same prompt generates several output sequences. In that case, computation and memory for the prompt can be shared across output sequences.

![Example of parallel sampling](../../../02-第二章-部署与推理/assest/大模型推理框架（二）vLLM/2.gif)

PagedAttention naturally implements memory sharing through the block table. Similar to how processes share physical pages, different sequences in PagedAttention can share blocks by mapping their logical blocks to the same physical block. To make sharing safe, PagedAttention tracks reference counts for physical blocks and implements copy-on-write.

![Example generation process for a request sampling multiple outputs](../../../02-第二章-部署与推理/assest/大模型推理框架（二）vLLM/3.gif)

PagedAttention's memory-sharing feature greatly reduces memory overhead for complex sampling algorithms such as parallel sampling and beam search: memory usage can drop by up to 55%. This can turn into up to 2.2 times higher throughput. Because of that, these sampling methods become practical for LLM services.

PagedAttention is the key technology behind vLLM. vLLM is an LLM inference and serving engine that supports many models, offers high performance, and has a convenient interface.

## 2. Other vLLM Features

Besides the **PagedAttention algorithm**, vLLM uses a set of optimizations that make large language models efficient to deploy in production environments. Some key vLLM features are:

1. **PagedAttention algorithm**: vLLM uses the new PagedAttention algorithm, which efficiently manages key and value memory in the attention mechanism, reduces GPU memory usage, and improves model throughput.

2. **Multi-GPU support**: vLLM supports multi-GPU systems, can efficiently distribute workload, reduce bottlenecks, and increase overall system throughput.

3. **Continuous batching**: vLLM supports continuous batching and can dynamically allocate tasks. This is especially useful in environments with fluctuating workload, because it reduces idle time and improves resource-management efficiency.

4. **Speculative decoding**: vLLM optimizes latency for chatbots and real-time text generators by pre-generating and verifying possible future tokens, reducing LLM inference time.

5. **Optimized memory usage**: the embedding layer in vLLM is deeply optimized for memory efficiency, providing balanced and efficient GPU memory usage in LLMs and solving memory-resource problems for most LLMs, such as ChatGPT, without performance loss.

6. **LLM adapters**: vLLM supports integration with LLM adapters, letting developers fine-tune and customize LLMs without retraining the whole system.

7. **Seamless HuggingFace model integration**: users can directly use vLLM with HuggingFace models for inference and serving without extra development work.

8. **Distributed inference support**: vLLM supports tensor parallelism and pipeline parallelism, giving users a flexible and efficient solution.

9. **OpenAI API compatibility**: vLLM is compatible with the OpenAI API interface, making it easier to integrate into existing systems.

10. **Quantization support**: vLLM supports int8 quantization, reduces model size, improves inference speed, and helps deploy large language models on resource-constrained devices.

## References

<div id="refer-anchor-1"></div>

[1] [vLLM](https://docs.vllm.ai/en/latest/)

<div id="refer-anchor-2"></div>

[2] [vllm-project](https://github.com/vllm-project/vllm)

## Welcome to my GitHub and WeChat account [The Real Ship of Theseus]: no time to explain, come aboard!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

The repository has the original Markdown files, and the project is fully open source. Stars and forks are very welcome.


---

## 📚 相关概念

[[concepts/LLM 推理 优化|LLM 推理 优化]] | [[concepts/推测解码|推测解码]] | [[concepts/分布式推理|分布式推理]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[concepts/LLM 应用 生态|LLM 应用 生态]] | [[entities/vllm|vllm]] | [[entities/tensorrt-llm|tensorrt-llm]] | [[entities/sglang|sglang]] | [[entities/Hugging Face|Hugging Face]] | [[concepts/LLM 推理 优化|LLM 推理 优化]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：部署与推理
