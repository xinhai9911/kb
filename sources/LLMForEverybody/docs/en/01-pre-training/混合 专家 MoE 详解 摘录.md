---
aliases: ["mixture-of-experts-moe-explained-excerpt"]
---

Mixture of Experts (MoE), detailed explanation excerpt

This article is an excerpt from https://huggingface.co/blog/zh/moe. The original title is "A Detailed Explanation of Mixture of Experts (MoE)." For quick reading, I selected the key paragraphs.

With the release of [Mixtral 8x7B](https://huggingface.co/mistralai/Mixtral-8x7B-v0.1), Transformer models called mixture-of-experts models, or MoEs, have attracted broad attention in the open source AI community.

## 1. Short Summary

Mixture of Experts (MoEs):

- pretrain faster than dense models;
- have higher inference speed compared with models with the same number of parameters;
- require a lot of VRAM, because all expert systems need to be loaded into memory;
- have many difficulties during fine-tuning, but [recent research](https://arxiv.org/pdf/2305.14705) shows that instruction tuning for mixture-of-experts models has strong potential.

## 2. What Is a Mixture of Experts?

Model size is one of the key factors in improving model quality. With a limited compute budget, training a larger model for fewer steps often gives a better result than training a smaller model for more steps.

One clear advantage of Mixture of Experts (MoE) is that these models can be pretrained efficiently with far fewer compute resources than dense models require. This means that, under the same compute budget, you can significantly increase model size or dataset size. Especially during pretraining, a mixture-of-experts model usually reaches the same quality level faster than a dense model.

So what is a Mixture of Experts (MoE)? As a model based on the Transformer architecture, a mixture of experts mainly consists of two key parts:

- Sparse MoE layers: these layers replace the feed-forward network (FFN) in a traditional Transformer model. An MoE layer contains several "experts" (for example, 8), each of which is itself a separate neural network. In practice, these experts are usually feed-forward networks (FFNs), but they can also be more complex network structures, or even MoE layers, forming a hierarchical MoE structure.

- Gate network or routing: this part decides which tokens are sent to which expert. For example, in the diagram below, the token "More" may be sent to the second expert, while the token "Parameters" may be sent to the first expert. Sometimes one token can be sent to several experts at once. Token routing is the key point when using MoE, because the router has trainable parameters and is pretrained with the rest of the network.

![alt text](<../../../01-第一章-预训练/assest/混合专家模型 (MoE) 详解（节选）/0.png>)

So in a Mixture of Experts (MoE), we replace each traditional feed-forward network (FFN) layer in the Transformer model with an MoE layer, which consists of two main parts: a gate network and a number of experts.

Although MoE provides several clear advantages, such as more efficient pretraining and faster inference compared with dense models, it also has challenges:

- Training challenges: although MoE allows more compute-efficient pretraining, during fine-tuning these models often face weak generalization and for a long time tended to overfit.

- Inference challenges: an MoE model may have a huge number of parameters, but during inference it only uses part of them. So its inference is faster than a dense model with the same number of parameters. However, the model has to load all parameters into memory, so memory requirements are very high. For example, an MoE such as Mixtral 8x7B needs enough VRAM to hold a dense model with 47B parameters. Why 47B and not 8 x 7B = 56B? Because in an MoE model, only the FFN layers are independent experts, while the rest of the model parameters are shared. Also, if each token uses only two experts, inference speed in FLOPs is closer to using a 12B model rather than a 14B one: although it runs 2x7B matrix multiplications, some layers remain shared.

## 3. What Is Sparsity?

The concept of sparsity uses the idea of conditional computation. In a traditional dense model, all parameters process all input data. Sparsity, by contrast, allows computation to happen only in certain parts of the whole system. This means not all parameters are activated or used for each input. Depending on the input's features or needs, only part of the parameter set is called and run.

Let's look more closely at Shazeer's contribution to applying Mixture of Experts (MoE) to translation. Conditional computation, meaning activating different parts of the network for each individual example, makes it possible to scale model size without increasing extra compute load. This strategy allows efficient use of thousands, or even more, experts in each MoE layer.

This sparse setup does create difficulties. For example, in MoE, although a large batch size is usually helpful for performance, when data flows through activated experts, the actual batch size may shrink. Suppose the input batch contains 10 tokens: five tokens may be routed to the same expert, while the remaining five tokens may be routed to different experts. This creates uneven batch-size distribution and low resource utilization. Later sections discuss other difficulties in running MoE efficiently and the corresponding solutions.

How do we solve this? A trainable gate network (G) decides which part of the input should be sent to which experts (E):

![alt text](<../../../01-第一章-预训练/assest/混合专家模型 (MoE) 详解（节选）/1.png>)

In this setup, all experts compute for all inputs, and then the result is weighted by the output of the gate network. But what happens if G, the gate-network output, equals 0? In that case, there is no need to compute the corresponding expert operation, so we can save compute resources. What is a typical gate function? Usually it is a simple network with softmax. This network learns to send the input to the right expert.

![alt text](<../../../01-第一章-预训练/assest/混合专家模型 (MoE) 详解（节选）/2.png>)

The work of Shazeer et al. also studied other gating mechanisms, including Noisy Top-K Gating. This gating method adds tunable noise, then keeps the top k values. More specifically:

1. Add some noise

![alt text](<../../../01-第一章-预训练/assest/混合专家模型 (MoE) 详解（节选）/3.png>)

2. Select and keep the top K values

![alt text](<../../../01-第一章-预训练/assest/混合专家模型 (MoE) 详解（节选）/4.png>)

3. Apply softmax

![alt text](<../../../01-第一章-预训练/assest/混合专家模型 (MoE) 详解（节选）/5.png>)

This sparsity gives several interesting properties. With a low k value, such as 1 or 2, training and inference can be faster than when many experts are activated. So why not choose only the top expert? The original hypothesis was that the input needs to be routed to more than one expert so the gate can learn effective routing, which means at least two experts should be selected. Switch Transformers explored this question in more detail.

## 4. How Does the Number of Experts Affect Pretraining?

Adding more experts can improve sample-processing efficiency and speed up model computation, but these benefits shrink as the number of experts grows, especially when the number reaches 256 or 512. At the same time, this means inference will require more VRAM to load the full model. Importantly, Switch Transformers show that properties observed in large models also apply to small models, even when each layer contains only 2, 4, or 8 experts.

## 5. Sparse vs. Dense: Which Should You Choose?

Sparse Mixture of Experts (MoE) is suitable for multi-machine scenarios with high throughput requirements. With fixed pretraining compute resources, sparse models often achieve better results. By contrast, in scenarios with less VRAM and lower throughput requirements, dense models are usually the better choice.

Note: directly comparing the parameter counts of sparse and dense models is incorrect, because these two model types are based on different concepts and count parameters differently.

## 6. A Few Interesting Research Directions

The first direction is trying to distill a sparse mixture of experts (SMoE) back into a dense model with fewer actual parameters but a similar equivalent parameter count.

MoE quantization is also an interesting research area. For example, QMoE (October 2023) quantizes MoE to less than 1 bit per parameter and compresses the storage needed for a 1.6-trillion-parameter Switch Transformer from 3.2 TB to only 160 GB.

In short, some interesting areas to explore are:

- distilling Mixtral into a dense model;
- studying expert-model merging techniques and their effect on inference time;
- trying experiments with extreme Mixtral quantization.

## Follow my GitHub and WeChat account: no time to explain, everyone aboard!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

The repository has the original Markdown files, and the project is fully open source. Stars and forks are very welcome.


---

## 📚 相关概念

[[concepts/Transformer 架构|Transformer 架构]] | [[concepts/分词器 LLM|分词器 LLM]] | [[concepts/LLM 训练 流水线|LLM 训练 流水线]] | [[concepts/RLHF DPO 对齐|RLHF DPO 对齐]] | [[concepts/LoRA PEFT 微调|LoRA PEFT 微调]] | [[concepts/多模态 LLM|多模态 LLM]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[entities/Hugging Face|Hugging Face]] | [[entities/DeepSeek|DeepSeek]] | [[entities/mindspore Transformer|mindspore Transformer]] | [[sources/Vaswani 2017 Attention|Vaswani 2017 Attention]] | [[sources/LLM 训练 流水线 指南|LLM 训练 流水线 指南]] | [[sources/DeepSeek 4 技术|DeepSeek 4 技术]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：预训练
