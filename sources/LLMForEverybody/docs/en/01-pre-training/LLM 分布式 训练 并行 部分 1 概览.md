---
aliases: ["llm-distributed-training-parallelism-part-1-overview"]
---

# LLM Distributed Training Parallelism, Part 1: Overview

## Introduction

> To train the largest Llama 3 model, Meta combined three parallelization methods: data parallelism, model parallelism, and pipeline parallelism. While training on 16K GPUs at once, their most efficient implementation reached more than 400 TFLOPS per GPU. Training runs were performed on two custom clusters with 24K GPUs each. To maximize GPU availability, they developed a new training stack that automatically detects, handles, and maintains failures. They also greatly improved hardware reliability and silent data corruption detection, and built a new scalable storage system that reduced checkpoint and rollback overhead. These improvements reduced total effective training time by more than 95% and improved Llama 3 training efficiency by about 3x compared with Llama 2.

![alt text](../../../01-第一章-预训练/assest/大模型分布式训练并行技术（一）概述/00.png)

Here Meta used three parallelization methods: data parallelism, model parallelism, and pipeline parallelism. These are key technologies in distributed LLM training. In this series, I will explain several such parallelism methods in detail.

The goal of the series is to explain distributed LLM training parallelism in the simplest possible way. We will not go too deep into implementation details, and will focus instead on the basic concepts.

## Parallelization Strategies

1. DataParallel (DP): the same configuration is copied several times, and each copy receives part of the data. Processing happens in parallel, and all copies synchronize at the end of each training step.

![alt text](../../../01-第一章-预训练/assest/大模型分布式训练并行技术（一）概述/0.png)

2. TensorParallel (TP): each tensor is split into several blocks. Instead of storing the whole tensor on one GPU, each tensor shard is placed on its own GPU. During processing, each shard is processed separately and in parallel on different GPUs, and results are synchronized at the end of the step. This is called horizontal parallelism because the split happens along a horizontal dimension.

![alt text](../../../01-第一章-预训练/assest/大模型分布式训练并行技术（一）概述/2.png)

3. PipelineParallel (PP): the model is split vertically by layers across several GPUs, so each GPU stores only one layer or a few layers of the model. Each GPU processes different pipeline stages in parallel and works on a small part of the batch.

![alt text](../../../01-第一章-预训练/assest/大模型分布式训练并行技术（一）概述/4.png)

4. MixedParallel (MP): an approach that combines data parallelism, model parallelism, and pipeline parallelism. It lets you run data parallelism and model parallelism across several GPUs at the same time, while also using pipeline parallelism inside each GPU group.

I plan to explain these parallelization methods in several articles. The next one is about data parallelism.

## References

<div id="refer-anchor-1"></div>

[1] [Llama 3 is out, the strongest open-source LLM: 15T pretraining data, largest model above 400B parameters](https://www.163.com/dy/article/J03PMO8I0531E3NX.html)

[2] [Model Parallelism](https://huggingface.co/docs/transformers/v4.15.0/en/parallelism)

## Author's GitHub and WeChat

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)


---

## 📚 相关概念

[[concepts/Transformer 架构|Transformer 架构]] | [[concepts/分词器 LLM|分词器 LLM]] | [[concepts/LLM 训练 流水线|LLM 训练 流水线]] | [[concepts/RLHF DPO 对齐|RLHF DPO 对齐]] | [[concepts/LoRA PEFT 微调|LoRA PEFT 微调]] | [[concepts/多模态 LLM|多模态 LLM]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[entities/Hugging Face|Hugging Face]] | [[entities/DeepSeek|DeepSeek]] | [[entities/mindspore Transformer|mindspore Transformer]] | [[sources/Vaswani 2017 Attention|Vaswani 2017 Attention]] | [[sources/LLM 训练 流水线 指南|LLM 训练 流水线 指南]] | [[sources/DeepSeek 4 技术|DeepSeek 4 技术]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：预训练
