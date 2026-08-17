LoRA is not the only option: secrets of fine-tuning large models with Soft Prompts, part 3: Prefix-Tuning

In the same year as Prompt Tuning, 2021, Prefix-Tuning was proposed. It adds trainable prompt vectors at the prefix position of the model input. The advantage of this method is that it allows different prompts to be set for different tasks without changing the model structure.

## Technical Breakdown

![alt text](../../../03-第三章-微调/assest/大模型微调之Soft prompts（三）Prefix-tuning/0.png)

Prefix Tuning is a parameter-efficient fine-tuning technique for natural language generation tasks. Its key idea is to add a set of task-specific continuous vectors before the model input sequence. These vectors are called the prefix. The prefix vectors are trained, while the remaining parameters of the pretrained language model (PLM) stay frozen.

In Prefix Tuning, the model input includes not only the original task input, but also these prefix vectors. In autoregressive language models, such as GPT-2, the prefix is added to the beginning of the input sequence, forming a new input sequence. In encoder-decoder models, such as BART, the prefix is added not only to the beginning of the input sequence, but also to the decoder input. Because of this, when processing the input sequence, each layer's input contains additional prefix vectors, which helps adapt the model to the downstream task.

One key advantage of Prefix Tuning is parameter efficiency. The method updates only a small portion of parameters, meaning the prefix vectors, and does not need to update all model parameters. This greatly reduces compute and storage requirements. Also, because only prefix vectors are updated, Prefix Tuning is easier to adapt to multiple tasks: there is no need to train and store a full copy of the model for every task.

In practice, Prefix Tuning has shown effectiveness in different natural language processing tasks, including text generation and summarization. By adding trainable prefix vectors to the model input, it lets the model adapt better to specific downstream tasks without changing the original parameters.

## Intuitive Explanation

The main difference between Prefix-Tuning and Prompt Tuning is that prefix parameters in Prefix-Tuning are inserted into all model layers, while Prompt Tuning adds prompt parameters only at the model embedding layer.

## References

<div id="refer-anchor-1"></div>

[1] [Prefix-Tuning: Optimizing Continuous Prompts for Generation](https://arxiv.org/abs/2101.00190)

## Follow my GitHub and WeChat channel [The Real Ship of Theseus]: no time to explain, hurry aboard!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

The repository has the original Markdown files, and everything is fully open source. Stars and forks are very welcome.
