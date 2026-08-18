---
aliases: ["fine-tuning-llm-soft-prompts-2-prompt-tuning"]
---

When fine-tuning, do not only know LoRA: Soft Prompts for large models, part 2: Prompt Tuning

In 2021, the concept of large language models had not fully settled yet, and understanding of the field was still exploratory. Among many research directions, the Causal Language Model, a decoder-only model, was only one of them. Then GPT-3 attracted broad attention. Soon after, in April of the same year, Google introduced Prompt Tuning, originally tested on T5, which uses an encoder-decoder architecture. Later, Prompt Tuning also proved effective on other downstream tasks.

## Technical Breakdown

![alt text](../../../03-第三章-微调/assest/大模型微调之Soft prompts（二）Prompt-tuning/0.png)

Prompt Tuning is an efficient fine-tuning method that adapts a model to downstream tasks by adding special text prompts to the model input, without fully updating the pretrained model parameters. The essence of the method is that it adjusts model behavior by optimizing the input prompt parameters: the model adapts better to a new task while the main pretrained model parameters remain unchanged.

The key advantage of Prompt Tuning is parameter efficiency. Compared with traditional fine-tuning methods, Prompt Tuning requires updating only a small part of the parameters, meaning the parameters related to the prompt. This noticeably reduces compute-resource demand and training time. Prompt Tuning can also improve the model's generalization ability, because it lets the model adapt to new tasks without a large amount of labeled data.

The Prompt Tuning process usually includes these steps:

1. Choose a pretrained model as the base.
2. Design or choose a prompt template for the specific task.
3. Combine the prompt template with the input data to form a new input sequence.
4. Train on the pretrained model, updating only the prompt-template parameters.
5. Evaluate model quality on the test dataset.

## Intuitive Explanation

The key idea of Prompt Tuning is that prompt tokens have their own parameters, which can be updated independently. This means the pretrained model parameters can stay unchanged, and only the gradients of prompt-token embedding vectors are updated. The resulting performance is comparable to traditional full-model training, and as model size grows, Prompt Tuning quality also improves.

## References

<div id="refer-anchor-1"></div>

[1] [The Power of Scale for Parameter-Efficient Prompt Tuning](https://arxiv.org/abs/2104.08691)

## Follow my GitHub and WeChat channel [The Real Ship of Theseus]: no time to explain, hurry aboard!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

The repository has the original Markdown files, and everything is fully open source. Stars and forks are very welcome.


---

## 📚 相关概念

[[concepts/LoRA PEFT 微调|LoRA PEFT 微调]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[entities/Hugging Face|Hugging Face]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：微调
