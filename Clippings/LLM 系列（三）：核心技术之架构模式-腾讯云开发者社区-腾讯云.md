---
title: "LLM系列（三)：核心技术之架构模式"
source: "https://cloud.tencent.com/developer/article/2532151"
author: "磊叔的技术博客"
published: "2025-06-16"
created: 2026-08-19
description: "在现代人工智能领域，一个基本信念推动着技术的前沿发展：模型规模、数据量和计算资源的持续扩大，能够带来性能的显著提升和涌现能力（Emergent Capabilities）"
tags:
  - "clippings"
  - "LLM 系列"
series: "LLM 系列"
part: "3"
---
## **引言：对规模的无尽探索**

在现代[人工智能](https://cloud.tencent.com/developer/techpedia/1500?from_column=20065&from=20065)领域，一个基本信念推动着技术的前沿发展：_模型_规模、数据量和计算资源的持续扩大，能够带来性能的显著提升和**涌现能力（Emergent Capabilities）**。这一\*\*规模法则（Scaling Law）\*\*已成为训练更强大语言_模型_的黄金准则。为了实现这一目标，业界逐渐分化出两种核心的架构哲学，它们代表了通往通用人工智能（AGI）的两条不同路径。

第一种是**稠密（Dense）架构**。这是一种“蛮力”方法，每一次计算都会动用_模型_中的每一个参数。它体现了一种集中式、整体化的智能哲学，即通过一个巨大而统一的_神经网络_来处理所有任务。

第二种是**混合专家（Mixture of Experts, MoE）架构**。这是一种`稀疏`或`条件化计算`（Conditional Computation）的方法，对于任意给定的输入，只有_模型_中的一小部分参数会被激活。它体现了一种分布式、专业化的智能哲学，即通过一个由众多“专家”组成的委员会来协同解决问题 。

本文将对这两种主流范式进行一次权威且深入的比较分析，系统性地剖析它们的技术基础、实践中的权衡，以及对未来人工智能发展的战略性影响。

![图片](https://mmbiz.qpic.cn/sz_mmbiz_png/zZ2u0norYEpBjarAMF9r9hibtI3XPzQRN9Cbgy8cJMUVl4BQc0vLwU3ZMc4a4X401Ec9rCBI8OmTCwCuu4dQrcA/640?wx_fmt=png&from=appmsg&watermark=1&tp=webp&wxfrom=5&wx_lazy=1)

图片

## **1、Dense Transformer 架构：集中式力量的基石**

`Dense Transformer` _模型_是现代大型语言_模型_（LLM）的起点，其设计理念直接继承自开创性的`Attention Is All You Need`论文，强调通过一个整体网络处理信息。

#### **1.1 架构蓝图：“全参数激活”范式**

`Dense Transformer` 的核心在于其**全参数激活**的工作模式，即在处理序列中的每一个令牌（token）时，_模型_的所有参数都会参与前向传播计算。其基本构成模块包括：

-   • **输入/输出嵌入与位置编码（Input/Output Embeddings & Positional Encoding）**：这是将文本（单词或子词）转换为_模型_能够理解的数值向量（嵌入）的第一步。由于 Transformer 结构本身不具备处理序列顺序的能力，因此必须加入位置编码，为每个令牌注入其在序列中的位置信息。
-   • **多头自注意力机制（Multi-Head Self-Attention, MHSA）**：这是 Transformer 的核心，它允许_模型_在处理一个令牌时，动态地衡量序列中所有其他令牌的重要性，从而捕捉丰富的上下文依赖关系。通过并行运行多个“注意力头”，_模型_可以从不同的表示子空间中学习信息。
-   • **前馈网络（Feed-Forward Network, FFN）**：在注意力机制捕获了上下文信息之后，每个令牌的表示向量都会被送入一个前馈网络进行深度处理和非线性变换。在稠密_模型_中，这是一个由两个线性层和一个非线性激活函数（如 ReLU 或 GeLU）组成的、尺寸巨大的多层感知机（MLP）。至关重要的是，在每一层中，所有令牌都经过同一个 FFN。

这种设计的本质是信息的无差别、最大化流动。每一个参数都对最终输出有潜在贡献，这保证了_模型_强大的表示能力，但代价是巨大的计算资源消耗。

![图片](https://mmbiz.qpic.cn/sz_mmbiz_png/zZ2u0norYEpBjarAMF9r9hibtI3XPzQRNYbAFbIu9MRDBNQ2wtPzqUL2tvOBJh9ia9yic32ialzcxvkIn40DnEvRzQ/640?wx_fmt=png&from=appmsg&watermark=1&tp=webp&wxfrom=5&wx_lazy=1)

图片

#### **1.2 规模化的困境：高昂的推理成本与横向扩展挑战**

这部分将直接回应一个核心问题：为什么稠密_模型_推理成本高，且难以进行横向扩展？

-   • **计算成本（FLOPs）**：稠密_模型_的计算成本（以浮点运算次数 FLOPs 衡量）与其参数量成正比。当_模型_规模增长到千亿级别时，例如拥有 1750 亿参数的 GPT-3 2，完成一次前向传播所需的计算量是惊人的。每一次的输入都需要驱动这 1750 亿个参数进行运算，导致训练和推理的成本都极为高昂。
-   • **内存成本（VRAM）**：更大的挑战_来自_于内存。_模型_的所有权重、优化器状态（在训练时）以及中间计算产生的激活值都必须加载到 GPU 的显存（VRAM）中。一个 1750 亿参数的 16 位精度_模型_，仅加载权重就需要 350 GB 的显存，这远远超出了任何单块消费级或企业级 GPU 的容量。

![图片](https://mmbiz.qpic.cn/sz_mmbiz_png/zZ2u0norYEpBjarAMF9r9hibtI3XPzQRN5R8vibvr95frJTUDiaOvKxvYuZW1CCf6tCiaQWJibx12LPGU7mBj52MafQ/640?wx_fmt=png&from=appmsg&watermark=1&tp=webp&wxfrom=5&wx_lazy=1)

图片

-   • **_模型_并行的必要性**：为了克服单 GPU 的内存瓶颈，必须将一个巨大的稠密_模型_`分片`（Shard）或`分区`（Partition），部署到多张 GPU 上协同工作。这就是大_模型_横向扩展的核心技术——_模型_并行（Model Parallelism）。主要有两种策略：
    -   • **流水线并行（Pipeline Parallelism, PP）**：将_模型_的不同层（Layers）顺序地分配到不同的 GPU 上。例如，GPU 1 负责 1-24 层，GPU 2 负责 25-48 层，以此类推，形成一条“流水线”。这是一种 **层间并行**（Inter-layer Parallelism）策略。
    -   • **张量并行（Tensor Parallelism, TP）**：将单个层内部的巨大权重矩阵（例如 FFN 或注意力中的线性层）沿特定维度切分到不同的 GPU 上。每个 GPU 只负责计算矩阵的一部分，然后通过通信操作将结果合并。这是一种 **层内并行**（Intra-layer Parallelism）策略。
-   • **横向扩展的“难点”**：真正的挑战在于这些并行策略引入了巨大的**通信开销**。张量并行在每次计算后都需要进行 `AllReduce` 这样的集合通信操作，以确保所有 GPU 上的张量分片能够同步并合并成完整的结果。这要求 GPU 之间有极高带宽的互联（如 NVIDIA 的 NVLink）。而流水线并行则会产生`流水线气泡`（Pipeline Bubbles）——在每个批次处理的开始和结束阶段，流水线中的部分 GPU 会处于空闲等待状态，这降低了硬件的整体利用率。为了高效训练，通常需要将数据并行（Data Parallelism）、流水线并行和张量并行结合起来，形成复杂的 2D 或 3D 并行策略，这不仅对硬件互联要求极高，也给工程实现带来了巨大的复杂性。

正是由于稠密_模型_在规模化过程中遇到的这些严峻的工程和成本挑战，才为其他更高效的架构创新铺平了道路。这种内在的压力催生了对一种新范式的需求：一种能够在不按比例增加计算成本的情况下，有效扩大_模型_容量的架构。这为混合专家（MoE）_模型_的复兴和现代化改造创造了绝佳的条件。

#### **1.3 稠密范式的典范_模型_**

-   • **OpenAI GPT-3**：作为证明了大规模稠密_模型_可行性的里程碑，GPT-3 以其 1750 亿的庞大参数量，展示了惊人的小样本（few-shot）和零样本（zero-shot）学习能力，为后续的 LLM 发展设定了标杆。其架构是经典的仅解码器（decoder-only）稠密 Transformer。
-   • **Meta Llama 2**：这是一个由 Meta 推出的开源稠密_模型_家族（参数规模从 70 亿到 700 亿不等），极大地推动了高性能 LLM 的普及。它遵循标准的自回归稠密 Transformer 架构，但引入了如 SwiGLU 激活函数和旋转位置编码（RoPE）等关键改进，提升了_模型_的性能和效率。

## **2、混合专家（MoE）架构：稀疏专业化的范式**

面对稠密_模型_高昂的扩展成本，混合专家（MoE）架构作为一种替代方案应运而生。它借鉴了`分而治之`的思想，通过条件化计算，实现了_模型_容量与计算成本的解耦。

![图片](https://mmbiz.qpic.cn/sz_mmbiz_png/zZ2u0norYEpBjarAMF9r9hibtI3XPzQRNq8arCd8qYuN6thr0B0Nw2fuv3XDO3yYRnnqib6o7Jia9xjWWOZ2iagQWA/640?wx_fmt=png&from=appmsg&watermark=1&tp=webp&wxfrom=5&wx_lazy=1)

图片

#### **2.1 架构蓝图：实践中的条件化计算**

MoE 架构的核心创新在于，它用一个**稀疏 MoE 层**替换了标准 Transformer 模块中的**稠密 FFN 子层**。这个 MoE 层主要由两个部分构成：

-   • **专家网络（Experts）**：一组并行的、结构独立的前馈网络（FFN）。每个专家都可以被看作是一个专门处理特定类型信息或模式的“专家” 。
-   • **门控网络（Gating Network）或****路由器****（Router）**：这是一个小型的、可训练的_神经网络_。它的作用是为输入的每一个令牌动态地决定应该将其发送给哪个（或哪些）专家进行处理。路由器会为每个令牌计算出一个在所有专家上的概率分布，并通常选择得分最高的 `top-k` 个专家（在现代_模型_中 `k` 通常为 1 或 2）来激活。

**条件化计算**是 MoE 的灵魂。对于每个令牌，_模型_不再激活全部参数，而是有条件地只激活一小部分——即被路由器选中的 `k` 个专家。因此，整个计算过程是**稀疏**的。MoE 层的最终输出是所有被激活专家输出的加权和，权重由路由器的打分决定 。

#### **2.2 稀疏性的经济学：解构更低的计算成本**

**这部分将详细解释为什么 MoE 架构在计算上更“便宜”。**

关键在于区分\*\*总参数量（Total Parameters）\*\*和 **激活参数量（Active Parameters）**。一个 MoE _模型_可以拥有巨大的总参数量（所有专家参数与共享参数之和），但在处理任何一个令牌时，它实际使用的只是激活参数量，即被选中的少数专家的参数。

以 **Mixtral 8x7B** 为例，这个_模型_完美地诠释了这一概念。它拥有 8 个专家，每个专家的参数规模约为 70 亿。然而，它的路由器在每一层为每个令牌只选择 2 个专家进行计算。这意味着，尽管其总参数量高达约 470 亿（考虑到各层共享的注意力模块等），但每个令牌在前向传播中实际参与计算的参数量仅为约 130 亿。

**这对成本和速度意味着什么？_模型_的训练和推理所需的计算量（FLOPs）是由激活参数量**决定的，而非总参数量。因此，**Mixtral 8x7B** 能够以一个 130 亿参数稠密_模型_的速度和成本进行训练和推理，同时却可能拥有一个 470 亿参数_模型_的知识容量和性能。这就是 MoE 架构最根本的经济优势。

这种架构的成功，标志着对 **大_模型_** 概念的认知转变。它成功地将_模型_的**知识容量**（与总参数量相关）与**计算成本**（与激活参数量相关）分离开来。这预示着未来的_模型_发展可能不再仅仅依赖于构建越来越庞大的稠密网络，而是转向设计更智能的路由机制和更专业的专家网络，在稀疏的框架内实现性能的飞跃。研究的重心正从单纯的扩大规模，转向提升参数的使用效率。系统的智能越来越多地体现在路由决策本身，而不仅仅是专家网络中。

![图片](https://mmbiz.qpic.cn/sz_mmbiz_png/zZ2u0norYEpBjarAMF9r9hibtI3XPzQRNAQsWicVV31W9kKOsdUlWlPV3Xz3Bp6YEGJR2TibOpmibAy4RvCwiaeiawvg/640?wx_fmt=png&from=appmsg&watermark=1&tp=webp&wxfrom=5&wx_lazy=1)

图片

#### **2.3 MoE 范式的典范_模型_**

-   • **Mistral AI Mixtral 8x7B**：这款_模型_将高性能、开源的 MoE 带入了主流视野。它采用 Top-2 路由策略，在多个基准测试中表现优于体量远大于它的 Llama 2 70B 稠密_模型_，有力地验证了稀疏 MoE（SMoE）方法的有效性。
-   • **xAI Grok-1**：这是一个拥有 3140 亿总参数的巨型 MoE _模型_，包含 8 个专家，同样采用 Top-2 路由策略（激活 25% 的权重，即 8 个专家中的 2 个）。它的开源进一步凸显了业界向大规模稀疏_模型_发展的趋势。
-   • **_DeepSeek_\-MoE**：代表了下一代 MoE 架构的探索方向。它引入了两项关键创新以提升专家的专业化程度：
    -   • 1）**细粒度专家（Fine-grained Experts）**，即将 FFN 拆分成更多、更小的专家，以实现更精细的知识划分；
    -   • 2）**共享专家（Shared Experts）**，即设置一个所有令牌都必须经过的小型稠密 FFN，用于处理通用知识（如语言结构），从而让被路由的专家能更专注于特定领域的知识。这是一种旨在克服 MoE 核心缺陷的混合式设计。

## **3、稀疏性的挑战：MoE 实施中的关键难题**

尽管 MoE 架构在计算效率上优势显著，但它也引入了一系列独特的工程挑战，尤其是在[负载均衡](https://cloud.tencent.com/developer/techpedia/1093?from_column=20065&from=20065)、训练稳定性和内存管理方面。

#### **3.1 负载均衡的困境**

这是 MoE 架构中最核心的挑战之一。

-   • **问题所在**：门控网络（路由器）的训练目标是最小化_模型_的整体损失。因此，它会很快`“学会”`将令牌发送给当前表现最好的专家。这就形成了一个“富者愈富”的恶性循环：被偏爱的专家获得更多的训练样本，从而变得更强，于是更频繁地被选中。而其他专家则因为得不到足够的训练样本（`“饥饿”`状态）而逐渐退化，最终变得无用，这完全违背了设置多个专家的初衷。这种不均衡会导致部分持有`“冷门”`专家的 GPU 资源被闲置，严重影响训练效率。
-   • **解决方案：辅助负载均衡损失（Auxiliary Load-Balancing Loss）**：为了解决这个问题，研究者在_模型_的主损失函数之外，额外增加了一个**辅助损失项**。这个损失函数的目标是鼓励令牌在所有专家之间均匀分布。如果路由器将过多的令牌分配给少数几个专家，该损失项就会产生一个惩罚信号，迫使路由器调整其路由策略，从而实现更均衡的负载。
-   • **其他缓解技术**：
    -   • **带噪声的 Top-k 门控（Noisy Top-k Gating）**：在路由器的 logits 输出上增加少量高斯噪声，然后再选择 top-k 专家。这种随机性有助于打破固化的路由模式，鼓励对不同专家的探索。
    -   • **专家容量（Expert Capacity）**：为每个专家设定一个在单批次中能够处理的令牌数量上限。如果一个令牌被路由到的首选专家都已满载，该令牌将被视为“溢出”（overflow），并通过残差连接直接传递到下一层，从而防止任何一个专家被过多任务压垮。

#### **3.2 对训练稳定性的追求**

MoE _模型_因其训练过程的脆弱性而闻名。

![图片](https://mmbiz.qpic.cn/sz_mmbiz_png/zZ2u0norYEpBjarAMF9r9hibtI3XPzQRNwYQibluCGaMXKibwEuJxdC11owKhWmrGsyZbuv1TNeIleyXRehhCnTeQ/640?wx_fmt=png&from=appmsg&watermark=1&tp=webp&wxfrom=5&wx_lazy=1)

图片

-   • **问题所在**：MoE _模型_在训练和微调过程中极易出现不稳定现象。这种不稳定性源于多个因素：路由器的计算可能会产生数值非常大的 logits，而这些 logits 又被输入到指数函数（Softmax）中，导致数值上的微小误差被急剧放大，最终可能引发梯度爆炸或消失，使训练崩溃。此外，辅助负载均衡损失有时会与主任务损失产生冲突的梯度信号，进一步加剧了训练的不稳定性。
-   • **解决方案：路由器 Z-loss（Router Z-loss）**：为了稳定训练过程，ST-MoE 论文提出了一种名为“Router Z-loss”的正则化项。它通过惩罚路由器产生的大数值 logits，鼓励其输出保持在较小的范围内。这有效地减少了计算过程中的舍入误差，从而显著提升了训练的稳定性，且不会牺牲_模型_质量。
-   • **其他缓解技术**：在实践中，工程师还会采取混合精度训练策略，例如，使用 32 位浮点数（float32）来训练对精度敏感的路由器，而专家网络则使用 16 位脑浮点数（bfloat16）以节省资源。同时，在 MoE 层中引入 Dropout 等技术也能在一定程度上提升稳定性。

#### **3.3 VRAM 的悖论：计算廉价，内存昂贵**

MoE _模型_存在一个看似矛盾的特性：**它在计算上是高效的，但在内存上却是贪婪的**。

-   • **问题所在**：虽然在处理每个令牌时只使用了 `k` 个专家，但在_模型_运行时，**所有专家**的参数都必须完整地加载到 GPU 的 VRAM 中。以 Mixtral 8x7B 为例，尽管它的计算量相当于一个 130 亿参数的_模型_，但它需要足够的 VRAM 来容纳一个 470 亿参数的完整_模型_ 9。这对部署环境的硬件配置提出了极高的要求。
-   • **解决方案：专家并行（Expert Parallelism, EP）**：这是针对 MoE 架构最自然的并行策略。与切分_模型_的层（PP）或张量（TP）不同，专家并行直接将**不同的专家**分配到不同的 GPU 上。例如，对于一个拥有 8 个专家的_模型_和 8 张 GPU，每张 GPU 可以独立承载一个专家。当一个令牌需要被路由到位于另一张 GPU 上的专家时，系统会使用 `All-to-All` 集合通信操作，将该令牌的数据发送到目标 GPU，计算完成后再将结果传回。这是一种高效利用多 GPU 内存空间的策略。
-   • **新的权衡**：专家并行虽然有效解决了内存容量问题，但它也引入了新的通信瓶颈。`All-to-All` 通信的开销相当可观，并且如果专家负载不均，会导致持有“冷门”专家的 GPU 处于空闲状态，造成资源浪费。这与稠密_模型_并行所面临的通信模式和挑战截然不同。

## **4、综合分析**

在深入剖析了稠密 Transformer 和 MoE 两种架构的内部机制与挑战后，本节将进行全面的对比总结，并探讨未来的发展趋势。

#### **4.1 全面比较分析**

下表提供了一个直观的、多维度的对比，旨在帮助从业者在架构选型时快速评估其优劣与权衡。

-   • **表1：稠密 Transformer 与混合专家（MoE）架构对比分析**

![图片](https://mmbiz.qpic.cn/sz_mmbiz_png/zZ2u0norYEpBjarAMF9r9hibtI3XPzQRNjsvklQGq6DdWHhlGpuf0jPu7kzPKsRoAhaP6hXXBjPKVWtEDtoKtVQ/640?wx_fmt=png&from=appmsg&watermark=1&tp=webp&wxfrom=5&wx_lazy=1)

图片

-   • 国外代表_模型_

![图片](https://mmbiz.qpic.cn/sz_mmbiz_png/zZ2u0norYEpBjarAMF9r9hibtI3XPzQRNP7EYVAiaRLjcPZtkC2Via1rGf6gtLe8pJtW4UEzqkYjFpcSnf1mqKQeA/640?wx_fmt=png&from=appmsg&watermark=1&tp=webp&wxfrom=5&wx_lazy=1)

图片

-   • 国内代表_模型_

![图片](https://mmbiz.qpic.cn/sz_mmbiz_png/zZ2u0norYEpBjarAMF9r9hibtI3XPzQRNpDbbWvVs7EhibdveEfwbE3gxzHWUxkSSRCHNGHicEnDBiaOhEfTG3OU2A/640?wx_fmt=png&from=appmsg&watermark=1&tp=webp&wxfrom=5&wx_lazy=1)

图片

#### **4.2 通才 vs. 专才：一种功能性视角**

从功能角度看，稠密_模型_和 MoE _模型_代表了两种不同的知识组织方式。

![image-20250616104847664](https://mmbiz.qpic.cn/sz_mmbiz_png/zZ2u0norYEpBjarAMF9r9hibtI3XPzQRNzickJ9QqicoBeianN6C2b2rAnVx9vNkUYJyWkgxesicoeOWicw1TVkEE1Lw/640?wx_fmt=png&from=appmsg&watermark=1&tp=webp&wxfrom=5&wx_lazy=1)

image-20250616104847664

image-202506161048476_64_

-   • **稠密_模型_：一个通才大脑**。知识被弥散地存储在所有参数中。_模型_通过一个庞大而统一的_神经网络_来解决所有问题，类似于一个知识渊博的通。
-   • **MoE** **_模型_：一个专家委员会**。知识被模块化地存储在各个专家网络中。路由器则扮演了“调度员”的角色，根据问题的性质，将其分派给最合适的专家（或专家小组）来处理 。

然而，这种界限并非绝对。一些研究（如“MoEfication”）发现，即使是稠密的 FFN，在训练后其内部也可能自发地形成稀疏的激活模式，表现得像一个隐式的 MoE 。这表明，专业化分工可能是[_深度学习_](https://cloud.tencent.com/developer/techpedia/1507?from_column=20065&from=20065)系统的一种内在涌现属性，而 MoE 架构只是将这种属性显式化、结构化了。这一视角对于_模型_的可解释性研究以及未来对特定专家进行定向微调具有重要启示。

![图片](https://mmbiz.qpic.cn/sz_mmbiz_png/zZ2u0norYEpBjarAMF9r9hibtI3XPzQRNBAgER7NCePWOy1LR2RiaVe7IaDrrNo40OJiahXicXflYGuhOCUvvvUODg/640?wx_fmt=png&from=appmsg&watermark=1&tp=webp&wxfrom=5&wx_lazy=1)

图片

#### **4.3 前路在何方：混合化与融合**

展望未来，LLM 架构的发展路径可能并非在纯粹的稠密和纯粹的 MoE 之间做出二元选择，而是走向一种融合二者之长的**混合式架构**。

-   • **混合化趋势**：这种趋势已经在最新的_模型_设计中显现。例如：
    -   • **Snowflake Arctic**：该_模型_在架构中明确地将一个标准的稠密 Transformer 模块与一个残差连接的 MoE 组件结合起来。
    -   • **_DeepSeek_\-MoE**：其设计的“共享专家”本质上就是一个小型的稠密 FFN，所有令牌都需经过它来学习通用知识，而更大规模的“路由专家”则负责处理专业化知识。

这种融合代表了业界对架构权衡的成熟理解。稠密组件可以为_模型_提供一个鲁棒的、通用的知识基础，而稀疏的 MoE 组件则提供了一种计算高效的方式来扩展_模型_的专业知识容量。未来的核心挑战将在于如何智能地设计这些混合系统，以在性能、成本和效率之间找到最佳的平衡点，从而持续推动人工智能能力的边界。

![](https://mmbiz.qlogo.cn/mmbiz_png/ZwdQSEf4Sx4YO0e0vSjyYO9ujj0j5Qze8Sr2augOQVbo9bia3EFw6t0ibV4EjN1rdvpnl6sficvHJHm68qbqZ3A9A/0?wx_fmt=png)

本文参与 [腾讯云自媒体同步曝光计划](https://cloud.tencent.com/developer/support-plan)，分享自微信公众号。

原始发表：2025-06-16，如有侵权请联系 [cloudcommunity@tencent.com](mailto:cloudcommunity@tencent.com) 删除

---

---

> **LLM 系列导航**：[[Clippings/LLM 系列 索引|系列索引]] ｜ 上一篇：[[LLM 系列（二）：基础概念篇-腾讯云开发者社区-腾讯云|二：基础概念篇]] ｜ 下一篇：[[LLM 系列(四)：神奇的魔法数 27-腾讯云开发者社区-腾讯云|四：神奇的魔法数 27]]
