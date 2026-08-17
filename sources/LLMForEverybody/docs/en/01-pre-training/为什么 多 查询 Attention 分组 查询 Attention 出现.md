---
aliases: ["why-multi-query-attention-and-grouped-query-attention-appeared"]
---

## Introduction

If you look at the GPT series papers, the self-attention you study there is **Multi-Head Attention** (MHA).
MHA contains $h$ Query, Key, and Value matrices, and the Key and Value matrix weights are not shared across attention heads.

This mechanism already captures information well. So why did MQA and GQA appear later?

Many articles immediately show the mathematical differences between these three attention mechanisms, but they do not explain why MQA, and even GQA, were needed when MHA already existed. This article gives a short explanation and an intuitive picture.

![alt text](<../../../01-第一章-预训练/assest/为什么会发展出Multi Query Attention和Group Query Attention/1.PNG>)

## KV Cache

As large models gained more parameters, inference speed also became a serious challenge. So people started using KV Cache, trying to trade space for time.

> article about KV cache

## MQA

But after memory usage increased, VRAM itself became the problem. Researchers then tried sharing keys and values inside the attention mechanism to reduce KV Cache content.
That is how Multi-Query Attention (MQA) appeared: there are still multiple queries, but only one set of keys and values, and all queries use that shared set. Because of this, KV Cache becomes smaller.

## GQA

The drawback of MQA is that it causes an accuracy drop, so researchers proposed a compromise: not all queries share one common KV set. Instead, queries inside one group share one common KV set. This reduces KV Cache while helping preserve accuracy. That is how Grouped-Query Attention appeared.

## References

<div id="refer-anchor-1"></div>

[1] [GQA: Training Generalized Multi-Query Transformer Models from Multi-Head Checkpoints](https://arxiv.org/pdf/2305.13245)

[2] [GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)
