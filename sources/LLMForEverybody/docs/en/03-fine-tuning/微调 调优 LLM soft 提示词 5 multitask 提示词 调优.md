---
aliases: ["fine-tuning-llm-soft-prompts-5-multitask-prompt-tuning"]
---

LoRA is not the only option: secrets of fine-tuning large models with Soft Prompts, part 5: Multitask prompt tuning

In May 2023, two years later, soft prompts got a new method. When I first saw this approach, one phrase flashed through my mind: "a lot of moving parts, but the effect is impressive." My facial expression was roughly like this:

![alt text](../../../03-第三章-微调/assest/大模型微调之Soft prompts（五）Multitask prompt tuning/1.png)

If not for the completeness of this series, I might never have read this paper. I recommend everyone jump straight to the intuitive explanation section.

## Technical Breakdown

![alt text](../../../03-第三章-微调/assest/大模型微调之Soft prompts（五）Multitask prompt tuning/0.png)

Multitask Prompt Tuning (MPT) trains one prompt on data from different task types, and this prompt can be shared across different target tasks. Other existing methods train a separate soft prompt for each task, and then those prompts need to be retrieved or aggregated to adapt to the target task. MPT has two stages:

1. Source training: for each task, its soft prompt is decomposed into task-specific vectors. These task-specific vectors are multiplied to form another matrix W, and then a Hadamard product is used between W and the shared prompt matrix P to obtain a task-specific prompt matrix. The task-specific prompt is distilled into one shared prompt matrix for all tasks. This prompt is trained through multitask learning.

2. Target adaptation: to adapt the shared prompt to the target task, the target prompt is initialized and represented as the Hadamard product of the shared prompt matrix and a task-specific low-rank prompt matrix, meaning an element-wise product.

## Intuitive Explanation

Imagine a student needs to prepare for several different exams at once, such as math, history, and natural science. In MPT, this student is like the pretrained language model, and the exams are like different downstream tasks.

1. Learning shared knowledge: at the beginning of the semester, the teacher gives the student a set of general knowledge useful for all subjects, such as problem-solving techniques, writing methods, or analytical frameworks. This is like MPT training a shared prompt that helps the model understand different task types.

2. Reviewing for specific subjects: then, for each subject exam, the teacher may give the student special preparation advice or key topics based on that subject's characteristics. In MPT, this means the model slightly adapts the shared prompt to each task's features, so it fits the task better.

3. Applying it during the exam: during the exam, the student uses the shared knowledge already learned plus subject-specific preparation points to answer questions. In MPT, when facing a new task, the model uses the shared prompt it has already learned and adjusts it to the task requirements to produce the right output.

## References

<div id="refer-anchor-1"></div>

[1] [Multitask Prompt Tuning Enables Parameter-Efficient Transfer Learning](https://arxiv.org/abs/2303.02861)

## Follow my GitHub and WeChat channel [The Real Ship of Theseus]: no time to explain, hurry aboard!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

The repository has the original Markdown files, and everything is fully open source. Stars and forks are very welcome.


---

## 📚 相关概念

[[concepts/LoRA PEFT 微调|LoRA PEFT 微调]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[entities/Hugging Face|Hugging Face]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：微调
