# The LLM Repeater Problem

> The essence of humanity is repetition.

The "LLM repeater" problem means that when generating text, these models tend to repeat what has already been said or reproduce common expressions, instead of creating new and varied output. This happens especially often when fine-tuning open source large models.

![alt text](../../../08-第八章-大模型企业落地/assest/大模型复读机问题/00.png)

## Concrete symptoms

1. **Word or phrase repetition**: the model may repeatedly use the same words or phrases in generated text, especially when context is insufficient.

2. **Topic or viewpoint repetition**: when discussing a topic, the model may repeat already stated positions instead of giving new ideas or information.

3. **Style imitation**: the model may imitate the style or tone of training data instead of creating a new style for the current context.

4. **Lack of novelty**: because the model's training objective is usually to predict the next most likely word or phrase, the model may prefer safe and common text over innovative or unique content.

## Solution strategies

### Fine-tuning strategy

**Diverse training data**: make sure the model training data is diverse, and avoid overdependence on individual text types or styles.

### Generation strategy

**Improve generation strategy**: by tuning generation parameters such as temperature or top-k sampling, the model can be encouraged to produce more diverse output.

### Prompt engineering

**Context control**: provide rich and relevant contextual information so the model better understands the current task and generates more meaningful answers.

### Post-processing (backup strategy)

**Post-processing**: after text generation, post-processing can detect and reduce repeated content.

In enterprise applications, when we fine-tune an open source model, it is often the case that data volume and quality are insufficient, while hardware limits push us to choose a smaller model in an attempt to build a domain-specific LLM. In this situation, it is very easy to run into the "LLM repeater" problem.

## The essence of the problem: failed intelligence emergence

The essence of a large model is next-token prediction, meaning it is a language model. The reason a large model can be called intelligent is that intelligence emerges from it.

### Emergence

***Emergence***

Emergence is the appearance of unpredictable new patterns or behaviors in a complex system, arising from the interaction of many simple elements.

Snowflake formation is a good example of the beauty and complexity of emergence in nature: a single water molecule is simple, but when countless water molecules in the atmosphere meet cold air and begin to crystallize, they spontaneously organize into a complex crystalline snowflake structure with certain symmetry.

![alt text](../../../08-第八章-大模型企业落地/assest/大模型复读机问题/0.png)

Other examples of emergence include ant colony behavior, fish schooling, bird flight patterns, and other complex collective phenomena that arise from simple individual behavior.

### Intelligence emergence

***Intelligence Emergence***

Intelligence emergence is a key concept in complex systems science. It describes a situation where, in a system where many simple elements interact in a certain way, new and unpredictable properties or behaviors spontaneously appear. These properties do not belong to any individual element, but to the system as a whole.

In artificial intelligence, intelligence emergence usually means that as an AI model grows in scale, for example in parameter count, the model starts to show capabilities or behaviors that were not explicitly programmed in advance.

![alt text](../../../08-第八章-大模型企业落地/assest/大模型复读机问题/1.png)

Characteristics of intelligence emergence include adaptability, novelty, and complexity. For example, after training, large language models such as GPT-3 can show surprising creative abilities: writing poems, articles, and even generating code. These abilities were not explicitly defined in the training data or program, but were learned from large amounts of data.

Before GPT-3, people may have found it hard to imagine that an AI model could generate natural language so freely. But as model size and training data volume grow, intelligence emergence becomes more and more common.

## References

<div id="refer-anchor-1"></div>

## Follow my GitHub and WeChat Official Account. No time to explain, come aboard!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

The repository has the original Markdown files. Everything is fully open source, and stars and forks are very welcome!
