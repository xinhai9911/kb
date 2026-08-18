---
aliases: ["fine-tuning-llm-adapters-2-lora"]
---

LoRA is not the only option: secrets of fine-tuning large models with Adapters, part 2: LoRA

LoRA (Low-Rank Adapter) [1](#refer-anchor-1) is one of the most popular PEFT methods. If you are just starting with PEFT, it is a good starting point. LoRA was originally developed for large language models, but because of its efficiency and effectiveness, it has also become a very popular method for training diffusion models.

## 1. Technical Breakdown

![alt text](<../../../03-第三章-微调/assest/大模型微调之Adapters（二）LoRA/lora_animated (1).gif>)

In large language models, weight matrices usually have very high dimensions, so fine-tuning involves a huge number of parameters. LoRA approximates the original weight matrix by decomposing these large matrices into the product of two smaller matrices, meaning a low-rank decomposition. The advantage is that only the parameters of these two smaller matrices need to be updated, not all parameters of the original large matrix. This greatly reduces the compute cost of fine-tuning.

The general process of applying LoRA looks like this:

1. Choose the model layers to fine-tune, for example self-attention layers in a Transformer model.
2. Add two new trainable matrices A and B to the weight matrices of these layers. Their dimensions are much smaller than the original weight matrix.
3. During the model forward pass, compute the new output as the sum of the original weight matrix and the product of A and B, where the product of A and B represents the low-rank update.
4. During training, update only A and B, while keeping the original weight matrix unchanged.

The advantage of LoRA is that it can greatly reduce the compute resources needed for fine-tuning while preserving model quality. This is especially valuable for research and applied scenarios with limited resources. LoRA can also be combined with other parameter-efficient fine-tuning techniques to improve fine-tuning efficiency even more.

It is important to note that the rank in LoRA, meaning the dimensions of matrices A and B, is an important hyperparameter and should be chosen for the specific task. A lower rank can further reduce the number of parameters, but the model may learn task-specific information less well. A higher rank may require more compute resources, but can provide better fine-tuning quality.

## 2. Intuitive Understanding

Imagine you are already an experienced chef: you have a full set of cooking skills, like a pretrained language model. Now, if you want to learn one new specific dish, such as sushi, you do not need to relearn all of cooking. You only need to learn a few new specialized skills, such as how to slice fish correctly. That is fine-tuning.

In LoRA, this process can be imagined as adding small new tools or techniques on top of your existing cooking skills, meaning the model weights. These new tools or techniques can be viewed as two small matrices A and B. Together, they help you make better sushi, but they do not contain all cooking knowledge by themselves. They only handle the key details needed for sushi.

## References

<div id="refer-anchor-1"></div>

[1] [LoRA: Low-Rank Adaptation of Large Language Models](https://arxiv.org/pdf/2106.09685)

## Follow my GitHub and WeChat channel [The Real Ship of Theseus]: no time to explain, hurry aboard!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

The repository has the original Markdown files, and everything is fully open source. Stars and forks are very welcome.


---

## 📚 相关概念

[[concepts/LoRA PEFT 微调|LoRA PEFT 微调]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[entities/Hugging Face|Hugging Face]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：微调
