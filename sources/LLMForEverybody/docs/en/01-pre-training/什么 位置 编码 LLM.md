---
aliases: ["what-is-positional-encoding-in-llms"]
---

# What Is Positional Encoding in LLMs?

## 1. What Is Positional Encoding?

Positional Encoding is a technique that gives a model information about the position of each element in a sequence when processing sequential data.

In natural language processing (`NLP`), especially when using the `Transformer` model, positional encoding is especially important because the `Transformer` architecture itself has no built-in mechanism for handling the order of sequence elements.

The main goal of positional encoding is to let the model distinguish word order in the input sequence, so it can better understand sentence structure and meaning.

![alt text](<../../../01-第一章-预训练/assest/什么是大模型的位置编码Position Encoding/1.PNG>)

## 2. Good Positional Encoding

- gives a unique code for each position;
- preserves the same difference between any two positions in sentences of different lengths;
- keeps code values bounded;
- has long-distance decay.

Long-distance decay in positional encoding means that as the relative distance between sequence elements grows, the influence of positional encoding on model quality gradually weakens. In theory, this is useful for a `Transformer` model because it imitates how human attention gradually diffuses when processing long text.

## 3. Types of Positional Encoding

Positional encoding is usually divided into two types: absolute positional encoding and relative positional encoding.

### Absolute Positional Encoding

This is the most common positional encoding method. Its core idea is to add a positional vector to each element of the input sequence, indicating that element's specific position in the sequence. This positional vector is usually generated with sine and cosine functions, has periodicity, and can capture relative position information in the sequence.

### Relative Positional Encoding

This encoding method focuses on distance information between elements. A positional bias is added to the self-attention mechanism, allowing the model to perceive relative positional relationships between elements. Common relative positional encoding methods include `Sinusoidal Positional Encoding` and `Learned Positional Encoding`: the first computes positional encoding with sine and cosine functions of different frequencies, while the second computes it through learnable parameters.

## 4. Implementing Absolute Positional Encoding

Absolute positional encoding is usually implemented with a combination of sine and cosine functions. This method was first proposed by Vaswani and coauthors in `Attention is All You Need`, and was later widely used in `Transformer` models.

Implementation usually includes these steps:

### 4.1 Generate the Positional Vector

Generate a positional vector for each position in the sequence. Its size usually matches the model's word embedding dimension.

### 4.2 Use Sine and Cosine Functions

For each position `pos` and each dimension index `i`:

when the dimension index is an **even dimension** (2i), use sin:

$PE(pos, 2i) = sin( pos / 10000^{(2i / d_{model})})$

when the dimension index is an **odd dimension** (2i+1), use cos:

$PE(pos, 2i+1) = cos( pos / 10000^{(2i / d_{model})})$

where:

- PE means positional encoding (`Positional Encoding`);
- pos is the position of the word in the sequence;
- d_model is the model dimension.

### 4.3 Add It to the Word Embedding

The computed positional vector is added to the corresponding word embedding vector. This way, each word embedding contains not only semantic information, but also positional information.

### 4.4 Train the Model

During training, the model learns to use these positional codes to better understand sequential data.

Absolute positional encoding lets the model capture relative position information in a sequence, which is critical for understanding language structure and performing tasks such as machine translation and text summarization. It helps the `Transformer` distinguish different meanings of the same word in different positions, improving model quality and accuracy.

## 5. FAQ on Absolute Positional Encoding

![alt text](<../../../01-第一章-预训练/assest/什么是大模型的位置编码Position Encoding/02.png>)

### Q1: Why use trigonometric functions?

A1: Sine and cosine are periodic functions and can capture relative position information between sequence elements. Their periodicity helps the model better understand positional relationships between sequence elements, improving model quality and accuracy.

### Q2: Why divide by 10000?

A2: Dividing by 10000 scales positional encoding values so different positions have a certain level of distinguishability. This helps the model tell elements in different positions apart. By changing the scaling coefficient 10000, you can control how sensitive the model is to distances between positions. A smaller scaling coefficient makes positional encoding more sensitive to distance, while a larger one makes the model sensitive to a broader range of positions.

### Q3: Why alternate sine and cosine?

A3: Alternating sine and cosine lets positional encoding represent position information in different dimensions. It gives the model more ways to learn relative position relationships.

## 6. Relative Positional Encoding

![alt text](<../../../01-第一章-预训练/assest/什么是大模型的位置编码Position Encoding/3.png>)

Key features of relative positional encoding:

- Sensitivity to relative positions: the encoding method lets the model consider not only interactions between elements when computing attention scores, but also their relative positions.
- Dynamic computation: relative positional codes are usually computed dynamically, meaning they are generated from the actual relative positions of elements in the input sequence.
- Attention mechanism extension: in self-attention, a bias related to relative position is usually added to the computed attention score; this bias can be a function of relative position.
- Different implementations: relative positional encoding can be implemented in different ways, such as through a predefined relative position matrix, learnable parameters, or more complex functions that capture relative distance.
- Better model quality: by considering relative positions between elements, relative positional encoding helps the model capture patterns and dependencies in sequential data, improving quality in some tasks.
- Suitable for long sequences: relative positional encoding is especially useful for long sequences because it lets the model understand sequence structure through relative positional relationships, without relying only on absolute positions.

