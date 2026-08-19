---
aliases: ["why-output-tokens-cost-more-than-input-tokens-in-llms"]
---

## Introduction

In recent years, prices for many commercial large models have kept falling. But have you noticed an important detail: output tokens are usually several times more expensive than input tokens. Why? In this article, we will look at the token generation mechanism in large models and explain why output tokens cost more.

![Image description](https://i-blog.csdnimg.cn/direct/36772da353dd4d12b04a177dd908d864.png)

## Large-Model Inference Mechanism

With KV cache (key-value cache), token generation in a large model is split into two stages:

### Prefill

During prefill, the model processes the input prompt, meaning the input tokens, in parallel and creates the KV cache. This step includes one full forward pass and outputs the first token. The time of this process is mostly determined by the input tokens, because the model needs to run a full calculation to initialize the whole generation process.

### Decoding

Decoding is the process of generating the next token one by one. At this step, the number of output tokens determines how many forward passes need to run. Although each forward pass is faster thanks to KV cache, the model still has to compute repeatedly, gradually generating each following token.

## Influencing Factors

Many factors affect large-model generation. They determine not only token generation efficiency, but also cost:

### Input Token

1. **Prefill time**: input tokens determine the time of the prefill stage, meaning the time to generate the first token. This process is computed only once.
2. **Lower bound of GPU memory usage**: input tokens determine the minimum GPU memory occupied by KV cache, because they create the basis for later token generation.
3. **Base generation speed**: input tokens also set the base generation speed starting from the second token and affect the efficiency of later computation.

### Output Token

1. **Decoding duration**: output tokens determine the duration of the decoding stage. Thanks to KV cache, each computation is much faster than for the first token, but many forward passes are still required.
2. **Upper bound of GPU memory usage**: output tokens determine the maximum GPU memory occupied by KV cache, because as each new token is generated, the amount of information in the cache also grows.

## Which Cost Is Higher?

What is more expensive: one full forward pass, determined by the number of input tokens, or many forward passes using KV cache, determined by the number of output tokens?

![Image description](https://i-blog.csdnimg.cn/direct/e76239e525c743d091994be740f631e5.png)

### Compute and Communication Bottlenecks

Although KV cache effectively reduces computation at each step, communication bandwidth has not improved as fast as compute power, so GPUs have become more sensitive to IO. Generating each output token still requires repeated forward passes, and GPU IO limits make each output token more expensive. This also explains why output tokens cost more than input tokens.

## Conclusion

Another useful fact for the pocket. Now you can casually bring it up with friends.

## References

- [1] [GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)


---

## 📚 相关概念

[[sources/推理引擎/LLM 推理 优化|LLM 推理 优化]] | [[sources/推理引擎/推测解码|推测解码]] | [[sources/推理引擎/分布式推理|分布式推理]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[concepts/LLM 应用 生态|LLM 应用 生态]] | [[sources/推理引擎/vllm|vllm]] | [[sources/推理引擎/tensorrt-llm|tensorrt-llm]] | [[sources/推理引擎/sglang|sglang]] | [[entities/Hugging Face|Hugging Face]] | [[sources/推理引擎/LLM 推理 优化|LLM 推理 优化]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：部署与推理