## 7. Extrapolation

The extrapolation ability of positional encoding means how well a model can extend positional encoding and preserve quality when processing sequences at inference time that are longer than sequences seen during training.

![alt text](<../../../01-第一章-预训练/assest/什么是大模型的位置编码Position Encoding/04.png>)

In LLMs, due to GPU memory limits, the maximum sequence length set during pretraining is usually limited, for example around 4K. But during inference, the model may need to process longer sequences, such as 32K text. So suitable positional encoding is critical for improving the model's extrapolation ability on longer sequences.

## 8. Rotary Position Encoding, RoPE

**Rotary Position Encoding, RoPE**

RoPE was proposed to use relative position information between tokens. It assumes that the dot product between the query vector $q_m$ and key vector $k_n$ can be expressed by a function $g$, whose inputs are word embedding vectors $x_m$, $x_n$, and the relative position between them, $m-n$:

![alt text](<../../../01-第一章-预训练/assest/什么是大模型的位置编码Position Encoding/2.png>)

A bold hypothesis needs careful verification. Now our goal is to find a suitable function $g$, so that $g(x_m, x_n, m-n)$ can capture relative position information between word vectors.

RoPE proposes this: when the word vector is two-dimensional, the plane can be transformed into the complex plane. If we define function $f$ as follows, we can find the corresponding function $g$.

![alt text](<../../../01-第一章-预训练/assest/什么是大模型的位置编码Position Encoding/3.png>)

$Re$ means the real part of a complex number. The function $f$ can then be defined as:

![alt text](<../../../01-第一章-预训练/assest/什么是大模型的位置编码Position Encoding/4.png>)

Isn't the original query matrix being multiplied by a rotation matrix here? In other words, after adding positional information $m$, the RoPE scheme is equivalent to rotating the original query matrix. That is where the word **rotary** comes from.

Similarly, $f_K$ can be expressed as:

![alt text](<../../../01-第一章-预训练/assest/什么是大模型的位置编码Position Encoding/5.png>)

The corresponding function $g$ is:

![alt text](<../../../01-第一章-预训练/assest/什么是大模型的位置编码Position Encoding/6.png>)

## 9. From Two Dimensions to the Multidimensional Case

In the two-dimensional case, we introduced the complex plane to use the elegant mathematical properties of Euler's formula and simplify the process. In the multidimensional case, we can directly use matrix properties to simplify the process. To generalize two-dimensional RoPE to multidimensional RoPE, just replace the rotation matrix $R$ in two-dimensional RoPE with a multidimensional rotation matrix $R$.

![alt text](<../../../01-第一章-预训练/assest/什么是大模型的位置编码Position Encoding/7.png>)

Because the dot product has linear additivity, RoPE of any ***even dimension*** can be represented as a concatenation of two-dimensional cases.

That is, the rotation matrix $R^d_{\theta,m}$ is added to the original $q*k$ matrix. This is the idea of RoPE.

The original paper has an intuitive diagram:

![alt text](<../../../01-第一章-预训练/assest/什么是大模型的位置编码Position Encoding/2.png>)

## 10. Summary

Rotary position encoding was developed by the great **Su Jianlin**. He introduced one of the most beautiful formulas in mathematics, Euler's formula, into this design.

You can follow his blog `科学空间`: https://kexue.fm/. There is a lot to learn there.

Later, I will talk separately about Euler's formula and the idea behind RoPE.

## References

<div id="refer-anchor-1"></div>

[1] [Understand rotary encoding (RoPE) in ten minutes](https://hub.baai.ac.cn/view/29979)

[2] [The Transformer positional encoding that researchers keep puzzling over](https://kexue.fm/archives/8130)

[3] [Transformer development path: 2. Rotary positional encoding, combining the strengths of different approaches](https://kexue.fm/archives/8265)

[4] [Transformer study notes, part 1: Positional Encoding](https://zhuanlan.zhihu.com/p/454482273)

[5] [RoFormer: Enhanced Transformer with Rotary Position Embedding](https://arxiv.org/abs/2104.09864)

[6] [GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)


---

## 📚 相关概念

[[concepts/Transformer 架构|Transformer 架构]] | [[concepts/分词器 LLM|分词器 LLM]] | [[concepts/LLM 训练 流水线|LLM 训练 流水线]] | [[concepts/RLHF DPO 对齐|RLHF DPO 对齐]] | [[concepts/LoRA PEFT 微调|LoRA PEFT 微调]] | [[concepts/多模态 LLM|多模态 LLM]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[entities/Hugging Face|Hugging Face]] | [[entities/DeepSeek|DeepSeek]] | [[entities/mindspore Transformer|mindspore Transformer]] | [[sources/Vaswani 2017 Attention|Vaswani 2017 Attention]] | [[sources/LLM 训练 流水线 指南|LLM 训练 流水线 指南]] | [[sources/DeepSeek 4 技术|DeepSeek 4 技术]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：预训练
